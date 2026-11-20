"""Production order tools (BAPI_PRODORD_GET_LIST)."""

from typing import Any

from core.app import (
    READ_ONLY, call_rfc, clamp, connection_unavailable, has_error, json_safe,
    mcp, org_unit, page, return_messages, rfc_error_result, sap_key, sap_rfc,
    validation_error, without_blanks,
    read_bapi,
)


@mcp.tool(annotations=READ_ONLY)
async def find_production_order() -> dict[str, Any]:
    """Return one existing production order through BAPI_PRODORD_GET_LIST."""
    function = "BAPI_PRODORD_GET_LIST"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)

    try:
        response = call_rfc(
            function,
            ORDER_NUMBER_RANGE=[
                {
                    "SIGN": "I",
                    "OPTION": "BT",
                    "LOW": "000000000001",
                    "HIGH": "999999999999",
                }
            ],
        )
    except Exception as error:
        return rfc_error_result(error, function=function)

    return_message = response.get("RETURN") or {}
    if return_message.get("TYPE") in {"A", "E", "X"}:
        return {
            "status": "error",
            "connection": "RFC",
            "function": function,
            "return_message": {
                "type": return_message.get("TYPE"),
                "id": return_message.get("ID"),
                "number": return_message.get("NUMBER"),
                "message": return_message.get("MESSAGE"),
            },
        }

    orders = [
        order
        for order in (response.get("ORDER_HEADER") or [])
        if order.get("ORDER_NUMBER") and not order.get("DELETION_FLAG")
    ]
    if not orders:
        return {
            "status": "not_found",
            "connection": "RFC",
            "function": function,
            "message": "No non-deleted production order was returned.",
        }

    order = max(
        orders,
        key=lambda item: int(item["ORDER_NUMBER"])
        if str(item["ORDER_NUMBER"]).isdigit()
        else -1,
    )
    result = {
        "status": "ok",
        "connection": "RFC",
        "function": function,
        "production_order": {
            "order_number": order.get("ORDER_NUMBER"),
            "order_type": order.get("ORDER_TYPE"),
            "system_status": order.get("SYSTEM_STATUS"),
            "material": order.get("MATERIAL_LONG")
            or order.get("MATERIAL_EXTERNAL")
            or order.get("MATERIAL"),
            "material_text": order.get("MATERIAL_TEXT"),
            "production_plant": order.get("PRODUCTION_PLANT"),
            "planning_plant": order.get("PLAN_PLANT"),
            "target_quantity": order.get("TARGET_QUANTITY"),
            "confirmed_quantity": order.get("CONFIRMED_QUANTITY"),
            "unit": order.get("UNIT_ISO") or order.get("UNIT"),
            "basic_start_date": order.get("START_DATE"),
            "basic_finish_date": order.get("FINISH_DATE"),
            "scheduled_start_date": order.get("PRODUCTION_START_DATE"),
            "scheduled_finish_date": order.get("PRODUCTION_FINISH_DATE"),
            "actual_start_date": order.get("ACTUAL_START_DATE"),
            "actual_finish_date": order.get("ACTUAL_FINISH_DATE"),
            "entered_by": order.get("ENTERED_BY"),
            "entered_date": order.get("ENTER_DATE"),
            "sales_order": order.get("SALES_ORDER"),
            "sales_order_item": order.get("SALES_ORDER_ITEM"),
            "batch": order.get("BATCH"),
        },
    }
    return json_safe(result)


@mcp.tool(annotations=READ_ONLY)
async def search_production_orders(
    plant: str,
    material: str = "",
    order_type: str = "",
    mrp_controller: str = "",
    system_status: str = "",
    include_deleted: bool = False,
    max_results: int = 100,
) -> dict[str, Any]:
    """Search production order headers with BAPI_PRODORD_GET_LIST.

    plant is required and filters SAP's production plant. material is an exact
    classic material number (at most 18 characters); numeric values are padded.
    order_type and mrp_controller also filter SAP's query. system_status filters
    the returned headers locally: space-separated status codes must all match
    (for example REL PCNF). max_results limits returned headers locally (1-500).
    Components, operations and confirmations are not included.
    """
    function = "BAPI_PRODORD_GET_LIST"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        plant = org_unit(plant, "plant", 4)
        if not plant:
            raise ValueError("plant is required.")
        material = sap_key(material, "material", 18, numeric_length=18) if material.strip() else ""
        order_type = org_unit(order_type, "order_type", 4)
        mrp_controller = org_unit(mrp_controller, "mrp_controller", 3)
        statuses = set(system_status.upper().split())
        if any(not code.isalnum() or len(code) > 4 for code in statuses):
            raise ValueError("system_status must contain space-separated SAP status codes, such as REL PCNF.")
    except ValueError as error:
        return validation_error(function, str(error))

    params = {}
    for parameter, value in (
        ("PRODPLANT_RANGE", plant), ("MATERIAL_RANGE", material),
        ("ORDER_TYPE_RANGE", order_type), ("MRP_CNTRL_RANGE", mrp_controller),
    ):
        if value:
            params[parameter] = [{"SIGN": "I", "OPTION": "EQ", "LOW": value}]
    try:
        response = call_rfc(function, **params)
    except Exception as error:
        return rfc_error_result(error, function=function)

    messages = return_messages(response.get("RETURN"))
    orders = [
        without_blanks(row) for row in response.get("ORDER_HEADER") or []
        if row.get("ORDER_NUMBER")
        and (include_deleted or not str(row.get("DELETION_FLAG") or "").strip())
        and statuses.issubset(str(row.get("SYSTEM_STATUS") or "").upper().split())
    ]
    orders.sort(key=lambda row: (str(row.get("ENTER_DATE") or ""), row["ORDER_NUMBER"]), reverse=True)
    rows, paging = page(orders, clamp(max_results, 1, 500))
    return json_safe({
        "status": "error" if has_error(messages) else "ok" if rows else "not_found",
        "connection": "RFC",
        "function": function,
        **paging,
        "orders": rows,
        "return_messages": messages,
    })


