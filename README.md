# SAP Data MCP

SAP Data MCP is organized first by deployment and then by integration route. Each provider has independent configuration, credentials, MCP registration and audit logs. The two HTTP providers share the standard business-domain implementations; neither loads PyRFC.

| Provider | Target | Integration | Status |
|---|---|---|---|
| [`private_cloud/rfc/`](private_cloud/rfc/) | S/4HANA Private Edition or On-Premise systems with RFC enabled; ECC / NetWeaver | RFC/BAPI via PyRFC + SAP NW RFC SDK | 95 read-only Tools / 98 fixed RFC functions (table display, source display and a runner for reviewed display-only reports added 2026-11-10) |
| [`private_cloud/odata/`](private_cloud/odata/) | Private Edition or On-Premise systems exposing the selected standard services | Explicit OData V2/V4 over HTTPS | 155 business Tools + 4 local/connection Tools |
| [`public_cloud/api/`](public_cloud/api/) | S/4HANA Cloud Public Edition | Released OData V4/V2 APIs over HTTPS | 154 business + 4 local/connection Tools |

GUI / Fiori are orientation labels: RFC/BAPI covers classic backend integration, and OData/API covers Fiori-related API integration. These routes do not automate SAP GUI or Fiori pages. Standard read coverage now includes MM/IM, PP, SD, WM/EWM, FI, CO, activated master data and QM. Route-specific interface gaps are listed below; no business writes or Agent are implemented.

```text
sap-data-mcp/
├── .venv/                  Python 3.12 virtual environment (create locally, not committed)
├── private_cloud/
│   ├── rfc/                Existing read-only RFC MCP Server and all current Tools
│   └── odata/              Private API entry point, local .env and audit logs
├── public_cloud/
│   └── api/                Public API entry point, local .env and audit logs
├── shared/                 Fixed OData client and shared tools registered by business module
├── tests/                  MM and standard-module offline regressions; no SAP login
├── requirements.txt        Shared HTTP/MCP dependencies; RFC adds PyRFC separately
├── .env.example            HTTP configuration template; copy into the selected provider
├── .gitignore
├── README.md
```

Each integration route runs as one MCP Server. Use client labels `sap_private_rfc`, `sap_private_odata` and `sap_public_api`. The RFC protocol name remains `sap-data-mcp`; the API protocol names are `sap_private_odata` and `sap_public_api`. All currently use version `0.2.0`. Tool names can overlap between servers; clients distinguish them by server.

RFC Tool source is grouped under `platform`, `master_data`, `mm`, `pp`, `sd`, `basis` and `integration`, with actual WM/FI/CO/QM read modules. MCP clients receive a flat Tool list. `check_odata_services` stays in RFC Integration because it reads Gateway registration over RFC; the legacy HTTPS connection test also remains available under its existing Tool name.

The Python virtual environment lives at the repository root and is shared by all providers. Start the current provider from [`private_cloud/rfc/README.md`](private_cloud/rfc/README.md):

```powershell
cd private_cloud/rfc
..\..\.venv\Scripts\python.exe server.py
```

## Standard modules: current delivery

