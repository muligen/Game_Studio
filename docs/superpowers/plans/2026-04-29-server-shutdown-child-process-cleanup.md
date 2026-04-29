# Server Shutdown Child Process Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure FastAPI server shutdown force-kills every subprocess started by Game Studio Claude fallback paths and does not wait for long-running agent worker threads.

**Architecture:** Add a focused `studio/runtime/process_registry.py` module that wraps `subprocess.Popen`, tracks active server-owned children, and exposes `run(...)` plus `kill_all(...)`. Replace Claude fallback `subprocess.run(...)` calls with `process_registry.run(...)`, then call `process_registry.kill_all(...)` before `pool.shutdown(wait=False)` during FastAPI lifespan teardown.

**Tech Stack:** Python 3.12, FastAPI lifespan, `subprocess.Popen`, Windows `taskkill`, POSIX process groups, `pytest`, `unittest.mock`.

---

## File Structure

- Create `studio/runtime/process_registry.py`
  - Owns subprocess tracking, `run(...)`, `kill_all(...)`, and platform-specific process-tree killing.
- Create `tests/test_process_registry.py`
  - Unit tests for process tracking, cleanup, timeout behavior, and kill-all behavior using fake process objects.
- Modify `studio/llm/claude_roles.py`
  - Replace Claude role subprocess fallback `subprocess.run(...)` calls with `process_registry.run(...)`.
- Modify `studio/llm/claude_worker.py`
  - Replace worker subprocess fallback `subprocess.run(...)` call with `process_registry.run(...)`.
- Modify `studio/api/main.py`
  - Import `process_registry`.
  - Call `process_registry.kill_all(reason="server_shutdown")` before `pool.shutdown(wait=False)`.
- Modify tests:
  - `tests/test_claude_roles.py`
  - `tests/test_claude_worker.py`
  - `tests/api/test_lifespan.py`

---

### Task 1: Add Process Registry Unit Tests

**Files:**
- Create: `tests/test_process_registry.py`
- Planned create in Task 2: `studio/runtime/process_registry.py`

- [ ] **Step 1: Write failing tests for registry behavior**

Create `tests/test_process_registry.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_process_registry.py -v
```

Expected: FAIL during import with `ImportError` or `ModuleNotFoundError` for `studio.runtime.process_registry`.

- [ ] **Step 3: Commit failing tests**

```powershell
git add tests/test_process_registry.py
git commit -m "test: add process registry cleanup coverage"
```

---

### Task 2: Implement Process Registry

**Files:**
- Create: `studio/runtime/process_registry.py`
- Test: `tests/test_process_registry.py`

- [ ] **Step 1: Add the registry implementation**

Create `studio/runtime/process_registry.py`:

