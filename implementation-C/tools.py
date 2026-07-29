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
    """Return database tables and column schemas.
    Call this BEFORE writing any query to discover available tables and column names.
    If table_name is blank, returns schemas for all tables in the database ('clients', 'orr_ratings')."""
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


def get_current_datetime() -> str:
    """Return the current server date/time. Use this instead of guessing
    'today's date' for any date-relative or financial-year query."""
    return json.dumps({"now": datetime.now().isoformat()})


def render_chart(chart_type: str, title: str, labels: list, values: list, dataset_label: str = "Value") -> str:
    """Render a visual chart in the chat UI. ONLY call this AFTER you have real data from a prior tool result.
    NEVER call with empty labels or values — fetch the data first via sql_query, then call this.
    NEVER output base64, data URIs, or image tags in text — this tool handles all rendering.
    Supported chart_type: 'bar', 'line', 'pie', 'doughnut'.
    - labels: array of category or entity names (e.g. ['Corporate', 'Commercial', 'Retail'])
    - values: array of corresponding numeric values (e.g. [150000000, 85000000, 42000000])
    - title: chart heading description
    - dataset_label: label for the dataset (e.g. 'Sales (PKR)', 'Count', 'Equity')"""
    if not labels or not values:
        return json.dumps({"error": "render_chart called with empty labels or values. Call sql_query first to fetch real data, then call render_chart with the results."})
    return json.dumps({
        "status": "rendered",
        "chart": {
            "chart_type": chart_type,
            "title": title,
            "labels": labels,
            "values": values,
            "dataset_label": dataset_label
        }
    })


TOOL_DISPATCH = {
    "sql_query":            sql_query,
    "get_schema":           get_schema,
    "lookup_client":        lookup_client,
    "get_client_orr":       get_client_orr,
    "get_current_datetime": get_current_datetime,
    "render_chart":         render_chart,
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
                    "table_name": {"type": "string", "description": "Optional table name. Leave blank to list all tables and schemas."}
                },
                "required": [],
            },
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
            "name": "get_current_datetime",
            "description": get_current_datetime.__doc__.strip(),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "render_chart",
            "description": render_chart.__doc__.strip(),
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_type": {
                        "type": "string",
                        "enum": ["bar", "line", "pie", "doughnut"],
                        "description": "Visual chart format to render."
                    },
                    "title": {
                        "type": "string",
                        "description": "Title heading for the chart."
                    },
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Category or entity names for X-axis / slices."
                    },
                    "values": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Numeric values corresponding to each label."
                    },
                    "dataset_label": {
                        "type": "string",
                        "description": "Label for the metric series (e.g. 'Sales (PKR)')."
                    }
                },
                "required": ["chart_type", "title", "labels", "values"],
            },
        },
    },
]
