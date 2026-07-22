# macOS 本机开发启动

在项目根目录执行：

```bash
npm run dev
```

也可以直接执行或双击根目录的 `start-dev.command`。

启动会优先读取项目根目录 `.env.local`。检查当前实际生效的 MySQL 配置：

```bash
npm run dev:env
```

脚本会在缺少后端 `.venv` 或前端 `node_modules` 时自动安装依赖。默认只使用一个 Terminal 窗口。
前后端监听 `0.0.0.0`，启动日志会同时打印本机地址和自动识别的局域网地址，例如：

- 本机前端：`http://127.0.0.1:5174`
- 内网前端：`http://192.168.1.3:5174`
- 内网后端：`http://192.168.1.3:8000`

可通过 `DEV_BIND_ADDRESS` 或 `DEV_LAN_IP` 覆盖监听地址和日志展示地址。

前端、后端和 Celery worker 的日志都会实时显示在当前 Terminal 窗口，
不再额外写入开发日志文件。

如果暂时没有 RabbitMQ，可以在 `.env.local` 设置：

```text
CELERY_TASK_ALWAYS_EAGER=true
DEV_START_WORKER=false
```

正常联调异步链路时保持：

```text
CELERY_TASK_ALWAYS_EAGER=false
DEV_START_WORKER=true
CELERY_QUEUE=alkaid-local
```

开发虚拟环境固定在项目根目录 `.venv`，不要再使用 `Alkaid-python/.venv`。

如果需要前后端分成两个窗口：

```bash
npm run dev:split
```

当前本机 MySQL 配置写在项目根目录 `.env.local`。如需换库，直接改这个文件即可。

没有 `.env.local` 时才使用默认 MySQL：

```text
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=alkaid_dev
MYSQL_USER=workflow
MYSQL_PASSWORD=workflow
```

请先创建开发库：

```sql
CREATE DATABASE alkaid_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

如果 Python 或依赖源不同，可以先设置环境变量：

```bash
export PYTHON_BOOTSTRAP=python3.10
export PIP_INSTALL_ARGS="--no-index --find-links /path/to/wheelhouse"
export NPM_INSTALL_CMD="npm ci --prefer-offline"
./start-dev.command
```
