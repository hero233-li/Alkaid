# Windows 本机发布脚本

这组脚本用于内网 Windows 本机运行。目标是让开机启动只读取已验证发布版，不要启动正在修改的
开发目录。

默认目录结构：

```text
Alkaid-dev\
Alkaid-releases\
Alkaid-runtime\
  current-release.txt
  previous-release.txt
  last-built-release.txt
```

如果仓库目录名不是 `Alkaid-dev` 也没关系，脚本会默认把 `Alkaid-releases` 和
`Alkaid-runtime` 放在仓库的上一级目录。也可以通过环境变量覆盖：

```bat
set ALKAID_RELEASES_DIR=D:\Alkaid-releases
set ALKAID_RUNTIME_DIR=D:\Alkaid-runtime
```

## 开发

开发目录可以改到一半，不参与开机启动：

```bat
npm run dev
```

启动会优先读取项目根目录 `.env.local`。检查当前实际生效的 MySQL 配置：

```bat
npm run dev:env
```

默认只使用一个命令窗口：前端、后端和 Celery worker 的日志都会实时显示在当前窗口，
不再额外写入开发日志文件。

如果暂时没有 RabbitMQ，可以在 `.env.local` 设置：

```text
CELERY_TASK_ALWAYS_EAGER=true
DEV_START_WORKER=false
```

这样 `npm run dev` 会跳过 worker，任务在 Django 进程里同步执行。正常联调异步链路时保持：

```text
CELERY_TASK_ALWAYS_EAGER=false
DEV_START_WORKER=true
CELERY_QUEUE=alkaid-local
```

开发虚拟环境固定在项目根目录 `.venv`，不要再使用 `Alkaid-python\.venv`。

如果需要前后端分成两个窗口：

```bat
npm run dev:split
```

开发默认端口：

- 前端：`http://127.0.0.1:5174`
- 后端：`http://127.0.0.1:8000`

当前本机 MySQL 配置写在项目根目录 `.env.local`。如需换库，直接改这个文件即可。

没有 `.env.local` 时才使用开发默认 MySQL：

```text
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=alkaid_dev
MYSQL_USER=workflow
MYSQL_PASSWORD=workflow
```

请提前创建开发库：

```sql
CREATE DATABASE alkaid_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## 构建发布候选

在开发目录中执行：

```bat
scripts\windows\release-build.bat
```

脚本会复制当前代码到 `Alkaid-releases\yyyyMMdd-HHmmss`，然后在发布目录里安装依赖、执行
Django/配置/架构/测试/Ruff 门禁并构建前端。任一检查失败都不会生成可验证发布候选。
如果内网只能使用本地 Python wheel 包：

```bat
set PIP_INSTALL_ARGS=--no-index --find-links D:\wheelhouse
scripts\windows\release-build.bat
```

如需改 npm 安装命令：

```bat
set NPM_INSTALL_CMD=npm ci --prefer-offline
scripts\windows\release-build.bat
```

## 验证发布候选

```bat
scripts\windows\release-verify.bat
```

默认读取上一步生成的 `last-built-release.txt`，用独立验证数据库和临时端口启动：

- 验证地址：`http://127.0.0.1:19000`
- 验证数据库：`alkaid_verify`

也可以指定发布目录：

```bat
scripts\windows\release-verify.bat D:\Alkaid-releases\20260709-2140
```

## 切换当前发布版

确认验证正常后执行：

```bat
scripts\windows\release-promote.bat
```

脚本会把发布目录写入：

```text
Alkaid-runtime\current-release.txt
```

开机启动脚本只读取这个文件。没有执行 promote 的半成品不会被启动。

## 开机启动

`release-promote.bat` 会把生产启动脚本复制到 `Alkaid-runtime`。把 runtime 里的这个脚本放入
Windows 启动项或任务计划程序：

```bat
Alkaid-runtime\prod-start.bat
```

启动前需要在任务计划或系统环境中提供 `DJANGO_SECRET_KEY`、`CELERY_BROKER_URL`、
`MOCK_PRODUCT_BASE_URL`、`APPLICATION_LINK_BASE_URL`、`APPLICATION_LINK_API_TOKEN` 和
`BUSINESS_ACCESS_BASE_URL`、`BUSINESS_ACCESS_API_TOKEN`、`VERIFICATION_APPROVAL_BASE_URL`、
`VERIFICATION_APPROVAL_API_TOKEN`、`MOCK_FIXED_SYSTEM_TOKEN`。生产固定使用
`config.settings.server`、真实外系统模式和异步 Celery；
启动脚本会监管 Web、Worker、Beat 三个进程，不再在 Web 进程内同步执行任务。

不要把开发目录里的 `scripts\windows\prod-start.bat` 放入开机启动项。否则以后脚本本身改到一半，
也可能影响开机。

生产默认端口：

- 入口地址：`http://127.0.0.1:9000`
- 生产数据库：`alkaid_prod`

生产默认 MySQL：

```text
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=alkaid_prod
MYSQL_USER=workflow
MYSQL_PASSWORD=workflow
```

如果生产库不是这些默认值，把变量写到任务计划程序或启动脚本环境里。不要把验证库和生产库设成
同一个库。

## 回滚

如果新版本有问题：

```bat
scripts\windows\release-rollback.bat
```

它会把 `current-release.txt` 切回 `previous-release.txt` 记录的上一个发布目录。
