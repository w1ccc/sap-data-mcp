"""Standard read-only purchasing documents and purchasing info records."""

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
    validation_error,
    without_blanks,
)


def _read_document(function, params, header_key, tables):
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        response = call_rfc(function, **params)
    except Exception as error:
        return rfc_error_result(error, function=function)
    messages = return_messages(response.get("RETURN"))
    header = without_blanks(response.get(header_key) or {})
    data = {name: [without_blanks(row) for row in response.get(table) or []] for name, table in tables.items()}
    return json_safe({"status": "error" if has_error(messages) else "ok" if any(data.values()) or header.get("NUMBER") or header.get("SHEET_NO") or header.get("PO_NUMBER") else "not_found",
                      "connection": "RFC", "function": function, "header": header, **data, "return_messages": messages})


@mcp.tool(annotations=READ_ONLY)
async def search_purchasing_info_records(
    material: str = "", supplier: str = "", purchasing_org: str = "", plant: str = "",
    include_deleted: bool = False, max_results: int = 100,
) -> dict[str, Any]:
    """Search purchasing info records by exact material, supplier, purchasing organization or plant.

    Returns general data and purchasing-organization/plant prices and quantities.
    At least one scope is required. SAP reads the matching set; output is capped locally.
    """
    return _info_records(material=material, supplier=supplier, purchasing_org=purchasing_org, plant=plant,
                         include_deleted=include_deleted, max_results=max_results)


@mcp.tool(annotations=READ_ONLY)
async def get_purchasing_info_record(purchasing_info_record: str, max_results: int = 100) -> dict[str, Any]:
    """Read a purchasing info record's general and purchasing-organization/plant data, including deleted records."""
    return _info_records(number=purchasing_info_record, include_deleted=True, max_results=max_results)


def _info_records(number="", material="", supplier="", purchasing_org="", plant="", include_deleted=False, max_results=100):
    function = "BAPI_INFORECORD_GETLIST"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        params = {"GENERAL_DATA": "X", "PURCHORG_DATA": "X", "DELETED_INFORECORDS": "X" if include_deleted else ""}
        for field, value, length in (("PURCHASINGINFOREC", number, 10), ("VENDOR", supplier, 10),
                                     ("PURCH_ORG", purchasing_org, 4), ("PLANT", plant, 4)):
            if value.strip():
                params[field] = sap_key(value, field, length, numeric_length=10 if length == 10 else None)
        if material.strip():
            params["MATERIAL_LONG"] = material_number(material)
        if not (number or material or supplier or purchasing_org or plant):
            raise ValueError("Provide material, supplier, purchasing_org or plant.")
    except ValueError as error:
        return validation_error(function, str(error))
    try:
        response = call_rfc(function, **params)
    except Exception as error:
        return rfc_error_result(error, function=function)
    messages = return_messages(response.get("RETURN"))
    general, paging = page([without_blanks(row) for row in response.get("INFORECORD_GENERAL") or []], clamp(max_results, 1, 500))
    org_data, org_paging = page([without_blanks(row) for row in response.get("INFORECORD_PURCHORG") or []], clamp(max_results, 1, 500))
    return json_safe({"status": "error" if has_error(messages) else "ok" if general or org_data else "not_found",
                      "connection": "RFC", "function": function, **paging, "items": general,
                      "purchasing_data": {**org_paging, "items": org_data}, "return_messages": messages})


@mcp.tool(annotations=READ_ONLY)
async def get_purchase_contract(purchase_contract: str) -> dict[str, Any]:
    """Read a standard purchase contract's header, items, account assignments, conditions and release documentation."""
    function = "BAPI_CONTRACT_GETDETAIL"
    try:
        number = sap_key(purchase_contract, "purchase_contract", 10, numeric_length=10)
    except ValueError as error:
        return validation_error(function, str(error))
    return _read_document(function, {"PURCHASINGDOCUMENT": number, "ITEM_DATA": "X", "ACCOUNT_DATA": "X", "CONDITION_DATA": "X", "RELEASE_DATA": "X"},
                          "HEADER", {"items": "ITEM", "account_assignments": "ACCOUNT", "conditions": "ITEM_CONDITION",
                                     "condition_validity": "ITEM_COND_VALIDITY", "release_documentation": "RELEASE_DOCU"})


