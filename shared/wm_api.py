"""Standard WM read-only tools; native SAP data and keys are retained."""
from typing import Any
from shared.odata import eq, key, typed_eq

def register(read_tool, client, record):

    @read_tool
    async def search_ewm_warehouses(warehouse: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for ewm warehouse. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Warehouse', key(warehouse, 'warehouse', 4), 'Edm.String', client.is_v4('ewm_warehouse'))]
        return await client.rows('ewm_warehouse', 'Warehouse', filters, max_results, offset)

    @read_tool
    async def get_ewm_warehouse(warehouse: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of ewm warehouse. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Warehouse', key(warehouse, 'warehouse', 4), 'Edm.String', client.is_v4('ewm_warehouse'))]
        return await record('ewm_warehouse', filters, [('storage_types', 'WarehouseStorageType', [typed_eq('Warehouse', key(warehouse, 'warehouse', 80), 'Edm.String', client.is_v4('ewm_warehouse'))])], max_results, offset)

    @read_tool
    async def search_ewm_storage_bins(warehouse: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for ewm storage bin. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Warehouse', key(warehouse, 'warehouse', 4), 'Edm.String', client.is_v4('ewm_storage_bin'))]
        return await client.rows('ewm_storage_bin', 'WarehouseStorageBin', filters, max_results, offset)

    @read_tool
    async def get_ewm_storage_bin(warehouse: str, storage_bin: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of ewm storage bin. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Warehouse', key(warehouse, 'warehouse', 4), 'Edm.String', client.is_v4('ewm_storage_bin')), typed_eq('StorageBin', key(storage_bin, 'storage_bin', 18), 'Edm.String', client.is_v4('ewm_storage_bin'))]
        return await record('ewm_storage_bin', filters, [], max_results, offset)

    @read_tool
    async def search_ewm_warehouse_orders(warehouse: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for ewm warehouse order. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Warehouse', key(warehouse, 'warehouse', 4), 'Edm.String', client.is_v4('ewm_warehouse_order'))]
        return await client.rows('ewm_warehouse_order', 'WarehouseOrder', filters, max_results, offset)

    @read_tool
    async def get_ewm_warehouse_order(warehouse: str, warehouse_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of ewm warehouse order. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Warehouse', key(warehouse, 'warehouse', 4), 'Edm.String', client.is_v4('ewm_warehouse_order')), typed_eq('WarehouseOrder', key(warehouse_order, 'warehouse_order', 12), 'Edm.String', client.is_v4('ewm_warehouse_order'))]
        return await record('ewm_warehouse_order', filters, [('tasks', 'WarehouseTask', [typed_eq('Warehouse', key(warehouse, 'warehouse', 80), 'Edm.String', client.is_v4('ewm_warehouse_order')), typed_eq('WarehouseOrder', key(warehouse_order, 'warehouse_order', 80), 'Edm.String', client.is_v4('ewm_warehouse_order'))])], max_results, offset)

    @read_tool
    async def search_ewm_warehouse_tasks(warehouse: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for ewm warehouse task. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Warehouse', key(warehouse, 'warehouse', 4), 'Edm.String', client.is_v4('ewm_warehouse_task'))]
        return await client.rows('ewm_warehouse_task', 'WarehouseTask', filters, max_results, offset)

    @read_tool
    async def get_ewm_warehouse_task(warehouse: str, warehouse_task: str, warehouse_task_item: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of ewm warehouse task. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Warehouse', key(warehouse, 'warehouse', 4), 'Edm.String', client.is_v4('ewm_warehouse_task')), typed_eq('WarehouseTask', key(warehouse_task, 'warehouse_task', 12), 'Edm.String', client.is_v4('ewm_warehouse_task')), typed_eq('WarehouseTaskItem', key(warehouse_task_item, 'warehouse_task_item', 4), 'Edm.String', client.is_v4('ewm_warehouse_task'))]
        return await record('ewm_warehouse_task', filters, [], max_results, offset)

    @read_tool
    async def search_ewm_handling_units(warehouse: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for ewm handling unit. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Warehouse', key(warehouse, 'warehouse', 4), 'Edm.String', client.is_v4('ewm_handling_unit'))]
        return await client.rows('ewm_handling_unit', 'HandlingUnit', filters, max_results, offset)

    @read_tool
    async def get_ewm_handling_unit(handling_unit: str, warehouse: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of ewm handling unit. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('HandlingUnitExternalID', key(handling_unit, 'handling_unit', 20), 'Edm.String', client.is_v4('ewm_handling_unit')), typed_eq('Warehouse', key(warehouse, 'warehouse', 4), 'Edm.String', client.is_v4('ewm_handling_unit'))]
        return await record('ewm_handling_unit', filters, [('items', 'HandlingUnitItem', [typed_eq('HandlingUnitExternalID', key(handling_unit, 'handling_unit', 80), 'Edm.String', client.is_v4('ewm_handling_unit')), typed_eq('Warehouse', key(warehouse, 'warehouse', 80), 'Edm.String', client.is_v4('ewm_handling_unit'))])], max_results, offset)

    @read_tool
    async def search_ewm_inbound_deliveries(warehouse: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for ewm inbound delivery. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Warehouse', key(warehouse, 'warehouse', 4), 'Edm.String', client.is_v4('ewm_inbound_delivery'))]
        return await client.rows('ewm_inbound_delivery', 'WhseInboundDeliveryHead', filters, max_results, offset)

    @read_tool
    async def get_ewm_inbound_delivery(ewm_inbound_delivery: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of ewm inbound delivery. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('InboundDelivery', key(ewm_inbound_delivery, 'ewm_inbound_delivery', 10), 'Edm.String', client.is_v4('ewm_inbound_delivery'))]
        return await record('ewm_inbound_delivery', filters, [('items', 'WhseInboundDeliveryItem', [typed_eq('InboundDelivery', key(ewm_inbound_delivery, 'ewm_inbound_delivery', 80), 'Edm.String', client.is_v4('ewm_inbound_delivery'))])], max_results, offset)

    @read_tool
    async def search_ewm_outbound_deliveries(warehouse: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for ewm outbound delivery. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Warehouse', key(warehouse, 'warehouse', 4), 'Edm.String', client.is_v4('ewm_outbound_delivery'))]
        return await client.rows('ewm_outbound_delivery', 'WhseOutboundDeliveryOrderHead', filters, max_results, offset)

    @read_tool
    async def get_ewm_outbound_delivery(ewm_outbound_delivery: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of ewm outbound delivery. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('OutboundDeliveryOrder', key(ewm_outbound_delivery, 'ewm_outbound_delivery', 10), 'Edm.String', client.is_v4('ewm_outbound_delivery'))]
        return await record('ewm_outbound_delivery', filters, [('items', 'WhseOutboundDeliveryOrderItem', [typed_eq('OutboundDeliveryOrder', key(ewm_outbound_delivery, 'ewm_outbound_delivery', 80), 'Edm.String', client.is_v4('ewm_outbound_delivery'))])], max_results, offset)

    @read_tool
    async def search_ewm_physical_inventory_items(warehouse: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for ewm physical inventory item. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Warehouse', key(warehouse, 'warehouse', 4), 'Edm.String', client.is_v4('ewm_physical_inventory'))]
        return await client.rows('ewm_physical_inventory', 'WhsePhysicalInventoryItem', filters, max_results, offset)

    @read_tool
    async def get_ewm_physical_inventory_item(document_uuid: str, item: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of ewm physical inventory item. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('PhysicalInventoryDocumentUUID', key(document_uuid, 'document_uuid', 36), 'Edm.Guid', client.is_v4('ewm_physical_inventory')), typed_eq('PhysicalInventoryItemNumber', key(item, 'item', 6), 'Edm.String', client.is_v4('ewm_physical_inventory'))]
        return await record('ewm_physical_inventory', filters, [('count_items', 'WhsePhysicalInventoryCountItem', [typed_eq('PhysicalInventoryDocumentUUID', key(document_uuid, 'document_uuid', 80), 'Edm.Guid', client.is_v4('ewm_physical_inventory')), typed_eq('PhysicalInventoryItemNumber', key(item, 'item', 80), 'Edm.String', client.is_v4('ewm_physical_inventory'))])], max_results, offset)

    @read_tool
    async def search_ewm_stock(warehouse: str, product: str = "", storage_bin: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search EWM available stock; returns the complete fifteen-dimensional stock identity, quantity and unit. Not total physical stock or classic WM quants."""
        filters = [eq("EWMWarehouse", key(warehouse, "warehouse", 4))]
        if product.strip(): filters.append(eq("Product", key(product, "product", 40)))
        if storage_bin.strip(): filters.append(eq("EWMStorageBin", key(storage_bin, "storage_bin", 18)))
        return await client.rows("ewm_stock", "WarehouseAvailableStock", filters, max_results, offset)

    @read_tool
    async def get_ewm_stock(warehouse: str, product: str, batch: str = "", ewm_stock_owner: str = "", entitled_to_dispose_party: str = "", ewm_stock_type: str = "", ewm_stock_usage: str = "", stock_document_category: str = "", ewm_document_category: str = "", wbs_element_externalid: str = "", special_stock_idfg_sales_order: str = "", special_stock_idfg_sales_order_item: str = "", handling_unit_externalid: str = "", ewm_storage_bin: str = "", ewm_resource: str = "") -> dict[str, Any]:
        """Read one EWM available-stock record using ALL fifteen key dimensions. Optional blank dimensions mean exact blanks."""
        filters = [eq("EWMWarehouse", key(warehouse, "warehouse", 4)), eq("Product", key(product, "product", 40))]
        filters.append(eq('Batch', key(batch, 'batch', 80) if batch.strip() else ""))
        filters.append(eq('EWMStockOwner', key(ewm_stock_owner, 'ewm_stock_owner', 80) if ewm_stock_owner.strip() else ""))
        filters.append(eq('EntitledToDisposeParty', key(entitled_to_dispose_party, 'entitled_to_dispose_party', 80) if entitled_to_dispose_party.strip() else ""))
        filters.append(eq('EWMStockType', key(ewm_stock_type, 'ewm_stock_type', 80) if ewm_stock_type.strip() else ""))
        filters.append(eq('EWMStockUsage', key(ewm_stock_usage, 'ewm_stock_usage', 80) if ewm_stock_usage.strip() else ""))
        filters.append(eq('StockDocumentCategory', key(stock_document_category, 'stock_document_category', 80) if stock_document_category.strip() else ""))
        filters.append(eq('EWMDocumentCategory', key(ewm_document_category, 'ewm_document_category', 80) if ewm_document_category.strip() else ""))
        filters.append(eq('WBSElementExternalID', key(wbs_element_externalid, 'wbs_element_externalid', 80) if wbs_element_externalid.strip() else ""))
        filters.append(eq('SpecialStockIdfgSalesOrder', key(special_stock_idfg_sales_order, 'special_stock_idfg_sales_order', 80) if special_stock_idfg_sales_order.strip() else ""))
        filters.append(eq('SpecialStockIdfgSalesOrderItem', key(special_stock_idfg_sales_order_item, 'special_stock_idfg_sales_order_item', 80) if special_stock_idfg_sales_order_item.strip() else ""))
        filters.append(eq('HandlingUnitExternalID', key(handling_unit_externalid, 'handling_unit_externalid', 80) if handling_unit_externalid.strip() else ""))
        filters.append(eq('EWMStorageBin', key(ewm_storage_bin, 'ewm_storage_bin', 80) if ewm_storage_bin.strip() else ""))
        filters.append(eq('EWMResource', key(ewm_resource, 'ewm_resource', 80) if ewm_resource.strip() else ""))
        return await record("ewm_stock", filters)

    @read_tool
    async def search_ewm_products(warehouse: str, entitled_to_dispose_party: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search EWM warehouse-product master records by warehouse and entitled party using Product Version 2."""
        filters = [eq("EWMWarehouse", key(warehouse, "warehouse", 4)), eq("EntitledToDisposeParty", key(entitled_to_dispose_party, "entitled_to_dispose_party", 10))]
        return await client.rows("ewm_product", "ProductEWMWarehouse", filters, max_results, offset)

    @read_tool
    async def get_ewm_product(product: str, warehouse: str, entitled_to_dispose_party: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read an EWM warehouse product by product, warehouse AND entitled party, including storage-type master data."""
        filters = [eq("Product", key(product, "product", 40)), eq("EWMWarehouse", key(warehouse, "warehouse", 4)), eq("EntitledToDisposeParty", key(entitled_to_dispose_party, "entitled_to_dispose_party", 10))]
        return await record("ewm_product", filters, [("storage_types", "ProductEWMStorageType", filters)], max_results, offset)
