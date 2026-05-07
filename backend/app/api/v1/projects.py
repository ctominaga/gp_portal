"""CRUD de Projects + upload de Proposals."""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from jump_storage.factory import get_storage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_role
from app.models import Proposal, ProposalStatus, Role, TaskType, User
from app.models.domain import Project
from app.queue.publisher import enqueue_agent_job
from app.schemas.project import ProjectCreate, ProjectPublic, ProposalPublic
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
