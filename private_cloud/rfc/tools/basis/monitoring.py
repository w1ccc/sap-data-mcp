"""System monitoring tools: ST22 short dumps, SM21 system log, SLG1 application logs, SM37 jobs."""

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from core.app import (
    READ_ONLY,
    call_rfc,
    clamp,
    connection_unavailable,
    has_error,
    has_error_except,
    json_safe,
    logger,
    mcp,
    page,
    resolve_window,
    return_messages,
    rfc_error_result,
    sap_datetime,
    sap_rfc,
    validation_error,
    wildcard_match,
    window_info,
    without_blanks,
)


XMI_COMPANY = "MCP"
XMI_PRODUCT = "SAP-DATA-MCP"
XMI_EXTERNAL_USER = "SAP-DATA-MCP"

# Generic E2E log columns of /SDF/GET_DUMP_LOG and /SDF/GET_SYS_LOG
# (named by the ES_E2E_LOG_STRUCT_DESC export of each function).
_DUMP_FIELDS = {
    "FIELD1": "runtime_error",
    "FIELD2": "exception",
    "FIELD4": "program",
    "FIELD9": "short_text",
    "FIELD3": "component",
    "FIELD7": "application_component",
    "FIELD5": "package",
}
_SYSLOG_FIELDS = {
    "FIELD7": "message_id",
    "FIELD6": "text",
    "FIELD3": "problem_class",
    "FIELD4": "program",
    "FIELD5": "transaction",
    "FIELD2": "component",
    "FIELD9": "application_component",
    "FIELD8": "package",
    "FIELD1": "software_component",
}

_JOB_STATUS = {
    "P": "scheduled",
    "S": "released",
    "Z": "released_suspended",
    "Y": "ready",
    "R": "active",
    "F": "finished",
    "A": "canceled",
}
_JOB_STATUS_FLAGS = {
    "scheduled": "PRELIM",
    "released": "SCHEDUL",
    "ready": "READY",
    "active": "RUNNING",
    "finished": "FINISHED",
    "canceled": "ABORTED",
}


class XMILogonError(RuntimeError):
    """Raised when BAPI_XMI_LOGON refuses the XBP session (e.g. missing S_XMI_PROD)."""


def _window_params(start: datetime, end: datetime) -> dict[str, str]:
    return {
        "DATE_FROM": start.strftime("%Y%m%d"),
        "TIME_FROM": start.strftime("%H%M%S"),
        "DATE_TO": end.strftime("%Y%m%d"),
        "TIME_TO": end.strftime("%H%M%S"),
    }


def _user_and_client(value: str) -> tuple[str, str | None]:
    """E2E logs report users as USER_CLIENT, e.g. SAP_SYSTEM_460."""
    user, _, client = (value or "").rpartition("_")
    if user and len(client) == 3 and client.isdigit():
        return user, client
    return value, None


def _e2e_entries(rows: list[dict[str, Any]], fields: dict[str, str]) -> list[dict[str, Any]]:
    entries = []
    for row in rows:
        user, client = _user_and_client(row.get("E2E_USER", ""))
        entry = {
            "timestamp": sap_datetime(row.get("E2E_DATE"), row.get("E2E_TIME")),
            "host": row.get("E2E_HOST"),
            "user": user,
            "client": client,
        }
        entry.update({name: row.get(field) for field, name in fields.items()})
        entries.append(without_blanks(entry))
    entries.sort(key=lambda entry: entry.get("timestamp") or "", reverse=True)
    return entries


def _count(value: Any) -> int:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else 0


