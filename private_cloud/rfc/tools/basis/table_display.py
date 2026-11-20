"""SE16N-style table display: read-only access to table fields and table contents.

DDIF_FIELDINFO_GET and RFC_READ_TABLE only read. Table and field names are validated,
filter values are quoted by this module (no free-form SQL reaches SAP), and tables that
hold password hashes or stored secrets are refused (GOLDEN_PATH.md, section 11).
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from core.app import (
    READ_ONLY,
    call_rfc,
    clamp,
    connection_unavailable,
    json_safe,
    mcp,
    rfc_error_result,
    sap_rfc,
    validation_error,
    wildcard_match,
)


_READ = "RFC_READ_TABLE"
_FIELD_INFO = "DDIF_FIELDINFO_GET"

# Password hashes and stored secrets are never displayed.
_BLOCKED_TABLES = frozenset(
    {"USR02", "USH02", "USRPWDHISTORY", "RFCDES", "RSECTAB", "RSECACTB", "ICFSECPASSWD", "SSF_PSE_D"}
)

_NAME = re.compile(r"[A-Z/][A-Z0-9_/]{0,29}")
_QUOTED = re.compile(r"'(?:[^']|'')*'")
_CONDITION = re.compile(
    r"(?P<field>[A-Za-z/][A-Za-z0-9_/]*)\s*"
    r"(?P<op><>|!=|<=|>=|=|<|>|(?<=\s)(?:NOT\s+)?(?:LIKE|IN|BETWEEN)(?=[\s('])|(?<=\s)(?:NOT\s+)?(?:LIKE|IN|BETWEEN)$)"
    r"\s*(?P<rest>.*)",
    re.IGNORECASE | re.DOTALL,
)
_SEMICOLON = re.compile(r";")
_COMMA = re.compile(r",")
_AND = re.compile(r"\s+AND\s+", re.IGNORECASE)

_NUMERIC_TYPES = frozenset("PIbsF")  # ABAP types whose text form carries a trailing minus sign
_OPTION_WIDTH = 72  # RFC_DB_OPT-TEXT
_MAX_VALUE_LENGTH = 255

_HINTS = {
    "NOT_AUTHORIZED": "The RFC user needs display authorization for this table (S_TABU_NAM or S_TABU_DIS).",
    "DATA_BUFFER_EXCEEDED": "The selected fields are wider than 512 characters in total; select fewer fields.",
    "FIELD_NOT_VALID": "A selected field does not exist in the table; check the names with list_table_fields.",
    "OPTION_NOT_VALID": "SAP rejected the filter; check the field names and value formats.",
    "TABLE_NOT_AVAILABLE": "The table or view does not exist.",
    "TABLE_WITHOUT_DATA": "The object has no table data (for example a structure).",
    "NOT_FOUND": "The table, view or structure does not exist.",
}

# Newer RFC_READ_TABLE versions can sort by primary key, which keeps paging stable.
_sorted_rows_supported = True


# ---------------------------------------------------------------------------
# Input validation (raise ValueError with a caller-facing message)
# ---------------------------------------------------------------------------


def _table_name(value: str) -> str:
    name = value.strip().upper()
    if not _NAME.fullmatch(name):
        raise ValueError("table must be a table or view name of up to 30 letters, digits, _ or /.")
    if name in _BLOCKED_TABLES:
        raise ValueError(f"{name} holds password hashes or stored secrets and is not displayed.")
    return name


def _field_names(value: str, name: str, required: bool = True) -> list[str]:
    fields: list[str] = []
    for part in re.split(r"[,\s]+", value.strip().upper()):
        if not part:
            continue
        if not _NAME.fullmatch(part):
            raise ValueError(f"{name} contains an invalid field name: {part[:40]}")
        if part not in fields:
            fields.append(part)
    if required and not fields:
        raise ValueError(f"{name} must list at least one technical field name.")
    if len(fields) > 60:
        raise ValueError(f"{name} may list at most 60 fields.")
    return fields


def _split_outside_quotes(text: str, separator: re.Pattern[str]) -> list[str]:
    """Split text at separator matches that are not inside a quoted literal."""
    masked = _QUOTED.sub(lambda match: "\x00" * len(match.group()), text)
    parts, start = [], 0
    for match in separator.finditer(masked):
        parts.append(text[start : match.start()])
        start = match.end()
    parts.append(text[start:])
    return parts


def _literal(raw: str, field: str, like: bool = False) -> str:
    """Return one filter value as a quoted Open SQL literal."""
    text = raw.strip()
    if len(text) >= 2 and text[0] == "'" and text[-1] == "'" and _QUOTED.fullmatch(text):
        value = text[1:-1].replace("''", "'")
    elif text and "'" not in text:
        value = text
    else:
        raise ValueError(f"The value for {field} is empty or has unbalanced quotes; write '' for an empty value.")
    if len(value) > _MAX_VALUE_LENGTH or not value.isprintable():
        raise ValueError(f"The value for {field} must be printable text of at most {_MAX_VALUE_LENGTH} characters.")
    if like:
        value = value.replace("*", "%")
    return "'" + value.replace("'", "''") + "'"


def _condition_tokens(condition: str) -> list[str]:
    match = _CONDITION.fullmatch(condition)
    if not match:
        raise ValueError(
            f"Cannot read the condition {condition[:60]!r}; use FIELD = value, FIELD IN a, b, "
            "FIELD BETWEEN a AND b or FIELD LIKE pattern, separated by ';'."
        )
    field = match["field"].upper()
    if not _NAME.fullmatch(field):
        raise ValueError(f"Invalid field name in the filter: {field[:40]}")
    operator = " ".join(match["op"].upper().split()).replace("!=", "<>")
    rest = match["rest"].strip()

    if operator in {"IN", "NOT IN"}:
        if rest.startswith("(") and rest.endswith(")"):
            rest = rest[1:-1]
        values = [_literal(part, field) for part in _split_outside_quotes(rest, _COMMA)]
        if len(values) > 200:
            raise ValueError(f"{field} {operator} may list at most 200 values.")
        return [field, operator, "(", *[f"{value}," for value in values[:-1]], values[-1], ")"]
    if operator in {"BETWEEN", "NOT BETWEEN"}:
        bounds = _split_outside_quotes(rest, _AND)
        if len(bounds) != 2:
            raise ValueError(f"{field} {operator} needs two values: low AND high.")
        return [field, operator, _literal(bounds[0], field), "AND", _literal(bounds[1], field)]
    return [field, operator, _literal(rest, field, like=operator.endswith("LIKE"))]


def _where_lines(where: str) -> list[str]:
    """Turn 'COND; COND; ...' into RFC_READ_TABLE option lines of at most 72 characters."""
    tokens: list[str] = []
    for condition in _split_outside_quotes(where, _SEMICOLON):
        condition = condition.strip()
        if not condition:
            continue
        if tokens:
            tokens.append("AND")
        tokens.extend(_condition_tokens(condition))

    lines, current = [], ""
    for token in tokens:
        if len(token) > _OPTION_WIDTH:
            raise ValueError("A filter value is longer than 70 characters and cannot be sent to SAP.")
        candidate = f"{current} {token}" if current else token
        if len(candidate) > _OPTION_WIDTH:
            lines.append(current)
            current = token
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# RFC_READ_TABLE
# ---------------------------------------------------------------------------


def _error(error: BaseException, **fields: Any) -> dict[str, Any]:
    result = rfc_error_result(error, **fields)
    hint = _HINTS.get(str(result.get("error_key") or ""))
    if hint:
        result["hint"] = hint
    return result


def _read(table: str, fields: list[str], lines: list[str], **params: Any) -> dict[str, Any]:
    """Call RFC_READ_TABLE with fixed-width rows, sorted by primary key when supported."""
    global _sorted_rows_supported
    params.update(
        QUERY_TABLE=table,
        DELIMITER="",
        OPTIONS=[{"TEXT": line} for line in lines],
        FIELDS=[{"FIELDNAME": field} for field in fields],
    )
    if _sorted_rows_supported:
        try:
            return call_rfc(_READ, GET_SORTED="X", **params)
        except Exception as error:
            if "GET_SORTED" not in str(error):
                raise
            _sorted_rows_supported = False
    return call_rfc(_READ, **params)


def _columns(response: dict[str, Any]) -> list[dict[str, Any]]:
    columns = []
    for meta in response.get("FIELDS") or []:
        columns.append(
            {
                "name": str(meta.get("FIELDNAME") or "").strip(),
                "type": str(meta.get("TYPE") or "").strip(),
                "length": int(str(meta.get("LENGTH") or "0").strip() or 0),
                "text": str(meta.get("FIELDTEXT") or "").strip(),
                "offset": int(str(meta.get("OFFSET") or "0").strip() or 0),
            }
        )
    return columns


def _rows(response: dict[str, Any], columns: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Slice the fixed-width rows; numbers get a leading minus instead of SAP's trailing one."""
    rows = []
    for entry in response.get("DATA") or []:
        line = str(entry.get("WA") or "")
        row = {}
        for column in columns:
            value = line[column["offset"] : column["offset"] + column["length"]].strip()
            if column["type"] in _NUMERIC_TYPES and value.endswith("-"):
                value = "-" + value[:-1].strip()
            row[column["name"]] = value
        rows.append(row)
    return rows


