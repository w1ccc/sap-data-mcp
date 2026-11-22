# Private Cloud OData Provider

标准 SAP 只读工具：155 个业务 Tool + 4 个基础 / 连接 / 审计 Tool，共 159 个，78 项服务映射。覆盖 MM/IM、PP、SD、EWM、FI、CO、已激活主数据和 QM；另提供私有 MDG 当前用户请求元数据查询。各模块、工具清单、分页约定及接口缺口以 [docs/COVERAGE.md](../../docs/COVERAGE.md) 为准，配置步骤见[项目说明](../../README.md#3-步上手)。不自动操作 Fiori 页面。

`search_mdg_my_change_requests` 只 GET `MDG_MYCR_SRV/ChangeRequests`，复用现有客户端、分页和审计；返回 `data_state=change_request_metadata`。需 MDG 组件、激活服务及 `SAP_MDG_MY_REQ_APP` 相关授权；独立 MDG 按本分支原方式启动独立进程并显式配置。该服务不在公有云分支注册，也不宣称支持暂存、校验执行或审批。

在项目根目录执行：

```powershell
cd private_cloud/odata
..\..\.venv\Scripts\python.exe server.py
```

MCP 服务名为 `sap_private_odata`。新部署时将根 `.env.example` 复制到本目录为 `.env`，填写本系统接入信息；已有配置不要覆盖。

| 对象 | 固定标准服务 |
|---|---|
| 物料 | `API_PRODUCT_SRV` |
| 供应商 | `API_BUSINESS_PARTNER` |
| 采购申请 | `API_PURCHASEREQ_PROCESS_SRV` |
| 采购订单 | `API_PURCHASEORDER_PROCESS_SRV` |
| 物料凭证 | `API_MATERIAL_DOCUMENT_SRV` |
| IM 库存 | `API_MATERIAL_STOCK_SRV` |
| MM 供应商发票 | `API_SUPPLIERINVOICE_PROCESS_SRV` |
| IM 盘点凭证 | `API_PHYSICAL_INVENTORY_DOC_SRV` |
| 预留 | `API_RESERVATION_DOCUMENT_SRV` |
| 批次主数据 | `API_BATCH_SRV` |
| 采购信息记录 | `API_INFORECORD_PROCESS_SRV` |
| 货源清单 | `API_PURCHASING_SOURCE_SRV` |
| 配额协议 | `API_PUR_QUOTA_ARRANGEMENT_SRV` |
| 采购合同 | `API_PURCHASECONTRACT_PROCESS_SRV;v=0002` |
| 采购计划协议 | `API_SCHED_AGRMT_PROCESS_SRV` |
| 询价单 | `API_RFQ_PROCESS_SRV` |
| 供应商报价 | `API_QTN_PROCESS_SRV` |
| 精简服务验收单 | `API_SERVICE_ENTRY_SHEET_SRV` |

现有 MM 映射继续使用原 V2；新增模块按已声明服务使用 V2 或 V4。上表仅列原 MM 服务，完整目录由 `get_server_info` 的 `service_catalog` 返回（含协议、版本路径与实体），连接检查枚举同步覆盖。每项服务需在目标系统分别激活 / 授权，不自动切换版本。

标准接口参考：[Product Master](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/bc6b9325fedd4344a84412b2195064fa/74aa2b58a333a107e10000000a441470.html)、[采购申请 V2](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/91af7f8d3acd47da90d33aaacfcd0d59/43c43f584eff2160e10000000a44147b.html)、[采购订单 V2](https://api.sap.com/api/API_PURCHASEORDER_PROCESS_SRV/overview)、[供应商](https://api.sap.com/api/API_BUSINESS_PARTNER/overview)。

