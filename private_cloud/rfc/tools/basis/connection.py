"""SAP connection tools: the single RFC login, RFC_SYSTEM_INFO and the legacy HTTPS check."""

import os
import ssl
from pathlib import Path
from typing import Any

import httpx

from core.app import (
    PROJECT_DIR,
    READ_ONLY,
    call_rfc,
    mcp,
    redact_sensitive_text,
    rfc_error_result,
    sap_rfc,
)


_rfc_login_attempted = False
_rfc_login_result: dict[str, Any] | None = None
_rfc_system_info_result: dict[str, Any] | None = None


@mcp.tool(annotations=READ_ONLY)
async def test_sap_rfc_connection() -> dict[str, Any]:
    """Attempt one RFC login and cache the connection for read-only system info."""
    global _rfc_login_attempted, _rfc_login_result

    if _rfc_login_attempted:
        return _rfc_login_result or {
            "status": "error",
            "connection": "RFC",
            "error_type": "RFCLoginStateError",
            "error_message": "The single RFC login attempt has already been used.",
        }

    _rfc_login_attempted = True
    try:
        sap_rfc.connect()
    except Exception as error:
        _rfc_login_result = rfc_error_result(error)
        return _rfc_login_result

    system_info = sap_rfc.system_info
    _rfc_login_result = {
        "status": "ok",
        "connection": "RFC",
        "system": system_info["System ID"],
        "client": system_info["Client"],
    }
    return _rfc_login_result


@mcp.tool(annotations=READ_ONLY)
async def get_sap_system_info() -> dict[str, Any]:
    """Call RFC_SYSTEM_INFO once through the cached RFC connection."""
    global _rfc_system_info_result

    if _rfc_system_info_result is not None:
        return _rfc_system_info_result
    if not sap_rfc.is_connected:
        return {
            "status": "error",
            "connection": "RFC",
            "error_type": "RFCConnectionUnavailable",
            "error_message": "RFC login is not established; no login retry was attempted.",
        }

    try:
        response = call_rfc("RFC_SYSTEM_INFO")
    except Exception as error:
        _rfc_system_info_result = rfc_error_result(error)
        return _rfc_system_info_result

    info = response.get("RFCSI_EXPORT", {})
    system_info = sap_rfc.system_info
    _rfc_system_info_result = {
        "status": "ok",
        "connection": "RFC",
        "system": info.get("RFCSYSID") or system_info["System ID"],
        "client": system_info["Client"],
        "application_server": info.get("RFCHOST"),
        "sap_release": info.get("RFCSAPRL"),
        "kernel_release": info.get("RFCKERNRL"),
        "operating_system": info.get("RFCOPSYS"),
        "database_system": info.get("RFCDBSYS"),
    }
    return _rfc_system_info_result


def _exception_chain(error: BaseException) -> list[BaseException]:
    """Collect an exception and its chained causes without exposing request data."""
    chain: list[BaseException] = []
    current: BaseException | None = error
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__

    return chain


@mcp.tool(annotations=READ_ONLY)
def test_sap_connection() -> dict[str, str | int | bool | None]:
    """Test strict HTTPS connectivity and Basic authentication against SAP."""
    base_url = os.getenv("SAP_BASE_URL", "").strip().rstrip("/")
    sap_client = os.getenv("SAP_CLIENT", "").strip()
    username = os.getenv("SAP_USERNAME", "").strip()
    password = os.getenv("SAP_PASSWORD", "")
    language = os.getenv("SAP_LANGUAGE", "EN").strip() or "EN"
    verify_ssl = os.getenv("SAP_VERIFY_SSL", "true").strip().lower()
    ca_bundle = os.getenv("SAP_CA_BUNDLE", "").strip()
    endpoint = "/sap/bc/ping"

    missing = [
        name
        for name, value in (
            ("SAP_BASE_URL", base_url),
            ("SAP_CLIENT", sap_client),
            ("SAP_USERNAME", username),
            ("SAP_PASSWORD", password),
        )
        if not value
    ]
    if missing:
        return {
            "endpoint": endpoint,
            "http_status": None,
            "sap_connection_success": False,
            "authentication_success": False,
            "certificate_verified": False,
            "error_type": "ConfigurationError",
            "error_message": f"Missing configuration: {', '.join(missing)}",
        }

    if verify_ssl != "true":
        return {
            "endpoint": endpoint,
            "http_status": None,
            "sap_connection_success": False,
            "authentication_success": False,
            "certificate_verified": False,
            "error_type": "ConfigurationError",
            "error_message": "SAP_VERIFY_SSL must remain true.",
        }

    ssl_context = ssl.create_default_context()
    if ca_bundle:
        ca_path = Path(ca_bundle)
        if not ca_path.is_absolute():
            ca_path = PROJECT_DIR / ca_path
        try:
            ssl_context.load_verify_locations(cafile=ca_path)
        except (OSError, ssl.SSLError) as error:
            return {
                "endpoint": endpoint,
                "http_status": None,
                "sap_connection_success": False,
                "authentication_success": False,
                "certificate_verified": False,
                "error_type": f"{type(error).__module__}.{type(error).__name__}",
                "error_message": redact_sensitive_text(str(error)),
            }

    try:
        response = httpx.get(
            f"{base_url}{endpoint}",
            params={"sap-client": sap_client, "sap-language": language},
            auth=httpx.BasicAuth(username, password),
            headers={"Accept": "text/plain"},
            follow_redirects=False,
            timeout=10.0,
            verify=ssl_context,
            # SAP is reached directly on the intranet. Ignore proxies from environment
            # variables and the Windows system settings (e.g. a corporate proxy that answers 503).
            trust_env=False,
        )
    except httpx.ConnectError as error:
        chain = _exception_chain(error)
        certificate_error = next(
            (
                item
                for item in chain
                if isinstance(item, ssl.SSLCertVerificationError)
                or "CERTIFICATE_VERIFY_FAILED" in str(item)
            ),
            None,
        )
        return {
            "endpoint": endpoint,
            "http_status": None,
            "sap_connection_success": False,
            "authentication_success": False,
            "certificate_verified": False,
            "error_type": f"{type(error).__module__}.{type(error).__name__}",
            "error_message": redact_sensitive_text(str(error)),
            "certificate_error_type": (
                f"{type(certificate_error).__module__}.{type(certificate_error).__name__}"
                if certificate_error is not None
                else None
            ),
            "certificate_error": (
                redact_sensitive_text(str(certificate_error))
                if certificate_error is not None
                else None
            ),
        }
    except httpx.HTTPError as error:
        return {
            "endpoint": endpoint,
            "http_status": None,
            "sap_connection_success": False,
            "authentication_success": False,
            "certificate_verified": False,
            "error_type": f"{type(error).__module__}.{type(error).__name__}",
            "error_message": redact_sensitive_text(str(error)),
        }

    authentication_success = 200 <= response.status_code < 300
    if response.status_code in (401, 403):
        message = "SAP returned an authentication or authorization failure."
    elif authentication_success:
        message = "SAP HTTPS connection and authentication succeeded."
    else:
        message = "SAP returned an unexpected HTTP status; authentication was not confirmed."

    return {
        "endpoint": endpoint,
        "http_status": response.status_code,
        "sap_connection_success": True,
        "authentication_success": authentication_success,
        "certificate_verified": True,
        "error_type": None,
        "error_message": message,
    }
