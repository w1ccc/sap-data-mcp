"""Shared runtime for sap-data-mcp: the MCP server with tool call auditing, the
single SAP RFC connector, and helpers used by every tool module."""

from __future__ import annotations

import atexit
import getpass
import logging
import os
import re
import uuid
from collections.abc import Iterable, Sequence
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
from fnmatch import fnmatchcase
from pathlib import Path
from time import perf_counter
from typing import Any

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from connectors import SAPRFCConnector, rfc_call_trace

from .audit_log import ToolCallAuditLog


PROJECT_NAME = "sap-data-mcp"
PROJECT_VERSION = "0.2.0"
PROJECT_DIR = Path(__file__).resolve().parents[1]
SYSTEM_INFO_PATH = PROJECT_DIR / "config" / "SAP_SYSTEM_INFO"
LOG_DIR = PROJECT_DIR / "logs"
SESSION_ID = uuid.uuid4().hex[:12]

load_dotenv(PROJECT_DIR / ".env", override=True)

logger = logging.getLogger(PROJECT_NAME)

# Tool annotations: SAP tools only read from SAP; local tools do not leave this machine.
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)
LOCAL_READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

sap_rfc = SAPRFCConnector(SYSTEM_INFO_PATH, PROJECT_DIR / ".env")
atexit.register(sap_rfc.close)


def redact_sensitive_text(message: str) -> str:
    """Return text with local credential values removed."""
    for variable in ("SAP_USERNAME", "SAP_PASSWORD"):
        value = os.getenv(variable, "")
        if value:
            message = message.replace(value, "[REDACTED]")
    return message


def redact_password(message: str) -> str:
    """Return text with the local SAP password removed; the audit log keeps the user."""
    password = os.getenv("SAP_PASSWORD", "")
    return message.replace(password, "[REDACTED]") if password else message


# ---------------------------------------------------------------------------
# Tool call audit log
# ---------------------------------------------------------------------------

audit_log = ToolCallAuditLog(LOG_DIR, redact_password)


def _os_user() -> str | None:
    try:
        return getpass.getuser()
    except Exception:
        return os.getenv("USERNAME")


OS_USER = _os_user()


def _mcp_client(context: Any) -> str | None:
    try:
        info = context.session.client_params.client_info
    except Exception:
        return None
    return " ".join(part for part in (info.name, info.version) if part) or None


def _request_id(context: Any) -> str | None:
    try:
        return context.request_id
    except Exception:
        return None


def _sap_target() -> tuple[str | None, str | None]:
    try:
        info = sap_rfc.system_info
    except Exception:
        return None, None
    return info.get("System ID"), info.get("Client")


def _outcome(result: Any) -> tuple[str, str | None]:
    """Return the audit status and error text of a CallToolResult."""
    if getattr(result, "is_error", False):
        texts = [getattr(item, "text", "") for item in getattr(result, "content", None) or []]
        return "error", " ".join(text for text in texts if text) or None
    structured = getattr(result, "structured_content", None)
    if not isinstance(structured, dict) or not isinstance(structured.get("status"), str):
        return "ok", None
    status = structured["status"]
    if status != "error":
        return status, None
    error = structured.get("error_message")
    if not isinstance(error, str):
        messages = structured.get("return_messages") or []
        error = next(
            (m.get("message") for m in messages if isinstance(m, dict) and m.get("type") in {"A", "E", "X"}),
            None,
        )
    return status, error


def _write_audit_entry(
    name: str,
    arguments: dict[str, Any],
    context: Any,
    status: str,
    error: str | None,
    rfc_functions: list[str],
    elapsed: float,
) -> None:
    system, client = _sap_target()
    try:
        audit_log.record(
            {
                "session_id": SESSION_ID,
                "request_id": _request_id(context),
                "mcp_client": _mcp_client(context),
                "os_user": OS_USER,
                "sap_user": os.getenv("SAP_USERNAME", "").strip() or None,
                "sap_system": system,
                "sap_client": client,
                "tool": name,
                "arguments": arguments,
                "status": status,
                "error": error,
                "rfc_functions": rfc_functions,
                "duration_ms": round(elapsed * 1000),
            }
        )
    except Exception:
        logger.exception("Could not write the tool call audit log.")


