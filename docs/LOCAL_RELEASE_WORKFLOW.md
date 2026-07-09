# 本机发布与开发隔离流程

这份文档说明内网 Windows 机器上如何处理“当前正在运行的稳定版本”和“本地改到一半的开发版本”。

## 目标

- 开发目录可以随时修改，改到一半也不影响开机启动。
- 开机启动只读取已经验证通过的发布目录。
- 发布前先用独立端口和独立 MySQL 验证库验证。
- 生产库继续使用 MySQL，不使用 SQLite。

## 目录约定

推荐把目录放在同一级：

```text
D:\Alkaid-dev
D:\Alkaid-releases
D:\Alkaid-runtime
```

含义：

- `Alkaid-dev`：开发目录。日常改代码，只在开发端口运行。
- `Alkaid-releases`：发布目录。由脚本生成，不手工修改。
- `Alkaid-runtime`：运行指针和稳定启动脚本目录。

`Alkaid-runtime` 里关键文件：

```text
current-release.txt      # 当前生产启动使用的发布目录
previous-release.txt     # 上一个发布目录，用于回滚
last-built-release.txt   # 最近一次构建出的候选发布目录
prod-start.bat           # 开机启动应指向这个稳定副本
release-rollback.bat     # runtime 副本，可直接回滚 current-release
```

如果你现在只有一个项目目录，也可以先直接使用当前目录开发。`Alkaid-releases`
和 `Alkaid-runtime` 会在第一次执行发布脚本时自动创建；也可以手工提前建好。

## MySQL 库隔离

不要让开发、验证、生产共用一个库。推荐：

```text
alkaid_dev      # 本地开发
alkaid_verify   # 发布候选验证
alkaid_prod     # 生产运行
```

初始化示例：

```sql
CREATE DATABASE alkaid_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE alkaid_verify CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE alkaid_prod CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

如果使用单独用户：

```sql
CREATE USER 'workflow'@'localhost' IDENTIFIED BY 'workflow';
GRANT ALL PRIVILEGES ON alkaid_dev.* TO 'workflow'@'localhost';
GRANT ALL PRIVILEGES ON alkaid_verify.* TO 'workflow'@'localhost';
GRANT ALL PRIVILEGES ON alkaid_prod.* TO 'workflow'@'localhost';
FLUSH PRIVILEGES;
```

## 日常开发

在开发目录执行：

```bat
npm run dev
```

默认端口：

```text
前端：http://127.0.0.1:5174
后端：http://127.0.0.1:8000
```

开发数据库配置读取项目根目录 `.env.local`。没有这个文件时，才会使用启动脚本里的本地默认值。

检查当前实际生效的 MySQL 配置：

```bat
npm run dev:env
```

开发目录不参与开机启动。即使这里代码改坏，重启电脑也不会读取它。

## 构建发布候选

在开发目录执行：

```bat
scripts\windows\release-build.bat
```

脚本会复制当前代码到：

```text
Alkaid-releases\yyyyMMdd-HHmmss
```

并在发布目录内安装后端依赖、安装前端依赖、构建前端产物。

如果内网依赖包在本地目录：

```bat
set PIP_INSTALL_ARGS=--no-index --find-links D:\wheelhouse
set NPM_INSTALL_CMD=npm ci --prefer-offline
scripts\windows\release-build.bat
```

## 验证发布候选

```bat
scripts\windows\release-verify.bat
```

默认验证地址：

```text
http://127.0.0.1:19000
```

默认验证库：

```text
MYSQL_DATABASE=alkaid_verify
```

验证库不能和生产库相同。需要验证生产数据兼容性时，先从生产库备份恢复到验证库，再运行候选版本。

## 切换当前发布版

验证通过后：

```bat
scripts\windows\release-promote.bat
```

它会：

- 把当前 `current-release.txt` 保存为 `previous-release.txt`。
- 把验证通过的发布目录写入 `current-release.txt`。
- 把稳定的 `prod-start.bat` 复制到 `Alkaid-runtime`。

注意：`release-promote.bat` 只切换指针，不会启动生产服务。

## 生产启动

开机启动项或任务计划程序应指向：

```bat
D:\Alkaid-runtime\prod-start.bat
```

不要指向：

```bat
D:\Alkaid-dev\scripts\windows\prod-start.bat
```

原因是开发目录里的脚本以后也可能改到一半。runtime 里的脚本是发布时复制出的稳定副本。

生产默认地址：

```text
http://127.0.0.1:9000
```

生产默认库：

```text
MYSQL_DATABASE=alkaid_prod
```

## 回滚

如果新版本有问题：

```bat
D:\Alkaid-runtime\release-rollback.bat
```

它会把 `current-release.txt` 切回 `previous-release.txt`。然后重启 `prod-start.bat`。

## 规则

- 不在开发目录上开机启动。
- 不手工修改发布目录。
- 不让开发库、验证库、生产库共用一个 MySQL 数据库。
- 数据库结构变更先在 `alkaid_verify` 验证。
- 只有验证通过后才执行 `release-promote.bat`。
