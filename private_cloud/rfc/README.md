# Private Cloud / On-Premise RFC Provider

通过 RFC **只读**访问允许 RFC 的 S/4HANA Private Edition、On-Premise、ECC 或 NetWeaver 系统的本地 MCP Server。所有 SAP 调用都必须经过
`connectors/sap_rfc_connector.py` 中的只读函数白名单 `READ_ONLY_FUNCTIONS`，不创建、修改、过账或提交任何数据。
RFC 连接的完整成功路径见 [docs/GOLDEN_PATH.md](docs/GOLDEN_PATH.md)。

## 当前标准模块覆盖（2026-10-23 晚间）

共 **90 个 Tool / 94 项固定函数白名单**。PP 新增 6 个并扩充生产订单明细；SD 保留原订单 `items` 状态语义，完整数据放 `details`，新增客户读取；经典 WM 4 个、FI 14 个、CO 12 个、QM 3 个工具。FI 本次补资产所选年末金额搜索/明细、总账期间余额；CO 补控制范围搜索/明细、内部订单搜索、订单组明细、利润中心及成本中心组搜索。MDG 主数据复用原有读取；请求元数据使用私有 OData。经典 WM 其余契约和各路线限制见根 README。

2026-11-10：允许只读查表和只读查看源码，新增 5 个 Tool（`list_table_fields`、`read_table`、`summarize_table`、`read_program_source`、`run_report`）和 4 个函数（`DDIF_FIELDINFO_GET`、`RFC_READ_TABLE`、`RPY_PROGRAM_READ`、`INST_EXECUTE_REPORT`），现共 **95 个 Tool / 98 项固定函数白名单**。18 项本地回归通过。所有 Tool 仍然只读，修改类能力需要用户额外授权；`run_report` 只运行 `config/reviewed_reports.json` 中登记并且审核后源码未改动的只显示报表。

## 环境准备（Windows PowerShell）

```powershell
cd "<path-to>\sap-data-mcp\private_cloud\rfc"
..\..\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` 仅供本地使用（`SAP_USERNAME` / `SAP_PASSWORD`），不要提交到版本控制。目标系统由 `config/SAP_SYSTEM_INFO` 决定，
可用 `.\scripts\switch-sap-system.ps1 -System <SID>` 切换（把 `config/systems/` 下对应系统的参数复制过去）。
依赖版本已固定为 GOLDEN_PATH 中验证过的版本；代码用到 MCP SDK 2.2 的内部接口，升级前需要重新验证。

## 启动

MCP Server 使用 stdio 传输；启动后会保持等待客户端连接，这是正常行为。按 `Ctrl+C` 停止。

```powershell
..\..\.venv\Scripts\python.exe server.py
```

调试可使用官方 MCP Inspector：`..\..\.venv\Scripts\mcp.exe dev server.py`

## 目录结构

```text
private_cloud/rfc/
├── server.py                   入口：注册全部 Tool 并以 stdio 启动
├── requirements.txt
├── .env / .env.example         本地 Credential（.env 不提交）
├── core/                       MCP Server、审计和公共函数
├── connectors/                 PyRFC 连接和只读函数白名单
├── tools/
│   ├── platform/              Health、Server Info、审计
│   ├── master_data/           Material、Business Partner / Supplier
│   ├── mm/                    Purchasing、Inventory Management
│   ├── pp/                    Production Order
│   ├── sd/                    Sales Order
│   ├── basis/                 RFC 连接、ST22、SM21、SLG1、SM37、表显示、源码显示
│   └── integration/           IDoc、qRFC/tRFC/bgRFC、Gateway 注册检查
├── config/                      当前系统、命名系统配置和 HTTPS 证书
├── scripts/                     目标系统切换
├── docs/GOLDEN_PATH.md          RFC 成功路径与安全边界
└── logs/                       调用审计日志
```

新增 SAP 函数时，必须先确认它是标准只读函数，再把函数名加入 `READ_ONLY_FUNCTIONS`，否则 Connector 会直接拒绝调用。

