# Alkaid

项目目录：

- `Alkaid-react`：React 前端源码。
- `Alkaid-python`：Django/Celery 后端源码。
- `scripts/windows`：内网 Windows 本机开发、构建、验证、发布和回滚脚本。

GitLab 分支、提交、发布和文件上传规范见
[`docs/GITLAB_VERSION_MANAGEMENT.md`](./docs/GITLAB_VERSION_MANAGEMENT.md)。

本机发布流程见 [`docs/LOCAL_RELEASE_WORKFLOW.md`](./docs/LOCAL_RELEASE_WORKFLOW.md)。

## 本机 DEV

后端本机开发使用 MySQL 5.7，并开启 Celery eager 模式，避免依赖消息队列。
本机启动会优先读取项目根目录的 `.env.local`，这个文件只放本机配置，不提交。

当前已按你提供的内网 MySQL 信息写入 `.env.local`。如需换库，直接改这个文件即可。

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

检查当前实际生效的 MySQL 配置：

```bash
npm run dev:env
```

它会自动按系统选择启动脚本：

```text
Windows -> scripts\windows\dev-start.bat
macOS   -> scripts/macos/dev-start.command
```

脚本会在缺少后端 `.venv` 或前端 `node_modules` 时自动安装依赖。默认只使用一个窗口：

- 前端日志显示在当前窗口
- 后端在后台运行，日志写到 `Alkaid-runtime/dev-backend.log`

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

- 前端：<http://127.0.0.1:5174>
- 后端：<http://127.0.0.1:8000>
- 健康检查：<http://127.0.0.1:8000/health/>

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
