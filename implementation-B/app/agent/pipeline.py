import asyncio
import json
import re
from typing import AsyncGenerator, Dict, Any, List
from langchain_core.messages import HumanMessage

from app.agent.tools.sql_tool import execute_sql_query
from app.services.llm_factory import get_llm
from app.core.logger import setup_logger

logger = setup_logger("alfa.pipeline")

class ConversationMemory:
    """Stores last 5 turns of user queries and executed SQL statements for context awareness."""
    def __init__(self, max_turns: int = 5):
        self.max_turns = max_turns
        self.history: List[Dict[str, str]] = []

    def add_turn(self, user_text: str, sql_query: str):
        self.history.append({"user": user_text, "sql": sql_query})
        if len(self.history) > self.max_turns:
            self.history.pop(0)

    def format_history_for_prompt(self) -> str:
        if not self.history:
            return "No previous conversation history."
        formatted = []
        for idx, turn in enumerate(self.history, 1):
            formatted.append(f"Turn #{idx}:\nUser Query: {turn['user']}\nExecuted SQL: {turn['sql']}")
        return "\n\n".join(formatted)

class AlfaPipeline:
    """Single-Instance Streaming Pipeline: Unified Conversational Greeting & SQL Tool Execution."""

    def __init__(self, schema_context: str):
        self.schema_context = schema_context
        self.memory = ConversationMemory(max_turns=5)
        self.llm = get_llm()

    async def run_pipeline_stream(self, user_text: str) -> AsyncGenerator[Dict[str, Any], None]:
        logger.info(f"🚀 [Alfa Single-Instance Pipeline] New User Query: '{user_text}'")
        history_str = self.memory.format_history_for_prompt()

        unified_prompt = f"""You are Alfa, a financial AI banking assistant.
Given the database schema, conversation history, and user query:

INSTRUCTIONS:
1. Provide a friendly, helpful, conversational response directly addressing the user.
2. IF AND ONLY IF the user query asks to view, search, filter, or analyze database records:
   Include a single valid read-only SELECT SQL query enclosed inside a ```sql ... ``` block to retrieve the relevant data.
3. IF the user query is a simple greeting, chit-chat, general inquiry, or question about your capabilities (e.g., "how are you", "hello", "what can you do"):
   Do NOT output any SQL code or ```sql ... ``` block. Respond standard conversationally.
4. IF the user requests financial metrics or entities not present in the database:
   Politely inform them what data is available without writing any SQL code.

DATABASE SCHEMA:
{self.schema_context}

PREVIOUS TURNS & EXECUTED SQL:
{history_str}

CURRENT USER QUERY: {user_text}"""

        logger.info("⚡ [Single-Instance LLM Call] Streaming token-by-token response...")
        full_response_text = ""

        try:
            for chunk in self.llm.stream([HumanMessage(content=unified_prompt)]):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if token:
                    full_response_text += token
                    yield {
                        "type": "token",
                        "content": token
                    }
                    await asyncio.sleep(0.005)
        except Exception as e:
            logger.error(f"❌ Error during LLM streaming: {e}")

        # Check if response contains a valid SELECT SQL query block
        sql_query = ""

        # 1. Standard markdown block: ```sql SELECT ... ```
        sql_match = re.search(r"```sql\s*(SELECT[\s\S]+?)\s*```", full_response_text, re.IGNORECASE)
        if sql_match:
            sql_query = sql_match.group(1).strip()
        else:
            # 2. Generic codeblock with SELECT
            sql_match = re.search(r"```\s*(SELECT[\s\S]+?)\s*```", full_response_text, re.IGNORECASE)
            if sql_match:
                sql_query = sql_match.group(1).strip()
            else:
                # 3. Direct SELECT query ending in semicolon or newline block
                sql_match = re.search(r"\b(SELECT\s+[\s\S]+?)(?:;|\n\n|$)", full_response_text, re.IGNORECASE)
                if sql_match and len(sql_match.group(1).strip()) > 10:
                    sql_query = sql_match.group(1).strip()

        payload = {}

        if sql_query:
            if not sql_query.endswith(";"):
                sql_query += ";"

            logger.info(f"📊 [SQL Detected in Response]: {sql_query}")
            yield {
                "type": "status",
                "state": "executing_tool",
                "tool": "execute_sql_query",
                "message": "Fetching data..."
            }

            try:
                db_records = execute_sql_query.invoke({"query": sql_query})
                logger.info(f"✅ [SQL Execution Success]: Retrieved {len(db_records) if isinstance(db_records, list) else 0} records from DB")

                if isinstance(db_records, list) and len(db_records) > 0 and isinstance(db_records[0], dict):
                    raw_keys = list(db_records[0].keys())
                    headers = [k.replace('_', ' ').title() for k in raw_keys]
                    rows = []
                    for rec in db_records:
                        row_vals = []
                        for k in raw_keys:
                            val = rec.get(k, "")
                            if isinstance(val, (int, float)) and ("sales" in k.lower() or "equity" in k.lower()):
                                val = f"${val:,.2f}"
                            row_vals.append(str(val))
                        rows.append(row_vals)

                    payload = {
                        "display_type": "table",
                        "title": "Query Results",
                        "table_headers": headers,
                        "rows": rows
                    }
            except Exception as e:
                logger.error(f"❌ [SQL Execution Error]: {e}")
        else:
            logger.info("ℹ️ No SQL query detected in LLM response (non-DB query or standard conversation).")

        # Record conversation turn in memory
        self.memory.add_turn(user_text, sql_query)

        # Complete turn
        yield {
            "type": "completed",
            "raw_response": full_response_text,
            "payload": payload
        }
