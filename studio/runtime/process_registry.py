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