def _public_columns(columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: column[key] for key in ("name", "type", "length", "text")} for column in columns]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def list_table_fields(table: str, pattern: str = "", max_results: int = 200, offset: int = 0) -> dict[str, Any]:
    """List the fields of a table, view or structure (as in SE11 / SE16N) with DDIF_FIELDINFO_GET.

    pattern filters by technical name or description; * and ? are wildcards, otherwise the
    text is searched anywhere. Each field shows its key flag, dictionary type, length,
    decimals and description. max_results: 1-500.
    """
    function = _FIELD_INFO
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        name = _table_name(table)
    except ValueError as error:
        return validation_error(function, str(error))
    if offset < 0:
        return validation_error(function, "offset must be non-negative.")
    limit = clamp(max_results, 1, 500)

    try:
        response = call_rfc(function, TABNAME=name, ALL_TYPES="X")
    except Exception as error:
        return _error(error, function=function, table=name)

    needle = pattern.strip()
    if needle and not any(character in needle for character in "*?"):
        needle = f"*{needle}*"
    fields = []
    for row in response.get("DFIES_TAB") or []:
        field = str(row.get("FIELDNAME") or "").strip()
        text = str(row.get("FIELDTEXT") or "").strip()
        if not field or (needle and not (wildcard_match(field, needle) or wildcard_match(text, needle))):
            continue
        fields.append(
            {
                "name": field,
                "key": row.get("KEYFLAG") == "X",
                "type": str(row.get("DATATYPE") or "").strip(),
                "length": int(str(row.get("LENG") or "0").strip() or 0),
                "decimals": int(str(row.get("DECIMALS") or "0").strip() or 0),
                "text": text,
            }
        )
    shown = fields[offset : offset + limit]
    return json_safe(
        {
            "status": "ok" if shown else "not_found",
            "connection": "RFC",
            "function": function,
            "table": name,
            "total": len(fields),
            "offset": offset,
            "returned": len(shown),
            "truncated": offset + len(shown) < len(fields),
            "fields": shown,
        }
    )


