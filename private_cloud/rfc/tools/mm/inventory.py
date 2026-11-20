"""Inventory tools: material documents (goods receipts/issues) and stock."""

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from core.app import (
    READ_ONLY,
    call_rfc,
    clamp,
    compact,
    connection_unavailable,
    has_error,
    has_error_except,
    is_initial,
    json_safe,
    material_number,
    mcp,
    org_unit,
    page,
    pick,
    return_messages,
    rfc_error_result,
    sap_date,
    sap_key,
    sap_rfc,
    sap_server_clock,
    validation_error,
    without_blanks,
)


_HEADER_FIELDS = ("PSTNG_DATE", "DOC_DATE", "ENTRY_DATE", "ENTRY_TIME", "USERNAME", "TR_EV_TYPE", "REF_DOC_NO", "HEADER_TXT")

_ITEM_FIELDS = (
    "MAT_DOC",
    "DOC_YEAR",
    "MATDOC_ITM",
    "MOVE_TYPE",
    "MATERIAL_LONG",
    "PLANT",
    "STGE_LOC",
    "BATCH",
    "ENTRY_QNT",
    "ENTRY_UOM",
    "STCK_TYPE",
    "SPEC_STOCK",
    "VENDOR",
    "CUSTOMER",
    "PO_NUMBER",
    "PO_ITEM",
    "ORDERID",
    "RESERV_NO",
    "RES_ITEM",
    "COSTCENTER",
    "SALES_ORD",
    "S_ORD_ITEM",
    "WBS_ELEM",
    "MOVE_MAT_LONG",
    "MOVE_PLANT",
    "MOVE_STLOC",
    "MOVE_BATCH",
    "MOVE_REAS",
    "AMOUNT_LC",
    "CURRENCY",
    "ITEM_TEXT",
    "REF_DOC",
    "REF_DOC_YR",
    "REF_DOC_IT",
    "PROD_DATE",
    "EXPIRYDATE",
)

# Plant stock buckets of BAPI_MRP_STOCK_DETAIL that are always reported, zero included.
_PLANT_STOCK = {
    "unrestricted": "UNRESTRICTED_STCK",
    "quality_inspection": "QUAL_INSPECTION",
    "blocked": "BLKD_STKC",
    "restricted_use": "RESTR_USE",
    "blocked_returns": "BLKD_RETURNS",
    "gr_blocked": "BLKD_GR",
    "in_transfer": "STCK_IN_TFR",
    "in_transit": "STCK_IN_TRANSIT",
    "total": "TOTAL_STCK",
}

_STORAGE_LOCATION_STOCK = {
    "storage_location": "LGORT",
    "batch": "CHARG",
    "special_stock": "SOBKZ",
    "supplier": "LIFNR",
    "sales_order": "VBELN",
    "sales_order_item": "POSNR",
    "wbs_element": "PSPNR",
    "unrestricted": "LABST",
    "quality_inspection": "INSME",
    "blocked": "SPEME",
    "returns": "RETME",
    "consignment_unrestricted": "KLABS",
    "consignment_quality_inspection": "KINSM",
    "consignment_blocked": "KSPEM",
    "unit": "MEINS",
}

_ALWAYS_REPORTED = {"storage_location", "unrestricted", "quality_inspection", "blocked", "unit"}


def _include(values: list[str]) -> list[dict[str, str]]:
    return [{"SIGN": "I", "OPTION": "EQ", "LOW": value} for value in values]


