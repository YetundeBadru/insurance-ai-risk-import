import os
import statistics
import threading


class Metrics:
    """In-memory call metrics: failure rate, p95 latency, token cost."""

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        self.calls = []  # (latency_s, ok, in_tok, out_tok)
        self.review_count = 0
        self.extractions = 0

    def record_call(self, latency, ok, in_tok=0, out_tok=0):
        with self._lock:
            self.calls.append((latency, ok, in_tok, out_tok))

    def record_extraction(self, needs_review: bool):
        with self._lock:
            self.extractions += 1
            self.review_count += int(needs_review)

    def summary(self):
        n = len(self.calls)
        lat = sorted(c[0] for c in self.calls)
        p95 = lat[min(n - 1, int(0.95 * n))] if n else 0.0
        pin = float(os.getenv("PRICE_IN_PER_M", 3))
        pout = float(os.getenv("PRICE_OUT_PER_M", 15))
        cost = sum(c[2] * pin + c[3] * pout for c in self.calls) / 1_000_000
        return {
            "llm_calls": n,
            "failed_call_rate": round(sum(1 for c in self.calls if not c[1]) / n, 4) if n else 0.0,
            "p50_latency_s": round(statistics.median(lat), 4) if n else 0.0,
            "p95_latency_s": round(p95, 4),
            "est_cost_usd": round(cost, 6),
            "human_review_rate": round(self.review_count / self.extractions, 4) if self.extractions else 0.0,
        }


metrics = Metrics()
