import re
import json
from typing import Optional


def parse_json(text: str) -> Optional[dict]:
    """Safely extract the first JSON object from a string using regex."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None
