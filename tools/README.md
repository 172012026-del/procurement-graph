# Local parsing tools

本机保留两个项目内解析运行时：

- `libreoffice/program/soffice.com`：旧Office格式转换。
- `sevenzip/7z.exe`：RAR、7z及嵌套压缩包处理。

Python依赖由`demo/procurement/backend/requirements.txt`管理，包括RapidOCR、PDF和表格解析组件。外部OCR还可使用系统安装的Tesseract。

运行时目录已加入`.gitignore`；无需将已安装程序和安装包推送Git。下载来源与校验记录见`tool-sources.json`，`scripts/download_local_tools.py`提供下载辅助。完整工具安装与Linux依赖以项目Dockerfile和各工具官方说明为准。
