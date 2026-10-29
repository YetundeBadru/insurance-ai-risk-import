import re

CANONICAL = ("registration_no", "make", "year", "sum_insured", "owner_id", "policy_number")

# normalized header -> canonical field (deterministic first pass; the LLM only sees what's left)
ALIASES = {
    "registrationno": "registration_no", "registrationnumber": "registration_no", "regno": "registration_no",
    "regnumber": "registration_no", "reg": "registration_no", "plate": "registration_no",
    "platenumber": "registration_no", "vehicleregistration": "registration_no", "vehicleregno": "registration_no",
    "make": "make", "vehiclemake": "make", "carmake": "make", "manufacturer": "make",
    "year": "year", "yearofmanufacture": "year", "yom": "year", "yrofmanufacture": "year",
    "manufactureyear": "year", "yr": "year",
    "suminsured": "sum_insured", "si": "sum_insured", "insuredamount": "sum_insured", "vehiclevalue": "sum_insured",
    "ownerid": "owner_id", "clientid": "owner_id", "customerid": "owner_id", "insuredid": "owner_id",
    "policynumber": "policy_number", "policyno": "policy_number", "policy": "policy_number",
    "policynum": "policy_number", "policyref": "policy_number",
}

MAP_PROMPT = (
    "MAP_COLUMNS. You map spreadsheet column headers to a fixed schema. You receive a JSON list of header "
    "names ONLY (never cell data). Return ONLY a JSON object mapping each header to one of "
    f"{list(CANONICAL)} or null. Use null when unsure. Never invent mappings."
)


def normalize_header(h) -> str:
    h = re.sub(r"\(.*?\)", "", str(h).lower())
    return re.sub(r"[^a-z0-9]", "", h)
