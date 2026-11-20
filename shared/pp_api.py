"""Standard manufacturing reads; interfaces verified against SAP's published SDK and Help."""

from typing import Any

from shared.odata import eq, key


def register(read_tool, client, record):
    async def orders(service, plant, material, limit, offset):
        filters = [eq("ProductionPlant", key(plant, "plant", 4))]
        if material.strip():
            filters.append(eq("Material", key(material, "material", 40)))
        return await client.rows(service, client.services[service][1], filters, limit, offset)

    async def order(service, number, limit, offset):
        filters = [eq("ManufacturingOrder", key(number, "order", 12))]
        entities = client.services[service]
        return await record(service, filters, [(field, entity, filters) for field, entity in
                            zip(("items", "operations", "components", "statuses"), entities[2:])], limit, offset)

    @read_tool
    async def search_production_orders(plant: str, material: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search production order headers within a production plant, optionally one exact material."""
        return await orders("production_order", plant, material, max_results, offset)

    @read_tool
    async def get_production_order(production_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a production order header, items, operations, components and statuses; child views page independently."""
        return await order("production_order", production_order, max_results, offset)

    @read_tool
    async def search_process_orders(plant: str, material: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search process order headers by production plant and optional exact material."""
        return await orders("process_order", plant, material, max_results, offset)

    @read_tool
    async def get_process_order(process_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a process order header, items, operations/phases, components and statuses."""
        return await order("process_order", process_order, max_results, offset)

    @read_tool
    async def search_planned_orders(plant: str, material: str = "", max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search planned order headers by production plant and optional material."""
        return await orders("planned_order", plant, material, max_results, offset)

    @read_tool
    async def get_planned_order(planned_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a planned order with independently paged components and capacity requirements."""
        filters = [eq("PlannedOrder", key(planned_order, "planned_order", 10))]
        return await record("planned_order", filters, [("components", "PlannedOrderComponent", filters),
                            ("capacities", "PlannedOrderCapacity", filters)], max_results, offset)

    async def confirmations(service, order_number, limit, offset):
        return await client.rows(service, client.services[service][1],
                                 [eq("OrderID", key(order_number, "order", 12))], limit, offset)

    async def confirmation(service, group, counter, limit, offset):
        filters = [eq("ConfirmationGroup", key(group, "confirmation_group", 10)),
                   eq("ConfirmationCount", key(counter, "confirmation_count", 8))]
        return await record(service, filters, [("goods_movements", client.services[service][2], filters)], limit, offset)

    @read_tool
    async def search_production_order_confirmations(production_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search existing production confirmations for one production order. Never enters or reverses confirmations."""
        return await confirmations("production_confirmation", production_order, max_results, offset)

    @read_tool
    async def get_production_order_confirmation(confirmation_group: str, confirmation_count: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one production confirmation using BOTH group and counter, with material-document references."""
        return await confirmation("production_confirmation", confirmation_group, confirmation_count, max_results, offset)

    @read_tool
    async def search_process_order_confirmations(process_order: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search existing process-order confirmations by order."""
        return await confirmations("process_confirmation", process_order, max_results, offset)

    @read_tool
    async def get_process_order_confirmation(confirmation_group: str, confirmation_count: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a process-order confirmation by group and counter, including goods-movement references."""
        return await confirmation("process_confirmation", confirmation_group, confirmation_count, max_results, offset)

    @read_tool
    async def search_bills_of_material(material: str, plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search material BOM headers by material and plant; returns all matching alternatives/versions."""
        return await client.rows("bill_of_material", "MaterialBOM", [eq("Material", key(material, "material", 40)),
                                 eq("Plant", key(plant, "plant", 4))], max_results, offset)

    @read_tool
    async def get_bill_of_material(bill_of_material: str, material: str, plant: str, variant: str,
                                   category: str = "M", version: str = "", engineering_change_document: str = "",
                                   max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read material BOM V2 using its complete seven-part key. Blank version/change document remain exact key values."""
        values = {"BillOfMaterial": key(bill_of_material, "bill_of_material", 8), "Material": key(material, "material", 40),
                  "Plant": key(plant, "plant", 4), "BillOfMaterialVariant": key(variant, "variant", 2),
                  "BillOfMaterialCategory": key(category, "category", 1),
                  "BillOfMaterialVersion": key(version, "version", 4) if version.strip() else "",
                  "EngineeringChangeDocument": key(engineering_change_document, "engineering_change_document", 12) if engineering_change_document.strip() else ""}
        item = {("HeaderChangeDocument" if k == "EngineeringChangeDocument" else k): v for k, v in values.items()}
        return await record("bill_of_material", [eq(k, v) for k, v in values.items()],
                            [("items", "MaterialBOMItem", [eq(k, v) for k, v in item.items()])], max_results, offset)

    @read_tool
    async def search_production_routings(plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search routing headers by plant; preserve group, counter, internal version and validity dates."""
        return await client.rows("production_routing", "ProductionRoutingHeader", [eq("Plant", key(plant, "plant", 4))], max_results, offset)

    @read_tool
    async def get_production_routing(routing_group: str, routing: str, internal_version: str,
                                      max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one routing header version and operation/sequence VERSION collections for its group/counter.

        Child versions have their own validity and version keys; they are not
        presented as a historical snapshot of the selected header version.
        """
        filters = [eq("ProductionRoutingGroup", key(routing_group, "routing_group", 8)), eq("ProductionRouting", key(routing, "routing", 2))]
        return await record("production_routing", [*filters, eq("ProductionRoutingInternalVers", key(internal_version, "internal_version", 8))],
                            [("operation_versions", "ProductionRoutingOperation", filters),
                             ("sequence_versions", "ProductionRoutingSequence", filters)], max_results, offset)

    @read_tool
    async def search_work_centers(plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search work-center master records by plant; returned internal ID and type form the complete read key."""
        return await client.rows("work_center", "WorkCenterHeader", [eq("Plant", key(plant, "plant", 4))], max_results, offset)

    @read_tool
    async def get_work_center(work_center_internal_id: str, work_center_type: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one work center by internal ID AND type, with capacity and cost-center allocations."""
        filters = [eq("WorkCenterInternalID", key(work_center_internal_id, "work_center_internal_id", 8)),
                   eq("WorkCenterTypeCode", key(work_center_type, "work_center_type", 2))]
        return await record("work_center", filters, [("capacities", "WorkCenterCapacity", filters),
                            ("cost_centers", "WorkCenterCostCenter", filters)], max_results, offset)

    @read_tool
    async def search_production_versions(material: str, plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search production versions for one material and plant, including BOM/routing references and validity."""
        return await client.rows("production_version", "ProductionVersion", [eq("Material", key(material, "material", 40)),
                                 eq("Plant", key(plant, "plant", 4))], max_results, offset)

    @read_tool
    async def get_production_version(material: str, plant: str, production_version: str) -> dict[str, Any]:
        """Read one production version by material, plant and version."""
        return await record("production_version", [eq("Material", key(material, "material", 40)),
                            eq("Plant", key(plant, "plant", 4)), eq("ProductionVersion", key(production_version, "production_version", 4))])

    @read_tool
    async def search_planned_independent_requirements(material: str, plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search planned independent requirement headers for an exact product/plant, preserving all seven key dimensions."""
        return await client.rows("independent_requirement", "PlannedIndepRqmt", [eq("Product", key(material, "material", 40)),
                                 eq("Plant", key(plant, "plant", 4))], max_results, offset)

    @read_tool
    async def get_planned_independent_requirement(material: str, plant: str, requirement_type: str, version: str,
                                                  mrp_area: str = "", requirement_plan: str = "", requirement_segment: str = "",
                                                  max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one PIR's complete seven-part key and paged period requirements. Optional blank key parts are exact blanks."""
        values = {"Product": key(material, "material", 40), "Plant": key(plant, "plant", 4),
                  "PlndIndepRqmtType": key(requirement_type, "requirement_type", 4), "PlndIndepRqmtVersion": key(version, "version", 2)}
        for field, value, length in (("MRPArea", mrp_area, 10), ("RequirementPlan", requirement_plan, 10), ("RequirementSegment", requirement_segment, 40)):
            values[field] = key(value, field, length) if value.strip() else ""
        filters = [eq(k, v) for k, v in values.items()]
        return await record("independent_requirement", filters, [("items", "PlannedIndepRqmtItem", filters)], max_results, offset)

    @read_tool
    async def search_master_recipes(plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search standard process-manufacturing master-recipe header versions by plant."""
        return await client.rows("master_recipe", "MasterRecipeHeader", [eq("Plant", key(plant, "plant", 4))], max_results, offset)

    @read_tool
    async def get_master_recipe(recipe_group: str, recipe: str, internal_version: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one recipe header version and its group's independently versioned operation/phase records, retaining validity dates."""
        filters = [eq("MasterRecipeGroup", key(recipe_group, "recipe_group", 8)), eq("MasterRecipe", key(recipe, "recipe", 2))]
        return await record("master_recipe", [*filters, eq("MasterRecipeInternalVersion", key(internal_version, "internal_version", 8))],
                            [("operation_versions", "MasterRecipeOperation", filters), ("phase_versions", "MasterRecipePhase", filters)], max_results, offset)
