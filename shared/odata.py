"""Fixed SAP read endpoints; shared by two independently configured providers."""

import os
import re
import ssl
from contextvars import ContextVar
from datetime import date
from pathlib import Path
from time import monotonic
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import httpx
from dotenv import dotenv_values


request_trace = ContextVar("sap_api_requests", default=None)

# Explicit version mappings, never automatic fallbacks. Private systems keep the
# established V2 APIs; Public Cloud uses the current PO, PR and Product V4 APIs.
V2_SERVICES = {
    "material": ("API_PRODUCT_SRV", "A_Product", "A_ProductDescription", "A_ProductPlant"),
    "supplier": ("API_BUSINESS_PARTNER", "A_Supplier"),
    "purchase_requisition": ("API_PURCHASEREQ_PROCESS_SRV", "A_PurchaseRequisitionHeader", "A_PurchaseRequisitionItem"),
    "purchase_order": ("API_PURCHASEORDER_PROCESS_SRV", "A_PurchaseOrder", "A_PurchaseOrderItem"),
    "material_document": ("API_MATERIAL_DOCUMENT_SRV", "A_MaterialDocumentHeader", "A_MaterialDocumentItem"),
    "stock": ("API_MATERIAL_STOCK_SRV", "A_MatlStkInAcctMod"),
    "supplier_invoice": ("API_SUPPLIERINVOICE_PROCESS_SRV", "A_SupplierInvoice", "A_SuplrInvcItemPurOrdRef",
                         "A_SupplierInvoiceItemGLAcct", "A_SupplierInvoiceTax", "A_SupplierInvoiceWhldgTax"),
    "physical_inventory": ("API_PHYSICAL_INVENTORY_DOC_SRV", "A_PhysInventoryDocHeader", "A_PhysInventoryDocItem"),
    "reservation": ("API_RESERVATION_DOCUMENT_SRV", "A_ReservationDocumentHeader", "A_ReservationDocumentItem"),
    "batch": ("API_BATCH_SRV", "Batch", "BatchPlant"),
    "purchasing_info_record": ("API_INFORECORD_PROCESS_SRV", "A_PurchasingInfoRecord", "A_PurgInfoRecdOrgPlantData"),
    "source_list": ("API_PURCHASING_SOURCE_SRV", "A_PurchasingSource"),
    "quota_arrangement": ("API_PUR_QUOTA_ARRANGEMENT_SRV", "A_PurchasingQuotaArrangement", "A_PurgQuotaArrangementItem"),
    "purchase_contract": ("API_PURCHASECONTRACT_PROCESS_SRV;v=0002", "A_PurchaseContract", "A_PurchaseContractItem"),
    "scheduling_agreement": ("API_SCHED_AGRMT_PROCESS_SRV", "A_SchAgrmtHeader", "A_SchAgrmtItem", "A_SchAgrmtSchLine"),
    "request_for_quotation": ("API_RFQ_PROCESS_SRV", "A_RequestForQuotation", "A_RequestForQuotationItem", "A_RequestForQuotationBidder"),
    "supplier_quotation": ("API_QTN_PROCESS_SRV", "A_SupplierQuotation", "A_SupplierQuotationItem"),
    "service_entry_sheet": ("API_SERVICE_ENTRY_SHEET_SRV", "A_ServiceEntrySheet", "A_ServiceEntrySheetItem"),
    'production_order': ('API_PRODUCTION_ORDER_2_SRV', 'A_ProductionOrder_2', 'A_ProductionOrderItem_2', 'A_ProductionOrderOperation_2', 'A_ProductionOrderComponent_3', 'A_ProductionOrderStatus_2'),
    'process_order': ('API_PROCESS_ORDER_2_SRV', 'A_ProcessOrder_2', 'A_ProcessOrderItem_2', 'A_ProcessOrderOperation_2', 'A_ProcessOrderComponent_2', 'A_ProcessOrderStatus_2'),
    'production_confirmation': ('API_PROD_ORDER_CONFIRMATION_2_SRV', 'ProdnOrdConf2', 'ProdnOrdConfMatlDocItm'),
    'process_confirmation': ('API_PROC_ORDER_CONFIRMATION_2_SRV', 'ProcOrdConf2', 'ProcOrdConfMatlDocItm'),
    'bill_of_material': ('API_BILL_OF_MATERIAL_SRV;v=0002', 'MaterialBOM', 'MaterialBOMItem'),
    'production_routing': ('API_PRODUCTION_ROUTING', 'ProductionRoutingHeader', 'ProductionRoutingOperation', 'ProductionRoutingSequence'),
    'independent_requirement': ('API_PLND_INDEP_RQMT_SRV', 'PlannedIndepRqmt', 'PlannedIndepRqmtItem'),
    'master_recipe': ('API_MASTER_RECIPE', 'MasterRecipeHeader', 'MasterRecipeOperation', 'MasterRecipePhase'),
    'sales_inquiry': ('API_SALES_INQUIRY_SRV', 'A_SalesInquiry', 'A_SalesInquiryItem', 'A_SalesInquiryItemPartner', 'A_SalesInquiryItemPrcgElmnt', 'A_SalesInquiryPartner', 'A_SalesInquiryPrcgElmnt'),
    'sales_quotation': ('API_SALES_QUOTATION_SRV', 'A_SalesQuotation', 'A_SalesQuotationItem', 'A_SalesQuotationItemPartner', 'A_SalesQuotationItemPrcgElmnt', 'A_SalesQuotationPartner', 'A_SalesQuotationPrcgElmnt'),
    'sales_order': ('API_SALES_ORDER_SRV', 'A_SalesOrder', 'A_SalesOrderBillingPlanItem', 'A_SalesOrderHeaderPartner', 'A_SalesOrderHeaderPrElement', 'A_SalesOrderItem', 'A_SalesOrderItemPartner', 'A_SalesOrderItemPrElement', 'A_SalesOrderPrecdgProcFlow', 'A_SalesOrderScheduleLine', 'A_SalesOrderSubsqntProcFlow', 'A_SlsOrderItemBillingPlanItem'),
    'sales_contract': ('API_SALES_CONTRACT_SRV', 'A_SalesContract', 'A_SalesContractItem', 'A_SalesContractItemPartner', 'A_SalesContractItemPrcgElmnt', 'A_SalesContractPartner', 'A_SalesContractPrcgElmnt'),
    'sales_scheduling_agreement': ('API_SALES_SCHEDULING_AGREEMENT', 'A_SalesSchedgAgrmt', 'A_SalesSchedgAgrmtItem', 'A_SalesSchedgAgrmtItemPartner', 'A_SalesSchedgAgrmtItmPrcgElmnt', 'A_SalesSchedgAgrmtPartner', 'A_SalesSchedgAgrmtPrcgElement', 'A_SalesSchedgAgrmtSchedLine'),
    'outbound_delivery': ('API_OUTBOUND_DELIVERY_SRV', 'A_OutbDeliveryHeader', 'A_OutbDeliveryDocFlow', 'A_OutbDeliveryItem', 'A_OutbDeliveryPartner'),
    'billing_document': ('API_BILLING_DOCUMENT_SRV', 'A_BillingDocument', 'A_BillingDocumentItem', 'A_BillingDocumentItemPartner', 'A_BillingDocumentItemPrcgElmnt', 'A_BillingDocumentPartner', 'A_BillingDocumentPrcgElmnt'),
    'customer_return': ('API_CUSTOMER_RETURN_SRV', 'A_CustomerReturn', 'A_CustomerReturnItem', 'A_CustomerReturnItemPartner', 'A_CustomerReturnItemPrcgElmnt', 'A_CustomerReturnPartner', 'A_CustomerReturnPrcgElmnt', 'A_CustomerReturnScheduleLine'),
    'credit_memo_request': ('API_CREDIT_MEMO_REQUEST_SRV', 'A_CreditMemoRequest', 'A_CreditMemoReqItemPartner', 'A_CreditMemoReqItemPrcgElmnt', 'A_CreditMemoReqPartner', 'A_CreditMemoReqPrcgElmnt', 'A_CreditMemoRequestItem'),
    'debit_memo_request': ('API_DEBIT_MEMO_REQUEST_SRV', 'A_DebitMemoRequest', 'A_DebitMemoReqItemPartner', 'A_DebitMemoReqItemPrcgElmnt', 'A_DebitMemoReqPartner', 'A_DebitMemoReqPrcgElmnt', 'A_DebitMemoRequestItem'),
    'customer': ('API_BUSINESS_PARTNER', 'A_Customer', 'A_CustomerSalesArea', 'A_CustomerCompany'),
    'ewm_warehouse': ('API_WAREHOUSE', 'Warehouse', 'WarehouseStorageType'),
    'ewm_storage_bin': ('API_WAREHOUSE_STORAGE_BIN', 'WarehouseStorageBin'),
    'ewm_warehouse_order': ('API_WAREHOUSE_ORDER_TASK', 'WarehouseOrder', 'WarehouseTask'),
    'ewm_warehouse_task': ('API_WAREHOUSE_ORDER_TASK', 'WarehouseTask'),
    'ewm_handling_unit': ('API_HANDLING_UNIT', 'HandlingUnit', 'HandlingUnitItem'),
    'ewm_inbound_delivery': ('API_WHSE_INBOUND_DELIVERY', 'WhseInboundDeliveryHead', 'WhseInboundDeliveryItem'),
    'ewm_outbound_delivery': ('API_WHSE_OUTB_DLV_ORDER', 'WhseOutboundDeliveryOrderHead', 'WhseOutboundDeliveryOrderItem'),
    'ewm_physical_inventory': ('API_WHSE_PHYSINVENTORYITEM', 'WhsePhysicalInventoryItem', 'WhsePhysicalInventoryCountItem'),
    'company_code': ('API_COMPANYCODE_SRV', 'A_CompanyCode'),
    'chart_of_accounts': ('API_CHARTOFACCOUNTS_SRV', 'A_ChartOfAccounts', 'A_ChartOfAccountsText'),
    'gl_account': ('API_GLACCOUNTINCHARTOFACCOUNTS_SRV', 'A_GLAccountInChartOfAccounts', 'A_GLAccountText'),
    'journal_entry': ('API_OPLACCTGDOCITEMCUBE_SRV', 'A_OperationalAcctgDocItemCube'),
    'trial_balance': ('C_TRIALBALANCE_CDS', 'C_TRIALBALANCE', 'C_TRIALBALANCEResults'),
    'controlling_area': ('API_CONTROLLINGAREA_SRV', 'A_ControllingArea'),
    'cost_center': ('API_COSTCENTER_SRV', 'A_CostCenter', 'A_CostCenterText'),
    'profit_center': ('API_PROFITCENTER_SRV', 'A_ProfitCenter', 'A_ProfitCenterText'),
    'activity_type': ('API_COSTCENTERACTIVITYTYPE_SRV', 'A_CostCenterActivityType', 'A_CostCenterActivityTypeText'),
    'statistical_key_figure': ('API_STATISTICALKEYFIGURE_SRV', 'A_StatisticalKeyFigure', 'A_StatisticalKeyFigureText'),
    'co_actual_balance': ('API_JOURNALENTRYITEMBASIC_SRV', 'A_JournalEntryItemBasic'),
    'co_plan_balance': ('API_FINPLANNINGENTRYITEM_SRV', 'A_FinPlanningEntryItem'),
    'business_partner': ('API_BUSINESS_PARTNER', 'A_BusinessPartner', 'A_BusinessPartnerRole', 'A_BusinessPartnerAddress', 'A_BusinessPartnerBank', 'A_BusinessPartnerTaxNumber', 'A_BuPaIdentification'),
    'supplier_organization': ('API_BUSINESS_PARTNER', 'A_Supplier', 'A_SupplierCompany', 'A_SupplierPurchasingOrg'),
    'inspection_plan': ('API_INSPECTIONPLAN_SRV', 'A_InspectionPlan', 'A_InspPlanOperation', 'A_InspPlanOpCharacteristic', 'A_InspPlanMaterialAssgmt'),
    'master_inspection_characteristic': ('API_MASTERINSPCHARACTERISTIC_SRV', 'A_InspectionSpecification'),
    'inspection_method': ('API_INSPECTIONMETHOD_SRV', 'A_InspectionMethod'),
    'quality_info_record': ('API_QUALITYINFORECORD_SRV', 'QualityInProcurement', 'QualityFirstArticleInspection'),
    'inspection_lot': ('API_INSPECTIONLOT_SRV', 'A_InspectionLot', 'A_InspectionLotWithStatus', 'A_InspectionOperation', 'A_InspectionCharacteristic', 'A_InspectionSubset', 'A_InspSampleCharacteristic', 'A_InspSampleResult', 'A_InspectionResult', 'A_InspectionResultValue', 'A_InspLotUsageDecision'),
    'qm_characteristic_selected_set': ('API_CHARCATTRIBUTECATALOG_SRV', 'A_CharcAttribSeldCodeSet', 'A_CharcAttribSeldSetCode', 'A_CharcAttribSeldSetCodeT', 'A_CharcAttribSeldSetT'),
    'gl_line_item': ('API_GLACCOUNTLINEITEM', 'GLAccountLineItem'),
}
PUBLIC_V4 = {
    "material": ("api_product/srvd_a2x/sap/product/0002", "Product", "ProductDescription", "ProductPlant"),
    "purchase_requisition": ("api_purchaserequisition_2/srvd_a2x/sap/purchaserequisition/0001", "PurchaseReqn", "PurchaseReqnItem"),
    "purchase_order": ("api_purchaseorder_2/srvd_a2x/sap/purchaseorder/0001", "PurchaseOrder", "PurchaseOrderItem"),
}

