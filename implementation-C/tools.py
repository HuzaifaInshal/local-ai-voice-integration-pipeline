"""
tools.py
Defines the tools available to the agent, both:
  1. the executable Python functions (TOOL_DISPATCH)
  2. the OpenAI-format JSON schemas the model sees (TOOL_SCHEMAS)

Add your real client tools here later -- this file is the only place
you should need to touch to go from 6 demo tools to your actual 7.
"""

import sqlite3
import json
import re
from datetime import datetime

from db_setup import DB_PATH, build_database

build_database()  # no-op if it already exists

READ_ONLY_BLOCKLIST = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|PRAGMA)\b",
    re.IGNORECASE,
)


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sql_query(query: str) -> str:
    """Run a read-only SQL query against the company database and return
    the actual rows as JSON. This is intentionally the ONLY way the agent
    can see real data -- it must never fabricate rows itself."""
    if READ_ONLY_BLOCKLIST.search(query):
        return json.dumps({"error": "Only read-only SELECT queries are allowed."})
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(query)
        rows = [dict(r) for r in cur.fetchmany(50)]  # cap rows for context safety
        conn.close()
        if not rows:
            return json.dumps({"result": [], "note": "Query returned 0 rows."})
        return json.dumps({"result": rows})
    except Exception as e:
        return json.dumps({"error": f"SQL execution failed: {e}"})


def get_schema(table_name: str = "") -> str:
    """Return column names/types for a table, or all tables if none given.
    Call this BEFORE writing a query if you are unsure of column names --
    do not guess column names."""
    try:
        conn = _connect()
        cur = conn.cursor()
        tables = [table_name] if table_name else None
        if not tables:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r["name"] for r in cur.fetchall()]
        schema = {}
        for t in tables:
            cur.execute(f"PRAGMA table_info({t})")
            schema[t] = [{"column": r["name"], "type": r["type"]} for r in cur.fetchall()]
        conn.close()
        return json.dumps(schema)
    except Exception as e:
        return json.dumps({"error": str(e)})


def list_tables() -> str:
    """List every table available in the database."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r["name"] for r in cur.fetchall()]
    conn.close()
    return json.dumps({"tables": tables})


def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression, e.g. '(15999*3)+2499'.
    Only digits and + - * / ( ) . are allowed."""
    if not re.fullmatch(r"[0-9\.\+\-\*\/\(\)\s]+", expression):
        return json.dumps({"error": "Invalid characters in expression."})
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return json.dumps({"result": result})
    except Exception as e:
        return json.dumps({"error": str(e)})


def get_current_datetime() -> str:
    """Return the current server date/time. Use this instead of guessing
    'today's date' for any date-relative query."""
    return json.dumps({"now": datetime.now().isoformat()})


def lookup_order_status(order_id: int) -> str:
    """Look up a single order's status by its numeric order id."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return json.dumps({"error": f"No order with id {order_id}."})
    return json.dumps({"result": dict(row)})


TOOL_DISPATCH = {
    "sql_query": sql_query,
    "get_schema": get_schema,
    "list_tables": list_tables,
    "calculator": calculator,
    "get_current_datetime": get_current_datetime,
    "lookup_order_status": lookup_order_status,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "sql_query",
            "description": sql_query.__doc__.strip(),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "A read-only SQL SELECT statement."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_schema",
            "description": get_schema.__doc__.strip(),
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Optional table name. Leave blank for all tables."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": list_tables.__doc__.strip(),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": calculator.__doc__.strip(),
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": get_current_datetime.__doc__.strip(),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_order_status",
            "description": lookup_order_status.__doc__.strip(),
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "integer"}},
                "required": ["order_id"],
            },
        },
    },
]
