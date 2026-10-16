# 官方基准数据

| 目录 | 内容 |
|---|---|
| `html/` | 1038份公告，文件名为公告UUID；仅本机保留 |
| `file/` | 970个同名附件ZIP；仅本机保留 |
| `format/` | 补充输出说明PDF与标准XLSX模板 |
| `indexes/` | 文件配对、成员、异常、字段定义和哈希索引 |

附件包均找到同名公告。68条公告没有同名附件包，不直接视为输入丢失。压缩包有2737个直接成员，嵌套压缩内容没有全部递归校验。

- [字段与模板定义](indexes/output-schema.json)：三表结构和22个蓝色必需位置。
- [输入体检](indexes/data-health.json)：文件规模、格式及检查范围。
- [公告与附件清单](indexes/notice-attachment-manifest.csv)：按UUID查找源文件。
- [附件内容异常](indexes/attachment-content-anomalies.csv)：文件头和网页替身等疑点，不代表全部已确认损坏。

全量HTML和附件ZIP不随Git提交。源码内另有20条公告回放样本，说明见[数据文档](../../docs/data.md)。

使用Python 3.12从项目根目录运行`scripts/prepare_official_data.py --source-dir <source-directory>`可重新整理输入。脚本只处理文件和索引，不调用模型或覆盖业务数据库。