@mcp.tool(annotations=READ_ONLY)
async def get_material_document(material_document: str, year: str) -> dict[str, Any]:
    """Read one material document (goods receipt, issue, transfer) with BAPI_GOODSMVT_GETDETAIL.

    year is the material document year (4 digits). Empty fields are omitted.
    """
    function = "BAPI_GOODSMVT_GETDETAIL"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        number = sap_key(material_document, "material_document", 10, numeric_length=10)
    except ValueError as error:
        return validation_error(function, str(error))
    year = year.strip()
    if len(year) != 4 or not year.isdigit():
        return validation_error(function, "year must have 4 digits.")

    try:
        response = call_rfc(function, MATERIALDOCUMENT=number, MATDOCUMENTYEAR=year)
    except Exception as error:
        return rfc_error_result(error, function=function, material_document=number, year=year)

    messages = return_messages(response.get("RETURN"))
    header = compact(response.get("GOODSMVT_HEADER") or {})
    if not header.get("MAT_DOC"):
        return json_safe(
            {
                "status": "error" if has_error(messages) else "not_found",
                "connection": "RFC",
                "function": function,
                "material_document": number,
                "year": year,
                "return_messages": messages,
            }
        )
    return json_safe(
        {
            "status": "error" if has_error(messages) else "ok",
            "connection": "RFC",
            "function": function,
            "material_document": number,
            "year": year,
            "header": header,
            "items": compact(response.get("GOODSMVT_ITEMS") or []),
            "return_messages": messages,
        }
    )


@mcp.tool(annotations=READ_ONLY)
async def search_material_documents(
    plant: str = "",
    material: str = "",
    movement_type: str = "",
    storage_location: str = "",
    batch: str = "",
    vendor: str = "",
    purchase_order: str = "",
    posting_date_from: str = "",
    posting_date_to: str = "",
    user: str = "",
    max_results: int = 100,
) -> dict[str, Any]:
    """List goods movement items (GR/GI/transfers) with BAPI_GOODSMVT_GETITEMS, newest first.

    Needs at least one of plant, material, purchase_order, vendor or batch.
    movement_type accepts a comma-separated list such as "101,102,261". Posting dates
    default to the last 7 days (SAP server date) and may span at most 366 days.
    Each item carries its document header fields (posting date, user, header text).
    """
    functions = ["RFC_SYSTEM_INFO", "BAPI_GOODSMVT_GETITEMS"]
    if not sap_rfc.is_connected:
        return connection_unavailable(functions)
    try:
        plant = org_unit(plant, "plant", 4)
        storage_location = org_unit(storage_location, "storage_location", 4)
        number = material_number(material) if material.strip() else ""
        batch = sap_key(batch, "batch", 10) if batch.strip() else ""
        vendor = sap_key(vendor, "vendor", 10, numeric_length=10) if vendor.strip() else ""
        purchase_order = (
            sap_key(purchase_order, "purchase_order", 10, numeric_length=10) if purchase_order.strip() else ""
        )
        movement_types = [
            org_unit(value, "movement_type", 3) for value in movement_type.split(",") if value.strip()
        ]
        date_from = sap_date(posting_date_from, "posting_date_from") if posting_date_from.strip() else ""
        date_to = sap_date(posting_date_to, "posting_date_to") if posting_date_to.strip() else ""
        user = sap_key(user, "user", 12) if user.strip() else ""
    except ValueError as error:
        return validation_error(functions, str(error))
    if not (plant or number or purchase_order or vendor or batch):
        return validation_error(functions, "Provide plant, material, purchase_order, vendor or batch.")
    limit = clamp(max_results, 1, 500)

    if not date_from or not date_to:
        try:
            today = sap_server_clock()[0].date()
        except Exception as error:
            return rfc_error_result(error, function=functions)
        date_to = date_to or today.strftime("%Y%m%d")
        date_from = date_from or (today - timedelta(days=7)).strftime("%Y%m%d")
    span = datetime.strptime(date_to, "%Y%m%d") - datetime.strptime(date_from, "%Y%m%d")
    if span < timedelta(0):
        return validation_error(functions, "posting_date_from is after posting_date_to.")
    if span > timedelta(days=366):
        return validation_error(functions, "The posting date range may span at most 366 days.")

    params: dict[str, Any] = {
        "PSTNG_DATE_RA": [{"SIGN": "I", "OPTION": "BT", "LOW": date_from, "HIGH": date_to}],
    }
    if plant:
        params["PLANT_RA"] = _include([plant])
    if storage_location:
        params["STGE_LOC_RA"] = _include([storage_location])
    if number:
        params["MATERIAL_RA"] = [{"SIGN": "I", "OPTION": "EQ", "LOW_LONG": number}]
    if movement_types:
        params["MOVE_TYPE_RA"] = _include(movement_types)
    if batch:
        params["BATCH_RA"] = _include([batch])
    if vendor:
        params["VENDOR_RA"] = _include([vendor])
    if purchase_order:
        params["PURCH_DOC_RA"] = _include([purchase_order])
    if user:
        params["USERNAME_RA"] = _include([user])

    try:
        response = call_rfc("BAPI_GOODSMVT_GETITEMS", **params)
    except Exception as error:
        return rfc_error_result(error, function=functions)

    messages = return_messages(response.get("RETURN"))
    headers = {
        (row.get("MAT_DOC"), row.get("DOC_YEAR")): pick(row, _HEADER_FIELDS)
        for row in response.get("GOODSMVT_HEADER") or []
    }
    items = []
    for row in response.get("GOODSMVT_ITEMS") or []:
        item = pick(row, _ITEM_FIELDS)
        if "MATERIAL_LONG" not in item and not is_initial(row.get("MATERIAL")):
            item["MATERIAL_LONG"] = row["MATERIAL"]
        item.update(headers.get((row.get("MAT_DOC"), row.get("DOC_YEAR")), {}))
        items.append(item)
    items.sort(
        key=lambda item: (
            item.get("PSTNG_DATE", ""),
            item.get("ENTRY_DATE", ""),
            item.get("ENTRY_TIME", ""),
            item.get("MAT_DOC", ""),
        ),
        reverse=True,
    )
    rows, paging = page(items, limit)

    # M7 842 "No document exists for the specified data" just means an empty result.
    if has_error_except(messages, ("M7", "842")):
        status = "partial" if items else "error"
    elif items:
        status = "ok"
    else:
        status = "not_found"
    return json_safe(
        {
            "status": status,
            "connection": "RFC",
            "function": functions,
            "posting_date_from": date_from,
            "posting_date_to": date_to,
            "documents": len(headers),
            "items_by_movement_type": dict(Counter(item.get("MOVE_TYPE") for item in items).most_common()),
            **paging,
            "items": rows,
            "return_messages": messages,
        }
    )


