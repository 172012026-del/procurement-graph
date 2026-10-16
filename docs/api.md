# API 接口

所有查询默认 `dataset_id=default`，可指定 `official`、`demo` 或导入时使用的数据集。金额均为元，只有标准 XLSX 导出转换为万元。配置 `APP_API_TOKEN` 后，除健康接口外的 `/api/` 请求须携带 `Authorization: Bearer <token>`。

| 方法 | 路径 | 用途及主要参数 |
|---|---|---|
| GET | `/api/health` | 配置、模型名、解析工具可用性；不发模型请求、不返回密钥 |
| GET | `/api/settings/model` | 当前模型地址、名称、启用状态及Key是否已配置；不返回Key |
| POST | `/api/settings/model` | JSON：`base_url`、`model`、`api_key`、`enabled`；持久保存并供新任务使用，Key空值保留原值，不发模型请求 |
| GET | `/api/samples` | 回放样本的规模、范围和可用性 |
| GET | `/api/knowledge` | `q`、`top_k`：本地域规则检索，不调用模型、不返回采购事实 |
| GET | `/api/samples/input.zip` | 下载20条样本公告ZIP |
| POST | `/api/samples/replay` | JSON：`dataset_id`；仅回放随项目提供的历史响应 |
| GET | `/api/datasets` | 数据集及公告/采购包数量 |
| GET | `/api/stats` | 当前数据集计数、已披露金额、未知金额/部分/兜底计数；自报置信度 |
| POST | `/api/ingest` | multipart：`files`、`dataset_id`、`mode=extract/parse-only/replay`；202 返回批次 |
| POST | `/api/ingest/local` | JSON：`dataset_id`、`limit`、`notice_ids`、`mode`；只读取服务器配置的官方目录 |
| GET | `/api/jobs` | 数据集的最近批次；`limit` 1—100 |
| GET | `/api/jobs/{id}` | 持久进度、`mode`、完整/待复核/失败/复用数、耗时、`finished` |
| GET | `/api/jobs/{id}/documents` | 逐公告状态与错误；`page`、`page_size` 最大200 |
| POST | `/api/jobs/{id}/retry` | 创建新批次；输入必须仍可用，完整且指纹一致的公告复用缓存 |
| GET | `/api/projects` | 采购包列表；`q` 匹配名称、编号、UUID、包名，`purchaser`，分页 |
| GET | `/api/projects/{id}` | 包详情、投标人审查、原始标的证据及 `item_hierarchy` 分层核验；受数据集约束 |
| GET | `/api/items` | 七字段、项目名、采购单位及中标供应商综合检索；分类、品牌、完整型号、来源、采购单位、中标供应商和数值范围筛选 |
| GET | `/api/entities` | `type=purchaser/supplier/brand/category` 主体候选 |
| GET | `/api/analytics/purchaser-partners` | `purchaser`，中标合作与品牌画像 |
| GET | `/api/analytics/purchaser-bidders` | `purchaser`，有效投标人TOP5及同包组合 |
| GET | `/api/analytics/supplier-competitors` | `supplier`，`history_scope=all/winning`，竞争主体及TOP5 |
| GET | `/api/analytics/common-purchasers` | `suppliers=甲,乙`，至少2个不同主体；采购包金额去重 |
| GET | `/api/analytics/common-projects` | `suppliers=甲,乙`，必须同时出现在同一已确认采购包 |
| GET | `/api/graph` | 当前数据集图；`limit` 1—300 个采购包，兜底与无效投标排除 |
| GET | `/api/export/standard.xlsx` | 严格三表，`job_id` 可选；`item_view=source/detail` 默认原文，明细视图仅折叠确认摘要；`include_notes=true` 仅内部复核 |
| GET | `/api/export/quality.json` | 逐公告处理状态、告警、空结果依据、批次失败清单及层级核验依据；接受相同 `item_view` |
| GET | `/api/export/items.csv` | 兼容导出；字段明确标注 `_yuan`，不是比赛三表 |

标的范围参数：`min_price/max_price`、`min_quantity/max_quantity`、`min_total/max_total`。上下限均含边界，单价和总价以元输入。`page>=1`，`page_size` 1—200；项目列表最大100。无披露金额保留空值，汇总另给 `unknown_amount_count`。

模型配置接口仅在本机访问或已配置访问令牌时可用，拒绝跨站页面请求。返回体只含 `base_url`、`model`、`api_key_configured`、`enabled`、`configuration_error`；校验失败不回显输入的Key。保存失败返回422或503，不覆盖原文件。保存位置、优先级和远程部署见[模型配置说明](model-settings.md)。

三表下载文件名为 `procurement-tables.xlsx`；指定 `job_id` 时为 `procurement-batch-tables.xlsx`，明细视图为 `procurement-detail-tables.xlsx`，同时指定批次和明细时为 `procurement-batch-detail-tables.xlsx`。三张工作表的表名、字段及金额单位保持相同。

## 批次状态

`queued → processing → completed / completed_with_warnings / completed_with_errors / failed`；服务重启将未结束任务标为 `interrupted`。前端依据 `finished` 终止轮询。

逐公告包括 `complete`、`cached`、`parsed`、`partial`、`fallback`、`failed`。`succeeded` 包含完整结果、缓存命中或预检通过；`partial` 包括部分抽取和规则兜底，不能与完整成功混为一谈。`mode` 用于区分预检和抽取。预检批次不允许生成三表。

同一服务只接受一个活动批次，冲突返回409。输入不合法返回400/422；上传超限413；需要令牌401。UUID 仅作为原始公告标识，包名另存，当前不会猜测样例中的 `_01/_02` 规则。

## 性能口径

`X-Response-Time-Ms` 只记录服务端响应开始前的时间，不覆盖下载完成、网络及页面渲染。批次 `elapsed_seconds` 覆盖发现文件、解析、抽取、写入及配置的镜像同步。评测脚本与合成性能脚本分别声明自身计时范围，均不得直接称为官方性能。
