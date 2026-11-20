"""Material master tools (BAPI_MATERIAL_GETLIST, BAPI_MATERIAL_GET_ALL)."""

from typing import Any

from core.app import (
    READ_ONLY,
    call_rfc,
    clamp,
    compact,
    connection_unavailable,
    has_error,
    json_safe,
    material_number,
    mcp,
    org_unit,
    page,
    return_messages,
    rfc_error_result,
    sap_rfc,
    validation_error,
)


@mcp.tool(annotations=READ_ONLY)
async def search_materials(
    description: str = "",
    material: str = "",
    plant: str = "",
    max_results: int = 50,
) -> dict[str, Any]:
    """Search materials by description and/or material number with BAPI_MATERIAL_GETLIST.

    description matches the short text case-insensitively; without * it is searched as
    *text*. material is an exact number or a pattern with * such as "2024010*"; numeric
    patterns get a leading * because SAP stores numeric material numbers with leading
    zeros. plant keeps only materials maintained in that plant. max_results: 1-500.
    """
    function = "BAPI_MATERIAL_GETLIST"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)

    text = description.strip()
    if text and "*" not in text:
        text = f"*{text}*"
    try:
        plant = org_unit(plant, "plant", 4)
        pattern = material.strip().upper()
        if pattern and "*" not in pattern:
            pattern = material_number(pattern)
        elif pattern[:1].isdigit():
            pattern = f"*{pattern}"
    except ValueError as error:
        return validation_error(function, str(error))
    if not text and not pattern:
        return validation_error(function, "Provide description and/or material.")
    if len(text) > 40 or len(pattern) > 40:
        return validation_error(function, "description and material may have at most 40 characters.")
    limit = clamp(max_results, 1, 500)

    params: dict[str, Any] = {"MAXROWS": limit + 1}
    if pattern:
        option = "CP" if "*" in pattern else "EQ"
        params["MATNRSELECTION"] = [{"SIGN": "I", "OPTION": option, "MATNR_LOW_LONG": pattern}]
    if text:
        params["MATERIALSHORTDESCSEL"] = [{"SIGN": "I", "OPTION": "CP", "DESCR_LOW": text}]
    if plant:
        params["PLANTSELECTION"] = [{"SIGN": "I", "OPTION": "EQ", "PLANT_LOW": plant}]

    try:
        response = call_rfc(function, **params)
    except Exception as error:
        return rfc_error_result(error, function=function)

    messages = return_messages(response.get("RETURN"))
    materials = [
        {
            "material": row.get("MATERIAL_LONG") or row.get("MATERIAL"),
            "description": row.get("MATL_DESC"),
        }
        for row in response.get("MATNRLIST") or []
    ]
    # MAXROWS = limit + 1 caps the list in SAP, so only truncation is known.
    rows, paging = page(materials, limit, exact_total=False)
    if has_error(messages):
        status = "error"
    else:
        status = "ok" if rows else "not_found"
    return json_safe(
        {
            "status": status,
            "connection": "RFC",
            "function": function,
            **paging,
            "materials": rows,
            "return_messages": messages,
        }
    )


@mcp.tool(annotations=READ_ONLY)
async def get_material(
    material: str,
    plant: str = "",
    storage_location: str = "",
    valuation_area: str = "",
    sales_org: str = "",
    distribution_channel: str = "",
    include_long_texts: bool = False,
) -> dict[str, Any]:
    """Read material master data with BAPI_MATERIAL_GET_ALL; empty fields are omitted.

    Basic data, descriptions and units of measure are always returned. The plant view
    needs plant, the storage location view needs plant + storage_location, the valuation
    view uses valuation_area (defaults to the plant) and the sales view needs sales_org +
    distribution_channel. Numeric material numbers may be given without leading zeros.
    """
    function = "BAPI_MATERIAL_GET_ALL"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)

    try:
        number = material_number(material)
        plant = org_unit(plant, "plant", 4)
        storage_location = org_unit(storage_location, "storage_location", 4)
        valuation_area = org_unit(valuation_area, "valuation_area", 4) or plant
        sales_org = org_unit(sales_org, "sales_org", 4)
        distribution_channel = org_unit(distribution_channel, "distribution_channel", 2)
    except ValueError as error:
        return validation_error(function, str(error))
    if storage_location and not plant:
        return validation_error(function, "storage_location requires plant.")
    if bool(sales_org) != bool(distribution_channel):
        return validation_error(function, "sales_org and distribution_channel must be given together.")

    params: dict[str, Any] = {"MATERIAL_LONG": number}
    if plant:
        params["PLANT"] = plant
    if storage_location:
        params["STGE_LOC"] = storage_location
    if valuation_area:
        params["VAL_AREA"] = valuation_area
    if sales_org:
        params["SALESORG"] = sales_org
        params["DISTR_CHAN"] = distribution_channel

    try:
        response = call_rfc(function, **params)
    except Exception as error:
        return rfc_error_result(error, function=function, material=number)

    messages = return_messages(response.get("RETURN"))
    basic_data = compact(response.get("CLIENTDATA") or {})
    if not basic_data.get("MATERIAL_LONG") and not basic_data.get("MATERIAL"):
        return json_safe(
            {
                "status": "not_found",
                "connection": "RFC",
                "function": function,
                "material": number,
                "return_messages": messages,
            }
        )

    result: dict[str, Any] = {
        "status": "partial" if has_error(messages) else "ok",
        "connection": "RFC",
        "function": function,
        "material": number,
        "basic_data": basic_data,
        "descriptions": [
            {"language": row.get("LANGU_ISO") or row.get("LANGU"), "description": row.get("MATL_DESC")}
            for row in response.get("MATERIALDESCRIPTION") or []
        ],
        "units_of_measure": compact(response.get("UNITSOFMEASURE") or []),
        "international_article_numbers": compact(response.get("INTERNATIONALARTNOS") or []),
        "tax_classifications": compact(response.get("TAXCLASSIFICATIONS") or []),
    }
    if plant:
        result["plant_data"] = compact(response.get("PLANTDATA") or {})
    if storage_location:
        result["storage_location_data"] = compact(response.get("STORAGELOCATIONDATA") or {})
    if valuation_area:
        result["valuation_data"] = compact(response.get("VALUATIONDATA") or {})
    if sales_org:
        result["sales_data"] = compact(response.get("SALESDATA") or {})
    if include_long_texts:
        result["long_texts"] = compact(response.get("MATERIALLONGTEXT") or [])
    result["return_messages"] = messages
    return json_safe(result)
