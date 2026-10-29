import json
from datetime import date

from app.extract import extract_claim
from app.llm import LLMResponse
from app.metrics import Metrics
from eval.run_eval import aggregate

DOC = "Claimant: Ngozi Eze\nPolicy No: AIC-1001\nDate of incident: {d}\nType: Motor\nAmount: NGN 450,000\n"


class Stub:
    def __init__(self, iso):
        self.iso = iso

    def complete(self, system, user):
        return LLMResponse(json.dumps({"claimant_name": "Ngozi Eze", "policy_number": "AIC-1001", "incident_date": self.iso,
                                       "claim_amount": 450000, "currency": "NGN", "claim_type": "motor",
                                       "missing_fields": [], "confidence": 0.95}), 10, 10)


def run(doc, iso):
    return extract_claim(doc, Stub(iso), metrics=Metrics())


def test_month_first_misreading_is_corrected_and_recorded():
    r = run(DOC.format(d="12/03/2026"), "2026-12-03")
    assert r.data.incident_date == date(2026, 3, 12) and "date_ddmm_applied" in r.reasons and r.status == "ok"


def test_correct_date_is_left_alone():
    r = run(DOC.format(d="12/03/2026"), "2026-03-12")
    assert r.data.incident_date == date(2026, 3, 12) and "date_ddmm_applied" not in r.reasons


def test_unambiguous_date_is_left_alone():
    r = run(DOC.format(d="25/03/2026"), "2026-03-25")
    assert r.data.incident_date == date(2026, 3, 25) and not r.reasons


def test_unrelated_model_date_is_not_overridden():
    r = run(DOC.format(d="12/03/2026"), "2026-05-05")
    assert r.data.incident_date == date(2026, 5, 5)


def test_future_date_routed_to_review():
    r = run(DOC.format(d="2031-03-12"), "2031-03-12")
    assert r.status == "needs_human_review" and "date_in_future" in r.reasons


def test_conflicting_policy_numbers_routed_to_review():
    r = run(DOC.format(d="2026-03-12") + "Policy No: AIC-1002\n", "2026-03-12")
    assert r.status == "needs_human_review" and "multiple_policy_numbers" in r.reasons


def test_claim_id_and_month_names_are_not_policy_numbers():
    r = run(DOC.format(d="2026-03-12") + "Claim ref: CLM-1001, reported in Mar-2026\n", "2026-03-12")
    assert r.status == "ok"


def test_aggregate_finds_flaky_and_stable_cases():
    s1 = {"field_accuracy": 0.9, "tenant_leaks": 0, "cases": 5}
    s2 = {"field_accuracy": 1.0, "tenant_leaks": 0, "cases": 5}
    mean, st = aggregate([(s1, [("E02", "x"), ("A12", "y")], {}), (s2, [("A12", "y")], {})])
    assert mean["field_accuracy"] == 0.95 and st["flaky"] == {"E02": 1} and st["always_failing"] == ["A12"]
    assert st["ranges"]["field_accuracy"] == [0.9, 1.0]
