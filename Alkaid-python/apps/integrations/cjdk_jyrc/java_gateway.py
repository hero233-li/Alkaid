from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from time import monotonic
from typing import Any

from apps.integrations.cjdk_jyrc import config
from apps.integrations.cjdk_jyrc.models import (
    ApplicationLinks,
    GenerateApplicationLinkRequest,
)
from apps.jobs.http import (
    JobHttpCallObserver,
    format_log_value,
    sanitize_text,
)
from apps.jobs.models import Job
from apps.jobs.services import add_job_log

logger = logging.getLogger(__name__)

RESULT_PREFIX = "ALKAID_RESULT="


class JavaApplicationLinkGateway:
    """Invoke the local Java SDK and parse ALKAID_RESULT."""

    def __init__(self, job: Job) -> None:
        self.job = job

    def generate_link(
        self,
        request: GenerateApplicationLinkRequest,
    ) -> ApplicationLinks:
        java_request = request.external_request()
        observer = JobHttpCallObserver(
            self.job,
            step="application_link.generate_link",
        )
        call_path = (
            "mock://java-application-link"
            if config.external_system_mode() == "mock"
            else config.java_main_class()
        )
        handle = observer.started(
            method="JAVA",
            path=call_path,
            headers={},
            request_body=java_request,
        )
        started_at = monotonic()

        logger.info(
            "application_link_java_started",
            extra={
                "job_id": self.job.id,
                "trace_id": self.job.trace_id,
                "env": request.env,
                "product": request.product,
                "category": request.category,
                "cooperation_project_id": request.cooperation_project_id,
                "payload_fields": sorted(request.payload.keys()),
            },
        )

        try:
            if config.external_system_mode() == "mock":
                result = self._mock_result(java_request)
            else:
                result = self._execute_java(java_request)
            links = ApplicationLinks.model_validate(result)
        except Exception as exc:
            observer.finished(
                handle,
                status_code=None,
                headers={},
                response_body={},
                duration_ms=self._duration_ms(started_at),
                error=exc,
            )
            raise

        observer.finished(
            handle,
            status_code=0,
            headers={},
            response_body=links.model_dump(mode="json"),
            duration_ms=self._duration_ms(started_at),
            error=None,
        )
        logger.info(
            "application_link_java_completed",
            extra={
                "job_id": self.job.id,
                "trace_id": self.job.trace_id,
                "env": request.env,
                "product": request.product,
                "category": request.category,
            },
        )
        return links

    def _execute_java(self, java_request: dict[str, Any]) -> dict[str, Any]:
        sdk_root = config.java_sdk_dir()
        java_executable = self._resolve_runtime_path(
            config.java_executable(),
            sdk_root,
        )
        jar_path = self._resolve_runtime_path(
            config.java_jar(),
            sdk_root,
        )
        self._validate_runtime(
            sdk_root=sdk_root,
            java_executable=java_executable,
            jar_path=jar_path,
        )

        classpath = os.pathsep.join(
            [
                str(jar_path),
                str(sdk_root / "lib" / "*"),
            ]
        )

        with tempfile.TemporaryDirectory(prefix="alkaid-link-") as temp_dir:
            request_path = Path(temp_dir) / "request.json"
            request_path.write_text(
                json.dumps(
                    java_request,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            command = [
                str(java_executable),
                "-cp",
                classpath,
                config.java_main_class(),
                str(request_path),
            ]

            self._write_diagnostic(
                "JavaGateway 执行信息",
                {
                    "cwd": str(sdk_root),
                    "command": [
                        *command[:-1],
                        "<temporary request.json>",
                    ],
                    "requestFileEncoding": "utf-8",
                    "outputEncoding": config.java_output_encoding(),
                    "timeoutSeconds": config.java_timeout_seconds(),
                },
            )

            try:
                completed = subprocess.run(
                    command,
                    cwd=str(sdk_root),
                    shell=False,
                    capture_output=True,
                    text=True,
                    encoding=config.java_output_encoding(),
                    errors="replace",
                    timeout=config.java_timeout_seconds(),
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    "申请链接 Java SDK 执行超时："
                    f"{config.java_timeout_seconds()} 秒"
                ) from exc
            except OSError as exc:
                raise RuntimeError(
                    f"申请链接 Java SDK 无法启动：{exc}"
                ) from exc

        self._write_diagnostic(
            "JavaGateway 执行结果",
            {
                "returnCode": completed.returncode,
                "stdout": sanitize_text(completed.stdout),
                "stderr": sanitize_text(completed.stderr),
            },
            level="INFO" if completed.returncode == 0 else "ERROR",
        )

        if completed.returncode != 0:
            raise RuntimeError(
                "申请链接 Java SDK 执行失败："
                f"exit_code={completed.returncode}; "
                f"stderr={completed.stderr[-2000:]}"
            )
        return self._parse_result(completed.stdout)

    def _write_diagnostic(
        self,
        title: str,
        content: dict[str, Any],
        *,
        level: str = "INFO",
    ) -> None:
        message = (
            f"{title}（敏感值已脱敏）：\n"
            f"{format_log_value(content)}"
        )
        add_job_log(
            self.job,
            level,
            message,
            step="application_link.generate_link",
            celery_task_id=self.job.celery_task_id,
            metadata={
                "event": "java_gateway_diagnostic",
                "title": title,
            },
        )
        log_method = logger.error if level == "ERROR" else logger.info
        log_method(
            "java_gateway_diagnostic %s\n%s",
            title,
            format_log_value(content),
        )

    @staticmethod
    def _parse_result(stdout: str) -> dict[str, Any]:
        for line in reversed(stdout.splitlines()):
            normalized = line.strip()
            if not normalized.startswith(RESULT_PREFIX):
                continue
            result_json = normalized[len(RESULT_PREFIX):]
            try:
                result = json.loads(result_json)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "Java ALKAID_RESULT 不是有效 JSON"
                ) from exc
            if not isinstance(result, dict):
                raise RuntimeError("Java 返回结果不是 JSON 对象")
            return result
        raise RuntimeError("Java 执行成功，但没有输出 ALKAID_RESULT")

    @staticmethod
    def _validate_runtime(
        *,
        sdk_root: Path,
        java_executable: Path,
        jar_path: Path,
    ) -> None:
        if not sdk_root.exists():
            raise RuntimeError(f"Java SDK 目录不存在：{sdk_root}")
        if not java_executable.exists():
            raise RuntimeError(f"Java 可执行文件不存在：{java_executable}")
        if not jar_path.exists():
            raise RuntimeError(f"申请链接 Jar 不存在：{jar_path}")

    @staticmethod
    def _resolve_runtime_path(value: Path, sdk_root: Path) -> Path:
        return value if value.is_absolute() else sdk_root / value

    @staticmethod
    def _mock_result(java_request: dict[str, Any]) -> dict[str, str]:
        digest = hashlib.sha256(
            json.dumps(
                java_request,
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:12].upper()
        link_id = f"LINK-{digest}"
        return {
            "internal_url": f"https://cjdk-jyrc.mock/application-entry/{link_id}",
            "external_url": (
                f"https://cjdk-jyrc.mock/application-entry/{link_id}?scope=external"
            ),
        }

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return max(0, int((monotonic() - started_at) * 1000))