## Tool 一览

在同一 MCP 会话中，先调用一次 `test_sap_rfc_connection`（每个进程只尝试登录一次，避免锁定账号），再调用其它 SAP Tool。

| 领域 | Tool | 使用的 SAP 函数 |
|---|---|---|
| 基础 | `health_check`、`get_server_info`、`test_sap_rfc_connection`、`get_sap_system_info` | `RFC_SYSTEM_INFO` |
| 采购订单 | `get_purchase_order`、`search_purchase_orders` | `BAPI_PO_GETDETAIL1`、`BAPI_PO_GETITEMS` |
| 生产订单 | `find_production_order`、`search_production_orders`、`get_production_order` | `BAPI_PRODORD_GET_LIST` |
| 销售订单 | `search_sales_orders`、`get_sales_order` | `BAPI_SALESORDER_GETLIST`、`BAPI_SALESORDER_GETSTATUS` |
| 物料主数据 | `search_materials`、`get_material` | `BAPI_MATERIAL_GETLIST`、`BAPI_MATERIAL_GET_ALL` |
| 供应商 / BP | `search_business_partners`、`get_business_partner`、`get_supplier` | `BAPI_BUPA_SEARCH_2`、`BAPI_BUPA_CENTRAL_GETDETAIL`、`BAPI_BUPA_ROLES_GET_2`、`BAPI_BUPA_ADDRESS_GETDETAIL`、`BAPI_BUPA_TAX_GETDETAILS`、`BAPI_BUPA_BANKDETAILS_GET`、`BAPI_VENDOR_GETDETAIL` |
| 采购申请 | `get_purchase_requisition`、`search_purchase_requisitions` | `BAPI_PR_GETDETAIL`、`BAPI_REQUISITION_GETITEMS` |
| MM 供应商发票 | `search_supplier_invoices`、`get_supplier_invoice` | `BAPI_INCOMINGINVOICE_GETLIST`、`BAPI_INCOMINGINVOICE_GETDETAIL` |
| IM 盘点凭证 | `search_physical_inventory_documents`、`get_physical_inventory_document` | `BAPI_MATPHYSINV_GETLIST`、`BAPI_MATPHYSINV_GETDETAIL` |
| 预留 | `search_reservations`、`get_reservation` | `BAPI_RESERVATION_GETITEMS1`、`BAPI_RESERVATION_GETDETAIL1` |
| 物料凭证（收发货） | `get_material_document`、`search_material_documents` | `BAPI_GOODSMVT_GETDETAIL`、`BAPI_GOODSMVT_GETITEMS` |
| 采购信息记录 | `search_purchasing_info_records`、`get_purchasing_info_record` | `BAPI_INFORECORD_GETLIST` |
| 采购合同 | `get_purchase_contract` | `BAPI_CONTRACT_GETDETAIL` |
| 采购计划协议 | `get_scheduling_agreement` | `BAPI_SAG_GETDETAIL` |
| 采购订单历史 | `get_purchase_order_history` | 复用 `BAPI_PO_GETDETAIL1` |
| 经典服务验收单 | `search_service_entry_sheets`、`get_service_entry_sheet` | `BAPI_ENTRYSHEET_GETLIST`、`BAPI_ENTRYSHEET_GETDETAIL` |
| 批次主数据 | `get_batch` | `BAPI_BATCH_GET_DETAIL` |
| 库存 | `get_material_stock`、`search_material_stock` | `BAPI_MATERIAL_STOCK_REQ_LIST`（MD04）、`/SPE/MATERIAL_STOCK_READ`（标准 IM 库存地点 / 批次 / 特殊库存） |
| 表显示（SE16N，只读） | `list_table_fields`、`read_table`、`summarize_table` | `DDIF_FIELDINFO_GET`、`RFC_READ_TABLE` |
| 源码显示（SE38，只读） | `read_program_source` | `RPY_PROGRAM_READ` |
| 运行已审核的只显示报表 | `run_report` | `INST_EXECUTE_REPORT`（只限 `config/reviewed_reports.json` 登记的报表）；运行前用 `RFC_READ_TABLE` 读 TRDIR 检查源码是否改动 |
| ST22 | `list_short_dumps` | `/SDF/GET_DUMP_LOG` |
| SM21 | `list_system_log` | `/SDF/GET_SYS_LOG` |
| SLG1 | `search_application_logs`、`get_application_log_messages` | `/SDF/GET_APP_LOG`、`BAPI_APPLICATIONLOG_GETDETAIL` |
| SM37 | `list_background_jobs`、`get_background_job_log` | `BAPI_XBP_JOB_SELECT`（XMI 会话内）、`/SDF/GET_JOB_INFO` |
| IDoc | `list_idocs`、`get_idoc` | `/SDF/IMA_DC_IDOC`、`EDI_DOCUMENT_OPEN_FOR_READ`、`EDI_DOCUMENT_READ_ALL_STATUS`、`EDI_SEGMENTS_GET_ALL`、`EDI_DOCUMENT_CLOSE_READ` |
| 队列 | `list_qrfc_queues`（SMQ1/SMQ2）、`list_trfc_errors`（SM58）、`get_bgrfc_overview` | `TRFC_QIN_OVERVIEW`、`TRFC_QOUT_OVERVIEW`、`/SDF/GPC_GET_TRFC_ERRORS`、`BGRFC_GET_OVERVIEW_INFORMATION` |
| OData | `check_odata_services` | `/IWFND/FM_DOES_SERVICE_EXIST`、`/IWFND/FM_GET_ALL_SRV_AND_MDL` |
| 审计 | `get_tool_call_log` | 本地日志文件 |
| HTTPS（旧） | `test_sap_connection` | `/sap/bc/ping`，使用 `.env` 中的 `SAP_BASE_URL` |

