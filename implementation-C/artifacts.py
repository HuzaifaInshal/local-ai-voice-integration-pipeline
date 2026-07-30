"""
artifacts.py
Turns real tool results into UI-renderable artifacts.

The agent still follows the native tool-calling ReAct loop. This module only
packages completed tool output into deterministic table/chart blocks so the UI
can render useful analytics before the final text finishes streaming.
"""

import json
import re
from typing import Any


MAX_TABLE_ROWS = 50
MAX_CHART_ROWS = 25

DATE_COLUMN_RE = re.compile(r"(date|year|month|period|fy|financial_year)", re.IGNORECASE)
NUMERIC_NAME_RE = re.compile(
    r"(count|total|sum|avg|average|min|max|rating|sales|equity|amount|revenue|value|balance|clients?)",
    re.IGNORECASE,
)
ID_NAME_RE = re.compile(r"(^id$|_id$|t24_id|crimsid)", re.IGNORECASE)


def build_artifacts(tool_name: str, args: dict[str, Any], result_text: str) -> list[dict[str, Any]]:
    """Return zero or more UI artifacts for a completed tool call."""
    if tool_name == "get_schema":
        diagram = _build_schema_diagram(result_text)
        return [diagram] if diagram else []

    rows = _extract_rows(result_text)
    if not rows:
        return []

    title = _title_for(tool_name, args)
    artifacts: list[dict[str, Any]] = [
        {
            "type": "table",
            "title": title,
            "columns": list(rows[0].keys()),
            "rows": rows[:MAX_TABLE_ROWS],
            "row_count": len(rows),
        }
    ]

    chart = _build_chart(title, rows)
    if chart:
        artifacts.append(chart)

    return artifacts


def _build_schema_diagram(result_text: str) -> dict[str, Any] | None:
    try:
        schema = json.loads(result_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(schema, dict) or not schema:
        return None

    nodes = []
    for table_name, columns in schema.items():
        if str(table_name).startswith("sqlite_"):
            continue
        if not isinstance(columns, list):
            continue
        fields = []
        for column in columns[:8]:
            if isinstance(column, dict) and column.get("column"):
                fields.append(str(column["column"]))
        nodes.append({"id": str(table_name), "label": str(table_name), "fields": fields})

    if not nodes:
        return None

    table_columns = {
        str(table_name): {
            str(column.get("column"))
            for column in columns
            if isinstance(column, dict) and column.get("column")
        }
        for table_name, columns in schema.items()
        if isinstance(columns, list) and not str(table_name).startswith("sqlite_")
    }
    edges = []
    table_names = list(table_columns.keys())
    for left_index, left in enumerate(table_names):
        for right in table_names[left_index + 1:]:
            shared = sorted(table_columns[left].intersection(table_columns[right]))
            join_keys = [column for column in shared if column.endswith("_id") or column in {"id", "t24_id"}]
            if join_keys:
                edges.append({"from": left, "to": right, "label": join_keys[0]})

    return {
        "type": "diagram",
        "title": "Schema relationship diagram",
        "nodes": nodes,
        "edges": edges,
    }


def _extract_rows(result_text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(result_text)
    except json.JSONDecodeError:
        return []

    data = payload.get("result")
    if isinstance(data, dict):
        return [data]
    if not isinstance(data, list):
        return []

    rows = [row for row in data if isinstance(row, dict)]
    if not rows:
        return []
    return rows


def _title_for(tool_name: str, args: dict[str, Any]) -> str:
    if tool_name == "sql_query":
        query = str(args.get("query", "")).strip()
        return "Query result" if not query else _title_from_query(query)
    if tool_name == "lookup_client":
        return "Client lookup"
    if tool_name == "get_client_orr":
        return "ORR history"
    return "Tool result"


def _title_from_query(query: str) -> str:
    compact = " ".join(query.split())
    if len(compact) <= 90:
        return compact
    return compact[:87].rstrip() + "..."


def _build_chart(title: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows or len(rows) > MAX_CHART_ROWS:
        return None

    columns = list(rows[0].keys())
    numeric_columns = [c for c in columns if _is_numeric_column(c, rows)]
    if not numeric_columns:
        return None

    x_column = _choose_x_column(columns, numeric_columns, rows)
    if not x_column:
        return None

    y_column = _choose_y_column(numeric_columns, x_column)
    if not y_column:
        return None

    points = []
    for row in rows[:MAX_CHART_ROWS]:
        x_value = row.get(x_column)
        y_value = _as_number(row.get(y_column))
        if x_value is None or y_value is None:
            continue
        points.append({"x": str(x_value), "y": y_value})

    if len(points) < 2:
        return None

    chart_type = "line" if DATE_COLUMN_RE.search(x_column) else "bar"
    return {
        "type": "chart",
        "chart_type": chart_type,
        "title": title,
        "x": x_column,
        "y": y_column,
        "data": points,
    }


def _choose_x_column(columns: list[str], numeric_columns: list[str], rows: list[dict[str, Any]]) -> str | None:
    non_numeric = [c for c in columns if c not in numeric_columns]
    dated = [c for c in non_numeric if DATE_COLUMN_RE.search(c)]
    if dated:
        return dated[0]
    if non_numeric:
        return non_numeric[0]

    # If every column is numeric, use the first ID-like or sequence-like column
    # as x and another numeric column as y.
    candidates = [c for c in columns if not ID_NAME_RE.search(c)]
    if len(candidates) >= 2:
        return candidates[0]
    if len(columns) >= 2:
        return columns[0]
    return None


def _choose_y_column(numeric_columns: list[str], x_column: str) -> str | None:
    choices = [c for c in numeric_columns if c != x_column]
    if not choices:
        choices = numeric_columns
    preferred = [c for c in choices if NUMERIC_NAME_RE.search(c) and not ID_NAME_RE.search(c)]
    if preferred:
        return preferred[0]
    non_id = [c for c in choices if not ID_NAME_RE.search(c)]
    if non_id:
        return non_id[0]
    return choices[0] if choices else None


def _is_numeric_column(column: str, rows: list[dict[str, Any]]) -> bool:
    values = [row.get(column) for row in rows if row.get(column) is not None]
    if not values:
        return False
    numeric_count = sum(1 for value in values if _as_number(value) is not None)
    return numeric_count == len(values)


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None
