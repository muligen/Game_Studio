from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from studio.runtime import process_registry


class FakeProcess:
    def __init__(
        self,
        *,
        pid: int = 1234,
        stdout: str = "out",
        stderr: str = "err",
        returncode: int = 0,
        timeout: bool = False,
    ) -> None:
        self.pid = pid
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.timeout = timeout
        self.communicate_calls: list[dict[str, object]] = []
        self.kill_called = False
        self.poll_value: int | None = None

    def communicate(self, input: object = None, timeout: float | None = None):
        self.communicate_calls.append({"input": input, "timeout": timeout})
        if self.timeout:
            raise subprocess.TimeoutExpired(cmd=["fake"], timeout=timeout)
        return self.stdout, self.stderr

    def poll(self) -> int | None:
        return self.poll_value

    def kill(self) -> None:
        self.kill_called = True

    def wait(self, timeout: float | None = None) -> int:
        self.returncode = -9
        self.poll_value = -9
        return self.returncode


class FakePopenFactory:
    def __init__(self, process: FakeProcess) -> None:
        self.process = process
        self.calls: list[dict[str, Any]] = []

    def __call__(self, args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return self.process


def test_run_registers_and_unregisters_process(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess(pid=4321, stdout="hello", stderr="", returncode=7)
    factory = FakePopenFactory(process)
    monkeypatch.setattr(process_registry.subprocess, "Popen", factory)

    completed = process_registry.run(
        ["python", "--version"],
        input="payload",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=Path("."),
        env={"A": "B"},
        timeout=3,
        purpose="unit-test",
    )

    assert completed.args == ["python", "--version"]
    assert completed.returncode == 7
    assert completed.stdout == "hello"
    assert completed.stderr == ""
    assert process.communicate_calls == [{"input": "payload", "timeout": 3}]
    assert process_registry.active_processes() == []
    assert factory.calls[0]["kwargs"]["cwd"] == Path(".")
    assert factory.calls[0]["kwargs"]["env"] == {"A": "B"}


def test_run_timeout_kills_and_unregisters(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess(pid=5000, timeout=True)
    factory = FakePopenFactory(process)
    killed: list[int] = []
    monkeypatch.setattr(process_registry.subprocess, "Popen", factory)
    monkeypatch.setattr(process_registry, "_kill_process_tree", lambda proc, reason: killed.append(proc.pid))

    with pytest.raises(subprocess.TimeoutExpired):
        process_registry.run(["slow"], timeout=1, purpose="slow-test")

    assert killed == [5000]
    assert process_registry.active_processes() == []


def test_kill_all_kills_each_active_process(monkeypatch: pytest.MonkeyPatch) -> None:
    proc_a = FakeProcess(pid=1001)
    proc_b = FakeProcess(pid=1002)
    killed: list[tuple[int, str]] = []

    registry = process_registry.ProcessRegistry()
    registry.register(proc_a, args=["a"], cwd=None, purpose="a")
    registry.register(proc_b, args=["b"], cwd=None, purpose="b")

    monkeypatch.setattr(
        process_registry,
        "_kill_process_tree",
        lambda proc, reason: killed.append((proc.pid, reason)),
    )

    summary = registry.kill_all(reason="server_shutdown")

    assert killed == [(1001, "server_shutdown"), (1002, "server_shutdown")]
    assert summary["attempted"] == 2
    assert summary["failed"] == 0
    assert registry.active_processes() == []


def test_kill_all_ignores_already_exited_process(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = FakeProcess(pid=2001)
    proc.poll_value = 0
    killed: list[int] = []

    registry = process_registry.ProcessRegistry()
    registry.register(proc, args=["done"], cwd=None, purpose="done")
    monkeypatch.setattr(process_registry, "_kill_process_tree", lambda proc, reason: killed.append(proc.pid))

    summary = registry.kill_all(reason="server_shutdown")

    assert killed == []
    assert summary["attempted"] == 0
    assert summary["already_exited"] == 1
    assert registry.active_processes() == []
