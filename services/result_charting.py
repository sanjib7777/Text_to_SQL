import re
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import json


ALLOWED_COLUMN_TYPES = {
    "NUMERIC",
    "CATEGORICAL",
    "DATE",
    "DATETIME",
    "BOOLEAN",
    "IDENTIFIER",
    "TEXT",
    "UNKNOWN",
}

_IDENTIFIER_NAME = re.compile(r"(^|_)(ID|CODE|NO|NUMBER|KEY|UUID)($|_)")
_TEXT_NAME = re.compile(r"(DESC|DESCRIPTION|REMARK|COMMENT|NOTE|ADDRESS|MESSAGE|DETAIL)")


@lru_cache(maxsize=1)
def _column_categories() -> dict[str, str]:
    category_file = Path(__file__).resolve().parents[1] / "column_categories.json"
    try:
        with category_file.open("r", encoding="utf-8") as file:
            categories = json.load(file)
        return {
            str(name).upper(): str(category).upper()
            for name, category in categories.items()
            if str(category).upper() in ALLOWED_COLUMN_TYPES
        }
    except (OSError, TypeError, ValueError, AttributeError):
        return {}


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _label(name: str) -> str:
    return re.sub(r"\s+", " ", name.replace("_", " ").replace("-", " ")).strip().title()


def _column_type(name: str, values: list[Any]) -> str:
    normalized_name = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")
    non_null = [value for value in values if value is not None]

    configured_type = _column_categories().get(normalized_name)
    if configured_type:
        return configured_type
    if _IDENTIFIER_NAME.search(normalized_name):
        return "IDENTIFIER"
    if _TEXT_NAME.search(normalized_name):
        return "TEXT"
    if any(isinstance(value, bool) for value in non_null):
        return "BOOLEAN"
    if any(isinstance(value, datetime) for value in non_null):
        return "DATETIME"
    if any(isinstance(value, date) for value in non_null):
        return "DATE"
    if non_null and all(isinstance(value, (int, float, Decimal)) and not isinstance(value, bool) for value in non_null):
        return "NUMERIC"
    if non_null and all(isinstance(value, str) for value in non_null):
        unique_count = len({value for value in non_null})
        if unique_count <= max(20, len(non_null) // 2):
            return "CATEGORICAL"
        return "TEXT"
    return "UNKNOWN"


def infer_column_metadata(columns: list[str] | None, rows: list[list[Any]] | None) -> list[dict[str, Any]]:
    columns = columns or []
    rows = rows or []
    metadata = []
    for index, name in enumerate(columns):
        values = [row[index] for row in rows if index < len(row)]
        metadata.append({
            "name": name,
            "label": _label(name),
            "type": _column_type(name, values),
            "nullable": any(value is None for value in values),
        })
    return metadata


def _rows_as_dicts(columns: list[str], rows: list[list[Any]]) -> list[dict[str, Any]]:
    return [
        {name: json_safe(row[index]) if index < len(row) else None for index, name in enumerate(columns)}
        for row in rows
    ]


def build_chart_data(
    columns: list[str] | None,
    rows: list[list[Any]] | None,
    metadata: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], str | None]:
    columns = columns or []
    rows = rows or []
    metadata = metadata or infer_column_metadata(columns, rows)
    numeric = [item["name"] for item in metadata if item["type"] == "NUMERIC"]
    categorical = [item["name"] for item in metadata if item["type"] == "CATEGORICAL"]
    date_columns = [item["name"] for item in metadata if item["type"] in {"DATE", "DATETIME"}]
    chart_rows = _rows_as_dicts(columns, rows)
    charts: list[dict[str, Any]] = []

    if categorical and numeric:
        category = categorical[0]
        values = numeric[0]
        grouped: dict[str, float] = {}
        for row in chart_rows:
            key = str(row.get(category)) if row.get(category) is not None else "NULL"
            value = row.get(values)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                grouped[key] = grouped.get(key, 0) + value
        aggregate_data = [{category: key, values: value} for key, value in grouped.items()]
        charts.append({"type": "bar", "categorical_column": category, "numeric_column": values, "data": aggregate_data})
        charts.append({"type": "pie", "categorical_column": category, "numeric_column": values, "data": aggregate_data})
        if len(numeric) > 1:
            charts.append({"type": "stacked_bar", "category_column": category, "numeric_columns": numeric, "data": chart_rows})

    if date_columns and numeric:
        charts.append({"type": "line", "date_column": date_columns[0], "numeric_columns": numeric, "data": chart_rows})

    if len(numeric) >= 2:
        charts.append({"type": "scatter", "x_numeric_column": numeric[0], "y_numeric_column": numeric[1], "data": chart_rows})

    if not charts:
        return {"charts": []}, "No categorical, date, or numeric column combination can produce a chart."
    return {"charts": charts}, None


def enrich_result(columns: list[str] | None, rows: list[list[Any]] | None) -> dict[str, Any]:
    columns = columns or []
    rows = rows or []
    safe_rows = [[json_safe(value) for value in row] for row in rows]
    metadata = infer_column_metadata(columns, rows)
    chart_data, chart_error = build_chart_data(columns, rows, metadata)
    return {
        "columns": columns,
        "rows": safe_rows,
        "column_metadata": metadata,
        "chart_data": chart_data,
        "chart_error": chart_error,
    }