import json


def parse_json_object(text: str) -> dict:
    """Parse the first JSON object in a model reply (tolerates code fences and surrounding prose)."""
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(text[start:end + 1])