@mcp.tool(annotations=READ_ONLY)
async def get_scheduling_agreement(scheduling_agreement: str) -> dict[str, Any]:
    """Read a purchase scheduling agreement's header, items, delivery schedule, accounts and subcontracting components."""
    function = "BAPI_SAG_GETDETAIL"
    try:
        number = sap_key(scheduling_agreement, "scheduling_agreement", 10, numeric_length=10)
    except ValueError as error:
        return validation_error(function, str(error))
    return _read_document(function, {"PURCHASINGDOCUMENT": number, "ACCOUNT_DATA": "X", "CONDITION_DATA": "X", "SC_COMPONENT_DATA": "X"},
                          "HEADER", {"items": "ITEM", "schedules": "SCHEDULE", "account_assignments": "ACCOUNT", "conditions": "ITEM_CONDITION", "components": "SC_COMPONENT"})


@mcp.tool(annotations=READ_ONLY)
async def get_purchase_order_history(purchase_order: str, max_results: int = 100) -> dict[str, Any]:
    """Read PO history references for goods movements, invoice receipts, reversals and service receipts.

    Returns SAP history categories, debit/credit signs and document years without
    inferring FI payment or clearing. Each history collection is capped locally.
    """
    function = "BAPI_PO_GETDETAIL1"
    try:
        number = sap_key(purchase_order, "purchase_order", 10, numeric_length=10)
    except ValueError as error:
        return validation_error(function, str(error))
    result = _read_document(function, {"PURCHASEORDER": number}, "POHEADER",
                            {"items": "POHISTORY", "account_history": "POHISTORY_MA", "totals": "POHISTORY_TOTALS"})
    for field in ("items", "account_history", "totals"):
        if field in result:
            rows, paging = page(result[field], clamp(max_results, 1, 500))
            result[field] = {**paging, "items": rows}
    return result


@mcp.tool(annotations=READ_ONLY)
async def search_service_entry_sheets(purchase_order: str, max_results: int = 100) -> dict[str, Any]:
    """List classic MM service entry sheets for one purchase order; output capped locally. Lean services use OData."""
    function = "BAPI_ENTRYSHEET_GETLIST"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        number = sap_key(purchase_order, "purchase_order", 10, numeric_length=10)
    except ValueError as error:
        return validation_error(function, str(error))
    try:
        response = call_rfc(function, PO_NUMBER=number)
    except Exception as error:
        return rfc_error_result(error, function=function)
    messages = return_messages(response.get("RETURN"))
    rows, paging = page([without_blanks(row) for row in response.get("ENTRYSHEET_HEADER") or []], clamp(max_results, 1, 500))
    return json_safe({"status": "error" if has_error(messages) else "ok" if rows else "not_found", "connection": "RFC",
                      "function": function, **paging, "items": rows, "return_messages": messages})


@mcp.tool(annotations=READ_ONLY)
async def get_service_entry_sheet(service_entry_sheet: str) -> dict[str, Any]:
    """Read a classic MM service entry sheet with service lines and account assignments. Lean services use OData."""
    function = "BAPI_ENTRYSHEET_GETDETAIL"
    try:
        number = sap_key(service_entry_sheet, "service_entry_sheet", 10, numeric_length=10)
    except ValueError as error:
        return validation_error(function, str(error))
    return _read_document(function, {"ENTRYSHEET": number}, "ENTRYSHEET_HEADER",
                          {"items": "ENTRYSHEET_SERVICES", "account_assignments": "ENTRYSHEET_ACCOUNT_ASSIGNMENT", "service_account_values": "ENTRYSHEET_SRV_ACCASS_VALUES"})