| Module / standard objects | RFC implementation | Private OData / Public Released API | Official scope and interface sources |
|---|---|---|---|
| PP: production/process orders and confirmations, planned orders, BOM, routing, work center, production version, PIR, master recipe | Existing production-order search/detail enriched; 6 added reads for planned/process orders and production/process confirmations | 22 tools. Production/process/confirmation/BOM/routing/recipe/PIR V2; planned order, work center and production version V4. Public routing uses version 3 | [Manufacturing APIs](https://help.sap.com/docs/SAP_S4HANA_CLOUD/d35113ee62644d3abee1aaec148291d9/2327fde359274cddb9c10ac914b09454.html), SAP-published SDK service paths/entities/keys |
| SD: customer and sales areas; inquiry, quotation, sales order, contract, scheduling agreement, outbound delivery, billing, return, credit/debit request | Search/detail verify SAP category C; original status `items` retained, full data in `details`; customer master read included | 22 tools. `API_BUSINESS_PARTNER`, `API_SALES_*`, outbound delivery, billing, customer return and memo-request V2 APIs | [Sales APIs](https://help.sap.com/docs/SAP_S4HANA_CLOUD/03c04db2a7434731b7fe21dca77440da/00d244581efca007e10000000a441470.html), [standard interfaces](https://help.sap.com/docs/SAP_S4HANA_BEST_PRACTICES/7c85a9907ecf4b039f4cf574cc299d93/5d55fc2d126844039fc4084ef3e945c9.html?locale=en-US) |
| Classic WM: stock quants and transfer orders | 4 `wm_*` tools through `BAPI_WHSE_STOCK_GET_LIST/DETAIL`, `BAPI_WHSE_TO_GET_LIST/DETAIL` | Classic WM is not represented by the EWM APIs | [Classic warehouse structure](https://help.sap.com/docs/SAP_ERP/78e0627c34ef43879d72718e21ea517b/cde1f461630a4a9c972fc99eb7badb04.html?version=6.17.latest), [WM BAPI reads](https://community.sap.com/t5/application-development-and-automation-discussions/inventory-count-with-wm-li11n/td-p/2013627) |
| EWM: warehouse/types, product, bin, available stock, HU, tasks/orders, inbound/outbound delivery, inventory item/count | No unverified EWM RFC functions added | 20 `ewm_*` tools. Warehouse/bin/HU/task/order/delivery/inventory V2; available stock and Product warehouse master V4 | [Orders/tasks](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/5aadd5aa0ed541e49b1e006d7e17919b/3f4ed3d800bb42ce9588fc7fa4051a9a.html), [warehouse product](https://help.sap.com/docs/SAP_S4HANA_CLOUD/3c916ef10fc240c9afc594b346ffaf77/b1f586e9ec304071b64c900636a9041c.html?locale=en-US) |
| FI: company, chart, GL account, operational journal items, Universal Journal items, customer/supplier open/cleared items, GL balances, asset master/selected values, bank | 14 tools: previous 11 plus asset-value search/detail and GL fiscal-period balances | 18 tools. Master/entry-view/trial-balance V2; Bank and Fixed Asset master V4. Universal Journal uses SAP's documented `API_GLACCOUNTLINEITEM/GLAccountLineItem` request path | [GL APIs](https://help.sap.com/docs/SAP_S4HANA_CLOUD/b978f98fc5884ff2aeb10c8fdeb8a43b/610d1f7204d94644950928f575782f22.html), [Universal Journal keys](https://help.sap.com/docs/SAP_S4HANA_CLOUD/b978f98fc5884ff2aeb10c8fdeb8a43b/80214b5ede2f4e97b640137a4eca208a.html?locale=en-US), [asset master reads](https://help.sap.com/docs/SAP_S4HANA_CLOUD/5bcca49998834de2b5533c36602e52a2/06ca541968e44eeca7980af1f53084f5.html) |
| CO: controlling area, cost/profit centers, activity types, statistical figures, internal order, groups, actual costs and plan/actual amounts | 12 tools: previous 6 plus controlling-area list/detail, internal-order search/group detail, profit-center search and cost-center-group search | 13 tools. Master V2, financial plan/actual amount views and Universal Journal cost items; cost elements reuse GL account reads | [Finance APIs](https://help.sap.com/docs/SAP_S4HANA_CLOUD/6b39bd1d0e5e4099a5b65d835c29c696/5792333ddf3c47eaad4314b071dfd684.html), [master-data services](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/48f4b4785b8e45938ac44a67be8032d9/9965a647179a4e5a95e081f3e93c89b4.html) |
| MDG: activated master data; authenticated user's request metadata on private MDG | Reuse existing master tools | 3 shared master-data tools; private OData adds 1 Track My Requests tool. No private Fiori governance service is registered in the public provider | [MDG Governance API](https://help.sap.com/docs/SAP_MASTER_DATA_GOVERNANCE/21d2a9e85c7242ee8c3a881f7de4ac89/888c744b11334485b32e337f4dcf0d84.html), [Track My Requests read collection](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/6d52de87aa0d4fb6a90924720a5b0549/1b5e7c571fbeb576e10000000a4450e5.html); local ABAP classes are not remote interfaces |
| QM: plan, MIC, method, quality info, lot/operation/characteristic, inspection points/sample results, results/usage decision, notification, catalog/code/selected set | 3 tools for lot search/detail and notification detail; selecting an operation adds its requirements/sample/results to lot detail | 20 tools. Inspection/characteristic-selected-set V2; quality notification, catalog/code groups and usage-decision-selected-set V4 | [Lot structure](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/a08e12a754cf4891b41a01a285d065bb/61ff4c3780864ce1b0822d9c5e6cd3bb.html), [notification API](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/a08e12a754cf4891b41a01a285d065bb/454808498fc344a8a08b912503d90ac0.html), [catalog reads](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/a08e12a754cf4891b41a01a285d065bb/82da28fcadae439c90e57d3bdd84969c.html) |

`get_server_info` returns the exact service catalog with protocol, versioned path and entities; `test_sap_api_connection(service=...)` accepts every catalog entry. Each business API must be available and authorized in the target release. A configured origin is not evidence that all listed APIs are installed.

Searches require business scope. Details preserve complete composite keys, native amounts/quantities/units/currencies, zero/false values and validity dates. Child views page independently with the requested offset; empty results, permission failures and partial reads remain distinct. Routing/recipe child-version collections retain their own validity instead of claiming a historical snapshot. EWM available stock is not total physical stock. FI clearing references do not establish actual payment; asset valuation master data is not a posted book value. MDG activated data is marked `active` and is never returned as staging data.

Follow-up tools reuse the existing modules and read helpers:

| Standard object / tools | Interface and route | Official basis |
|---|---|---|
| Asset values: `search_fixed_asset_values`, `get_fixed_asset_values` | RFC `BAPI_FIXEDASSET_GETLIST`, `REQUESTEDTABLESX-DEPRECIATIONAREAVALS`; detail filters the complete asset/subnumber key | [SAP-published BAPI SDK sources](https://repo.maven.apache.org/maven2/com/sap/cloud/s4hana/datamodel/bapi-api/2.28.0/bapi-api-2.28.0-sources.jar): `BAPI1022_VALUES` retains area/year/currency, year-end APC/NBV and planned depreciation separately |
| GL periods: `get_gl_account_period_balances` | RFC `BAPI_GL_GETGLACCPERIODBALANCES`; company/account/year/currency type | [SAP Community original call example](https://community.sap.com/t5/application-development-and-automation-discussions/error-while-transferin-intenal-table-data-to-application-server/m-p/1189757/highlight/true). No ledger, daily or business-area breakdown is claimed |
| Controlling areas: `search_controlling_areas`, `get_controlling_area` | RFC `BAPI_CONTROLLINGAREA_GETLIST/GETDETAIL` | [Standard BAPI objects](https://community.sap.com/t5/application-development-and-automation-discussions/std-bapi/m-p/2529729/highlight/true), [detail call and authorization](https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-members/about-a-small-bug/ba-p/13291259) |
| Internal orders/groups: `search_internal_orders`, `get_internal_order_group` | RFC `BAPI_INTERNALORDER_GETLIST`, `BAPI_INTERNALORDRGRP_GETDETAIL` | [SAP internal-order BAPI guidance](https://help.sap.com/docs/SUPPORT_CONTENT/ficontrolling/3361878453.html?locale=en-US), [standard interface catalog](https://help.sap.com/docs/SAP_S4HANA_BEST_PRACTICES/7c85a9907ecf4b039f4cf574cc299d93/5d55fc2d126844039fc4084ef3e945c9.html?locale=en-US) |
| Profit centers: `search_profit_centers` | RFC `BAPI_PROFITCENTER_GETLIST`, explicit controlling area and key date | [Original parameter example](https://community.sap.com/t5/enterprise-resource-planning-q-a/bapi-profitcenter-getlist/qaq-p/6684234) |
| Cost-center groups: `search_cost_center_groups` | RFC `BAPI_COSTCENTERGROUP_GETLIST`, exact controlling-area mask | [Original group-list example](https://community.sap.com/t5/enterprise-resource-planning-q-a/display-cost-center-group-text/qaq-p/874884). Existing detail returns SET nodes and intervals |
| My MDG requests: `search_mdg_my_change_requests` | Private OData only: `MDG_MYCR_SRV/ChangeRequests`; current authenticated user | [SAP service catalog](https://help.sap.com/doc/00144c6cf07a4879b4b51e8d47a67413/MDG90.SP15/en-US/loioecef2cb358b441b89fc6b59ba4c4110e.pdf), [read collection](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/6d52de87aa0d4fb6a90924720a5b0549/1b5e7c571fbeb576e10000000a4450e5.html), [service authorization](https://help.sap.com/doc/0b26768917f947f4b76d6dec9d892fa4/2.0%202016-08/en-US/356445533e416857e10000000a44538d.html). Returns metadata, not staging data |

**Remaining boundaries and reasons:**

- **Classic WM warehouse/storage type/bin/transfer requirement:** no complete remotely callable read contract was verified. SAP's [WMTREQ interface](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/9609b5f9e9304ef6850945b359a1f5d4/a528bd534f22b44ce10000000a174cb4.html) creates requirements; it is not a read interface. EWM warehouse/bin APIs have different objects and keys. The four existing WM quant/transfer-order tools remain; no table-reader or custom wrapper is added.
- **FI:** Use the actual asset/company depreciation area: depreciation areas differ by chart of depreciation; do not assume area `01`. A master record can exist without returned value records; empty values are not zero balances. These tools do not supply arbitrary-day posted balances by ledger. The Fixed Asset OData API contains master/valuation terms. A remote amount contract and enterprise bank-account contract remain unverified. [Transactional Banking accounts](https://help.sap.com/docs/TRBK_S4HANA/d2151b51aacc4d82ad2861e007337fa2/15028611fde842d383c55d1e223000d0.html) have industry-specific contract semantics, and trial-balance bank-account value-help IDs/texts are not full bank-account master data.
- **CO:** RFC internal-order search/detail and classic group reads are available. SAP documents `API_INTERNALORDER_SRV`, `C_COSTCENTERHIERARCHYNODE_SRV`, `C_PROFITCENTERHIERNODE_SRV` and `API_COSTCENTER_HIERARCHY`; their complete remote entity/key/version contracts are still unverified here, so HTTP tools are not registered. [SET groups and global hierarchies differ](https://userapps.support.sap.com/sap/support/knowledge/en/3081506); the [group hierarchy replication API](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/b3438d89db5040508a3873ad6c6e55bc/7776f04d698745869171aae5c57438d8.html) writes data and is excluded.
- **MDG:** the private request list is implemented; all-user request searches, standalone type/status catalogs, steps/objects, staging, change history, existing validation messages, key mapping and replication status remain unimplemented because their read entities/keys are not verified. `MDG_APPROVE_CR` exists, but its approval workflow is not treated as a generic read API. Internal Governance API classes cannot be called remotely without an SAP wrapper. No Released Public Cloud governance contract was verified, so the public provider retains master-data tools only. A configured MDG component, service and authorization are needed for live acceptance.
- **Other existing limits:** the selected QM notification V4 has no activity collection; use RFC notification detail for activities. Physical sample-management master records beyond inspection-point/sample-result data are not claimed.

Unverified contracts are research gaps, **not** claims that SAP has no standard interface in every release. No placeholder tools are registered for them.

## Standard MM and IM queries

| Object | RFC | Private OData / Public API |
|---|---|---|
| Material master | `search_materials`, `get_material` | `search_materials`, `get_material` |
| Supplier | `search_business_partners`, `get_supplier` | `search_suppliers`, `get_supplier` |
| Purchase requisition | `search_purchase_requisitions`, `get_purchase_requisition` | Same names |
| Purchase order | `search_purchase_orders`, `get_purchase_order` | Same names |
| IM material documents | `search_material_documents`, `get_material_document` | Same names |
| IM stock by plant/storage location | `search_material_stock` | `get_material_stock` |
| MM supplier invoices | `search_supplier_invoices`, `get_supplier_invoice` | Same names |
| IM physical inventory documents | `search_physical_inventory_documents`, `get_physical_inventory_document` | Same names |
| Reservations | `search_reservations`, `get_reservation` | Same names |
| Batch master | `get_batch`; batch stock via `search_material_stock` | `search_batches`, `get_batch` |
| Purchasing info records | `search_purchasing_info_records`, `get_purchasing_info_record` | Same names |
| Purchasing source lists | Use API route; no generic table reader | `search_source_lists`, `get_source_list` |
| Quota arrangements | Use API route | `search_quota_arrangements`, `get_quota_arrangement` |
| Purchase contracts | `get_purchase_contract` | `search_purchase_contracts`, `get_purchase_contract` |
| Purchase scheduling agreements | `get_scheduling_agreement` | `search_scheduling_agreements`, `get_scheduling_agreement` |
| Requests for quotation / supplier quotations | Use API route | `search_requests_for_quotation`, `get_request_for_quotation`, `search_supplier_quotations`, `get_supplier_quotation` |
| Service entry sheets | `search_service_entry_sheets`, `get_service_entry_sheet` (classic MM services) | Same names (lean services) |
| PO follow-on document references | `get_purchase_order_history` (SAP history categories, signs and years) | Same name (material-document and invoice-reference views, separately paged) |

The existing RFC `get_material_stock` keeps its MD04/MRP view and optional storage-location detail. The RFC stock search and the API stock Tool read IM stock. Field names and stock-type codes are returned as supplied by SAP, with zero quantities preserved. API document reads return the header and paged items. Invoice reads also return G/L account items and tax views, scheduling agreements add delivery schedules, and RFQs add bidders. Each extra view pages separately; failed views produce partial results. The API PO history Tool reads material documents and MM invoice items referencing the PO; it does not reproduce every EKBE history category or infer FI payments. RFC and API parameters differ where standard interfaces differ; the Tool descriptions specify those limits.

This coverage was assessed against SAP's standard sourcing, purchasing, inventory, batch and invoice objects. It provides their basic reads, not every MM field or configuration transaction. API PO/PR account and condition expansions, separate purchasing pricing-condition records, batch classification and valuation reports are not implemented by MM tools. Separate FI tools now read accounting and clearing references; they do not establish actual payment. Source lists, quotas and RFQs use the API routes; no unsupported RFC wrappers or generic table tools were added. Batch detail uses the full Material/Batch/BatchIdentifyingPlant key in OData (empty identifying plant is meaningful); the RFC batch Tool uses the classic 18-character material input.

Added interface references: SAP's [released info-record BAPI](https://help.sap.com/docs/SUPPORT_CONTENT/spmm/3362168709.html), [purchasing info-record API operations](https://help.sap.com/docs/SAP_S4HANA_CLOUD/bb9f1469daf04bd894ab2167f8132a1a/50d17127bda54d66832be55592d423a3.html?locale=en-US), [source-list API](https://help.sap.com/docs/SAP_S4HANA_CLOUD/bb9f1469daf04bd894ab2167f8132a1a/5692d23783a94d8282659356113c384f.html?locale=en-US), [quota reads](https://help.sap.com/docs/SAP_S4HANA_CLOUD/bb9f1469daf04bd894ab2167f8132a1a/397ffd9cc70e4d3fa6cb7824469a7073.html?locale=en-US), [contract API version 2](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/91af7f8d3acd47da90d33aaacfcd0d59/1e7ae14775154b65939267d6fa4d9535.html), [scheduling agreements](https://help.sap.com/docs/SAP_S4HANA_CLOUD/bb9f1469daf04bd894ab2167f8132a1a/c7584658aac4a007e10000000a441470.html?locale=en-US), [RFQs](https://help.sap.com/docs/SAP_S4HANA_CLOUD/bb9f1469daf04bd894ab2167f8132a1a/0747b64b221046a08c552f55a4b9d292.html?locale=en-US), [supplier quotations](https://help.sap.com/docs/SAP_S4HANA_CLOUD/bb9f1469daf04bd894ab2167f8132a1a/87a40bc9b4db43d89fcbb6e10dd152fe.html), and [service-entry reads](https://help.sap.com/docs/SAP_S4HANA_CLOUD/bb9f1469daf04bd894ab2167f8132a1a/f7c7e21562b74c12a61ef3db42926e5c.html?locale=en-US). No create/change operations from these API specifications are exposed.

Invoice search requires a supplier and both **document dates** (at most 366 days apart). Physical inventory search requires a plant and fiscal year; reservation search requires a plant. Invoice and physical inventory detail reads require the document number **and fiscal year**. Count quantities, zero amounts and API false flags are preserved; the reservation item key `RecordType` is retained even when empty. No payment/clearing status is inferred, and no count, recount, difference-posting or reservation-change operation is exposed. RFC reservation search uses the standard BAPI movement/final-issue selection defaults and accepts classic material numbers up to 18 characters.

The added shared API mappings use the standard V2 services in both providers: [Supplier Invoice](https://help.sap.com/docs/PRODUCT_ID/bb9f1469daf04bd894ab2167f8132a1a/af62388a0c05492b94410ea79cb1b13f.html?locale=en-US&state=PRODUCTION&version=LATEST), [Physical Inventory Document](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/eb2a39dd0c124fed8252f684002d55e1/a5a89756e43649daa9e1d20ad2c6e7d2.html?version=2023.latest), [Reservation Document](https://help.sap.com/docs/SAP_S4HANA_CLOUD/3f57e7df4a114edabffe8b2d581a59ed/025cdccd12e4438f95788d5e3acfdb12.html).

## Start an API provider

Create a Python 3.12 virtual environment at `.venv` and install `requirements.txt`; API providers do not require PyRFC or the SAP RFC SDK.

Copy the root `.env.example` into the chosen API provider as `.env`, and fill in its HTTPS origin and Basic or OAuth client-credentials settings. Each provider reads only its own `.env` plus explicit `SAP_API_*` environment overrides. Keep TLS verification enabled; `SAP_API_CA_BUNDLE` accepts a PEM CA bundle relative to that provider. No business Tool accepts credentials, arbitrary URLs or raw OData queries.

From the repository root, select one provider:

```powershell
cd private_cloud/odata   # or: cd public_cloud/api
..\..\.venv\Scripts\python.exe server.py
```

Connect an MCP client to that process, then call `health_check`, `get_server_info`, and `test_sap_api_connection(service="material")`. The connection Tool checks one service's metadata and reports missing entities; it does not prove all services are available. No additional project-specific Agent is required to invoke the Tools.

API searches require business filters. `max_results` (1-500) and `offset` page the results in SAP; server-driven paging is followed only within the same origin and entity. `next_offset` is returned when more results exist. A missing service/permission is an error; a successful empty collection is `not_found`. After HTTP 401, the process does not retry credentials; correct the configuration and restart it. The only POST is OAuth token acquisition; all business calls are fixed GET reads.

API Tool calls are logged under the selected provider's `logs/tool_calls_YYYY-MM-DD.jsonl`. Logs contain Tool arguments, status, duration and API paths, with configured credentials and tokens redacted. Read them with `get_tool_call_log`.

## Verification and remaining prerequisites

