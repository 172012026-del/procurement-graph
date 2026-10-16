# 数据说明

## 本机完整输入

`data/official-benchmark/html`包含1038份公告，`file`包含970个公告级附件ZIP。公告UUID由原文件名确定，同名HTML与ZIP配对；68条公告没有同名附件包，不直接视为文件丢失。

完整输入约3.4GiB，保留在本机并从Git提交范围排除。输出标准保存在`data/official-benchmark/format`，三表字段定义保存在`indexes/output-schema.json`。

数据准备命令：

```powershell
.\demo\procurement\.venv\Scripts\python.exe .\scripts\prepare_official_data.py --source-dir "C:\path\to\competition-files"
```

原始压缩包不被删除或改写。脚本按提供的数据命名读取外层文件，只整理输入和索引，不调用模型。

## 随源码提供的样本

`demo/procurement/data/demo`包含20条公告、历史模型响应、结构化结果及清单。首次启动将结果加载到`official-reference`数据集；在数据接入页可下载公告ZIP并重新回放。

样本仅覆盖公告正文，不能作为完整附件演示。历史响应缓存用于复现已有提取结果，不代表对新文件的推理能力。

## 参考标注与验证

`data/reference/announcements.jsonl`覆盖79条标准商品行；`relationships.jsonl`覆盖20公告、26采购包、123条投标事实。它们由程序生成并核对来源，尚未完成独立人工双人复核，不能作为官方评分答案。

参考集曾用于调试，原有`diagnostic/holdout`字段只是历史分组，不能据此宣称独立留出测试。`gold.example.jsonl`是评测格式示例，不是模型效果证明。

正文回放产生138条商品，其中59条额外细表未纳入79行参考。含附件回放产生216条商品，两种结果对应不同输入范围；不能将商品数量增加直接解释为准确率提高。

## 本地缓存和数据库

- `.cache/model-responses`：历史模型响应，保留以减少重复请求。
- `.cache/parsed`：已解析文本，可重建。
- `demo/procurement/data/entity_mining.db`：当前业务数据库。
- `demo/procurement/data/uploads`：上传原件及重试所需输入。
- `results/offline-release`、`offline-direct`、`offline-attachments-final`：保留的三个有效验证结果集。

上述运行数据默认不提交Git。完整公告及附件的来源、原始哈希和异常索引保留在本机。
