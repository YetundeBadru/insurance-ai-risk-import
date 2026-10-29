"""PII redaction applied BEFORE any text is sent to a model or written to logs.

Redacts: emails, phone numbers (NG/KE), bank account numbers, BVN.
NOT redacted: claimant name and policy number, because extraction needs them.
In production these would go only to an approved, contractually covered provider.
"""
import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_ACCOUNT = re.compile(r"(?i)(account(?:\s*(?:no\.?|number))?\s*[:#]?\s*)(\d{10})(?!\d)")
_BVN = re.compile(r"(?i)(bvn\s*[:#]?\s*)(\d{11})(?!\d)")
_PHONE = re.compile(r"(?<![\w/\-])(?:\+?(?:234|254)|0)(?:[\s-]?\d){9,10}(?!\d)")


def redact(text: str):
    counts = {"email": 0, "phone": 0, "account": 0, "bvn": 0}

    def sub(pattern, label, s, keep_prefix=False):
        def _r(m):
            counts[label] += 1
            return (m.group(1) if keep_prefix else "") + f"[{label.upper()}]"
        return pattern.sub(_r, s)

    text = sub(_EMAIL, "email", text)
    text = sub(_ACCOUNT, "account", text, keep_prefix=True)
    text = sub(_BVN, "bvn", text, keep_prefix=True)
    text = sub(_PHONE, "phone", text)
    return text, {k: v for k, v in counts.items() if v}
