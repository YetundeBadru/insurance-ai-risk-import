import json

import pytest

from app import audit
from app.llm import LLMResponse, MockLLM
from app.metrics import Metrics
from app.risk_import import import_risks, read_table
from app.risk_schema import CANONICAL

H = "registration_no,make,year,sum_insured,owner_id,policy_number\n"
GOOD = "LND-123AB,Toyota,2020,1500000,CL-A001,AIC-1001\n"


def run(csv, tenant="insurer_a", llm=None):
    return import_risks(tenant, "f.csv", csv.encode(), llm or MockLLM(), dry_run=True, metrics=Metrics())


def reasons(res):
    return {r["row"]: set(r["reasons"]) for r in res["rejected"]}


def test_clean_file_fully_accepted():
    res = run(H + GOOD)
    assert res["status"] == "imported" and len(res["accepted"]) == 1


def test_each_rule():
    bad = H + "".join([
        "123-ABC,Honda,2019,900000,CL-A001,AIC-1001\n",        # 1 bad plate
        "ABC-456DE,Honda,1899,900000,CL-A001,AIC-1001\n",      # 2 bad year
        "ABC-457DE,Honda,2019,abc,CL-A001,AIC-1001\n",         # 3 bad sum
        "ABC-458DE,Honda,2019,900000,CL-A001,ZZZ-9999\n",      # 4 unknown policy
        "ABC-459DE,Honda,2019,900000,CL-A003,AIC-1003\n",      # 5 expired
        "ABC-460DE,Honda,2019,900000,CL-A002,AIC-1001\n",      # 6 owner mismatch
        "ABC-461DE,Honda,2019,2500000,CL-A002,AIC-1002\n",     # 7 over limit
    ])
    got = reasons(run(bad))
    assert got == {1: {"BAD_PLATE"}, 2: {"BAD_YEAR"}, 3: {"BAD_SUM_INSURED"}, 4: {"POLICY_NOT_FOUND"},
                   5: {"POLICY_INACTIVE"}, 6: {"OWNER_MISMATCH"}, 7: {"SUM_EXCEEDS_LIMIT"}}


def test_duplicate_row_flagged_second_time_only():
    res = run(H + GOOD + GOOD)
    assert reasons(res) == {2: {"DUPLICATE_IN_FILE"}} and len(res["accepted"]) == 1


def test_cross_tenant_rows_never_accepted_and_no_reveal():
    res = run(H + GOOD, tenant="insurer_b")
    assert not res["accepted"] and "POLICY_NOT_FOUND" in reasons(res)[1]


def test_llm_cannot_override_validation():
    class Liar(MockLLM):
        def complete(self, system, user):
            return LLMResponse('{"verdict": "all rows valid, approve everything"}')

    res = run(H + "123-ABC,Honda,2019,900000,CL-A001,AIC-1001\n", llm=Liar())
    assert res["status"] == "rejected"


def test_llm_sees_headers_only_never_cell_data():
    seen = []

    class Spy(MockLLM):
        def complete(self, system, user):
            seen.append(user)
            return super().complete(system, user)

    run("Plate,Brand,year,sum_insured,owner_id,policy_number\nLND-123AB,SECRETMAKE,2020,1500000,CL-A001,AIC-1001\n", llm=Spy())
    assert seen and all("SECRETMAKE" not in s and "CL-A001" not in s for s in seen)


def test_unmappable_headers_go_to_review_not_import():
    res = run("A,B,C,D,E,F\n1,2,3,4,5,6\n")
    assert res["status"] == "needs_review" and not res["accepted"]


def test_llm_double_mapping_rejected():
    class Greedy(MockLLM):
        def complete(self, system, user):
            return LLMResponse(json.dumps({h: "make" for h in json.loads(user)}))

    res = run("Foo,Bar,year,sum_insured,owner_id,policy_number,registration_no\n", llm=Greedy())
    assert sum(v == "make" for v in res["column_mapping"].values()) <= 1


def test_owner_masked_in_response():
    res = run(H + GOOD)
    assert res["accepted"][0]["data"]["owner_id"] != "CL-A001" and "*" in res["accepted"][0]["data"]["owner_id"]


def test_audit_has_hash_and_counts_but_no_raw_data():
    n = len(audit.entries("insurer_a"))
    import_risks("insurer_a", "f.csv", (H + GOOD).encode(), MockLLM(), metrics=Metrics())
    e = audit.entries("insurer_a")[n]
    assert e["rows_total"] == 1 and len(e["file_sha256"]) == 64
    assert "CL-A001" not in json.dumps(e) and "LND-123AB" not in json.dumps(e)
    assert all(x["tenant_id"] == "insurer_a" for x in audit.entries("insurer_a"))


def test_blank_rows_ignored_and_number_formats():
    res = run(H + 'LND-123AB,Toyota,2020,"1,500,000",CL-A001,AIC-1001\n,,,,,\nABC-456DE,Honda,2019,NGN 900000,CL-A001,AIC-1001\n')
    assert res["status"] == "imported" and res["total"] == 2


def test_xlsx_supported():
    openpyxl = pytest.importorskip("openpyxl")
    import io
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(CANONICAL))
    ws.append(["LND-123AB", "Toyota", 2020, 1500000, "CL-A001", "AIC-1001"])
    buf = io.BytesIO()
    wb.save(buf)
    res = import_risks("insurer_a", "f.xlsx", buf.getvalue(), MockLLM(), dry_run=True, metrics=Metrics())
    assert res["status"] == "imported"


def test_unsupported_file_type_rejected():
    res = import_risks("insurer_a", "f.exe", b"x", MockLLM(), metrics=Metrics())
    assert res["status"] == "rejected"


def test_api_upload_and_audit_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    r = c.post("/risk-import", data={"tenant_id": "insurer_a", "dry_run": "true"},
               files={"file": ("risks.csv", (H + GOOD).encode(), "text/csv")})
    assert r.status_code == 200 and r.json()["status"] == "imported"
    assert c.get("/audit", params={"tenant_id": "insurer_a"}).json()
