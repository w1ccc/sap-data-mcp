"""Shared SAP read server; MM tools and domain registrations use one client."""

import logging
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

import httpx
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

# Reuse the existing dependency-free writer, without loading the RFC runtime.
from private_cloud.rfc.core.audit_log import ToolCallAuditLog
from shared.odata import APIError, ODataClient, eq, key, request_trace


READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)
LOCAL = ToolAnnotations(read_only_hint=True, open_world_hint=False)
Service = Literal[
    'material', 'supplier', 'purchase_requisition', 'purchase_order',
    'material_document', 'stock', 'supplier_invoice', 'physical_inventory',
    'reservation', 'purchasing_info_record', 'source_list', 'quota_arrangement',
    'purchase_contract', 'scheduling_agreement', 'request_for_quotation', 'supplier_quotation',
    'service_entry_sheet', 'batch', 'production_order', 'process_order',
    'planned_order', 'production_confirmation', 'process_confirmation', 'bill_of_material',
    'production_routing', 'work_center', 'production_version', 'independent_requirement',
    'master_recipe', 'sales_inquiry', 'sales_quotation', 'sales_order',
    'sales_contract', 'sales_scheduling_agreement', 'outbound_delivery', 'billing_document',
    'customer_return', 'credit_memo_request', 'debit_memo_request', 'customer',
    'ewm_warehouse', 'ewm_storage_bin', 'ewm_warehouse_order', 'ewm_warehouse_task',
    'ewm_handling_unit', 'ewm_inbound_delivery', 'ewm_outbound_delivery', 'ewm_physical_inventory',
    'ewm_stock', 'ewm_product', 'company_code', 'chart_of_accounts',
    'gl_account', 'journal_entry', 'trial_balance', 'bank',
    'fixed_asset_master', 'controlling_area', 'cost_center', 'profit_center',
    'activity_type', 'statistical_key_figure', 'co_actual_balance', 'co_plan_balance',
    'business_partner', 'supplier_organization', 'inspection_plan', 'master_inspection_characteristic',
    'inspection_method', 'quality_info_record', 'inspection_lot', 'quality_notification',
    'qm_characteristic_selected_set', 'qm_usage_decision_selected_set', 'qm_catalog', 'qm_code_group',
    'gl_line_item',
]
PrivateService = Literal[Service, "mdg_my_change_request"]


