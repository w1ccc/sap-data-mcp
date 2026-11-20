"""Standard MDG read-only tools; native SAP data and keys are retained."""
from typing import Any
from shared.odata import eq, key

def register(read_tool, client, record):

    if not client.public:
        @read_tool
        async def search_mdg_my_change_requests(max_results: int = 100, offset: int = 0) -> dict[str, Any]:
            """Read Track My Requests metadata for the authenticated user from private MDG_MYCR_SRV. Retains SAP request identifiers, status and other supplied fields; not an all-users governance search or staging read. Requires the MDG component and SAP_MDG_MY_REQ_APP authorization. Public Cloud does not expose this Fiori service here."""
            result = await client.rows("mdg_my_change_request", "ChangeRequests", [], max_results, offset)
            result["data_state"] = "change_request_metadata"
            result["scope"] = "authenticated_user_requests"
            return result

    @read_tool
    async def search_business_partners(name: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search activated BP master records by name prefix. Returns active master data, not MDG change-request staging data."""
        value = key(name, "name", 220).replace("'", "''")
        return await client.rows("business_partner", "A_BusinessPartner", [f"startswith(BusinessPartnerFullName,'{value}')"], max_results, offset)

    @read_tool
    async def get_business_partner(business_partner: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read activated BP general data, roles, addresses, banks, tax and external identifications. Each view pages independently. This is not MDG staging, key mapping or replication status."""
        filters = [eq("BusinessPartner", key(business_partner, "business_partner", 10))]
        result = await record("business_partner", filters, [('roles', 'A_BusinessPartnerRole', filters), ('addresses', 'A_BusinessPartnerAddress', filters), ('banks', 'A_BusinessPartnerBank', filters), ('tax_numbers', 'A_BusinessPartnerTaxNumber', filters), ('identifications', 'A_BuPaIdentification', filters)], max_results, offset)
        result["data_state"] = "active"
        return result

    @read_tool
    async def get_supplier_organization_data(supplier: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read activated supplier company-code and purchasing-organization data without changing existing MM supplier tool fields. Native organizational keys are retained."""
        filters = [eq("Supplier", key(supplier, "supplier", 10))]
        result = await record("supplier_organization", filters, [("company_codes", "A_SupplierCompany", filters), ("purchasing_organizations", "A_SupplierPurchasingOrg", filters)], max_results, offset)
        result["data_state"] = "active"
        return result
