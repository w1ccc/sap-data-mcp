# Public Cloud API Provider

标准 SAP 只读工具：154 个业务 Tool + 4 个基础 / 连接 / 审计 Tool，共 158 个。覆盖 MM/IM、PP、SD、EWM、FI、CO、已激活主数据和 QM；各模块及接口缺口以根 README 为准。与私有 OData 共用工具实现，独立运行、配置和记录日志。工具清单及使用方式见[项目说明](../../README.md)。不自动操作 Fiori 页面，也不使用 RFC/PyRFC。

在项目根目录执行：

```powershell
cd public_cloud/api
..\..\.venv\Scripts\python.exe server.py
```

MCP 服务名为 `sap_public_api`。将根 `.env.example` 复制到本目录为 `.env`，填真实租户与通信用户或 OAuth 客户端信息。当前没有租户配置；未配置时工具会返回 `ConfigurationError`，不会读取私有云凭据或连接私有系统。

| 对象 | 固定 Released API / 版本 |
|---|---|
| 物料 | `API_PRODUCT`，OData V4 `product/0002` |
| 供应商 | `API_BUSINESS_PARTNER`，OData V2 |
| 采购申请 | `API_PURCHASEREQUISITION_2`，OData V4 `purchaserequisition/0001` |
| 采购订单 | `API_PURCHASEORDER_2`，OData V4 `purchaseorder/0001` |
| 物料凭证 | `API_MATERIAL_DOCUMENT_SRV`，OData V2 |
| IM 库存 | `API_MATERIAL_STOCK_SRV`，OData V2 |
| MM 供应商发票 | `API_SUPPLIERINVOICE_PROCESS_SRV`，OData V2 |
| IM 盘点凭证 | `API_PHYSICAL_INVENTORY_DOC_SRV`，OData V2 |
| 预留 | `API_RESERVATION_DOCUMENT_SRV`，OData V2 |
| 批次主数据 | `API_BATCH_SRV` |
| 采购信息记录 | `API_INFORECORD_PROCESS_SRV` |
| 货源清单 | `API_PURCHASING_SOURCE_SRV` |
| 配额协议 | `API_PUR_QUOTA_ARRANGEMENT_SRV` |
| 采购合同 | `API_PURCHASECONTRACT_PROCESS_SRV;v=0002` |
| 采购计划协议 | `API_SCHED_AGRMT_PROCESS_SRV` |
| 询价单 | `API_RFQ_PROCESS_SRV` |
| 供应商报价 | `API_QTN_PROCESS_SRV` |
| 精简服务验收单 | `API_SERVICE_ENTRY_SHEET_SRV` |

每个 API 都需要在租户中配置相应 Communication Arrangement、认证和读取权限。版本映射固定，不回退到已弃用的公有云采购 V2 接口。`test_sap_api_connection` 每次只检查指定 API 的元数据。

标准接口参考：[Product V2](https://help.sap.com/docs/SAP_S4HANA_CLOUD/3c916ef10fc240c9afc594b346ffaf77/26089fa7cff8499d81c57bdcb51fe694.html)、[采购申请 V4](https://help.sap.com/docs/SAP_S4HANA_CLOUD/bb9f1469daf04bd894ab2167f8132a1a/de371314a0fc46e5a54b0c1cdd0d8ce4.html)、[采购订单 V4](https://help.sap.com/docs/SAP_S4HANA_CLOUD/bb9f1469daf04bd894ab2167f8132a1a/649d14483a984b788f3753ac88b37810.html)、[IM 库存](https://help.sap.com/docs/SAP_S4HANA_CLOUD/3f57e7df4a114edabffe8b2d581a59ed/dfc5b3e292874297843ed6cfb08eb83a.html)、[物料凭证](https://help.sap.com/docs/SAP_S4HANA_CLOUD/3f57e7df4a114edabffe8b2d581a59ed/1aef4e402acd4c8b8ec2ea2bfda7715b.html)。

