"""Offline MM regressions: fixed APIs, real MCP dispatch, paging, auth and IM errors."""

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.mm_api import create_server
from shared.odata import ODataClient

logging.getLogger("httpx").setLevel(logging.WARNING)


class APITools(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            await client._http.aclose()
        self.temp.cleanup()

    def server(self, public=False, handler=None, config=None):
        client = ODataClient(self.directory, public)
        client.config = {"SAP_API_BASE_URL": "https://sap.example", "SAP_API_AUTH": "basic",
                         "SAP_API_USERNAME": "test-user", "SAP_API_PASSWORD": "test-password",
                         **(config or {})}
        requests = []

        def handle(request):
            requests.append(request)
            if handler:
                return handler(request)
            # Fixtures are named independently from the implementation catalog.
            entity = request.url.path.rsplit("/", 1)[-1]
            if entity in ("A_Product", "Product"):
                rows = [{"Product": "TEST_MATERIAL", "BaseUnit": "EA"}]
            elif entity in ("A_ProductPlant", "ProductPlant"):
                rows = [{"Product": "TEST_MATERIAL", "Plant": "1000"}]
            elif entity in ("A_ProductDescription", "ProductDescription"):
                rows = [{"Product": "TEST_MATERIAL", "ProductDescription": "Test part"}]
            elif entity == "A_Supplier":
                rows = [{"Supplier": "123", "SupplierName": "Test supplier"}]
            elif entity in ("A_PurchaseOrder", "PurchaseOrder"):
                rows = [{"PurchaseOrder": "4500000001", "Supplier": "123"}]
            elif entity in ("A_PurchaseOrderItem", "PurchaseOrderItem"):
                rows = [{"PurchaseOrder": "4500000001", "PurchaseOrderItem": "10", "OrderQuantity": "0.000"}]
            elif entity in ("A_PurchaseRequisitionHeader", "PurchaseReqn"):
                rows = [{"PurchaseRequisition": "10000001"}]
            elif entity in ("A_PurchaseRequisitionItem", "PurchaseReqnItem"):
                rows = [{"PurchaseRequisition": "10000001", "PurchaseRequisitionItem": "10", "IsDeleted": False if public else ""}]
            elif entity == "A_MaterialDocumentHeader":
                rows = [{"MaterialDocument": "5000000001", "MaterialDocumentYear": "2026"}]
            elif entity == "A_MaterialDocumentItem":
                rows = [{"MaterialDocument": "5000000001", "MaterialDocumentItem": "1", "QuantityInEntryUnit": "0.000"}]
            elif entity == "A_MatlStkInAcctMod":
                rows = [{"Material": "TEST_MATERIAL", "Plant": "1000", "MatlWrhsStkQtyInMatlBaseUnit": "0.000"}]
            elif entity == "A_SupplierInvoice":
                rows = [{"SupplierInvoice": "5100000001", "FiscalYear": "2026", "InvoiceGrossAmount": "0.00"}]
            elif entity in ("A_SuplrInvcItemPurOrdRef", "A_SupplierInvoiceItemGLAcct"):
                rows = [{"SupplierInvoice": "5100000001", "FiscalYear": "2026", "SupplierInvoiceItemAmount": "0.00"}]
            elif entity in ("A_SupplierInvoiceTax", "A_SupplierInvoiceWhldgTax"):
                rows = [{"SupplierInvoice": "5100000001", "FiscalYear": "2026", "TaxAmount": "0.00"}]
            elif entity == "A_PhysInventoryDocHeader":
                rows = [{"PhysicalInventoryDocument": "100000001", "FiscalYear": "2026", "Plant": "1000"}]
            elif entity == "A_PhysInventoryDocItem":
                rows = [{"PhysicalInventoryDocument": "100000001", "FiscalYear": "2026", "QuantityInUnitOfEntry": 0, "PhysicalInventoryItemIsCounted": False}]
            elif entity == "A_ReservationDocumentHeader":
                rows = [{"Reservation": "123", "GoodsMovementType": "201"}]
            elif entity == "A_ReservationDocumentItem":
                rows = [{"Reservation": "123", "ReservationItem": "1", "RecordType": "", "Product": "TEST_MATERIAL", "ResvnItmRequiredQtyInEntryUnit": "0.000", "ReservationItemIsFinallyIssued": False}]
            else:
                raise AssertionError(f"Unexpected entity: {entity}")
            v4 = "/odata4/" in request.url.path
            return httpx.Response(200, json={"value": rows} if v4 else {"d": {"results": rows}})

        client._http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        self.clients.append(client)
        with patch("shared.mm_api.ODataClient", return_value=client):
            mcp = create_server(self.directory, public)
        return client, mcp, requests

    async def call(self, server, tool_name, **arguments):
        result = await server.call_tool(tool_name, arguments)
        self.assertFalse(result.is_error, result)
        return result.structured_content

    async def test_business_tools_in_both_providers(self):
        cases = [
            ("search_materials", {"description": "part"}), ("get_material", {"material": "TEST_MATERIAL", "plant": "1000"}),
            ("search_suppliers", {"name": "supplier"}), ("get_supplier", {"supplier": "123"}),
            ("search_purchase_requisitions", {"plant": "1000"}),
            ("get_purchase_requisition", {"purchase_requisition": "10000001"}),
            ("search_purchase_orders", {"supplier": "123"}), ("get_purchase_order", {"purchase_order": "4500000001"}),
            ("search_material_documents", {"plant": "1000", "posting_date_from": "2026-10-01", "posting_date_to": "2026-10-22"}),
            ("get_material_document", {"material_document": "5000000001", "year": "2026"}),
            ("get_material_stock", {"plant": "1000"}),
            ("search_supplier_invoices", {"supplier": "123", "document_date_from": "2026-10-01", "document_date_to": "2026-10-22"}),
            ("get_supplier_invoice", {"supplier_invoice": "5100000001", "fiscal_year": "2026"}),
            ("search_physical_inventory_documents", {"plant": "1000", "fiscal_year": "2026"}),
            ("get_physical_inventory_document", {"physical_inventory_document": "100000001", "fiscal_year": "2026"}),
            ("search_reservations", {"plant": "1000", "material": "TEST_MATERIAL", "requirement_date": "2026-10-22"}),
            ("get_reservation", {"reservation": "123"}),
        ]
        for public in (False, True):
            client, server, requests = self.server(public)
            self.assertGreaterEqual(len(await server.list_tools()), 40)
            for name, args in cases:
                with self.subTest(public=public, tool=name):
                    result = await self.call(server, name, **args)
                    self.assertEqual(result["status"], "ok")
                    self.assertTrue(result["items"])
                    if name in ("get_purchase_order", "get_purchase_requisition", "get_material_document"):
                        self.assertTrue(result["header"])
                    if name == "get_supplier_invoice":
                        self.assertEqual(result["gl_account_items"]["items"][0]["SupplierInvoiceItemAmount"], "0.00")
                        self.assertEqual(result["taxes"]["items"][0]["TaxAmount"], "0.00")
                        self.assertEqual(result["withholding_taxes"]["items"][0]["TaxAmount"], "0.00")
                    if name == "get_physical_inventory_document":
                        self.assertEqual(result["items"][0]["QuantityInUnitOfEntry"], 0)
                        self.assertIs(result["items"][0]["PhysicalInventoryItemIsCounted"], False)
                    if name == "get_reservation":
                        self.assertEqual(result["items"][0]["RecordType"], "")
                        self.assertIs(result["items"][0]["ReservationItemIsFinallyIssued"], False)
            self.assertTrue(all(r.method == "GET" for r in requests))
            self.assertTrue(all(r.url.host == "sap.example" for r in requests))
            paths = {r.url.path for r in requests}
            prefix = "/sap/opu/odata4/sap/api_purchaseorder_2/srvd_a2x/sap/purchaseorder/0001/" if public else "/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV/"
            self.assertIn(prefix + ("PurchaseOrder" if public else "A_PurchaseOrder"), paths)
            pr = next(r for r in requests if r.url.path.endswith("/PurchaseReqnItem" if public else "/A_PurchaseRequisitionItem"))
            self.assertIn("IsDeleted eq false" if public else "IsDeleted eq ''", pr.url.params["$filter"])

    async def test_sourcing_and_agreement_reads_in_both_providers(self):
        # SAP entity names/keys are explicit fixtures, separate from the catalog.
        fixtures = {
            "Batch": {"Material": "123", "Batch": "B1", "BatchIdentifyingPlant": "", "BatchIsMarkedForDeletion": False},
            "BatchPlant": {"Material": "123", "Batch": "B1", "Plant": "1010", "BatchIdentifyingPlant": ""},
            "A_PurchasingInfoRecord": {"PurchasingInfoRecord": "5300000464", "Material": "123", "Supplier": "1024"},
            "A_PurgInfoRecdOrgPlantData": {"PurchasingInfoRecord": "5300000464", "PurchasingOrganization": "1000", "Plant": "1010", "NetPriceAmount": "0.00"},
            "A_PurchasingSource": {"Material": "123", "Plant": "1010", "SourceListRecord": "00001", "SourceOfSupplyIsFixed": False},
            "A_PurchasingQuotaArrangement": {"QuotaArrangement": "4731", "Plant": "1010", "Material": "123"},
            "A_PurgQuotaArrangementItem": {"QuotaArrangement": "4731", "QuotaArrangementItem": "1", "QuotaAllocatedQuantity": "0.000"},
            "A_PurchaseContract": {"PurchaseContract": "4600000001"},
            "A_PurchaseContractItem": {"PurchaseContract": "4600000001", "PurchaseContractItem": "00010"},
            "A_SchAgrmtHeader": {"SchedulingAgreement": "5500000001"},
            "A_SchAgrmtItem": {"SchedulingAgreement": "5500000001", "SchedulingAgreementItem": "00010"},
            "A_SchAgrmtSchLine": {"SchedulingAgreement": "5500000001", "ScheduleLine": "1", "ScheduleLineOrderQuantity": "0.000"},
            "A_RequestForQuotation": {"RequestForQuotation": "7000000001"},
            "A_RequestForQuotationItem": {"RequestForQuotation": "7000000001", "RequestForQuotationItem": "00010"},
            "A_RequestForQuotationBidder": {"RequestForQuotation": "7000000001", "Supplier": "1024"},
            "A_SupplierQuotation": {"SupplierQuotation": "8000000001"},
            "A_SupplierQuotationItem": {"SupplierQuotation": "8000000001", "SupplierQuotationItem": "00010"},
            "A_ServiceEntrySheet": {"ServiceEntrySheet": "43784", "PurchaseOrder": "4700000545"},
            "A_ServiceEntrySheetItem": {"ServiceEntrySheet": "43784", "ConfirmedQuantity": "0.000"},
            "A_MaterialDocumentItem": {"PurchaseOrder": "4700000545", "MaterialDocument": "4900001900", "MaterialDocumentYear": "2026"},
            "A_SuplrInvcItemPurOrdRef": {"PurchaseOrder": "4700000545", "SupplierInvoice": "5100000001", "FiscalYear": "2026"},
        }
        cases = [
            ("search_batches", {"material": "123"}), ("get_batch", {"material": "123", "batch": "B1"}),
            ("search_purchasing_info_records", {"supplier": "1024"}),
            ("get_purchasing_info_record", {"purchasing_info_record": "5300000464"}),
            ("search_source_lists", {"plant": "1010", "material": "123"}),
            ("get_source_list", {"material": "123", "plant": "1010", "source_list_record": "00001"}),
            ("search_quota_arrangements", {"plant": "1010"}), ("get_quota_arrangement", {"quota_arrangement": "4731"}),
            ("search_purchase_contracts", {"supplier": "1024"}), ("get_purchase_contract", {"purchase_contract": "4600000001"}),
            ("search_scheduling_agreements", {"purchasing_org": "1000"}), ("get_scheduling_agreement", {"scheduling_agreement": "5500000001"}),
            ("search_requests_for_quotation", {"purchasing_group": "103"}), ("get_request_for_quotation", {"request_for_quotation": "7000000001"}),
            ("search_supplier_quotations", {"supplier": "1024"}), ("get_supplier_quotation", {"supplier_quotation": "8000000001"}),
            ("search_service_entry_sheets", {"purchase_order": "4700000545"}), ("get_service_entry_sheet", {"service_entry_sheet": "43784"}),
            ("get_purchase_order_history", {"purchase_order": "4700000545"}),
        ]
        for public in (False, True):
            def handler(request):
                entity = request.url.path.rsplit("/", 1)[-1]
                self.assertIn(entity, fixtures)
                return httpx.Response(200, json={"d": {"results": [fixtures[entity]]}})
            _, server, requests = self.server(public, handler)
            for name, args in cases:
                with self.subTest(public=public, tool=name):
                    result = await self.call(server, name, **args)
                    self.assertEqual(result["status"], "ok", result)
                    if name == "get_purchase_order_history":
                        self.assertEqual(result["goods_movements"]["items"][0]["MaterialDocumentYear"], "2026")
                        self.assertEqual(result["invoice_items"]["items"][0]["FiscalYear"], "2026")
                    else:
                        self.assertTrue(result["items"])
                    if name == "get_purchasing_info_record":
                        self.assertEqual(result["items"][0]["NetPriceAmount"], "0.00")
                    if name == "get_batch":
                        self.assertIs(result["header"]["BatchIsMarkedForDeletion"], False)
                        self.assertIn("BatchIdentifyingPlant eq ''", requests[-1].url.params["$filter"])
                    if name == "get_source_list":
                        self.assertIs(result["items"][0]["SourceOfSupplyIsFixed"], False)
                        self.assertIn("SourceListRecord eq '00001'", requests[-1].url.params["$filter"])
                        self.assertIn("Material eq '123'", requests[-1].url.params["$filter"])
                        self.assertIn("Plant eq '1010'", requests[-1].url.params["$filter"])
                    if name == "get_scheduling_agreement":
                        self.assertEqual(result["schedules"]["items"][0]["ScheduleLineOrderQuantity"], "0.000")
                    if name == "get_request_for_quotation":
                        self.assertEqual(result["bidders"]["items"][0]["Supplier"], "1024")
            self.assertTrue(all(r.method == "GET" for r in requests))
            self.assertTrue(any("API_PURCHASECONTRACT_PROCESS_SRV;v=0002/" in r.url.path for r in requests))

    async def test_new_views_keep_errors_and_readable_data_distinct(self):
        def handler(request):
            entity = request.url.path.rsplit("/", 1)[-1]
            if entity in ("A_SchAgrmtSchLine", "A_SuplrInvcItemPurOrdRef"):
                return httpx.Response(403, json={"error": {"message": {"value": "No authorization"}}})
            rows = [] if entity == "A_RequestForQuotation" else [{"SchedulingAgreement": "55", "PurchaseOrder": "47"}]
            return httpx.Response(200, json={"d": {"results": rows}})
        _, server, requests = self.server(handler=handler)
        result = await self.call(server, "get_scheduling_agreement", scheduling_agreement="55")
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["items"])
        self.assertEqual(result["schedules"]["http_status"], 403)
        result = await self.call(server, "get_purchase_order_history", purchase_order="47")
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["goods_movements"]["items"])
        self.assertEqual(result["invoice_items"]["http_status"], 403)
        start = len(requests)
        result = await self.call(server, "get_request_for_quotation", request_for_quotation="7")
        self.assertEqual(result["status"], "not_found")
        self.assertEqual(len(requests) - start, 1)

    async def test_missing_filters_and_invalid_pages_do_not_call_sap(self):
        _, server, requests = self.server()
        cases = [("search_materials", {}), ("search_suppliers", {}), ("search_purchase_orders", {}),
                 ("search_purchase_requisitions", {}), ("get_material_stock", {"plant": ""}),
                 ("get_purchase_order", {"purchase_order": "4500000001", "max_results": 0}),
                 ("get_material_document", {"material_document": "1", "year": "26"}),
                 ("search_material_documents", {"plant": "1000", "posting_date_from": "2026-10-22", "posting_date_to": "2026-10-01"})]
        cases.extend([
            ("search_supplier_invoices", {"supplier": "", "document_date_from": "2026-10-01", "document_date_to": "2026-10-22"}),
            ("search_supplier_invoices", {"supplier": "123", "document_date_from": "2026-02-30", "document_date_to": "2026-10-22"}),
            ("get_supplier_invoice", {"supplier_invoice": "1", "fiscal_year": "26"}),
            ("get_supplier_invoice", {"supplier_invoice": "1", "fiscal_year": "2026", "max_results": 0}),
            ("search_physical_inventory_documents", {"plant": "", "fiscal_year": "2026"}),
            ("get_physical_inventory_document", {"physical_inventory_document": "1", "fiscal_year": "ABCD"}),
            ("search_reservations", {"plant": "1000", "requirement_date": "2026-02-30"}),
            ("get_reservation", {"reservation": ""}),
            ("search_purchasing_info_records", {}), ("search_source_lists", {"plant": ""}),
            ("search_batches", {"material": ""}), ("get_batch", {"material": "123", "batch": ""}),
            ("get_source_list", {"material": "123", "plant": "1010", "source_list_record": ""}),
            ("search_quota_arrangements", {"plant": ""}), ("get_quota_arrangement", {"quota_arrangement": "1", "offset": -1}),
            ("search_purchase_contracts", {}), ("get_purchase_contract", {"purchase_contract": "1", "max_results": 0}),
            ("search_scheduling_agreements", {}), ("search_requests_for_quotation", {}),
            ("search_supplier_quotations", {}), ("search_service_entry_sheets", {}),
            ("get_purchase_order_history", {"purchase_order": "1", "offset": -1}),
        ])
        for name, args in cases:
            result = await self.call(server, name, **args)
            self.assertEqual(result["error_type"], "ValidationError")
        self.assertEqual(requests, [])

    async def test_quote_escaping_and_backend_filters(self):
        _, server, requests = self.server()
        await self.call(server, "search_suppliers", name="O'Brian")
        self.assertEqual(requests[-1].url.params["$filter"], "substringof('o''brian',tolower(SupplierName))")
        await self.call(server, "get_material_stock", plant="1000", storage_location="0001", batch="B01", inventory_stock_type="01")
        self.assertEqual(requests[-1].url.params["$filter"], "Plant eq '1000' and StorageLocation eq '0001' and Batch eq 'B01' and InventoryStockType eq '01'")

    async def test_added_mm_filters_use_correct_properties_and_compound_keys(self):
        for public in (False, True):
            _, server, requests = self.server(public)
            await self.call(server, "search_supplier_invoices", supplier="123", document_date_from="2026-10-01", document_date_to="2026-10-22")
            self.assertEqual(requests[-1].url.params["$filter"], "InvoicingParty eq '123' and DocumentDate ge datetime'2026-10-01T00:00:00' and DocumentDate le datetime'2026-10-22T00:00:00'")
            await self.call(server, "get_supplier_invoice", supplier_invoice="5100000001", fiscal_year="2026")
            for request in requests[-5:]:
                self.assertEqual(request.url.params["$filter"], "SupplierInvoice eq '5100000001' and FiscalYear eq '2026'")
            await self.call(server, "get_physical_inventory_document", physical_inventory_document="100000001", fiscal_year="2026")
            self.assertEqual(requests[-1].url.params["$filter"], "PhysicalInventoryDocument eq '100000001' and FiscalYear eq '2026'")
            await self.call(server, "search_reservations", plant="1000", material="TEST_MATERIAL", requirement_date="2026-10-22")
            self.assertEqual(requests[-1].url.params["$filter"], "Plant eq '1000' and Product eq 'TEST_MATERIAL' and MatlCompRequirementDate eq datetime'2026-10-22T00:00:00'")

    async def test_added_mm_empty_results_and_service_errors(self):
        cases = [("search_supplier_invoices", {"supplier": "123", "document_date_from": "2026-10-01", "document_date_to": "2026-10-22"}),
                 ("get_supplier_invoice", {"supplier_invoice": "1", "fiscal_year": "2026"}),
                 ("search_physical_inventory_documents", {"plant": "1000", "fiscal_year": "2026"}),
                 ("get_physical_inventory_document", {"physical_inventory_document": "1", "fiscal_year": "2026"}),
                 ("search_reservations", {"plant": "1000"}), ("get_reservation", {"reservation": "1"})]
        for public in (False, True):
            for http_status in (200, 403):
                _, server, _ = self.server(public, handler=lambda request: httpx.Response(http_status, json={"d": {"results": []}} if http_status == 200 else {"error": {"message": "No read permission"}}))
                for name, args in cases:
                    result = await self.call(server, name, **args)
                    self.assertEqual(result["status"], "not_found" if http_status == 200 else "error")

    async def test_invoice_keeps_readable_views_when_tax_view_fails(self):
        def handler(request):
            entity = request.url.path.rsplit("/", 1)[-1]
            if entity == "A_SupplierInvoiceTax":
                return httpx.Response(403, json={"error": {"message": "Tax read denied"}})
            row = {"SupplierInvoice": "1", "FiscalYear": "2026", "SupplierInvoiceItemAmount": "0.00"}
            return httpx.Response(200, json={"d": {"results": [row]}})
        _, server, _ = self.server(handler=handler)
        result = await self.call(server, "get_supplier_invoice", supplier_invoice="1", fiscal_year="2026")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["taxes"]["http_status"], 403)
        self.assertTrue(result["gl_account_items"]["items"])
        self.assertTrue(result["withholding_taxes"]["items"])

    async def test_paging_and_decimal_precision(self):
        def handler(request):
            if "$skiptoken" not in request.url.params:
                return httpx.Response(200, json={"d": {"results": [{"Supplier": "1"}], "__next": "A_Supplier?$skiptoken=NEXT"}})
            return httpx.Response(200, content=b'{"d":{"results":[{"Supplier":"2","Amount":12345678901234567890.123},{"Supplier":"3","Amount":0}]}}')
        _, server, requests = self.server(handler=handler)
        result = await self.call(server, "search_suppliers", name="test", max_results=2)
        self.assertEqual(result["returned"], 2)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["next_offset"], 2)
        self.assertEqual(result["items"][1]["Amount"], "12345678901234567890.123")
        self.assertEqual(len(requests), 2)

    async def test_hostile_paging_link_never_receives_credentials(self):
        def handler(request):
            return httpx.Response(200, json={"d": {"results": [{"Supplier": "1"}], "__next": "https://other.example/A_Supplier"}})
        _, server, requests = self.server(handler=handler)
        result = await self.call(server, "search_suppliers", name="test")
        self.assertEqual(result["error_type"], "InvalidPagingLink")
        self.assertEqual(len(requests), 1)

    async def test_empty_collection_and_missing_service_are_distinct(self):
        responses = iter([httpx.Response(200, json={"d": {"results": []}}),
                          httpx.Response(404, json={"error": {"code": "SERVICE_NOT_FOUND", "message": {"value": "Service inactive"}}})])
        _, server, _ = self.server(handler=lambda request: next(responses))
        self.assertEqual((await self.call(server, "search_suppliers", name="test"))["status"], "not_found")
        result = await self.call(server, "search_suppliers", name="test")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "SERVICE_NOT_FOUND")

    async def test_document_keeps_header_when_items_fail(self):
        def handler(request):
            if request.url.path.endswith("/PurchaseOrder"):
                return httpx.Response(200, json={"value": [{"PurchaseOrder": "4500000001"}]})
            return httpx.Response(403, json={"error": {"message": "Missing item authorization"}})
        _, server, _ = self.server(public=True, handler=handler)
        result = await self.call(server, "get_purchase_order", purchase_order="4500000001")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["header"]["PurchaseOrder"], "4500000001")

    async def test_no_auth_retry_and_no_secrets_in_errors_or_logs(self):
        _, server, requests = self.server(handler=lambda request: httpx.Response(401, json={"error": {"message": "test-user test-password"}}))
        first = await self.call(server, "search_suppliers", name="supplier")
        second = await self.call(server, "search_suppliers", name="supplier")
        self.assertEqual(first["http_status"], 401)
        self.assertEqual(second["error_type"], "AuthenticationBlocked")
        self.assertEqual(len(requests), 1)
        log = next((self.directory / "logs").glob("*.jsonl")).read_text(encoding="utf-8")
        for secret in ("test-user", "test-password"):
            self.assertNotIn(secret, json.dumps(first) + log)

    async def test_oauth_token_is_reused_and_only_token_endpoint_receives_post(self):
        def handler(request):
            if request.url.host == "auth.example":
                self.assertEqual(request.method, "POST")
                self.assertEqual(request.content, b"grant_type=client_credentials")
                return httpx.Response(200, json={"access_token": "test-token", "expires_in": 3600, "token_type": "Bearer"})
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.headers["Authorization"], "Bearer test-token")
            return httpx.Response(200, json={"d": {"results": []}})
        _, server, requests = self.server(public=True, handler=handler, config={"SAP_API_AUTH": "oauth", "SAP_API_TOKEN_URL": "https://auth.example/token", "SAP_API_CLIENT_ID": "client-id", "SAP_API_CLIENT_SECRET": "client-secret"})
        await self.call(server, "search_suppliers", name="supplier")
        await self.call(server, "search_suppliers", name="supplier")
        self.assertEqual(sum(r.method == "POST" for r in requests), 1)

    async def test_unconfigured_public_provider_does_not_connect(self):
        _, server, requests = self.server(public=True, config={"SAP_API_BASE_URL": ""})
        result = await self.call(server, "get_material_stock", plant="1000")
        self.assertEqual(result["error_type"], "ConfigurationError")
        self.assertEqual(requests, [])

    async def test_metadata_reports_missing_entities(self):
        xml = b'<edmx:Edmx xmlns:edmx="urn:edmx" xmlns="urn:edm"><Schema><EntityContainer><EntitySet Name="Product"/></EntityContainer></Schema></edmx:Edmx>'
        _, server, _ = self.server(public=True, handler=lambda request: httpx.Response(200, content=xml))
        result = await self.call(server, "test_sap_api_connection", service="material")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["missing_entities"], ["ProductDescription", "ProductPlant"])

    async def test_mm_write_operations_remain_outside_api_allowlist(self):
        from shared.odata import APIError
        client, _, requests = self.server()
        for service, operation in (("physical_inventory", "PostDifferencesOnItem"),
                                   ("supplier_invoice", "Cancel"), ("reservation", "DeleteReservation")):
            with self.assertRaises(APIError) as failure:
                await client.get(service, operation)
            self.assertEqual(failure.exception.error_type, "OperationNotAllowed")
        self.assertEqual(requests, [])