class AuditedMCPServer(MCPServer):
    """MCPServer that appends every tool call to logs/tool_calls_YYYY-MM-DD.jsonl."""

    async def call_tool(self, name: str, arguments: dict[str, Any], context: Any = None) -> Any:
        rfc_functions: list[str] = []
        token = rfc_call_trace.set(rfc_functions)
        started = perf_counter()
        status, error = "exception", None
        try:
            result = await super().call_tool(name, arguments, context)
            status, error = _outcome(result)
            return result
        except BaseException as exc:
            error = f"{type(exc).__name__}: {exc}"
            cause = exc.__cause__
            if cause is not None and str(cause) not in str(exc):
                error += f" ({type(cause).__name__}: {cause})"
            raise
        finally:
            rfc_call_trace.reset(token)
            _write_audit_entry(name, arguments, context, status, error, rfc_functions, perf_counter() - started)


mcp = AuditedMCPServer(
    PROJECT_NAME,
    version=PROJECT_VERSION,
    instructions=(
        "Read-only access to SAP S/4HANA over RFC. Call test_sap_rfc_connection once per "
        "session before any other SAP tool. Dates accept YYYY-MM-DD or YYYYMMDD. Monitoring "
        "tools (ST22, SM21, SLG1, SM37, IDoc, qRFC/tRFC) use SAP application server local time."
    ),
)


# ---------------------------------------------------------------------------
# RFC results
# ---------------------------------------------------------------------------


def _redact_rfc_error(error: BaseException) -> str:
    """Return an RFC error message with local credential values removed."""
    return redact_sensitive_text(str(getattr(error, "message", error)))


def rfc_error_result(error: BaseException, **fields: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "error",
        "connection": "RFC",
        "error_type": f"{type(error).__module__}.{type(error).__name__}",
        "error_key": getattr(error, "key", None),
        "error_message": _redact_rfc_error(error),
    }
    if getattr(error, "key", None) == "RFC_LOGON_FAILURE":
        result["possible_causes"] = [
            "RFC password logon may be disabled by system policy.",
            "The SAP user type may not allow RFC logon.",
            "SNC or SSO may be required for RFC logon.",
            "Client or user authentication policy may reject RFC password logon.",
        ]
    result.update(fields)
    return result


def connection_unavailable(function: str | Sequence[str]) -> dict[str, Any]:
    return {
        "status": "error",
        "connection": "RFC",
        "function": function,
        "error_type": "RFCConnectionUnavailable",
        "error_message": (
            "RFC login is not established; call test_sap_rfc_connection first "
            "in the same MCP Server session."
        ),
    }


def validation_error(function: str | Sequence[str], message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "connection": "RFC",
        "function": function,
        "error_type": "ValidationError",
        "error_message": message,
    }


def call_rfc(function: str, **params: Any) -> dict[str, Any]:
    """Call an allowlisted function; invalid packed numbers come back as NaN instead of raising."""
    with localcontext() as context:
        context.traps[InvalidOperation] = False
        return sap_rfc.call(function, **params)


def json_safe(value: Any) -> Any:
    """Convert RFC response values into MCP JSON-compatible values."""
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return str(value) if value.is_finite() else None
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


def return_messages(value: Any) -> list[dict[str, Any]]:
    """Normalize BAPIRETURN/BAPIRET1/BAPIRET2 structures or tables, skipping empty rows."""
    rows = [value] if isinstance(value, dict) else (value or [])
    messages = []
    for row in rows:
        if not (row.get("TYPE") or row.get("MESSAGE")):
            continue
        code = str(row.get("CODE") or "")
        split_code = len(code) == 5 and code[-3:].isdigit()
        messages.append(
            {
                "type": row.get("TYPE"),
                "id": row.get("ID") or (code[:-3] if split_code else code or None),
                "number": row.get("NUMBER") or (code[-3:] if split_code else None),
                "message": row.get("MESSAGE"),
            }
        )
    return messages


