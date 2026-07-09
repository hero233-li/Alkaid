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

脚本会在缺少后端 `.venv` 或前端 `node_modules` 时自动安装依赖。默认只使用一个 Terminal 窗口：

- 后端：`http://127.0.0.1:8000`
- 前端：`http://127.0.0.1:5174`

前端日志显示在当前窗口，后端日志写到：

```text
Alkaid-runtime/dev-backend.log
```

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
