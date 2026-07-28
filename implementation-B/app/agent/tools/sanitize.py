import re

MUTATING_KEYWORDS = [
    r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b", r"\bINSERT\b",
    r"\bALTER\b", r"\bTRUNCATE\b", r"\bGRANT\b", r"\bREVOKE\b"
]

def sanitize_sql_query(query: str) -> tuple[bool, str]:
    if not query or not query.strip():
        return False, "Empty SQL query."

    upper_query = query.upper()
    for kw in MUTATING_KEYWORDS:
        if re.search(kw, upper_query):
            return False, f"Security Violation: Mutating SQL keyword '{kw}' detected. Only SELECT queries are permitted."

    return True, query.strip()