```python
from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    args: list[str]
    cwd: str | None
    purpose: str
    started_at: str


class ProcessRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: dict[int, tuple[subprocess.Popen[str], ProcessInfo]] = {}

    def register(
        self,
        process: subprocess.Popen[str],
        *,
        args: Sequence[object],
        cwd: str | os.PathLike[str] | None,
        purpose: str,
    ) -> None:
        info = ProcessInfo(
            pid=int(process.pid),
            args=[str(item) for item in args],
            cwd=str(cwd) if cwd is not None else None,
            purpose=purpose,
            started_at=datetime.now(UTC).isoformat(),
        )
        with self._lock:
            self._processes[info.pid] = (process, info)

    def unregister(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._processes.pop(int(process.pid), None)

    def active_processes(self) -> list[ProcessInfo]:
        with self._lock:
            return [info for _, info in self._processes.values()]

    def kill_all(self, *, reason: str = "shutdown") -> dict[str, int]:
        with self._lock:
            entries = list(self._processes.values())

        attempted = 0
        already_exited = 0
        failed = 0
        for process, info in entries:
            if process.poll() is not None:
                already_exited += 1
                self.unregister(process)
                continue
            attempted += 1
            try:
                _kill_process_tree(process, reason)
            except Exception:
                failed += 1
                logger.exception("failed to kill process tree pid=%s purpose=%s", info.pid, info.purpose)
            finally:
                self.unregister(process)

        summary = {
            "attempted": attempted,
            "already_exited": already_exited,
            "failed": failed,
        }
        logger.info("process registry kill_all complete: %s", summary)
        return summary


_registry = ProcessRegistry()


def active_processes() -> list[ProcessInfo]:
    return _registry.active_processes()


def kill_all(*, reason: str = "shutdown") -> dict[str, int]:
    return _registry.kill_all(reason=reason)


def run(
    args: Sequence[object],
    *,
    input: str | bytes | None = None,
    capture_output: bool = False,
    text: bool | None = None,
    encoding: str | None = None,
    errors: str | None = None,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    purpose: str = "subprocess",
) -> subprocess.CompletedProcess[str]:
    popen_kwargs: dict[str, Any] = {
        "cwd": cwd,
        "env": dict(env) if env is not None else None,
        "text": text,
        "encoding": encoding,
        "errors": errors,
    }
    if capture_output:
        popen_kwargs["stdout"] = subprocess.PIPE
        popen_kwargs["stderr"] = subprocess.PIPE
    if _supports_process_group():
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen(args, **popen_kwargs)
    _registry.register(process, args=args, cwd=cwd, purpose=purpose)
    try:
        stdout, stderr = process.communicate(input=input, timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_tree(process, "timeout")
        process.wait(timeout=5)
        raise
    finally:
        _registry.unregister(process)

    return subprocess.CompletedProcess(
        args=list(args),
        returncode=process.returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _supports_process_group() -> bool:
    return os.name != "nt"


def _kill_process_tree(process: subprocess.Popen[str], reason: str) -> None:
    pid = int(process.pid)
    logger.warning("force killing process tree pid=%s reason=%s", pid, reason)
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            logger.exception("taskkill failed for pid=%s; falling back to process.kill()", pid)
            process.kill()
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except ProcessLookupError:
            return
        except Exception:
            logger.exception("killpg failed for pid=%s; falling back to process.kill()", pid)
            process.kill()
```

- [ ] **Step 2: Run process registry tests**

Run:

```powershell
uv run pytest tests/test_process_registry.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit registry implementation**

```powershell
git add studio/runtime/process_registry.py tests/test_process_registry.py
git commit -m "feat: add server child process registry"
```

---

### Task 3: Route Claude Subprocess Fallbacks Through Registry

**Files:**
- Modify: `studio/llm/claude_roles.py`
- Modify: `studio/llm/claude_worker.py`
- Modify: `tests/test_claude_roles.py`
- Modify: `tests/test_claude_worker.py`

- [ ] **Step 1: Add regression tests for Claude role registry usage**

In `tests/test_claude_roles.py`, update existing subprocess fallback tests that patch `subprocess.run` to patch `process_registry.run` instead. Add this import near the existing imports:

```python
from studio.runtime import process_registry
```

Add a focused test near the existing subprocess tests:

```python
def test_role_subprocess_fallback_uses_process_registry(monkeypatch, tmp_path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_profile(
            name="reviewer",
            system_prompt="reviewer prompt",
            claude_project_root=claude_root,
        ),
    )

    calls: list[dict[str, object]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append({"cmd": cmd, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout='{"decision":"approve","risks":[],"summary":"ok"}',
            stderr="",
        )

    monkeypatch.setattr(process_registry, "run", fake_run)

    adapter._generate_payload_via_subprocess(
        "reviewer",
        {"prompt": "Review it"},
        "prompt text",
    )

    assert calls
    assert calls[0]["kwargs"]["purpose"] == "claude_role:reviewer"
```

- [ ] **Step 2: Add regression test for Claude chat registry usage**

In `tests/test_claude_roles.py`, add:

```python
def test_chat_subprocess_fallback_uses_process_registry(monkeypatch, tmp_path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "reviewer"
    claude_root.mkdir(parents=True)
    adapter = ClaudeRoleAdapter(
        project_root=tmp_path,
        profile=_profile(
            name="reviewer",
            system_prompt="reviewer prompt",
            claude_project_root=claude_root,
        ),
    )

    calls: list[dict[str, object]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append({"cmd": cmd, "kwargs": kwargs})
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="reply", stderr="")

    monkeypatch.setattr(process_registry, "run", fake_run)

    assert adapter._chat_via_subprocess("hello") == "reply"
    assert calls[0]["kwargs"]["purpose"] == "claude_role:chat"
```

- [ ] **Step 3: Add regression test for worker registry usage**

In `tests/test_claude_worker.py`, add this import near existing imports:

```python
from studio.runtime import process_registry
```

Add this test near the worker subprocess tests:

```python
def test_worker_subprocess_fallback_uses_process_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    claude_root = tmp_path / ".claude" / "agents" / "worker"
    claude_root.mkdir(parents=True)
    profile = _profile(system_prompt="worker prompt", claude_project_root=claude_root)
    adapter = ClaudeWorkerAdapter(project_root=tmp_path, profile=profile)

    calls: list[dict[str, object]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append({"cmd": cmd, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout='{"title":"Demo","summary":"Summary","genre":"Puzzle"}',
            stderr="",
        )

    monkeypatch.setattr(process_registry, "run", fake_run)

    payload = adapter._generate_design_brief_via_subprocess("Design a puzzle")

    assert payload.title == "Demo"
    assert calls[0]["kwargs"]["purpose"] == "claude_worker"
```

- [ ] **Step 4: Run new tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_claude_roles.py::test_role_subprocess_fallback_uses_process_registry tests/test_claude_roles.py::test_chat_subprocess_fallback_uses_process_registry tests/test_claude_worker.py::test_worker_subprocess_fallback_uses_process_registry -v
```

Expected: FAIL because current code still calls `subprocess.run`, so the fake `process_registry.run` is not used.

- [ ] **Step 5: Replace Claude role subprocess calls**

Modify `studio/llm/claude_roles.py`:

Add import:

```python
from studio.runtime import process_registry
```

In `_generate_payload_via_subprocess`, replace:

```python
proc = subprocess.run(
```

with:

```python
proc = process_registry.run(
```

and add:

```python
purpose=f"claude_role:{role_name}",
```

to the call arguments.

In `_chat_via_subprocess`, replace `subprocess.run(...)` with
`process_registry.run(...)` and add:

```python
purpose="claude_role:chat",
```

- [ ] **Step 6: Replace Claude worker subprocess call**

Modify `studio/llm/claude_worker.py`:

Add import:

```python
from studio.runtime import process_registry
```

In `_generate_design_brief_via_subprocess`, replace:

```python
proc = subprocess.run(
```

with:

```python
proc = process_registry.run(
```

and add:

```python
purpose="claude_worker",
```

to the call arguments.

- [ ] **Step 7: Run Claude adapter tests**

Run:

```powershell
uv run pytest tests/test_claude_roles.py tests/test_claude_worker.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit Claude subprocess registry integration**

```powershell
git add studio/llm/claude_roles.py studio/llm/claude_worker.py tests/test_claude_roles.py tests/test_claude_worker.py
git commit -m "feat: track Claude fallback subprocesses"
```

---

### Task 4: Force Kill Registered Processes During FastAPI Shutdown

**Files:**
- Modify: `studio/api/main.py`
- Modify: `tests/api/test_lifespan.py`

- [ ] **Step 1: Add lifespan shutdown test**

Replace `tests/api/test_lifespan.py` with:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def test_app_lifespan_shutdown_kills_child_processes_before_pool_shutdown():
    events: list[str] = []

    with (
        patch("studio.api.main.WorkflowPoller") as MockWorkflowPoller,
        patch("studio.api.main.DeliveryTaskPoller") as MockDeliveryTaskPoller,
        patch("studio.api.main.process_registry") as mock_registry,
        patch("studio.api.main.pool") as mock_pool,
    ):
        workflow_poller = MagicMock()
        delivery_poller = MagicMock()

        async def workflow_start():
            events.append("workflow_start")

        async def delivery_start():
            events.append("delivery_start")

        async def workflow_stop():
            events.append("workflow_stop")

        async def delivery_stop():
            events.append("delivery_stop")

        workflow_poller.start = workflow_start
        delivery_poller.start = delivery_start
        workflow_poller.stop = workflow_stop
        delivery_poller.stop = delivery_stop
        MockWorkflowPoller.return_value = workflow_poller
        MockDeliveryTaskPoller.return_value = delivery_poller

        def kill_all(*, reason: str):
            events.append(f"kill_all:{reason}")
            return {"attempted": 0, "already_exited": 0, "failed": 0}

        def shutdown(*, wait: bool = True):
            events.append(f"pool_shutdown:{wait}")

        mock_registry.kill_all.side_effect = kill_all
        mock_pool.shutdown.side_effect = shutdown

        from studio.api.main import create_app

        app = create_app()
        with TestClient(app) as client:
            assert client.get("/api/health").json() == {"status": "ok"}

    assert "workflow_stop" in events
    assert "delivery_stop" in events
    assert events.index("kill_all:server_shutdown") < events.index("pool_shutdown:False")
```

- [ ] **Step 2: Run lifespan test to verify it fails**

Run:

```powershell
uv run pytest tests/api/test_lifespan.py -v
```

Expected: FAIL because `studio.api.main` does not import or call `process_registry`, and `pool.shutdown` currently uses default wait behavior.

- [ ] **Step 3: Update FastAPI lifespan shutdown**

Modify `studio/api/main.py`:

Add import:

```python
from studio.runtime import pool, process_registry
```

Replace the existing separate `from studio.runtime import pool` import.

In `_default_lifespan`, after awaiting/canceling poller tasks and before pool shutdown, replace:

```python
pool.shutdown()
```

with:

```python
process_registry.kill_all(reason="server_shutdown")
pool.shutdown(wait=False)
```

- [ ] **Step 4: Run lifespan tests**

Run:

```powershell
uv run pytest tests/api/test_lifespan.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit lifespan shutdown integration**

```powershell
git add studio/api/main.py tests/api/test_lifespan.py
git commit -m "feat: kill child processes during server shutdown"
```

---

### Task 5: Focused Verification

**Files:**
- Verify: `studio/runtime/process_registry.py`
- Verify: `studio/llm/claude_roles.py`
- Verify: `studio/llm/claude_worker.py`
- Verify: `studio/api/main.py`

- [ ] **Step 1: Run focused test suite**

Run:

```powershell
uv run pytest tests/test_process_registry.py tests/test_claude_roles.py tests/test_claude_worker.py tests/api/test_lifespan.py -v
```

Expected: PASS.

- [ ] **Step 2: Run existing Langfuse/hook tests to check adjacent integrations**

Run:

```powershell
uv run pytest tests/test_langfuse_observability.py tests/test_claude_code_langfuse_hook.py -v
```

Expected: PASS.

- [ ] **Step 3: Run a disabled-Claude smoke test**

Run:

```powershell
$env:GAME_STUDIO_CLAUDE_ENABLED = "false"
$env:GAME_STUDIO_LANGFUSE_ENABLED = "false"
uv run python -m studio.interfaces.cli run-demo --workspace .runtime-data --prompt "Design a simple 2D game concept"
```

Expected: command completes and prints a demo result.

- [ ] **Step 4: Inspect git status**

Run:

```powershell
git status --short
```

Expected: no uncommitted implementation changes.

---

## Implementation Notes

- Do not scan global process lists by name.
- Do not kill user-owned Claude Code sessions.
- Keep `process_registry.run(...)` behavior close to `subprocess.run(...)` for current call sites.
- The strong shutdown behavior is intentional: `pool.shutdown(wait=False)` is required.
- If a test monkeypatch currently targets `subprocess.run` for Claude fallback code, update it to target `studio.runtime.process_registry.run`.
