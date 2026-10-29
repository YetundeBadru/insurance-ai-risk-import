from eval.run_eval import gate, run

BASE = {"field_accuracy": 0.9, "review_routing_accuracy": 0.9, "agent_pass_rate": 0.9,
        "risk_invalid_row_recall": 0.9, "risk_reason_accuracy": 0.9, "risk_mapping_accuracy": 0.9,
        "risk_false_reject_rate": 0.05}


def test_gate_blocks_regression():
    assert gate({**BASE, "field_accuracy": 0.5, "tenant_leaks": 0}, BASE)


def test_gate_blocks_more_false_rejects():
    assert gate({**BASE, "risk_false_reject_rate": 0.2, "tenant_leaks": 0}, BASE)


def test_gate_blocks_any_tenant_leak():
    assert gate({**BASE, "tenant_leaks": 1}, BASE)


def test_gate_passes_when_equal():
    assert not gate({**BASE, "tenant_leaks": 0}, BASE)


def test_zero_tenant_leaks_on_real_eval_set():
    scores, _, _ = run()
    assert scores["tenant_leaks"] == 0
