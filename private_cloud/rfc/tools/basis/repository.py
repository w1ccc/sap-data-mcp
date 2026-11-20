"""ABAP repository display: read-only access to program and include source (SE38 display)."""

import re
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
)


_FUNCTION = "RPY_PROGRAM_READ"
_PROGRAM = re.compile(r"[A-Z0-9_/=]{1,40}")

_HINTS = {
    "PERMISSION_ERROR": "The RFC user needs display authorization for the program (S_DEVELOP, ACTVT 03).",
    "NOT_FOUND": "The program or include does not exist.",
}


def _selected_lines(source: list[str], terms: list[str], context: int) -> list[tuple[int, bool]]:
    """Return (index, is_hit) for every line, or for the hits and their context when searching."""
    if not terms:
        return [(index, False) for index in range(len(source))]
    hits = {index for index, line in enumerate(source) if any(term in line.lower() for term in terms)}
    shown: set[int] = set()
    for index in hits:
        shown.update(range(max(0, index - context), min(len(source), index + context + 1)))
    return [(index, index in hits) for index in sorted(shown)]


@mcp.tool(annotations=READ_ONLY)
async def read_program_source(
    program: str,
    search: str = "",
    context_lines: int = 3,
    max_lines: int = 300,
    offset: int = 0,
) -> dict[str, Any]:
    """Display the source of an ABAP program or include (as in SE38 display) with RPY_PROGRAM_READ.

    The result lists the includes of the program; read an include by passing its name. search
    keeps only the lines containing one of the terms separated by "|" (case-insensitive) plus
    context_lines (0-10) lines around each hit; hits are marked with "*". Every line starts
    with its line number. max_lines: 1-1000; use offset to page. Nothing is changed in SAP.
    """
    function = _FUNCTION
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    name = program.strip().upper()
    if not _PROGRAM.fullmatch(name):
        return validation_error(function, "program must be a program or include name of up to 40 characters.")
    if offset < 0:
        return validation_error(function, "offset must be non-negative.")
    limit = clamp(max_lines, 1, 1000)
    context = clamp(context_lines, 0, 10)
    terms = [term.strip().lower() for term in search.split("|") if term.strip()]

    try:
        response = call_rfc(function, PROGRAM_NAME=name, WITH_INCLUDELIST="X", ONLY_SOURCE="X", WITH_LOWERCASE="X")
    except Exception as error:
        result = rfc_error_result(error, function=function, program=name)
        hint = _HINTS.get(str(result.get("error_key") or ""))
        if hint:
            result["hint"] = hint
        return result

    source = [str(row.get("LINE") or "").rstrip() for row in response.get("SOURCE_EXTENDED") or response.get("SOURCE") or []]
    selected = _selected_lines(source, terms, context)
    shown = selected[offset : offset + limit]
    width = len(str(len(source)))
    return json_safe(
        {
            "status": "ok" if source else "not_found",
            "connection": "RFC",
            "function": function,
            "program": name,
            "includes": [str(row.get("INCLNAME") or "").strip() for row in response.get("INCLUDE_TAB") or []],
            "total_lines": len(source),
            "matching_lines": sum(1 for _, hit in selected if hit) if terms else None,
            "offset": offset,
            "returned": len(shown),
            "truncated": offset + len(shown) < len(selected),
            "next_offset": offset + limit if offset + len(shown) < len(selected) else None,
            "lines": [f"{index + 1:>{width}}{'*' if hit else ' '} {source[index]}" for index, hit in shown],
        }
    )