# Tables of BAPI_PO_GETDETAIL1 that get_purchase_order does not return.
_UNUSED_PO_TABLES = [
    "POEXPIMPHEADER",
    "ALLVERSIONS",
    "EXTENSIONOUT",
    "INVPLANHEADER",
    "INVPLANITEM",
    "POCOMPONENTS",
    "POCONDHEADER",
    "POCONFIRMATION",
    "POCONTRACTLIMITS",
    "POEXPIMPITEM",
    "POHISTORY",
    "POHISTORY_MA",
    "POHISTORY_TOTALS",
    "POLIMITS",
    "POSERVICES",
    "POSHIPPINGEXP",
    "POSRVACCESSVALUES",
    "POTEXTHEADER",
    "POTEXTITEM",
    "SERIALNUMBER",
]


@mcp.tool(annotations=READ_ONLY)
async def get_purchase_order(purchase_order: str) -> dict[str, Any]:
    """Read purchase order details with the standard BAPI_PO_GETDETAIL1 BAPI."""
    function = "BAPI_PO_GETDETAIL1"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)

    po_number = purchase_order.strip()
    if not po_number or not po_number.isdigit() or len(po_number) > 10:
        return validation_error(function, "purchase_order must contain 1 to 10 digits.")
    po_number = po_number.zfill(10)

    try:
        response = call_rfc(
            function,
            options={"not_requested": _UNUSED_PO_TABLES},
            PURCHASEORDER=po_number,
            ACCOUNT_ASSIGNMENT="X",
        )
    except Exception as error:
        return rfc_error_result(error, function=function, purchase_order=po_number)

    messages = return_messages(response.get("RETURN"))
    result = {
        "status": "error" if has_error(messages) else "ok" if response.get("POITEM") or (response.get("POHEADER") or {}).get("PO_NUMBER") else "not_found",
        "connection": "RFC",
        "function": function,
        "purchase_order": po_number,
        "header": response.get("POHEADER") or {},
        "items": response.get("POITEM") or [],
        "schedules": response.get("POSCHEDULE") or [],
        "account_assignments": response.get("POACCOUNT") or [],
        "delivery_addresses": response.get("POADDRDELIVERY") or [],
        "partners": response.get("POPARTNER") or [],
        "conditions": response.get("POCOND") or [],
        "return_messages": messages,
    }
    return json_safe(result)


# Tables that BAPI_PR_GETDETAIL fills without being asked but no tool returns.
_UNUSED_DETAIL_TABLES = [
    "ALLVERSIONS",
    "EXTENSIONOUT",
    "PRCOMPONENTS",
    "SERIALNUMBERS",
    "SERVICEACCOUNT",
    "SERVICECONTRACTLIMITS",
    "SERVICELIMIT",
    "SERVICELINES",
    "SERVICELONGTEXTS",
    "SERVICEOUTLINE",
]

_ITEM_FIELDS = (
    "PREQ_NO",
    "PREQ_ITEM",
    "DOC_TYPE",
    "PREQ_DATE",
    "CREATED_BY",
    "PREQ_NAME",
    "PUR_GROUP",
    "PURCH_ORG",
    "MATERIAL_LONG",
    "SHORT_TEXT",
    "MAT_GRP",
    "PLANT",
    "STORE_LOC",
    "QUANTITY",
    "UNIT",
    "ORDERED",
    "DELIV_DATE",
    "REL_DATE",
    "C_AMT_BAPI",
    "PRICE_UNIT",
    "CURRENCY",
    "ITEM_CAT",
    "ACCTASSCAT",
    "DES_VENDOR",
    "FIXED_VEND",
    "AGREEMENT",
    "AGMT_ITEM",
    "INFO_REC",
    "TRACKINGNO",
    "MRP_CONTR",
    "GENERAL_RELEASE",
    "REQ_BLOCKED",
)