def read_bapi(function: str, params: dict[str, Any], max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read a code-fixed BAPI and retain its native fields, with paging for each returned table."""
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    if not 1 <= max_results <= 500 or offset < 0:
        return validation_error(function, "max_results must be 1-500 and offset must be non-negative.")
    try:
        response = call_rfc(function, **params)
    except Exception as error:
        return rfc_error_result(error, function=function)
    messages = return_messages(response.get("RETURN"))
    data, paging = {}, {}
    for name, value in response.items():
        if name == "RETURN" or (name == "SELECTIONCRITERIA" and name in params):
            continue
        if isinstance(value, list):
            start = 0 if name in {"HEADER", "ORDER_HEADERS_OUT", "TOHEADERDATA"} else offset
            data[name], paging[name] = page(value[start:], max_results, exact_total="MAXROWS" not in params)
            if "MAXROWS" not in params:
                paging[name]["total"] = len(value)
            paging[name].update(offset=start, next_offset=start + max_results if len(value) > start + max_results else None)
        else:
            data[name] = value
    present = any(bool(value) if isinstance(value, list) else bool(compact(value)) for value in data.values())
    status = ("partial" if present else "error") if has_error(messages) else "ok" if present else "not_found"
    return json_safe({"status": status, "connection": "RFC", "function": function,
                      "data": data, "paging": paging, "return_messages": messages})


def has_error(messages: Iterable[dict[str, Any]]) -> bool:
    return any(message.get("type") in {"A", "E", "X"} for message in messages)


def has_error_except(messages: Iterable[dict[str, Any]], *ignored: tuple[str, str]) -> bool:
    """has_error, ignoring the (message class, number) pairs SAP uses for "nothing found"."""
    return has_error(m for m in messages if (m.get("id"), m.get("number")) not in ignored)


_ZERO_TEXT = re.compile(r"[+-]?(0+\.?0*|\.0+)")


def is_initial(value: Any) -> bool:
    """True for SAP initial values: blanks, zeros, zero dates and empty tables."""
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip()
        return not text or _ZERO_TEXT.fullmatch(text) is not None
    if isinstance(value, Decimal):
        return not value.is_finite() or value == 0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value == 0
    if isinstance(value, (dict, list, tuple)):
        return not value
    return False


def compact(value: Any) -> Any:
    """Recursively drop initial fields so SAP structures only show maintained values."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            item = compact(item)
            if not is_initial(item):
                result[key] = item
        return result
    if isinstance(value, (list, tuple)):
        return [row for row in (compact(item) for item in value) if not is_initial(row)]
    return value


def pick(row: dict[str, Any], fields: Sequence[str]) -> dict[str, Any]:
    """Return the listed SAP fields that carry a value, in the listed order."""
    return {field: row[field] for field in fields if field in row and not is_initial(row[field])}


def without_blanks(row: dict[str, Any]) -> dict[str, Any]:
    """Drop None and blank-string fields but keep zeros (counts, quantities, numbers)."""
    return {
        key: value
        for key, value in row.items()
        if value is not None and not (isinstance(value, str) and not value.strip())
    }


def page(rows: list[Any], max_results: int, exact_total: bool = True) -> tuple[list[Any], dict[str, Any]]:
    """Cut rows to max_results and describe what was left out.

    Pass exact_total=False when SAP itself capped the rows, so len(rows) is no total.
    """
    paging: dict[str, Any] = {"total": len(rows)} if exact_total else {}
    paging.update({"returned": min(len(rows), max_results), "truncated": len(rows) > max_results})
    return rows[:max_results], paging


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def wildcard_match(value: Any, pattern: str) -> bool:
    """Case-insensitive match; * and ? are wildcards, otherwise the values must be equal."""
    text = str(value or "").strip().upper()
    pattern = pattern.strip().upper()
    if "*" in pattern or "?" in pattern:
        return fnmatchcase(text, pattern)
    return text == pattern


# ---------------------------------------------------------------------------
# Input normalization (raise ValueError with a caller-facing message)
# ---------------------------------------------------------------------------


def sap_key(value: str, name: str, max_length: int, numeric_length: int | None = None) -> str:
    """Upper-case a document or master data key and apply ALPHA padding to numbers."""
    text = value.strip().upper()
    if not text or len(text) > max_length or "*" in text or not text.isprintable():
        raise ValueError(f"{name} must be 1 to {max_length} characters without wildcards.")
    if numeric_length and text.isdigit() and len(text) <= numeric_length:
        text = text.zfill(numeric_length)
    return text


def material_number(value: str) -> str:
    """Internal material number: numeric values are padded to 18 digits (MATN1)."""
    return sap_key(value, "material", 40, numeric_length=18)


def org_unit(value: str, name: str, length: int) -> str:
    """Validate an optional organizational unit key such as a plant (empty stays empty)."""
    text = value.strip().upper()
    if text and (len(text) > length or not text.isalnum()):
        raise ValueError(f"{name} must be up to {length} letters or digits.")
    return text


def sap_date(value: str, name: str) -> str:
    """Accept YYYY-MM-DD or YYYYMMDD and return SAP YYYYMMDD."""
    text = value.strip().replace("-", "").replace("/", "").replace(".", "")
    try:
        if len(text) != 8:
            raise ValueError
        datetime.strptime(text, "%Y%m%d")
    except ValueError:
        raise ValueError(f"{name} must be a date like 2026-09-28 or 20260928.") from None
    return text


def sap_time(value: str, name: str) -> str:
    """Accept HH:MM, HH:MM:SS or HHMMSS and return SAP HHMMSS."""
    text = value.strip().replace(":", "")
    if len(text) == 4:
        text += "00"
    try:
        if len(text) != 6:
            raise ValueError
        datetime.strptime(text, "%H%M%S")
    except ValueError:
        raise ValueError(f"{name} must be a time like 13:30, 13:30:00 or 133000.") from None
    return text


def sap_datetime(sap_date_value: Any, sap_time_value: Any = "") -> str | None:
    """Format SAP date and time fields as ISO 8601 local time; None when the date is initial."""
    day = str(sap_date_value or "").strip().replace("-", "")
    if len(day) != 8 or not day.isdigit() or is_initial(day):
        return None
    clock = str(sap_time_value or "").strip().replace(":", "")
    iso_day = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    if len(clock) != 6 or not clock.isdigit():
        return iso_day
    return f"{iso_day}T{clock[:2]}:{clock[2:4]}:{clock[4:]}"


# ---------------------------------------------------------------------------
# SAP server time (monitoring tools work in the application server's local time)
# ---------------------------------------------------------------------------


def sap_server_clock() -> tuple[datetime, timedelta]:
    """Return the SAP application server's local time now and its offset from UTC.

    RFC_SYSTEM_INFO reports the standard offset (SY-TZONE) and whether daylight saving
    time is active (SY-DAYST).
    """
    info = call_rfc("RFC_SYSTEM_INFO").get("RFCSI_EXPORT", {})
    seconds = int(str(info.get("RFCTZONE") or "0").strip() or "0")
    if info.get("RFCDAYST") == "X":
        seconds += 3600
    offset = timedelta(seconds=seconds)
    return datetime.now(timezone.utc).replace(tzinfo=None) + offset, offset


def utc_offset_label(offset: timedelta) -> str:
    total = int(offset.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"UTC{sign}{total // 3600:02d}:{total % 3600 // 60:02d}"


def time_window(
    date_from: str,
    time_from: str,
    date_to: str,
    time_to: str,
    now: datetime,
    max_days: int,
) -> tuple[datetime, datetime]:
    """Resolve an SAP-local window; empty dates mean the server's today, empty times the whole day."""
    today = now.strftime("%Y%m%d")
    start = datetime.strptime(
        (sap_date(date_from, "date_from") if date_from.strip() else today)
        + (sap_time(time_from, "time_from") if time_from.strip() else "000000"),
        "%Y%m%d%H%M%S",
    )
    end = datetime.strptime(
        (sap_date(date_to, "date_to") if date_to.strip() else today)
        + (sap_time(time_to, "time_to") if time_to.strip() else "235959"),
        "%Y%m%d%H%M%S",
    )
    if end < start:
        raise ValueError("The end of the time window is before its start.")
    if end - start > timedelta(days=max_days):
        raise ValueError(f"The time window may cover at most {max_days} days.")
    return start, end


def resolve_window(
    date_from: str,
    time_from: str,
    date_to: str,
    time_to: str,
    max_days: int,
) -> tuple[datetime, datetime, timedelta]:
    """Read the SAP server clock and resolve a local window (see time_window).

    Raises ValueError for invalid input and RFC errors from RFC_SYSTEM_INFO.
    """
    now, offset = sap_server_clock()
    start, end = time_window(date_from, time_from, date_to, time_to, now, max_days)
    return start, end, offset


def window_info(start: datetime, end: datetime, offset: timedelta) -> dict[str, str]:
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "time_zone": f"{utc_offset_label(offset)} (SAP server local time)",
    }
