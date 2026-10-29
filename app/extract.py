import re
import time
from datetime import date

from pydantic import ValidationError

from .jsonutil import parse_json_object
from .llm import SYSTEM_PROMPT
from .metrics import metrics as default_metrics
from .redact import redact
from .schemas import ClaimExtraction, ExtractionResult

REQUIRED = ("policy_number", "incident_date", "claim_amount")
INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior|above) instructions|approve (this|the) claim|"
    r"system prompt|you are now|disregard .{0,30}(rules|instructions)", re.I)


_NUM_DATE = re.compile(r"(?<!\d)(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})(?!\d)")
_POLICY = re.compile(r"\b[A-Z]{2,5}[-/]\d{3,}\b")  # uppercase prefix only, so "Mar-2026" is not a policy


def _apply_date_rules(text, data, reasons):
    """House convention is day-first (Nigeria/Kenya). If the model read an ambiguous numeric date month-first,
    correct it and record why. Returns True if the date is implausible (in the future)."""
    d = data.incident_date
    if d is None:
        return False
    for a, b, y in _NUM_DATE.findall(text):
        a, b, y = int(a), int(b), int(y)
        if a <= 12 and b <= 12 and a != b:
            try:
                us, eu = date(y, a, b), date(y, b, a)
            except ValueError:
                continue
            if d == us:
                data.incident_date = d = eu
                reasons.append("date_ddmm_applied")
    if d > date.today():
        reasons.append("date_in_future")
        return True
    return False


def _conflicting_policies(text):
    found = {m for m in _POLICY.findall(text) if not m.startswith("CLM")}
    return len(found) > 1


def extract_claim(text: str, llm, max_attempts=3, min_conf=0.6, metrics=default_metrics) -> ExtractionResult:
    reasons = []
    if not text or not text.strip():
        metrics.record_extraction(True)
        return ExtractionResult(status="needs_human_review", reasons=["empty_document"])

    injected = bool(INJECTION.search(text))
    if injected:
        reasons.append("possible_prompt_injection")
    clean, redactions = redact(text)

    for attempt in range(1, max_attempts + 1):
        t0 = time.perf_counter()
        try:
            resp = llm.complete(SYSTEM_PROMPT, clean)
        except Exception as e:  # provider error/timeout -> retry
            metrics.record_call(time.perf_counter() - t0, False)
            reasons.append(f"llm_error:{type(e).__name__}")
            continue
        metrics.record_call(getattr(llm, "last_call_seconds", None) or (time.perf_counter() - t0), True,
                            resp.input_tokens, resp.output_tokens)
        try:
            data = ClaimExtraction(**parse_json_object(resp.text))
        except (ValueError, ValidationError):
            reasons.append("invalid_output")
            continue

        implausible = _apply_date_rules(text, data, reasons)
        conflict = _conflicting_policies(text)
        if conflict:
            reasons.append("multiple_policy_numbers")
        missing = [f for f in REQUIRED if getattr(data, f) is None]
        if missing:
            reasons.append("missing:" + ",".join(missing))
        if data.confidence < min_conf:
            reasons.append("low_confidence")
        review = bool(injected or missing or implausible or conflict or data.confidence < min_conf)
        metrics.record_extraction(review)
        return ExtractionResult(status="needs_human_review" if review else "ok", data=data,
                                reasons=reasons, attempts=attempt, redactions=redactions)

    metrics.record_extraction(True)  # fallback: never block the user, route to a human
    return ExtractionResult(status="needs_human_review", reasons=reasons + ["retries_exhausted"],
                            attempts=max_attempts, redactions=redactions)
