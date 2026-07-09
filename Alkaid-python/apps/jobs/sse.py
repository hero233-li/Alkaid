import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from django.db import close_old_connections

from apps.jobs.models import Job
from apps.jobs.services import serialize_log

ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
ASGISend = Callable[[dict[str, Any]], Awaitable[None]]
JOB_LOG_STREAM_PATH = re.compile(r"^/api/jobs/(?P<job_id>\d+)/logs/stream/?$")


def _snapshot(job_id: int, after_id: int) -> dict[str, Any] | None:
    close_old_connections()
    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return None
    logs = list(job.logs.filter(id__gt=after_id).order_by("id")[:500])
    return {
        "status": job.status,
        "progress": job.progress,
        "logs": [serialize_log(log) for log in logs],
    }


async def _load_snapshot(job_id: int, after_id: int) -> dict[str, Any] | None:
    return await sync_to_async(_snapshot, thread_sensitive=True)(job_id, after_id)


def _event(name: str, data: dict[str, Any]) -> bytes:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {name}\ndata: {payload}\n\n".encode()


class JobLogSSEApplication:
    def __init__(self, django_application: Callable[..., Awaitable[None]]) -> None:
        self.django_application = django_application

    async def __call__(self, scope: dict[str, Any], receive: ASGIReceive, send: ASGISend) -> None:
        match = JOB_LOG_STREAM_PATH.match(scope.get("path", ""))
        if scope.get("type") != "http" or scope.get("method") != "GET" or match is None:
            await self.django_application(scope, receive, send)
            return

        job_id = int(match.group("job_id"))
        query = parse_qs(scope.get("query_string", b"").decode())
        try:
            after_id = max(0, int(query.get("afterId", ["0"])[0]))
        except ValueError:
            await self._json_error(send, 400, "afterId 必须是整数")
            return
        snapshot = await _load_snapshot(job_id, after_id)
        if snapshot is None:
            await self._json_error(send, 404, "Job 不存在")
            return

        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/event-stream; charset=utf-8"),
                    (b"cache-control", b"no-cache, no-transform"),
                    (b"x-accel-buffering", b"no"),
                ],
            }
        )
        last_status: tuple[str, int] | None = None
        heartbeat_seconds = 15.0
        last_heartbeat = asyncio.get_running_loop().time()

        while True:
            snapshot = await _load_snapshot(job_id, after_id)
            if snapshot is None:
                break
            for log in snapshot["logs"]:
                await send(
                    {"type": "http.response.body", "body": _event("log", log), "more_body": True}
                )
                after_id = max(after_id, int(log["id"]))

            current_status = (snapshot["status"], snapshot["progress"])
            if current_status != last_status:
                await send(
                    {
                        "type": "http.response.body",
                        "body": _event(
                            "status",
                            {"status": snapshot["status"], "progress": snapshot["progress"]},
                        ),
                        "more_body": True,
                    }
                )
                last_status = current_status

            now = asyncio.get_running_loop().time()
            if now - last_heartbeat >= heartbeat_seconds:
                await send(
                    {
                        "type": "http.response.body",
                        "body": b": heartbeat\n\n",
                        "more_body": True,
                    }
                )
                last_heartbeat = now
            try:
                message = await asyncio.wait_for(receive(), timeout=0.5)
                if message.get("type") == "http.disconnect":
                    return
            except asyncio.TimeoutError:
                pass

        await send({"type": "http.response.body", "body": b"", "more_body": False})

    @staticmethod
    async def _json_error(send: ASGISend, status: int, message: str) -> None:
        body = json.dumps(
            {"ok": False, "message": message, "data": None}, ensure_ascii=False
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})
