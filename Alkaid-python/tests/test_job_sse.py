import asyncio

from apps.workflow.Jobs.sse import JobLogSSEApplication


def test_sse_closes_after_terminal_snapshot(monkeypatch) -> None:
    async def load_snapshot(job_id: int, after_id: int, log_view: str = "all"):
        assert log_view == "business"
        return {"status": "success", "progress": 100, "logs": [], "has_more": False}

    async def django_application(scope, receive, send) -> None:
        raise AssertionError("request should be handled by SSE")

    async def run() -> list[dict[str, object]]:
        sent: list[dict[str, object]] = []

        async def receive() -> dict[str, str]:
            return {"type": "http.disconnect"}

        async def send(message: dict[str, object]) -> None:
            sent.append(message)

        app = JobLogSSEApplication(django_application)
        await app(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/jobs/1/logs/stream",
                "query_string": b"afterId=0&view=business",
            },
            receive,
            send,
        )
        return sent

    monkeypatch.setattr("apps.workflow.Jobs.sse._load_snapshot", load_snapshot)
    sent = asyncio.run(run())

    assert sent[0]["status"] == 200
    assert any(b"event: status" in message.get("body", b"") for message in sent[1:])
    assert sent[-1]["more_body"] is False
