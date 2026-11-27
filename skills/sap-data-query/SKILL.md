---
name: SAP Data Query
description: Answer business and Basis questions about an SAP S/4HANA (or ECC) system by reading live data through the read-only SAP Data MCP servers (RFC/BAPI, private-cloud OData, public-cloud released APIs). Use this skill whenever the user asks about SAP purchase orders, invoices, payment blocks, supplier or customer open items, material stock, material documents, production or process orders, sales orders, deliveries, cost centers, internal orders, fixed assets, G/L balances, quality lots or notifications, warehouse stock, or system health such as short dumps (ST22), system log (SM21), application logs (SLG1), background jobs (SM37), IDocs and qRFC/tRFC/bgRFC queues - e.g. "Why hasn't PO 4500000417 been paid yet?" or "Which jobs were canceled this morning?".
author: w1ccc
license: MIT
---

# SAP Data Query

Use the read-only tools of [SAP Data MCP](https://github.com/w1ccc/sap-data-mcp) to answer questions about an SAP S/4HANA system in plain language, the way an experienced SAP consultant would look them up across several T-codes, but without SAP GUI and without changing any data.

## Prerequisites

This skill needs at least one of the SAP Data MCP servers registered in the AI client. Pick the one that matches the target system:

| MCP server name | Target system | Route |
|---|---|---|
| `sap_private_rfc` | S/4HANA Private Edition or on-premise, ECC / NetWeaver | RFC/BAPI via PyRFC and the SAP NW RFC SDK |
| `sap_private_odata` | Private Edition or on-premise with standard OData services active | OData V2/V4 over HTTPS |
| `sap_public_api` | S/4HANA Cloud Public Edition | Released OData APIs over HTTPS |

Setup (Python 3.12, Windows PowerShell shown):

```powershell
git clone https://github.com/w1ccc/sap-data-mcp.git
cd sap-data-mcp
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example public_cloud\api\.env   # then fill in URL and credentials locally
claude mcp add sap_public_api -- <repo>\.venv\Scripts\python.exe <repo>\public_cloud\api\server.py
```

The RFC server additionally needs the SAP NW RFC SDK and PyRFC; see `private_cloud/rfc/docs/GOLDEN_PATH.md` in the repository. Credentials live only in each server's local `.env` and are never passed through the assistant.

If no SAP Data MCP tools are available, tell the user the server is not connected and point them to the setup above. Do not invent SAP data.

## Workflow

1. **Check the connection first, once per session.**
   - RFC: `test_sap_rfc_connection`, then optionally `get_sap_system_info`.
   - OData / public API: `health_check`, then `test_sap_connection` / `test_sap_api_connection(service=...)` for the service you are about to use.
   - `get_server_info` lists the registered tools and, for the HTTP servers, the service catalog.
2. **Translate the question into business objects.** Identify document numbers, company code, plant, supplier, customer, material and date range. Ask the user only when a required key is truly missing.
3. **Prefer standard business tools over raw tables.** Use `get_*` / `search_*` tools for purchasing, inventory, production, sales, finance, controlling, quality and warehouse objects. Fall back to `read_table`, `list_table_fields` or `summarize_table` (RFC only) when no business tool covers the question.
4. **Follow the document flow.** Chain lookups the way the process does, e.g. purchase order → PO history (goods receipts, invoice receipts) → supplier invoice → supplier open items.
5. **Page deliberately.** Lists accept `max_results` and `offset`; say when a result is partial instead of silently truncating.
6. **Answer, then show the evidence.** Give the answer in one or two sentences, then the key documents, amounts with currency, quantities with unit and dates that support it.

## Common question patterns

| Question | Typical tool chain |
|---|---|
| Why hasn't PO X been paid? | `get_purchase_order` → `get_purchase_order_history` → `search_supplier_invoices` / `get_supplier_invoice` → `search_supplier_open_items` |
| Open items of supplier / customer | `search_supplier_open_items`, `search_supplier_account_items`, `search_customer_open_items`, `search_customer_account_items` |
| Stock of material M in plant P | RFC: `search_material_stock`; HTTP servers: `get_material_stock` |
| Goods movements for a material or PO | `search_material_documents` → `get_material_document` |
| Status of a production / process order | `get_production_order` / `get_process_order`, plus confirmations |
| Sales order status | `search_sales_orders` → `get_sales_order` |
| Cost center, internal order, profit center | `get_cost_center`, `search_internal_orders`, `search_profit_centers` and the group tools |
| G/L or asset balances | `get_gl_account_period_balances`, `get_fixed_asset_values` |
| Quality | `search_inspection_lots`, `get_quality_notification` |
| Today's short dumps / system log | `list_short_dumps`, `list_system_log` (RFC) |
| Canceled background jobs | `list_background_jobs` → `get_background_job_log` (RFC) |
| IDocs or queues in error | `list_idocs` → `get_idoc`, `list_qrfc_queues`, `list_trfc_errors`, `get_bgrfc_overview` (RFC) |

Exact tool names differ slightly between the three servers; check the available tool list rather than guessing.

## Rules for interpreting results

- Every result carries a `status` of `ok`, `not_found`, `partial` or `error`. Report it honestly.
- An empty list is not a zero balance. A missing authorization is not "no data". Say which one it is.
- A clearing document or clearing reference is not proof of payment. Do not claim money was paid unless the data shows it.
- Keep SAP's own keys, field names, amounts, units and currencies. Preserve zero and false values; don't round away differences such as price variances.
- Monitoring timestamps (ST22, SM21, SLG1, SM37, IDocs, queues) are SAP application-server local time.
- Dates may be passed as `YYYY-MM-DD` or `YYYYMMDD`.

## Boundaries

- **Read-only.** These tools never create, change, post, release or approve anything. If the user asks for a change, explain what they would do in SAP (T-code or Fiori app) instead of attempting it.
- No SAP GUI or Fiori screen automation; only standard RFC functions, OData services and released APIs.
- What can be read depends on the services activated in the target system and the logon user's authorizations.
- Every call is written to the server's audit log; `get_tool_call_log` shows what was queried in this session.
- Never ask the user for, print or store SAP passwords, client secrets or tokens.
