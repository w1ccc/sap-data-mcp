"""Local MCP server health and runtime information."""

from core.app import LOCAL_READ_ONLY, PROJECT_NAME, PROJECT_VERSION, mcp, sap_rfc


@mcp.tool(annotations=LOCAL_READ_ONLY)
def health_check() -> dict[str, str]:
    """Return the current MCP server health status."""
    return {
        "status": "ok",
        "server": PROJECT_NAME,
    }


@mcp.tool(annotations=LOCAL_READ_ONLY)
def get_server_info() -> dict[str, str]:
    """Return basic project information and the current SAP connection status."""
    return {
        "project_name": PROJECT_NAME,
        "version": PROJECT_VERSION,
        "sap_status": "SAP 已连接" if sap_rfc.is_connected else "SAP 尚未连接",
    }