@mcp.tool(annotations=READ_ONLY)
async def get_purchase_requisition(
    purchase_requisition: str,
    include_account_assignment: bool = True,
    include_texts: bool = True,
    include_delivery_address: bool = False,
) -> dict[str, Any]:
    """Read one purchase requisition (header, items, account assignment, texts) with BAPI_PR_GETDETAIL.

    Numeric requisition numbers may omit leading zeros. Empty fields are omitted.
    """
    function = "BAPI_PR_GETDETAIL"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        number = sap_key(purchase_requisition, "purchase_requisition", 10, numeric_length=10)
    except ValueError as error:
        return validation_error(function, str(error))

    try:
        response = call_rfc(
            function,
            options={"not_requested": _UNUSED_DETAIL_TABLES},
            NUMBER=number,
            ACCOUNT_ASSIGNMENT="X" if include_account_assignment else "",
            HEADER_TEXT="X" if include_texts else "",
            ITEM_TEXT="X" if include_texts else "",
            DELIVERY_ADDRESS="X" if include_delivery_address else "",
        )
    except Exception as error:
        return rfc_error_result(error, function=function, purchase_requisition=number)

    messages = return_messages(response.get("RETURN"))
    header = compact(response.get("PRHEADER") or {})
    items = compact(response.get("PRITEM") or [])
    if not header.get("PREQ_NO") and not items:
        return json_safe(
            {
                "status": "error" if has_error(messages) else "not_found",
                "connection": "RFC",
                "function": function,
                "purchase_requisition": number,
                "return_messages": messages,
            }
        )

    result: dict[str, Any] = {
        "status": "error" if has_error(messages) else "ok",
        "connection": "RFC",
        "function": function,
        "purchase_requisition": number,
        "header": header,
        "items": items,
    }
    if include_account_assignment:
        result["account_assignments"] = compact(response.get("PRACCOUNT") or [])
    if include_texts:
        result["header_texts"] = compact(response.get("PRHEADERTEXT") or [])
        result["item_texts"] = compact(response.get("PRITEMTEXT") or [])
    if include_delivery_address:
        result["delivery_addresses"] = compact(response.get("PRADDRDELIVERY") or [])
    result["return_messages"] = messages
    return json_safe(result)


@mcp.tool(annotations=READ_ONLY)
async def search_purchase_requisitions(
    plant: str = "",
    material: str = "",
    purchasing_group: str = "",
    requisitioner: str = "",
    material_group: str = "",
    document_type: str = "",
    requested_since: str = "",
    include_closed: bool = False,
    include_deleted: bool = False,
    include_partially_ordered: bool = False,
    include_assigned: bool = False,
    max_results: int = 100,
) -> dict[str, Any]:
    """List purchase requisition items with BAPI_REQUISITION_GETITEMS; open items by default.

    Needs at least one of plant, material, purchasing_group, requisitioner or
    material_group. requested_since keeps items requested on or after that date
    (YYYY-MM-DD). The include_* flags add closed, deleted, partially ordered or
    source-assigned items. Newest requisitions come first; max_results: 1-500.
    """
    function = "BAPI_REQUISITION_GETITEMS"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        plant = org_unit(plant, "plant", 4)
        purchasing_group = org_unit(purchasing_group, "purchasing_group", 3)
        document_type = org_unit(document_type, "document_type", 4)
        number = material_number(material) if material.strip() else ""
        material_group = sap_key(material_group, "material_group", 9) if material_group.strip() else ""
        requisitioner = requisitioner.strip().upper()
        since = sap_date(requested_since, "requested_since") if requested_since.strip() else ""
    except ValueError as error:
        return validation_error(function, str(error))
    if len(requisitioner) > 12:
        return validation_error(function, "requisitioner may have at most 12 characters.")
    if not (plant or number or purchasing_group or requisitioner or material_group):
        return validation_error(
            function, "Provide plant, material, purchasing_group, requisitioner or material_group."
        )
    limit = clamp(max_results, 1, 500)

    params: dict[str, Any] = {
        "OPEN_ITEMS": "X",
        "CLOSED_ITEMS": "X" if include_closed else "",
        "DELETED_ITEMS": "X" if include_deleted else "",
        "PARTIALLY_ORDERED_ITEMS": "X" if include_partially_ordered else "",
        "ASSIGNED_ITEMS": "X" if include_assigned else "",
    }
    for parameter, value in (
        ("PLANT", plant),
        ("MATERIAL_LONG", number),
        ("PUR_GROUP", purchasing_group),
        ("PREQ_NAME", requisitioner),
        ("MAT_GRP", material_group),
        ("DOC_TYPE", document_type),
        ("PREQ_DATE", since),
    ):
        if value:
            params[parameter] = value

    try:
        response = call_rfc(function, **params)
    except Exception as error:
        return rfc_error_result(error, function=function)

    messages = return_messages(response.get("RETURN"))
    items = [pick(row, _ITEM_FIELDS) for row in response.get("REQUISITION_ITEMS") or []]
    items.sort(key=lambda row: (row.get("PREQ_DATE", ""), row.get("PREQ_NO", "")), reverse=True)
    rows, paging = page(items, limit)
    if has_error(messages):
        status = "error"
    else:
        status = "ok" if rows else "not_found"
    return json_safe(
        {
            "status": status,
            "connection": "RFC",
            "function": function,
            "requisitions": len({row.get("PREQ_NO") for row in items}),
            **paging,
            "items": rows,
            "return_messages": messages,
        }
    )


