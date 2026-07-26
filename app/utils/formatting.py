import json
import re
from typing import Dict, Any, Tuple

def extract_json_payload(response_text: str) -> Tuple[str, Dict[str, Any]]:
    """
    Parses agent markdown output to separate standard conversational text
    from visual JSON specs (charts/tables/metric cards).
    """
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            payload = json.loads(json_match.group(1))
            clean_text = re.sub(r'```json\s*\{.*?\}\s*```', '', response_text, flags=re.DOTALL).strip()
            return clean_text, payload
        except Exception:
            pass
            
    return response_text, {}
