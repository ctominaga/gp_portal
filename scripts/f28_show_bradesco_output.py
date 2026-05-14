"""Helper interno: imprime resumo do bradesco_actual.json (run F5.6b)."""
import json
import sys
from pathlib import Path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".jump-runner/f28-bradesco/bradesco_actual.json"
d = json.loads(path.read_text(encoding="utf-8"))


def trunc(s, n=100):
    s = str(s)
    return s if len(s) <= n else s[: n - 3] + "..."


print("=== project ===")
for k, v in d.get("project", {}).items():
    print(f"  {k}: {trunc(v)}")
print()

phases = d.get("phases", [])
print(f"=== phases: {len(phases)} ===")
for p in phases:
    print(f"  - [{p.get('phase_id')}] {p.get('name')} ({p.get('deliverable_count')} entregas)")
print()

delivs = d.get("deliverables", [])
print(f"=== deliverables: {len(delivs)} ===")
for x in delivs[:6]:
    title = trunc(x.get("title", ""), 60)
    print(f"  - [{x.get('id')}] {title} | {x.get('type')} / {x.get('category')} / {x.get('complexity')}")
if len(delivs) > 6:
    print(f"  ... +{len(delivs) - 6} more")
print()

prem = d.get("key_premises", [])
print(f"=== key_premises: {len(prem)} ===")
for x in prem:
    print(f"  - {trunc(x)}")
print()

oos = d.get("out_of_scope", [])
print(f"=== out_of_scope: {len(oos)} ===")
for x in oos:
    print(f"  - {trunc(x)}")
print()

print("=== confidence ===")
print(f"  score: {d.get('confidence_score')}")
notes = d.get("confidence_notes") or ""
print(f"  notes: {trunc(notes, 400)}")
