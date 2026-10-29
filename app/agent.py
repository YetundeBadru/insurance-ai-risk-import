"""Claim reporting/status agent with tool calls and guardrails.
Rule-based router for the starter; swap `handle_message` routing for an LLM tool-calling loop
later and keep the guardrails + tenant checks + eval cases unchanged."""
import re

from . import claims_db

CLAIM_ID = re.compile(r"\bCLM-\d{4,}\b", re.I)
POLICY = re.compile(r"\b(?!CLM)[A-Z]{2,5}[-/]\d{3,}\b", re.I)
STATUS_WORDS = ("status", "where is my claim", "update on my claim", "how far", "hali ya dai")
REPORT_WORDS = ("report a claim", "file a claim", "new claim", "make a claim", "i want to claim")
INJECTION = re.compile(r"ignore (all |any )?(previous|prior) instructions|system prompt|you are now", re.I)


def handle_message(tenant_id: str, message: str) -> dict:
    if not tenant_id:
        return _out("Missing tenant.", refused=True)
    if INJECTION.search(message):
        return _out("I can only help with reporting a claim or checking a claim status.", refused=True)

    low = message.lower()
    cid = CLAIM_ID.search(message)
    pol = POLICY.search(message)

    if any(w in low for w in STATUS_WORDS):
        if not (cid and pol):
            return _out("Please share your claim ID (e.g. CLM-1234) and policy number so I can check.")
        res = claims_db.get_claim_status(tenant_id, cid.group(), pol.group())
        if not res:
            return _out("I couldn't find a claim matching those details.", tool="get_claim_status")
        return _out(f"Claim {res['claim_id']} status: {res['status']}.", tool="get_claim_status")

    if any(w in low for w in REPORT_WORDS):
        if not pol:
            return _out("Please share your policy number and a short description of what happened.")
        res = claims_db.create_claim(tenant_id, pol.group(), message)
        return _out(f"Your claim has been logged as {res['claim_id']} ({res['status']}).", tool="create_claim")

    return _out("I can only help with reporting a claim or checking a claim status.", refused=True)


def _out(reply, tool=None, refused=False):
    return {"reply": reply, "tool": tool, "refused": refused}