@mcp.tool(annotations=READ_ONLY)
async def get_material_stock(
    material: str,
    plant: str,
    storage_location: str = "",
    include_mrp_elements: bool = False,
    max_mrp_elements: int = 50,
) -> dict[str, Any]:
    """Current stock of a material in a plant (MD04 view) with BAPI_MATERIAL_STOCK_REQ_LIST.

    plant_stock always lists unrestricted, quality inspection, blocked, restricted,
    returns, GR-blocked, in-transfer, in-transit and total stock in the base unit.
    storage_location (comma-separated, up to 10) adds batch and special stock per
    storage location from /SPE/MATERIAL_STOCK_READ. include_mrp_elements adds the MD04
    receipt/requirement lines (max_mrp_elements: 1-500).
    """
    functions = ["BAPI_MATERIAL_STOCK_REQ_LIST"]
    if storage_location.strip():
        functions.append("/SPE/MATERIAL_STOCK_READ")
    if not sap_rfc.is_connected:
        return connection_unavailable(functions)
    try:
        number = material_number(material)
        plant = org_unit(plant, "plant", 4)
        storage_locations = list(
            dict.fromkeys(
                org_unit(value, "storage_location", 4) for value in storage_location.split(",") if value.strip()
            )
        )
    except ValueError as error:
        return validation_error(functions, str(error))
    if not plant:
        return validation_error(functions, "plant is required.")
    if len(storage_locations) > 10:
        return validation_error(functions, "storage_location accepts at most 10 values.")

    try:
        response = call_rfc(
            "BAPI_MATERIAL_STOCK_REQ_LIST",
            MATERIAL_LONG=number,
            PLANT=plant,
            GET_IND_LINES="X" if include_mrp_elements else "",
        )
    except Exception as error:
        return rfc_error_result(error, function=functions, material=number, plant=plant)

    messages = return_messages(response.get("RETURN"))
    mrp_list = response.get("MRP_LIST") or {}
    stock = response.get("MRP_STOCK_DETAIL") or {}
    result: dict[str, Any] = {
        "status": "ok",
        "connection": "RFC",
        "function": functions,
        "material": number,
        "plant": plant,
    }
    if has_error(messages):
        result["status"] = "error"
    else:
        result["base_unit"] = mrp_list.get("BASE_UOM")
        result["plant_stock"] = {name: stock.get(field) for name, field in _PLANT_STOCK.items()}
        result["open_quantities"] = compact(
            {
                field: value
                for field, value in stock.items()
                if field not in _PLANT_STOCK.values()
                and field not in {"STATISTIC_CREATED", "DENOMINATR", "NUMERATOR"}
            }
        )
        result["planning"] = pick(
            mrp_list,
            ("MRP_TYPE", "MRP_CTRLER", "PROC_TYPE", "ABC_ID", "SAFETY_STK", "REORDER_PT", "MAX_STOCK", "LOTSIZEKEY"),
        )
        if include_mrp_elements:
            lines = [
                without_blanks(
                    {
                        "date": line.get("AVAIL_DATE"),
                        "element": line.get("MRP_ELEMNT"),
                        "element_data": line.get("ELEMNT_DATA"),
                        "quantity": line.get("REC_REQD_QTY"),
                        "available_quantity": line.get("AVAIL_QTY1"),
                        "storage_location": line.get("STORAGE_LOC"),
                        "exception": line.get("EXCMESSAGE"),
                        "vendor": line.get("VENDOR_NO"),
                        "customer": line.get("CUSTOMER"),
                    }
                )
                for line in response.get("MRP_IND_LINES") or []
            ]
            result["mrp_elements"], result["mrp_elements_paging"] = page(lines, clamp(max_mrp_elements, 1, 500))

    if storage_locations:
        by_location: dict[str, list[dict[str, Any]]] = {}
        for location in storage_locations:
            try:
                rows = call_rfc(
                    "/SPE/MATERIAL_STOCK_READ",
                    I_PLANT=plant,
                    I_STORAGE_LOC=location,
                    IT_MATNR_RANGE=[{"SIGN": "I", "OPTION": "EQ", "LOW_LONG": number}],
                ).get("ET_MAT_STOCK") or []
            except Exception as error:
                return rfc_error_result(error, function=functions, material=number, plant=plant)
            by_location[location] = [
                {
                    name: row.get(field)
                    for name, field in _STORAGE_LOCATION_STOCK.items()
                    if name in _ALWAYS_REPORTED or not is_initial(row.get(field))
                }
                for row in rows
            ]
        result["storage_location_stock"] = by_location
        if result["status"] == "error":
            result["status"] = "partial"

    result["return_messages"] = messages
    return json_safe(result)