@mcp.tool(annotations=READ_ONLY)
async def search_purchase_orders(
    plant: str = "",
    supplier: str = "",
    material: str = "",
    purchasing_org: str = "",
    purchasing_group: str = "",
    document_type: str = "",
    document_date: str = "",
    open_for_receipt: bool = False,
    include_deleted: bool = False,
    max_results: int = 100,
) -> dict[str, Any]:
    """Search purchase order items with BAPI_PO_GETITEMS, including their headers.

    Provide plant, supplier, material, purchasing_org or purchasing_group.
    document_date is an exact document date (YYYY-MM-DD), not a starting date.
    open_for_receipt restricts the SAP query to items still awaiting receipt.
    max_results limits returned items locally (1-500); headers cover those items.
    This is a basic item list; use get_purchase_order for quantities and schedules.
    """
    function = "BAPI_PO_GETITEMS"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        plant = org_unit(plant, "plant", 4)
        supplier = sap_key(supplier, "supplier", 10, numeric_length=10) if supplier.strip() else ""
        material = material_number(material) if material.strip() else ""
        purchasing_org = org_unit(purchasing_org, "purchasing_org", 4)
        purchasing_group = org_unit(purchasing_group, "purchasing_group", 3)
        document_type = org_unit(document_type, "document_type", 4)
        document_date = sap_date(document_date, "document_date") if document_date.strip() else ""
    except ValueError as error:
        return validation_error(function, str(error))
    if not (plant or supplier or material or purchasing_org or purchasing_group):
        return validation_error(function, "Provide plant, supplier, material, purchasing_org or purchasing_group.")

    params = {
        "WITH_PO_HEADERS": "X",
        "ITEMS_OPEN_FOR_RECEIPT": "X" if open_for_receipt else "",
        "DELETED_ITEMS": "X" if include_deleted else "",
    }
    for parameter, value in (
        ("PLANT", plant), ("VENDOR", supplier), ("MATERIAL_LONG", material),
        ("PURCH_ORG", purchasing_org), ("PUR_GROUP", purchasing_group),
        ("DOC_TYPE", document_type), ("DOC_DATE", document_date),
    ):
        if value:
            params[parameter] = value
    try:
        response = call_rfc(function, **params)
    except Exception as error:
        return rfc_error_result(error, function=function)

    messages = return_messages(response.get("RETURN"))
    items = [
        without_blanks(row) for row in response.get("PO_ITEMS") or []
        if row.get("PO_NUMBER") and (include_deleted or not str(row.get("DELETE_IND") or "").strip())
    ]
    headers = {row["PO_NUMBER"]: row for row in response.get("PO_HEADERS") or [] if row.get("PO_NUMBER")}
    items.sort(key=lambda row: (str(headers.get(row["PO_NUMBER"], {}).get("DOC_DATE") or ""), row["PO_NUMBER"], row.get("PO_ITEM", "")), reverse=True)
    rows, paging = page(items, clamp(max_results, 1, 500))
    visible_orders = dict.fromkeys(row["PO_NUMBER"] for row in rows)
    return json_safe({
        "status": "error" if has_error_except(messages, ("W5", "037")) else "ok" if rows else "not_found",
        "connection": "RFC",
        "function": function,
        "purchase_orders": len({row["PO_NUMBER"] for row in items}),
        **paging,
        "headers": [without_blanks(headers[number]) for number in visible_orders if number in headers],
        "items": rows,
        "return_messages": messages,
    })


