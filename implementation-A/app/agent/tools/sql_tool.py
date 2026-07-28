import json
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import Optional

from app.services.db_registry import DatabaseRegistry
from app.agent.tools.sanitize import validate_read_only_sql

db_registry_instance: Optional[DatabaseRegistry] = None

def set_global_db_registry(registry: DatabaseRegistry) -> None:
    """Configures the global DB registry reference used by sql_tool."""
    global db_registry_instance
    db_registry_instance = registry

class SQLQueryInput(BaseModel):
    query: str = Field(description="Executable SQL SELECT query generated to fulfill the request.")

@tool("execute_sql_query", args_schema=SQLQueryInput)
def execute_sql_query(query: str) -> str:
    """Executes a SQL query against the banking database and returns results as a JSON string."""
    if not db_registry_instance:
        return json.dumps({"error": "DB Registry is not initialized."})
    
    try:
        validate_read_only_sql(query)
        results = db_registry_instance.execute_read_only_query(query)
        return json.dumps(results, default=str)
    except Exception as e:
        return json.dumps({"error": f"Execution failed: {str(e)}"})
