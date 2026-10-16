# 开发与部署

所有示例命令在项目根目录执行。

## Windows

Python 3.12、Node.js 22.12+为基础依赖。Python包固定在后端`requirements.txt`，前端版本由`package-lock.json`锁定。

```powershell
.\scripts\run_project.ps1 -Mode Setup
.\scripts\run_project.ps1 -Mode Api
# 在另一终端启动前端
.\scripts\run_project.ps1 -Mode Web
```

部署参数放在根目录`.env`，已有文件无需重复复制模板。模型服务可在前端“连接设置”中保存，页面私有配置优先于`.env`中的对应项。启动服务不会自动发起模型请求；模型调用关闭时仍可浏览、查询、解析预检和历史响应回放。

Office、RAR/7z和OCR需要本机解析工具。完整工具安装后使用`tools/libreoffice`和`tools/sevenzip`等路径；这些安装目录不随源码提交，依赖说明见[工具目录](../tools/README.md)。

## 后端与构建验证

```powershell
.\scripts\run_project.ps1 -Mode Test
```

该命令执行后端隔离测试和前端生产构建。后端测试使用独立数据库、空Key和模拟模型响应。

## 浏览器回归

浏览器测试依赖独立保存在`scripts/package.json`，不进入生产前端：

```powershell
npm --prefix scripts ci
.\scripts\node_modules\.bin\playwright.cmd install chromium
node .\scripts\verify_frontend.mjs --production
```

生产回归从空数据库创建固定样本，使用随源码提供的20篇公告，显式禁止模型HTTP调用。无需业务数据库或官方全量目录。输出位于`results/ui-checks`。交互回归也独立启动隔离服务：

```powershell
node .\scripts\verify_frontend_edgecases.mjs
```

自定义浏览器可设置`PLAYWRIGHT_EXECUTABLE_PATH`，Python可设置`PYTHON_EXECUTABLE`。

跨平台启动、工具安装、评审操作及模型元数据配置见[部署说明](deployment.md)。Neo4j、RAG和LoRA入口见[可选能力](advanced-features.md)。

## Linux与Docker

```bash
python3 -m venv demo/procurement/.venv
demo/procurement/.venv/bin/python -m pip install -r demo/procurement/backend/requirements.txt
npm --prefix demo/procurement/frontend ci
demo/procurement/.venv/bin/python -m uvicorn app.main:app --app-dir demo/procurement/backend --host 127.0.0.1 --port 8000 --workers 1
# 在另一终端启动前端
npm --prefix demo/procurement/frontend run dev -- --host 127.0.0.1
```

```powershell
docker compose --env-file .env -f demo/procurement/docker-compose.yml up --build
```

Docker定义了Ubuntu解析依赖和单worker服务，本机尚未完成镜像实跑。2CPU/4GiB是当前工程资源设置，不代表赛事官方机器规格。容器部署的样本目录和缓存挂载应按实际部署数据配置。

## 发布检查

```powershell
.\demo\procurement\.venv\Scripts\python.exe .\scripts\audit_publish.py
```

检查凭据、异常大文件、文件命名和Markdown链接；不创建提交，也不推送远程。未初始化Git时按项目忽略规则检查，初始化后使用Git实际文件列表。

## 源码交付包

```powershell
.\demo\procurement\.venv\Scripts\python.exe scripts/package_release.py --include-materials
.\demo\procurement\.venv\Scripts\python.exe scripts/verify_release.py
```

压缩包内附文件哈希、样本结果和交付范围声明；不包含个人配置、业务数据库或已安装依赖。源码验证从压缩包解出全新目录，使用已有Python依赖检查启动、样本回放和三表；不等同于新系统依赖安装验收。

GitHub的 `.github/workflows/verify.yml` 提供Ubuntu24.04依赖安装、测试、独立浏览器、真实图服务比对和Docker构建流程。它不使用模型Key；是否通过以实际运行记录为准。
