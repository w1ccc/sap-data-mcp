"""Standard FI BAPI reads through the existing cached RFC provider."""
from typing import Any
from core.app import READ_ONLY, mcp, read_bapi, sap_key, sap_date, validation_error


@mcp.tool(annotations=READ_ONLY)
async def search_company_codes(max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """List standard company codes; page the returned table locally."""
    function = 'BAPI_COMPANYCODE_GETLIST'
    try:
        params = {}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_company_code(company_code: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read a company code and its native address/detail structures."""
    function = 'BAPI_COMPANYCODE_GETDETAIL'
    try:
        params = {"COMPANYCODEID": sap_key(company_code, "company_code", 4)}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_bank(bank_country: str, bank_key: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read a bank by country AND bank key."""
    function = 'BAPI_BANK_GETDETAIL'
    try:
        params = {"BANKCOUNTRY": sap_key(bank_country, "bank_country", 3), "BANKKEY": sap_key(bank_key, "bank_key", 15)}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def search_fixed_assets(company_code: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Search fixed-asset master records within a company code; returned tables page locally."""
    function = 'BAPI_FIXEDASSET_GETLIST'
    try:
        params = {"COMPANYCODE": sap_key(company_code, "company_code", 4),
                  "REQUESTEDTABLESX": {"GENERALDATA": "X"}}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def search_fixed_asset_values(company_code: str, depreciation_area: str, evaluation_date: str,
                                    max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read SAP selected asset values for a company and depreciation area. DEPRECIATIONAREAVALS retains asset/subnumber, area, fiscal year, currency, year-end APC/net book value and planned depreciation separately. The returned FISC_YEAR identifies the values' year; evaluation_date does not promise a daily posted balance."""
    function = "BAPI_FIXEDASSET_GETLIST"
    try:
        area = sap_key(depreciation_area, "depreciation_area", 2, numeric_length=2)
        if not area.isdigit():
            raise ValueError("depreciation_area must be numeric.")
        params = {"COMPANYCODE": sap_key(company_code, "company_code", 4),
                  "DEPRECIATIONAREA": area, "EVALUATIONDATE": sap_date(evaluation_date, "evaluation_date"),
                  "REQUESTEDTABLESX": {"DEPRECIATIONAREAVALS": "X"}}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_fixed_asset_values(company_code: str, master_fixed_asset: str, fixed_asset: str,
                                 depreciation_area: str, evaluation_date: str, max_results: int = 100,
                                 offset: int = 0) -> dict[str, Any]:
    """Read SAP selected asset values for the complete company/main-asset/subnumber/area key. Preserves fiscal year and currency, year-end book value and planned amounts with their original field names; not a daily posted-value snapshot."""
    function = "BAPI_FIXEDASSET_GETLIST"
    try:
        area = sap_key(depreciation_area, "depreciation_area", 2, numeric_length=2)
        if not area.isdigit():
            raise ValueError("depreciation_area must be numeric.")
        params = {"COMPANYCODE": sap_key(company_code, "company_code", 4),
                  "DEPRECIATIONAREA": area, "EVALUATIONDATE": sap_date(evaluation_date, "evaluation_date"),
                  "REQUESTEDTABLESX": {"DEPRECIATIONAREAVALS": "X"},
                  "SELECTIONCRITERIA": [
                      {"PARAMETER": "GENERALDATA", "FIELD": field, "SIGN": "I", "OPTION": "EQ", "LOW": value}
                      for field, value in (("ASSET", sap_key(master_fixed_asset, "master_fixed_asset", 12, numeric_length=12)),
                                           ("SUBNUMBER", sap_key(fixed_asset, "fixed_asset", 4, numeric_length=4)))]}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_gl_account_period_balances(company_code: str, gl_account: str, fiscal_year: str,
                                          currency_type: str = "10", max_results: int = 100,
                                          offset: int = 0) -> dict[str, Any]:
    """Read SAP fiscal-period GL balances and carryforward in currency type 00 (transaction) or 10 (company code). This classic BAPI has no ledger, business-area or daily breakdown; use the API balance tool for ledger-specific reads."""
    function = "BAPI_GL_GETGLACCPERIODBALANCES"
    try:
        year = sap_key(fiscal_year, "fiscal_year", 4)
        if len(year) != 4 or not year.isdigit():
            raise ValueError("fiscal_year must have four digits.")
        if currency_type not in {"00", "10"}:
            raise ValueError("currency_type must be 00 or 10.")
        params = {"COMPANYCODE": sap_key(company_code, "company_code", 4),
                  "GLACCT": sap_key(gl_account, "gl_account", 10, numeric_length=10),
                  "FISCALYEAR": year, "CURRENCYTYPE": currency_type}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_fixed_asset(company_code: str, master_fixed_asset: str, fixed_asset: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read fixed-asset master/depreciation-area terms by complete company, main-asset and subnumber key. Not posted book values."""
    function = 'BAPI_FIXEDASSET_GETDETAIL'
    try:
        params = {"COMPANYCODE": sap_key(company_code, "company_code", 4), "ASSET": sap_key(master_fixed_asset, "master_fixed_asset", 12, numeric_length=12), "SUBNUMBER": sap_key(fixed_asset, "fixed_asset", 4, numeric_length=4)}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def search_customer_open_items(company_code: str, customer: str, key_date: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read customer items open at a specified key date. Native clearing references and amount/currency fields are retained."""
    function = 'BAPI_AR_ACC_GETOPENITEMS'
    try:
        params = {"COMPANYCODE": sap_key(company_code, "company_code", 4), 'CUSTOMER': sap_key(customer, 'customer', 10, numeric_length=10), "KEYDATE": sap_date(key_date, "key_date")}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def search_customer_account_items(company_code: str, customer: str, date_from: str, date_to: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read customer account statement items over a date range, including open and cleared items. Clearing is not proof of actual payment."""
    function = 'BAPI_AR_ACC_GETSTATEMENT'
    try:
        start, end = sap_date(date_from, "date_from"), sap_date(date_to, "date_to")
        if start > end: raise ValueError("date_from must not follow date_to.")
        params = {"COMPANYCODE": sap_key(company_code, "company_code", 4), 'CUSTOMER': sap_key(customer, 'customer', 10, numeric_length=10), "DATE_FROM": start, "DATE_TO": end}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_customer_account_balance(company_code: str, customer: str, key_date: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read SAP-calculated customer key-date balances, retaining currency and special-GL dimensions."""
    function = 'BAPI_AR_ACC_GETKEYDATEBALANCE'
    try:
        params = {"COMPANYCODE": sap_key(company_code, "company_code", 4), 'CUSTOMER': sap_key(customer, 'customer', 10, numeric_length=10), "KEYDATE": sap_date(key_date, "key_date"), "BALANCESPGLI": "X"}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def search_supplier_open_items(company_code: str, supplier: str, key_date: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read supplier items open at a specified key date. Native clearing references and amount/currency fields are retained."""
    function = 'BAPI_AP_ACC_GETOPENITEMS'
    try:
        params = {"COMPANYCODE": sap_key(company_code, "company_code", 4), 'VENDOR': sap_key(supplier, 'supplier', 10, numeric_length=10), "KEYDATE": sap_date(key_date, "key_date")}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def search_supplier_account_items(company_code: str, supplier: str, date_from: str, date_to: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read supplier account statement items over a date range, including open and cleared items. Clearing is not proof of actual payment."""
    function = 'BAPI_AP_ACC_GETSTATEMENT'
    try:
        start, end = sap_date(date_from, "date_from"), sap_date(date_to, "date_to")
        if start > end: raise ValueError("date_from must not follow date_to.")
        params = {"COMPANYCODE": sap_key(company_code, "company_code", 4), 'VENDOR': sap_key(supplier, 'supplier', 10, numeric_length=10), "DATE_FROM": start, "DATE_TO": end}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)


@mcp.tool(annotations=READ_ONLY)
async def get_supplier_account_balance(company_code: str, supplier: str, key_date: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
    """Read SAP-calculated supplier key-date balances, retaining currency and special-GL dimensions."""
    function = 'BAPI_AP_ACC_GETKEYDATEBALANCE'
    try:
        params = {"COMPANYCODE": sap_key(company_code, "company_code", 4), 'VENDOR': sap_key(supplier, 'supplier', 10, numeric_length=10), "KEYDATE": sap_date(key_date, "key_date"), "BALANCESPGLI": "X"}
    except ValueError as error:
        return validation_error(function, str(error))
    return read_bapi(function, params, max_results, offset)

