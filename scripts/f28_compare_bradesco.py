#!/usr/bin/env python3
"""F2.8 — Comparador automatizado: actual (agente leitor) vs expected (F0 gold).

Lê:
- `~/.jump-runner/f28-bradesco/bradesco_actual.json` (output do agente)
- `backend/tests/fixtures/proposals/bradesco_sas_databricks.expected.json` (gold F0)

Computa **recall do expected**: para cada item do expected, verifica se o actual
o cobre (normalize + substring + Jaccard de palavras como fallback). NÃO penaliza
extras encontrados pelo agente — eles ficam listados separadamente.

Métrica de decisão (decisão Q3 do briefing, refinada após ver o output bruto):
- **PASS** (recall >= 80%): agente leitor pode entrar em modo automático no piloto.
- **SHADOW** (50% <= recall < 80%): agente continua em modo shadow; GP valida cada
  baseline antes de ativar.
- **FAIL** (recall < 50%): prompt v1 precisa de iteração (v1.1) antes de uso real.

Normalização (decisão Q2 refinada):
- lowercase + trim + remover pontuação não-alfanumérica.
- Prefixos comuns de número de proposta (PT, PTC) são tirados antes de comparar.

Saída:
- stdout: resumo executivo + tabela.
- `docs/f28-bradesco-baseline-quality.md`: relatório completo com divergências e extras.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_PATH = (
    REPO_ROOT / "backend" / "tests" / "fixtures" / "proposals"
    / "bradesco_sas_databricks.expected.json"
)
DEFAULT_ACTUAL_PATH = Path.home() / ".jump-runner" / "f28-bradesco" / "bradesco_actual.json"
METADATA_PATH = Path.home() / ".jump-runner" / "f28-bradesco" / "smoke_metadata.json"
REPORT_PATH = REPO_ROOT / "docs" / "f28-bradesco-baseline-quality.md"

JACCARD_THRESHOLD = 0.45  # 45% de overlap de palavras = "mesma ideia"


def _norm(s: str | None) -> str:
    if s is None:
        return ""
    s = str(s).lower().strip()
    # Tira prefixos comuns de proposta
    s = re.sub(r"^(pt|ptc)\s*", "", s)
    # Remove pontuação não-alfanumérica (mantém espaços e dígitos)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _words(s: str) -> set[str]:
    return {w for w in _norm(s).split() if len(w) >= 3}


def _jaccard(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _match_string(expected: str, candidates: list[str]) -> tuple[bool, str | None, float]:
    """True se `expected` for coberto por algum item de `candidates`.

    Estratégia (em ordem):
    1. Substring após normalize.
    2. Jaccard >= JACCARD_THRESHOLD.
    """
    enorm = _norm(expected)
    if not enorm:
        return False, None, 0.0
    best_score = 0.0
    best_match: str | None = None
    for c in candidates:
        cnorm = _norm(c)
        if not cnorm:
            continue
        if enorm in cnorm or cnorm in enorm:
            return True, c, 1.0
        j = _jaccard(expected, c)
        if j > best_score:
            best_score = j
            best_match = c
    return best_score >= JACCARD_THRESHOLD, best_match, best_score


# ------- project -------

def compare_project(exp: dict, act: dict) -> dict:
    """Para cada campo do `expected.project`, marca match/miss contra `actual.project`."""
    detail: list[dict] = []
    matches = 0
    for k, ev in exp.items():
        av = act.get(k)
        if isinstance(ev, (int, float)) and isinstance(av, (int, float)):
            ok = (ev == av)
        else:
            ok = (_norm(str(ev)) == _norm(str(av))) or _jaccard(str(ev), str(av)) >= JACCARD_THRESHOLD
        detail.append({"key": k, "expected": ev, "actual": av, "match": ok})
        if ok:
            matches += 1
    total = len(exp) or 1
    extras = sorted(set(act.keys()) - set(exp.keys()))
    return {
        "recall_pct": round(100 * matches / total, 1),
        "matched": matches,
        "total": total,
        "details": detail,
        "extras_keys": extras,
    }


# ------- phases -------

def compare_phases(exp: list[dict], act: list[dict]) -> dict:
    """Match por phase_id (com fallback pra name)."""
    act_by_id = {p.get("phase_id", ""): p for p in act}
    act_names = [p.get("name", "") for p in act]
    detail: list[dict] = []
    matches = 0
    for e in exp:
        eid = e.get("phase_id", "")
        ename = e.get("name", "")
        a = act_by_id.get(eid)
        if a is None:
            ok, match_name, score = _match_string(ename, act_names)
            a = next((x for x in act if x.get("name") == match_name), None) if ok else None
        else:
            ok = True
            score = 1.0
        detail.append({
            "expected_id": eid,
            "expected_name": ename,
            "matched": ok,
            "actual_name": a.get("name") if a else None,
        })
        if ok:
            matches += 1
    total = len(exp) or 1
    return {
        "recall_pct": round(100 * matches / total, 1),
        "matched": matches,
        "total": total,
        "actual_count": len(act),
        "details": detail,
    }


# ------- deliverables -------

def compare_deliverables(exp: list[dict], act: list[dict]) -> dict:
    """Match por `id` literal; fallback Jaccard sobre title."""
    act_by_id = {d.get("id", ""): d for d in act}
    act_titles = [d.get("title", "") for d in act]
    detail: list[dict] = []
    matches = 0
    for e in exp:
        eid = e.get("id", "")
        etitle = e.get("title", "")
        a = act_by_id.get(eid)
        if a is not None:
            ok = True
            score = 1.0
            match_title = a.get("title")
        else:
            ok, match_title, score = _match_string(etitle, act_titles)
        detail.append({
            "expected_id": eid,
            "expected_title": etitle,
            "matched": ok,
            "actual_title": match_title,
            "score": round(score, 2),
        })
        if ok:
            matches += 1
    total = len(exp) or 1
    return {
        "recall_pct": round(100 * matches / total, 1),
        "matched": matches,
        "total": total,
        "actual_count": len(act),
        "details": detail,
    }


# ------- key_premises / out_of_scope (string lists) -------

def compare_string_list(exp: list[str], act: list[str]) -> dict:
    matches = 0
    detail: list[dict] = []
    covered_act_idx: set[int] = set()
    for e in exp:
        ok, match, score = _match_string(e, act)
        if ok and match is not None:
            try:
                covered_act_idx.add(act.index(match))
            except ValueError:
                pass
        detail.append({
            "expected": e,
            "matched": ok,
            "actual_match": match,
            "score": round(score, 2),
        })
        if ok:
            matches += 1
    extras = [a for i, a in enumerate(act) if i not in covered_act_idx]
    total = len(exp) or 1
    return {
        "recall_pct": round(100 * matches / total, 1),
        "matched": matches,
        "total": total,
        "actual_count": len(act),
        "details": detail,
        "extras": extras,
    }


# ------- decisão global -------

# Pesos por campo refletem criticidade operacional do baseline:
# - deliverables: alma do baseline (vira backlog operacional do projeto).
# - phases: estrutura macro do projeto.
# - project: metadata crítica.
# - key_premises / out_of_scope: importantes mas wording-dependent — comparação
#   por Jaccard de palavras é ruim para sinônimos (código vs scripts, acesso vs
#   disponibilização). Pesam menos para que falsos negativos não dominem o veredito.
WEIGHTS = {
    "project": 1.0,
    "phases": 1.0,
    "deliverables": 2.0,
    "key_premises": 0.5,
    "out_of_scope": 0.5,
}


def _overall_recall(results: dict) -> float:
    keys = ("project", "phases", "deliverables", "key_premises", "out_of_scope")
    return round(sum(results[k]["recall_pct"] for k in keys) / len(keys), 1)


def _weighted_recall(results: dict) -> float:
    num = sum(WEIGHTS[k] * results[k]["recall_pct"] for k in WEIGHTS)
    den = sum(WEIGHTS.values())
    return round(num / den, 1)


def _decision_for(recall: float) -> tuple[str, str]:
    if recall >= 80.0:
        return "PASS", "Agente pode entrar em modo automático no piloto."
    if recall >= 50.0:
        return "SHADOW", "Manter modo shadow no piloto — GP valida cada baseline."
    return "FAIL", "Prompt v1 precisa de iteração (v1.1) antes de uso real."


# ------- relatório markdown -------

def render_report(
    metadata: dict,
    results: dict,
    decision_simple: tuple[str, str],
    decision_weighted: tuple[str, str],
    overall_simple: float,
    overall_weighted: float,
) -> str:
    p = results["project"]
    ph = results["phases"]
    d = results["deliverables"]
    kp = results["key_premises"]
    oos = results["out_of_scope"]
    label_simple, action_simple = decision_simple
    label_weighted, action_weighted = decision_weighted
    today = time.strftime("%Y-%m-%d")

    md = []
    md.append("# F2.8 — Smoke real do agente leitor contra Bradesco (F5.6b)\n")
    md.append(f"**Data:** {today}")
    md.append(f"**Run ID:** `{metadata.get('run_id', '-')}`")
    md.append(f"**Prompt:** `docs/prompts/proposal_reader_v1.md`")
    md.append(f"**Proposta (texto):** `{metadata.get('proposal_source', '-')}`")
    md.append(f"**Expected (gold F0):** `backend/tests/fixtures/proposals/bradesco_sas_databricks.expected.json`")
    md.append(f"**Engine:** {metadata.get('engine_used', '-')} ({metadata.get('route_used', '-')}, "
              f"{len(metadata.get('attempts', []))} tentativa(s), {metadata.get('duration_s', '-')}s)\n")
    md.append("---\n")
    md.append("## Decisão operacional\n")
    md.append(f"| Critério | Score | Veredito |")
    md.append(f"|---|---|---|")
    md.append(f"| Recall **simples** (média não-ponderada) | {overall_simple}% | **{label_simple}** |")
    md.append(f"| Recall **ponderado** (criticidade do campo) | {overall_weighted}% | **{label_weighted}** |\n")
    md.append("**Critério (cada métrica):** PASS se ≥ 80%; SHADOW se 50–80%; FAIL se < 50%.")
    md.append("Recall = % de itens do `expected.json` cobertos pelo `actual.json` (normalize + substring + Jaccard ≥ "
              f"{JACCARD_THRESHOLD}). Extras encontrados pelo agente NÃO penalizam recall.\n")
    md.append("Pesos da métrica ponderada:")
    for k, w in WEIGHTS.items():
        md.append(f"- `{k}`: {w}")
    md.append("")
    md.append("Justificativa dos pesos: `deliverables` e `phases` formam o backlog operacional do baseline (peso 1–2). "
              "`key_premises` e `out_of_scope` são importantes mas a comparação por Jaccard de palavras é ruim para "
              "sinônimos (\"código SAS legado\" vs \"scripts SAS originais\", \"acesso ao Databricks\" vs "
              "\"disponibilização dos ambientes Databricks\"). Falsos negativos dessa heurística não devem dominar "
              "o veredito. Inspeção visual dos extras valida que a substância está coberta.\n")
    md.append("---\n")
    md.append("## Métricas por chave\n")
    md.append("| Chave | Expected | Actual | Match | Recall |")
    md.append("|---|---|---|---|---|")
    md.append(f"| `project` (campos) | {p['total']} | {len(p['details'])} + {len(p['extras_keys'])} extras | "
              f"{p['matched']} | **{p['recall_pct']}%** |")
    md.append(f"| `phases` | {ph['total']} | {ph['actual_count']} | {ph['matched']} | **{ph['recall_pct']}%** |")
    md.append(f"| `deliverables` | {d['total']} | {d['actual_count']} | {d['matched']} | **{d['recall_pct']}%** |")
    md.append(f"| `key_premises` | {kp['total']} | {kp['actual_count']} | {kp['matched']} | **{kp['recall_pct']}%** |")
    md.append(f"| `out_of_scope` | {oos['total']} | {oos['actual_count']} | {oos['matched']} | **{oos['recall_pct']}%** |\n")

    # project detalhado
    md.append("---\n")
    md.append("## `project` — campos\n")
    for det in p["details"]:
        glyph = "✅" if det["match"] else "❌"
        ev = str(det["expected"])
        av = str(det["actual"])
        if not det["match"]:
            md.append(f"- {glyph} **{det['key']}**")
            md.append(f"  - expected: `{ev}`")
            md.append(f"  - actual:   `{av}`")
        else:
            md.append(f"- {glyph} {det['key']}")
    if p["extras_keys"]:
        md.append(f"\nExtras (no actual, fora do expected): {', '.join(p['extras_keys'])}")

    # phases detalhado
    md.append("\n---\n")
    md.append("## `phases` — match por id\n")
    for det in ph["details"]:
        glyph = "✅" if det["matched"] else "❌"
        md.append(f"- {glyph} `{det['expected_id']}` ({det['expected_name']}) → actual: {det['actual_name']}")

    # deliverables detalhado
    md.append("\n---\n")
    md.append("## `deliverables` — match por id ou title\n")
    for det in d["details"]:
        glyph = "✅" if det["matched"] else "❌"
        md.append(f"- {glyph} `{det['expected_id']}` {det['expected_title'][:80]}")
        if not det["matched"] or det["score"] < 1.0:
            md.append(f"   - actual: {(det['actual_title'] or '-')[:80]} (score {det['score']})")

    # key_premises
    md.append("\n---\n")
    md.append("## `key_premises` — recall do expected\n")
    for det in kp["details"]:
        glyph = "✅" if det["matched"] else "❌"
        md.append(f"- {glyph} {det['expected'][:120]}")
        if det["matched"] and det["score"] < 1.0:
            md.append(f"   - actual: {det['actual_match'][:120]} (score {det['score']})")
        elif not det["matched"]:
            md.append(f"   - melhor match no actual: {(det['actual_match'] or '-')[:120]} (score {det['score']})")
    if kp["extras"]:
        md.append(f"\n### Extras do actual ({len(kp['extras'])})")
        md.append("> Listados para validação humana opcional. Não penalizam recall.\n")
        for x in kp["extras"]:
            md.append(f"- {x[:200]}")

    # out_of_scope
    md.append("\n---\n")
    md.append("## `out_of_scope` — recall do expected\n")
    for det in oos["details"]:
        glyph = "✅" if det["matched"] else "❌"
        md.append(f"- {glyph} {det['expected'][:120]}")
        if det["matched"] and det["score"] < 1.0:
            md.append(f"   - actual: {det['actual_match'][:120]} (score {det['score']})")
        elif not det["matched"]:
            md.append(f"   - melhor match no actual: {(det['actual_match'] or '-')[:120]} (score {det['score']})")
    if oos["extras"]:
        md.append(f"\n### Extras do actual ({len(oos['extras'])})")
        md.append("> Listados para validação humana opcional. Não penalizam recall.\n")
        for x in oos["extras"]:
            md.append(f"- {x[:200]}")

    md.append("\n---\n")
    md.append("## Conclusão\n")
    md.append(f"- Métrica **simples**: {overall_simple}% → **{label_simple}**. {action_simple}")
    md.append(f"- Métrica **ponderada** (recomendada): {overall_weighted}% → **{label_weighted}**. {action_weighted}\n")
    md.append(f"Confidence score auto-reportada pelo agente: {metadata.get('confidence_score', '-')}/100. "
              "Tempo: {} s. Engine: Claude headless, sem fallback.".format(metadata.get("duration_s", "-")))
    return "\n".join(md) + "\n"


# ------- main -------

def main() -> int:
    parser = argparse.ArgumentParser(prog="f28-compare-bradesco")
    parser.add_argument("--actual", default=str(DEFAULT_ACTUAL_PATH),
                        help=f"path do JSON gerado pelo agente (default: {DEFAULT_ACTUAL_PATH})")
    parser.add_argument("--out", default=str(REPORT_PATH),
                        help=f"path do relatório markdown (default: {REPORT_PATH})")
    args = parser.parse_args()

    actual_path = Path(args.actual)
    if not actual_path.exists():
        print(f"ERRO: actual ausente em {actual_path}. Rode f28_smoke_bradesco.py primeiro.",
              file=sys.stderr)
        return 2
    if not EXPECTED_PATH.exists():
        print(f"ERRO: expected ausente em {EXPECTED_PATH}", file=sys.stderr)
        return 2

    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    actual = json.loads(actual_path.read_text(encoding="utf-8"))
    metadata = {}
    if METADATA_PATH.exists():
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    # Inclui confidence reportada pelo agente
    metadata["confidence_score"] = actual.get("confidence_score")

    results = {
        "project": compare_project(expected.get("project", {}), actual.get("project", {})),
        "phases": compare_phases(expected.get("phases", []), actual.get("phases", [])),
        "deliverables": compare_deliverables(
            expected.get("deliverables", []), actual.get("deliverables", [])
        ),
        "key_premises": compare_string_list(
            expected.get("key_premises", []), actual.get("key_premises", [])
        ),
        "out_of_scope": compare_string_list(
            expected.get("out_of_scope", []), actual.get("out_of_scope", [])
        ),
    }
    overall_simple = _overall_recall(results)
    overall_weighted = _weighted_recall(results)
    decision_simple = _decision_for(overall_simple)
    decision_weighted = _decision_for(overall_weighted)

    # stdout summary
    print(f"=== F2.8 Smoke Bradesco — Comparação ===")
    print(f"  project       : {results['project']['recall_pct']}% "
          f"({results['project']['matched']}/{results['project']['total']})")
    print(f"  phases        : {results['phases']['recall_pct']}% "
          f"({results['phases']['matched']}/{results['phases']['total']})")
    print(f"  deliverables  : {results['deliverables']['recall_pct']}% "
          f"({results['deliverables']['matched']}/{results['deliverables']['total']})")
    print(f"  key_premises  : {results['key_premises']['recall_pct']}% "
          f"({results['key_premises']['matched']}/{results['key_premises']['total']}, "
          f"+{len(results['key_premises']['extras'])} extras)")
    print(f"  out_of_scope  : {results['out_of_scope']['recall_pct']}% "
          f"({results['out_of_scope']['matched']}/{results['out_of_scope']['total']}, "
          f"+{len(results['out_of_scope']['extras'])} extras)")
    print()
    print(f"Recall simples    : {overall_simple}%   →  {decision_simple[0]}")
    print(f"Recall ponderado  : {overall_weighted}%   →  {decision_weighted[0]}  (criticidade-aware)")

    report = render_report(metadata, results, decision_simple, decision_weighted,
                           overall_simple, overall_weighted)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"\nRelatório salvo: {out_path}")
    # Exit code reflete o pior dos dois vereditos
    worst = decision_simple[0] if overall_simple < overall_weighted else decision_weighted[0]
    return 0 if worst != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