# Explicit standard V4 services supported in both deployment routes.
COMMON_V4 = {
    'planned_order': ('api_plannedorder/srvd_a2x/sap/plannedorder/0001', 'PlannedOrderHeader', 'PlannedOrderComponent', 'PlannedOrderCapacity'),
    'work_center': ('api_work_center/srvd_a2x/sap/workcenter/0001', 'WorkCenterHeader', 'WorkCenterCapacity', 'WorkCenterCostCenter'),
    "production_version": ("api_production_version/srvd_a2x/sap/productionversion/0001", "ProductionVersion"),
    'ewm_stock': ('api_whse_availablestock/srvd_a2x/sap/warehouseavailablestock/0001', 'WarehouseAvailableStock'),
    'ewm_product': ('api_product/srvd_a2x/sap/product/0002', 'ProductEWMWarehouse', 'ProductEWMStorageType'),
    'bank': ('api_bank/srvd_a2x/sap/bank/0001', 'Bank'),
    'fixed_asset_master': ('api_fixedasset/srvd_a2x/sap/fixedasset/0001', 'FixedAsset', 'FixedAssetValuation'),
    'quality_notification': ('api_qualitynotification/srvd_a2x/sap/qualitynotification/0001', 'QualityNotification', 'QualityNotificationItem', 'QualityNotificationTask', 'QltyNotificationItemCause', 'QltyNotificationPartner'),
    'qm_usage_decision_selected_set': ('api_usagedcsnseldcodeset/srvd_a2x/sap/usagedecisionseldcodeset/0001', 'UsgeDcsnSelectedCodeSet', 'UsgeDcsnSelectedCode', 'UsgeDcsnSeldCodeText', 'UsgeDcsnSeldCodeGroupText', 'UsgeDcsnSeldCodeSetText'),
    'qm_catalog': ('api_configblcodescatalog/srvd_a2x/sap/configurablecodescatalog/0001', 'ConfigurableCodesCatalog', 'ConfigurableCodesCodeGroup'),
    'qm_code_group': ('api_configblcodescatalog/srvd_a2x/sap/configurablecodescatalog/0001', 'ConfigurableCodesCodeGroup', 'ConfigurableCodesCode', 'ConfigurableCodesCodeGroupText', 'ConfigurableCodesCodeText'),
}
PUBLIC_V2 = {
    "production_routing": ("API_PRODUCTION_ROUTING;v=0003", "ProductionRoutingHeader", "ProductionRoutingOperation", "ProductionRoutingSequence"),
}


