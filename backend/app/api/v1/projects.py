"""CRUD de Projects + upload de Proposals + encerramento (F5.3 — v3.1 §10.4)."""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from jump_storage.factory import get_storage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_role
from app.models import (
    Baseline,
    BaselineStatus,
    ProjectRetrospective,
    ProjectStatus,
    Proposal,
    ProposalStatus,
    Report,
    ReportStatus,
    Risk,
    Role,
    ScopeChange,
    ScopeChangeStatus,
    TaskType,
    User,
)
from app.models.domain import Project
from app.queue.publisher import enqueue_agent_job
from app.schemas.project import ProjectCreate, ProjectPublic, ProposalPublic
from app.schemas.retrospective import (
    MaterializedRiskItem,
    ProjectCloseResult,
    RetrospectiveCreate,
    RetrospectivePublic,
)
from app.services.worker_stub import schedule_extraction

router = APIRouter(tags=["projects"])

# Roles que podem criar/listar projetos. CLIENT só vê o próprio (rota separada em F4).
_INTERNAL_ROLES = (Role.GP, Role.PMO, Role.OPERATOR)
_GP_ONLY = (Role.GP,)


@router.post("/projects", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    user: User = Depends(require_any_role(Role.GP, Role.PMO)),
    db: AsyncSession = Depends(get_db),
) -> Project:
    client_user_id: uuid.UUID | None = None
    if payload.client_user_email:
        client = (
            await db.execute(select(User).where(User.email == payload.client_user_email.lower()))
        ).scalar_one_or_none()
        if not client or client.role != Role.CLIENT:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "client_user_email deve apontar para usuário existente com role CLIENT",
            )
        client_user_id = client.id

    project = Project(
        name=payload.name,
        client_name=payload.client_name,
        description=payload.description,
        gp_user_id=user.id if user.role == Role.GP else user.id,  # GP vira o owner
        client_user_id=client_user_id,
        started_at=payload.started_at,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectPublic])