@mcp.tool(annotations=READ_ONLY)
async def search_material_stock(
    plant: str,
    storage_location: str,
    material: str = "",
    batch: str = "",
    max_results: int = 100,
) -> dict[str, Any]:
    """List standard IM stock in one plant/storage location via /SPE/MATERIAL_STOCK_READ.

    material is an optional exact SAP selection. batch filters returned CHARG
    values locally. Returns native SAP fields, including stock buckets and
    special-stock dimensions; preserves zero quantities. No EWM bins or MD04
    totals. max_results limits returned rows locally (1-500), not SAP's query.
    """
    function = "/SPE/MATERIAL_STOCK_READ"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        plant = org_unit(plant, "plant", 4)
        storage_location = org_unit(storage_location, "storage_location", 4)
        if not plant or not storage_location:
            raise ValueError("plant and storage_location are required.")
        material = material_number(material) if material.strip() else ""
        batch = sap_key(batch, "batch", 10) if batch.strip() else ""
    except ValueError as error:
        return validation_error(function, str(error))
    try:
        response = call_rfc(
            function, I_PLANT=plant, I_STORAGE_LOC=storage_location,
            IT_MATNR_RANGE=[{"SIGN": "I", "OPTION": "EQ", "LOW_LONG": material}] if material else [],
        )
    except Exception as error:
        return rfc_error_result(error, function=function)
    messages = return_messages(response.get("RETURN"))
    items = [without_blanks(row) for row in response.get("ET_MAT_STOCK") or []
             if not batch or str(row.get("CHARG") or "").strip() == batch]
    rows, paging = page(items, clamp(max_results, 1, 500))
    return json_safe({
        "status": "error" if has_error(messages) else "ok" if rows else "not_found",
        "connection": "RFC", "function": function, "plant": plant, "storage_location": storage_location,
        **paging, "items": rows, "return_messages": messages,
    })


