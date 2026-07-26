import re

FORBIDDEN_KEYWORDS = [
    "UPDATE", "DELETE", "DROP", "INSERT", "ALTER",
    "TRUNCATE", "GRANT", "REVOKE", "EXEC", "EXECUTE"
]

def validate_read_only_sql(sql_query: str) -> None:
    """
    Validates that a SQL query contains no data-modifying or destructive statements.
    Raises PermissionError if a forbidden keyword or multiline injection attempt is detected.
    """
    cleaned = sql_query.strip()
    if not cleaned:
        raise ValueError("Empty SQL query provided.")

    # Remove SQL comments
    no_comments = re.sub(r'--.*$', '', cleaned, flags=re.MULTILINE)
    no_comments = re.sub(r'/\*.*?\*/', '', no_comments, flags=re.DOTALL)
    
    tokens = re.findall(r'\b[A-Za-z_]+\b', no_comments.upper())

    for token in tokens:
        if token in FORBIDDEN_KEYWORDS:
            raise PermissionError(
                f"Security Violation: Statement '{token}' is forbidden. "
                "Parakeet is strictly limited to READ-ONLY SELECT queries."
            )
