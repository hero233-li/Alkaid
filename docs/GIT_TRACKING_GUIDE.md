# Git 提交与忽略约定

本项目不依赖 Docker。Git 只保存可复现的源码、脚本、文档和示例配置；本机运行产生的文件、真实密码和临时目录都不要提交。

## 需要提交到 Git

- 根目录启动入口：`package.json`、`start-dev.bat`、`start-dev.command`
- 开发/发布脚本：`scripts/windows/`、`scripts/macos/`
- 项目文档：`README.md`、`docs/`
- 后端源码与配置模板：`Alkaid-python/` 下的源码、测试、`pyproject.toml`、唯一依赖锁 `requirements-dev.lock`、`.env.example`、`.env.server.example`
- 前端源码与依赖清单：`Alkaid-react/src/`、`Alkaid-react/package.json`、`Alkaid-react/package-lock.json`、Vite/TS 配置文件
- 本地配置模板：`.env.local.example`

## 不要提交到 Git

- 真实环境变量和密码：`.env.local`、`Alkaid-python/.env`
- 运行目录和发布产物：`Alkaid-runtime/`、`Alkaid-releases/`
- 本地压缩包和导出包：`*.zip`、`*.tar`、`*.tar.gz`、`*.tgz`
- 依赖目录：`node_modules/`、`Alkaid-react/node_modules/`、`.venv/`
- 构建产物：`Alkaid-react/dist/`、`Alkaid-python/staticfiles/`、`*.tsbuildinfo`
- 本地数据库、上传文件和日志：`*.sqlite3`、`Alkaid-python/db.sqlite3`、`Alkaid-python/media/`、`*.log`
- 缓存目录：`__pycache__/`、`.pytest_cache/`、`.ruff_cache/`
- IDE 和系统文件：`.idea/`、`.vscode/`、`.DS_Store`

## 新机器使用方式

1. 拉取 Git 仓库代码。
2. 复制 `.env.local.example` 为 `.env.local`，填入本机 MySQL 地址、账号和密码。
3. 执行 `npm run dev` 启动本地开发前后端。

`.env.local` 是每台机器自己的配置，不要提交。这样第二天重启或切换分支时，服务只会读取稳定的本机配置，不会把未完成代码或密码混进 Git。
