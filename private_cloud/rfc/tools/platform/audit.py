"""Read access to the local tool call audit log."""

from typing import Any

from core.app import LOCAL_READ_ONLY, audit_log, clamp, mcp


@mcp.tool(annotations=LOCAL_READ_ONLY)
def get_tool_call_log(limit: int = 50, tool: str = "", status: str = "") -> dict[str, Any]:
    """Return recent entries of the local tool call audit log, newest first (last 31 days).

    Every MCP tool call is logged with time, session, MCP client, OS user, SAP logon
    user, SAP system/client, tool, arguments, status, error, RFC functions called and
    duration. tool and status (ok, error, not_found, partial, exception) filter the
    entries; limit: 1-500. Entries are returned as written: the SAP logon user is shown,
    the password never reaches the log.
    """
    entries = audit_log.read_recent(clamp(limit, 1, 500), tool.strip(), status.strip())
    return {
        "status": "ok",
        "log_directory": str(audit_log.directory),
        "returned": len(entries),
        "entries": entries,
    }
