# 核实审批异步响应迁移确认

## 协议变化

核实审批业务 URL 和请求 Body 保持不变，但所有访问外系统的操作现在返回 HTTP 202 Job，
调用方必须轮询 `GET /api/jobs/{id}`，并从成功 Job 的 `result.task` 读取任务对象。

旧调用方式（不再兼容）：

```text
POST 核实审批接口 → 直接读取 response.data.task
```

当前调用方式：

```text
POST 核实审批接口 → response.data.id
→ GET /api/jobs/{id}
→ status == success
→ response.data.result.task
```

## 合并签字清单

- [ ] 仓库内前端已适配（自动化测试覆盖）。
- [ ] 内网脚本已检索并确认。
- [ ] Postman/Apifox 集合已检索并确认。
- [ ] 其他页面或服务调用方已检索并确认。
- [ ] 调用方已处理 failed/cancelled/timed_out。
- [ ] 调用方已设置轮询截止时间和取消机制。

后五项需要在内网调用方清单中由发布负责人确认；本地仓库不能替代该签字。

## Celery 环境验证

在 RabbitMQ 和独立 Worker 启动后执行：

```bash
cd Alkaid-python
python scripts/verify_celery_runtime.py --min-workers 2
```

该命令会连接真实 Broker，确认 Worker 可达，并逐个检查产品数据 Task 注册。Worker 强杀、
外系统成功后进程退出和人工补偿仍需在隔离的集成环境按发布演练执行。
