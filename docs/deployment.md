# 部署与评审操作

## 环境准备

需要 Python 3.12+、Node.js 22.12+。所有命令均在项目根目录执行。

```bash
python scripts/manage_project.py setup
python scripts/manage_project.py doctor
```

Setup 保留已有 `.env`，仅在文件不存在时复制空模板。浏览内置20篇样本、查询、预检和历史响应回放不需要模型Key。

Windows 完整附件环境可执行以下命令，将官方工具安装到项目 `tools` 目录：

```powershell
python scripts/manage_project.py setup --with-tools
```

Linux 可使用下面的容器环境，或由管理员安装 LibreOffice Writer/Calc、7zip、Tesseract及中文语言包。检查完整解析能力：

```bash
python scripts/manage_project.py doctor --require-tools
```

## 本地启动

分别在两个终端执行：

```bash
python scripts/manage_project.py api
python scripts/manage_project.py web
```

打开 `http://127.0.0.1:5173`。后端使用单worker运行；上传任务和SQLite写入不支持直接扩成多worker。`--host`、`--port`可用于调整监听地址和端口。

## Docker

Docker镜像包含Linux解析工具，无需复制Windows运行时、虚拟环境或node_modules。

```bash
docker compose --env-file .env -f demo/procurement/docker-compose.yml up --build -d
docker compose --env-file .env -f demo/procurement/docker-compose.yml ps
```

默认仅允许本机访问。评审服务器需根据实际入口设置 `.env` 中的 `WEB_BIND_ADDRESS=0.0.0.0`，并配置随机、私密的 `APP_API_TOKEN`；后端8000端口保持仅本机绑定，通过前端代理访问。公开互联网部署应由平台网关提供HTTPS。

数据库、上传文件和页面保存的模型配置持久保存在 `demo/procurement/data`。官方全量输入由管理员放到 `data/official-benchmark/html` 和 `file`；源码内置演示不依赖这两个目录。

## 模型资源

复制 `config/model-profile.example.json` 为 `config/model-profile.local.json`，填写阶段、模型标识、版本、参数规模、资源来源及证明材料位置。初赛另填高校约定的模型标准，决赛记录主办方资源；微调方案记录允许基座和自托管服务证据。模型地址、名称、Key及启用状态可在页面“连接设置”中保存，也可在首次启动前通过私有 `.env` 配置。

空模板默认 `MODEL_NETWORK_ENABLED=false`，可在页面勾选“启用模型抽取”并保存，立即对新任务生效。页面配置优先于 `.env`，刷新和重启后保留；Key留空保留原值且不回显。保存不执行推理请求。OpenAI兼容接口适用于相应Qwen/DeepSeek服务，但兼容接口本身不能证明使用了赛事指定资源。

本地页面配置默认存于 `config/model-settings.local.json`；容器设置 `MODEL_SETTINGS_PATH=/app/data/model-settings.local.json`，使用可写且持久的业务数据卷。两种位置均已排除Git跟踪。远程管理模型配置必须启用 `APP_API_TOKEN`。详见[模型配置说明](model-settings.md)。

```bash
demo/procurement/.venv/bin/python scripts/doctor.py --require-tools --require-competition
```

Windows将Python路径替换为 `demo/procurement/.venv/Scripts/python.exe`。此命令检查工具、分阶段模型元数据及应用访问令牌，不进行付费请求；实际推理与平台性能仍须分别验收。答疑表说明初赛自行部署，决赛统一环境为2vCPU、4GB、Ubuntu24.04且不含GPU，详见[答疑补充](requirements/clarifications.md)。

## 评审操作步骤

1. 管理员向评审私下提供实际访问地址和应用访问令牌。应用令牌与模型提供商Key是两份不同凭据。
2. 打开平台，点击“连接设置”，填写应用访问令牌并保存。
3. 在工作台查看内置样本；在“标的检索”使用七字段筛选，并打开来源证据。
4. 进入“关系分析”，分别执行合作画像、高频投标、供应商竞争、共同合作单位、共同竞标五个场景。
5. 进入“数据接入”，下载样本公告ZIP，再上传并选择历史响应回放。新数据应选择模型抽取，且需要模型服务已启用。
6. 查看批次状态，下载此批三表和处理说明，区分完整、部分与失败结果。

当前访问控制使用共享应用令牌，不包含用户名、角色或账号管理。最终评审凭据形式以主办方要求为准。地址及真实令牌不放进公开仓库或公开文档。

## 停止与数据保留

```bash
docker compose --env-file .env -f demo/procurement/docker-compose.yml down
```

停止容器不会删除挂载的业务数据。重启前后应保留 `.env`、页面保存的模型配置、业务数据库与需要重试的上传输入。
