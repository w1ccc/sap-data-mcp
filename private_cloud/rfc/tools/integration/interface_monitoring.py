"""Interface monitoring tools: IDocs (WE02/WE05), qRFC queues (SMQ1/SMQ2), tRFC (SM58), bgRFC."""

from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from core.app import (
    READ_ONLY,
    call_rfc,
    clamp,
    compact,
    connection_unavailable,
    is_initial,
    json_safe,
    logger,
    mcp,
    page,
    resolve_window,
    rfc_error_result,
    sap_datetime,
    sap_rfc,
    validation_error,
    wildcard_match,
    window_info,
    without_blanks,
)


IDOC_SCAN_LIMIT = 5000
_DIRECTIONS = {"1": "outbound", "2": "inbound"}
# qRFC queue states that need attention in SMQ1/SMQ2.
QUEUE_ERROR_STATES = frozenset({"SYSFAIL", "CPICERR", "STOP", "WAITSTOP", "RETRY", "ARETRY", "ANORETRY", "NOEXEC"})


def _utc_stamp(moment: datetime, offset: timedelta) -> Decimal:
    """SAP UTC time stamp (YYYYMMDDhhmmss) for a server-local time."""
    return Decimal((moment - offset).strftime("%Y%m%d%H%M%S"))


def _utc_to_local(day: Any, clock: Any, offset: timedelta) -> str | None:
    """Convert the collector's UTC date ("2026-04-02") and time ("03:40:57") to server local time."""
    try:
        moment = datetime.strptime(f"{day} {clock}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return (moment + offset).isoformat()


def _status_text(row: dict[str, Any]) -> str:
    """Fill the & placeholders of an IDoc status text with its parameters, as WE02 shows it."""
    text = row.get("STATXT") or ""
    parameters = [(row.get(f"STAPA{index}") or "").strip() for index in range(1, 5)]
    for index, value in enumerate(parameters, start=1):
        text = text.replace(f"&{index}", value)
    for value in parameters:
        if "&" not in text:
            break
        text = text.replace("&", value, 1)
    return text.strip()


def _filter_range(value: str) -> list[dict[str, str]]:
    return [{"SIGN": "I", "OPTION": "CP" if "*" in value else "EQ", "LOW": value, "HIGH": ""}]


@mcp.tool(annotations=READ_ONLY)
async def list_idocs(
    date_from: str = "",
    time_from: str = "",
    date_to: str = "",
    time_to: str = "",
    direction: str = "",
    message_type: str = "",
    idoc_type: str = "",
    sender_partner: str = "",
    receiver_partner: str = "",
    status: str = "",
    errors_only: bool = False,
    max_results: int = 100,
) -> dict[str, Any]:
    """List IDocs created or changed in a time window (WE02/WE05) with /SDF/IMA_DC_IDOC, newest first.

    direction: inbound or outbound. message_type, idoc_type and the partner numbers
    accept * wildcards. status is a comma-separated list such as "51,56"; errors_only
    keeps IDocs whose status has a red traffic light. The window is SAP server local time,
    defaults to today and may cover at most 31 days. At most 5000 IDocs are scanned from
    the start of the window; window_complete=false means narrow the window. Read one IDoc
    with get_idoc.
    """
    functions = ["RFC_SYSTEM_INFO", "/SDF/IMA_DC_IDOC"]
    if not sap_rfc.is_connected:
        return connection_unavailable(functions)
    direction = direction.strip().lower()
    if direction and direction not in _DIRECTIONS.values():
        return validation_error(functions, "direction must be inbound or outbound.")
    statuses = {value.strip().zfill(2) for value in status.split(",") if value.strip()}
    filters = {
        "DIRECT": next((code for code, label in _DIRECTIONS.items() if label == direction), ""),
        "MESTYP": message_type.strip().upper(),
        "IDOCTP": idoc_type.strip().upper(),
        "SNDPRN": sender_partner.strip().upper(),
        "RCVPRN": receiver_partner.strip().upper(),
    }
    if any(len(value) > 30 for value in filters.values()):
        return validation_error(functions, "Filter values may have at most 30 characters.")
    try:
        start, end, offset = resolve_window(date_from, time_from, date_to, time_to, max_days=31)
    except ValueError as error:
        return validation_error(functions, str(error))
    except Exception as error:
        return rfc_error_result(error, function=functions)

    try:
        response = call_rfc(
            "/SDF/IMA_DC_IDOC",
            START_TIMESTAMP=_utc_stamp(start, offset),
            END_TIMESTAMP=_utc_stamp(end + timedelta(seconds=1), offset),
            LIMIT=IDOC_SCAN_LIMIT,
            FILTER=[{"PARAM": param, "VALUE": _filter_range(value)} for param, value in filters.items() if value],
        )
    except Exception as error:
        return rfc_error_result(error, function=functions)

    return_status = response.get("RETURN_STATUS") or {}
    if return_status.get("RC"):
        return json_safe(
            {
                "status": "error",
                "connection": "RFC",
                "function": functions,
                "error_type": "IDocCollectorError",
                "error_message": return_status.get("MESSAGE") or f"RC {return_status.get('RC')}",
            }
        )

    idocs = response.get("IDOCS") or {}
    last_status: dict[str, dict[str, Any]] = {}
    for row in idocs.get("IDOC_STATUS") or []:
        current = last_status.get(row.get("DOCNUM"))
        if current is None or str(row.get("COUNTR")) > str(current.get("COUNTR")):
            last_status[row.get("DOCNUM")] = row

    entries = []
    for header in idocs.get("IDOC_HEADERS") or []:
        if statuses and header.get("STATUS") not in statuses:
            continue
        if errors_only and header.get("STATUS_GROUP") != "ERROR":
            continue
        latest = last_status.get(header.get("DOCNUM")) or {}
        entries.append(
            without_blanks(
                {
                    "idoc": header.get("DOCNUM"),
                    "status": header.get("STATUS"),
                    "status_group": (header.get("STATUS_GROUP") or "").lower(),
                    "direction": _DIRECTIONS.get(header.get("DIRECT")),
                    "message_type": header.get("MESTYP"),
                    "idoc_type": header.get("IDOCTP"),
                    "extension": header.get("CIMTYP"),
                    "sender": compact(
                        {"port": header.get("SNDPOR"), "type": header.get("SNDPRT"), "partner": header.get("SNDPRN")}
                    ),
                    "receiver": compact(
                        {"port": header.get("RCVPOR"), "type": header.get("RCVPRT"), "partner": header.get("RCVPRN")}
                    ),
                    "created": _utc_to_local(header.get("CREDAT"), header.get("CRETIM"), offset),
                    "updated": _utc_to_local(header.get("UPDDAT"), header.get("UPDTIM"), offset),
                    "last_status_text": _status_text(latest) if latest else None,
                    "last_status_message": " ".join(
                        part for part in (latest.get("STAMID"), latest.get("STAMNO")) if part and not is_initial(part)
                    ),
                }
            )
        )
    entries.sort(key=lambda entry: entry.get("updated") or "", reverse=True)
    rows, paging = page(entries, clamp(max_results, 1, 1000))

    complete = response.get("INTERVAL_COMPLETED") == "X"
    result: dict[str, Any] = {
        "status": "ok",
        "connection": "RFC",
        "function": functions,
        "window": window_info(start, end, offset),
        "window_complete": complete,
    }
    if not complete:
        next_start = str(response.get("NEXT_START_TIMESTAMP") or "").split(".")[0]
        if len(next_start) == 14:
            covered = datetime.strptime(next_start, "%Y%m%d%H%M%S") + offset
            result["covered_until"] = covered.isoformat()
    result.update(
        {
            "by_status": dict(Counter(entry.get("status") for entry in entries).most_common()),
            "by_message_type": dict(Counter(entry.get("message_type") for entry in entries).most_common(10)),
            **paging,
            "idocs": rows,
        }
    )
    return json_safe(result)


@mcp.tool(annotations=READ_ONLY)
async def get_idoc(idoc_number: str, include_segments: bool = False, max_segments: int = 200) -> dict[str, Any]:
    """Read one IDoc (WE02): control record, all status records and optionally its data segments.

    Uses EDI_DOCUMENT_OPEN_FOR_READ, EDI_DOCUMENT_READ_ALL_STATUS, EDI_SEGMENTS_GET_ALL and
    EDI_DOCUMENT_CLOSE_READ. Segment data is the raw fixed-width SDATA text. A status
    record's application_log can be read with get_application_log_messages.
    """
    functions = ["EDI_DOCUMENT_OPEN_FOR_READ", "EDI_DOCUMENT_READ_ALL_STATUS", "EDI_DOCUMENT_CLOSE_READ"]
    if include_segments:
        functions.insert(2, "EDI_SEGMENTS_GET_ALL")
    if not sap_rfc.is_connected:
        return connection_unavailable(functions)
    number = idoc_number.strip()
    if not number.isdigit() or len(number) > 16:
        return validation_error(functions, "idoc_number must contain 1 to 16 digits.")
    number = number.zfill(16)

    try:
        control = call_rfc("EDI_DOCUMENT_OPEN_FOR_READ", DOCUMENT_NUMBER=number).get("IDOC_CONTROL") or {}
    except Exception as error:
        if getattr(error, "key", None) == "DOCUMENT_NOT_EXIST":
            return {"status": "not_found", "connection": "RFC", "function": functions, "idoc": number}
        return rfc_error_result(error, function=functions, idoc=number)
    try:
        status_rows = call_rfc("EDI_DOCUMENT_READ_ALL_STATUS", DOCUMENT_NUMBER=number).get("INT_EDIDS") or []
        segment_rows = (
            call_rfc("EDI_SEGMENTS_GET_ALL", DOCUMENT_NUMBER=number).get("IDOC_CONTAINERS") or []
            if include_segments
            else []
        )
    except Exception as error:
        return rfc_error_result(error, function=functions, idoc=number)
    finally:
        try:
            call_rfc("EDI_DOCUMENT_CLOSE_READ", DOCUMENT_NUMBER=number)
        except Exception:
            logger.warning("EDI_DOCUMENT_CLOSE_READ failed for IDoc %s.", number, exc_info=True)

    status_records = [
        without_blanks(
            {
                "counter": int(row.get("COUNTR") or 0),
                "status": row.get("STATUS"),
                "timestamp": sap_datetime(row.get("LOGDAT"), row.get("LOGTIM")),
                "text": _status_text(row),
                "message": " ".join(
                    part for part in (row.get("STAMID"), row.get("STAMNO")) if part and not is_initial(part)
                ),
                "type": row.get("STATYP"),
                "application_log": None if is_initial(row.get("APPL_LOG")) else row.get("APPL_LOG"),
                "user": row.get("UNAME"),
                "program": row.get("REPID"),
                "segment": None if is_initial(row.get("SEGNUM")) else row.get("SEGNUM"),
                "field": row.get("SEGFLD"),
            }
        )
        for row in sorted(status_rows, key=lambda row: str(row.get("COUNTR")))
    ]
    result: dict[str, Any] = {
        "status": "ok",
        "connection": "RFC",
        "function": functions,
        "idoc": number,
        "direction": _DIRECTIONS.get(control.get("DIRECT")),
        "created": sap_datetime(control.get("CREDAT"), control.get("CRETIM")),
        "updated": sap_datetime(control.get("UPDDAT"), control.get("UPDTIM")),
        "control": compact(control),
        "status_records": status_records,
    }
    if include_segments:
        segments = [
            without_blanks(
                {
                    "number": row.get("SEGNUM"),
                    "segment": row.get("SEGNAM"),
                    "parent": row.get("PSGNUM"),
                    "level": row.get("HLEVEL"),
                    "data": (row.get("SDATA") or "").rstrip(),
                }
            )
            for row in segment_rows
        ]
        result["segments"], result["segments_paging"] = page(segments, clamp(max_segments, 1, 2000))
    return json_safe(result)


@mcp.tool(annotations=READ_ONLY)
async def list_qrfc_queues(
    direction: str = "inbound",
    queue_name: str = "*",
    destination: str = "*",
    errors_only: bool = False,
    max_results: int = 100,
) -> dict[str, Any]:
    """List qRFC queues of the current client: inbound (SMQ2), outbound (SMQ1) or both.

    Uses TRFC_QIN_OVERVIEW / TRFC_QOUT_OVERVIEW. queue_name and destination accept *
    wildcards. errors_only keeps SYSFAIL, CPICERR, STOP and similar states. Queues in
    error come first, then the deepest queues. Times are SAP server local time.
    """
    direction = direction.strip().lower() or "inbound"
    if direction not in {"inbound", "outbound", "both"}:
        return validation_error("TRFC_QIN_OVERVIEW", "direction must be inbound, outbound or both.")
    functions = {
        "inbound": ["TRFC_QIN_OVERVIEW"],
        "outbound": ["TRFC_QOUT_OVERVIEW"],
        "both": ["TRFC_QIN_OVERVIEW", "TRFC_QOUT_OVERVIEW"],
    }[direction]
    if not sap_rfc.is_connected:
        return connection_unavailable(functions)
    queue_pattern = queue_name.strip().upper() or "*"
    destination_pattern = destination.strip() or "*"
    if len(queue_pattern) > 24 or len(destination_pattern) > 32:
        return validation_error(functions, "queue_name allows 24 characters, destination 32 characters.")

    queues = []
    for function in functions:
        params: dict[str, Any] = {"QNAME": queue_pattern}
        if function == "TRFC_QOUT_OVERVIEW":
            params["DEST"] = destination_pattern
        try:
            response = call_rfc(function, **params)
        except Exception as error:
            return rfc_error_result(error, function=functions)
        first_luws = {}
        for row in response.get("QTABLE") or []:
            first_luws.setdefault((row.get("QNAME"), row.get("DEST")), row)
        for row in response.get("QVIEW") or []:
            if not wildcard_match(row.get("DEST"), destination_pattern):
                continue
            state = (row.get("QSTATE") or "").strip()
            if errors_only and state not in QUEUE_ERROR_STATES:
                continue
            first = first_luws.get((row.get("QNAME"), row.get("DEST"))) or {}
            queues.append(
                without_blanks(
                    {
                        "direction": "inbound" if function == "TRFC_QIN_OVERVIEW" else "outbound",
                        "queue": row.get("QNAME"),
                        "destination": row.get("DEST"),
                        "state": state,
                        "entries": row.get("QDEEP"),
                        "first_entry": sap_datetime(row.get("FDATE"), row.get("FTIME")),
                        "last_entry": sap_datetime(row.get("LDATE"), row.get("LTIME")),
                        "error_message": row.get("ERRMESS"),
                        "first_function": first.get("QRFCFNAM"),
                        "first_user": first.get("QRFCUSER"),
                        "retries": int(first["RETRYNR"]) if str(first.get("RETRYNR") or "").isdigit() else None,
                    }
                )
            )
    queues.sort(key=lambda queue: (queue.get("state") not in QUEUE_ERROR_STATES, -(queue.get("entries") or 0)))
    rows, paging = page(queues, clamp(max_results, 1, 1000))
    return json_safe(
        {
            "status": "ok",
            "connection": "RFC",
            "function": functions,
            "by_state": dict(Counter(queue.get("state") for queue in queues).most_common()),
            "queues_in_error": sum(queue.get("state") in QUEUE_ERROR_STATES for queue in queues),
            "total_entries": sum(queue.get("entries") or 0 for queue in queues),
            **paging,
            "queues": rows,
        }
    )


@mcp.tool(annotations=READ_ONLY)
async def list_trfc_errors(
    date_from: str = "",
    time_from: str = "",
    date_to: str = "",
    time_to: str = "",
    state: str = "",
    destination: str = "*",
    max_results: int = 100,
) -> dict[str, Any]:
    """List tRFC LUWs of the current client still waiting in SM58 with /SDF/GPC_GET_TRFC_ERRORS.

    state filters on the LUW status such as SYSFAIL, CPICERR or RECORDED; destination
    accepts * wildcards. The window is SAP server local time, defaults to today and may
    cover at most 31 days. Newest LUWs first.
    """
    functions = ["RFC_SYSTEM_INFO", "/SDF/GPC_GET_TRFC_ERRORS"]
    if not sap_rfc.is_connected:
        return connection_unavailable(functions)
    state = state.strip().upper()
    destination_pattern = destination.strip() or "*"
    if len(state) > 8:
        return validation_error(functions, "state may have at most 8 characters.")
    try:
        start, end, offset = resolve_window(date_from, time_from, date_to, time_to, max_days=31)
    except ValueError as error:
        return validation_error(functions, str(error))
    except Exception as error:
        return rfc_error_result(error, function=functions)

    params: dict[str, Any] = {
        "IV_TIMESTAMP_FROM": _utc_stamp(start, offset),
        "IV_TIMESTAMP_TO": _utc_stamp(end, offset),
    }
    if state:
        params["IV_ARFCSTATE"] = state
    try:
        response = call_rfc("/SDF/GPC_GET_TRFC_ERRORS", **params)
    except Exception as error:
        return rfc_error_result(error, function=functions)
    if (response.get("EV_ERROR_MESSAGE") or "").strip():
        return json_safe(
            {
                "status": "error",
                "connection": "RFC",
                "function": functions,
                "error_type": "TRFCReadError",
                "error_message": response["EV_ERROR_MESSAGE"].strip(),
            }
        )

    luws = [
        without_blanks(
            {
                "timestamp": sap_datetime(row.get("ARFCDATUM"), row.get("ARFCUZEIT")),
                "destination": row.get("ARFCDEST"),
                "state": row.get("ARFCSTATE"),
                "function": row.get("ARFCFNAM"),
                "user": row.get("ARFCUSER"),
                "transaction": row.get("ARFCTCODE"),
                "host": row.get("ARFCRHOST"),
                "message": row.get("ARFCMSG"),
                "retries": int(row["ARFCRETRYS"]) if str(row.get("ARFCRETRYS") or "").isdigit() else None,
                "tid": "".join(
                    row.get(field) or "" for field in ("ARFCIPID", "ARFCPID", "ARFCTIME", "ARFCTIDCNT")
                ),
            }
        )
        for row in response.get("ET_ARFCSSTATE") or []
        if wildcard_match(row.get("ARFCDEST"), destination_pattern)
    ]
    luws.sort(key=lambda luw: luw.get("timestamp") or "", reverse=True)
    rows, paging = page(luws, clamp(max_results, 1, 1000))
    return json_safe(
        {
            "status": "ok",
            "connection": "RFC",
            "function": functions,
            "window": window_info(start, end, offset),
            "by_state": dict(Counter(luw.get("state") for luw in luws).most_common()),
            "by_destination": dict(Counter(luw.get("destination") for luw in luws).most_common(10)),
            **paging,
            "luws": rows,
        }
    )


@mcp.tool(annotations=READ_ONLY)
async def get_bgrfc_overview() -> dict[str, Any]:
    """Summarize bgRFC units per destination (SBGRFCMON) with BGRFC_GET_OVERVIEW_INFORMATION.

    Returns inbound and outbound destinations with their unit counts, including units in
    SYSFAIL (UNIT_T_CNT_SYSFAIL / UNIT_Q_CNT_SYSFAIL).
    """
    function = "BGRFC_GET_OVERVIEW_INFORMATION"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    result: dict[str, Any] = {"status": "ok", "connection": "RFC", "function": function}
    failed = 0
    for scenario, label in (("I", "inbound"), ("O", "outbound")):
        try:
            rows = call_rfc(function, SCENARIO=scenario).get("RESULT_TAB") or []
        except Exception as error:
            return rfc_error_result(error, function=function)
        failed += sum((row.get("UNIT_T_CNT_SYSFAIL") or 0) + (row.get("UNIT_Q_CNT_SYSFAIL") or 0) for row in rows)
        result[label] = compact(rows)
    result["units_in_sysfail"] = failed
    return json_safe(result)