每个 Tool 的参数说明见其 docstring（MCP 客户端中显示为 Tool 描述）。

发票搜索必须提供供应商与起止单据日期（最多相隔 366 天）；盘点搜索必须提供工厂与会计年度；预留搜索必须提供工厂，采用 BAPI 默认的移动 / 最终发货筛选条件。发票与盘点明细必须同时提供编号和会计年度。三类搜索的 `max_results` 都在本地截断，不限制 SAP 查询行数。标准数量、金额中的零值保留，不推断付款状态，不录入盘点、不重盘、不过账差异、不修改预留。

新增采购、生产、销售搜索工具的 `max_results` 在本地截断结果，不限制 SAP 查询行数。采购搜索至少提供一个组织或业务筛选，生产搜索必须提供工厂，销售搜索必须提供客户与销售组织。生产订单读取仅返回基本抬头；销售订单读取仅返回 SAP `STATUSINFO` 中的基本行项与状态，不包含完整单据流。

## 通用约定

- 返回结果中的 `status`：`ok`、`not_found`、`partial`（部分视图/数据读取失败）、`error`。`return_messages` 为 SAP 原始返回消息。
- 数字编号（物料、BP、供应商、采购申请、物料凭证、IDoc 等）可以省略前导零。
- 业务 Tool 返回 SAP 原始字段名，并省略空字段；列表类 Tool 返回 `total` / `returned` / `truncated`。
- 监控类 Tool 的日期时间都是 **SAP 应用服务器本地时间**（与 SAP GUI 中 ST22/SM21/SM37 显示一致），
  结果中的 `window.time_zone` 会注明。日期默认取服务器的“今天”。时间窗口上限：ST22 / IDoc / tRFC 31 天，SM21 / SLG1 / SM37 7 天。
- Tool 结果和错误信息中，本机配置的 SAP 登录用户名显示为 `[REDACTED]`。

## 调用审计日志

每一次 Tool 调用（包括参数校验失败、未知 Tool 和异常）都会追加一行 JSON 到 `logs/tool_calls_YYYY-MM-DD.jsonl`
（按本机日期分文件；日志已在 `.gitignore` 中排除）。字段的详细解释、示例和查看方法见 [logs/README.md](logs/README.md)。字段：

