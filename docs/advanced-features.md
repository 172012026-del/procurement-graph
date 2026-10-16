# 可选能力

## 本地知识检索与RAG抽取

`backend/app/knowledge/procurement.json`保存金额、采购包、审查、联合体、声明函和来源证据六类领域规则。检索器使用中文二元词和BM25，无额外服务或嵌入模型。

`GET /api/knowledge?q=联合体报价`可查看检索结果。将 `.env` 中 `EXTRACTION_STRATEGY=rag` 后，新抽取会把相关规则加入当前文档的提示上下文，模型仍由原有网络开关控制。规则不作为公告事实或字段证据，也不读取验证集答案。

RAG请求使用独立响应缓存；规则内容变化也使处理指纹变化。随项目提供的历史响应属于 `schema` 策略，不能冒充RAG输出。回放内置样本时保持 `EXTRACTION_STRATEGY=schema`。

RAG路径已具备离线检索与模拟请求验证；提升准确率的幅度需要相同输入、模型和后处理条件下另行比较。

## Neo4j镜像与关系检索

默认SQLite提供全部功能。Neo4j可选保存采购单位、采购包、投标事实、供应商、标的和品牌，并按数据集隔离。明确失败的投标记录仍保留，查询聚合使用同一有效参与规则。

在 `.env` 设置私密 `NEO4J_PASSWORD` 后启动可选图服务：

```bash
docker compose --env-file .env -f demo/procurement/docker-compose.yml -f demo/procurement/docker-compose.graph.yml up --build -d
docker compose --env-file .env -f demo/procurement/docker-compose.yml -f demo/procurement/docker-compose.graph.yml exec api python -m app.graph_cli --dataset official-reference
```

图同步命令包含约束创建、存量同步、过期公告清理，以及该数据集五场景SQLite/Neo4j结果比对，不调用模型。首次同步成功后，设置 `RELATION_BACKEND=neo4j` 并重建API服务，即可由图数据库读取事实，再执行相同业务聚合。

图服务额外消耗内存。2核4GB机器优先使用默认SQLite；同机启用图服务时须验证附件解析峰值，必要时把Neo4j放在独立服务上。可选Compose将API上限降为2GB，图服务上限1.5GB，这些是限制值而非性能保证。

原生部署使用 `NEO4J_URI=bolt://127.0.0.1:7687`、`NEO4J_USER`、`NEO4J_PASSWORD`、`NEO4J_DATABASE`，执行 `python scripts/sync_graph.py --dataset official-reference`。Docker内部使用 `bolt://neo4j:7687`。

镜像缺失或原始公告快照已变化时，关系查询明确返回503，提示重新同步。其他SQLite页面和原始数据仍保留。旧数据没有公告快照时需重新导入，再启用图查询。图同步与查询必须在实际Neo4j环境执行验证，模拟驱动测试不代表图服务验收。

Neo4j部署参数参考[官方Docker文档](https://neo4j.com/docs/operations-manual/current/docker/introduction/)。

## 人工复核数据与LoRA

训练依赖独立放在 `training/requirements.txt`，不会安装进业务服务。准备数据不调用模型：

```bash
python scripts/prepare_finetune.py
```

输出在 `results/training`：`draft.jsonl`为历史预测草稿，`review-queue.json`记录原始公告与目标结果的哈希。人工修订时，先把随项目的 `sample-results.jsonl`复制为 `results/training/candidates.jsonl`，修订副本并用 `--candidates`指定，保留原始回放样本。重新生成队列后对照原文确认、填写复核人并设置 `approved=true`。目标或来源变化会使旧审批失效。

```bash
python scripts/prepare_finetune.py --candidates results/training/candidates.jsonl --reviews results/training/review-queue.json
python training/train_lora.py --data results/training --validate-only
```

只有审批有效的记录进入 `train.jsonl`、`validation.jsonl`。按公告划分训练和验证，拒绝跨集合重复公告及相同源内容。没有人工通过的数据时，两份文件为空，训练入口会拒绝执行。

在独立CUDA环境安装训练依赖，使用赛事允许的本地Qwen/DeepSeek基座与完整模型元数据；统一评审服务器不承担GPU推理托管：

```bash
python training/train_lora.py --data results/training --base-model /models/approved-model --model-profile config/model-profile.local.json --output results/lora-adapter
```

配方使用LoRA rank 8、q_proj/v_proj适配，训练损失仅计算助手输出。模型仅从本地加载，不自动下载或运行远程自定义代码；超长样本拒绝截断，需重新划分和复核。模型架构、GPU显存及中文表格效果需要实测。

保存的适配器还需由兼容推理服务加载，再通过模型接口接入应用。当前不包含训练完成的权重或收益证明。实现参考[PEFT LoRA](https://huggingface.co/docs/peft/v0.15.0/en/package_reference/lora)与[Transformers Trainer](https://huggingface.co/docs/transformers/v4.51.3/en/main_classes/trainer)。