class APIError(Exception):
    def __init__(self, message, *, error_type="APIError", http_status=None, code=None):
        super().__init__(message)
        self.error_type = error_type
        self.http_status = http_status
        self.code = code


def key(value: str, name: str, length: int) -> str:
    value = value.strip()
    if not value or len(value) > length or not value.isprintable() or any(c in value for c in "*?"):
        raise ValueError(f"{name} must contain 1 to {length} characters without wildcards.")
    return value


def eq(field: str, value: str) -> str:
    return f"{field} eq '" + value.replace("'", "''") + "'"


def typed_eq(field: str, value: str, edm_type: str, v4: bool = False) -> str:
    """Encode SAP's date/GUID/numeric key types instead of quoting every key as text."""
    if edm_type in {"Edm.DateTime", "Edm.Date"}:
        value = date.fromisoformat(value).isoformat()
        return f"{field} eq {value}" if v4 else f"{field} eq datetime'{value}T00:00:00'"
    if edm_type == "Edm.Guid":
        from uuid import UUID
        value = str(UUID(value))
        return f"{field} eq {value}" if v4 else f"{field} eq guid'{value}'"
    if edm_type in {"Edm.Int16", "Edm.Int32", "Edm.Int64"}:
        if not value.isascii() or not value.isdigit():
            raise ValueError(f"{field} must be a non-negative integer.")
        return f"{field} eq {int(value)}"
    return eq(field, value)


