"""Basic sales order queries through standard read-only BAPIs."""

from typing import Any

from core.app import (
    READ_ONLY, call_rfc, clamp, connection_unavailable, has_error, json_safe,
    material_number, mcp, org_unit, page, return_messages, rfc_error_result,
    sap_key, sap_rfc, validation_error, without_blanks, read_bapi,
)


@mcp.tool(annotations=READ_ONLY)
async def search_sales_orders(
    customer: str,
    sales_org: str,
    material: str = "",
    max_results: int = 100,
) -> dict[str, Any]:
    """List only SAP document-category C sales order items for one customer and sales organization.

    customer and sales_org are required and filter SAP's query. Numeric customer
    numbers may omit leading zeros. material is an optional exact local filter;
    Candidate categories are verified together with BAPISDORDER_GETDETAILEDLIST
    before counting or limiting results. max_results limits items locally (1-500).
    Use get_sales_order for
    one order's basic item quantities and statuses.
    """
    function = "BAPI_SALESORDER_GETLIST"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        customer = sap_key(customer, "customer", 10, numeric_length=10)
        sales_org = org_unit(sales_org, "sales_org", 4)
        if not sales_org:
            raise ValueError("sales_org is required.")
        material = material_number(material) if material.strip() else ""
    except ValueError as error:
        return validation_error(function, str(error))
    try:
        response = call_rfc(function, CUSTOMER_NUMBER=customer, SALES_ORGANIZATION=sales_org)
    except Exception as error:
        return rfc_error_result(error, function=function)

    messages = return_messages(response.get("RETURN"))
    items = []
    for row in (response.get("SALES_ORDERS") or []) if not has_error(messages) else []:
        if not row.get("SD_DOC"):
            continue
        if material:
            value = row.get("MATERIAL_LONG") or row.get("MATERIAL_EXTERNAL") or row.get("MATERIAL") or ""
            if not str(value).strip() or material_number(str(value)) != material:
                continue
        items.append(without_blanks(row))
    category_unavailable = False
    if items:
        try:
            headers = call_rfc(
                "BAPISDORDER_GETDETAILEDLIST",
                SALES_DOCUMENTS=[{"VBELN": number} for number in sorted({row["SD_DOC"] for row in items})],
                I_BAPI_VIEW={"HEADER": "X"},
            )
        except Exception as error:
            return rfc_error_result(error, function="BAPISDORDER_GETDETAILEDLIST")
        messages.extend(return_messages(headers.get("RETURN")))
        categories = {row.get("DOC_NUMBER"): (row.get("SD_DOC_CAT") or "").strip()
                      for row in headers.get("ORDER_HEADERS_OUT") or []}
        category_unavailable = any(not categories.get(row["SD_DOC"]) for row in items)
        items = [] if has_error(messages) or category_unavailable else [
            row for row in items if categories[row["SD_DOC"]] == "C"]
    items.sort(key=lambda row: (row["SD_DOC"], row.get("ITM_NUMBER", "")), reverse=True)
    rows, paging = page(items, clamp(max_results, 1, 500))
    result = {
        "status": "error" if has_error(messages) or category_unavailable else "ok" if rows else "not_found",
        "connection": "RFC",
        "function": function,
        "customer": customer,
        "sales_org": sales_org,
        "sales_orders": len({row["SD_DOC"] for row in items}),
        **paging,
        "items": rows,
        "return_messages": messages,
    }
    if category_unavailable and not has_error(messages):
        result.update(error_type="DocumentCategoryUnavailable",
                      error_message="SAP did not return a document category for every candidate; no order items were returned.")
    return json_safe(result)


@mcp.tool(annotations=READ_ONLY)
async def get_sales_order(sales_order: str) -> dict[str, Any]:
    """Read only a verified SAP document-category C sales order.

    Numeric sales order numbers may omit leading zeros. Returns STATUSINFO
    fields supplied by SAP, including material, requested quantity, price,
    currency and statuses. Complete data is added in details; items keeps its
    original STATUSINFO meaning. Child tables are capped independently at 100.
    """
    function = "BAPI_SALESORDER_GETSTATUS"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        number = sap_key(sales_order, "sales_order", 10, numeric_length=10)
    except ValueError as error:
        return validation_error(function, str(error))
    try:
        response = call_rfc(function, SALESDOCUMENT=number)
    except Exception as error:
        return rfc_error_result(error, function=function, sales_order=number)

    messages = return_messages(response.get("RETURN"))
    items = [without_blanks(row) for row in response.get("STATUSINFO") or []] if not has_error(messages) else []
    result = {
        "status": "error" if has_error(messages) else "ok" if items else "not_found",
        "connection": "RFC",
        "function": function,
        "sales_order": number,
        "items": items,
        "return_messages": messages,
    }
    if result["status"] == "ok":
        details = read_bapi("BAPISDORDER_GETDETAILEDLIST", {
            "SALES_DOCUMENTS": [{"VBELN": number}],
            "I_BAPI_VIEW": {"HEADER": "X", "ITEM": "X", "SDSCHEDULE": "X", "PARTNER": "X", "SDCOND": "X", "FLOW": "X"},
        })
        header = next((row for row in details.get("data", {}).get("ORDER_HEADERS_OUT", [])
                       if row.get("DOC_NUMBER") == number), {})
        category = (header.get("SD_DOC_CAT") or "").strip()
        if category != "C":
            result.update(status="error", items=[], expected_document_category="C",
                          document_category=category or None,
                          error_type=details.get("error_type") or ("UnexpectedDocumentCategory" if category else "DocumentCategoryUnavailable"),
                          error_message=details.get("error_message") or f"Expected SAP sales-order category C; received {category or 'no verified category'}.")
            result["return_messages"].extend(details.get("return_messages", []))
            return json_safe(result)
        result["details"] = details
        if details["status"] != "ok":
            result["status"] = "partial"
    return json_safe(result)



@mcp.tool(annotations=READ_ONLY)
async def get_customer(customer: str) -> dict[str, Any]:
    """Read activated customer general/address data with BAPI_CUSTOMER_GETDETAIL2. Sales areas use the API route."""
    function = "BAPI_CUSTOMER_GETDETAIL2"
    try:
        number = sap_key(customer, "customer", 10, numeric_length=10)
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, {"CUSTOMERNO": number})
