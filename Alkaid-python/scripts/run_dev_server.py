#!/usr/bin/env python3
"""Run Uvicorn with a Windows-safe polling reloader.

Uvicorn's native Windows reloader uses CTRL_C_EVENT to stop its child. When the
backend shares a console with Vite and Celery, that event can stop every process
in the console. This supervisor runs Uvicorn without ``--reload`` and terminates
only that child when Python sources change.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRECTORY_NAMES = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__"}


class ManagedProcess(Protocol):
    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def kill(self) -> None: ...


def source_snapshot(root: Path) -> dict[Path, tuple[int, int]]:
    """Return enough source metadata to detect creates, edits and deletes."""
    snapshot: dict[Path, tuple[int, int]] = {}
    for path in root.rglob("*.py"):
        if any(part in IGNORED_DIRECTORY_NAMES for part in path.parts):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        snapshot[path] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def changed_sources(
    previous: dict[Path, tuple[int, int]],
    current: dict[Path, tuple[int, int]],
) -> list[Path]:
    return sorted(
        path for path in previous.keys() | current.keys() if previous.get(path) != current.get(path)
    )


def stop_process(process: ManagedProcess, timeout: float = 10) -> None:
    """Stop only the Uvicorn child; on Windows terminate() uses TerminateProcess."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout)


def start_uvicorn(host: str, port: int) -> subprocess.Popen[bytes]:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "config.asgi:application",
        "--host",
        host,
        "--port",
        str(port),
    ]
    print(f"Starting backend: {' '.join(command)}", flush=True)
    return subprocess.Popen(command, cwd=ROOT)


def supervise(host: str, port: int, poll_seconds: float) -> int:
    process = start_uvicorn(host, port)
    snapshot = source_snapshot(ROOT)
    try:
        while True:
            exit_code = process.poll()
            if exit_code is not None:
                print(f"Backend exited with code {exit_code}", flush=True)
                return exit_code

            time.sleep(poll_seconds)
            current = source_snapshot(ROOT)
            changed = changed_sources(snapshot, current)
            if not changed:
                continue

            preview = ", ".join(str(path.relative_to(ROOT)) for path in changed[:5])
            if len(changed) > 5:
                preview += f", ... ({len(changed)} files)"
            print(f"Python source changed: {preview}; restarting backend", flush=True)

            # Allow editors that save through a temporary file to finish before restart.
            time.sleep(min(poll_seconds, 0.25))
            snapshot = source_snapshot(ROOT)
            stop_process(process)
            process = start_uvicorn(host, port)
    except KeyboardInterrupt:
        return 0
    finally:
        stop_process(process)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Alkaid backend with safe source reload")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be greater than zero")
    return supervise(args.host, args.port, args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
