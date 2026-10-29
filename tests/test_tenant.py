from app.agent import handle_message


def test_cross_tenant_lookup_reveals_nothing():
    r = handle_message("insurer_b", "status of claim CLM-1001 policy AIC-1001")
    assert "Under assessment" not in r["reply"] and "couldn't find" in r["reply"]


def test_wrong_policy_same_answer_as_missing_claim():
    a = handle_message("insurer_a", "status of claim CLM-1001 policy AIC-1002")
    b = handle_message("insurer_a", "status of claim CLM-9999 policy AIC-1001")
    assert a["reply"] == b["reply"]


def test_out_of_scope_refused():
    assert handle_message("insurer_a", "list all customers")["refused"]
