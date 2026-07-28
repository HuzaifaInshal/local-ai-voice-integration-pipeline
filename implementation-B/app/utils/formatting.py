import json
import re
from typing import Tuple, Dict, Any

def _find_json_object(text: str) -> Tuple[str, str]:
    """Finds JSON object containing 'display_type' and returns (raw_json_str, full_matched_str)."""
    # 1. First check if wrapped in markdown codeblock ```
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\"display_type\"[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1), match.group(0)

    # 2. Otherwise search for 'display_type' and find opening '{' and matching closing '}'
    pos = text.find('"display_type"')
    if pos == -1:
        pos = text.find("'display_type'")
    if pos == -1:
        return "", ""

    start = text.rfind('{', 0, pos)
    if start == -1:
        return "", ""

    brace_count = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        char = text[i]
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    raw_json = text[start:i+1]
                    return raw_json, raw_json

    return "", ""

def extract_json_payload(text: str) -> Tuple[str, Dict[str, Any]]:
    if not text:
        return "", {}

    raw_json, full_match = _find_json_object(text)
    payload = {}
    clean_text = text

    if raw_json and full_match:
        try:
            payload = json.loads(raw_json)
            clean_text = text.replace(full_match, "").strip()
        except Exception:
            try:
                sanitized = re.sub(r",\s*([\]}])", r"\1", raw_json)
                payload = json.loads(sanitized)
                clean_text = text.replace(full_match, "").strip()
            except Exception:
                payload = {}

    # Strip any SQL codeblocks or raw SELECT queries from clean text so UI stays 100% SQL-free
    clean_text = re.sub(r"```sql[\s\S]*?```", "", clean_text, flags=re.IGNORECASE).strip()
    clean_text = re.sub(r"\bSELECT\s+[\s\S]+?(?:;|\n\n|$)", "", clean_text, flags=re.IGNORECASE).strip()
    clean_text = re.sub(r"To find[\s\S]*?SQL query:", "", clean_text, flags=re.IGNORECASE).strip()
    clean_text = re.sub(r"Let's run this query[\s\S]*?results\.", "", clean_text, flags=re.IGNORECASE).strip()

    return clean_text.strip(), payload