def _job(row: dict[str, Any]) -> dict[str, Any]:
    """Map a job header (BAPIXMJOB or TBTCO) to SM37-style fields."""
    start = sap_datetime(row.get("STRTDATE"), row.get("STRTTIME"))
    end = sap_datetime(row.get("ENDDATE"), row.get("ENDTIME"))
    duration = None
    if start and end and "T" in start and "T" in end:
        duration = int((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())
    return without_blanks(
        {
            "job_name": row.get("JOBNAME"),
            "job_count": row.get("JOBCOUNT"),
            "status": _JOB_STATUS.get(row.get("STATUS"), row.get("STATUS")),
            "scheduled_by": row.get("SDLUNAME"),
            "planned_start": sap_datetime(row.get("SDLSTRTDT"), row.get("SDLSTRTTM")),
            "start": start,
            "end": end,
            "duration_seconds": duration,
            "periodic": row.get("PERIODIC") == "X",
            "job_class": row.get("JOBCLASS"),
            "server": (row.get("EXECSERVER") or "").strip() or (row.get("REAXSERVER") or "").strip(),
            "steps": row.get("STEPCOUNT"),
            "event": row.get("EVENTID"),
            "client": row.get("AUTHCKMAN"),
        }
    )


@contextmanager
def _xmi_session() -> Iterator[None]:
    """Open an XMI session for the XBP interface; logon and logoff only write the XMI audit log."""
    response = call_rfc(
        "BAPI_XMI_LOGON",
        EXTCOMPANY=XMI_COMPANY,
        EXTPRODUCT=XMI_PRODUCT,
        INTERFACE="XBP",
        VERSION="3.0",
    )
    messages = return_messages(response.get("RETURN"))
    if has_error(messages):
        raise XMILogonError("; ".join(message["message"] or "" for message in messages))
    try:
        yield
    finally:
        try:
            call_rfc("BAPI_XMI_LOGOFF", INTERFACE="XBP")
        except Exception:
            logger.warning("BAPI_XMI_LOGOFF failed.", exc_info=True)


@mcp.tool(annotations=READ_ONLY)
async def list_short_dumps(
    date_from: str = "",
    time_from: str = "",
    date_to: str = "",
    time_to: str = "",
    user: str = "",
    runtime_error: str = "",
    program: str = "",
    client: str = "",
    max_results: int = 50,
) -> dict[str, Any]:
    """List ABAP short dumps (ST22) of all clients with /SDF/GET_DUMP_LOG, newest first.

    The window is SAP server local time, defaults to the server's today and may cover
    at most 31 days. user, runtime_error (e.g. "TIME_OUT") and program accept *
    wildcards; client keeps one client only. max_results: 1-500.
    """
    functions = ["RFC_SYSTEM_INFO", "/SDF/GET_DUMP_LOG"]
    if not sap_rfc.is_connected:
        return connection_unavailable(functions)
    try:
        start, end, offset = resolve_window(date_from, time_from, date_to, time_to, max_days=31)
    except ValueError as error:
        return validation_error(functions, str(error))
    except Exception as error:
        return rfc_error_result(error, function=functions)

    try:
        response = call_rfc("/SDF/GET_DUMP_LOG", **_window_params(start, end))
    except Exception as error:
        return rfc_error_result(error, function=functions)

    dumps = [
        entry
        for entry in _e2e_entries(response.get("ET_E2E_LOG") or [], _DUMP_FIELDS)
        if (not user.strip() or wildcard_match(entry.get("user"), user))
        and (not runtime_error.strip() or wildcard_match(entry.get("runtime_error"), runtime_error))
        and (not program.strip() or wildcard_match(entry.get("program"), program))
        and (not client.strip() or entry.get("client") == client.strip())
    ]
    rows, paging = page(dumps, clamp(max_results, 1, 500))
    return json_safe(
        {
            "status": "ok",
            "connection": "RFC",
            "function": functions,
            "window": window_info(start, end, offset),
            "by_runtime_error": dict(Counter(entry.get("runtime_error") for entry in dumps).most_common(10)),
            **paging,
            "dumps": rows,
        }
    )


@mcp.tool(annotations=READ_ONLY)
async def list_system_log(
    date_from: str = "",
    time_from: str = "",
    date_to: str = "",
    time_to: str = "",
    message_id: str = "",
    user: str = "",
    text: str = "",
    client: str = "",
    max_results: int = 100,
) -> dict[str, Any]:
    """List SM21 system log entries of all application servers with /SDF/GET_SYS_LOG, newest first.

    message_id (such as "BY-2" or "BY*") and user accept * wildcards; text keeps entries
    whose message contains it (case-insensitive); client keeps one client only. The window
    is SAP server local time, defaults to today and may cover at most 7 days.
    """
    functions = ["RFC_SYSTEM_INFO", "/SDF/GET_SYS_LOG"]
    if not sap_rfc.is_connected:
        return connection_unavailable(functions)
    try:
        start, end, offset = resolve_window(date_from, time_from, date_to, time_to, max_days=7)
    except ValueError as error:
        return validation_error(functions, str(error))
    except Exception as error:
        return rfc_error_result(error, function=functions)

    try:
        response = call_rfc("/SDF/GET_SYS_LOG", **_window_params(start, end))
    except Exception as error:
        return rfc_error_result(error, function=functions)

    needle = text.strip().lower()
    entries = [
        entry
        for entry in _e2e_entries(response.get("ET_E2E_LOG") or [], _SYSLOG_FIELDS)
        if (not message_id.strip() or wildcard_match(entry.get("message_id"), message_id))
        and (not user.strip() or wildcard_match(entry.get("user"), user))
        and (not needle or needle in str(entry.get("text", "")).lower())
        and (not client.strip() or entry.get("client") == client.strip())
    ]
    rows, paging = page(entries, clamp(max_results, 1, 1000))
    return json_safe(
        {
            "status": "ok",
            "connection": "RFC",
            "function": functions,
            "window": window_info(start, end, offset),
            "by_message_id": dict(Counter(entry.get("message_id") for entry in entries).most_common(10)),
            **paging,
            "entries": rows,
        }
    )


@mcp.tool(annotations=READ_ONLY)
async def search_application_logs(
    log_object: str = "",
    subobject: str = "",
    external_id: str = "",
    date_from: str = "",
    time_from: str = "",
    date_to: str = "",
    time_to: str = "",
    user: str = "",
    problems_only: bool = False,
    max_results: int = 50,
) -> dict[str, Any]:
    """Search application logs (SLG1) of the current client with /SDF/GET_APP_LOG, newest first.

    log_object and subobject are the SLG1 object/subobject, external_id the external ID.
    problems_only keeps logs with error or abort messages; user accepts * wildcards.
    Each log shows its message counts and up to 3 error texts; read all messages with
    get_application_log_messages. The window is SAP server local time, defaults to
    today and may cover at most 7 days.
    """
    functions = ["RFC_SYSTEM_INFO", "/SDF/GET_APP_LOG"]
    if not sap_rfc.is_connected:
        return connection_unavailable(functions)
    log_object = log_object.strip().upper()
    subobject = subobject.strip().upper()
    external_id = external_id.strip()
    if len(log_object) > 20 or len(subobject) > 20 or len(external_id) > 100:
        return validation_error(
            functions, "log_object and subobject allow 20 characters, external_id 100 characters."
        )
    try:
        start, end, offset = resolve_window(date_from, time_from, date_to, time_to, max_days=7)
    except ValueError as error:
        return validation_error(functions, str(error))
    except Exception as error:
        return rfc_error_result(error, function=functions)

    params = _window_params(start, end)
    for parameter, value in (("OBJECT", log_object), ("SUBOBJECT", subobject), ("EXTERNAL_NUMBER", external_id)):
        if value:
            params[parameter] = value
    try:
        response = call_rfc("/SDF/GET_APP_LOG", **params)
    except Exception as error:
        return rfc_error_result(error, function=functions)

    error_texts: dict[str, list[dict[str, Any]]] = {}
    for row in response.get("ET_E2E_LOG") or []:
        error_texts.setdefault(row.get("FIELD1"), []).append(
            without_blanks({"message_id": row.get("FIELD7"), "text": row.get("FIELD6")})
        )

    logs = []
    for header in response.get("LOG_HEADER_T") or []:
        counts = {
            name: _count(header.get(field))
            for name, field in (
                ("total", "MSG_CNT_AL"),
                ("abort", "MSG_CNT_A"),
                ("error", "MSG_CNT_E"),
                ("warning", "MSG_CNT_W"),
                ("info", "MSG_CNT_I"),
                ("success", "MSG_CNT_S"),
            )
        }
        if problems_only and not (counts["abort"] or counts["error"]):
            continue
        if user.strip() and not wildcard_match(header.get("ALUSER"), user):
            continue
        logs.append(
            without_blanks(
                {
                    "log_number": header.get("LOGNUMBER"),
                    "object": header.get("OBJECT"),
                    "subobject": header.get("SUBOBJECT"),
                    "external_id": header.get("EXTNUMBER"),
                    "timestamp": sap_datetime(header.get("ALDATE"), header.get("ALTIME")),
                    "user": header.get("ALUSER"),
                    "transaction": header.get("ALTCODE"),
                    "program": header.get("ALPROG"),
                    "mode": header.get("ALMODE"),
                    "problem_class": header.get("PROBCLASS"),
                    "message_counts": {name: count for name, count in counts.items() if count},
                    "error_messages": error_texts.get(header.get("LOGNUMBER"), [])[:3] or None,
                }
            )
        )
    logs.sort(key=lambda log: log.get("timestamp") or "", reverse=True)
    rows, paging = page(logs, clamp(max_results, 1, 500))
    by_object = Counter(f"{log.get('object', '')}/{log.get('subobject', '')}" for log in logs)
    return json_safe(
        {
            "status": "ok",
            "connection": "RFC",
            "function": functions,
            "window": window_info(start, end, offset),
            "by_object": dict(by_object.most_common(10)),
            **paging,
            "logs": rows,
        }
    )


@mcp.tool(annotations=READ_ONLY)
async def get_application_log_messages(log_number: str, max_messages: int = 200) -> dict[str, Any]:
    """Read all messages of one application log (SLG1) with BAPI_APPLICATIONLOG_GETDETAIL.

    log_number comes from search_application_logs or from an IDoc status record
    (get_idoc). max_messages: 1-1000.
    """
    function = "BAPI_APPLICATIONLOG_GETDETAIL"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    number = log_number.strip()
    if not number.isdigit() or len(number) > 20:
        return validation_error(function, "log_number must contain 1 to 20 digits.")
    number = number.zfill(20)

    try:
        response = call_rfc(function, LOGKEYS=[{"LOGNUMBER": number, "MSGNUMBER": "000000"}])
    except Exception as error:
        return rfc_error_result(error, function=function, log_number=number)

    messages = return_messages(response.get("RETURN"))
    rows = response.get("LOGDATA") or []
    if not rows:
        # S& 115 "No relevant application log entries found"
        return json_safe(
            {
                "status": "error" if has_error_except(messages, ("S&", "115")) else "not_found",
                "connection": "RFC",
                "function": function,
                "log_number": number,
                "return_messages": messages,
            }
        )

    entries = [
        without_blanks(
            {
                "number": _count(row.get("MSGNUMBER")),
                "type": row.get("TYPE"),
                "id": row.get("ID"),
                "message_number": row.get("NUMBER"),
                "text": row.get("MESSAGE"),
                "timestamp": sap_datetime(row.get("DATE"), row.get("TIME")),
                "user": row.get("USER"),
            }
        )
        for row in rows
    ]
    shown, paging = page(entries, clamp(max_messages, 1, 1000))
    first = rows[0]
    return json_safe(
        {
            "status": "ok",
            "connection": "RFC",
            "function": function,
            "log_number": number,
            "object": first.get("OBJECT"),
            "subobject": first.get("SUBOBJECT"),
            "external_id": first.get("EXTNUMBER"),
            "by_type": dict(Counter(entry.get("type") for entry in entries)),
            **paging,
            "messages": shown,
            "return_messages": messages,
        }
    )


@mcp.tool(annotations=READ_ONLY)
async def list_background_jobs(
    job_name: str = "*",
    user: str = "*",
    status: str = "",
    date_from: str = "",
    time_from: str = "",
    date_to: str = "",
    time_to: str = "",
    max_results: int = 100,
) -> dict[str, Any]:
    """List background jobs (SM37) with the XBP interface BAPI_XBP_JOB_SELECT, newest first.

    job_name and user accept * wildcards. status is a comma-separated subset of
    scheduled, released, ready, active, finished, canceled (default: all). The window is
    SAP server local time, defaults to today and may cover at most 7 days; by_status
    counts all selected jobs. The XBP call runs in an XMI session: BAPI_XMI_LOGON and
    BAPI_XMI_LOGOFF only write the XMI audit log. Read a job log with get_background_job_log.
    """
    functions = ["RFC_SYSTEM_INFO", "BAPI_XMI_LOGON", "BAPI_XBP_JOB_SELECT", "BAPI_XMI_LOGOFF"]
    if not sap_rfc.is_connected:
        return connection_unavailable(functions)
    name = (job_name.strip() or "*").upper()
    owner = (user.strip() or "*").upper()
    statuses = [value.strip().lower() for value in status.split(",") if value.strip()]
    unknown = sorted(set(statuses) - set(_JOB_STATUS_FLAGS))
    if unknown:
        return validation_error(
            functions, f"Unknown status {', '.join(unknown)}; use {', '.join(_JOB_STATUS_FLAGS)}."
        )
    if len(name) > 32 or len(owner) > 12:
        return validation_error(functions, "job_name allows 32 characters, user 12 characters.")
    try:
        start, end, offset = resolve_window(date_from, time_from, date_to, time_to, max_days=7)
    except ValueError as error:
        return validation_error(functions, str(error))
    except Exception as error:
        return rfc_error_result(error, function=functions)

    selection = {
        "JOBNAME": name,
        "USERNAME": owner,
        "FROM_DATE": start.strftime("%Y%m%d"),
        "FROM_TIME": start.strftime("%H%M%S"),
        "TO_DATE": end.strftime("%Y%m%d"),
        "TO_TIME": end.strftime("%H%M%S"),
    }
    selection.update(
        {flag: "X" for label, flag in _JOB_STATUS_FLAGS.items() if not statuses or label in statuses}
    )
    try:
        with _xmi_session():
            response = call_rfc(
                "BAPI_XBP_JOB_SELECT",
                JOB_SELECT_PARAM=selection,
                EXTERNAL_USER_NAME=XMI_EXTERNAL_USER,
            )
    except Exception as error:
        return rfc_error_result(error, function=functions)

    messages = return_messages(response.get("RETURN"))
    jobs = [_job(row) for row in response.get("JOB_HEAD") or []]
    jobs.sort(key=lambda job: job.get("start") or job.get("planned_start") or "", reverse=True)
    rows, paging = page(jobs, clamp(max_results, 1, 1000))
    return json_safe(
        {
            # XM 057 "No job was found that corresponds to the specification"
            "status": "error" if has_error_except(messages, ("XM", "057")) and not jobs else "ok",
            "connection": "RFC",
            "function": functions,
            "window": window_info(start, end, offset),
            "by_status": dict(Counter(job.get("status") for job in jobs).most_common()),
            **paging,
            "jobs": rows,
            "return_messages": messages,
        }
    )


@mcp.tool(annotations=READ_ONLY)
async def get_background_job_log(job_name: str, job_count: str, max_lines: int = 200) -> dict[str, Any]:
    """Read one background job's header and job log (SM37) with /SDF/GET_JOB_INFO.

    job_name and job_count (the job ID) come from list_background_jobs. The last
    max_lines log lines are returned (1-2000).
    """
    function = "/SDF/GET_JOB_INFO"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    name = job_name.strip().upper()
    count = job_count.strip()
    if not name or len(name) > 32 or "*" in name:
        return validation_error(function, "job_name must be 1 to 32 characters without wildcards.")
    if not count.isdigit() or len(count) > 8:
        return validation_error(function, "job_count must contain 1 to 8 digits.")
    count = count.zfill(8)

    try:
        response = call_rfc(function, IT_JOB_HEAD=[{"JOBNAME": name, "JOBCOUNT": count}])
    except Exception as error:
        return rfc_error_result(error, function=function, job_name=name, job_count=count)

    messages = return_messages(response.get("ET_RETURN"))
    heads = response.get("ET_JOBHEAD") or []
    if not heads:
        # /SDF/JOB_INFO 002 "Job name ... job count ... does not exist"
        return json_safe(
            {
                "status": "error" if has_error_except(messages, ("/SDF/JOB_INFO", "002")) else "not_found",
                "connection": "RFC",
                "function": function,
                "job_name": name,
                "job_count": count,
                "return_messages": messages,
            }
        )

    log = [
        without_blanks(
            {
                "timestamp": sap_datetime(row.get("ENTERDATE"), row.get("ENTERTIME")),
                "type": row.get("MSGTYPE"),
                "id": row.get("MSGID"),
                "number": row.get("MSGNO"),
                "text": row.get("TEXT"),
            }
        )
        for row in response.get("ET_JOBLOG") or []
    ]
    limit = clamp(max_lines, 1, 2000)
    return json_safe(
        {
            "status": "ok",
            "connection": "RFC",
            "function": function,
            "job": _job(heads[0]),
            "log_lines": len(log),
            "truncated": len(log) > limit,
            "log": log[-limit:],
            "return_messages": messages,
        }
    )