@mcp.tool(annotations=READ_ONLY)
async def search_physical_inventory_documents(
    plant: str,
    fiscal_year: str,
    storage_location: str = "",
    max_results: int = 100,
) -> dict[str, Any]:
    """Search standard IM physical inventory headers with BAPI_MATPHYSINV_GETLIST.

    plant/year are required; storage_location is optional. max_results limits
    returned headers locally (1-500). Use get_physical_inventory_document for
    item counts, book quantities and SAP difference-posting status fields.
    """
    function = "BAPI_MATPHYSINV_GETLIST"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        plant = org_unit(plant, "plant", 4)
        storage_location = org_unit(storage_location, "storage_location", 4)
        if not plant:
            raise ValueError("plant is required.")
        year = fiscal_year.strip()
        if len(year) != 4 or not year.isdigit():
            raise ValueError("fiscal_year must have four digits.")
    except ValueError as error:
        return validation_error(function, str(error))
    params = {"PLANT_RA": _include([plant]), "FISCALYEAR_RA": _include([year])}
    if storage_location:
        params["STGE_LOC_RA"] = _include([storage_location])
    try:
        response = call_rfc(function, **params)
    except Exception as error:
        return rfc_error_result(error, function=function)
    messages = return_messages(response.get("RETURN"))
    rows, paging = page([without_blanks(row) for row in response.get("HEADERS") or []], clamp(max_results, 1, 500))
    return json_safe({
        "status": "error" if has_error(messages) else "ok" if rows else "not_found",
        "connection": "RFC", "function": function, **paging, "items": rows, "return_messages": messages,
    })


@mcp.tool(annotations=READ_ONLY)
async def get_physical_inventory_document(physical_inventory_document: str, fiscal_year: str) -> dict[str, Any]:
    """Read an IM physical inventory header/items with BAPI_MATPHYSINV_GETDETAIL.

    Document number AND fiscal year are required. Numeric document numbers may
    omit leading zeros. Zero counts and amounts are preserved. Never enters
    counts, initiates recounts or posts inventory differences.
    """
    function = "BAPI_MATPHYSINV_GETDETAIL"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        number = sap_key(physical_inventory_document, "physical_inventory_document", 10, numeric_length=10)
        year = fiscal_year.strip()
        if len(year) != 4 or not year.isdigit():
            raise ValueError("fiscal_year must have four digits.")
    except ValueError as error:
        return validation_error(function, str(error))
    try:
        response = call_rfc(function, PHYSINVENTORY=number, FISCALYEAR=year)
    except Exception as error:
        return rfc_error_result(error, function=function)
    messages = return_messages(response.get("RETURN"))
    header = response.get("HEAD") or {}
    items = [without_blanks(row) for row in response.get("ITEMS") or []]
    return json_safe({
        "status": "error" if has_error(messages) else "ok" if compact(header) or items else "not_found",
        "connection": "RFC", "function": function, "physical_inventory_document": number, "fiscal_year": year,
        "header": without_blanks(header), "items": items, "return_messages": messages,
    })


