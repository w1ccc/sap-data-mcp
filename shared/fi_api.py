"""Standard FI read-only tools; native SAP data and keys are retained."""
from typing import Any
from shared.odata import eq, key, typed_eq

def register(read_tool, client, record):

    @read_tool
    async def search_company_codes(company_code: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for company code. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('CompanyCode', key(company_code, 'company_code', 4), 'Edm.String', client.is_v4('company_code'))]
        return await client.rows('company_code', 'A_CompanyCode', filters, max_results, offset)

    @read_tool
    async def get_company_code(company_code: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of company code. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('CompanyCode', key(company_code, 'company_code', 4), 'Edm.String', client.is_v4('company_code'))]
        return await record('company_code', filters, [], max_results, offset)

    @read_tool
    async def search_charts_of_accounts(chart_of_accounts: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for chart of accounts. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ChartOfAccounts', key(chart_of_accounts, 'chart_of_accounts', 4), 'Edm.String', client.is_v4('chart_of_accounts'))]
        return await client.rows('chart_of_accounts', 'A_ChartOfAccounts', filters, max_results, offset)

    @read_tool
    async def get_chart_of_accounts(chart_of_accounts: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of chart of accounts. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ChartOfAccounts', key(chart_of_accounts, 'chart_of_accounts', 4), 'Edm.String', client.is_v4('chart_of_accounts'))]
        return await record('chart_of_accounts', filters, [('texts', 'A_ChartOfAccountsText', [typed_eq('ChartOfAccounts', key(chart_of_accounts, 'chart_of_accounts', 80), 'Edm.String', client.is_v4('chart_of_accounts'))])], max_results, offset)

    @read_tool
    async def search_gl_accounts(chart_of_accounts: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for gl account. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ChartOfAccounts', key(chart_of_accounts, 'chart_of_accounts', 4), 'Edm.String', client.is_v4('gl_account'))]
        return await client.rows('gl_account', 'A_GLAccountInChartOfAccounts', filters, max_results, offset)

    @read_tool
    async def get_gl_account(chart_of_accounts: str, gl_account: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of gl account. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ChartOfAccounts', key(chart_of_accounts, 'chart_of_accounts', 4), 'Edm.String', client.is_v4('gl_account')), typed_eq('GLAccount', key(gl_account, 'gl_account', 10), 'Edm.String', client.is_v4('gl_account'))]
        return await record('gl_account', filters, [('texts', 'A_GLAccountText', filters)], max_results, offset)

    @read_tool
    async def search_banks(bank_country: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for bank. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('BankCountry', key(bank_country, 'bank_country', 3), 'Edm.String', client.is_v4('bank'))]
        return await client.rows('bank', 'Bank', filters, max_results, offset)

    @read_tool
    async def get_bank(bank_country: str, bank_key: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of bank. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('BankCountry', key(bank_country, 'bank_country', 3), 'Edm.String', client.is_v4('bank')), typed_eq('BankInternalID', key(bank_key, 'bank_key', 15), 'Edm.String', client.is_v4('bank'))]
        return await record('bank', filters, [], max_results, offset)

    @read_tool
    async def search_fixed_assets(company_code: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search fixed-asset master records in a company code, using the released master-data API, not the usage-object API."""
        return await client.rows("fixed_asset_master", "FixedAsset", [eq("CompanyCode", key(company_code, "company_code", 4))], max_results, offset)

    @read_tool
    async def get_fixed_asset(company_code: str, master_fixed_asset: str, fixed_asset: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read fixed-asset master by company, main number AND subnumber. Valuation master data describes depreciation terms, not posted book values."""
        filters = [eq("CompanyCode", key(company_code, "company_code", 4)), eq("MasterFixedAsset", key(master_fixed_asset, "master_fixed_asset", 12)), eq("FixedAsset", key(fixed_asset, "fixed_asset", 4))]
        return await record("fixed_asset_master", filters, [("valuation_master_data", "FixedAssetValuation", filters)], max_results, offset)

    @read_tool
    async def search_journal_entry_items(company_code: str, fiscal_year: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search operational accounting document items by company and fiscal year; preserve document/item keys, amounts/currencies and existing clearing references."""
        year = key(fiscal_year, "fiscal_year", 4)
        if len(year) != 4 or not year.isascii() or not year.isdigit(): raise ValueError("fiscal_year must have four digits.")
        return await client.rows("journal_entry", "A_OperationalAcctgDocItemCube", [eq("CompanyCode", key(company_code, "company_code", 4)), eq("FiscalYear", year)], max_results, offset)

    @read_tool
    async def get_journal_entry(company_code: str, fiscal_year: str, accounting_document: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read all paged operational line items of one journal entry by company, year AND document. Header attributes are returned in native line-item records."""
        filters = [eq("CompanyCode", key(company_code, "company_code", 4)), eq("FiscalYear", key(fiscal_year, "fiscal_year", 4)), eq("AccountingDocument", key(accounting_document, "accounting_document", 10))]
        return await client.rows("journal_entry", "A_OperationalAcctgDocItemCube", filters, max_results, offset)

    @read_tool
    async def get_journal_entry_item(company_code: str, fiscal_year: str, accounting_document: str, accounting_document_item: str) -> dict[str, Any]:
        """Read an accounting line item using all four entry-view keys; clearing references do not establish actual payment."""
        filters = [eq("CompanyCode", key(company_code, "company_code", 4)), eq("FiscalYear", key(fiscal_year, "fiscal_year", 4)), eq("AccountingDocument", key(accounting_document, "accounting_document", 10)), eq("AccountingDocumentItem", key(accounting_document_item, "accounting_document_item", 3))]
        return await record("journal_entry", filters)

    @read_tool
    async def search_customer_account_items(company_code: str, customer: str, fiscal_year: str, clearing_status: str = "all", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search customer open/cleared accounting items in one company/year. This is current SAP clearing status, not a historical key-date reconstruction or proof of payment."""
        if clearing_status not in {"all", "open", "cleared"}: raise ValueError("clearing_status must be all, open or cleared.")
        filters = [eq("CompanyCode", key(company_code, "company_code", 4)), eq('Customer', key(customer, 'customer', 10)), eq("FiscalYear", key(fiscal_year, "fiscal_year", 4))]
        if clearing_status != "all": filters.append("IsCleared eq " + ("true" if clearing_status == "cleared" else "false"))
        return await client.rows("journal_entry", "A_OperationalAcctgDocItemCube", filters, max_results, offset)

    @read_tool
    async def search_supplier_account_items(company_code: str, supplier: str, fiscal_year: str, clearing_status: str = "all", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search supplier open/cleared accounting items in one company/year. This is current SAP clearing status, not a historical key-date reconstruction or proof of payment."""
        if clearing_status not in {"all", "open", "cleared"}: raise ValueError("clearing_status must be all, open or cleared.")
        filters = [eq("CompanyCode", key(company_code, "company_code", 4)), eq('Supplier', key(supplier, 'supplier', 10)), eq("FiscalYear", key(fiscal_year, "fiscal_year", 4))]
        if clearing_status != "all": filters.append("IsCleared eq " + ("true" if clearing_status == "cleared" else "false"))
        return await client.rows("journal_entry", "A_OperationalAcctgDocItemCube", filters, max_results, offset)

    @read_tool
    async def get_gl_account_balances(company_code: str, ledger: str, gl_account: str, posting_date_from: str, posting_date_to: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read SAP trial balances in company-code currency for one ledger/account and period range. Uses server balances; never sums an incomplete page of transactions."""
        from datetime import date
        start, end = date.fromisoformat(posting_date_from), date.fromisoformat(posting_date_to)
        if not 0 <= (end - start).days <= 366: raise ValueError("Dates must be ordered and at most 366 days apart.")
        entity = f"C_TRIALBALANCE(P_FromPostingDate=datetime'{start.isoformat()}T00:00:00',P_ToPostingDate=datetime'{end.isoformat()}T00:00:00')/Results"
        filters = [eq("CompanyCode", key(company_code, "company_code", 4)), eq("Ledger", key(ledger, "ledger", 2)), eq("GLAccount", key(gl_account, "gl_account", 10))]
        return await client.rows("trial_balance", entity, filters, max_results, offset, select=("CompanyCode", "Ledger", "GLAccount", "CompanyCodeCurrency", "StartingBalanceAmtInCoCodeCrcy", "DebitAmountInCoCodeCrcy", "CreditAmountInCoCodeCrcy", "EndingBalanceAmtInCoCodeCrcy"))

    @read_tool
    async def search_gl_account_line_items(company_code: str, ledger: str, fiscal_year: str, gl_account: str,
                                           max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search Universal Journal line items for one company, ledger, year and GL account. Includes six accounting keys to retain line-item granularity."""
        filters = [eq("CompanyCode", key(company_code, "company_code", 4)), eq("Ledger", key(ledger, "ledger", 2)),
                   eq("LedgerFiscalYear", key(fiscal_year, "fiscal_year", 4)), eq("GLAccount", key(gl_account, "gl_account", 10))]
        return await client.rows("gl_line_item", "GLAccountLineItem", filters, max_results, offset, select=(
            "*", "AccountingDocument", "CompanyCode", "FiscalYear", "Ledger", "LedgerGLLineItem", "SourceLedger",
            "LedgerFiscalYear", "GLAccount", "CostCenter", "ProfitCenter", "FiscalYearPeriod",
            "AmountInCompanyCodeCurrency", "CompanyCodeCurrency", "AmountInTransactionCurrency", "TransactionCurrency"))

    @read_tool
    async def get_gl_account_line_item(company_code: str, fiscal_year: str, accounting_document: str,
                                       ledger: str, ledger_gl_line_item: str, source_ledger: str) -> dict[str, Any]:
        """Read a Universal Journal item with the full company/year/document/ledger/ledger-line/source-ledger identity. This line number differs from the entry-view item number."""
        filters = [eq("CompanyCode", key(company_code, "company_code", 4)), eq("FiscalYear", key(fiscal_year, "fiscal_year", 4)),
                   eq("AccountingDocument", key(accounting_document, "accounting_document", 10)), eq("Ledger", key(ledger, "ledger", 2)),
                   eq("LedgerGLLineItem", key(ledger_gl_line_item, "ledger_gl_line_item", 6)), eq("SourceLedger", key(source_ledger, "source_ledger", 2) if source_ledger.strip() else "")]
        return await record("gl_line_item", filters, select=(
            "*", "AccountingDocument", "CompanyCode", "FiscalYear", "Ledger", "LedgerGLLineItem", "SourceLedger",
            "GLAccount", "CostCenter", "ProfitCenter", "FiscalYearPeriod",
            "AmountInCompanyCodeCurrency", "CompanyCodeCurrency", "AmountInTransactionCurrency", "TransactionCurrency"))
