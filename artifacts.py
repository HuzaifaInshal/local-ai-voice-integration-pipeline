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
MAX_CHART_ROWS = 100
CHART_TYPES = {"bar", "horizontal_bar", "line", "donut", "pie", "scatter"}

DATE_COLUMN_RE = re.compile(r"(date|year|month|period|fy|financial_year)", re.IGNORECASE)
SESSION_DATASETS: dict[str, list[dict[str, Any]]] = {}


def reset_artifacts(session_id: str) -> None:
    SESSION_DATASETS.pop(session_id, None)


def build_artifacts(
    tool_name: str,
    args: dict[str, Any],
    result_text: str,
    session_id: str = "",
) -> list[dict[str, Any]]:
    """Return zero or more UI artifacts for a completed tool call."""
    if tool_name == "get_schema":
        diagram = _build_schema_diagram(result_text)
        return [diagram] if diagram else []

    if tool_name == "render_chart":
        chart = _build_requested_chart(session_id, args)
        return [chart] if chart else []

    if tool_name == "render_dashboard":
        dashboard = _build_dashboard_artifact(session_id, args)
        return [dashboard] if dashboard else []

    rows = _extract_rows(result_text)
    if not rows:
        return []

    title = _title_for(tool_name, args)
    columns = list(rows[0].keys())
    if session_id:
        if session_id not in SESSION_DATASETS:
            SESSION_DATASETS[session_id] = []
        SESSION_DATASETS[session_id].append({
            "title": title,
            "columns": columns,
            "rows": rows,
        })

    artifacts: list[dict[str, Any]] = [
        {
            "type": "table",
            "title": title,
            "columns": columns,
            "rows": rows[:MAX_TABLE_ROWS],
            "row_count": len(rows),
        }
    ]
    return artifacts


def render_chart_result(session_id: str, args: dict[str, Any]) -> str:
    """Validate a chart request against the latest real tabular result."""
    chart = _build_requested_chart(session_id, args)
    if not chart:
        return json.dumps({
            "error": "Chart could not be rendered. First run a data query, then request a supported chart with valid columns."
        })
    return json.dumps({
        "result": "Chart rendered.",
        "chart_type": chart["chart_type"],
        "title": chart["title"],
        "source_columns": chart["source_columns"],
    })



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


def _build_dashboard_artifact(session_id: str, args: dict[str, Any]) -> dict[str, Any] | None:
    title = str(args.get("title") or "Executive Analytics Dashboard")
    subtitle = str(args.get("subtitle") or "")
    kpis = args.get("kpis") if isinstance(args.get("kpis"), list) else []
    chart_specs = args.get("charts") if isinstance(args.get("charts"), list) else []

    rendered_charts = []
    for spec in chart_specs:
        if isinstance(spec, dict):
            chart_art = _build_requested_chart(session_id, spec)
            if chart_art:
                rendered_charts.append(chart_art)

    if not rendered_charts and not kpis:
        return None

    return {
        "type": "dashboard",
        "title": title,
        "subtitle": subtitle,
        "kpis": kpis,
        "charts": rendered_charts,
    }


def _build_requested_chart(session_id: str, args: dict[str, Any]) -> dict[str, Any] | None:
    datasets = SESSION_DATASETS.get(session_id) or []
    if not datasets:
        return None

    ds_idx = args.get("dataset_index", -1)
    if not isinstance(ds_idx, int) or ds_idx >= len(datasets) or ds_idx < -len(datasets):
        ds_idx = -1

    state = datasets[ds_idx]
    rows = state.get("rows") or []
    columns = state.get("columns") or []
    if not rows or not columns:
        return None

    chart_type = str(args.get("chart_type", "")).strip().lower()
    if chart_type not in CHART_TYPES:
        return None

    title = str(args.get("title") or state.get("title") or "Chart")
    chart_rows = rows[:MAX_CHART_ROWS]

    if chart_type in {"donut", "pie"}:
        label_col = _first_present(columns, args.get("label"), args.get("x"))
        value_col = _first_present(columns, args.get("value"), args.get("y"))
        if not label_col or not value_col or not _is_numeric_column(value_col, chart_rows):
            return None
        labels = []
        values = []
        for row in chart_rows:
            value = _as_number(row.get(value_col))
            if value is None:
                continue
            labels.append(str(row.get(label_col)))
            values.append(value)
        if len(values) < 2:
            return None
        return {
            "type": "chart",
            "chart_type": chart_type,
            "title": title,
            "labels": labels,
            "datasets": [{"label": value_col, "data": values}],
            "source_columns": {"label": label_col, "value": value_col},
        }

    if chart_type == "scatter":
        x_col = _first_present(columns, args.get("x"))
        y_col = _first_present(columns, args.get("y"))
        label_col = _first_present(columns, args.get("label"))
        if not x_col or not y_col or not _is_numeric_column(x_col, chart_rows) or not _is_numeric_column(y_col, chart_rows):
            return None
        points = []
        for row in chart_rows:
            x_value = _as_number(row.get(x_col))
            y_value = _as_number(row.get(y_col))
            if x_value is None or y_value is None:
                continue
            point = {"x": x_value, "y": y_value}
            if label_col:
                point["label"] = str(row.get(label_col))
            points.append(point)
        if len(points) < 2:
            return None
        return {
            "type": "chart",
            "chart_type": chart_type,
            "title": title,
            "datasets": [{"label": f"{y_col} by {x_col}", "data": points}],
            "source_columns": {"x": x_col, "y": y_col, "label": label_col},
        }

    x_col = _first_present(columns, args.get("x"), args.get("label"))
    y_col = _first_present(columns, args.get("y"), args.get("value"))
    series_col = _first_present(columns, args.get("series"))
    if not x_col or not y_col or not _is_numeric_column(y_col, chart_rows):
        return None

    if series_col:
        labels = _unique_labels(row.get(x_col) for row in chart_rows)
        series_values = _unique_labels(row.get(series_col) for row in chart_rows)
        datasets = []
        for series_value in series_values:
            points_by_label = {}
            for row in chart_rows:
                if str(row.get(series_col)) != series_value:
                    continue
                value = _as_number(row.get(y_col))
                if value is not None:
                    points_by_label[str(row.get(x_col))] = value
            datasets.append({
                "label": series_value,
                "data": [points_by_label.get(label) for label in labels],
            })
    else:
        labels = []
        values = []
        for row in chart_rows:
            value = _as_number(row.get(y_col))
            if value is None:
                continue
            labels.append(str(row.get(x_col)))
            values.append(value)
        datasets = [{"label": y_col, "data": values}]

    if not labels or not datasets or len(labels) < 2:
        return None

    return {
        "type": "chart",
        "chart_type": chart_type,
        "title": title,
        "labels": labels,
        "datasets": datasets,
        "source_columns": {"x": x_col, "y": y_col, "series": series_col},
    }


def _first_present(columns: list[str], *candidates: Any) -> str | None:
    normalized = {column.lower(): column for column in columns}
    for candidate in candidates:
        if not candidate:
            continue
        exact = str(candidate).strip()
        if exact in columns:
            return exact
        lowered = exact.lower()
        if lowered in normalized:
            return normalized[lowered]
    return None


def _unique_labels(values) -> list[str]:
    seen = set()
    labels = []
    for value in values:
        label = str(value)
        if label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return labels


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
