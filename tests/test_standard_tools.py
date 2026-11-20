"""Standard-domain reads: real MCP dispatch against independent SAP-shaped fixtures."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.mm_api import create_server
from shared.odata import ODataClient


SD_CASES = [['search_sales_inquiries', {'sales_org': '1000'}],
 ['get_sales_inquiry', {'sales_inquiry': '100'}],
 ['search_sales_quotations', {'sales_org': '1000'}],
 ['get_sales_quotation', {'sales_quotation': '100'}],
 ['search_sales_orders', {'sales_org': '1000'}],
 ['get_sales_order', {'sales_order': '100'}],
 ['search_sales_contracts', {'sales_org': '1000'}],
 ['get_sales_contract', {'sales_contract': '100'}],
 ['search_sales_scheduling_agreements', {'sales_org': '1000'}],
 ['get_sales_scheduling_agreement', {'sales_scheduling_agreement': '100'}],
 ['search_outbound_deliveries', {'sales_org': '1000'}],
 ['get_outbound_delivery', {'outbound_delivery': '100'}],
 ['search_billing_documents', {'sales_org': '1000'}],
 ['get_billing_document', {'billing_document': '100'}],
 ['search_customer_returns', {'sales_org': '1000'}],
 ['get_customer_return', {'customer_return': '100'}],
 ['search_credit_memo_requests', {'sales_org': '1000'}],
 ['get_credit_memo_request', {'credit_memo_request': '100'}],
 ['search_debit_memo_requests', {'sales_org': '1000'}],
 ['get_debit_memo_request', {'debit_memo_request': '100'}],
 ['search_customers', {'name': 'Test'}],
 ['get_customer', {'customer': '100'}]]


WM_CASES = [['search_ewm_warehouses', {'warehouse': '0001'}],
 ['get_ewm_warehouse', {'warehouse': '0001'}],
 ['search_ewm_storage_bins', {'warehouse': '0001'}],
 ['get_ewm_storage_bin', {'storage_bin': 'A01', 'warehouse': '0001'}],
 ['search_ewm_warehouse_orders', {'warehouse': '0001'}],
 ['get_ewm_warehouse_order', {'warehouse': '0001', 'warehouse_order': '1'}],
 ['search_ewm_warehouse_tasks', {'warehouse': '0001'}],
 ['get_ewm_warehouse_task', {'warehouse': '0001', 'warehouse_task': '1', 'warehouse_task_item': '0'}],
 ['search_ewm_handling_units', {'warehouse': '0001'}],
 ['get_ewm_handling_unit', {'handling_unit': 'HU1', 'warehouse': '0001'}],
 ['search_ewm_inbound_deliveries', {'warehouse': '0001'}],
 ['get_ewm_inbound_delivery', {'ewm_inbound_delivery': '100'}],
 ['search_ewm_outbound_deliveries', {'warehouse': '0001'}],
 ['get_ewm_outbound_delivery', {'ewm_outbound_delivery': '100'}],
 ['search_ewm_physical_inventory_items', {'warehouse': '0001'}],
 ['get_ewm_physical_inventory_item', {'document_uuid': '12345678-1234-1234-1234-123456789abc', 'item': '1'}],
 ['search_ewm_stock', {'warehouse': '0001'}],
 ['get_ewm_stock', {'product': 'M1', 'warehouse': '0001'}],
 ['search_ewm_products', {'entitled_to_dispose_party': '100', 'warehouse': '0001'}],
 ['get_ewm_product', {'entitled_to_dispose_party': '100', 'product': 'M1', 'warehouse': '0001'}]]


FI_CASES = [['search_company_codes', {'company_code': '1000'}],
 ['get_company_code', {'company_code': '1000'}],
 ['search_charts_of_accounts', {'chart_of_accounts': 'YCOA'}],
 ['get_chart_of_accounts', {'chart_of_accounts': 'YCOA'}],
 ['search_gl_accounts', {'chart_of_accounts': 'YCOA'}],
 ['get_gl_account', {'chart_of_accounts': 'YCOA', 'gl_account': '100000'}],
 ['search_banks', {'bank_country': 'CN'}],
 ['get_bank', {'bank_country': 'CN', 'bank_key': '123'}],
 ['search_fixed_assets', {'company_code': '1000'}],
 ['get_fixed_asset', {'company_code': '1000', 'fixed_asset': '0', 'master_fixed_asset': '100'}],
 ['search_journal_entry_items', {'company_code': '1000', 'fiscal_year': '2026'}],
 ['get_journal_entry', {'accounting_document': '100', 'company_code': '1000', 'fiscal_year': '2026'}],
 ['get_journal_entry_item',
  {'accounting_document': '100',
   'accounting_document_item': '1',
   'company_code': '1000',
   'fiscal_year': '2026'}],
 ['search_customer_account_items', {'company_code': '1000', 'customer': '100', 'fiscal_year': '2026'}],
 ['search_supplier_account_items', {'company_code': '1000', 'fiscal_year': '2026', 'supplier': '100'}],
 ['get_gl_account_balances',
  {'company_code': '1000',
   'gl_account': '100000',
   'ledger': '0L',
   'posting_date_from': '2026-01-01',
   'posting_date_to': '2026-10-23'}]]


CO_CASES = [['search_controlling_areas', {'controlling_area': '1000'}],
 ['get_controlling_area', {'controlling_area': '1000'}],
 ['search_cost_centers', {'controlling_area': '1000'}],
 ['get_cost_center', {'controlling_area': '1000', 'cost_center': '100', 'validity_end_date': '9999-12-31'}],
 ['search_profit_centers', {'controlling_area': '1000'}],
 ['get_profit_center',
  {'controlling_area': '1000', 'profit_center': '100', 'validity_end_date': '9999-12-31'}],
 ['search_activity_types', {'controlling_area': '1000'}],
 ['get_activity_type',
  {'activity_type': '100', 'controlling_area': '1000', 'validity_end_date': '9999-12-31'}],
 ['search_statistical_key_figures', {'controlling_area': '1000'}],
 ['get_statistical_key_figure', {'controlling_area': '1000', 'statistical_key_figure': 'HEAD'}],
 ['search_co_actual_balances',
  {'controlling_area': '1000', 'cost_center': '100', 'fiscal_year': '2026', 'ledger': '0L'}],
 ['search_co_plan_balances',
  {'controlling_area': '1000',
   'cost_center': '100',
   'fiscal_year': '2026',
   'ledger': '0L',
   'planning_category': 'PLN'}],
 ['search_actual_cost_items',
  {'company_code': '1000', 'controlling_area': '1000', 'cost_center': '100', 'fiscal_year': '2026'}]]


MDG_CASES = [['search_business_partners', {'name': 'Test'}],
 ['get_business_partner', {'business_partner': '100'}],
 ['get_supplier_organization_data', {'supplier': '100'}]]


QM_CASES = [['search_inspection_plans', {'plant': '1000'}],
 ['get_inspection_plan', {'internal_version': '1', 'plan': '1', 'plan_group': '1'}],
 ['search_master_inspection_characteristics', {'plant': '1000'}],
 ['get_master_inspection_characteristic', {'characteristic': 'MIC1', 'plant': '1000', 'version': '1'}],
 ['search_inspection_methods', {'plant': '1000'}],
 ['get_inspection_method', {'inspection_method': 'METHOD1', 'plant': '1000', 'version': '1'}],
 ['search_quality_info_records', {'plant': '1000'}],
 ['get_quality_info_record', {'material': 'M1', 'quality_info_record_id': '1'}],
 ['search_inspection_lots', {'plant': '1000'}],
 ['get_inspection_lot', {'inspection_lot': '100'}],
 ['search_quality_notifications', {'notification_type': 'Q1'}],
 ['get_quality_notification', {'quality_notification': '100'}],
 ['search_qm_characteristic_selected_sets', {'plant': '1000'}],
 ['get_qm_characteristic_selected_set', {'plant': '1000', 'selected_set': 'SET1'}],
 ['search_qm_usage_decision_selected_sets', {'plant': '1000'}],
 ['get_qm_usage_decision_selected_set', {'plant': '1000', 'selected_set': 'SET1'}],
 ['search_qm_catalogs', {'catalog_type': '9'}],
 ['get_qm_catalog', {'catalog_type': '9'}],
 ['search_qm_code_groups', {'catalog_type': '9'}],
 ['get_qm_code_group', {'catalog_type': '9', 'code_group': 'GROUP1'}]]


FI_CASES.extend([
    ("search_gl_account_line_items", {"company_code": "1000", "ledger": "0L", "fiscal_year": "2026", "gl_account": "100000"}),
    ("get_gl_account_line_item", {"company_code": "1000", "fiscal_year": "2026", "accounting_document": "100", "ledger": "0L", "ledger_gl_line_item": "000001", "source_ledger": "0L"}),
])
for _name, _args in CO_CASES:
    if _name == "search_actual_cost_items": _args["ledger"] = "0L"


class StandardAPIs(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clients = []

    async def asyncTearDown(self):
        for c in self.clients:
            await c._http.aclose()
        self.temp.cleanup()

    def server(self, public=False, handler=None):
        c = ODataClient(Path(self.temp.name), public)
        c.config = {"SAP_API_BASE_URL": "https://sap.example", "SAP_API_AUTH": "basic",
                    "SAP_API_USERNAME": "test", "SAP_API_PASSWORD": "secret"}
        requests = []
        def handle(r):
            requests.append(r)
            if handler:
                return handler(r)
            entity = r.url.path.rsplit("/", 1)[-1]
            rows = [{"ManufacturingOrder": "100", "Material": "M1", "ProductionPlant": "1010",
                     "Plant": "1010", "OrderInternalBillOfOperations": "10", "TotalQuantity": "0.000",
                     "MaterialCompIsAlternativeItem": False}]
            return httpx.Response(200, json={"value": rows} if "/odata4/" in r.url.path else {"d": {"results": rows}})
        c._http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        self.clients.append(c)
        with patch("shared.mm_api.ODataClient", return_value=c):
            server = create_server(Path(self.temp.name), public)
        return c, server, requests

    async def call(self, server, tool_name, **args):
        r = await server.call_tool(tool_name, args)
        self.assertFalse(r.is_error, r)
        return r.structured_content

    async def test_service_catalog_connection_enum_and_read_annotations(self):
        from typing import get_args
        from shared.mm_api import PrivateService, Service
        for public in (False, True):
            client, server, requests = self.server(public)
            info = await self.call(server, "get_server_info")
            self.assertEqual(set(get_args(Service if public else PrivateService)), set(client.services))
            self.assertEqual(set(info["service_catalog"]), set(client.services))
            for alias, service in client.services.items():
                self.assertEqual(info["service_catalog"][alias]["entities"], list(service[1:]))
                self.assertEqual(info["service_catalog"][alias]["protocol"], "OData V4" if client.is_v4(alias) else "OData V2")
            for tool in await server.list_tools():
                self.assertTrue(tool.annotations.read_only_hint, tool.name)
            self.assertEqual(requests, [])

    async def test_private_mdg_request_scope_paging_and_public_exclusion(self):
        rows = [{"ChangeRequest": "000000001001", "Status": "00", "NoOfDays": "0"},
                {"ChangeRequest": "000000001002", "Status": "01", "Count": 0}]
        def handler(r):
            skip = int(r.url.params.get("$skip", "0"))
            return httpx.Response(200, json={"d": {"results": rows[skip:skip + int(r.url.params["$top"])]}})
        client, server, requests = self.server(handler=handler)
        result = await self.call(server, "search_mdg_my_change_requests", max_results=1, offset=1)
        self.assertEqual(result["items"], [rows[1]])
        self.assertEqual(result["scope"], "authenticated_user_requests")
        self.assertEqual(result["data_state"], "change_request_metadata")
        self.assertEqual(requests[0].url.path, "/sap/opu/odata/sap/MDG_MYCR_SRV/ChangeRequests")
        self.assertEqual(requests[0].method, "GET")
        self.assertNotIn("$filter", requests[0].url.params)
        for status in (200, 403):
            def response(r):
                return httpx.Response(status, json={"d": {"results": []}} if status == 200 else {"error": {"message": "Denied"}})
            _, private_server, _ = self.server(handler=response)
            data = await self.call(private_server, "search_mdg_my_change_requests")
            self.assertEqual(data["status"], "not_found" if status == 200 else "error")
            if status == 200: self.assertEqual(data["items"], [])
        public_client, public_server, _ = self.server(True)
        self.assertNotIn("mdg_my_change_request", public_client.services)
        self.assertNotIn("search_mdg_my_change_requests", {tool.name for tool in await public_server.list_tools()})
        for target, expected in ((server, True), (public_server, False)):
            tool = next(tool for tool in await target.list_tools() if tool.name == "test_sap_api_connection")
            self.assertEqual("mdg_my_change_request" in tool.input_schema["properties"]["service"]["enum"], expected)

    async def test_qm_compound_versions_and_results(self):
        for public in (False, True):
            _, server, requests = self.server(public)
            for name, args in QM_CASES:
                with self.subTest(public=public, tool=name):
                    self.assertEqual((await self.call(server, name, **args))["status"], "ok")
            info = next(r for r in requests if r.url.path.endswith("/QualityInProcurement") and "QltyInProcmtIntID" in r.url.params["$filter"])
            self.assertEqual(info.url.params["$filter"], "Material eq 'M1' and QltyInProcmtIntID eq '1'")
            result = next(r for r in requests if r.url.path.endswith("/A_InspSampleResult"))
            self.assertEqual(result.url.params["$filter"], "InspectionLot eq '100'")
            selected = next(r for r in requests if r.url.path.endswith("/A_CharcAttribSeldSetCode"))
            self.assertIn("SelectedCodeSetPlant eq '1000' and SelectedCodeSet eq 'SET1'", selected.url.params["$filter"])
            self.assertTrue(all(r.method == "GET" for r in requests))

    async def test_standard_empty_denied_and_partial_pages(self):
        for public in (False, True):
            for code in (200, 403):
                def handler(r):
                    if code != 200: return httpx.Response(code, json={"error": {"message": "No permission"}})
                    return httpx.Response(200, json={"value": []} if "/odata4/" in r.url.path else {"d": {"results": []}})
                _, server, requests = self.server(public, handler)
                for name, args in SD_CASES + WM_CASES + FI_CASES + CO_CASES + MDG_CASES + QM_CASES:
                    with self.subTest(public=public, http=code, tool=name):
                        d = await self.call(server, name, **args)
                        self.assertEqual(d["status"], "not_found" if code == 200 else "error", d)
                self.assertTrue(all(r.method == "GET" for r in requests))
        def pages(r):
            entity = r.url.path.rsplit("/", 1)[-1]
            if entity == "QualityNotificationTask": return httpx.Response(403, json={"error": {"message": "Denied"}})
            rows = [{"QualityNotification": "100"}] if entity == "QualityNotification" else [{"NotificationItem": "1"}, {"NotificationItem": "2"}]
            return httpx.Response(200, json={"value": rows})
        _, server, _ = self.server(handler=pages)
        d = await self.call(server, "get_quality_notification", quality_notification="100", max_results=1, offset=1)
        self.assertEqual(d["status"], "partial")
        self.assertEqual(d["header"]["QualityNotification"], "100")
        self.assertEqual(d["next_offset"], 2)
        self.assertEqual(d["tasks"]["http_status"], 403)

    async def test_mdg_active_data_is_not_staging(self):
        for public in (False, True):
            _, server, requests = self.server(public)
            for name, args in MDG_CASES:
                result = await self.call(server, name, **args)
                self.assertEqual(result["status"], "ok")
                if name.startswith("get_"):
                    self.assertEqual(result["data_state"], "active")
                    self.assertNotIn("staging_data", result)
            bp = next(r for r in requests if r.url.path.endswith("/A_BusinessPartnerBank"))
            self.assertEqual(bp.url.params["$filter"], "BusinessPartner eq '100'")

    async def test_co_validity_and_plan_dimensions(self):
        for public in (False, True):
            _, server, requests = self.server(public)
            for name, args in CO_CASES:
                with self.subTest(public=public, tool=name):
                    self.assertEqual((await self.call(server, name, **args))["status"], "ok")
            center = next(r for r in requests if r.url.path.endswith("/A_CostCenter") and "ValidityEndDate" in r.url.params["$filter"])
            self.assertIn("ValidityEndDate eq datetime'9999-12-31T00:00:00'", center.url.params["$filter"])
            plan = next(r for r in requests if r.url.path.endswith("/A_FinPlanningEntryItem"))
            self.assertIn("PlanningCategory eq 'PLN'", plan.url.params["$filter"])
            actual = next(r for r in requests if r.url.path.endswith("/GLAccountLineItem"))
            self.assertIn("*", actual.url.params["$select"].split(","))
            for field in ("AccountingDocument", "CompanyCode", "FiscalYear", "Ledger", "LedgerGLLineItem", "SourceLedger"):
                self.assertIn(field, actual.url.params["$select"].split(","))
            before = len(requests)
            result = await self.call(server, "get_cost_center", controlling_area="1000", cost_center="100", validity_end_date="2026-02-30")
            self.assertEqual(result["error_type"], "ValidationError")
            self.assertEqual(before, len(requests))

    async def test_fi_keys_clearing_and_server_balances(self):
        def handler(r):
            row = {"CompanyCode": "1000", "FiscalYear": "2026", "AccountingDocument": "100",
                   "AccountingDocumentItem": "001", "ClearingAccountingDocument": "200", "IsCleared": True,
                   "AmountInCompanyCodeCurrency": "0.00", "CompanyCodeCurrency": "CNY"}
            return httpx.Response(200, json={"value": [row]} if "/odata4/" in r.url.path else {"d": {"results": [row]}})
        for public in (False, True):
            _, server, requests = self.server(public, handler)
            for name, args in FI_CASES:
                with self.subTest(public=public, tool=name):
                    result = await self.call(server, name, **args)
                    self.assertEqual(result["status"], "ok", result)
                    self.assertEqual(result["items"][0]["AmountInCompanyCodeCurrency"], "0.00")
                    self.assertNotIn("paid", result["items"][0])
            await self.call(server, "search_customer_account_items", company_code="1000", customer="100", fiscal_year="2026", clearing_status="cleared")
            self.assertIn("IsCleared eq true", requests[-1].url.params["$filter"])
            balances = next(r for r in requests if r.url.path.endswith("/Results"))
            self.assertIn("C_TRIALBALANCE(P_FromPostingDate=datetime'2026-01-01T00:00:00'", balances.url.path)
            self.assertIn("CompanyCodeCurrency", balances.url.params["$select"])
            await self.call(server, "get_gl_account_line_item", company_code="1000", fiscal_year="2026", accounting_document="100", ledger="0L", ledger_gl_line_item="000001", source_ledger="")
            self.assertIn("SourceLedger eq ''", requests[-1].url.params["$filter"])
            self.assertTrue(all(r.method == "GET" for r in requests))

    async def test_wm_reads_and_guid_identity(self):
        for public in (False, True):
            _, server, requests = self.server(public)
            for name, args in WM_CASES:
                with self.subTest(public=public, tool=name):
                    self.assertEqual((await self.call(server, name, **args))["status"], "ok")
            inventory = next(r for r in requests if r.url.path.endswith("/WhsePhysicalInventoryItem") and "guid'" in r.url.params["$filter"])
            self.assertIn("PhysicalInventoryItemNumber eq '1'", inventory.url.params["$filter"])
            stock = next(r for r in requests if r.url.path.endswith("/WarehouseAvailableStock") and "Batch eq ''" in r.url.params["$filter"])
            self.assertIn("/odata4/", stock.url.path)
            self.assertIn("EWMResource eq ''", stock.url.params["$filter"])
            self.assertTrue(all(r.method == "GET" for r in requests))

    async def test_sd_reads_in_both_routes(self):
        for public in (False, True):
            _, server, requests = self.server(public)
            for name, args in SD_CASES:
                with self.subTest(public=public, tool=name):
                    result = await self.call(server, name, **args)
                    self.assertEqual(result["status"], "ok", result)
            order = next(r for r in requests if r.url.path.endswith("/A_SalesOrder"))
            self.assertIn("SalesOrganization eq '1000'", order.url.params["$filter"])
            partner = next(r for r in requests if r.url.path.endswith("/A_OutbDeliveryPartner"))
            self.assertEqual(partner.url.params["$filter"], "SDDocument eq '100'")
            self.assertTrue(all(r.method == "GET" for r in requests))

    async def test_pp_reads_in_both_routes(self):
        cases = [
            ("search_production_orders", {"plant": "1010"}), ("get_production_order", {"production_order": "100"}),
            ("search_process_orders", {"plant": "1010"}), ("get_process_order", {"process_order": "100"}),
            ("search_planned_orders", {"plant": "1010"}), ("get_planned_order", {"planned_order": "1"}),
            ("search_production_order_confirmations", {"production_order": "100"}),
            ("get_production_order_confirmation", {"confirmation_group": "10", "confirmation_count": "1"}),
            ("search_process_order_confirmations", {"process_order": "100"}),
            ("get_process_order_confirmation", {"confirmation_group": "10", "confirmation_count": "1"}),
            ("search_bills_of_material", {"material": "M1", "plant": "1010"}),
            ("get_bill_of_material", {"bill_of_material": "1", "material": "M1", "plant": "1010", "variant": "01"}),
            ("search_production_routings", {"plant": "1010"}),
            ("get_production_routing", {"routing_group": "1", "routing": "1", "internal_version": "1"}),
            ("search_work_centers", {"plant": "1010"}), ("get_work_center", {"work_center_internal_id": "1", "work_center_type": "A"}),
            ("search_production_versions", {"material": "M1", "plant": "1010"}),
            ("get_production_version", {"material": "M1", "plant": "1010", "production_version": "0001"}),
            ("search_planned_independent_requirements", {"material": "M1", "plant": "1010"}),
            ("get_planned_independent_requirement", {"material": "M1", "plant": "1010", "requirement_type": "VSF", "version": "00"}),
            ("search_master_recipes", {"plant": "1010"}), ("get_master_recipe", {"recipe_group": "1", "recipe": "1", "internal_version": "1"}),
        ]
        for public in (False, True):
            c, s, requests = self.server(public)
            for name, args in cases:
                with self.subTest(public=public, tool=name):
                    d = await self.call(s, name, **args)
                    self.assertEqual(d["status"], "ok", d)
                    self.assertEqual(d.get("header", d["items"][0])["TotalQuantity"], "0.000")
                    self.assertIs(d.get("header", d["items"][0])["MaterialCompIsAlternativeItem"], False)
            self.assertTrue(all(r.method == "GET" for r in requests))
            self.assertTrue(c.is_v4("work_center"))
            self.assertTrue(c.is_v4("planned_order"))
            self.assertIn("v=0003", c.services["production_routing"][0]) if public else self.assertNotIn("v=", c.services["production_routing"][0])
            bom = next(r for r in requests if r.url.path.endswith("/MaterialBOMItem"))
            self.assertIn("HeaderChangeDocument eq ''", bom.url.params["$filter"])
            pir = next(r for r in requests if r.url.path.endswith("/PlannedIndepRqmtItem"))
            for field in ("MRPArea", "RequirementPlan", "RequirementSegment"):
                self.assertIn(field + " eq ''", pir.url.params["$filter"])

    async def test_complete_key_and_partial_child_reads(self):
        def handler(r):
            entity = r.url.path.rsplit("/", 1)[-1]
            if entity == "A_ProductionOrderOperation_2":
                return httpx.Response(403, json={"error": {"message": "Denied"}})
            return httpx.Response(200, json={"d": {"results": [{"ManufacturingOrder": "100", "TotalQuantity": "0"}]}})
        _, s, _ = self.server(handler=handler)
        d = await self.call(s, "get_production_order", production_order="100")
        self.assertEqual(d["status"], "partial")
        self.assertEqual(d["operations"]["http_status"], 403)
        self.assertEqual(d["header"]["TotalQuantity"], "0")
        self.assertTrue(d["items"])
        def ambiguous(r):
            return httpx.Response(200, json={"d": {"results": [{"Key": "1"}, {"Key": "2"}]}})
        _, s, requests = self.server(handler=ambiguous)
        d = await self.call(s, "get_production_routing", routing_group="1", routing="1", internal_version="1")
        self.assertEqual(d["error_type"], "ValidationError")
        self.assertEqual(len(requests), 1)

    async def test_pp_invalid_scope_and_page_never_calls_sap(self):
        _, s, requests = self.server()
        for name, args in [("search_production_orders", {"plant": ""}),
                           ("get_work_center", {"work_center_internal_id": "1", "work_center_type": ""}),
                           ("get_planned_order", {"planned_order": "1", "offset": -1})]:
            d = await self.call(s, name, **args)
            self.assertEqual(d["error_type"], "ValidationError")
        self.assertEqual(requests, [])


class StandardRFC(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "private_cloud/rfc"))
        import core.app as app
        from tools.sd import sales
        from tools.pp import production
        from tools import fi, co, qm, wm
        cls.app, cls.sales, cls.fi, cls.co, cls.qm, cls.wm = app, sales, fi, co, qm, wm
        cls.production = production

    def connected(self):
        from types import SimpleNamespace
        return patch.object(self.app, "sap_rfc", SimpleNamespace(is_connected=True))

    async def test_asset_master_reads_request_data_and_use_standard_detail(self):
        from connectors.sap_rfc_connector import READ_ONLY_FUNCTIONS
        assets = [{"ASSET": "000000000123", "SUBNUMBER": "0000"},
                  {"ASSET": "000000000124", "SUBNUMBER": "0000"}]
        with self.connected(), patch.object(self.app, "call_rfc", return_value={"GENERALDATA": assets}) as call:
            data = await self.fi.search_fixed_assets("1000", max_results=1, offset=1)
            self.assertEqual(call.call_args.args, ("BAPI_FIXEDASSET_GETLIST",))
            self.assertEqual(call.call_args.kwargs["REQUESTEDTABLESX"], {"GENERALDATA": "X"})
            self.assertEqual(data["data"]["GENERALDATA"], [assets[1]])
            self.assertEqual(data["paging"]["GENERALDATA"]["total"], 2)
            await self.fi.get_fixed_asset("1000", "123", "0")
            self.assertEqual(call.call_args.args, ("BAPI_FIXEDASSET_GETDETAIL",))
        self.assertIn("BAPI_FIXEDASSET_GETDETAIL", READ_ONLY_FUNCTIONS)
        self.assertNotIn("BAPI_FIXEDASSET_GETDETAIL1", READ_ONLY_FUNCTIONS)

    async def test_asset_selected_values_keys_amounts_and_empty_echo(self):
        from decimal import Decimal
        values = [{"ASSET": "000000000123", "SUBNUMBER": "0000", "AREA": "01", "FISC_YEAR": "2026",
                   "CURRENT_NBV": Decimal("0.00"), "DEPR_CURR_YEAR": Decimal("12.30"), "CURRENCY": "CNY"}]
        with self.connected(), patch.object(self.app, "call_rfc", return_value={"DEPRECIATIONAREAVALS": values}) as call:
            data = await self.fi.get_fixed_asset_values("1000", "123", "0", "1", "2026-10-23")
            self.assertEqual(data["data"]["DEPRECIATIONAREAVALS"][0]["CURRENT_NBV"], "0.00")
            self.assertEqual(data["data"]["DEPRECIATIONAREAVALS"][0]["DEPR_CURR_YEAR"], "12.30")
            params = call.call_args.kwargs
            self.assertEqual(params["REQUESTEDTABLESX"], {"DEPRECIATIONAREAVALS": "X"})
            self.assertEqual(params["SELECTIONCRITERIA"], [
                {"PARAMETER": "GENERALDATA", "FIELD": "ASSET", "SIGN": "I", "OPTION": "EQ", "LOW": "000000000123"},
                {"PARAMETER": "GENERALDATA", "FIELD": "SUBNUMBER", "SIGN": "I", "OPTION": "EQ", "LOW": "0000"}])
            self.assertEqual(params["DEPRECIATIONAREA"], "01")
            self.assertEqual(params["EVALUATIONDATE"], "20261023")
            call.return_value = {"SELECTIONCRITERIA": params["SELECTIONCRITERIA"], "DEPRECIATIONAREAVALS": []}
            data = await self.fi.get_fixed_asset_values("1000", "123", "0", "1", "2026-10-23")
            self.assertEqual(data["status"], "not_found")
            self.assertNotIn("SELECTIONCRITERIA", data["data"])
            call.return_value["RETURN"] = {"TYPE": "E", "MESSAGE": "Not authorized"}
            self.assertEqual((await self.fi.get_fixed_asset_values("1000", "123", "0", "1", "2026-10-23"))["status"], "error")
            count = call.call_count
            self.assertEqual((await self.fi.search_fixed_asset_values("1000", "AB", "2026-10-23"))["error_type"], "ValidationError")
            self.assertEqual(call.call_count, count)

    async def test_gl_period_balances_keep_carryforward_currency_and_period(self):
        response = {"BALANCE_CARRIED_FORWARD": 0, "ACCOUNT_BALANCES": [
            {"FISC_YEAR": "2026", "FIS_PERIOD": "01", "BALANCE": "0.00", "CURRENCY": "CNY"},
            {"FISC_YEAR": "2026", "FIS_PERIOD": "13", "BALANCE": "123.45", "CURRENCY": "CNY"}]}
        with self.connected(), patch.object(self.app, "call_rfc", return_value=response) as call:
            data = await self.fi.get_gl_account_period_balances("1000", "100000", "2026", max_results=1, offset=1)
            self.assertEqual(call.call_args.kwargs, {"COMPANYCODE": "1000", "GLACCT": "0000100000", "FISCALYEAR": "2026", "CURRENCYTYPE": "10"})
            self.assertEqual(data["data"]["BALANCE_CARRIED_FORWARD"], 0)
            self.assertEqual(data["data"]["ACCOUNT_BALANCES"][0]["FIS_PERIOD"], "13")
            for year, currency in (("26", "10"), ("2026", "XX")):
                count = call.call_count
                self.assertEqual((await self.fi.get_gl_account_period_balances("1000", "100000", year, currency))["error_type"], "ValidationError")
                self.assertEqual(call.call_count, count)

    async def test_co_controlling_area_order_selection_and_group_intervals(self):
        with self.connected(), patch.object(self.app, "call_rfc", return_value={"HIERARCHYNODES": [{"GROUPNAME": "ROOT", "HIERLEVEL": 0}],
                    "HIERARCHYVALUES": [{"VALFROM": "000000000100", "VALTO": "000000000199"}]}) as call:
            await self.co.get_controlling_area("1000")
            self.assertEqual(call.call_args.args, ("BAPI_CONTROLLINGAREA_GETDETAIL",))
            self.assertEqual(call.call_args.kwargs, {"CONTROLLINGAREAID": "1000"})
            await self.co.search_controlling_areas()
            self.assertEqual(call.call_args.args, ("BAPI_CONTROLLINGAREA_GETLIST",))
            self.assertEqual(call.call_args.kwargs, {})
            await self.co.search_internal_orders("1000", "0100", "123")
            self.assertEqual(call.call_args.kwargs, {"CONTROLLING_AREA": "1000", "ORDER_TYPE": "0100", "RESP_COST_CENTER": "0000000123"})
            result = await self.co.get_internal_order_group("1000", "ROOT")
            self.assertEqual(call.call_args.args, ("BAPI_INTERNALORDRGRP_GETDETAIL",))
            self.assertEqual(result["data"]["HIERARCHYNODES"][0]["HIERLEVEL"], 0)
            self.assertEqual(result["data"]["HIERARCHYVALUES"][0]["VALTO"], "000000000199")
            await self.co.search_profit_centers("1000", "2026-10-23")
            self.assertEqual(call.call_args.kwargs, {"CONTROLLINGAREA": "1000", "DATE": "20261023", "PERSONINCHARGE": "%", "IN_CHARGE_USER": "%"})
            await self.co.search_cost_center_groups("1000")
            self.assertEqual(call.call_args.kwargs, {"CONTROLLINGAREAMASK": "1000", "GROUPNAMEMASK": "*"})
            count = call.call_count
            self.assertEqual((await self.co.search_internal_orders(""))["error_type"], "ValidationError")
            self.assertEqual(count, call.call_count)

    async def test_pp_confirmation_offset_and_complete_confirmation_keys(self):
        with self.connected(), patch.object(self.app, "call_rfc", return_value={"CONFIRMATIONS": [{"COUNTER": "1"}, {"COUNTER": "2"}]}) as call:
            for fn in (self.production.search_production_order_confirmations, self.production.search_process_order_confirmations):
                result = await fn("100", max_results=1, offset=1)
                self.assertEqual(result["data"]["CONFIRMATIONS"], [{"COUNTER": "2"}])
                self.assertEqual(call.call_args.kwargs["ORDER_RANGE"], [{"SIGN": "I", "OPTION": "EQ", "LOW": "000000000100"}])
            for fn in (self.production.get_production_order_confirmation, self.production.get_process_order_confirmation):
                result = await fn("123", "1", max_results=1, offset=1)
                self.assertEqual(result["data"]["CONFIRMATIONS"], [{"COUNTER": "2"}])
                self.assertEqual(call.call_args.kwargs, {"CONFIRMATION": "0000000123", "CONFIRMATIONCOUNTER": "00000001"})
            await self.production.get_process_order("100")
            self.assertEqual(call.call_args.kwargs["ORDER_OBJECTS"]["PHASES"], "X")

    async def test_native_tables_zero_partial_and_offsets(self):
        from decimal import Decimal
        response = {"RETURN": [{"TYPE": "E", "ID": "AUTH", "NUMBER": "001", "MESSAGE": "Read denied"}],
                    "ITEMS": [{"KEY": "1", "QTY": Decimal("0.000"), "UNIT": "EA"}, {"KEY": "2", "QTY": 0}],
                    "OTHER": [{"KEY": "X"}], "HEADER": [{"ORDER": "100"}]}
        with self.connected(), patch.object(self.app, "call_rfc", return_value=response):
            result = self.app.read_bapi("BAPI_WHSE_TO_GET_DETAIL", {}, 1, 1)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["data"]["ITEMS"], [{"KEY": "2", "QTY": 0}])
        self.assertEqual(result["paging"]["ITEMS"]["offset"], 1)
        self.assertEqual(result["paging"]["ITEMS"]["total"], 2)
        self.assertEqual(result["data"]["HEADER"], [{"ORDER": "100"}])
        with self.connected(), patch.object(self.app, "call_rfc", return_value={"ITEMS": [{"QTY": 0}]}):
            self.assertEqual(self.app.read_bapi("BAPI_WHSE_TO_GET_DETAIL", {})["status"], "ok")
        with self.connected(), patch.object(self.app, "call_rfc", return_value={"RETURN": response["RETURN"]}):
            self.assertEqual(self.app.read_bapi("BAPI_WHSE_TO_GET_DETAIL", {})["status"], "error")
        with self.connected(), patch.object(self.app, "call_rfc") as call:
            self.assertEqual(self.app.read_bapi("BAPI_WHSE_TO_GET_DETAIL", {}, 0)["error_type"], "ValidationError")
            call.assert_not_called()

    async def test_sales_order_keeps_status_items_and_separates_details(self):
        from types import SimpleNamespace
        old = [{"ITM_NUMBER": "000010", "REQ_QTY": 0, "CURRENCY": "CNY"}]
        with self.connected(), patch.object(self.sales, "sap_rfc", SimpleNamespace(is_connected=True)), \
             patch.object(self.sales, "call_rfc", return_value={"STATUSINFO": old}), \
             patch.object(self.app, "call_rfc", return_value={"ORDER_HEADERS_OUT": [{"DOC_NUMBER": "0000000100", "SD_DOC_CAT": "C"}], "ORDER_ITEMS_OUT": [{"NET_VALUE": 0}]}) as detail:
            result = await self.sales.get_sales_order("100")
        self.assertEqual(result["items"], old)
        self.assertEqual(result["details"]["data"]["ORDER_ITEMS_OUT"][0]["NET_VALUE"], 0)
        self.assertEqual(detail.call_args.kwargs["SALES_DOCUMENTS"], [{"VBELN": "0000000100"}])
        self.assertEqual(detail.call_args.kwargs["I_BAPI_VIEW"]["SDSCHEDULE"], "X")

    async def test_sales_search_batches_categories_before_counts_and_limit(self):
        from types import SimpleNamespace
        candidates = [{"SD_DOC": number, "ITM_NUMBER": item, "DOC_TYPE": kind, "NET_VALUE": 0}
                      for number, item, kind in (("0000000999", "000010", "OR"),
                                                ("0000000998", "000010", "ZRET"),
                                                ("0000000100", "000010", "ZANY"),
                                                ("0000000100", "000020", "ZANY"),
                                                ("0000000099", "000010", "ZNEW"))]
        headers = [{"DOC_NUMBER": number, "SD_DOC_CAT": category} for number, category in
                   (("0000000999", "L"), ("0000000998", "H"), ("0000000100", "C"), ("0000000099", "C"))]
        with patch.object(self.sales, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(
                self.sales, "call_rfc", side_effect=[{"SALES_ORDERS": candidates}, {"ORDER_HEADERS_OUT": headers}]) as call:
            result = await self.sales.search_sales_orders("CUST01", "1000", max_results=1)
        self.assertEqual(result["status"], "ok")
        self.assertEqual((result["sales_orders"], result["total"], result["returned"]), (2, 3, 1))
        self.assertTrue(result["truncated"])
        self.assertEqual(result["items"], [candidates[3]])
        self.assertEqual(call.call_count, 2)
        self.assertEqual(call.call_args.args, ("BAPISDORDER_GETDETAILEDLIST",))
        self.assertEqual(call.call_args.kwargs["I_BAPI_VIEW"], {"HEADER": "X"})
        self.assertEqual({r["VBELN"] for r in call.call_args.kwargs["SALES_DOCUMENTS"]},
                         {r["SD_DOC"] for r in candidates})

    async def test_sales_search_does_not_accept_unknown_or_unreadable_categories(self):
        from types import SimpleNamespace
        candidate = {"SALES_ORDERS": [{"SD_DOC": "0000000100", "ITM_NUMBER": "000010"}]}
        cases = [({"ORDER_HEADERS_OUT": [{"DOC_NUMBER": "0000000100", "SD_DOC_CAT": "L"}]}, "not_found"),
                 ({"ORDER_HEADERS_OUT": []}, "error"),
                 ({"ORDER_HEADERS_OUT": [{"DOC_NUMBER": "0000000100"}]}, "error"),
                 ({"RETURN": {"TYPE": "E", "MESSAGE": "No authorization"}}, "error"),
                 (RuntimeError("Category read failed"), "error")]
        for response, expected in cases:
            with self.subTest(response=response), patch.object(self.sales, "sap_rfc", SimpleNamespace(is_connected=True)), \
                 patch.object(self.sales, "call_rfc", side_effect=[candidate, response]):
                result = await self.sales.search_sales_orders("CUST01", "1000")
            self.assertEqual(result["status"], expected)
            self.assertEqual(result.get("items", []), [])
            if "total" in result: self.assertEqual(result["total"], 0)

    async def test_sales_detail_rejects_other_or_unknown_categories_without_exposing_data(self):
        from types import SimpleNamespace
        for category in ("L", "H", "K", ""):
            with self.subTest(category=category), self.connected(), \
                 patch.object(self.sales, "sap_rfc", SimpleNamespace(is_connected=True)), \
                 patch.object(self.sales, "call_rfc", return_value={"STATUSINFO": [{"ITM_NUMBER": "000010", "NET_VALUE": 0}]}), \
                 patch.object(self.app, "call_rfc", return_value={
                     "ORDER_HEADERS_OUT": [{"DOC_NUMBER": "0020000418", "SD_DOC_CAT": category}],
                     "ORDER_ITEMS_OUT": [{"NET_VALUE": 123}]}):
                result = await self.sales.get_sales_order("20000418")
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["expected_document_category"], "C")
            self.assertEqual(result["document_category"], category or None)
            self.assertEqual(result["error_type"], "UnexpectedDocumentCategory" if category else "DocumentCategoryUnavailable")
            self.assertEqual(result["items"], [])
            self.assertNotIn("details", result)

    async def test_fi_co_wm_compound_keys_dates_and_invalid_scope(self):
        with self.connected(), patch.object(self.app, "call_rfc", return_value={"DATA": [{"KEY": "1"}]}) as call:
            await self.fi.get_fixed_asset("1000", "123", "0")
            self.assertEqual(call.call_args.kwargs, {"COMPANYCODE": "1000", "ASSET": "000000000123", "SUBNUMBER": "0000"})
            await self.fi.search_supplier_open_items("1000", "123", "2026-10-23")
            self.assertEqual(call.call_args.kwargs["KEYDATE"], "20261023")
            self.assertEqual(call.call_args.kwargs["VENDOR"], "0000000123")
            await self.co.get_cost_center("1000", "123", "2026-10-23")
            self.assertEqual(call.call_args.kwargs["COSTCENTER"], "0000000123")
            await self.wm.get_wm_transfer_order("001", "123")
            self.assertEqual(call.call_args.kwargs["TRANSFERORDERNO"], "0000000123")
            count = call.call_count
            invalid_material = await self.wm.search_wm_stock("001", "M" * 19, "1000")
            self.assertEqual(invalid_material["error_type"], "ValidationError")
            result = await self.fi.search_customer_open_items("1000", "123", "2026-02-30")
            self.assertEqual(result["error_type"], "ValidationError")
            self.assertEqual(count, call.call_count)

    async def test_qm_parent_keeps_readable_data_on_operation_failure(self):
        def read(function, **params):
            if function == "BAPI_INSPLOT_GETDETAIL": return {"GENERAL_DATA": {"INSPLOT": "000000000100"}}
            if function == "BAPI_INSPLOT_GETOPERATIONS": return {"INSPOPER_LIST": [{"INSPOPER": "0010"}]}
            return {"RETURN": {"TYPE": "E", "MESSAGE": "No permission"}}
        with self.connected(), patch.object(self.app, "call_rfc", side_effect=read) as call:
            result = await self.qm.get_inspection_lot("100", "10")
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["data"]["GENERAL_DATA"])
        self.assertEqual(result["operation_details"]["status"], "error")
        self.assertEqual(call.call_args.kwargs["INSPLOT"], "000000000100")
        self.assertEqual(call.call_args.kwargs["INSPOPER"], "0010")
        self.assertEqual(call.call_args.kwargs["READ_SAMPLE_RESULTS"], "X")


if __name__ == "__main__":
    unittest.main()
