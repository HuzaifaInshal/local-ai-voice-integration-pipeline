"""
tools.py
Defines the tools available to the agent, both:
  1. the executable Python functions (TOOL_DISPATCH)
  2. the OpenAI-format JSON schemas the model sees (TOOL_SCHEMAS)

Tables in the database:
  - clients     : banking customer master (CRIMSID, T24_ID, segments, branches, SBP codes, financials, PEP flag)
  - orr_ratings : Obligor Risk Rating history per T24_ID per financial year
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
    """Run a read-only SQL SELECT query against the banking database and return
    actual rows as JSON (capped at 50). The database has two tables:
    'clients' (customer master) and 'orr_ratings' (ORR history).
    ALWAYS call get_schema first if unsure of column names. Never fabricate data."""
    if READ_ONLY_BLOCKLIST.search(query):
        return json.dumps({"error": "Only read-only SELECT queries are allowed."})
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute(query)
        rows = [dict(r) for r in cur.fetchmany(50)]
        conn.close()
        if not rows:
            return json.dumps({"result": [], "note": "Query returned 0 rows."})
        return json.dumps({"result": rows})
    except Exception as e:
        return json.dumps({"error": f"SQL execution failed: {e}"})


def get_schema(table_name: str = "") -> str:
    """Return column names and types for a specific table, or all tables if none given.
    Call this BEFORE writing any query to avoid guessing column names.
    Tables available: 'clients', 'orr_ratings'."""
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


def lookup_client(identifier: str) -> str:
    """Look up a single banking client by CRIMSID (numeric) or T24 ID (12-digit string)
    or partial name (case-insensitive). Returns full client record from the 'clients' table."""
    conn = _connect()
    cur = conn.cursor()
    row = None
    # Try CRIMSID (integer)
    if identifier.isdigit() and len(identifier) <= 6:
        cur.execute("SELECT * FROM clients WHERE crimsid = ?", (int(identifier),))
        row = cur.fetchone()
    # Try T24 ID (12 digits)
    if not row and re.fullmatch(r"\d{12}", identifier):
        cur.execute("SELECT * FROM clients WHERE t24_id = ?", (identifier,))
        row = cur.fetchone()
    # Try name search
    if not row:
        cur.execute("SELECT * FROM clients WHERE LOWER(customer_name) LIKE ?", (f"%{identifier.lower()}%",))
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return json.dumps({"error": f"No client found for identifier '{identifier}'."})
        return json.dumps({"result": [dict(r) for r in rows]})
    conn.close()
    if not row:
        return json.dumps({"error": f"No client found for identifier '{identifier}'."})
    return json.dumps({"result": dict(row)})


def get_client_orr(t24_id: str) -> str:
    """Return all ORR (Obligor Risk Rating) records for a given T24 ID from the
    'orr_ratings' table, ordered by financial year ascending."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM orr_ratings WHERE t24_id = ? ORDER BY financial_year ASC",
        (t24_id,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    if not rows:
        return json.dumps({"result": [], "note": f"No ORR records found for T24 ID {t24_id}."})
    return json.dumps({"result": rows})


def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression, e.g. '(5000000000 * 0.15) / 12'.
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
    'today's date' for any date-relative or financial-year query."""
    return json.dumps({"now": datetime.now().isoformat()})


TOOL_DISPATCH = {
    "sql_query":          sql_query,
    "get_schema":         get_schema,
    "list_tables":        list_tables,
    "lookup_client":      lookup_client,
    "get_client_orr":     get_client_orr,
    "calculator":         calculator,
    "get_current_datetime": get_current_datetime,
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
            "name": "lookup_client",
            "description": lookup_client.__doc__.strip(),
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "CRIMSID (e.g. '12355'), T24 ID (e.g. '145345670000'), or partial customer name."
                    }
                },
                "required": ["identifier"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_client_orr",
            "description": get_client_orr.__doc__.strip(),
            "parameters": {
                "type": "object",
                "properties": {
                    "t24_id": {"type": "string", "description": "12-digit T24 ID of the client."}
                },
                "required": ["t24_id"],
            },
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
]
