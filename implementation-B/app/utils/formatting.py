import json
import re
from typing import Tuple, Dict, Any

def extract_json_payload(text: str) -> Tuple[str, Dict[str, Any]]:
    if not text:
        return "", {}

    json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    payload = {}
    clean_text = text

    if json_match:
        raw_json = json_match.group(1)
        try:
            payload = json.loads(raw_json)
            clean_text = text.replace(json_match.group(0), "").strip()
        except Exception:
            payload = {}

    return clean_text, payload