@mcp.tool(annotations=READ_ONLY)
async def search_supplier_invoices(
    supplier: str,
    document_date_from: str,
    document_date_to: str,
    max_results: int = 100,
) -> dict[str, Any]:
    """Search MM incoming invoice headers with BAPI_INCOMINGINVOICE_GETLIST.

    supplier and both document dates are required; the interval may span at
    most 366 days. These are invoice document dates, not posting/payment dates.
    max_results limits returned headers locally (1-500), not the SAP query.
    SAP invoice statuses are returned without inferring payment or FI clearing.
    """
    function = "BAPI_INCOMINGINVOICE_GETLIST"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        supplier = sap_key(supplier, "supplier", 10, numeric_length=10)
        start = sap_date(document_date_from, "document_date_from")
        end = sap_date(document_date_to, "document_date_to")
        if not timedelta(0) <= datetime.strptime(end, "%Y%m%d") - datetime.strptime(start, "%Y%m%d") <= timedelta(days=366):
            raise ValueError("Document dates must be ordered and at most 366 days apart.")
    except ValueError as error:
        return validation_error(function, str(error))
    try:
        response = call_rfc(
            function, VENDOR_RA=[{"SIGN": "I", "OPTION": "EQ", "LOW": supplier}],
            DOCDATE_RA=[{"SIGN": "I", "OPTION": "BT", "LOW": start, "HIGH": end}],
        )
    except Exception as error:
        return rfc_error_result(error, function=function)
    messages = return_messages(response.get("RETURN"))
    rows, paging = page([without_blanks(row) for row in response.get("HEADERLIST") or []], clamp(max_results, 1, 500))
    return json_safe({
        "status": "error" if has_error(messages) else "ok" if rows else "not_found",
        "connection": "RFC", "function": function, **paging, "items": rows, "return_messages": messages,
    })


@mcp.tool(annotations=READ_ONLY)
async def get_supplier_invoice(supplier_invoice: str, fiscal_year: str) -> dict[str, Any]:
    """Read an MM incoming invoice by number/year using BAPI_INCOMINGINVOICE_GETDETAIL.

    Numeric invoice numbers may omit leading zeros. Returns standard header,
    PO-reference items, account assignments, G/L/material items and tax tables.
    Preserves zero amounts/quantities. Does not read FI payment/clearing documents.
    """
    function = "BAPI_INCOMINGINVOICE_GETDETAIL"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        number = sap_key(supplier_invoice, "supplier_invoice", 10, numeric_length=10)
        year = fiscal_year.strip()
        if len(year) != 4 or not year.isdigit():
            raise ValueError("fiscal_year must have four digits.")
    except ValueError as error:
        return validation_error(function, str(error))
    try:
        response = call_rfc(function, INVOICEDOCNUMBER=number, FISCALYEAR=year)
    except Exception as error:
        return rfc_error_result(error, function=function, supplier_invoice=number, fiscal_year=year)
    messages = return_messages(response.get("RETURN"))
    header = response.get("HEADERDATA") or {}
    tables = {name: [without_blanks(row) for row in response.get(table) or []] for name, table in (
        ("items", "ITEMDATA"), ("account_assignments", "ACCOUNTINGDATA"),
        ("gl_account_items", "GLACCOUNTDATA"), ("material_items", "MATERIALDATA"),
        ("taxes", "TAXDATA"), ("withholding_taxes", "WITHTAXDATA"),
    )}
    return json_safe({
        "status": "error" if has_error(messages) else "ok" if compact(header) or any(tables.values()) else "not_found",
        "connection": "RFC", "function": function, "supplier_invoice": number, "fiscal_year": year,
        "header": without_blanks(header), **tables, "return_messages": messages,
    })
