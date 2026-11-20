"""Business partner and supplier tools (BAPI_BUPA_*, BAPI_VENDOR_GETDETAIL)."""

from typing import Any

from core.app import (
    READ_ONLY,
    call_rfc,
    clamp,
    compact,
    connection_unavailable,
    has_error,
    json_safe,
    mcp,
    org_unit,
    page,
    return_messages,
    rfc_error_result,
    sap_key,
    sap_rfc,
    validation_error,
)


def _partner_number(value: str, name: str) -> str:
    return sap_key(value, name, 10, numeric_length=10)


def _partner_name(details: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return the BP category and display name from BAPI_BUPA_CENTRAL_GETDETAIL."""
    organization = details.get("CENTRALDATAORGANIZATION") or {}
    person = details.get("CENTRALDATAPERSON") or {}
    group = details.get("CENTRALDATAGROUP") or {}
    if organization.get("NAME1"):
        names = (organization.get(f"NAME{index}") for index in range(1, 5))
        return "organization", " ".join(name for name in names if name)
    if person.get("FULLNAME") or person.get("LASTNAME"):
        name = person.get("FULLNAME") or " ".join(
            part for part in (person.get("FIRSTNAME"), person.get("LASTNAME")) if part
        )
        return "person", name
    if group.get("NAMEGROUP1"):
        return "group", " ".join(part for part in (group.get("NAMEGROUP1"), group.get("NAMEGROUP2")) if part)
    return None, None


def _tagged(messages: list[dict[str, Any]], function: str) -> list[dict[str, Any]]:
    return [{"function": function, **message} for message in messages]


@mcp.tool(annotations=READ_ONLY)
async def search_business_partners(
    name: str = "",
    city: str = "",
    postal_code: str = "",
    country: str = "",
    role: str = "",
    email: str = "",
    telephone: str = "",
    max_results: int = 20,
) -> dict[str, Any]:
    """Search business partners (suppliers, customers, ...) with BAPI_BUPA_SEARCH_2.

    name matches the partner name case-insensitively; without * it is searched as
    *name*. role narrows to one BP role, e.g. FLVN00/FLVN01 (supplier) or FLCU00/FLCU01
    (customer). country is the ISO/SAP country key. Each hit gets its name and category
    from BAPI_BUPA_CENTRAL_GETDETAIL. max_results: 1-50.
    """
    functions = ["BAPI_BUPA_SEARCH_2", "BAPI_BUPA_CENTRAL_GETDETAIL"]
    if not sap_rfc.is_connected:
        return connection_unavailable(functions)

    pattern = name.strip().upper()
    if pattern and "*" not in pattern:
        pattern = f"*{pattern}*"
    try:
        role = org_unit(role, "role", 6)
        country = org_unit(country, "country", 3)
    except ValueError as error:
        return validation_error(functions, str(error))
    if len(pattern) > 35:
        return validation_error(functions, "name may have at most 35 characters.")
    address = {
        field: value
        for field, value in (
            ("CITY1", city.strip().upper()),
            ("POSTL_COD1", postal_code.strip().upper()),
            ("COUNTRY", country),
        )
        if value
    }
    if not (pattern or address or email.strip() or telephone.strip()):
        return validation_error(functions, "Provide name, an address field, email or telephone.")
    limit = clamp(max_results, 1, 50)

    params: dict[str, Any] = {"OTHERS": {"MAXSEL": limit + 1}}
    if pattern:
        params["CENTRALDATA"] = {"MC_NAME1": pattern}
    if address:
        params["ADDRESSDATA"] = address
    if role:
        params["BUSINESSPARTNERROLE"] = role
    if email.strip():
        params["EMAIL"] = email.strip()
    if telephone.strip():
        params["TELEPHONE"] = telephone.strip()

    try:
        response = call_rfc("BAPI_BUPA_SEARCH_2", **params)
    except Exception as error:
        return rfc_error_result(error, function=functions)

    messages = return_messages(response.get("RETURN"))
    partners = list(dict.fromkeys(row["PARTNER"] for row in response.get("SEARCHRESULT") or [] if row.get("PARTNER")))
    # MAXSEL may cap the hits in SAP, so the number found is no reliable total.
    selected, paging = page(partners, limit, exact_total=False)

    hits = []
    for partner in selected:
        try:
            details = call_rfc("BAPI_BUPA_CENTRAL_GETDETAIL", BUSINESSPARTNER=partner)
        except Exception as error:
            hits.append({"business_partner": partner, "error_message": rfc_error_result(error)["error_message"]})
            continue
        category, display_name = _partner_name(details)
        central = details.get("CENTRALDATA") or {}
        hits.append(
            compact(
                {
                    "business_partner": partner,
                    "name": display_name,
                    "category": category,
                    "search_term": central.get("SEARCHTERM1"),
                    "grouping": central.get("PARTNERTYPE"),
                    "central_block": central.get("CENTRALBLOCK"),
                }
            )
        )

    if has_error(messages):
        status = "error"
    else:
        status = "ok" if hits else "not_found"
    return json_safe(
        {
            "status": status,
            "connection": "RFC",
            "function": functions,
            **paging,
            "business_partners": hits,
            "return_messages": messages,
        }
    )


@mcp.tool(annotations=READ_ONLY)
async def get_business_partner(business_partner: str, include_bank_details: bool = False) -> dict[str, Any]:
    """Read one business partner: central data, roles, standard address, communication, tax numbers.

    Uses BAPI_BUPA_CENTRAL_GETDETAIL, BAPI_BUPA_ROLES_GET_2, BAPI_BUPA_ADDRESS_GETDETAIL
    and BAPI_BUPA_TAX_GETDETAILS; bank details (BAPI_BUPA_BANKDETAILS_GET) only when
    include_bank_details is true. Numeric BP numbers may omit leading zeros.
    """
    functions = [
        "BAPI_BUPA_CENTRAL_GETDETAIL",
        "BAPI_BUPA_ROLES_GET_2",
        "BAPI_BUPA_ADDRESS_GETDETAIL",
        "BAPI_BUPA_TAX_GETDETAILS",
    ]
    if include_bank_details:
        functions.append("BAPI_BUPA_BANKDETAILS_GET")
    if not sap_rfc.is_connected:
        return connection_unavailable(functions)
    try:
        partner = _partner_number(business_partner, "business_partner")
    except ValueError as error:
        return validation_error(functions, str(error))

    try:
        central = call_rfc("BAPI_BUPA_CENTRAL_GETDETAIL", BUSINESSPARTNER=partner)
    except Exception as error:
        return rfc_error_result(error, function=functions, business_partner=partner)
    messages = _tagged(return_messages(central.get("RETURN")), "BAPI_BUPA_CENTRAL_GETDETAIL")
    category, display_name = _partner_name(central)
    central_data = compact(central.get("CENTRALDATA") or {})
    if category is None and not central_data:
        return json_safe(
            {
                "status": "not_found",
                "connection": "RFC",
                "function": functions,
                "business_partner": partner,
                "return_messages": messages,
            }
        )

    try:
        roles = call_rfc("BAPI_BUPA_ROLES_GET_2", BUSINESSPARTNER=partner)
        address = call_rfc("BAPI_BUPA_ADDRESS_GETDETAIL", BUSINESSPARTNER=partner)
        tax = call_rfc("BAPI_BUPA_TAX_GETDETAILS", BUSINESSPARTNER=partner)
        bank = call_rfc("BAPI_BUPA_BANKDETAILS_GET", BUSINESSPARTNER=partner) if include_bank_details else {}
    except Exception as error:
        return rfc_error_result(error, function=functions, business_partner=partner)
    for function, response in (
        ("BAPI_BUPA_ROLES_GET_2", roles),
        ("BAPI_BUPA_ADDRESS_GETDETAIL", address),
        ("BAPI_BUPA_TAX_GETDETAILS", tax),
        ("BAPI_BUPA_BANKDETAILS_GET", bank),
    ):
        messages += _tagged(return_messages(response.get("RETURN")), function)

    sections = {
        "central_data": central_data,
        "organization": compact(central.get("CENTRALDATAORGANIZATION") or {}),
        "person": compact(central.get("CENTRALDATAPERSON") or {}),
        "group": compact(central.get("CENTRALDATAGROUP") or {}),
        "validity": compact(central.get("CENTRALDATAVALIDITY") or {}),
        "roles": compact(roles.get("BUSINESSPARTNERROLES") or []),
        "address": compact(address.get("ADDRESSDATA") or {}),
        "emails": compact((address.get("BAPIADSMTP") or []) + (central.get("E_MAILDATANONADDRESS") or [])),
        "telephones": compact((address.get("BAPIADTEL") or []) + (central.get("TELEFONDATANONADDRESS") or [])),
        "fax_numbers": compact((address.get("BAPIADFAX") or []) + (central.get("FAXDATANONADDRESS") or [])),
        "tax_numbers": compact(tax.get("TAXDETAILS") or []),
    }
    result: dict[str, Any] = {
        "status": "ok",
        "connection": "RFC",
        "function": functions,
        "business_partner": partner,
        "name": display_name,
        "category": category,
        **{key: value for key, value in sections.items() if value},
    }
    if include_bank_details:
        result["bank_details"] = compact(bank.get("BANKDETAILS") or [])
    result["return_messages"] = messages
    return json_safe(result)


@mcp.tool(annotations=READ_ONLY)
async def get_supplier(supplier: str, company_code: str = "", include_bank_details: bool = False) -> dict[str, Any]:
    """Read supplier (vendor) master data with BAPI_VENDOR_GETDETAIL.

    Returns general data; company_code adds company code data such as payment terms and
    clerk. In S/4HANA the supplier is a business partner with a supplier role; use
    get_business_partner for roles, address details and tax numbers.
    """
    function = "BAPI_VENDOR_GETDETAIL"
    if not sap_rfc.is_connected:
        return connection_unavailable(function)
    try:
        vendor = _partner_number(supplier, "supplier")
        company_code = org_unit(company_code, "company_code", 4)
    except ValueError as error:
        return validation_error(function, str(error))

    params: dict[str, Any] = {"VENDORNO": vendor}
    if company_code:
        params["COMPANYCODE"] = company_code
    try:
        response = call_rfc(function, **params)
    except Exception as error:
        return rfc_error_result(error, function=function, supplier=vendor)

    messages = return_messages(response.get("RETURN"))
    general = compact(response.get("GENERALDETAIL") or {})
    if not general.get("VENDOR"):
        return json_safe(
            {
                "status": "not_found",
                "connection": "RFC",
                "function": function,
                "supplier": vendor,
                "return_messages": messages,
            }
        )

    result: dict[str, Any] = {
        "status": "partial" if has_error(messages) else "ok",
        "connection": "RFC",
        "function": function,
        "supplier": vendor,
        "general_data": general,
    }
    if company_code:
        result["company_code_data"] = compact(response.get("COMPANYDETAIL") or {})
    if include_bank_details:
        result["bank_details"] = compact(response.get("BANKDETAIL") or [])
        result["iban_details"] = compact(response.get("VENDORIBANDETAIL") or [])
    result["return_messages"] = messages
    return json_safe(result)