async def list_projects(
    user: User = Depends(require_any_role(*_INTERNAL_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> list[Project]:
    """GP vê os próprios; PMO/OPERATOR veem todos."""
    stmt = select(Project)
    if user.role == Role.GP:
        stmt = stmt.where(Project.gp_user_id == user.id)
    return list((await db.execute(stmt)).scalars().all())


@router.get("/projects/{project_id}", response_model=ProjectPublic)
async def get_project(
    project_id: uuid.UUID,
    user: User = Depends(require_any_role(*_INTERNAL_ROLES, Role.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> Project:
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto não encontrado")
    # CLIENT só vê o próprio projeto
    if user.role == Role.CLIENT and project.client_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cliente não tem acesso a esse projeto")
    if user.role == Role.GP and project.gp_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "GP não é dono desse projeto")
    return project


@router.get("/projects/{project_id}/health-score-breakdown")
async def get_health_score_breakdown(
    project_id: uuid.UUID,
    user: User = Depends(require_any_role(*_INTERNAL_ROLES, Role.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Breakdown dos 5 componentes do Health Score (spec v3.1 §10.3).

    Usado pelo tooltip do gauge no dashboard PMO e por debug pelo PMO.
    """
    from app.services import health_score as _hs

    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto não encontrado")
    if user.role == Role.CLIENT and project.client_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cliente não tem acesso a esse projeto")
    if user.role == Role.GP and project.gp_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "GP não é dono desse projeto")

    breakdown = await _hs.compute_for_project(db, project_id)
    return breakdown.as_dict()


@router.post(
    "/projects/{project_id}/proposals",
    response_model=ProposalPublic,
    status_code=status.HTTP_201_CREATED,
)
async def upload_proposal(
    project_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(require_any_role(*_GP_ONLY)),
    db: AsyncSession = Depends(get_db),
) -> Proposal:
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto não encontrado")
    if project.gp_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "GP não é dono desse projeto")

    raw = await file.read()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "arquivo vazio")
    sha256 = hashlib.sha256(raw).hexdigest()

    # Próxima versão
    last_version = (
        await db.execute(
            select(Proposal.version)
            .where(Proposal.project_id == project_id)
            .order_by(Proposal.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    next_version = (last_version or 0) + 1

    key = f"proposals/{project_id}/v{next_version}.pdf"
    storage = get_storage()
    storage.put(
        raw,
        key,
        content_type=file.content_type or "application/pdf",
        metadata={"project_id": str(project_id), "version": str(next_version)},
    )

    proposal = Proposal(
        project_id=project_id,
        version=next_version,
        file_url=key,
        file_sha256=sha256,
        original_filename=file.filename or f"v{next_version}.pdf",
        size_bytes=len(raw),
        status=ProposalStatus.PENDING_EXTRACTION,
        uploaded_by_id=user.id,
    )
    db.add(proposal)
    await db.flush()
    await db.refresh(proposal)

    # Publica job de extração no Redis. Se app.state.redis estiver indisponível
    # (CI sem Redis), só registra log e segue — vai ser retomado pelo agendador.
    redis = getattr(request.app.state, "redis", None)
    run_id: str | None = None
    if redis is not None:
        log = await enqueue_agent_job(
            db=db,
            redis=redis,
            task_type=TaskType.PROPOSAL_EXTRACTION,
            project_id=project_id,
            proposal_id=proposal.id,
            input_files=[{"key": key, "kind": "proposal"}],
            output_path_hint=f"baseline-{proposal.id}.json",
            timeout_hard_s=900,
            heartbeat_s=30,
        )
        run_id = log.run_id
    await db.commit()

    # Worker stub agenda a transição pending_extraction → extracted após N segundos.
    # Em F2.6 quando o worker real assumir, basta STUB_WORKER_ENABLED=false.
    schedule_extraction(proposal.id, run_id=run_id)

    return proposal


@router.get(
    "/projects/{project_id}/proposals/{proposal_id}",
    response_model=ProposalPublic,
)
async def get_proposal(
    project_id: uuid.UUID,
    proposal_id: uuid.UUID,
    user: User = Depends(require_any_role(*_INTERNAL_ROLES, Role.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> Proposal:
    prop = (
        await db.execute(
            select(Proposal).where(Proposal.id == proposal_id, Proposal.project_id == project_id)
        )
    ).scalar_one_or_none()
    if not prop:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "proposta não encontrada")
    return prop


# ---------- F5.3 — Encerramento de projeto + Retrospectiva (v3.1 §10.4) ----------


# Status de Report que indicam "trabalho ainda em fluxo" — bloqueiam o
# encerramento do projeto. CLIENT_RELEASED e ARCHIVED são terminais e OK.
#
# DESVIO INTENCIONAL DA SPEC v3.1 §10.4:
# Spec lista DRAFT/SUBMITTED/PMO_APPROVED como bloqueadores.
# NEEDS_REVISION adicionado porque é trabalho pendente do GP
# (re-submissão necessária). Permitir encerrar projeto com report
# em NEEDS_REVISION cria órfão semântico (PMO devolveu pedindo
# correção e o GP simplesmente fecha o projeto sem responder).
# ADR registrado em docs/decisoes.md (2026-05-12).
_REPORT_BLOCKING_STATUSES: tuple[ReportStatus, ...] = (
    ReportStatus.DRAFT,
    ReportStatus.SUBMITTED,
    ReportStatus.PMO_APPROVED,
    ReportStatus.NEEDS_REVISION,
)


@router.post(
    "/projects/{project_id}/close",
    response_model=ProjectCloseResult,
)
async def close_project(
    project_id: uuid.UUID,
    payload: RetrospectiveCreate,
    user: User = Depends(require_any_role(Role.GP)),
    db: AsyncSession = Depends(get_db),
) -> ProjectCloseResult:
    """Encerra o projeto com retrospectiva estruturada (spec v3.1 §10.4).

    Ação **irreversível** via API. Reabertura é caminho operacional
    excepcional (intervenção direta no banco), não exposto. Decisão F5.3
    documentada no ADR `decisoes.md`.

    Validações (cascata Q4 — primeira falha vence):
      1. Projeto existe (404)
      2. user é GP-dono do projeto (403)
      3. Project.status não é CLOSED nem PAUSED (409 explicativo)
      4. Sem ScopeChange PROPOSED do projeto (409)
      5. Sem Reports em DRAFT/SUBMITTED/PMO_APPROVED/NEEDS_REVISION (409)
      6. Sem Baseline DRAFT com proposal.version > 1 (409)
      7. Cada `materialized_risks[*].risk_id` existe e pertence ao
         projeto (422)

    Side-effects (transação única — tudo ou nada):
      - Cria ProjectRetrospective com 4 campos + materialized_risks
      - Project.status: ACTIVE → CLOSED
      - Project.ended_at: today (date lógica do encerramento)
    """
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto não encontrado")

    # 2) GP-dono
    if project.gp_user_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Apenas o GP responsável pelo projeto pode encerrá-lo.",
        )

    # 3) Status do projeto
    if project.status == ProjectStatus.CLOSED:
        when = project.ended_at.isoformat() if project.ended_at else "data desconhecida"
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Projeto já está encerrado em {when}.",
        )
    if project.status == ProjectStatus.PAUSED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Projeto está pausado. Reative antes de encerrar.",
        )
    # Sanity (ACTIVE é o único restante; se aparecer outro estado no enum
    # futuramente, falhar explícito em vez de seguir).
    if project.status != ProjectStatus.ACTIVE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Projeto em estado {project.status.value} não pode ser encerrado.",
        )

    # 4) ScopeChanges PROPOSED do projeto
    scope_pending = (
        await db.execute(
            select(func.count())
            .select_from(ScopeChange)
            .where(
                ScopeChange.project_id == project_id,
                ScopeChange.status == ScopeChangeStatus.PROPOSED,
            )
        )
    ).scalar_one()
    if scope_pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Há {scope_pending} transição(ões) de escopo aguardando aprovação do PMO. "
            "Aprovem ou rejeitem antes de encerrar o projeto.",
        )

    # 5) Reports em fluxo
    reports_pending = (
        await db.execute(
            select(func.count())
            .select_from(Report)
            .where(
                Report.project_id == project_id,
                Report.status.in_(_REPORT_BLOCKING_STATUSES),
            )
        )
    ).scalar_one()
    if reports_pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Há {reports_pending} report(s) em revisão "
            "(DRAFT/SUBMITTED/PMO_APPROVED/NEEDS_REVISION). "
            "Conclua o fluxo de aprovação antes de encerrar o projeto.",
        )

    # 6) Baseline DRAFT v2+ (transição pendente que não tem ScopeChanges
    # PROPOSED — caso de baseline criado mas worker ainda não computou diff,
    # ou ScopeChanges já decididos mas baseline ficou em DRAFT por algum motivo)
    baseline_pending = (
        await db.execute(
            select(Baseline, Proposal.version)
            .join(Proposal, Baseline.proposal_id == Proposal.id)
            .where(
                Baseline.project_id == project_id,
                Baseline.status == BaselineStatus.DRAFT,
                Proposal.version > 1,
            )
        )
    ).first()
    if baseline_pending:
        _, version = baseline_pending
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Há baseline v{version} aguardando decisão de mudança de escopo. "
            "Resolva a transição antes de encerrar.",
        )

    # 7) Validar materialized_risks (1 query para todos os IDs).
    if payload.materialized_risks:
        risk_ids = [item.risk_id for item in payload.materialized_risks]
        valid_ids = set(
            (
                await db.execute(
                    select(Risk.id)
                    .join(Report, Report.id == Risk.report_id)
                    .where(
                        Risk.id.in_(risk_ids),
                        Report.project_id == project_id,
                    )
                )
            ).scalars().all()
        )
        invalid = [str(rid) for rid in risk_ids if rid not in valid_ids]
        if invalid:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Risk IDs inexistentes ou não pertencentes a este projeto: "
                + ", ".join(invalid),
            )

    # Tudo validado — cria retrospectiva e marca projeto como encerrado.
    retro = ProjectRetrospective(
        project_id=project_id,
        delivered_vs_proposed=payload.delivered_vs_proposed,
        would_do_differently=payload.would_do_differently,
        client_feedback=payload.client_feedback,
        materialized_risks=[item.model_dump(mode="json") for item in payload.materialized_risks],
        created_by_id=user.id,
    )
    db.add(retro)

    project.status = ProjectStatus.CLOSED
    project.ended_at = date.today()

    await db.commit()
    await db.refresh(retro)
    await db.refresh(project)

    return ProjectCloseResult(
        project_id=project.id,
        status=project.status,
        ended_at=project.ended_at,
        retrospective=RetrospectivePublic(
            id=retro.id,
            project_id=retro.project_id,
            delivered_vs_proposed=retro.delivered_vs_proposed,
            would_do_differently=retro.would_do_differently,
            client_feedback=retro.client_feedback,
            materialized_risks=[
                MaterializedRiskItem(**item) for item in retro.materialized_risks
            ],
            created_by_id=retro.created_by_id,
            created_at=retro.created_at,
        ),
    )


@router.get(
    "/projects/{project_id}/retrospective",
    response_model=RetrospectivePublic,
)
async def get_retrospective(
    project_id: uuid.UUID,
    user: User = Depends(require_any_role(Role.GP, Role.PMO, Role.OPERATOR, Role.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> RetrospectivePublic:
    """Lê a retrospectiva de um projeto encerrado (F5.3 — v3.1 §10.4).

    Acesso mais permissivo que o `POST /close`:
      - GP-dono do projeto
      - PMO / OPERATOR (visão portfólio)
      - CLIENT-dono do projeto (transparência do encerramento)

    404 quando o projeto não existe OU quando ainda não foi encerrado.
    """
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "projeto não encontrado")

    if user.role == Role.GP and project.gp_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "GP não é dono desse projeto")
    if user.role == Role.CLIENT and project.client_user_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "cliente não tem acesso a esse projeto"
        )

    retro = (
        await db.execute(
            select(ProjectRetrospective).where(
                ProjectRetrospective.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if not retro:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "retrospectiva não encontrada (projeto não foi encerrado)",
        )

    return RetrospectivePublic(
        id=retro.id,
        project_id=retro.project_id,
        delivered_vs_proposed=retro.delivered_vs_proposed,
        would_do_differently=retro.would_do_differently,
        client_feedback=retro.client_feedback,
        materialized_risks=[MaterializedRiskItem(**item) for item in retro.materialized_risks],
        created_by_id=retro.created_by_id,
        created_at=retro.created_at,
    )
