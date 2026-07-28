import os
from typing import Dict, Any, List
from sqlalchemy import create_engine, inspect, text
from app.core.logger import setup_logger

logger = setup_logger("alfa.db")

class DatabaseRegistry:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = None
        self.inspector = None
        self.catalog: Dict[str, Any] = {}
        self.schema_context: str = ""

    def initialize(self):
        db_path = self.db_url.replace("sqlite:///", "")
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)
            self.db_url = f"sqlite:///{db_path}"

        logger.info(f"Connecting to database at {self.db_url}")
        self.engine = create_engine(self.db_url)
        self.inspector = inspect(self.engine)
        self._inspect_and_cache()

    def _inspect_and_cache(self):
        table_names = self.inspector.get_table_names()
        logger.info(f"Discovered DB tables: {table_names}")

        schema_snippets = []
        with self.engine.connect() as conn:
            for table_name in table_names:
                columns = self.inspector.get_columns(table_name)
                col_defs = [f"{c['name']} ({c['type']})" for c in columns]
                
                # Fetch 2 sample rows
                sample_rows = []
                try:
                    result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT 2;"))
                    sample_rows = [dict(row._mapping) for row in result]
                except Exception as e:
                    logger.warning(f"Could not fetch sample rows for {table_name}: {e}")

                self.catalog[table_name] = {
                    "columns": col_defs,
                    "sample_records": sample_rows
                }

                snippet = f"Table '{table_name}':\n  Columns: {', '.join(col_defs)}\n  Sample Records: {sample_rows}"
                schema_snippets.append(snippet)

        self.schema_context = "\n\n".join(schema_snippets)
        logger.info("Successfully cached DB schema context for ReAct prompts.")
