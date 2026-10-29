"""Print eval/history.jsonl as a markdown table to paste into the README.   python -m eval.report"""
import json
from pathlib import Path

KEYS = [("field_accuracy", "Field acc"), ("review_routing_accuracy", "Routing acc"), ("agent_pass_rate", "Agent pass"),
        ("risk_invalid_row_recall", "Risk recall"), ("risk_false_reject_rate", "Risk false-reject"),
        ("risk_mapping_accuracy", "Header mapping"), ("tenant_leaks", "Leaks")]

runs = [json.loads(l) for l in (Path(__file__).parent / "history.jsonl").read_text().splitlines() if l.strip()]
print("| Run | Model | Cases | Runs | " + " | ".join(n for _, n in KEYS) + " | p95 s |")
print("|---|---|---|---|" + "---|" * (len(KEYS) + 1))
for r in runs:
    sc, ops = r["scores"], r["ops"]
    print(f"| {r['label']} | {r['model']} | {sc.get('cases', '-')}+{sc.get('risk_cases', '-')} | {r.get('repeats', 1)} | "
          + " | ".join(str(sc.get(k, "-")) for k, _ in KEYS) + f" | {ops['p95_latency_s']} |")
