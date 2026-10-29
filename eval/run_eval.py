"""Evaluation harness + release gate.

  python -m eval.run_eval                  # run and print scores
  python -m eval.run_eval --gate           # exit 1 if any metric regresses vs eval/baseline.json
  python -m eval.run_eval --update-baseline  # accept current scores as the new baseline
"""
import argparse
import json
import sys
from pathlib import Path

from app.agent import handle_message
from app.extract import extract_claim
from app.llm import get_llm
from app.metrics import Metrics
from app.risk_import import import_risks

HERE = Path(__file__).parent
TOL = 0.005


def _val(data, field):
    v = getattr(data, field, None)
    return v.isoformat() if hasattr(v, "isoformat") else v


def run(llm=None):
    llm = llm or get_llm()
    m = Metrics()
    cases = [json.loads(l) for l in (HERE / "cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    field_ok = field_total = route_ok = route_total = agent_ok = agent_total = leaks = 0
    failures = []

    for c in cases:
        if c["type"] == "extraction":
            res = extract_claim(c["text"], llm, metrics=m)
            route_total += 1
            if res.status == c["expect_status"]:
                route_ok += 1
            else:
                failures.append((c["id"], f"status {res.status} != {c['expect_status']}"))
            for f, want in c["expected"].items():
                field_total += 1
                got = _val(res.data, f) if res.data else None
                if got == want:
                    field_ok += 1
                else:
                    failures.append((c["id"], f"{f}: got {got!r}, want {want!r}"))
        else:
            out = handle_message(c["tenant_id"], c["message"])
            agent_total += 1
            ok = (out["tool"] == c["expect_tool"] and out["refused"] == c["expect_refused"]
                  and all(s in out["reply"] for s in c["must_contain"])
                  and not any(s in out["reply"] for s in c["must_not_contain"]))
            if ok:
                agent_ok += 1
            else:
                failures.append((c["id"], f"agent reply {out['reply']!r} tool={out['tool']}"))
            if c["leak_check"] and any(s in out["reply"] for s in c["must_not_contain"]):
                leaks += 1

    risk_scores, risk_failures, risk_leaks = run_risk(llm, m)
    failures += risk_failures
    leaks += risk_leaks
    scores = {
        "field_accuracy": round(field_ok / field_total, 4),
        "review_routing_accuracy": round(route_ok / route_total, 4),
        "agent_pass_rate": round(agent_ok / agent_total, 4),
        "tenant_leaks": leaks,
        "cases": len(cases),
        **risk_scores,
    }
    return scores, failures, m.summary()


def run_risk(llm, m):
    cases = [json.loads(l) for l in (HERE / "risk_cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    exp_rej = caught = reason_ok = valid_total = false_rej = map_total = map_ok = leaks = 0
    failures = []
    for c in cases:
        res = import_risks(c["tenant_id"], "case.csv", c["csv"].encode(), llm, dry_run=True, metrics=m)
        rej = {str(r["row"]): set(r["reasons"]) for r in res["rejected"]}
        expected = {k: set(v) for k, v in c["expected_rejections"].items()}
        for k, want in expected.items():
            exp_rej += 1
            if k in rej:
                caught += 1
                if rej[k] == want:
                    reason_ok += 1
                else:
                    failures.append((c["id"], f"row {k}: reasons {sorted(rej[k])} != {sorted(want)}"))
            else:
                failures.append((c["id"], f"row {k}: invalid row NOT rejected (expected {sorted(want)})"))
        n_valid = res["total"] - len(expected)
        valid_total += n_valid
        accepted_ok = {str(r["row"]) for r in res["accepted"]} - set(expected)
        wrongly = n_valid - len(accepted_ok)
        false_rej += wrongly
        if wrongly:
            failures.append((c["id"], f"{wrongly} valid row(s) not accepted (status={res['status']}, {res.get('reason', '')})"))
        for h, want in c["expected_mapping"].items():
            map_total += 1
            if res["column_mapping"].get(h) == want:
                map_ok += 1
            else:
                failures.append((c["id"], f"header {h!r}: mapped {res['column_mapping'].get(h)!r}, want {want!r}"))
        if c["cross_tenant"]:  # leak = a row that should have been rejected for tenant reasons was accepted
            leaks += len({str(r["row"]) for r in res["accepted"]} & set(expected))
    scores = {
        "risk_invalid_row_recall": round(caught / exp_rej, 4),
        "risk_reason_accuracy": round(reason_ok / exp_rej, 4),
        "risk_false_reject_rate": round(false_rej / valid_total, 4),
        "risk_mapping_accuracy": round(map_ok / map_total, 4),
        "risk_cases": len(cases),
    }
    return scores, failures, leaks


def gate(scores, baseline):
    problems = []
    for k in ("field_accuracy", "review_routing_accuracy", "agent_pass_rate", "risk_invalid_row_recall",
              "risk_reason_accuracy", "risk_mapping_accuracy"):
        if k in baseline and scores[k] < baseline[k] - TOL:
            problems.append(f"{k} regressed: {scores[k]} < baseline {baseline[k]}")
    if "risk_false_reject_rate" in baseline and scores["risk_false_reject_rate"] > baseline["risk_false_reject_rate"] + TOL:
        problems.append(f"risk_false_reject_rate worsened: {scores['risk_false_reject_rate']} > baseline {baseline['risk_false_reject_rate']}")
    if scores["tenant_leaks"] > 0:
        problems.append(f"tenant_leaks = {scores['tenant_leaks']} (must be 0)")
    return problems


def aggregate(runs):
    """runs: list of (scores, failures, ops). Returns (mean_scores, stability)."""
    n = len(runs)
    first = runs[0][0]
    mean_scores, ranges = dict(first), {}
    for k, v in first.items():
        if k in ("cases", "risk_cases") or not isinstance(v, (int, float)):
            continue
        vals = [r[0][k] for r in runs]
        mean_scores[k] = max(vals) if k == "tenant_leaks" else round(sum(vals) / n, 4)
        ranges[k] = [min(vals), max(vals)]
    counts = {}
    for _, failures, _ in runs:
        for cid in {c for c, _ in failures}:
            counts[cid] = counts.get(cid, 0) + 1
    stability = {"repeats": n, "ranges": ranges,
                 "flaky": {c: k for c, k in sorted(counts.items()) if k < n},
                 "always_failing": sorted(c for c, k in counts.items() if k == n)}
    return mean_scores, stability


def _preflight(provider):
    import os
    if provider == "mock":
        return
    if provider != "anthropic":  # free / OpenAI-compatible providers
        from app.llm import get_llm
        try:
            get_llm()
        except RuntimeError as e:
            sys.exit(str(e))
        return
    try:
        import anthropic  # noqa: F401
    except ImportError:
        sys.exit("Install the SDK first: pip install anthropic")
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY in your shell (never commit it, never paste it into chats).")


if __name__ == "__main__":
    import os
    import time

    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["mock", "anthropic", "gemini", "groq", "openrouter", "openai_compat"], default=os.getenv("LLM_PROVIDER", "mock"))
    ap.add_argument("--model", help="override LLM_MODEL for this run")
    ap.add_argument("--label", help="record this run in eval/history.jsonl, e.g. prompt-v1")
    ap.add_argument("--baseline", help="baseline file (default: baseline.json for mock, baseline_<provider>.json otherwise)")
    ap.add_argument("--repeat", type=int, default=1, help="run the suite N times and report stability")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--update-baseline", action="store_true")
    a = ap.parse_args()

    os.environ["LLM_PROVIDER"] = a.provider
    if a.model:
        os.environ["LLM_MODEL"] = a.model
    _preflight(a.provider)
    if a.provider not in ("mock", "anthropic"):
        os.environ.setdefault("PRICE_IN_PER_M", "0")   # free tiers: do not show a made-up cost
        os.environ.setdefault("PRICE_OUT_PER_M", "0")
        os.environ.setdefault("LLM_MIN_INTERVAL", "4")  # stay under free-tier requests-per-minute limits
    model = "mock" if a.provider == "mock" else os.getenv("LLM_MODEL", "claude-sonnet-4-6")

    all_runs = [run() for _ in range(a.repeat)]
    scores, failures, ops = all_runs[-1]
    stability = None
    if a.repeat > 1:
        scores, stability = aggregate(all_runs)   # scores = mean over runs (tenant_leaks = worst case)
    print(f"provider={a.provider} model={model}")
    print(json.dumps({"scores": scores, "ops": ops}, indent=2))
    print("\nFailing cases (investigate each one and document why):")
    for cid, why in failures:
        print(f"  - {cid}: {why}")
    (HERE / f"results_{a.provider}.json").write_text(json.dumps({"scores": scores, "ops": ops, "failures": failures}, indent=2))

    if stability:
        print(f"\nStability over {stability['repeats']} runs (min - max per metric):")
        for k, (lo, hi) in stability["ranges"].items():
            print(f"  {k}: {lo} - {hi}" + ("   <-- varies" if lo != hi else ""))
        print("Failed in every run:", stability["always_failing"] or "none")
        print("Flaky (failed in some runs):", stability["flaky"] or "none")

    if a.label:
        with open(HERE / "history.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M"), "label": a.label, "provider": a.provider,
                                "model": model, "scores": scores, "ops": ops, "failing_cases": sorted({c for c, _ in failures}),
                                "repeats": a.repeat, "stability": stability}) + "\n")
        print(f"\nRecorded run '{a.label}' in eval/history.jsonl")

    base_path = Path(a.baseline) if a.baseline else HERE / ("baseline.json" if a.provider == "mock" else f"baseline_{a.provider}.json")
    if a.update_baseline:
        base_path.write_text(json.dumps(scores, indent=2))
        print(f"\nBaseline updated: {base_path.name}")
    elif a.gate:
        problems = gate(scores, json.loads(base_path.read_text()))
        if problems:
            print("\nGATE FAILED:\n  " + "\n  ".join(problems))
            sys.exit(1)
        print("\nGATE PASSED: no regression against baseline.")
