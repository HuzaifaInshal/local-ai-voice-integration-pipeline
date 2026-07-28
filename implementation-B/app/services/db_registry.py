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

                self.catalog[table_name] = {
                    "columns": col_defs
                }

                snippet = f"Table '{table_name}': {', '.join(col_defs)}"
                schema_snippets.append(snippet)

        self.schema_context = "\n".join(schema_snippets)
        logger.info("Successfully cached compact DB schema context for ReAct prompts.")

