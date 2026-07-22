# Alkaid

项目目录：

- `Alkaid-react`：React 前端源码。
- `Alkaid-python`：Django/Celery 后端源码。
- `scripts/windows`：内网 Windows 本机开发、构建、验证、发布和回滚脚本。

GitLab 分支、提交、发布和文件上传规范见
[`docs/GITLAB_VERSION_MANAGEMENT.md`](./docs/GITLAB_VERSION_MANAGEMENT.md)。

本机发布流程见 [`docs/LOCAL_RELEASE_WORKFLOW.md`](./docs/LOCAL_RELEASE_WORKFLOW.md)。

本次异步 Job、外系统 Integration、环境变量、数据库迁移、调用链和测试说明见
[`docs/ASYNC_WORKFLOW_OPERATIONS.md`](./docs/ASYNC_WORKFLOW_OPERATIONS.md)；完整接口契约见
[`docs/API.md`](./docs/API.md)。

## 本机 DEV

本机接口工作台默认启用；如需临时关闭，可设置 `WORKBENCH_ENABLED=false`。服务端配置默认关闭接口工作台，只有显式设置 `WORKBENCH_ENABLED=true` 才会显示和开放对应菜单。

后端本机开发使用 MySQL 5.7。`npm run dev` 默认会同时启动前端、Django 和 Celery worker；
如果暂时没有 RabbitMQ，可以在 `.env.local` 里把 `CELERY_TASK_ALWAYS_EAGER=true`，脚本会跳过
worker，任务改为同步执行。
即使保持异步配置，开发环境的 Mock 模式在投递 RabbitMQ 失败时也会自动回退到本地执行，
不会再把队列连接异常直接返回成 HTTP 500；生产模式不会启用这个回退。
本机启动会优先读取项目根目录的 `.env.local`，这个文件只放本机配置，不提交。

如果没有 `.env.local`，脚本才会使用默认连接：

```text
127.0.0.1:3306 / alkaid_dev / workflow
```

如需新建本地开发库：

```sql
CREATE DATABASE alkaid_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

一键启动：

```bash
npm run dev
```

首次启动或拉取包含 Migration 的版本后，必须先执行：

```bash
cd Alkaid-python
make migrate
```

检查当前实际生效的 MySQL 配置：

```bash
npm run dev:env
```

它会自动按系统选择启动脚本：

```text
Windows -> scripts\windows\dev-start.bat
macOS   -> scripts/macos/dev-start.command
```

脚本会在缺少后端 `.venv` 或前端 `node_modules` 时自动安装依赖。默认只使用一个窗口，
前端、后端和 Celery worker 的日志都会实时显示在当前终端，不再额外写入开发日志文件。
Windows 单窗口模式使用项目内的安全轮询监管器重启 Uvicorn 子进程，保存 Python 文件时不会
再通过控制台 Ctrl+C 连带终止 Vite、Celery 或启动 PowerShell。

单独启动 worker：

```bash
npm run dev:worker
```

如果需要前后端分成两个窗口：

```bash
npm run dev:split
```

如果内网只能用本地 Python wheel 目录，可以先设置：

```bat
set PIP_INSTALL_ARGS=--no-index --find-links D:\wheelhouse
npm run dev
```

如果 npm 需要使用本地缓存或内网源，可以先设置：

```bat
set NPM_INSTALL_CMD=npm ci --prefer-offline
npm run dev
```

- 本机前端：<http://127.0.0.1:5174>
- 本机后端：<http://127.0.0.1:8000>
- 内网访问：启动日志会自动打印 `LAN frontend` 和 `LAN backend` 地址
- 存活检查：<http://127.0.0.1:8000/health/>
- 就绪检查：<http://127.0.0.1:8000/health/ready/>

开发虚拟环境固定在项目根目录 `.venv`，不要再使用 `Alkaid-python/.venv`。

## Windows 本机发布

内网 Windows 机器不要从开发目录开机启动。发布版使用独立目录和指针文件：

```text
Alkaid-dev\                  # 开发目录，可以改到一半
Alkaid-releases\             # 已构建发布目录
Alkaid-runtime\current-release.txt
MySQL: alkaid_dev / alkaid_verify / alkaid_prod
```

构建、验证、切换和开机启动脚本在：

```text
scripts\windows\
```

推荐流程：

```bat
scripts\windows\release-build.bat
scripts\windows\release-verify.bat
scripts\windows\release-promote.bat
..\Alkaid-runtime\prod-start.bat
```

`release-promote.bat` 会把生产启动脚本复制到 `Alkaid-runtime\prod-start.bat`。Windows
开机启动项应指向这个 runtime 副本，不要指向开发目录里的脚本。

详细说明见 [`scripts/windows/README.md`](./scripts/windows/README.md)。
