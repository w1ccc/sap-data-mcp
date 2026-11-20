# 调用审计日志说明

本文件夹保存 sap-data-mcp 的**工具调用审计日志**：MCP Server 每执行一次 Tool 调用，就在日志里追加一条记录。
失败的调用也会记录，包括参数不合法、调用了不存在的 Tool、程序异常。

## 文件

- 文件名：`tool_calls_YYYY-MM-DD.jsonl`，按**这台电脑的本地日期**每天一个文件。
- 格式：JSON Lines，**一行是一条完整的 JSON 记录**，只追加、不修改。
- 多个 MCP 客户端同时使用时（例如 Claude Code 和 Codex 各开一个 Server），会写入同一个文件，用 `session_id` 区分。
- 不会自动清理，请按需归档或删除。

## 示例记录

```json
{
 "timestamp": "2026-09-29T04:17:37.587+08:00",
 "session_id": "8cc38bd39818",
 "request_id": "8",
 "mcp_client": "check 1.0",
 "os_user": "jdoe",
 "sap_user": "RFC_READER",
 "sap_system": "S4Q",
 "sap_client": "100",
 "tool": "list_background_jobs",
 "arguments": {"job_name": "ZDEMO_JOB", "max_results": 1000},
 "status": "ok",
 "error": null,
 "rfc_functions": ["RFC_SYSTEM_INFO", "BAPI_XMI_LOGON", "BAPI_XBP_JOB_SELECT", "BAPI_XMI_LOGOFF"],
 "duration_ms": 920
}
```

## 字段说明

| 字段 | 含义 | 说明 |
|---|---|---|
| `timestamp` | 调用完成的时间 | 这台电脑的本地时间，带时区（`+08:00` 为北京时间），精确到毫秒。注意它**不是** SAP 服务器时间 |
| `session_id` | MCP Server 进程编号 | Server 每启动一次生成一个新值；同一个值的记录属于同一次会话 |
| `request_id` | 请求编号 | 同一会话内由 MCP 客户端递增分配，和 `session_id` 一起唯一确定一次调用 |
| `mcp_client` | 调用方客户端 | 客户端名称和版本，例如 Claude Code 或 Codex；示例中的 `check 1.0` 是测试脚本 |
| `os_user` | Windows 账号 | 运行 MCP Server 的电脑登录账号，即“谁在用” |
| `sap_user` | SAP 登录账号 | 这次调用登录 SAP 所用的账号，来自 `.env` 的 `SAP_USERNAME` |
| `sap_system` | SAP 系统 | 调用时 `config/SAP_SYSTEM_INFO` 指向的系统，例如 `S4D`、`S4Q` |
| `sap_client` | SAP 集团 | 例如 `100` |
| `tool` | 调用的 Tool | 例如 `get_material`、`list_background_jobs` |
| `arguments` | 传入的参数 | 客户端实际传的参数；超过 1000 个字符的文本会截断，并标记 `...[truncated]` |
| `status` | 结果状态 | 见下表 |
| `error` | 错误原因 | 仅在 `error` / `exception` 时有值，否则为 `null` |
| `rfc_functions` | 实际执行的 SAP 函数 | 按执行顺序列出，包括执行失败的；为空 `[]` 表示没有访问 SAP，例如参数校验失败或查看本日志。示例：先读 SAP 服务器时钟，再做 XMI 登录、查询作业、XMI 登出 |
| `duration_ms` | 耗时 | 从收到调用到返回结果的毫秒数 |

### `status` 取值

| 值 | 含义 |
|---|---|
| `ok` | 成功 |
| `not_found` | 调用成功，但 SAP 中没有符合条件的数据 |
| `partial` | 部分成功，例如物料存在但某个工厂视图读取失败 |
| `error` | Tool 正常返回了错误，例如未登录、参数不合法、SAP 返回错误消息或无权限 |
| `exception` | 调用在 Tool 执行前或执行中被中断，例如调用了不存在的 Tool、缺少必填参数、程序异常 |

## 查看方式

- 在 MCP 客户端中调用 `get_tool_call_log`，可按 `tool`、`status` 过滤，最近的记录排在最前。
- 用 PowerShell 查看，例如列出今天所有失败的调用：

```powershell
Get-Content .\tool_calls_2026-09-29.jsonl -Encoding UTF8 | ConvertFrom-Json |
  Where-Object status -in 'error','exception' |
  Format-Table timestamp, os_user, sap_user, tool, status, error -AutoSize
```

## 安全

- 日志**从不记录密码**。
- 日志包含 SAP 账号和业务查询参数（物料号、供应商号等），属于内部信息，不要外发。
- 本文件夹已在 `.gitignore` 中排除（只保留本说明文件），日志不会被提交到版本控制。