@mcp.tool(annotations=READ_ONLY)
async def read_table(table: str, fields: str, where: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Display table rows like SE16N (read-only) with RFC_READ_TABLE.

    fields is a comma-separated list of technical field names; together they may be at most
    512 characters wide. where holds conditions separated by ";" and combined with AND, e.g.
    "WERKS = 1010; BUDAT BETWEEN 20260801 AND 20260831; BWART IN 101, 261; MATNR LIKE 4000*".
    Operators: = <> < <= > >=, LIKE / NOT LIKE (* or % as wildcard), IN / NOT IN, BETWEEN.
    Values are literals and are quoted by the tool: dates as YYYYMMDD, numeric material
    numbers in their 18-digit form with leading zeros. Quantities and amounts come back as
    text with a leading minus sign. max_results: 1-1000; use offset to page. Tables with
    password hashes or stored secrets are refused. Find field names with list_table_fields.
    """
    function = _READ
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        name = _table_name(table)
        selected = _field_names(fields, "fields")
        lines = _where_lines(where)
    except ValueError as error:
        return validation_error(function, str(error))
    if offset < 0:
        return validation_error(function, "offset must be non-negative.")
    limit = clamp(max_results, 1, 1000)

    try:
        response = _read(name, selected, lines, ROWSKIPS=offset, ROWCOUNT=limit + 1)
    except Exception as error:
        return _error(error, function=function, table=name, where=lines)

    columns = _columns(response)
    rows = _rows(response, columns)
    truncated = len(rows) > limit
    rows = rows[:limit]
    return json_safe(
        {
            "status": "ok" if rows else "not_found",
            "connection": "RFC",
            "function": function,
            "table": name,
            "where": lines,
            "columns": _public_columns(columns),
            "offset": offset,
            "returned": len(rows),
            "truncated": truncated,
            "next_offset": offset + limit if truncated else None,
            "rows": rows,
        }
    )


@mcp.tool(annotations=READ_ONLY)
async def summarize_table(
    table: str,
    sum_fields: str,
    group_by: str = "",
    where: str = "",
    max_scan_rows: int = 20000,
) -> dict[str, Any]:
    """Total numeric table fields per group (like the SE16N totals row) with RFC_READ_TABLE.

    sum_fields and group_by are comma-separated technical field names; where uses the
    read_table syntax. Matching rows are read (up to max_scan_rows, 1-100000) and summed
    locally. complete is false when more rows matched than were read; narrow the filter
    then, because the totals are partial.
    """
    function = _READ
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        name = _table_name(table)
        sums = _field_names(sum_fields, "sum_fields")
        groups = _field_names(group_by, "group_by", required=False)
        lines = _where_lines(where)
    except ValueError as error:
        return validation_error(function, str(error))
    limit = clamp(max_scan_rows, 1, 100000)
    selected = groups + [field for field in sums if field not in groups]

    try:
        columns = _columns(_read(name, selected, lines, NO_DATA="X"))
        types = {column["name"]: column["type"] for column in columns}
        not_numeric = [field for field in sums if types.get(field) not in _NUMERIC_TYPES]
        if not_numeric:
            return validation_error(function, f"sum_fields must be numeric; not numeric: {', '.join(not_numeric)}.")
        response = _read(name, selected, lines, ROWCOUNT=limit + 1)
    except Exception as error:
        return _error(error, function=function, table=name, where=lines)

    rows = _rows(response, _columns(response))
    complete = len(rows) <= limit
    rows = rows[:limit]
    totals: dict[tuple[str, ...], dict[str, Any]] = {}
    grand = {field: Decimal(0) for field in sums}
    for row in rows:
        entry = totals.setdefault(
            tuple(row[field] for field in groups), {"rows": 0, **{field: Decimal(0) for field in sums}}
        )
        entry["rows"] += 1
        for field in sums:
            try:
                amount = Decimal(row[field] or "0")
            except InvalidOperation:
                return validation_error(function, f"{field} holds a value that is not a number: {row[field][:30]!r}.")
            entry[field] += amount
            grand[field] += amount

    return json_safe(
        {
            "status": "ok" if rows else "not_found",
            "connection": "RFC",
            "function": function,
            "table": name,
            "where": lines,
            "group_by": groups,
            "sum_fields": sums,
            "rows_scanned": len(rows),
            "complete": complete,
            "groups": [{**dict(zip(groups, key)), **totals[key]} for key in sorted(totals)],
            "total": {"rows": len(rows), **grand},
        }
    )
