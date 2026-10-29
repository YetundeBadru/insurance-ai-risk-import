from app.extract import extract_claim
from app.llm import LLMResponse, MockLLM
from app.metrics import Metrics
from app.schemas import ClaimExtraction

import pytest


@pytest.mark.parametrize("raw,want", [("₦", "NGN"), ("ngn", "NGN"), ("N", "NGN"), ("Naira", "NGN"), ("KSh", "KES"),
                                       ("ksh.", "KES"), ("$", "USD"), ("GBP", "GBP"), (None, None)])
def test_currency_is_normalised(raw, want):
    assert ClaimExtraction(currency=raw).currency == want


def test_latency_uses_client_timing_not_wall_clock():
    class Timed(MockLLM):
        last_call_seconds = 1.5

        def complete(self, system, user):
            return super().complete(system, user)

    m = Metrics()
    extract_claim("Claimant: A B\nPolicy No: AIC-1001\nDate of incident: 2026-03-12\nType: Motor\nAmount: NGN 1,000", Timed(), metrics=m)
    assert m.summary()["p50_latency_s"] == 1.5
