from typing import List, Dict, Any
from langchain_core.tools import tool
from sqlalchemy import text
from app.agent.tools.sanitize import sanitize_sql_query
from app.core.logger import setup_logger

logger = setup_logger("alfa.sql_tool")

_global_db_registry = None

def set_global_db_registry(registry: Any):
    global _global_db_registry
    _global_db_registry = registry

@tool
def execute_sql_query(query: str) -> List[Dict[str, Any]]:
    """Executes a read-only SQL SELECT query against the local SQLite database. Returns matching rows as dictionaries."""
    global _global_db_registry
    
    if not _global_db_registry or not _global_db_registry.engine:
        logger.error("Database Registry is not initialized!")
        return [{"error": "Database Registry not initialized."}]

    is_valid, msg = sanitize_sql_query(query)
    if not is_valid:
        logger.warning(f"Rejected SQL query execution: {msg}")
        return [{"error": msg}]

    try:
        logger.info(f"Executing SQL Query: {query}")
        with _global_db_registry.engine.connect() as conn:
            result = conn.execute(text(query))
            rows = [dict(r._mapping) for r in result]
            logger.info(f"Retrieved {len(rows)} rows from database.")
            return rows
    except Exception as e:
        logger.error(f"SQL execution error: {e}")
        return [{"error": f"SQL Execution Failure: {str(e)}"}]
