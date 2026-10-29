"""Append-only audit trail. Stores a file hash and counts, never raw rows or PII."""
import hashlib
from datetime import datetime, timezone

_LOG = []


def file_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def record(tenant_id, action, **details):
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "tenant_id": tenant_id, "action": action, **details}
    _LOG.append(entry)
    return entry


def entries(tenant_id):
    return [e for e in _LOG if e["tenant_id"] == tenant_id]  # a tenant can only read its own trail
