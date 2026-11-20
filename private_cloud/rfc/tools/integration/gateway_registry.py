"""OData service registration check against the SAP Gateway hub (/IWFND/MAINT_SERVICE)."""

import re
from typing import Any

from core.app import (
    READ_ONLY,
    call_rfc,
    connection_unavailable,
    json_safe,
    mcp,
    rfc_error_result,
    sap_rfc,
    validation_error,
)


# Standard S/4HANA OData V2 APIs for the domains this server covers.
DEFAULT_SERVICES = (
    "API_PRODUCT_SRV",
    "API_BUSINESS_PARTNER",
    "API_PURCHASEREQ_PROCESS_SRV",
    "API_MATERIAL_DOCUMENT_SRV",
    "API_MATERIAL_STOCK_SRV",
    "API_PURCHASEORDER_PROCESS_SRV",
    "API_PRODUCTION_ORDER_2_SRV",
)
_SERVICE_NAME = re.compile(r"[A-Z0-9_/]{1,35}")


@mcp.tool(annotations=READ_ONLY)
async def check_odata_services(service_names: list[str] | None = None, version: str = "0001") -> dict[str, Any]:
    """Check whether OData V2 services are registered in the SAP Gateway (/IWFND/MAINT_SERVICE).

    Reads the Gateway registry over RFC (/IWFND/FM_DOES_SERVICE_EXIST and
    /IWFND/FM_GET_ALL_SRV_AND_MDL), so no HTTPS access is needed. Defaults to the
    standard APIs for product, business partner, purchase requisition, material
    document, stock, purchase order and production order. registered_as lists the
    technical names, e.g. ZAPI_BUSINESS_PARTNER_0001 when activated with a Z prefix.
    Registration does not prove a service is callable: the system alias and S_SERVICE
    authorization are checked at call time. Needs authorization for /IWFND/MAINT_SERVICE.
    """
    functions = ["/IWFND/FM_GET_ALL_SRV_AND_MDL", "/IWFND/FM_DOES_SERVICE_EXIST"]
    if not sap_rfc.is_connected:
        return connection_unavailable(functions)
    names = list(dict.fromkeys(name.strip().upper() for name in (service_names or DEFAULT_SERVICES) if name.strip()))
    invalid = [name for name in names if not _SERVICE_NAME.fullmatch(name)]
    if not names or invalid or len(names) > 50:
        return validation_error(
            functions, "service_names needs 1 to 50 names of up to 35 characters (A-Z, 0-9, _ and /)."
        )
    version = version.strip()
    if not version.isdigit() or len(version) > 4:
        return validation_error(functions, "version must contain 1 to 4 digits.")
    version = version.zfill(4)

    try:
        registry = {
            row.get("SRV_IDENTIFIER", "").strip()
            for row in call_rfc("/IWFND/FM_GET_ALL_SRV_AND_MDL").get("ET_SRV_MDL_ASSIGNMENTS") or []
        }
        services = []
        for name in names:
            response = call_rfc(
                "/IWFND/FM_DOES_SERVICE_EXIST",
                IV_TECH_SERVICE_NAME=name,
                IV_TECH_SERVICE_VERSION=version,
            )
            identifier = f"{name}_{version}"
            registered_as = sorted(registry & {identifier, f"Z{identifier}", f"Y{identifier}"})
            backend_found = response.get("EV_SERVICE_EXIST") == "X"
            services.append(
                {
                    "service": name,
                    "version": version,
                    "registered": backend_found or bool(registered_as),
                    "registered_as": registered_as,
                    "backend_service_found": backend_found,
                }
            )
    except Exception as error:
        return rfc_error_result(error, function=functions)

    system_info = sap_rfc.system_info
    return json_safe(
        {
            "status": "ok",
            "connection": "RFC",
            "function": functions,
            "system": system_info["System ID"],
            "client": system_info["Client"],
            "registered_service_count": len(registry),
            "services": services,
        }
    )
