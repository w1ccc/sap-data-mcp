"""Classic WM reads. EWM APIs are separately named and implemented."""
from typing import Any
from core.app import READ_ONLY, mcp, read_bapi, sap_key, material_number, validation_error


@mcp.tool(annotations=READ_ONLY)
async def search_wm_stock(warehouse: str, material: str, plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Search classic WM stock keys by warehouse, classic material (up to 18 characters) and plant. Use get_wm_quant for quantities."""
    function = "BAPI_WHSE_STOCK_GET_LIST"
    try:
        number = material_number(material)
        if len(number) > 18:
            raise ValueError("This classic WM BAPI accepts material numbers up to 18 characters; use the API route for long products.")
        params = {"WAREHOUSENUMBER": sap_key(warehouse, "warehouse", 3), "MATERIAL": number,
                  "PLANT": sap_key(plant, "plant", 4), "MAXROWS": offset + max_results + 1}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_wm_quant(warehouse: str, quant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read one classic WM quant by warehouse AND quant number, preserving native stock category, quantity and unit."""
    function = "BAPI_WHSE_STOCK_GET_DETAIL"
    try:
        params = {"WHSENUMBER": sap_key(warehouse, "warehouse", 3), "QUANT": sap_key(quant, "quant", 10, numeric_length=10)}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def search_wm_transfer_orders(warehouse: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Search classic WM transfer-order keys within a warehouse; never creates or confirms transfer orders."""
    function = "BAPI_WHSE_TO_GET_LIST"
    try:
        params = {"WAREHOUSENUMBER": sap_key(warehouse, "warehouse", 3), "MAXROWS": offset + max_results + 1}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_wm_transfer_order(warehouse: str, transfer_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read classic WM transfer-order header and items by warehouse AND order, including existing delivery references."""
    function = "BAPI_WHSE_TO_GET_DETAIL"
    try:
        params = {"WHSENUMBER": sap_key(warehouse, "warehouse", 3), "TRANSFERORDERNO": sap_key(transfer_order, "transfer_order", 10, numeric_length=10)}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)
