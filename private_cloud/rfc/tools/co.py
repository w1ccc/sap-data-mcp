"""Standard CO BAPI reads through the existing cached RFC provider."""
from typing import Any
from core.app import READ_ONLY, mcp, read_bapi, sap_key, sap_date, validation_error


@mcp.tool(annotations=READ_ONLY)
async def search_controlling_areas(max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """List controlling areas with native identifiers; page the returned table locally."""
    return read_bapi("BAPI_CONTROLLINGAREA_GETLIST", {}, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_controlling_area(controlling_area: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read controlling-area master data, including the SAP currency and fiscal-year variant."""
    function = "BAPI_CONTROLLINGAREA_GETDETAIL"
    try:
        params = {"CONTROLLINGAREAID": sap_key(controlling_area, "controlling_area", 4)}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_cost_center(controlling_area: str, cost_center: str, key_date: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read a cost center for an explicit key date, retaining SAP validity and standard-hierarchy assignment."""
    function = 'BAPI_COSTCENTER_GETDETAIL1'
    try:
        params = {"CONTROLLINGAREA": sap_key(controlling_area, "controlling_area", 4), "COSTCENTER": sap_key(cost_center, "cost_center", 10, numeric_length=10), "KEYDATE": sap_date(key_date, "key_date")}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def search_cost_centers(controlling_area: str, date_from: str, date_to: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Search cost-center records in a controlling area and explicit validity range."""
    function = 'BAPI_COSTCENTER_GETLIST1'
    try:
        start, end = sap_date(date_from, "date_from"), sap_date(date_to, "date_to")
        if start > end: raise ValueError("date_from must not follow date_to.")
        params = {"CONTROLLINGAREA": sap_key(controlling_area, "controlling_area", 4), "DATE_FROM": start, "DATE_TO": end}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_internal_order(internal_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read an internal order with native master data, system/user status and existing business-transaction information."""
    function = 'BAPI_INTERNALORDER_GETDETAIL'
    try:
        params = {"ORDERID": sap_key(internal_order, "internal_order", 12, numeric_length=12)}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def search_internal_orders(controlling_area: str, order_type: str = "", responsible_cost_center: str = "",
                                  max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Search internal orders within a controlling area, optionally by type and responsible cost center. The standard BAPI returns the matching list; pagination is local."""
    function = "BAPI_INTERNALORDER_GETLIST"
    try:
        params = {"CONTROLLING_AREA": sap_key(controlling_area, "controlling_area", 4)}
        if order_type:
            params["ORDER_TYPE"] = sap_key(order_type, "order_type", 4)
        if responsible_cost_center:
            params["RESP_COST_CENTER"] = sap_key(responsible_cost_center, "responsible_cost_center", 10, numeric_length=10)
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_internal_order_group(controlling_area: str, group_name: str, max_results: int = 100,
                                    offset: int = 0) -> dict[str, Any]:
    """Read an internal-order group with native hierarchy nodes and order intervals, paged independently. This is the classic SET hierarchy, not a global hierarchy snapshot."""
    function = "BAPI_INTERNALORDRGRP_GETDETAIL"
    try:
        params = {"CONTROLLINGAREA": sap_key(controlling_area, "controlling_area", 4),
                  "GROUPNAME": sap_key(group_name, "group_name", 15)}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def search_profit_centers(controlling_area: str, key_date: str, max_results: int = 100,
                                 offset: int = 0) -> dict[str, Any]:
    """List profit centers valid on a key date within a controlling area, without restricting the responsible person or user. Native validity dates and keys are retained."""
    function = "BAPI_PROFITCENTER_GETLIST"
    try:
        params = {"CONTROLLINGAREA": sap_key(controlling_area, "controlling_area", 4),
                  "DATE": sap_date(key_date, "key_date"), "PERSONINCHARGE": "%", "IN_CHARGE_USER": "%"}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def search_cost_center_groups(controlling_area: str, max_results: int = 100,
                                     offset: int = 0) -> dict[str, Any]:
    """List classic cost-center SET groups in one controlling area. Use get_cost_center_group to read hierarchy nodes and value intervals."""
    function = "BAPI_COSTCENTERGROUP_GETLIST"
    try:
        params = {"CONTROLLINGAREAMASK": sap_key(controlling_area, "controlling_area", 4), "GROUPNAMEMASK": "*"}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_cost_center_group(controlling_area: str, group_name: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read a standard/alternative cost center group with independently paged hierarchy nodes and value intervals; retains native hierarchy level information."""
    function = 'BAPI_COSTCENTERGROUP_GETDETAIL'
    try:
        params = {"CONTROLLINGAREA": sap_key(controlling_area, "controlling_area", 4), "GROUPNAME": sap_key(group_name, "group_name", 15)}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_profit_center_group(controlling_area: str, group_name: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read a standard/alternative profit center group with independently paged hierarchy nodes and value intervals; retains native hierarchy level information."""
    function = 'BAPI_PROFITCENTERGRP_GETDETAIL'
    try:
        params = {"CONTROLLINGAREA": sap_key(controlling_area, "controlling_area", 4), "GROUPNAME": sap_key(group_name, "group_name", 15)}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_activity_type_group(controlling_area: str, group_name: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read a standard/alternative activity type group with independently paged hierarchy nodes and value intervals; retains native hierarchy level information."""
    function = 'BAPI_ACTIVITYTYPEGRP_GETDETAIL'
    try:
        params = {"CONTROLLINGAREA": sap_key(controlling_area, "controlling_area", 4), "GROUPNAME": sap_key(group_name, "group_name", 15)}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)

