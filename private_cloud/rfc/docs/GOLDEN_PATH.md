# Private Cloud / On-Premise RFC Golden Path

## 1. 目标与成功路径

这是本项目已经实际跑通的 SAP RFC 连接路径，只保留成功步骤：

```text
MCP Client
    ↓ stdio
server.py / core.app (MCPServer)
    ↓ SAPRFCConnector
PyRFC Connection
    ↓
SAP NetWeaver RFC runtime
    ↓ RFC
SAP <SID> / Client <CLIENT>
    ↓
RFC_SYSTEM_INFO
```

连接验收标准：

1. MCP Server 能启动。
2. `import pyrfc` 成功。
3. `test_sap_rfc_connection` 返回 `status: ok`。
4. 在同一 MCP Server 进程内，`get_sap_system_info` 成功返回 `RFC_SYSTEM_INFO`。

## 2. 已验证的本机基线

| 项目 | 已验证值 |
|---|---|
| 操作系统 | Windows x64 |
| Python | 3.12.10 x64 |
| Python 路径 | `C:\Users\<user>\AppData\Local\Programs\Python\Python312\python.exe` |
| 项目虚拟环境 | 上层 `sap-data-mcp/.venv` |
| MCP SDK | 2.2.0 |
| httpx | 0.28.1 |
| python-dotenv | 1.2.3 |
| PyRFC | 3.3.1 |
| RFC runtime | `C:\Windows\System32\sapnwrfc.dll` |
| RFC runtime 版本 | 7.53, patch 1533 |
| SAP System ID | S4D |
| SAP Client | 100 |

## 3. 准备 Python 3.12 x64

通过 Windows 官方 `winget` 渠道以当前用户范围安装 Python 3.12 x64：

```powershell
winget install --id Python.Python.3.12 --exact --scope user --architecture x64
```

验证：

```powershell
py -0p
py -3.12 --version
```

成功基线：

```text
Python 3.12.10
C:\Users\<user>\AppData\Local\Programs\Python\Python312\python.exe
```

## 4. 创建项目虚拟环境

在项目目录执行：

```powershell
cd "<path-to>\sap-data-mcp"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe --version
```

验收输出：

```text
Python 3.12.10
```

## 5. 安装已验证依赖

`requirements.txt` 的直接依赖：

```text
mcp[cli]
httpx
python-dotenv
pyrfc==3.3.1
```

安装：

