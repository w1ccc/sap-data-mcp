"""Standard CO read-only tools; native SAP data and keys are retained."""
from typing import Any
from shared.odata import eq, key, typed_eq

def register(read_tool, client, record):

    @read_tool
    async def search_controlling_areas(controlling_area: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for controlling area. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ControllingArea', key(controlling_area, 'controlling_area', 4), 'Edm.String', client.is_v4('controlling_area'))]
        return await client.rows('controlling_area', 'A_ControllingArea', filters, max_results, offset)

    @read_tool
    async def get_controlling_area(controlling_area: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of controlling area. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ControllingArea', key(controlling_area, 'controlling_area', 4), 'Edm.String', client.is_v4('controlling_area'))]
        return await record('controlling_area', filters, [], max_results, offset)

    @read_tool
    async def search_cost_centers(controlling_area: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for cost center. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ControllingArea', key(controlling_area, 'controlling_area', 4), 'Edm.String', client.is_v4('cost_center'))]
        return await client.rows('cost_center', 'A_CostCenter', filters, max_results, offset)

    @read_tool
    async def get_cost_center(controlling_area: str, cost_center: str, validity_end_date: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of cost center. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ControllingArea', key(controlling_area, 'controlling_area', 4), 'Edm.String', client.is_v4('cost_center')), typed_eq('CostCenter', key(cost_center, 'cost_center', 10), 'Edm.String', client.is_v4('cost_center')), typed_eq('ValidityEndDate', key(validity_end_date, 'validity_end_date', 10), 'Edm.DateTime', client.is_v4('cost_center'))]
        return await record('cost_center', filters, [('texts', 'A_CostCenterText', [typed_eq('ControllingArea', key(controlling_area, 'controlling_area', 80), 'Edm.String', client.is_v4('cost_center')), typed_eq('CostCenter', key(cost_center, 'cost_center', 80), 'Edm.String', client.is_v4('cost_center')), typed_eq('ValidityEndDate', key(validity_end_date, 'validity_end_date', 80), 'Edm.DateTime', client.is_v4('cost_center'))])], max_results, offset)

    @read_tool
    async def search_profit_centers(controlling_area: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for profit center. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ControllingArea', key(controlling_area, 'controlling_area', 4), 'Edm.String', client.is_v4('profit_center'))]
        return await client.rows('profit_center', 'A_ProfitCenter', filters, max_results, offset)

    @read_tool
    async def get_profit_center(controlling_area: str, profit_center: str, validity_end_date: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of profit center. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ControllingArea', key(controlling_area, 'controlling_area', 4), 'Edm.String', client.is_v4('profit_center')), typed_eq('ProfitCenter', key(profit_center, 'profit_center', 10), 'Edm.String', client.is_v4('profit_center')), typed_eq('ValidityEndDate', key(validity_end_date, 'validity_end_date', 10), 'Edm.DateTime', client.is_v4('profit_center'))]
        return await record('profit_center', filters, [('texts', 'A_ProfitCenterText', [typed_eq('ControllingArea', key(controlling_area, 'controlling_area', 80), 'Edm.String', client.is_v4('profit_center')), typed_eq('ProfitCenter', key(profit_center, 'profit_center', 80), 'Edm.String', client.is_v4('profit_center')), typed_eq('ValidityEndDate', key(validity_end_date, 'validity_end_date', 80), 'Edm.DateTime', client.is_v4('profit_center'))])], max_results, offset)

    @read_tool
    async def search_activity_types(controlling_area: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for activity type. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ControllingArea', key(controlling_area, 'controlling_area', 4), 'Edm.String', client.is_v4('activity_type'))]
        return await client.rows('activity_type', 'A_CostCenterActivityType', filters, max_results, offset)

    @read_tool
    async def get_activity_type(controlling_area: str, activity_type: str, validity_end_date: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of activity type. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ControllingArea', key(controlling_area, 'controlling_area', 4), 'Edm.String', client.is_v4('activity_type')), typed_eq('CostCtrActivityType', key(activity_type, 'activity_type', 6), 'Edm.String', client.is_v4('activity_type')), typed_eq('ValidityEndDate', key(validity_end_date, 'validity_end_date', 10), 'Edm.DateTime', client.is_v4('activity_type'))]
        return await record('activity_type', filters, [('texts', 'A_CostCenterActivityTypeText', [typed_eq('ControllingArea', key(controlling_area, 'controlling_area', 80), 'Edm.String', client.is_v4('activity_type')), typed_eq('CostCtrActivityType', key(activity_type, 'activity_type', 80), 'Edm.String', client.is_v4('activity_type')), typed_eq('ValidityEndDate', key(validity_end_date, 'validity_end_date', 80), 'Edm.DateTime', client.is_v4('activity_type'))])], max_results, offset)

    @read_tool
    async def search_statistical_key_figures(controlling_area: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for statistical key figure. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ControllingArea', key(controlling_area, 'controlling_area', 4), 'Edm.String', client.is_v4('statistical_key_figure'))]
        return await client.rows('statistical_key_figure', 'A_StatisticalKeyFigure', filters, max_results, offset)

    @read_tool
    async def get_statistical_key_figure(controlling_area: str, statistical_key_figure: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of statistical key figure. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ControllingArea', key(controlling_area, 'controlling_area', 4), 'Edm.String', client.is_v4('statistical_key_figure')), typed_eq('StatisticalKeyFigure', key(statistical_key_figure, 'statistical_key_figure', 6), 'Edm.String', client.is_v4('statistical_key_figure'))]
        return await record('statistical_key_figure', filters, [('texts', 'A_StatisticalKeyFigureText', [typed_eq('ControllingArea', key(controlling_area, 'controlling_area', 80), 'Edm.String', client.is_v4('statistical_key_figure')), typed_eq('StatisticalKeyFigure', key(statistical_key_figure, 'statistical_key_figure', 80), 'Edm.String', client.is_v4('statistical_key_figure'))])], max_results, offset)

    @read_tool
    async def search_co_actual_balances(controlling_area: str, ledger: str, fiscal_year: str, cost_center: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read SAP financial actual amounts for one controlling area, ledger, year and cost center. Retains period, account and currency dimensions; pages are not locally summed or presented as document-level items."""
        filters = [eq("ControllingArea", key(controlling_area, "controlling_area", 4)), eq("Ledger", key(ledger, "ledger", 2)), eq("LedgerFiscalYear", key(fiscal_year, "fiscal_year", 4)), eq("CostCenter", key(cost_center, "cost_center", 10))]
        return await client.rows('co_actual_balance', 'A_JournalEntryItemBasic', filters, max_results, offset)

    @read_tool
    async def search_co_plan_balances(controlling_area: str, ledger: str, fiscal_year: str, cost_center: str, planning_category: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read SAP financial plan amounts for one controlling area, ledger, year and cost center. Retains period, account and currency dimensions; pages are not locally summed or presented as document-level items."""
        filters = [eq("ControllingArea", key(controlling_area, "controlling_area", 4)), eq("Ledger", key(ledger, "ledger", 2)), eq("LedgerFiscalYear", key(fiscal_year, "fiscal_year", 4)), eq("CostCenter", key(cost_center, "cost_center", 10))]
        filters.append(eq("PlanningCategory", key(planning_category, "planning_category", 10)))
        return await client.rows('co_plan_balance', 'A_FinPlanningEntryItem', filters, max_results, offset)

    @read_tool
    async def search_actual_cost_items(company_code: str, controlling_area: str, ledger: str, fiscal_year: str,
                                       cost_center: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read Universal Journal actual cost items for one company, controlling area, ledger, year and cost center. Explicit document keys prevent an aggregated balance response."""
        filters = [eq("CompanyCode", key(company_code, "company_code", 4)), eq("ControllingArea", key(controlling_area, "controlling_area", 4)),
                   eq("Ledger", key(ledger, "ledger", 2)), eq("LedgerFiscalYear", key(fiscal_year, "fiscal_year", 4)),
                   eq("CostCenter", key(cost_center, "cost_center", 10))]
        return await client.rows("gl_line_item", "GLAccountLineItem", filters, max_results, offset, select=(
            "*", "AccountingDocument", "CompanyCode", "FiscalYear", "Ledger", "LedgerGLLineItem", "SourceLedger",
            "ControllingArea", "CostCenter", "ProfitCenter", "GLAccount", "FiscalYearPeriod",
            "AmountInCompanyCodeCurrency", "CompanyCodeCurrency", "AmountInTransactionCurrency", "TransactionCurrency"))
