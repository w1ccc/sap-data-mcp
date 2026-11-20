"""Standard QM read-only tools; native SAP data and keys are retained."""
from typing import Any
from shared.odata import eq, key, typed_eq

def register(read_tool, client, record):

    @read_tool
    async def search_inspection_plans(plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for inspection plan. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Plant', key(plant, 'plant', 4), 'Edm.String', client.is_v4('inspection_plan'))]
        return await client.rows('inspection_plan', 'A_InspectionPlan', filters, max_results, offset)

    @read_tool
    async def get_inspection_plan(plan_group: str, plan: str, internal_version: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of inspection plan. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('InspectionPlanGroup', key(plan_group, 'plan_group', 8), 'Edm.String', client.is_v4('inspection_plan')), typed_eq('InspectionPlan', key(plan, 'plan', 2), 'Edm.String', client.is_v4('inspection_plan')), typed_eq('InspectionPlanInternalVersion', key(internal_version, 'internal_version', 8), 'Edm.String', client.is_v4('inspection_plan'))]
        return await record('inspection_plan', filters, [('operations', 'A_InspPlanOperation', [typed_eq('InspectionPlanGroup', key(plan_group, 'plan_group', 80), 'Edm.String', client.is_v4('inspection_plan')), typed_eq('InspectionPlan', key(plan, 'plan', 80), 'Edm.String', client.is_v4('inspection_plan')), typed_eq('InspectionPlanInternalVersion', key(internal_version, 'internal_version', 80), 'Edm.String', client.is_v4('inspection_plan'))]), ('characteristics', 'A_InspPlanOpCharacteristic', [typed_eq('InspectionPlanGroup', key(plan_group, 'plan_group', 80), 'Edm.String', client.is_v4('inspection_plan')), typed_eq('InspectionPlan', key(plan, 'plan', 80), 'Edm.String', client.is_v4('inspection_plan')), typed_eq('InspectionPlanInternalVersion', key(internal_version, 'internal_version', 80), 'Edm.String', client.is_v4('inspection_plan'))]), ('material_assignment_versions', 'A_InspPlanMaterialAssgmt', [typed_eq('InspectionPlanGroup', key(plan_group, 'plan_group', 80), 'Edm.String', client.is_v4('inspection_plan')), typed_eq('InspectionPlan', key(plan, 'plan', 80), 'Edm.String', client.is_v4('inspection_plan'))])], max_results, offset)

    @read_tool
    async def search_master_inspection_characteristics(plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for master inspection characteristic. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('InspectionSpecificationPlant', key(plant, 'plant', 4), 'Edm.String', client.is_v4('master_inspection_characteristic'))]
        return await client.rows('master_inspection_characteristic', 'A_InspectionSpecification', filters, max_results, offset)

    @read_tool
    async def get_master_inspection_characteristic(characteristic: str, version: str, plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of master inspection characteristic. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('InspectionSpecification', key(characteristic, 'characteristic', 8), 'Edm.String', client.is_v4('master_inspection_characteristic')), typed_eq('InspectionSpecificationVersion', key(version, 'version', 6), 'Edm.String', client.is_v4('master_inspection_characteristic')), typed_eq('InspectionSpecificationPlant', key(plant, 'plant', 4), 'Edm.String', client.is_v4('master_inspection_characteristic'))]
        return await record('master_inspection_characteristic', filters, [], max_results, offset)

    @read_tool
    async def search_inspection_methods(plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for inspection method. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('InspectionMethodPlant', key(plant, 'plant', 4), 'Edm.String', client.is_v4('inspection_method'))]
        return await client.rows('inspection_method', 'A_InspectionMethod', filters, max_results, offset)

    @read_tool
    async def get_inspection_method(inspection_method: str, version: str, plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of inspection method. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('InspectionMethod', key(inspection_method, 'inspection_method', 8), 'Edm.String', client.is_v4('inspection_method')), typed_eq('InspectionMethodVersion', key(version, 'version', 6), 'Edm.String', client.is_v4('inspection_method')), typed_eq('InspectionMethodPlant', key(plant, 'plant', 4), 'Edm.String', client.is_v4('inspection_method'))]
        return await record('inspection_method', filters, [], max_results, offset)

    @read_tool
    async def search_quality_info_records(plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for quality info record. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Plant', key(plant, 'plant', 4), 'Edm.String', client.is_v4('quality_info_record'))]
        return await client.rows('quality_info_record', 'QualityInProcurement', filters, max_results, offset)

    @read_tool
    async def get_quality_info_record(material: str, quality_info_record_id: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of quality info record. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Material', key(material, 'material', 40), 'Edm.String', client.is_v4('quality_info_record')), typed_eq('QltyInProcmtIntID', key(quality_info_record_id, 'quality_info_record_id', 12), 'Edm.String', client.is_v4('quality_info_record'))]
        return await record('quality_info_record', filters, [('first_article_inspections', 'QualityFirstArticleInspection', [typed_eq('Material', key(material, 'material', 80), 'Edm.String', client.is_v4('quality_info_record')), typed_eq('QltyInProcmtIntID', key(quality_info_record_id, 'quality_info_record_id', 80), 'Edm.String', client.is_v4('quality_info_record'))])], max_results, offset)

    @read_tool
    async def search_inspection_lots(plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for inspection lot. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('Plant', key(plant, 'plant', 4), 'Edm.String', client.is_v4('inspection_lot'))]
        return await client.rows('inspection_lot', 'A_InspectionLot', filters, max_results, offset)

    @read_tool
    async def get_inspection_lot(inspection_lot: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of inspection lot. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('InspectionLot', key(inspection_lot, 'inspection_lot', 12), 'Edm.String', client.is_v4('inspection_lot'))]
        return await record('inspection_lot', filters, [('statuses', 'A_InspectionLotWithStatus', [typed_eq('InspectionLot', key(inspection_lot, 'inspection_lot', 80), 'Edm.String', client.is_v4('inspection_lot'))]), ('operations', 'A_InspectionOperation', [typed_eq('InspectionLot', key(inspection_lot, 'inspection_lot', 80), 'Edm.String', client.is_v4('inspection_lot'))]), ('characteristics', 'A_InspectionCharacteristic', [typed_eq('InspectionLot', key(inspection_lot, 'inspection_lot', 80), 'Edm.String', client.is_v4('inspection_lot'))]), ('subsets', 'A_InspectionSubset', [typed_eq('InspectionLot', key(inspection_lot, 'inspection_lot', 80), 'Edm.String', client.is_v4('inspection_lot'))]), ('sample_characteristics', 'A_InspSampleCharacteristic', [typed_eq('InspectionLot', key(inspection_lot, 'inspection_lot', 80), 'Edm.String', client.is_v4('inspection_lot'))]), ('sample_results', 'A_InspSampleResult', [typed_eq('InspectionLot', key(inspection_lot, 'inspection_lot', 80), 'Edm.String', client.is_v4('inspection_lot'))]), ('results', 'A_InspectionResult', [typed_eq('InspectionLot', key(inspection_lot, 'inspection_lot', 80), 'Edm.String', client.is_v4('inspection_lot'))]), ('result_values', 'A_InspectionResultValue', [typed_eq('InspectionLot', key(inspection_lot, 'inspection_lot', 80), 'Edm.String', client.is_v4('inspection_lot'))]), ('usage_decision', 'A_InspLotUsageDecision', [typed_eq('InspectionLot', key(inspection_lot, 'inspection_lot', 80), 'Edm.String', client.is_v4('inspection_lot'))])], max_results, offset)

    @read_tool
    async def search_quality_notifications(notification_type: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search standard quality-notification headers by notification type. Native status and document references are returned."""
        return await client.rows("quality_notification", "QualityNotification", [eq("NotificationType", key(notification_type, "notification_type", 2))], max_results, offset)

    @read_tool
    async def get_quality_notification(quality_notification: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read a quality notification with independently paged items, tasks, causes and partners. Activities are available through RFC, not this published API version."""
        filters = [eq("QualityNotification", key(quality_notification, "quality_notification", 12))]
        return await record("quality_notification", filters, [("items", "QualityNotificationItem", filters), ("tasks", "QualityNotificationTask", filters), ("causes", "QltyNotificationItemCause", filters), ("partners", "QltyNotificationPartner", filters)], max_results, offset)

    @read_tool
    async def search_qm_characteristic_selected_sets(plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for qm characteristic selected set. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('SelectedCodeSetPlant', key(plant, 'plant', 4), 'Edm.String', client.is_v4('qm_characteristic_selected_set'))]
        return await client.rows('qm_characteristic_selected_set', 'A_CharcAttribSeldCodeSet', filters, max_results, offset)

    @read_tool
    async def get_qm_characteristic_selected_set(plant: str, selected_set: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of qm characteristic selected set. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('SelectedCodeSetPlant', key(plant, 'plant', 4), 'Edm.String', client.is_v4('qm_characteristic_selected_set')), typed_eq('SelectedCodeSet', key(selected_set, 'selected_set', 8), 'Edm.String', client.is_v4('qm_characteristic_selected_set'))]
        return await record('qm_characteristic_selected_set', filters, [('codes', 'A_CharcAttribSeldSetCode', [typed_eq('SelectedCodeSetPlant', key(plant, 'plant', 80), 'Edm.String', client.is_v4('qm_characteristic_selected_set')), typed_eq('SelectedCodeSet', key(selected_set, 'selected_set', 80), 'Edm.String', client.is_v4('qm_characteristic_selected_set'))]), ('code_texts', 'A_CharcAttribSeldSetCodeT', [typed_eq('SelectedCodeSetPlant', key(plant, 'plant', 80), 'Edm.String', client.is_v4('qm_characteristic_selected_set')), typed_eq('SelectedCodeSet', key(selected_set, 'selected_set', 80), 'Edm.String', client.is_v4('qm_characteristic_selected_set'))]), ('texts', 'A_CharcAttribSeldSetT', [typed_eq('SelectedCodeSetPlant', key(plant, 'plant', 80), 'Edm.String', client.is_v4('qm_characteristic_selected_set')), typed_eq('SelectedCodeSet', key(selected_set, 'selected_set', 80), 'Edm.String', client.is_v4('qm_characteristic_selected_set'))])], max_results, offset)

    @read_tool
    async def search_qm_usage_decision_selected_sets(plant: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for qm usage decision selected set. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('SelectedCodeSetPlant', key(plant, 'plant', 4), 'Edm.String', client.is_v4('qm_usage_decision_selected_set'))]
        return await client.rows('qm_usage_decision_selected_set', 'UsgeDcsnSelectedCodeSet', filters, max_results, offset)

    @read_tool
    async def get_qm_usage_decision_selected_set(plant: str, selected_set: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of qm usage decision selected set. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('SelectedCodeSetPlant', key(plant, 'plant', 4), 'Edm.String', client.is_v4('qm_usage_decision_selected_set')), typed_eq('SelectedCodeSet', key(selected_set, 'selected_set', 8), 'Edm.String', client.is_v4('qm_usage_decision_selected_set'))]
        return await record('qm_usage_decision_selected_set', filters, [('codes', 'UsgeDcsnSelectedCode', [typed_eq('SelectedCodeSetPlant', key(plant, 'plant', 80), 'Edm.String', client.is_v4('qm_usage_decision_selected_set')), typed_eq('SelectedCodeSet', key(selected_set, 'selected_set', 80), 'Edm.String', client.is_v4('qm_usage_decision_selected_set'))]), ('code_texts', 'UsgeDcsnSeldCodeText', [typed_eq('SelectedCodeSetPlant', key(plant, 'plant', 80), 'Edm.String', client.is_v4('qm_usage_decision_selected_set')), typed_eq('SelectedCodeSet', key(selected_set, 'selected_set', 80), 'Edm.String', client.is_v4('qm_usage_decision_selected_set'))]), ('group_texts', 'UsgeDcsnSeldCodeGroupText', [typed_eq('SelectedCodeSetPlant', key(plant, 'plant', 80), 'Edm.String', client.is_v4('qm_usage_decision_selected_set')), typed_eq('SelectedCodeSet', key(selected_set, 'selected_set', 80), 'Edm.String', client.is_v4('qm_usage_decision_selected_set'))]), ('texts', 'UsgeDcsnSeldCodeSetText', [typed_eq('SelectedCodeSetPlant', key(plant, 'plant', 80), 'Edm.String', client.is_v4('qm_usage_decision_selected_set')), typed_eq('SelectedCodeSet', key(selected_set, 'selected_set', 80), 'Edm.String', client.is_v4('qm_usage_decision_selected_set'))])], max_results, offset)

    @read_tool
    async def search_qm_catalogs(catalog_type: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for qm catalog. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ConfigurableCodesCatalog', key(catalog_type, 'catalog_type', 1), 'Edm.String', client.is_v4('qm_catalog'))]
        return await client.rows('qm_catalog', 'ConfigurableCodesCatalog', filters, max_results, offset)

    @read_tool
    async def get_qm_catalog(catalog_type: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of qm catalog. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ConfigurableCodesCatalog', key(catalog_type, 'catalog_type', 1), 'Edm.String', client.is_v4('qm_catalog'))]
        return await record('qm_catalog', filters, [('code_groups', 'ConfigurableCodesCodeGroup', [typed_eq('ConfigurableCodesCatalog', key(catalog_type, 'catalog_type', 80), 'Edm.String', client.is_v4('qm_catalog'))])], max_results, offset)

    @read_tool
    async def search_qm_code_groups(catalog_type: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Search within the specified scope for qm code group. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ConfigurableCodesCatalog', key(catalog_type, 'catalog_type', 1), 'Edm.String', client.is_v4('qm_code_group'))]
        return await client.rows('qm_code_group', 'ConfigurableCodesCodeGroup', filters, max_results, offset)

    @read_tool
    async def get_qm_code_group(catalog_type: str, code_group: str, max_results: int = 100, offset: int = 0) -> dict[str, Any]:
        """Read one complete key/version of qm code group. Child collections page independently; all native quantities, currency, status and validity fields are retained."""
        filters = [typed_eq('ConfigurableCodesCatalog', key(catalog_type, 'catalog_type', 1), 'Edm.String', client.is_v4('qm_code_group')), typed_eq('ConfigurableCodesCodeGroup', key(code_group, 'code_group', 8), 'Edm.String', client.is_v4('qm_code_group'))]
        return await record('qm_code_group', filters, [('codes', 'ConfigurableCodesCode', [typed_eq('ConfigurableCodesCatalog', key(catalog_type, 'catalog_type', 80), 'Edm.String', client.is_v4('qm_code_group')), typed_eq('ConfigurableCodesCodeGroup', key(code_group, 'code_group', 80), 'Edm.String', client.is_v4('qm_code_group'))]), ('texts', 'ConfigurableCodesCodeGroupText', [typed_eq('ConfigurableCodesCatalog', key(catalog_type, 'catalog_type', 80), 'Edm.String', client.is_v4('qm_code_group')), typed_eq('ConfigurableCodesCodeGroup', key(code_group, 'code_group', 80), 'Edm.String', client.is_v4('qm_code_group'))]), ('code_texts', 'ConfigurableCodesCodeText', [typed_eq('ConfigurableCodesCatalog', key(catalog_type, 'catalog_type', 80), 'Edm.String', client.is_v4('qm_code_group')), typed_eq('ConfigurableCodesCodeGroup', key(code_group, 'code_group', 80), 'Edm.String', client.is_v4('qm_code_group'))])], max_results, offset)