def clean(value):
    if isinstance(value, list):
        return [clean(row) for row in value]
    if isinstance(value, dict):
        return {
            name: clean(item) for name, item in value.items()
            if not name.startswith(("__", "@odata.")) and item is not None
            and not (isinstance(item, str) and not item.strip() and name not in {
                "RecordType", "SourceLedger", "BillOfMaterialVersion", "EngineeringChangeDocument", "HeaderChangeDocument",
                "MRPArea", "RequirementPlan", "RequirementSegment", "BatchIdentifyingPlant", "Batch",
                "EWMStockOwner", "EntitledToDisposeParty", "EWMStockType", "EWMStockUsage",
                "StockDocumentCategory", "EWMDocumentCategory", "WBSElementExternalID",
                "SpecialStockIdfgSalesOrder", "SpecialStockIdfgSalesOrderItem", "HandlingUnitExternalID",
                "EWMStorageBin", "EWMResource",
            })
        }
    return value


class ODataClient:
    def __init__(self, directory: Path, public: bool):
        self.directory = directory
        self.public = public
        # Each process owns one provider. No credentials/configuration are read
        # from another provider at runtime.
        self.config = {**dotenv_values(directory / ".env"), **os.environ}
        self.services = dict(V2_SERVICES)
        self.services.update(COMMON_V4)
        if public:
            self.services.update(PUBLIC_V4)
            self.services.update(PUBLIC_V2)
        else:
            self.services["mdg_my_change_request"] = ("MDG_MYCR_SRV", "ChangeRequests")
        self._token = ""
        self._expires_at = 0.0
        self._http = None
        self._auth_failed = False
        self.verified_services = set()

    def is_v4(self, service):
        return service in COMMON_V4 or (self.public and service in PUBLIC_V4)

    def service_path(self, service):
        prefix = "/sap/opu/odata4/sap/" if self.is_v4(service) else "/sap/opu/odata/sap/"
        return prefix + self.services[service][0] + "/"

    def redact(self, value):
        text = str(value)
        for secret in (self.config.get("SAP_API_USERNAME"), self.config.get("SAP_API_PASSWORD"),
                       self.config.get("SAP_API_CLIENT_SECRET"), self._token):
            if secret:
                text = text.replace(secret, "[REDACTED]")
        return text

    def failure(self, error):
        return {
            "status": "error", "connection": "OData",
            "error_type": getattr(error, "error_type", type(error).__name__),
            "http_status": getattr(error, "http_status", None),
            "error_code": getattr(error, "code", None),
            "error_message": self.redact(error)[:1000],
        }

    def _configuration(self):
        base = self.config.get("SAP_API_BASE_URL", "").strip().rstrip("/")
        url = urlsplit(base)
        if url.scheme != "https" or not url.netloc or url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
            raise APIError("Set SAP_API_BASE_URL to an HTTPS server origin, without credentials or a path.", error_type="ConfigurationError")
        mode = self.config.get("SAP_API_AUTH", "basic").strip().lower()
        required = {"basic": ("SAP_API_USERNAME", "SAP_API_PASSWORD"),
                    "oauth": ("SAP_API_TOKEN_URL", "SAP_API_CLIENT_ID", "SAP_API_CLIENT_SECRET")}
        if mode not in required:
            raise APIError("SAP_API_AUTH must be basic or oauth.", error_type="ConfigurationError")
        missing = [name for name in required[mode] if not self.config.get(name)]
        if missing:
            raise APIError("Missing configuration: " + ", ".join(missing), error_type="ConfigurationError")
        return base, mode

    def _client(self):
        if self._http is None:
            ca = self.config.get("SAP_API_CA_BUNDLE", "").strip()
            context = ssl.create_default_context()
            if ca:
                context.load_verify_locations(cafile=str((self.directory / ca).resolve()))
            self._http = httpx.AsyncClient(
                verify=context, timeout=15.0, follow_redirects=False,
                # Follow the verified private intranet path; Public Cloud may
                # use the workstation's configured HTTPS proxy.
                trust_env=self.public,
            )
        return self._http

    def _check_response(self, response):
        if response.status_code == 401:
            # Reusing rejected credentials on every subsequent Tool call can
            # lock the account. A new process is needed after fixing access.
            self._auth_failed = True
        if response.status_code >= 300:
            try:
                error = response.json().get("error", {})
                message = error.get("message", "")
                if isinstance(message, dict):
                    message = message.get("value", "")
                code = error.get("code")
            except (ValueError, AttributeError):
                message, code = "", None
            raise APIError(message or f"SAP returned HTTP {response.status_code}.", http_status=response.status_code, code=code)

    async def _credentials(self, mode):
        if self._auth_failed:
            raise APIError("Authentication was rejected in this session; correct access and restart the provider. No retry was attempted.", error_type="AuthenticationBlocked")
        if mode == "basic":
            return {}, httpx.BasicAuth(self.config["SAP_API_USERNAME"], self.config["SAP_API_PASSWORD"])
        if not self._token or monotonic() >= self._expires_at:
            token_url = self.config["SAP_API_TOKEN_URL"].strip()
            parsed = urlsplit(token_url)
            if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
                raise APIError("SAP_API_TOKEN_URL must be an HTTPS URL without credentials.", error_type="ConfigurationError")
            data = {"grant_type": "client_credentials"}
            if self.config.get("SAP_API_SCOPE"):
                data["scope"] = self.config["SAP_API_SCOPE"]
            response = await self._client().post(
                token_url, data=data,
                auth=httpx.BasicAuth(self.config["SAP_API_CLIENT_ID"], self.config["SAP_API_CLIENT_SECRET"]),
            )
            self._check_response(response)
            body = response.json()
            token = body.get("access_token")
            if not isinstance(token, str) or not token or str(body.get("token_type", "Bearer")).lower() != "bearer":
                raise APIError("OAuth response did not contain a Bearer access token.")
            self._token = token
            self._expires_at = monotonic() + max(1, int(body.get("expires_in", 300)) - 30)
        return {"Authorization": "Bearer " + self._token}, None

    async def get(self, service, entity, params=None, next_url=None):
        trial_result = service == "trial_balance" and re.fullmatch(
            r"C_TRIALBALANCE\(P_FromPostingDate=datetime'\d{4}-\d{2}-\d{2}T00:00:00',P_ToPostingDate=datetime'\d{4}-\d{2}-\d{2}T00:00:00'\)/Results", entity)
        if service not in self.services or (entity not in (*self.services[service][1:], "$metadata") and not trial_result):
            raise APIError("Only the fixed SAP entities and $metadata may be read.", error_type="OperationNotAllowed")
        base, mode = self._configuration()
        url = base + self.service_path(service) + entity
        if next_url:
            candidate = urljoin(url, next_url)
            # SAP supplies paging links. Credentials must never follow a link
            # to another origin, service, entity or operation.
            target, original = urlsplit(candidate), urlsplit(url)
            if target.scheme != original.scheme or target.netloc != original.netloc or target.path != original.path or target.fragment:
                raise APIError("SAP returned a paging link outside the requested entity.", error_type="InvalidPagingLink")
            url = candidate
            params = None
        headers, auth = await self._credentials(mode)
        headers["Accept"] = "application/xml" if entity == "$metadata" else "application/json;IEEE754Compatible=true"
        if params is not None:
            params = dict(params)
        else:
            params = dict(httpx.URL(url).params)
            url = str(httpx.URL(url).copy_with(query=None))
        for name, variable in (("sap-client", "SAP_API_CLIENT"), ("sap-language", "SAP_API_LANGUAGE")):
            if self.config.get(variable):
                params[name] = self.config[variable]
        if not self.is_v4(service) and entity != "$metadata":
            params["$format"] = "json"
        trace = request_trace.get()
        if trace is not None:
            trace.append("GET " + self.service_path(service) + entity)
        response = await self._client().get(url, params=params, headers=headers, auth=auth)
        self._check_response(response)
        return response

    async def metadata(self, service):
        response = await self.get(service, "$metadata")
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError:
            raise APIError("SAP did not return OData XML metadata; check the API endpoint and authentication.") from None
        entities = sorted({node.attrib["Name"] for node in root.iter() if node.tag.endswith("}EntitySet") and "Name" in node.attrib})
        if not entities:
            raise APIError("The response contained no OData entity sets.")
        missing = sorted(set(self.services[service][1:]) - set(entities))
        if not missing:
            self.verified_services.add(service)
        return {"status": "partial" if missing else "ok", "connection": "OData",
                "service": self.services[service][0], "entity_sets": entities, "missing_entities": missing}

    async def rows(self, service, entity, filters, limit=100, offset=0, select=None):
        if not 1 <= limit <= 500 or offset < 0:
            raise ValueError("max_results must be 1-500 and offset must be non-negative.")
        params = {"$top": limit + 1, "$skip": offset}
        if filters:
            params["$filter"] = " and ".join(filters)
        if select:
            params["$select"] = ",".join(select)
        rows, next_url, visited = [], None, set()
        while True:
            response = await self.get(service, entity, params, next_url)
            try:
                body = response.json(parse_float=str)
                value = body.get("d", body)
                collection_key = "value" if self.is_v4(service) else "results"
                if collection_key not in value:
                    raise APIError("SAP did not return an OData JSON collection.")
                batch = value[collection_key]
                next_url = value.get("__next") or value.get("@odata.nextLink")
            except (ValueError, AttributeError):
                raise APIError("SAP did not return an OData JSON collection.") from None
            if not isinstance(batch, list) or any(not isinstance(row, dict) for row in batch):
                raise APIError("SAP returned an invalid OData collection.")
            rows.extend(clean(batch))
            if len(rows) > limit or not next_url:
                break
            if not batch or next_url in visited:
                raise APIError("SAP returned a repeated or empty continuation page.", error_type="InvalidPagingLink")
            visited.add(next_url)
        return {"status": "ok" if rows else "not_found", "connection": "OData",
                "service": self.services[service][0], "returned": min(len(rows), limit),
                "truncated": len(rows) > limit or bool(next_url), "next_offset": offset + limit if len(rows) > limit or next_url else None,
                "items": rows[:limit]}
