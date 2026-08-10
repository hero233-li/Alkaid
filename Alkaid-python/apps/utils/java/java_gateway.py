from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RESULT_PREFIX = "ALKAID_RESULT="


@dataclass(frozen=True)
class JavaGatewayConfig:
    sdk_dir: Path
    java_executable: Path
    jar: Path
    main_class: str
    output_encoding: str = "utf-8"
    timeout_seconds: float = 120


class JavaGateway:
    """Run one local Java SDK entrypoint using a JSON request-file contract."""

    def __init__(self, config: JavaGatewayConfig) -> None:
        self._config = config

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        sdk_root = self._config.sdk_dir
        java_executable = _resolve_runtime_path(self._config.java_executable, sdk_root)
        jar_path = _resolve_runtime_path(self._config.jar, sdk_root)
        _validate_runtime(
            sdk_root=sdk_root,
            java_executable=java_executable,
            jar_path=jar_path,
        )
        classpath = os.pathsep.join([str(jar_path), str(sdk_root / "lib" / "*")])
        with tempfile.TemporaryDirectory(prefix="alkaid-java-") as temp_dir:
            request_path = Path(temp_dir) / "request.json"
            request_path.write_text(
                json.dumps(request, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            command = [
                str(java_executable),
                "-cp",
                classpath,
                self._config.main_class,
                str(request_path),
            ]
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(sdk_root),
                    shell=False,
                    capture_output=True,
                    text=True,
                    encoding=self._config.output_encoding,
                    errors="replace",
                    timeout=self._config.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(f"Java SDK 执行超时：{self._config.timeout_seconds} 秒") from exc
            except OSError as exc:
                raise RuntimeError(f"Java SDK 无法启动：{exc}") from exc
        if completed.returncode != 0:
            error_tail = completed.stderr[-2000:]
            raise RuntimeError(
                f"Java SDK 执行失败：exit_code={completed.returncode}; stderr={error_tail}"
            )
        return parse_java_result(completed.stdout)


def parse_java_result(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        normalized = line.strip()
        if normalized.startswith(RESULT_PREFIX):
            try:
                result = json.loads(normalized[len(RESULT_PREFIX) :])
            except json.JSONDecodeError as exc:
                raise RuntimeError("Java ALKAID_RESULT 不是有效 JSON") from exc
            if not isinstance(result, dict):
                raise RuntimeError("Java 返回结果不是 JSON 对象")
            return result
    raise RuntimeError("Java 执行成功，但没有输出 ALKAID_RESULT")


def _validate_runtime(*, sdk_root: Path, java_executable: Path, jar_path: Path) -> None:
    if not sdk_root.exists():
        raise RuntimeError(f"Java SDK 目录不存在：{sdk_root}")
    if not java_executable.exists():
        raise RuntimeError(f"Java 可执行文件不存在：{java_executable}")
    if not jar_path.exists():
        raise RuntimeError(f"Java SDK Jar 不存在：{jar_path}")


def _resolve_runtime_path(value: Path, sdk_root: Path) -> Path:
    return value if value.is_absolute() else sdk_root / value
