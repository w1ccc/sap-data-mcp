"""Run reviewed display-only reports (custom apps such as ZDEMO1) and return their list output.

INST_EXECUTE_REPORT can run any report the RFC user may start with SA38, so this module only
accepts the reports registered in config/reviewed_reports.json. A report is registered after
its source was read and found to only read business data, and it is refused again as soon as
its source changes after that review. Only the registered selection fields are passed, so the
function's batch mode (which would create a job) cannot be reached. A report's own technical
logging still happens and is described in its note (GOLDEN_PATH.md, section 11).
"""

import json
import re
from typing import Any

from core.app import (
    PROJECT_DIR,
    READ_ONLY,
    call_rfc,
    clamp,
    connection_unavailable,
    json_safe,
    material_number,
    mcp,
    rfc_error_result,
    sap_rfc,
    validation_error,
)

from .table_display import _COMMA, _CONDITION, _QUOTED, _SEMICOLON, _split_outside_quotes


_RUN = "INST_EXECUTE_REPORT"
_READ = "RFC_READ_TABLE"
_REGISTRY_PATH = PROJECT_DIR / "config" / "reviewed_reports.json"

_PROGRAM = re.compile(r"[A-Z0-9_/]{1,40}")
_SOURCE_PATTERN = re.compile(r"[A-Z0-9_/$%]{1,40}")
_MAX_VALUE_LENGTH = 45  # RSPARAMS-LOW
_LINE_WIDTH = 256  # LISTZEILE-ZEILE: longer list lines are cut by SAP


def _registry() -> dict[str, dict[str, Any]]:
    """Read the reviewed reports on every call, so a new review takes effect without a restart."""
    return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Selection screen values (raise ValueError with a caller-facing message)
# ---------------------------------------------------------------------------


def _value(raw: str, name: str, material: bool) -> str:
    text = raw.strip()
    if len(text) >= 2 and text[0] == "'" and text[-1] == "'" and _QUOTED.fullmatch(text):
        value = text[1:-1].replace("''", "'")
    elif text and "'" not in text:
        value = text
    else:
        raise ValueError(f"The value for {name} is empty or has unbalanced quotes; write '' for an empty value.")
    if len(value) > _MAX_VALUE_LENGTH or not value.isprintable():
        raise ValueError(f"The value for {name} must be printable text of at most {_MAX_VALUE_LENGTH} characters.")
    value = value.upper()
    return material_number(value) if material and value else value


def _selection(program: str, entry: dict[str, Any], parameters: str) -> list[dict[str, str]]:
    """Turn 'NAME = value; NAME IN a, b' into INSTPARAMS rows for the registered selection fields.

    INST_EXECUTE_REPORT passes every row as an "include, equal" selection, so only single
    values and value lists are possible.
    """
    specs: dict[str, dict[str, Any]] = entry["parameters"]
    rows: list[dict[str, str]] = []
    given: set[str] = set()
    for condition in _split_outside_quotes(parameters, _SEMICOLON):
        condition = condition.strip()
        if not condition:
            continue
        match = _CONDITION.fullmatch(condition)
        if not match:
            raise ValueError(f"Cannot read {condition[:60]!r}; write NAME = value or NAME IN a, b, separated by ';'.")
        name = match["field"].upper()
        spec = specs.get(name)
        if spec is None:
            raise ValueError(f"{program} has no selection field {name}; available: {', '.join(specs)}.")
        operator = " ".join(match["op"].upper().split())
        rest = match["rest"].strip()
        material = bool(spec.get("material"))
        if operator == "=":
            values = [rest]
        elif operator == "IN" and spec["kind"] == "S":
            values = _split_outside_quotes(rest[1:-1] if rest.startswith("(") and rest.endswith(")") else rest, _COMMA)
        else:
            raise ValueError(
                f"{name} accepts {'= value or IN a, b' if spec['kind'] == 'S' else '= value'}; "
                "ranges, patterns and exclusions cannot be passed to this report runner."
            )
        if name in given and spec["kind"] == "P":
            raise ValueError(f"{name} takes a single value and was given twice.")
        given.add(name)
        rows.extend({"PARA_NAME": name, "PARA_VALUE": _value(value, name, material)} for value in values)

    missing = [name for name, spec in specs.items() if spec.get("required") and name not in given]
    if missing:
        raise ValueError(f"{program} needs a value for {', '.join(missing)}.")
    return rows


# ---------------------------------------------------------------------------
# Review status and list output
# ---------------------------------------------------------------------------


def _changed_since_review(entry: dict[str, Any]) -> list[dict[str, str]]:
    """Return the source objects (TRDIR) changed after the reviewed state; empty when unchanged."""
    patterns = [pattern for pattern in entry["source_objects"] if _SOURCE_PATTERN.fullmatch(pattern)]
    if len(patterns) != len(entry["source_objects"]) or not patterns:
        raise ValueError("config/reviewed_reports.json lists an invalid source object pattern.")
    options = [{"TEXT": ("" if index == 0 else "OR ") + f"NAME LIKE '{pattern}'"} for index, pattern in enumerate(patterns)]
    response = call_rfc(
        _READ, QUERY_TABLE="TRDIR", DELIMITER="|", OPTIONS=options,
        FIELDS=[{"FIELDNAME": "NAME"}, {"FIELDNAME": "UDAT"}],
    )
    known = entry["source_last_changed"].replace("-", "")
    changed = []
    for line in response.get("DATA") or []:
        name, _, day = str(line.get("WA") or "").partition("|")
        if day.strip() > known:
            changed.append({"object": name.strip(), "changed_on": day.strip()})
    return changed


