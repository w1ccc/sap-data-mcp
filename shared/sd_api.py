"""Standard sales reads. Native SAP fields and document references are retained."""
from typing import Any
from shared.odata import eq, key

def register(read_tool, client, record):

    @read_tool
    async def search_sales_inquiries(sales_org: str, sold_to_party: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search standard sales inquiries within one sales organization, optionally one exact sold-to party."""
        filters = [eq("SalesOrganization", key(sales_org, "sales_org", 4))]
        if sold_to_party.strip(): filters.append(eq("SoldToParty", key(sold_to_party, "sold_to_party", 10)))
        return await client.rows('sales_inquiry', 'A_SalesInquiry', filters, max_results, offset)

    @read_tool
    async def get_sales_inquiry(sales_inquiry: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read sales inquiry with independently paged items, partners, conditions and available schedule/document references. Native processing statuses are retained."""
        number = key(sales_inquiry, 'sales_inquiry', 10)
        return await record('sales_inquiry', [eq('SalesInquiry', number)], [('items', 'A_SalesInquiryItem', [eq('SalesInquiry', number)]), ('item_partners', 'A_SalesInquiryItemPartner', [eq('SalesInquiry', number)]), ('item_pricing_conditions', 'A_SalesInquiryItemPrcgElmnt', [eq('SalesInquiry', number)]), ('partners', 'A_SalesInquiryPartner', [eq('SalesInquiry', number)]), ('pricing_conditions', 'A_SalesInquiryPrcgElmnt', [eq('SalesInquiry', number)])], max_results, offset)

    @read_tool
    async def search_sales_quotations(sales_org: str, sold_to_party: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search standard sales quotations within one sales organization, optionally one exact sold-to party."""
        filters = [eq("SalesOrganization", key(sales_org, "sales_org", 4))]
        if sold_to_party.strip(): filters.append(eq("SoldToParty", key(sold_to_party, "sold_to_party", 10)))
        return await client.rows('sales_quotation', 'A_SalesQuotation', filters, max_results, offset)

    @read_tool
    async def get_sales_quotation(sales_quotation: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read sales quotation with independently paged items, partners, conditions and available schedule/document references. Native processing statuses are retained."""
        number = key(sales_quotation, 'sales_quotation', 10)
        return await record('sales_quotation', [eq('SalesQuotation', number)], [('items', 'A_SalesQuotationItem', [eq('SalesQuotation', number)]), ('item_partners', 'A_SalesQuotationItemPartner', [eq('SalesQuotation', number)]), ('item_pricing_conditions', 'A_SalesQuotationItemPrcgElmnt', [eq('SalesQuotation', number)]), ('partners', 'A_SalesQuotationPartner', [eq('SalesQuotation', number)]), ('pricing_conditions', 'A_SalesQuotationPrcgElmnt', [eq('SalesQuotation', number)])], max_results, offset)

    @read_tool
    async def search_sales_orders(sales_org: str, sold_to_party: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search standard sales orders within one sales organization, optionally one exact sold-to party."""
        filters = [eq("SalesOrganization", key(sales_org, "sales_org", 4))]
        if sold_to_party.strip(): filters.append(eq("SoldToParty", key(sold_to_party, "sold_to_party", 10)))
        return await client.rows('sales_order', 'A_SalesOrder', filters, max_results, offset)

    @read_tool
    async def get_sales_order(sales_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read sales order with independently paged items, partners, conditions and available schedule/document references. Native processing statuses are retained."""
        number = key(sales_order, 'sales_order', 10)
        return await record('sales_order', [eq('SalesOrder', number)], [('items', 'A_SalesOrderBillingPlanItem', [eq('SalesOrder', number)]), ('partners', 'A_SalesOrderHeaderPartner', [eq('SalesOrder', number)]), ('pricing_conditions', 'A_SalesOrderHeaderPrElement', [eq('SalesOrder', number)]), ('items', 'A_SalesOrderItem', [eq('SalesOrder', number)]), ('item_partners', 'A_SalesOrderItemPartner', [eq('SalesOrder', number)]), ('item_pricing_conditions', 'A_SalesOrderItemPrElement', [eq('SalesOrder', number)]), ('preceding_documents', 'A_SalesOrderPrecdgProcFlow', [eq('SalesOrder', number)]), ('schedule_lines', 'A_SalesOrderScheduleLine', [eq('SalesOrder', number)]), ('subsequent_documents', 'A_SalesOrderSubsqntProcFlow', [eq('SalesOrder', number)]), ('items', 'A_SlsOrderItemBillingPlanItem', [eq('SalesOrder', number)])], max_results, offset)

    @read_tool
    async def search_sales_contracts(sales_org: str, sold_to_party: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search standard sales contracts within one sales organization, optionally one exact sold-to party."""
        filters = [eq("SalesOrganization", key(sales_org, "sales_org", 4))]
        if sold_to_party.strip(): filters.append(eq("SoldToParty", key(sold_to_party, "sold_to_party", 10)))
        return await client.rows('sales_contract', 'A_SalesContract', filters, max_results, offset)

    @read_tool
    async def get_sales_contract(sales_contract: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read sales contract with independently paged items, partners, conditions and available schedule/document references. Native processing statuses are retained."""
        number = key(sales_contract, 'sales_contract', 10)
        return await record('sales_contract', [eq('SalesContract', number)], [('items', 'A_SalesContractItem', [eq('SalesContract', number)]), ('item_partners', 'A_SalesContractItemPartner', [eq('SalesContract', number)]), ('item_pricing_conditions', 'A_SalesContractItemPrcgElmnt', [eq('SalesContract', number)]), ('partners', 'A_SalesContractPartner', [eq('SalesContract', number)]), ('pricing_conditions', 'A_SalesContractPrcgElmnt', [eq('SalesContract', number)])], max_results, offset)

    @read_tool
    async def search_sales_scheduling_agreements(sales_org: str, sold_to_party: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search standard sales scheduling agreements within one sales organization, optionally one exact sold-to party."""
        filters = [eq("SalesOrganization", key(sales_org, "sales_org", 4))]
        if sold_to_party.strip(): filters.append(eq("SoldToParty", key(sold_to_party, "sold_to_party", 10)))
        return await client.rows('sales_scheduling_agreement', 'A_SalesSchedgAgrmt', filters, max_results, offset)

    @read_tool
    async def get_sales_scheduling_agreement(sales_scheduling_agreement: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read sales scheduling agreement with independently paged items, partners, conditions and available schedule/document references. Native processing statuses are retained."""
        number = key(sales_scheduling_agreement, 'sales_scheduling_agreement', 10)
        return await record('sales_scheduling_agreement', [eq('SalesSchedulingAgreement', number)], [('items', 'A_SalesSchedgAgrmtItem', [eq('SalesSchedulingAgreement', number)]), ('item_partners', 'A_SalesSchedgAgrmtItemPartner', [eq('SalesSchedulingAgreement', number)]), ('item_pricing_conditions', 'A_SalesSchedgAgrmtItmPrcgElmnt', [eq('SalesSchedulingAgreement', number)]), ('partners', 'A_SalesSchedgAgrmtPartner', [eq('SalesSchedulingAgreement', number)]), ('pricing_conditions', 'A_SalesSchedgAgrmtPrcgElement', [eq('SalesSchedulingAgreement', number)]), ('schedule_lines', 'A_SalesSchedgAgrmtSchedLine', [eq('SalesSchedulingAgreement', number)])], max_results, offset)

    @read_tool
    async def search_outbound_deliveries(sales_org: str, sold_to_party: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search standard outbound deliveries within one sales organization, optionally one exact sold-to party."""
        filters = [eq("SalesOrganization", key(sales_org, "sales_org", 4))]
        if sold_to_party.strip(): filters.append(eq("SoldToParty", key(sold_to_party, "sold_to_party", 10)))
        return await client.rows('outbound_delivery', 'A_OutbDeliveryHeader', filters, max_results, offset)

    @read_tool
    async def get_outbound_delivery(outbound_delivery: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read outbound delivery with independently paged items, partners, conditions and available schedule/document references. Native processing statuses are retained."""
        number = key(outbound_delivery, 'outbound_delivery', 10)
        return await record('outbound_delivery', [eq('DeliveryDocument', number)], [('subsequent_documents', 'A_OutbDeliveryDocFlow', [eq('PrecedingDocument', number)]), ('items', 'A_OutbDeliveryItem', [eq('DeliveryDocument', number)]), ('partners', 'A_OutbDeliveryPartner', [eq('SDDocument', number)])], max_results, offset)

    @read_tool
    async def search_billing_documents(sales_org: str, sold_to_party: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search standard billing documents within one sales organization, optionally one exact sold-to party."""
        filters = [eq("SalesOrganization", key(sales_org, "sales_org", 4))]
        if sold_to_party.strip(): filters.append(eq("SoldToParty", key(sold_to_party, "sold_to_party", 10)))
        return await client.rows('billing_document', 'A_BillingDocument', filters, max_results, offset)

    @read_tool
    async def get_billing_document(billing_document: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read billing document with independently paged items, partners, conditions and available schedule/document references. Native processing statuses are retained."""
        number = key(billing_document, 'billing_document', 10)
        return await record('billing_document', [eq('BillingDocument', number)], [('items', 'A_BillingDocumentItem', [eq('BillingDocument', number)]), ('item_partners', 'A_BillingDocumentItemPartner', [eq('BillingDocument', number)]), ('item_pricing_conditions', 'A_BillingDocumentItemPrcgElmnt', [eq('BillingDocument', number)]), ('partners', 'A_BillingDocumentPartner', [eq('BillingDocument', number)]), ('pricing_conditions', 'A_BillingDocumentPrcgElmnt', [eq('BillingDocument', number)])], max_results, offset)

    @read_tool
    async def search_customer_returns(sales_org: str, sold_to_party: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search standard customer returns within one sales organization, optionally one exact sold-to party."""
        filters = [eq("SalesOrganization", key(sales_org, "sales_org", 4))]
        if sold_to_party.strip(): filters.append(eq("SoldToParty", key(sold_to_party, "sold_to_party", 10)))
        return await client.rows('customer_return', 'A_CustomerReturn', filters, max_results, offset)

    @read_tool
    async def get_customer_return(customer_return: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read customer return with independently paged items, partners, conditions and available schedule/document references. Native processing statuses are retained."""
        number = key(customer_return, 'customer_return', 10)
        return await record('customer_return', [eq('CustomerReturn', number)], [('items', 'A_CustomerReturnItem', [eq('CustomerReturn', number)]), ('item_partners', 'A_CustomerReturnItemPartner', [eq('CustomerReturn', number)]), ('item_pricing_conditions', 'A_CustomerReturnItemPrcgElmnt', [eq('CustomerReturn', number)]), ('partners', 'A_CustomerReturnPartner', [eq('CustomerReturn', number)]), ('pricing_conditions', 'A_CustomerReturnPrcgElmnt', [eq('CustomerReturn', number)]), ('schedule_lines', 'A_CustomerReturnScheduleLine', [eq('CustomerReturn', number)])], max_results, offset)

    @read_tool
    async def search_credit_memo_requests(sales_org: str, sold_to_party: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search standard credit memo requests within one sales organization, optionally one exact sold-to party."""
        filters = [eq("SalesOrganization", key(sales_org, "sales_org", 4))]
        if sold_to_party.strip(): filters.append(eq("SoldToParty", key(sold_to_party, "sold_to_party", 10)))
        return await client.rows('credit_memo_request', 'A_CreditMemoRequest', filters, max_results, offset)

    @read_tool
    async def get_credit_memo_request(credit_memo_request: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read credit memo request with independently paged items, partners, conditions and available schedule/document references. Native processing statuses are retained."""
        number = key(credit_memo_request, 'credit_memo_request', 10)
        return await record('credit_memo_request', [eq('CreditMemoRequest', number)], [('item_partners', 'A_CreditMemoReqItemPartner', [eq('CreditMemoRequest', number)]), ('item_pricing_conditions', 'A_CreditMemoReqItemPrcgElmnt', [eq('CreditMemoRequest', number)]), ('partners', 'A_CreditMemoReqPartner', [eq('CreditMemoRequest', number)]), ('pricing_conditions', 'A_CreditMemoReqPrcgElmnt', [eq('CreditMemoRequest', number)]), ('items', 'A_CreditMemoRequestItem', [eq('CreditMemoRequest', number)])], max_results, offset)

    @read_tool
    async def search_debit_memo_requests(sales_org: str, sold_to_party: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search standard debit memo requests within one sales organization, optionally one exact sold-to party."""
        filters = [eq("SalesOrganization", key(sales_org, "sales_org", 4))]
        if sold_to_party.strip(): filters.append(eq("SoldToParty", key(sold_to_party, "sold_to_party", 10)))
        return await client.rows('debit_memo_request', 'A_DebitMemoRequest', filters, max_results, offset)

    @read_tool
    async def get_debit_memo_request(debit_memo_request: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read debit memo request with independently paged items, partners, conditions and available schedule/document references. Native processing statuses are retained."""
        number = key(debit_memo_request, 'debit_memo_request', 10)
        return await record('debit_memo_request', [eq('DebitMemoRequest', number)], [('item_partners', 'A_DebitMemoReqItemPartner', [eq('DebitMemoRequest', number)]), ('item_pricing_conditions', 'A_DebitMemoReqItemPrcgElmnt', [eq('DebitMemoRequest', number)]), ('partners', 'A_DebitMemoReqPartner', [eq('DebitMemoRequest', number)]), ('pricing_conditions', 'A_DebitMemoReqPrcgElmnt', [eq('DebitMemoRequest', number)]), ('items', 'A_DebitMemoRequestItem', [eq('DebitMemoRequest', number)])], max_results, offset)

    @read_tool
    async def search_customers(name: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search activated customer master records by a customer-name prefix."""
        value = key(name, "name", 220).replace("'", "''")
        return await client.rows("customer", "A_Customer", [f"startswith(CustomerName,'{value}')"], max_results, offset)

    @read_tool
    async def get_customer(customer: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read an activated customer with separately paged sales areas and company-code data, retaining all organizational keys."""
        filters = [eq("Customer", key(customer, "customer", 10))]
        return await record("customer", filters, [("sales_areas", "A_CustomerSalesArea", filters), ("company_codes", "A_CustomerCompany", filters)], max_results, offset)
