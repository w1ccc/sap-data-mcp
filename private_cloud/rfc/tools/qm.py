"""Standard QM BAPI reads through the existing cached RFC provider."""
from typing import Any
from core.app import READ_ONLY, mcp, read_bapi, sap_key, sap_date, validation_error


@mcp.tool(annotations=READ_ONLY)
async def search_inspection_lots(plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Search standard inspection lots in one plant; returned list pages locally."""
    function = 'BAPI_INSPLOT_GETLIST'
    try:
        params = {"PLANT": sap_key(plant, "plant", 4)}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_inspection_lot(inspection_lot: str, operation: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read a lot and operation list. Supply operation from the list to include requirements, samples and existing results inside this parent detail; never records results or usage decisions."""
    function = 'BAPI_INSPLOT_GETDETAIL'
    try:
        params = {"NUMBER": sap_key(inspection_lot, "inspection_lot", 12, numeric_length=12)}
        if operation.strip(): operation = sap_key(operation, "operation", 4, numeric_length=4)
    except ValueError as error:
        return validation_error(function, str(error))
    result = read_bapi(function, params, max_results, offset)
    if result["status"] in {"ok", "partial"}:
        result["operations"] = read_bapi("BAPI_INSPLOT_GETOPERATIONS", params, max_results, offset)
        if result["operations"]["status"] == "error": result["status"] = "partial"
        if operation:
            result["operation_details"] = read_bapi("BAPI_INSPOPER_GETDETAIL", {
                "INSPLOT": params["NUMBER"], "INSPOPER": operation, "READ_INSPPOINTS": "X",
                "READ_CHAR_REQUIREMENTS": "X", "READ_CHAR_RESULTS": "X", "READ_SAMPLE_RESULTS": "X",
                "READ_SINGLE_RESULTS": "X", "READ_CHARS_WITH_CLASSES": "X", "READ_CHARS_WITHOUT_RECORDING": "X",
            }, max_results, offset)
            if result["operation_details"]["status"] != "ok": result["status"] = "partial"
    return result


@mcp.tool(annotations=READ_ONLY)
async def get_quality_notification(quality_notification: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read standard quality-notification header, items, tasks, ACTIVITIES, causes, partners and long texts; native table keys/statuses are retained."""
    function = 'BAPI_QUALNOT_GETDETAIL'
    try:
        params = {"NUMBER": sap_key(quality_notification, "quality_notification", 12, numeric_length=12)}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)