@mcp.tool(annotations=READ_ONLY)
async def get_production_order(production_order: str) -> dict[str, Any]:
    """Read a production order's original header plus standard order details.

    Numeric order numbers may omit leading zeros. Returns SAP header fields,
    The header keeps its existing shape. details contains BAPI_PRODORD_GET_DETAIL
    header, positions, operations, sequences and components, including zero quantities.
    """
    function = "BAPI_PRODORD_GET_LIST"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        number = sap_key(production_order, "production_order", 12, numeric_length=12)
    except ValueError as error:
        return validation_error(function, str(error))
    try:
        response = call_rfc(function, ORDER_NUMBER_RANGE=[{"SIGN": "I", "OPTION": "EQ", "LOW": number}])
    except Exception as error:
        return rfc_error_result(error, function=function, production_order=number)

    messages = return_messages(response.get("RETURN"))
    header = next((row for row in response.get("ORDER_HEADER") or [] if row.get("ORDER_NUMBER") == number), {})
    result = json_safe({
        "status": "error" if has_error(messages) else "ok" if header else "not_found",
        "connection": "RFC",
        "function": function,
        "production_order": number,
        "header": without_blanks(header),
        "return_messages": messages,
    })
    if header and not has_error(messages):
        result["details"] = read_bapi("BAPI_PRODORD_GET_DETAIL", {"NUMBER": number, "ORDER_OBJECTS": {
            "HEADER": "X", "POSITIONS": "X", "SEQUENCES": "X", "OPERATIONS": "X", "COMPONENTS": "X"}})
        if result["details"]["status"] != "ok":
            result["status"] = "partial"
    return result


@mcp.tool(annotations=READ_ONLY)
async def get_process_order(process_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read a process order's header, positions, phases and components using the standard read BAPI."""
    function = "BAPI_PROCORD_GET_DETAIL"
    try:
        number = sap_key(process_order, "process_order", 12, numeric_length=12)
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, {"NUMBER": number, "ORDER_OBJECTS": {"HEADER": "X", "POSITIONS": "X", "PHASES": "X", "COMPONENTS": "X"}}, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_planned_order(planned_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read a planned order by number; preserve the standard BAPI header/component/capacity fields."""
    function = "BAPI_PLANNEDORDER_GET_DETAIL"
    try:
        number = sap_key(planned_order, "planned_order", 10, numeric_length=10)
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, {"PLANNEDORDER": number}, max_results, offset)


def _confirmations(function, order_number, max_results, offset):
    try:
        number = sap_key(order_number, "order", 12, numeric_length=12)
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, {"ORDER_RANGE": [{"SIGN": "I", "OPTION": "EQ", "LOW": number}]}, max_results, offset)


def _confirmation(function, number, counter, max_results, offset):
    try:
        number = sap_key(number, "confirmation", 10, numeric_length=10)
        counter = sap_key(counter, "counter", 8, numeric_length=8)
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, {"CONFIRMATION": number, "CONFIRMATIONCOUNTER": counter}, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def search_production_order_confirmations(production_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """List confirmation keys for one production order. No confirmations are entered or canceled."""
    return _confirmations("BAPI_PRODORDCONF_GETLIST", production_order, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_production_order_confirmation(confirmation: str, counter: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read a production confirmation by number AND counter, including successful and failed goods-movement references."""
    return _confirmation("BAPI_PRODORDCONF_GETDETAIL", confirmation, counter, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def search_process_order_confirmations(process_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """List confirmation keys for one process order."""
    return _confirmations("BAPI_PROCORDCONF_GETLIST", process_order, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_process_order_confirmation(confirmation: str, counter: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read a process-order confirmation using its number and counter."""
    return _confirmation("BAPI_PROCORDCONF_GETDETAIL", confirmation, counter, max_results, offset)