def _alv_table(lines: list[str]) -> tuple[list[str], list[dict[str, str]]] | None:
    """Split an ALV list (|a|b|...| lines) into column names and rows; None for any other list.

    SAP cuts every line at 256 characters, so the last column of a wide list can be missing
    or incomplete in the header and in the rows.
    """
    cells = [
        [cell.strip() for cell in line.strip()[1:].removesuffix("|").split("|")]
        for line in lines
        if len(line.strip()) > 2 and line.strip().startswith("|")
    ]
    if len(cells) < 2:
        return None
    names: list[str] = []
    for index, name in enumerate(cells[0]):
        name = name or f"COLUMN_{index + 1}"
        while name in names:
            name += "_"
        names.append(name)
    return names, [dict(zip(names, row)) for row in cells[1:] if any(row)]


def _reviewed(registry: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        program: {
            "transaction": entry.get("transaction"),
            "title": entry.get("title"),
            "selection_fields": list(entry["parameters"]),
            "reviewed_on": entry.get("reviewed_on"),
        }
        for program, entry in registry.items()
    }


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def run_report(report: str = "", parameters: str = "", max_lines: int = 300, offset: int = 0) -> dict[str, Any]:
    """Run a reviewed display-only report (custom app) and return its list, with INST_EXECUTE_REPORT.

    Only reports registered after a source review are accepted; call it without report to list
    them with their selection fields. Example for ZDEMO1 (program ZDEMO_REPORT, demo consumption
    summary): parameters "P_WERKS = 1010; P_MONTH = 202608; S_MATNR IN 10000000011, 10000000021".
    parameters holds the selection as "NAME = value" or "NAME IN a, b" separated by ";"; ranges
    and patterns cannot be passed. The report runs as in SAP GUI but without drill-down; an ALV
    list is also returned as columns and rows, and list lines wider than 256 characters are cut
    by SAP. Business data is only read; the report's own technical logging still happens (see
    note in the result). A report whose source changed after its review is refused until it is
    reviewed again. max_lines: 1-1000; use offset to page.
    """
    function = [_READ, _RUN]
    try:
        registry = _registry()
    except (OSError, ValueError) as error:
        return validation_error(_RUN, f"config/reviewed_reports.json cannot be read: {error}")
    name = report.strip().upper()
    by_transaction = {entry.get("transaction"): program for program, entry in registry.items()}
    program = by_transaction.get(name, name)
    if program not in registry or not _PROGRAM.fullmatch(program):
        if not name:
            return {"status": "ok", "connection": "RFC", "function": _RUN, "reviewed_reports": _reviewed(registry)}
        result = validation_error(_RUN, f"{name[:40]} is not a reviewed display-only report.")
        result["reviewed_reports"] = _reviewed(registry)
        return result
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    entry = registry[program]
    try:
        selection = _selection(program, entry, parameters)
    except ValueError as error:
        return validation_error(function, str(error))
    if offset < 0:
        return validation_error(function, "offset must be non-negative.")
    limit = clamp(max_lines, 1, 1000)

    try:
        changed = _changed_since_review(entry)
    except ValueError as error:
        return validation_error(function, str(error))
    except Exception as error:
        return rfc_error_result(error, function=function, report=program)
    if changed:
        return {
            "status": "error",
            "connection": "RFC",
            "function": function,
            "report": program,
            "error_type": "SourceChangedSinceReview",
            "error_message": (
                "The report's source changed after its review, so it was not run. Read the changed "
                "source again and update config/reviewed_reports.json when it still only reads data."
            ),
            "changed_objects": changed,
            "reviewed_on": entry.get("reviewed_on"),
        }

    try:
        response = call_rfc(_RUN, PROGRAM=program, PARA=selection)
    except Exception as error:
        return rfc_error_result(error, function=function, report=program)

    lines = [str(row.get("ZEILE") or "").rstrip() for row in response.get("OUTPUT_TAB") or []]
    shown = lines[offset : offset + limit]
    failed = str(response.get("RESULT") or "").strip() not in {"S", ""}
    result: dict[str, Any] = {
        "status": "error" if failed else "ok" if lines else "not_found",
        "connection": "RFC",
        "function": function,
        "report": program,
        "transaction": entry.get("transaction"),
        "selection": [f"{row['PARA_NAME']} = {row['PARA_VALUE']}" for row in selection],
        "sap_result": str(response.get("RESULT_TEXT") or "").strip(),
        "note": entry.get("note"),
        "total_lines": len(lines),
        "offset": offset,
        "returned": len(shown),
        "truncated": offset + len(shown) < len(lines),
        "next_offset": offset + limit if offset + len(shown) < len(lines) else None,
        "lines_cut_at_256": any(len(line) >= _LINE_WIDTH - 1 for line in lines),
    }
    if failed:
        result["error_type"] = "ReportRunFailed"
        result["error_message"] = result["sap_result"] or "INST_EXECUTE_REPORT reported an error."
        result["hint"] = "The RFC user needs authorization for transaction SA38 and for the report itself."
    table = _alv_table(shown)
    if table:
        result["columns"], result["rows"] = table
    else:
        result["lines"] = shown
    if not lines and not failed:
        result["hint"] = "The report produced no list: no data matched, or it ended with a message."
    return json_safe(result)
