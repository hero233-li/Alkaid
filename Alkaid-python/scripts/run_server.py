#!/usr/bin/env python3
"""Run the web, Celery worker and optional beat as one supervised process group."""

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _stop_process_group(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def _command(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Alkaid server processes")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--queue", default="alkaid-prod")
    parser.add_argument("--without-beat", action="store_true")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _stop_process_group)
    signal.signal(signal.SIGINT, _stop_process_group)

    commands = [
        (
            "worker",
            _command(
                "-m",
                "celery",
                "-A",
                "config",
                "worker",
                "--loglevel=INFO",
                "--pool=solo",
                f"--queues={args.queue}",
            ),
        ),
        (
            "web",
            _command(
                "-m",
                "uvicorn",
                "config.asgi:application",
                "--host",
                args.host,
                "--port",
                str(args.port),
            ),
        ),
    ]
    if not args.without_beat:
        commands.append(
            (
                "beat",
                _command("-m", "celery", "-A", "config", "beat", "--loglevel=INFO"),
            )
        )

    processes: list[tuple[str, subprocess.Popen[bytes]]] = []
    try:
        for name, command in commands:
            print(f"Starting {name}: {' '.join(command)}", flush=True)
            processes.append((name, subprocess.Popen(command, cwd=ROOT)))

        while True:
            for name, process in processes:
                exit_code = process.poll()
                if exit_code is not None:
                    print(f"{name} exited with code {exit_code}", flush=True)
                    return exit_code or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        for _, process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for _, process in reversed(processes):
            if process.poll() is not None:
                continue
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