| 字段 | 含义 |
|---|---|
| `timestamp` | 调用完成时间（本机时间，带时区） |
| `session_id` / `request_id` | MCP Server 进程会话 ID / MCP 请求 ID |
| `mcp_client` | MCP 客户端名称和版本 |
| `os_user` | 运行 MCP Server 的 Windows 账号 |
| `sap_user`、`sap_system`、`sap_client` | 使用的 SAP 登录账号、系统、集团 |
| `tool`、`arguments` | 调用的 Tool 及传入参数 |
| `status`、`error` | 结果状态和错误信息 |
| `rfc_functions` | 本次调用实际执行的 SAP 函数 |
| `duration_ms` | 耗时 |

日志从不记录密码。日志文件和 `get_tool_call_log` 都显示 SAP 登录账号（其它 Tool 结果中仍遮蔽为 `[REDACTED]`）。
日志不会自动清理，请按需归档或删除。

## 所需 SAP 权限

若某个 Tool 返回权限错误，请 Basis 为 RFC 用户补充相应权限，常见的有：

- `S_RFC`：以上函数所在的函数组；
- `/SDF/E2E`（ACTVT 03）：`list_idocs`、`list_trfc_errors`；
- `S_XMI_PROD`：`list_background_jobs` 的 XMI 登录（`BAPI_XMI_LOGON` / `BAPI_XMI_LOGOFF` 只会在 SAP 的 XMI 日志中记录会话）；
- 事务码 `/IWFND/MAINT_SERVICE`：`check_odata_services`；
- `S_TABU_NAM` 或 `S_TABU_DIS`（ACTVT 03）：`read_table`、`summarize_table` 要读的表；
- `S_DEVELOP`（ACTVT 03）：`read_program_source` 要看的程序；
- 事务码 `SA38` 以及报表自身的权限：`run_report`。

`run_report` 的限制：只接受 `NAME = value` 和 `NAME IN a, b`（`INST_EXECUTE_REPORT` 只能传“包含、等于”的选择条件）；列表每行超过 256 个字符的部分被 SAP 截掉；不能下钻。新增报表的步骤：先用 `read_program_source` 读完源码，确认只读取业务数据，再把报表、选择字段、审核日期和当时的最后修改日期登记到 `config/reviewed_reports.json`（改登记文件不需要重启 Server）。

查表 Tool 的筛选条件写法：条件之间用 `;` 分隔并以 AND 连接，例如
`WERKS = 1010; BUDAT BETWEEN 20260801 AND 20260831; BWART IN 101, 261; MATNR LIKE 4000*`。
值由 Tool 加引号；日期写 `YYYYMMDD`，数字物料号写 18 位带前导零的内部格式。所选字段总宽度不能超过 512 个字符。
`summarize_table` 在本地汇总，`complete` 为 `false` 时表示匹配的行数超过了扫描上限，合计不完整。

## 已知限制

- `test_sap_connection` 走 `SAP_BASE_URL`，与 `config/SAP_SYSTEM_INFO` 的目标系统无关。它直连 SAP，
  忽略环境变量和 Windows 系统设置中的代理（例如公司代理）。自签名证书请通过 `SAP_CA_BUNDLE` 指定。
- `dev_rfc.log` 由 SAP RFC 库在连接出错时自动写入 Server 的工作目录（按上面的启动方式即 `private_cloud/rfc/`），仅用于排查连接问题，可随时删除。
  项目路径含中文（“桌面”）时，RFC 库无法把它改写到 `logs/`，所以它留在工作目录。
- 如果 SAP 系统只能通过 VPN 访问，使用前需要先连上 VPN。Server 每次启动只尝试登录一次 SAP；VPN 断开时登录失败，连上后需重启 MCP Server。
- `list_idocs` 每次最多扫描 5000 个 IDoc，从时间窗口起点开始；`window_complete` 为 `false` 时请缩小窗口。
- `get_material_stock` 的库存地点明细需要指定库存地点（`storage_location`，可逗号分隔）。
