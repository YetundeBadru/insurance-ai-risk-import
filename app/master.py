"""Mock policy master and client master (synthetic), keyed by tenant."""
POLICIES = {
    ("insurer_a", "AIC-1001"): {"status": "active", "owner_id": "CL-A001", "limit": 5_000_000},
    ("insurer_a", "AIC-1002"): {"status": "active", "owner_id": "CL-A002", "limit": 2_000_000},
    ("insurer_a", "AIC-1003"): {"status": "expired", "owner_id": "CL-A003", "limit": 3_000_000},
    ("insurer_b", "KIC-2001"): {"status": "active", "owner_id": "CL-B001", "limit": 4_000_000},
}
CLIENTS = {("insurer_a", "CL-A001"), ("insurer_a", "CL-A002"), ("insurer_a", "CL-A003"), ("insurer_b", "CL-B001")}