class RFCInventory(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "private_cloud/rfc"))
        from tools.mm import inventory, purchasing
        cls.inventory, cls.purchasing = inventory, purchasing

    async def test_purchase_order_requests_and_preserves_account_assignments(self):
        assignment = {"PO_ITEM": "00010", "SERIAL_NO": "01", "ASSET_NO": "100000000005",
                      "SUB_NUMBER": "0000", "GL_ACCOUNT": "9999000000", "QUANTITY": 0}
        with patch.object(self.purchasing, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(
                self.purchasing, "call_rfc", return_value={"POHEADER": {"PO_NUMBER": "4700000716"},
                                                           "POACCOUNT": [assignment]}) as call:
            result = await self.purchasing.get_purchase_order("4700000716")
            self.assertEqual(call.call_args.kwargs["ACCOUNT_ASSIGNMENT"], "X")
            self.assertEqual(call.call_args.kwargs["PURCHASEORDER"], "4700000716")
            self.assertNotIn("POACCOUNT", call.call_args.kwargs["options"]["not_requested"])
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["account_assignments"], [assignment])

    async def test_sourcing_and_service_bapis_use_real_parameter_names(self):
        p = self.purchasing
        connected = SimpleNamespace(is_connected=True)
        with patch.object(self.inventory, "sap_rfc", connected), patch.object(self.inventory, "call_rfc", return_value={"BATCHATTRIBUTES": {"PROD_DATE": "20260101"}, "BATCHSTATUS": {"RESTRICTED": ""}}) as call:
            result = await self.inventory.get_batch("123", "B1", "1010")
            self.assertEqual(call.call_args.kwargs, {"MATERIAL": "000000000000000123", "BATCH": "B1", "PLANT": "1010"})
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["attributes"]["PROD_DATE"], "20260101")
        with patch.object(p, "sap_rfc", connected), patch.object(p, "call_rfc", return_value={
                "INFORECORD_GENERAL": [{"INFO_REC": "5300000464"}],
                "INFORECORD_PURCHORG": [{"INFO_REC": "5300000464", "NET_PRICE": 0}]}) as call:
            result = await p.get_purchasing_info_record("5300000464")
            self.assertEqual(call.call_args.kwargs["PURCHASINGINFOREC"], "5300000464")
            self.assertEqual(call.call_args.kwargs["PURCHORG_DATA"], "X")
            self.assertEqual(result["purchasing_data"]["items"][0]["NET_PRICE"], 0)
            await p.search_purchasing_info_records(material="123", supplier="1024")
            self.assertEqual(call.call_args.kwargs["MATERIAL_LONG"], "000000000000000123")
            self.assertEqual(call.call_args.kwargs["VENDOR"], "0000001024")
        with patch.object(p, "sap_rfc", connected), patch.object(p, "call_rfc", return_value={
                "ENTRYSHEET_HEADER": [{"SHEET_NO": "1", "NET_VALUE": 0}]}) as call:
            result = await p.search_service_entry_sheets("47")
            self.assertEqual(call.call_args.kwargs, {"PO_NUMBER": "0000000047"})
            self.assertEqual(result["items"][0]["NET_VALUE"], 0)
        cases = [("get_purchase_contract", "BAPI_CONTRACT_GETDETAIL", "PURCHASINGDOCUMENT", "HEADER", "NUMBER"),
                 ("get_scheduling_agreement", "BAPI_SAG_GETDETAIL", "PURCHASINGDOCUMENT", "HEADER", "NUMBER"),
                 ("get_service_entry_sheet", "BAPI_ENTRYSHEET_GETDETAIL", "ENTRYSHEET", "ENTRYSHEET_HEADER", "SHEET_NO"),
                 ("get_purchase_order_history", "BAPI_PO_GETDETAIL1", "PURCHASEORDER", "POHEADER", "PO_NUMBER")]
        for name, function, field, header, key_name in cases:
            with self.subTest(tool=name), patch.object(p, "sap_rfc", connected), patch.object(p, "call_rfc", return_value={header: {key_name: "0000000001"}}) as call:
                result = await getattr(p, name)("1")
                self.assertEqual(result["status"], "ok")
                self.assertEqual(call.call_args.args, (function,))
                self.assertEqual(call.call_args.kwargs[field], "0000000001")

    async def test_new_rfc_reads_report_empty_auth_and_offline_separately(self):
        p = self.purchasing
        cases = [("search_purchasing_info_records", {"supplier": "1024"}),
                 ("get_purchasing_info_record", {"purchasing_info_record": "1"}),
                 ("get_purchase_contract", {"purchase_contract": "1"}),
                 ("get_scheduling_agreement", {"scheduling_agreement": "1"}),
                 ("get_purchase_order_history", {"purchase_order": "1"}),
                 ("search_service_entry_sheets", {"purchase_order": "1"}),
                 ("get_service_entry_sheet", {"service_entry_sheet": "1"})]
        for name, args in cases:
            for response, expected in (({}, "not_found"), ({"RETURN": [{"TYPE": "E", "MESSAGE": "Not authorized"}]}, "error")):
                with self.subTest(tool=name, expected=expected), patch.object(p, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(p, "call_rfc", return_value=response):
                    self.assertEqual((await getattr(p, name)(**args))["status"], expected)
            with patch.object(p, "sap_rfc", SimpleNamespace(is_connected=False)), patch.object(p, "call_rfc") as call:
                self.assertEqual((await getattr(p, name)(**args))["error_type"], "RFCConnectionUnavailable")
                call.assert_not_called()

    async def test_im_query_selection_batch_and_zero_stock(self):
        inv = self.inventory
        response = {"ET_MAT_STOCK": [{"MATNR": "000000000000000123", "CHARG": "B1", "LABST": 0},
                                     {"MATNR": "000000000000000456", "CHARG": "B2", "LABST": 10}]}
        with patch.object(inv, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(inv, "call_rfc", return_value=response) as call:
            result = await inv.search_material_stock("1000", "0001", material="123", batch="B1")
            self.assertEqual(result["items"], [response["ET_MAT_STOCK"][0]])
            self.assertEqual(call.call_args.kwargs["IT_MATNR_RANGE"][0]["LOW_LONG"], "000000000000000123")
        with patch.object(inv, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(inv, "call_rfc") as call:
            result = await inv.search_material_stock("1000", "")
            self.assertEqual(result["error_type"], "ValidationError")
            call.assert_not_called()

    async def test_mm_authorization_errors_are_not_reported_as_missing_data(self):
        error = {"RETURN": [{"TYPE": "E", "ID": "AUTH", "MESSAGE": "No authorization"}]}
        for module, name, args in ((self.inventory, "get_material_document", ("1", "2026")),
                                   (self.purchasing, "get_purchase_requisition", ("1",))):
            with patch.object(module, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(module, "call_rfc", return_value=error):
                result = await getattr(module, name)(*args)
                self.assertEqual(result["status"], "error")

    async def test_mm_empty_po_and_partial_movement_results(self):
        with patch.object(self.purchasing, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(self.purchasing, "call_rfc", return_value={}):
            self.assertEqual((await self.purchasing.get_purchase_order("1"))["status"], "not_found")
        response = {"GOODSMVT_ITEMS": [{"MAT_DOC": "5000000001", "MOVE_TYPE": "101"}],
                    "RETURN": [{"TYPE": "E", "ID": "AUTH", "MESSAGE": "Some data unavailable"}]}
        with patch.object(self.inventory, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(self.inventory, "call_rfc", return_value=response):
            result = await self.inventory.search_material_documents(plant="1000", posting_date_from="2026-10-01", posting_date_to="2026-10-22")
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["returned"], 1)

    async def test_live_sap_empty_selection_messages_are_not_authorization_failures(self):
        cases = [(self.purchasing, "search_purchase_orders", {"plant": "1010"}, {"TYPE": "E", "CODE": "W5037", "MESSAGE": "No purchase orders satisfying selection criteria"}),
                 (self.inventory, "search_reservations", {"plant": "1010"}, {"TYPE": "E", "ID": "W5", "NUMBER": "027", "MESSAGE": "No reservations satisfying these selection criteria exist"})]
        for module, name, args, empty in cases:
            for messages, expected in (([empty], "not_found"), ([empty, {"TYPE": "E", "ID": "AUTH", "MESSAGE": "Denied"}], "error")):
                with self.subTest(tool=name, expected=expected), patch.object(module, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(module, "call_rfc", return_value={"RETURN": messages}):
                    self.assertEqual((await getattr(module, name)(**args))["status"], expected)

    async def test_added_document_reads_normalize_ids_and_preserve_zero(self):
        cases = [
            (self.purchasing, "get_supplier_invoice", {"supplier_invoice": "123", "fiscal_year": "2026"},
             {"HEADERDATA": {"COMP_CODE": "1000", "GROSS_AMOUNT": "0.00"}, "ITEMDATA": [{"ITEM_AMOUNT": "0.00"}], "GLACCOUNTDATA": [{"ITEM_AMOUNT": "0.00"}], "TAXDATA": [{"TAX_AMOUNT": "0.00"}]},
             "BAPI_INCOMINGINVOICE_GETDETAIL", {"INVOICEDOCNUMBER": "0000000123", "FISCALYEAR": "2026"}),
            (self.inventory, "get_physical_inventory_document", {"physical_inventory_document": "123", "fiscal_year": "2026"},
             {"HEAD": {"PHYSINVENTORY": "0000000123"}, "ITEMS": [{"QUANTITY": 0, "BOOK_QTY": 0}]},
             "BAPI_MATPHYSINV_GETDETAIL", {"PHYSINVENTORY": "0000000123", "FISCALYEAR": "2026"}),
            (self.inventory, "get_reservation", {"reservation": "123"},
             {"RESERVATION_HEADER": {"MOVE_TYPE": "201"}, "RESERVATION_ITEMS": [{"QUANTITY": 0}]},
             "BAPI_RESERVATION_GETDETAIL1", {"RESERVATION": "0000000123"}),
        ]
        for module, name, args, response, function, params in cases:
            with patch.object(module, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(module, "call_rfc", return_value=response) as call:
                result = await getattr(module, name)(**args)
                self.assertEqual(result["status"], "ok")
                call.assert_called_once_with(function, **params)
                self.assertTrue(result["items"])
                if name == "get_supplier_invoice":
                    self.assertEqual(result["gl_account_items"][0]["ITEM_AMOUNT"], "0.00")
                    self.assertEqual(result["taxes"][0]["TAX_AMOUNT"], "0.00")
                else:
                    self.assertEqual(result["items"][0]["QUANTITY"], 0)

    async def test_added_searches_send_scoped_sap_queries(self):
        from connectors.sap_rfc_connector import READ_ONLY_FUNCTIONS
        rows = [{"INV_DOC_NO": "1"}, {"INV_DOC_NO": "2"}]
        with patch.object(self.purchasing, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(self.purchasing, "call_rfc", return_value={"HEADERLIST": rows}) as call:
            result = await self.purchasing.search_supplier_invoices("123", "2026-10-01", "2026-10-22", max_results=1)
            self.assertEqual(result["returned"], 1)
            self.assertTrue(result["truncated"])
            self.assertEqual(call.call_args.kwargs, {"VENDOR_RA": [{"SIGN": "I", "OPTION": "EQ", "LOW": "0000000123"}], "DOCDATE_RA": [{"SIGN": "I", "OPTION": "BT", "LOW": "20261001", "HIGH": "20261022"}]})
        with patch.object(self.inventory, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(self.inventory, "call_rfc", return_value={"HEADERS": [{"PHYSINVENTORY": "1"}]}) as call:
            result = await self.inventory.search_physical_inventory_documents("1000", "2026", storage_location="0001")
            self.assertEqual(result["status"], "ok")
            self.assertEqual(call.call_args.kwargs["FISCALYEAR_RA"], [{"SIGN": "I", "OPTION": "EQ", "LOW": "2026"}])
            self.assertEqual(call.call_args.kwargs["STGE_LOC_RA"][0]["LOW"], "0001")
        with patch.object(self.inventory, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(self.inventory, "call_rfc", return_value={"RESERVATION_ITEMS": [{"QUANTITY": 0}]}) as call:
            result = await self.inventory.search_reservations("1000", material="123", requirement_date="2026-10-22")
            self.assertEqual(result["status"], "ok")
            self.assertEqual(call.call_args.kwargs, {"PLANT": "1000", "MATERIAL": "000000000000000123", "REQ_DATE": "20261022"})
        required = {"BAPI_INCOMINGINVOICE_GETLIST", "BAPI_INCOMINGINVOICE_GETDETAIL", "BAPI_MATPHYSINV_GETLIST", "BAPI_MATPHYSINV_GETDETAIL", "BAPI_RESERVATION_GETITEMS1", "BAPI_RESERVATION_GETDETAIL1"}
        self.assertTrue(required.issubset(READ_ONLY_FUNCTIONS))
        self.assertTrue({"BAPI_MATPHYSINV_POSTDIFF", "BAPI_MATPHYSINV_COUNT", "BAPI_RESERVATION_CHANGE", "BAPI_INCOMINGINVOICE_POST", "BAPI_TRANSACTION_COMMIT"}.isdisjoint(READ_ONLY_FUNCTIONS))

    async def test_added_rfc_empty_error_and_disconnected_results(self):
        cases = [(self.purchasing, "search_supplier_invoices", {"supplier": "123", "document_date_from": "2026-10-01", "document_date_to": "2026-10-22"}),
                 (self.purchasing, "get_supplier_invoice", {"supplier_invoice": "123", "fiscal_year": "2026"}),
                 (self.inventory, "search_physical_inventory_documents", {"plant": "1000", "fiscal_year": "2026"}),
                 (self.inventory, "get_physical_inventory_document", {"physical_inventory_document": "123", "fiscal_year": "2026"}),
                 (self.inventory, "search_reservations", {"plant": "1000"}),
                 (self.inventory, "get_reservation", {"reservation": "123"})]
        for module, name, args in cases:
            for response, expected in (({}, "not_found"), ({"RETURN": [{"TYPE": "E", "MESSAGE": "No read permission"}]}, "error")):
                with patch.object(module, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(module, "call_rfc", return_value=response):
                    self.assertEqual((await getattr(module, name)(**args))["status"], expected)
            with patch.object(module, "sap_rfc", SimpleNamespace(is_connected=False)), patch.object(module, "call_rfc") as call:
                result = await getattr(module, name)(**args)
                self.assertEqual(result["error_type"], "RFCConnectionUnavailable")
                call.assert_not_called()

    async def test_added_rfc_invalid_filters_do_not_call_sap(self):
        cases = [(self.purchasing, "search_supplier_invoices", {"supplier": "123", "document_date_from": "2026-10-22", "document_date_to": "2026-10-01"}),
                 (self.purchasing, "get_supplier_invoice", {"supplier_invoice": "1", "fiscal_year": "26"}),
                 (self.inventory, "search_physical_inventory_documents", {"plant": "", "fiscal_year": "2026"}),
                 (self.inventory, "get_physical_inventory_document", {"physical_inventory_document": "1", "fiscal_year": "ABCD"}),
                 (self.inventory, "search_reservations", {"plant": "1000", "material": "X" * 19}),
                 (self.inventory, "get_reservation", {"reservation": ""})]
        for module, name, args in cases:
            with patch.object(module, "sap_rfc", SimpleNamespace(is_connected=True)), patch.object(module, "call_rfc") as call:
                result = await getattr(module, name)(**args)
                self.assertEqual(result["error_type"], "ValidationError")
                call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
