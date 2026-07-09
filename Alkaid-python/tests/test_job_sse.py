import asyncio

import pytest

from apps.jobs.services import JobRepository
from apps.jobs.sse import JobLogSSEApplication


@pytest.mark.django_db(transaction=True)
def test_sse_stream_returns_existing_logs_and_terminal_status():
    job = JobRepository.create(
        kind="test",
        name="SSE 测试",
        product="",
        payload={},
        trace_id="sse-trace",
        idempotency_key="sse-job-1",
        timeout_seconds=30,
    ).job
    JobRepository.mark_success(job.id, {"ok": True})
    sent: list[dict[str, object]] = []
    receive_count = 0

    async def fallback(scope, receive, send):
        raise AssertionError("SSE 路径不应进入 Django fallback")

    async def receive():
        nonlocal receive_count
        receive_count += 1
        if receive_count == 1:
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    async def run_application():
        application = JobLogSSEApplication(fallback)
        await application(
            {
                "type": "http",
                "method": "GET",
                "path": f"/api/jobs/{job.id}/logs/stream",
                "query_string": b"afterId=0",
            },
            receive,
            send,
        )

    asyncio.run(run_application())

    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 200
    body = b"".join(message.get("body", b"") for message in sent[1:]).decode()
    assert "event: log" in body
    assert "任务执行完成" in body
    assert "event: status" in body
    assert '"status":"success"' in body