```powershell
cd "<path-to>\sap-data-mcp\private_cloud\rfc"
..\..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

验证 PyRFC 及 RFC runtime 可加载：

```powershell
..\..\.venv\Scripts\python.exe -c "import pyrfc; print(pyrfc.__version__)"
```

验收输出：

```text
3.3.1
```

本机直接使用现有 RFC runtime，没有复制或替换 `C:\Windows\System32` 中的 DLL。

## 6. 配置 SAP System Info 与本地 Credential

`config/SAP_SYSTEM_INFO` 是 RFC 非敏感参数的唯一配置源。示例（请替换为自己的系统参数）：

```text
System Name: S4D
Environment: DEV
System ID: S4D
Application Server: <APPLICATION_SERVER>
System Number: 00
Client: 100
Language: EN
Connection Type: RFC
```

新系统从 `config/SAP_SYSTEM_INFO.example` 复制为 `config/systems/<系统>`，只修改上述非敏感字段，再用 `scripts/switch-sap-system.ps1` 切换。`Application Server` 保留实际已验证的 RFC 连接目标，不用 `RFC_SYSTEM_INFO` 返回的主机名自动覆盖。

Provider 目录下的 `private_cloud/rfc/.env`（不是仓库根目录 `sap-data-mcp/`）仅作为本地 Credential 来源：

```ini
SAP_USERNAME=<本地填写>
SAP_PASSWORD=<本地填写>
```

现有 `.env` 中的历史非敏感键可保留，但 RFC Connector 不再依赖它们。`.env` 只保留在本场景中，不提交到版本控制。任何地方都不得输出密码。调用审计日志（第 13 节，包括日志文件和 `get_tool_call_log`）显示 SAP 登录账号；其它 MCP Tool 结果和错误信息中，本机配置的 SAP 登录用户名显示为 `[REDACTED]`。

## 7. 通过 SAP RFC Connector 建立连接

`connectors/sap_rfc_connector.py` 是项目中唯一直接导入和调用 PyRFC 的位置。`core/app.py` 只创建一个 Connector，`tools/` 中的所有 Tool 共用它：

```python
sap_rfc = SAPRFCConnector(SYSTEM_INFO_PATH, PROJECT_DIR / ".env")
```

成功路径的关键点：

- `Application Server` 对应 PyRFC `ashost`。
- `System Number` 对应 `sysnr`。
- `Client` 对应 `client`。
- `SAP_USERNAME` 对应 `user`。
- `SAP_PASSWORD` 对应 `passwd`。
- `Language` 对应 `lang`。
- 一个 MCP Server 进程只建立一个 RFC Connection，后续固定的只读 Tool 通过 `sap_rfc.call(...)` 复用该连接。
- MCP Tool 不直接导入 PyRFC，也不允许用户传入任意 RFC Function Name。
- `SAPRFCConnector.call` 只接受 `READ_ONLY_FUNCTIONS` 白名单中的函数名，其它名称在发往 SAP 之前就被拒绝。
- Server 退出时关闭 RFC Connection。

## 8. 启动 MCP Server

```powershell
..\..\.venv\Scripts\python.exe server.py
```

Server 使用 `stdio` transport：

```python
mcp.run(transport="stdio")
```

启动后保持等待 MCP Client 是正常状态。

## 9. MCP Client 验证顺序

在同一个 MCP Server 会话中按以下顺序调用：

### 9.1 `health_check`

期望结果：

```json
{
  "status": "ok",
  "server": "sap-data-mcp"
}
```

### 9.2 `test_sap_rfc_connection`

该 Tool 从 `config/SAP_SYSTEM_INFO` 读取非敏感 RFC 参数，从 `.env` 读取 Credential，建立并缓存 Connector 内的 `pyrfc.Connection`。

已验证结果：

```json
{
  "status": "ok",
  "connection": "RFC",
  "system": "S4D",
  "client": "100"
}
```

### 9.3 `get_sap_system_info`

该 Tool 复用上一步的 RFC Connection，只调用一次标准只读系统信息函数：

```text
RFC_SYSTEM_INFO
```

已验证结果：

```json
{
  "status": "ok",
  "connection": "RFC",
  "system": "S4D",
  "client": "100",
  "application_server": "<sap-host>",
  "sap_release": "758",
  "kernel_release": "793",
  "operating_system": "Linux",
  "database_system": "HDB"
}
```

到这一步，以下链路已全部证明成功：

```text
MCP Client → MCP Server → Python/PyRFC → RFC runtime → SAP 登录 → RFC_SYSTEM_INFO
```

## 10. 已验证的只读扩展

连接成功后，已继续验证：

- `get_purchase_order`：通过标准 `BAPI_PO_GETDETAIL1` 读取采购订单。
- SAP Repository 元数据：通过标准只读 RFC 接口获取开发包和事务码信息。

（物料主数据、供应商 / BP、采购申请、物料凭证、库存、ST22、SM21、SLG1、SM37、IDoc、qRFC / tRFC / bgRFC、OData 服务检查、调用审计日志），
包括未登录、参数校验失败和数据不存在等路径。所用函数见 `READ_ONLY_FUNCTIONS`；其中 `/SDF/*` 监控函数的源码已确认只读取数据。

这些只读扩展都复用同一条 RFC 连接路径。

## 11. 必须保持的安全边界

- 所有 Tool 只读。任何创建、修改、删除、过账或提交数据的能力，都必须先得到用户的额外明确授权，再单独实现。
- 不在代码、日志、Tool 结果或文档中输出 Credential。
- 允许只读查表和只读查看源码：`list_table_fields`、`read_table`、`summarize_table` 通过 `DDIF_FIELDINFO_GET`、`RFC_READ_TABLE` 读取表字段和表内容（相当于 SE16N 显示），`read_program_source` 通过 `RPY_PROGRAM_READ` 读取程序源码（相当于 SE38 显示）。表名、字段名经过校验，筛选值由 Tool 加引号，不接受自由拼写的 SQL；存放密码哈希和密钥的表（`USR02`、`RFCDES` 等）不允许读取。
- 允许运行已审核的只显示报表（`run_report`）：`INST_EXECUTE_REPORT` 本身可以运行 RFC 用户有权用 SA38 启动的任何报表，所以 Tool 只接受登记在 `config/reviewed_reports.json` 里的报表（仓库中只附带示例登记）。登记前必须读过源码并确认它只读取业务数据；报表或其函数组的源码在审核后有改动时，Tool 拒绝运行，重新审核并更新登记后才恢复。Tool 只传登记过的选择屏幕字段，因此进不了该函数的后台作业模式。报表自身的技术日志会照常写入，这和用户在 SAP GUI 里运行报表时一样，不属于业务数据修改。
- 不调用 `BAPI_TRANSACTION_COMMIT`。
- 不调用创建、修改、删除、发布、过账或提交类 RFC/BAPI。
- 不执行名称中带有 `UPDATE` 的自定义 Function Module。
- 业务 Tool 只允许调用代码中固定的、已审核的标准只读 BAPI/RFC，不接受用户传入任意 RFC 函数名；Connector 的 `READ_ONLY_FUNCTIONS` 白名单强制执行这一点。
- 唯一的例外是 SM37 所需的 `BAPI_XMI_LOGON` / `BAPI_XMI_LOGOFF`：它们只在 SAP 的 XMI 日志中记录外部管理会话，不修改业务数据。

## 12. 最短日常启动流程

已完成环境安装、`config/SAP_SYSTEM_INFO` 和 `.env` 配置后，日常只需：

```powershell
cd "<path-to>\sap-data-mcp\private_cloud\rfc"
..\..\.venv\Scripts\python.exe server.py
```

然后在同一 MCP 会话中依次调用：

```text
health_check
test_sap_rfc_connection
get_sap_system_info
```

`test_sap_rfc_connection = ok` 且 `get_sap_system_info = ok` 即代表 Golden Path 完整跑通。

## 13. 调用审计日志

`core/app.py` 中的 `AuditedMCPServer.call_tool` 是所有 Tool 调用的统一入口，每次调用（包括参数校验失败、未知 Tool 和异常）
都会追加一行 JSON 到 `logs/tool_calls_YYYY-MM-DD.jsonl`，记录时间、会话、MCP 客户端、Windows 账号、SAP 登录账号、
SAP 系统 / 集团、Tool、参数、状态、错误、实际执行的 RFC 函数（由 Connector 记录）和耗时。

- 审计日志从不记录密码；写日志失败不会影响 Tool 调用本身。
- `logs/` 已在 `.gitignore` 中排除，不提交到版本控制。
- 日志文件和 `get_tool_call_log` 都显示 SAP 登录账号（`sap_user`），便于追溯是谁、用哪个账号调用了哪些 SAP 函数。
