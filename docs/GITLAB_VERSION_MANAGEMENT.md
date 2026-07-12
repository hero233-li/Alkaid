# Alkaid GitLab 版本管理规范

本文档适用于当前 Alkaid 单仓库：

```text
Alkaid/
├── Alkaid-react/        # React 前端
├── Alkaid-python/       # Django/Celery 后端
├── docs/                # 项目级文档
├── scripts/windows/     # 本机开发、构建、验证、发布、回滚脚本
└── README.md
```

一个 Git 提交号同时确定前端、后端、脚本和文档版本，避免前后端版本对应不上。

## 分支策略

当前阶段使用简单主干开发：

| 分支 | 用途 | 规则 |
| --- | --- | --- |
| `main` | 稳定可发布版本 | 合并前必须完成本地验证 |

短期分支按任务创建：

| 类型 | 命名示例 | 用途 |
| --- | --- | --- |
| 功能 | `feature/workflow-retry` | 新功能开发 |
| 修复 | `fix/card-status-timeout` | 普通缺陷修复 |
| 紧急修复 | `hotfix/login-500` | 生产紧急问题 |
| 重构 | `refactor/http-client` | 不改变业务行为的重构 |
| 工程 | `chore/local-release-script` | 依赖、脚本、构建流程调整 |
| 文档 | `docs/local-release-workflow` | 只修改文档 |

一个分支只解决一个明确问题，完成后合并并删除。

## 本地验证

后端：

```bash
cd Alkaid-python
make check
```

前端：

```bash
cd Alkaid-react
npm run build
```

架构检查：

```bash
cd Alkaid-python
.venv/bin/python scripts/check_architecture.py
```

## 提交规范

先检查修改：

```bash
git status
git diff
git diff --staged
```

按功能选择文件，不建议无检查地执行 `git add .`。

提交消息格式：

```text
类型(模块): 简短说明
```

常用类型：

| 类型 | 含义 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 缺陷修复 |
| `refactor` | 重构但不改变行为 |
| `test` | 测试变更 |
| `docs` | 文档变更 |
| `chore` | 构建、依赖、脚本等工程变更 |

示例：

```text
feat(workflow): support retry
fix(card-status): handle request timeout
docs(release): describe local release workflow
chore(windows): add release promotion script
```

## 发布版本

正式版本使用 Git Tag：

```text
v主版本.次版本.修订版本
```

示例：

```text
v0.1.0
v0.1.1
v1.0.0
```

发布前：

```bash
git switch main
git pull --ff-only
git status
```

工作区必须干净。创建标签：

```bash
git tag -a v0.1.0 -m "Alkaid v0.1.0"
git push origin v0.1.0
```

## 本机发布目录

发布目录由脚本生成，不手工修改：

```text
Alkaid-dev\          # 开发目录
Alkaid-releases\     # 发布目录
Alkaid-runtime\      # 当前发布指针和稳定启动脚本
```

生产启动只读取：

```text
Alkaid-runtime\current-release.txt
```

开机启动项只指向：

```text
Alkaid-runtime\prod-start.bat
```

不要把开发目录里的脚本放入开机启动项。

## MySQL 数据库

不同用途使用不同数据库：

```text
alkaid_dev      # 日常开发
alkaid_verify   # 发布候选验证
alkaid_prod     # 生产运行
```

发布候选必须先在 `alkaid_verify` 验证，通过后才允许执行：

```bat
scripts\windows\release-promote.bat
```

生产启动默认连接 `alkaid_prod`。不要让开发目录或验证服务连接生产库。

## 回滚

发布切换时，脚本会保存上一个发布目录到：

```text
Alkaid-runtime\previous-release.txt
```

需要回滚时执行：

```bat
Alkaid-runtime\release-rollback.bat
```

然后重启生产启动脚本。

## 不提交的内容

以下内容不要进入 Git：

```text
node_modules/
.venv/
dist/
*.pyc
__pycache__/
.env
.idea/
.DS_Store
```

依赖版本通过锁文件控制：

```text
Alkaid-react/package-lock.json
Alkaid-python/requirements-dev.lock
```

本机 MySQL 数据不进入 Git，通过 migration 管理结构，通过备份工具管理数据。
