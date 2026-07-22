from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType


def load_dev_server() -> ModuleType:
    script = Path(__file__).parents[1] / "scripts" / "run_dev_server.py"
    spec = importlib.util.spec_from_file_location("run_dev_server", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_snapshot_detects_python_changes_and_ignores_cache(tmp_path: Path) -> None:
    dev_server = load_dev_server()
    source = tmp_path / "apps" / "service.py"
    source.parent.mkdir()
    source.write_text("value = 1\n", encoding="utf-8")
    ignored = tmp_path / "apps" / "__pycache__" / "cached.py"
    ignored.parent.mkdir()
    ignored.write_text("value = 1\n", encoding="utf-8")

    before = dev_server.source_snapshot(tmp_path)
    source.write_text("value = 200\n", encoding="utf-8")
    after = dev_server.source_snapshot(tmp_path)

    assert source in before
    assert ignored not in before
    assert dev_server.changed_sources(before, after) == [source]


class FakeProcess:
    def __init__(self, *, times_out: bool = False) -> None:
        self.running = True
        self.times_out = times_out
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return None if self.running else 0

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        if self.times_out and not self.killed:
            raise subprocess.TimeoutExpired("uvicorn", timeout)
        self.running = False
        return 0

    def kill(self) -> None:
        self.killed = True


def test_stop_process_terminates_only_managed_child() -> None:
    dev_server = load_dev_server()
    process = FakeProcess()

    dev_server.stop_process(process)

    assert process.terminated is True
    assert process.killed is False


def test_stop_process_kills_child_after_timeout() -> None:
    dev_server = load_dev_server()
    process = FakeProcess(times_out=True)

    dev_server.stop_process(process, timeout=0.01)

    assert process.terminated is True
    assert process.killed is True