def create_server(directory: Path, public: bool):
    client = ODataClient(directory, public)
    audit = ToolCallAuditLog(directory / "logs", client.redact)
    session_id = uuid.uuid4().hex[:12]
    name = "sap_public_api" if public else "sap_private_odata"

    class MMServer(MCPServer):
        async def call_tool(self, name: str, arguments: dict[str, Any], context: Any = None) -> Any:
            requests = []
            token = request_trace.set(requests)
            started = perf_counter()
            status, error = "error", None
            try:
                result = await super().call_tool(name, arguments, context)
                data = result.structured_content or {}
                status = "error" if result.is_error else data.get("status", "ok")
                error = data.get("error_message")
                return result
            except BaseException as exc:
                error = str(exc)
                raise
            finally:
                request_trace.reset(token)
                try:
                    audit.record({"session_id": session_id, "tool": name, "arguments": arguments,
                                  "status": status, "error": error, "api_requests": requests,
                                  "duration_ms": round((perf_counter() - started) * 1000)})
                except Exception:
                    logging.getLogger(__name__).exception("Could not write the tool call audit log.")

    mcp = MMServer(name, version="0.2.0", instructions=(
        "Read-only standard SAP business APIs. Credentials are local configuration, "
        "never Tool arguments. Run test_sap_api_connection for a selected service before using it. "
        "Searches require business filters. Use native returned keys, including leading zeros. "
        "Use offset and max_results for paging. "
        "API availability and permissions depend on the SAP release and communication setup."
    ))

    def read_tool(function):
        @wraps(function)
        async def guarded(*args, **kwargs):
            try:
                return await function(*args, **kwargs)
            except ValueError as error:
                return client.failure(APIError(str(error), error_type="ValidationError"))
            except (APIError, httpx.HTTPError, OSError) as error:
                return client.failure(error)
        return mcp.tool(annotations=READ_ONLY)(guarded)

    def filters_for(**values):
        return [eq(field, value) for field, value in values.items() if value]

    def year_key(value):
        value = key(value, "fiscal_year", 4)
        if len(value) != 4 or not value.isdigit():
            raise ValueError("fiscal_year must have four digits.")
        return value

    def date_filters(field, date_from, date_to):
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d")
            end = datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Provide both dates as YYYY-MM-DD.") from None
        if not timedelta(0) <= end - start <= timedelta(days=366):
            raise ValueError("Dates must be ordered and at most 366 days apart.")
        return [f"{field} ge datetime'{start:%Y-%m-%d}T00:00:00'", f"{field} le datetime'{end:%Y-%m-%d}T00:00:00'"]

    async def document(service, number, field, max_results, offset, extra_filters=None):
        if not 1 <= max_results <= 500 or offset < 0:
            raise ValueError("max_results must be 1-500 and offset must be non-negative.")
        header_entity, item_entity = client.services[service][1:3]
        filters = [eq(field, number), *(extra_filters or [])]
        header = await client.rows(service, header_entity, filters, 1)
        if not header["items"]:
            return {**header, "header": {}, "items": []}
        try:
            result = await client.rows(service, item_entity, filters, max_results, offset)
            result["header"] = header["items"][0]
            # The document exists even when it has no returned items.
            result["status"] = "ok"
            return result
        except (APIError, httpx.HTTPError) as error:
            return {**client.failure(error), "status": "partial", "header": header["items"][0], "items": []}

    async def record(service, filters, collections=(), max_results=100, offset=0, select=None):
        """Read a complete business key and independently paged, code-fixed child views."""
        if not 1 <= max_results <= 500 or offset < 0:
            raise ValueError("max_results must be 1-500 and offset must be non-negative.")
        result = await client.rows(service, client.services[service][1], filters, 1, select=select)
        if result["truncated"]:
            raise ValueError("The supplied key matched multiple records; provide the complete SAP key/version.")
        result["header"] = result["items"][0] if result["items"] else {}
        if not result["header"]:
            return result
        for field, entity, child_filters in collections:
            try:
                view = await client.rows(service, entity, child_filters, max_results, offset)
                if field == "items":
                    result.update({k: v for k, v in view.items() if k != "status"})
                else:
                    result[field] = view
            except (APIError, httpx.HTTPError) as error:
                if field == "items":
                    result.update(items=[], returned=0, items_error=client.failure(error))
                else:
                    result[field] = client.failure(error)
                result["status"] = "partial"
        return result

    @mcp.tool(annotations=LOCAL)
    def health_check() -> dict[str, Any]:
        """Check the local MCP process; does not connect to SAP."""
        return {"status": "ok", "server": name}

    @mcp.tool(annotations=LOCAL)
    def get_server_info() -> dict[str, Any]:
        """Show this provider's fixed API versions and whether local connection configuration is complete."""
        try:
            client._configuration()
            configured = True
        except APIError:
            configured = False
        return {"status": "ok", "server": name, "version": "0.2.0", "configured": configured,
                "metadata_verified_services": sorted(client.verified_services),
                "services": {service: value[0] for service, value in client.services.items()},
                "service_catalog": {service: {"protocol": "OData V4" if client.is_v4(service) else "OData V2",
                                              "service": value[0], "entities": list(value[1:])}
                                    for service, value in client.services.items()}}

    @read_tool
    async def test_sap_api_connection(service: (Service if public else PrivateService) = "material") -> dict[str, Any]:
        """Read one standard API's $metadata over verified HTTPS. No business writes or login retry.

        This confirms only the selected service. Each API must be activated and
        authorized separately; availability of one does not prove the others.
        """
        return await client.metadata(service)

    @mcp.tool(annotations=LOCAL)
    def get_tool_call_log(max_results: int = 50, tool: str = "", status: str = "") -> dict[str, Any]:
        """Read this provider's recent local Tool audit entries, newest first (1-500)."""
        entries = audit.read_recent(max(1, min(500, max_results)), tool, status)
        return {"status": "ok", "returned": len(entries), "entries": entries}

    @read_tool
    async def search_materials(
        material: str = "", description: str = "", language: str = "EN",
        max_results: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        """Search exact material numbers or material descriptions using the standard Product API.

        Provide material and/or description. description is a case-insensitive
        substring in the requested language, not a wildcard expression. API keys
        use SAP's external representation; preserve returned leading zeros.
        """
        material = key(material, "material", 40) if material.strip() else ""
        description = key(description, "description", 40) if description.strip() else ""
        if not (material or description):
            raise ValueError("Provide material and/or description.")
        filters = filters_for(Product=material)
        entity = client.services["material"][1]
        if description:
            entity = client.services["material"][2]
            filters.append(eq("Language", key(language, "language", 2).upper()))
            text = description.lower().replace("'", "''")
            filters.append(f"contains(tolower(ProductDescription),'{text}')" if client.is_v4("material")
                           else f"substringof('{text}',tolower(ProductDescription))")
        return await client.rows("material", entity, filters, max_results, offset)

    @read_tool
    async def get_material(material: str, plant: str = "") -> dict[str, Any]:
        """Read basic material master fields; optionally read its plant data. Stock is a separate Tool."""
        material = key(material, "material", 40)
        plant = key(plant, "plant", 4) if plant.strip() else ""
        result = await client.rows("material", client.services["material"][1], [eq("Product", material)], 1)
        if plant and result["items"]:
            try:
                result["plant_data"] = await client.rows("material", client.services["material"][3],
                                                         filters_for(Product=material, Plant=plant), 1)
                if result["plant_data"]["status"] != "ok":
                    result["status"] = "partial"
            except (APIError, httpx.HTTPError) as error:
                result.update(status="partial", plant_data=client.failure(error))
        return result

    @read_tool
    async def search_suppliers(supplier: str = "", name: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search standard supplier master data by exact supplier or case-insensitive name substring."""
        supplier = key(supplier, "supplier", 10) if supplier.strip() else ""
        name = key(name, "name", 80) if name.strip() else ""
        if not (supplier or name):
            raise ValueError("Provide supplier and/or name.")
        filters = filters_for(Supplier=supplier)
        if name:
            filters.append("substringof('" + name.lower().replace("'", "''") + "',tolower(SupplierName))")
        return await client.rows("supplier", "A_Supplier", filters, max_results, offset)

    @read_tool
    async def get_supplier(supplier: str) -> dict[str, Any]:
        """Read one standard supplier master record; no bank, company or purchasing-organization expansion."""
        return await client.rows("supplier", "A_Supplier", [eq("Supplier", key(supplier, "supplier", 10))], 1)

    @read_tool
    async def search_purchase_requisitions(
        plant: str = "", material: str = "", purchasing_group: str = "",
        include_deleted: bool = False, max_results: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        """List standard purchase requisition items scoped by plant, exact material or purchasing group.

        Deleted items are excluded by default. Other processing statuses are
        included; this Tool does not imply that returned items are still open.
        """
        plant = key(plant, "plant", 4) if plant.strip() else ""
        material = key(material, "material", 40) if material.strip() else ""
        purchasing_group = key(purchasing_group, "purchasing_group", 3) if purchasing_group.strip() else ""
        if not (plant or material or purchasing_group):
            raise ValueError("Provide plant, material or purchasing_group.")
        filters = filters_for(Plant=plant, Material=material, PurchasingGroup=purchasing_group)
        if not include_deleted:
            filters.append("IsDeleted eq false" if client.is_v4("purchase_requisition") else "IsDeleted eq ''")
        return await client.rows("purchase_requisition", client.services["purchase_requisition"][2], filters, max_results, offset)

    @read_tool
    async def get_purchase_requisition(purchase_requisition: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a standard purchase requisition's header and paged items; no account, address or text expansion."""
        return await document("purchase_requisition", key(purchase_requisition, "purchase_requisition", 10),
                              "PurchaseRequisition", max_results, offset)

    @read_tool
    async def search_purchase_orders(
        supplier: str = "", purchasing_org: str = "", purchasing_group: str = "", company_code: str = "",
        max_results: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        """Search standard purchase order headers by supplier, purchasing organization/group or company code.

        At least one filter is required. This returns headers, not item matches;
        use get_purchase_order to read the items of a returned document.
        """
        supplier = key(supplier, "supplier", 10) if supplier.strip() else ""
        purchasing_org = key(purchasing_org, "purchasing_org", 4) if purchasing_org.strip() else ""
        purchasing_group = key(purchasing_group, "purchasing_group", 3) if purchasing_group.strip() else ""
        company_code = key(company_code, "company_code", 4) if company_code.strip() else ""
        filters = filters_for(Supplier=supplier, PurchasingOrganization=purchasing_org,
                              PurchasingGroup=purchasing_group, CompanyCode=company_code)
        if not filters:
            raise ValueError("Provide supplier, purchasing_org, purchasing_group or company_code.")
        return await client.rows("purchase_order", client.services["purchase_order"][1], filters, max_results, offset)

    @read_tool
    async def get_purchase_order(purchase_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a standard purchase order's header and paged items; no history, conditions or schedule expansion."""
        return await document("purchase_order", key(purchase_order, "purchase_order", 10), "PurchaseOrder", max_results, offset)

    @read_tool
    async def get_purchase_order_history(purchase_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read material-document items and MM invoice items referencing one PO, with separate paging.

        Uses the released material-document and invoice APIs. This is a reference
        lookup, not an EKBE history replica: no delivery costs, FI clearing or
        payment status is inferred. Unavailable views are reported explicitly.
        """
        number = key(purchase_order, "purchase_order", 10)
        result = {"status": "not_found", "purchase_order": number}
        for field, service, entity in (("goods_movements", "material_document", "A_MaterialDocumentItem"),
                                       ("invoice_items", "supplier_invoice", "A_SuplrInvcItemPurOrdRef")):
            try:
                result[field] = await client.rows(service, entity, [eq("PurchaseOrder", number)], max_results, offset)
            except (APIError, httpx.HTTPError) as error:
                result[field] = client.failure(error)
        statuses = [result[field]["status"] for field in ("goods_movements", "invoice_items")]
        result["status"] = ("error" if all(s == "error" for s in statuses) else "partial" if "error" in statuses
                            else "ok" if "ok" in statuses else "not_found")
        return result

    @read_tool
    async def search_material_documents(
        plant: str = "", material: str = "", storage_location: str = "", movement_type: str = "", purchase_order: str = "",
        posting_date_from: str = "", posting_date_to: str = "", max_results: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        """Search standard IM goods movement items (receipts, issues, transfers, reversals).

        Provide plant, material or purchase_order. Both posting dates are required
        (YYYY-MM-DD), at most 366 days apart. This never posts or reverses goods.
        """
        filters = filters_for(
            Plant=key(plant, "plant", 4) if plant.strip() else "",
            Material=key(material, "material", 40) if material.strip() else "",
            PurchaseOrder=key(purchase_order, "purchase_order", 10) if purchase_order.strip() else "",
        )
        if not filters:
            raise ValueError("Provide plant, material or purchase_order.")
        for field, value, length in (("StorageLocation", storage_location, 4), ("GoodsMovementType", movement_type, 3)):
            if value.strip():
                filters.append(eq(field, key(value, field, length)))
        filters.extend(date_filters("PostingDate", posting_date_from, posting_date_to))
        return await client.rows("material_document", "A_MaterialDocumentItem", filters, max_results, offset)

    @read_tool
    async def get_material_document(material_document: str, year: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a standard IM material document's header and paged items using document number and year."""
        year = key(year, "year", 4)
        if len(year) != 4 or not year.isdigit():
            raise ValueError("year must have four digits.")
        return await document("material_document", key(material_document, "material_document", 10),
                              "MaterialDocument", max_results, offset, [eq("MaterialDocumentYear", year)])

    @read_tool
    async def get_material_stock(
        plant: str, material: str = "", storage_location: str = "", batch: str = "", inventory_stock_type: str = "",
        max_results: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        """Read standard IM stock by plant, optionally material, storage location, batch and stock type.

        Returns SAP InventoryStockType/InventorySpecialStockType codes, quantity,
        base unit and accounting dimensions. No EWM bins, MD04 totals or synthetic
        stock totals are included. Zero quantities are preserved. Results are paged.
        """
        filters = filters_for(
            Plant=key(plant, "plant", 4),
            Material=key(material, "material", 40) if material.strip() else "",
            StorageLocation=key(storage_location, "storage_location", 4) if storage_location.strip() else "",
            Batch=key(batch, "batch", 10) if batch.strip() else "",
            InventoryStockType=key(inventory_stock_type, "inventory_stock_type", 2) if inventory_stock_type.strip() else "",
        )
        return await client.rows("stock", "A_MatlStkInAcctMod", filters, max_results, offset)

    @read_tool
    async def search_supplier_invoices(
        supplier: str, document_date_from: str, document_date_to: str,
        max_results: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        """Search MM supplier invoice headers by invoicing party and document-date range.

        Both dates are required (YYYY-MM-DD), at most 366 days apart. Dates are
        invoice document dates, not posting or payment dates. Includes SAP's
        returned invoice statuses; no payment or FI clearing inference is made.
        """
        filters = [eq("InvoicingParty", key(supplier, "supplier", 10))]
        filters.extend(date_filters("DocumentDate", document_date_from, document_date_to))
        return await client.rows("supplier_invoice", "A_SupplierInvoice", filters, max_results, offset)

    @read_tool
    async def get_supplier_invoice(
        supplier_invoice: str, fiscal_year: str, max_results: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        """Read an MM supplier invoice by invoice number AND fiscal year.

        Returns header, PO-reference items, G/L account items, taxes and
        withholding taxes. Each item collection has its own paging fields and
        uses max_results/offset. Failed item views produce partial results.
        This does not read FI payment/clearing documents or infer payment status.
        """
        number = key(supplier_invoice, "supplier_invoice", 10)
        year = year_key(fiscal_year)
        result = await document("supplier_invoice", number, "SupplierInvoice", max_results, offset, [eq("FiscalYear", year)])
        if result["header"]:
            filters = filters_for(SupplierInvoice=number, FiscalYear=year)
            for field, entity in (("gl_account_items", "A_SupplierInvoiceItemGLAcct"),
                                  ("taxes", "A_SupplierInvoiceTax"), ("withholding_taxes", "A_SupplierInvoiceWhldgTax")):
                try:
                    result[field] = await client.rows("supplier_invoice", entity, filters, max_results, offset)
                except (APIError, httpx.HTTPError) as error:
                    result[field] = client.failure(error)
                    result["status"] = "partial"
        return result

    @read_tool
    async def search_physical_inventory_documents(
        plant: str, fiscal_year: str, storage_location: str = "", max_results: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        """Search standard IM physical inventory document headers by plant/year and optional storage location.

        Read the returned document with get_physical_inventory_document for
        book/count quantities and SAP's count/difference-posting status fields.
        """
        filters = filters_for(Plant=key(plant, "plant", 4), FiscalYear=year_key(fiscal_year),
                              StorageLocation=key(storage_location, "storage_location", 4) if storage_location.strip() else "")
        return await client.rows("physical_inventory", "A_PhysInventoryDocHeader", filters, max_results, offset)

    @read_tool
    async def get_physical_inventory_document(
        physical_inventory_document: str, fiscal_year: str, max_results: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        """Read a standard IM physical inventory document header and paged items by number/year.

        Preserves zero counts, book quantities and false status flags. Reads
        SAP's values only; never enters counts, starts recounts or posts differences.
        """
        return await document("physical_inventory", key(physical_inventory_document, "physical_inventory_document", 10),
                              "PhysicalInventoryDocument", max_results, offset, [eq("FiscalYear", year_key(fiscal_year))])

    @read_tool
    async def search_reservations(
        plant: str, material: str = "", requirement_date: str = "", max_results: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        """Search standard reservation items by plant, optional exact material and requirement date.

        requirement_date is an exact component requirement date (YYYY-MM-DD).
        Includes SAP's deletion, final-issue and movement-allowed flags without
        deriving an open/closed status or changing the reservation.
        """
        filters = filters_for(Plant=key(plant, "plant", 4), Product=key(material, "material", 40) if material.strip() else "")
        if requirement_date.strip():
            try:
                day = datetime.strptime(requirement_date, "%Y-%m-%d")
            except ValueError:
                raise ValueError("requirement_date must be YYYY-MM-DD.") from None
            filters.append(f"MatlCompRequirementDate eq datetime'{day:%Y-%m-%d}T00:00:00'")
        return await client.rows("reservation", "A_ReservationDocumentItem", filters, max_results, offset)

    @read_tool
    async def get_reservation(reservation: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a standard reservation header and paged items, including RecordType and SAP quantity/status fields."""
        return await document("reservation", key(reservation, "reservation", 10), "Reservation", max_results, offset)

    @read_tool
    async def search_batches(material: str, batch: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search batch master records for an exact material, optionally one exact batch. Includes dates, supplier batch and restriction flags."""
        return await client.rows("batch", "Batch", filters_for(
            Material=key(material, "material", 40), Batch=key(batch, "batch", 10) if batch.strip() else ""), max_results, offset)

    @read_tool
    async def get_batch(material: str, batch: str, batch_identifying_plant: str = "",
                        max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read batch master and paged plant assignments using material, batch and BatchIdentifyingPlant.

        Leave batch_identifying_plant empty for material-level batches; supply
        the identifying plant for plant-level batches. Empty is part of the key,
        not a wildcard. Classification characteristics are not included.
        """
        plant = key(batch_identifying_plant, "batch_identifying_plant", 4) if batch_identifying_plant.strip() else ""
        return await document("batch", key(batch, "batch", 10), "Batch", max_results, offset,
                              [eq("Material", key(material, "material", 40)), eq("BatchIdentifyingPlant", plant)])

    @read_tool
    async def search_purchasing_info_records(
        material: str = "", supplier: str = "", max_results: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        """Search purchasing info record general data by exact material or supplier. Read a record for purchasing/plant data."""
        filters = filters_for(Material=key(material, "material", 40) if material.strip() else "",
                              Supplier=key(supplier, "supplier", 10) if supplier.strip() else "")
        if not filters:
            raise ValueError("Provide material or supplier.")
        return await client.rows("purchasing_info_record", "A_PurchasingInfoRecord", filters, max_results, offset)

    @read_tool
    async def get_purchasing_info_record(purchasing_info_record: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read purchasing info record general data and paged purchasing-organization/plant records, including SAP prices/units."""
        return await document("purchasing_info_record", key(purchasing_info_record, "purchasing_info_record", 10),
                              "PurchasingInfoRecord", max_results, offset)

    @read_tool
    async def search_source_lists(plant: str, material: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read purchasing source-list records by plant and optional exact material, including validity, fixed/blocked source flags."""
        return await client.rows("source_list", "A_PurchasingSource", filters_for(
            Plant=key(plant, "plant", 4), Material=key(material, "material", 40) if material.strip() else ""), max_results, offset)

    @read_tool
    async def get_source_list(material: str, plant: str, source_list_record: str) -> dict[str, Any]:
        """Read one source-list record using all three keys: material, plant and source-list record number."""
        return await client.rows("source_list", "A_PurchasingSource", filters_for(
            Material=key(material, "material", 40), Plant=key(plant, "plant", 4),
            SourceListRecord=key(source_list_record, "source_list_record", 5)), 1)

    @read_tool
    async def search_quota_arrangements(plant: str, material: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search quota arrangement headers by plant and optional material, including validity dates."""
        return await client.rows("quota_arrangement", "A_PurchasingQuotaArrangement", filters_for(
            Plant=key(plant, "plant", 4), Material=key(material, "material", 40) if material.strip() else ""), max_results, offset)

    @read_tool
    async def get_quota_arrangement(quota_arrangement: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a quota arrangement with supplier/plant sources, quotas, base quantities and allocated quantities; no source determination."""
        return await document("quota_arrangement", key(quota_arrangement, "quota_arrangement", 10), "QuotaArrangement", max_results, offset)

    async def purchasing_headers(service, supplier, purchasing_org, purchasing_group, max_results, offset):
        filters = filters_for(Supplier=key(supplier, "supplier", 10) if supplier.strip() else "",
                              PurchasingOrganization=key(purchasing_org, "purchasing_org", 4) if purchasing_org.strip() else "",
                              PurchasingGroup=key(purchasing_group, "purchasing_group", 3) if purchasing_group.strip() else "")
        if not filters:
            raise ValueError("Provide supplier, purchasing_org or purchasing_group.")
        return await client.rows(service, client.services[service][1], filters, max_results, offset)

    @read_tool
    async def search_purchase_contracts(supplier: str = "", purchasing_org: str = "", purchasing_group: str = "",
                                        max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search standard purchase contract headers by supplier or purchasing organization/group. Uses contract API version 2."""
        return await purchasing_headers("purchase_contract", supplier, purchasing_org, purchasing_group, max_results, offset)

    @read_tool
    async def get_purchase_contract(purchase_contract: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a standard purchase contract's header and paged items, including target quantities and item prices."""
        return await document("purchase_contract", key(purchase_contract, "purchase_contract", 10), "PurchaseContract", max_results, offset)

    @read_tool
    async def search_scheduling_agreements(supplier: str = "", purchasing_org: str = "", purchasing_group: str = "",
                                           max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search purchase scheduling agreement headers by supplier or purchasing organization/group."""
        return await purchasing_headers("scheduling_agreement", supplier, purchasing_org, purchasing_group, max_results, offset)

    async def extra_view(result, field, service, entity, filters, max_results, offset):
        if result.get("header"):
            try:
                result[field] = await client.rows(service, entity, filters, max_results, offset)
            except (APIError, httpx.HTTPError) as error:
                result[field] = client.failure(error)
                result["status"] = "partial"
        return result

    @read_tool
    async def get_scheduling_agreement(scheduling_agreement: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a purchase scheduling agreement's header, items and delivery schedule lines; items and schedules page independently."""
        number = key(scheduling_agreement, "scheduling_agreement", 10)
        result = await document("scheduling_agreement", number, "SchedulingAgreement", max_results, offset)
        return await extra_view(result, "schedules", "scheduling_agreement", "A_SchAgrmtSchLine",
                                [eq("SchedulingAgreement", number)], max_results, offset)

    @read_tool
    async def search_requests_for_quotation(purchasing_org: str = "", purchasing_group: str = "",
                                            max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search RFQ headers by purchasing organization or group; no RFQ publishing or approval operation is exposed."""
        return await purchasing_headers("request_for_quotation", "", purchasing_org, purchasing_group, max_results, offset)

    @read_tool
    async def get_request_for_quotation(request_for_quotation: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read an RFQ's header, items and bidders, with independent paging for items and bidders."""
        number = key(request_for_quotation, "request_for_quotation", 10)
        result = await document("request_for_quotation", number, "RequestForQuotation", max_results, offset)
        return await extra_view(result, "bidders", "request_for_quotation", "A_RequestForQuotationBidder",
                                [eq("RequestForQuotation", number)], max_results, offset)

    @read_tool
    async def search_supplier_quotations(supplier: str = "", purchasing_org: str = "", purchasing_group: str = "",
                                          max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search supplier quotation headers by supplier or purchasing organization/group."""
        return await purchasing_headers("supplier_quotation", supplier, purchasing_org, purchasing_group, max_results, offset)

    @read_tool
    async def get_supplier_quotation(supplier_quotation: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a supplier quotation header and paged items, including prices and RFQ references returned by SAP."""
        return await document("supplier_quotation", key(supplier_quotation, "supplier_quotation", 10), "SupplierQuotation", max_results, offset)

    @read_tool
    async def search_service_entry_sheets(purchase_order: str = "", supplier: str = "",
                                          max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search lean-service entry sheet headers by purchase order or supplier, including approval and material-document references."""
        filters = filters_for(PurchaseOrder=key(purchase_order, "purchase_order", 10) if purchase_order.strip() else "",
                              Supplier=key(supplier, "supplier", 10) if supplier.strip() else "")
        if not filters:
            raise ValueError("Provide purchase_order or supplier.")
        return await client.rows("service_entry_sheet", "A_ServiceEntrySheet", filters, max_results, offset)

    @read_tool
    async def get_service_entry_sheet(service_entry_sheet: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a lean-service entry sheet header and paged service items. Classic ML81N service sheets use the RFC Tools."""
        return await document("service_entry_sheet", key(service_entry_sheet, "service_entry_sheet", 10), "ServiceEntrySheet", max_results, offset)

    from shared import pp_api
    pp_api.register(read_tool, client, record)

    from shared import sd_api
    sd_api.register(read_tool, client, record)

    from shared import wm_api
    wm_api.register(read_tool, client, record)

    from shared import fi_api
    fi_api.register(read_tool, client, record)

    from shared import co_api
    co_api.register(read_tool, client, record)

    from shared import mdg_api
    mdg_api.register(read_tool, client, record)

    from shared import qm_api
    qm_api.register(read_tool, client, record)

    return mcp
