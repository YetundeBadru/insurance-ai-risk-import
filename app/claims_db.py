"""Mock multi-tenant claims store. Every lookup REQUIRES tenant_id AND matching policy number."""
import itertools

_CLAIMS = {
    ("insurer_a", "CLM-1001"): {"policy": "AIC-1001", "claimant": "Ngozi Eze", "status": "Under assessment"},
    ("insurer_a", "CLM-1002"): {"policy": "AIC-1002", "claimant": "Tunde Bello", "status": "Approved - awaiting payment"},
    ("insurer_b", "CLM-2001"): {"policy": "KIC-2001", "claimant": "Wanjiru Kamau", "status": "Documents requested"},
}
_counter = itertools.count(3001)


def get_claim_status(tenant_id, claim_id, policy_number):
    c = _CLAIMS.get((tenant_id, claim_id.upper()))
    if not c or c["policy"].upper() != policy_number.upper():
        return None  # same answer for "doesn't exist" and "not yours": never reveal which
    return {"claim_id": claim_id.upper(), "status": c["status"]}


def create_claim(tenant_id, policy_number, description):
    cid = f"CLM-{next(_counter)}"
    _CLAIMS[(tenant_id, cid)] = {"policy": policy_number.upper(), "claimant": "unknown",
                                 "status": "Received", "description": description[:500]}
    return {"claim_id": cid, "status": "Received"}