@mcp.tool(annotations=READ_ONLY)
async def search_reservations(
    plant: str,
    material: str = "",
    requirement_date: str = "",
    max_results: int = 100,
) -> dict[str, Any]:
    """Search standard reservation items with BAPI_RESERVATION_GETITEMS1.

    plant is required. material is an exact classic material number (max 18);
    requirement_date is an exact date, not a start date. SAP's standard BAPI
    movement/final-issue selection defaults apply. Returned status flags do
    not establish an inferred open/closed state. max_results truncates locally.
    """
    function = "BAPI_RESERVATION_GETITEMS1"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        plant = org_unit(plant, "plant", 4)
        if not plant:
            raise ValueError("plant is required.")
        material = sap_key(material, "material", 18, numeric_length=18) if material.strip() else ""
        day = sap_date(requirement_date, "requirement_date") if requirement_date.strip() else ""
    except ValueError as error:
        return validation_error(function, str(error))
    params = {"PLANT": plant}
    if material:
        params["MATERIAL"] = material
    if day:
        params["REQ_DATE"] = day
    try:
        response = call_rfc(function, **params)
    except Exception as error:
        return rfc_error_result(error, function=function)
    messages = return_messages(response.get("RETURN"))
    rows, paging = page([without_blanks(row) for row in response.get("RESERVATION_ITEMS") or []], clamp(max_results, 1, 500))
    return json_safe({
        "status": "error" if has_error_except(messages, ("W5", "027")) else "ok" if rows else "not_found",
        "connection": "RFC", "function": function, **paging, "items": rows, "return_messages": messages,
    })


@mcp.tool(annotations=READ_ONLY)
async def get_batch(material: str, batch: str, plant: str = "") -> dict[str, Any]:
    """Read batch master attributes (manufacture/expiry dates, supplier batch) and restriction status.

    Uses BAPI_BATCH_GET_DETAIL's classic material field (at most 18 characters).
    Supply plant for plant-level batches; an empty plant supports material-level
    batches. No batch classification or status change is performed.
    """
    function = "BAPI_BATCH_GET_DETAIL"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        number = sap_key(material, "material", 18, numeric_length=18)
        batch = sap_key(batch, "batch", 10)
        plant = org_unit(plant, "plant", 4)
    except ValueError as error:
        return validation_error(function, str(error))
    try:
        response = call_rfc(function, MATERIAL=number, BATCH=batch, PLANT=plant)
    except Exception as error:
        return rfc_error_result(error, function=function)
    messages = return_messages(response.get("RETURN"))
    return json_safe({"status": "error" if has_error(messages) else "ok", "connection": "RFC", "function": function,
                      "material": number, "batch": batch, "plant": plant,
                      "attributes": without_blanks(response.get("BATCHATTRIBUTES") or {}),
                      "batch_status": without_blanks(response.get("BATCHSTATUS") or {}), "return_messages": messages})


@mcp.tool(annotations=READ_ONLY)
async def get_reservation(reservation: str) -> dict[str, Any]:
    """Read a standard reservation header/items with BAPI_RESERVATION_GETDETAIL1.

    Numeric reservation numbers may omit leading zeros. Returns SAP quantities
    and status flags with zero quantities preserved; does not change reservations.
    """
    function = "BAPI_RESERVATION_GETDETAIL1"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        number = sap_key(reservation, "reservation", 10, numeric_length=10)
    except ValueError as error:
        return validation_error(function, str(error))
    try:
        response = call_rfc(function, RESERVATION=number)
    except Exception as error:
        return rfc_error_result(error, function=function)
    messages = return_messages(response.get("RETURN"))
    header = response.get("RESERVATION_HEADER") or {}
    items = [without_blanks(row) for row in response.get("RESERVATION_ITEMS") or []]
    return json_safe({
        "status": "error" if has_error(messages) else "ok" if compact(header) or items else "not_found",
        "connection": "RFC", "function": function, "reservation": number,
        "header": without_blanks(header), "items": items, "return_messages": messages,
    })
