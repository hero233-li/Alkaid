# 合并 main 前 Git Diff 审计报告（2026-07-15）

## 一、审计范围

- 目标分支：`main`（审计时 `59a1759`）
- 功能分支：`agent/job-and-application-link-refactor`
- 差异范围：`main...agent/job-and-application-link-refactor`
- 范围说明：该分支包含异步 Job、产品数据模块化、Integration、前端页面、运行脚本及两轮审查整改的完整提交链，不只包含最近两个提交。

## 二、七项确认

### 1. 临时调试代码

未发现 `debugger`、`breakpoint()`、临时调试分支或未关闭的调试开关。

`.env.local.example` 中 `VERIFICATION_APPROVAL_DEBUG_DELAY_SECONDS` 已从 `3` 修正为 `0`。
CLI 脚本中的 `print`、开发启动器中的 `console.log` 和 Workbench 示例代码生成内容属于正常输出，予以保留。

### 2. 密钥、Token、真实账号

未发现私钥、云访问密钥、真实 Token、真实密码或需要清除的真实账号。

- `.env*.example` 只包含 `replace-me`、空值或明确的本地 Mock 默认值；
- 测试中的 `test`、`secret-token` 为隔离测试数据；
- 真实配置文件 `.env.local`、`Alkaid-python/.env` 未被 Git 跟踪；
- 服务器设置会拒绝默认 Django 密钥、Mock Token、缺失外系统配置或 eager Celery。

### 3. 无关文件

发现并删除未被引用的早期对话式说明稿：

- `docs/001.md`
- `docs/002.md`

其余代码、测试、配置、运行脚本、契约和审查报告均与本功能链或合并验收相关。

### 4. 遗漏新增文件

`git status` 和 `git diff --name-status` 已检查。新增的 Migration、TaskRunner、Mock 状态辅助函数、
前端轮询工具、测试、接口契约及运维文档均纳入提交，不存在应提交而未跟踪的源码文件。

### 5. 临时 print

未发现业务运行路径中的临时 `print`。

保留项均有明确用途：架构/配置/Celery 验证脚本输出、进程监管输出、开发环境配置展示，以及
Workbench 生成的 Python/TypeScript 调用示例。

### 6. 被注释掉的大段旧代码

未发现。旧 Workflow、Handler 和重复配置实现通过 Git 删除，不以注释形式残留。

### 7. 数据库 Migration

Migration 链完整：

```text
jobs.0001_initial
→ jobs.0002_job_execution_config
→ jobs.0003_job_status_deadline_index
→ jobs.0004_mocktoolstate
```

验证结果：

- `manage.py makemigrations --check --dry-run --settings=config.settings.test`：No changes detected；
- `manage.py migrate --plan --settings=config.settings.test`：完整列出 `0001` 至 `0004`；
- `0004` 包含 `MockToolState` 及 `(namespace, key)` 唯一约束；
- 已移除 Workflow App 的历史表不自动 DROP，由 DBA 备份后按需清理。

## 三、文档更新

已至少覆盖用户要求的文档：

| 要求 | 文件 |
| --- | --- |
| README | `README.md`、`Alkaid-python/README.md` |
| 接口说明 | `docs/API.md` |
| 调用链说明 | `docs/ASYNC_WORKFLOW_OPERATIONS.md` 第 1 节 |
| 环境变量说明 | `docs/ASYNC_WORKFLOW_OPERATIONS.md` 第 2 节及三个 `.env*.example` |
| 数据库变更 | `docs/ASYNC_WORKFLOW_OPERATIONS.md` 第 3 节 |
| 测试方式 | `docs/ASYNC_WORKFLOW_OPERATIONS.md` 第 5 节 |

## 四、验证结果

| 项目 | 结果 |
| --- | --- |
| 后端 pytest | `57 passed` |
| Ruff | 通过 |
| 架构检查 | 通过 |
| Migration 差异检查 | No changes detected |
| Migration 计划 | `jobs.0001` 至 `jobs.0004` 完整 |
| 前端 Vitest | `9 files / 16 tests passed` |
| TypeScript + Vite build | 通过 |
| `git diff --check` | 通过 |

Vite 仍有单 bundle 超过 500 kB 的既有非阻塞告警。

## 五、结论

完整差异已达到本地合并 `main` 的条件。真实外系统生产上线仍受申请链接协议/Signer、真实
RabbitMQ 双 Worker、Worker 强杀演练和仓库外调用方确认门禁约束；本地合并不等于生产上线确认。
