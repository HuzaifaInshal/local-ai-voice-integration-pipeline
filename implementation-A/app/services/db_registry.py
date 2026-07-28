import json
import logging
from typing import Dict, Any, List
from sqlalchemy import create_engine, inspect, text, Engine

from app.core.logger import setup_logger

logger = setup_logger("parakeet.db")

class DatabaseRegistry:
    """Introspects backend SQL database schemas and provides read-only query execution."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine: Engine = create_engine(db_url, pool_pre_ping=True)
        self.schema_context: str = ""
        self.catalog: List[Dict[str, Any]] = []

    def initialize(self) -> None:
        """Startup routine: Introspects tables, columns, primary keys, and sample rows."""
        logger.info("Initializing Database Registry for Parakeet...")
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        
        schema_summary = []
        with self.engine.connect() as conn:
            for table in tables:
                columns = inspector.get_columns(table)
                pk = inspector.get_pk_constraint(table)
                col_defs = [f"{c['name']} ({c['type']})" for c in columns]
                
                sample_rows = []
                try:
                    result = conn.execute(text(f"SELECT * FROM {table} LIMIT 5"))
                    keys = result.keys()
                    for row in result.fetchall():
                        sample_rows.append(dict(zip(keys, row)))
                except Exception as e:
                    logger.warning(f"Failed to fetch sample records for table '{table}': {e}")

                schema_summary.append({
                    "table_name": table,
                    "columns": col_defs,
                    "primary_key": pk.get("constrained_columns", []),
                    "sample_records": sample_rows
                })

        self.catalog = schema_summary
        self.schema_context = json.dumps(schema_summary, indent=2, default=str)
        logger.info(f"Database Registry initialized. Cataloged {len(tables)} tables.")

    def execute_read_only_query(self, sql_query: str) -> List[Dict[str, Any]]:
        """Executes SQL query after enforcing read-only keyword guardrails."""
        sanitized = sql_query.strip().upper()
        forbidden = ["UPDATE", "DELETE", "DROP", "INSERT", "ALTER", "TRUNCATE", "GRANT", "REVOKE"]
        if any(keyword in sanitized for keyword in forbidden):
            raise PermissionError("Parakeet is strictly limited to READ-ONLY SELECT operations.")
            
        with self.engine.connect() as conn:
            result = conn.execute(text(sql_query))
            keys = result.keys()
            return [dict(zip(keys, row)) for row in result.fetchall()]
