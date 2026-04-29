# Server Shutdown Child Process Cleanup Design

## Context

Game Studio starts background work from the FastAPI application lifespan in
`studio/api/main.py`. The server starts a `WorkflowPoller` and a
`DeliveryTaskPoller`; both can submit agent work to the shared thread pool in
`studio/runtime/pool.py`.

Live Claude work can run in two ways:

- In-process Claude Agent SDK calls.
- Subprocess fallback paths in `studio/llm/claude_roles.py` and
  `studio/llm/claude_worker.py`.

The subprocess fallback currently uses `subprocess.run(...)`. That waits for
the child process to finish, but the server has no central list of child
processes it started. During shutdown, `pool.shutdown(wait=True)` can block
while an agent task is stuck inside a Claude subprocess. If the server process
is stopped at the wrong time, Claude Code or Python subprocesses can remain
alive longer than intended.

The desired behavior is strict: when the server shuts down, it must force-kill
all child processes that this server started.

## Goals

- Track every subprocess started by the server for Claude subprocess fallback
  paths.
- Force-kill tracked child processes and their descendants during FastAPI
  shutdown.
- Avoid waiting for long-running agent tasks after shutdown begins.
- Avoid killing unrelated user processes, including Claude Code sessions the
  user started manually.
- Keep subprocess call sites close to their current shape.
- Keep cleanup best-effort and robust: shutdown should continue even if one
  process is already gone or cannot be killed.

## Non-Goals

- Killing every process named `claude`, `node`, or `python` on the machine.
- Managing processes started outside the Game Studio server process.
- Changing prompt content, agent routing, or Claude Agent SDK behavior.
- Replacing the shared thread pool with a new execution framework.
- Adding graceful shutdown configuration. The chosen behavior is always
  force-kill tracked server-started child processes.

## Recommended Approach

Add a small runtime process registry:

```text
studio/runtime/process_registry.py
```

The registry owns subprocess lifecycle for server-started children. It exposes a
`run(...)` helper that mirrors the subset of `subprocess.run(...)` used by the
Claude fallback paths, and a `kill_all(...)` helper for shutdown.

Claude subprocess fallback call sites should use:

```python
from studio.runtime import process_registry

proc = process_registry.run(...)
```

instead of:

```python
proc = subprocess.run(...)
```

The registry implementation should use `subprocess.Popen(...)` internally so it
can register the process before waiting on it. On normal completion, timeout, or
error, it unregisters the process.

FastAPI lifespan teardown should call:

```python
process_registry.kill_all(reason="server_shutdown")
pool.shutdown(wait=False)
```

This ensures shutdown is decisive. Running thread-pool tasks will be unblocked
when their child subprocess is killed, and the server will not wait for the
pool to drain.

## Process Ownership

Only subprocesses started through `process_registry.run(...)` are tracked and
killed. This avoids process-name scanning and prevents accidental termination
of user-owned Claude Code or terminal sessions.

Tracked metadata should include:

- PID
- command preview
- cwd
- started_at
- purpose, when provided by the caller

The metadata is for logs and tests; it is not a persistence contract.

## Cross-Platform Kill Strategy

Windows:

- Start child processes normally or in a new process group if needed.
- Force-kill the process tree with:

```powershell
taskkill /PID <pid> /T /F
```

Non-Windows:

- Start child processes in their own process group with `start_new_session=True`.
- Force-kill the process group with:

```python
os.killpg(os.getpgid(pid), signal.SIGKILL)
```

If process-group killing fails because the process has already exited, the
registry should treat that as success.

## Shutdown Flow

Update the FastAPI lifespan teardown in `studio/api/main.py`:

1. Signal both pollers to stop.
2. Cancel and await the poller tasks.
3. Call `process_registry.kill_all(reason="server_shutdown")`.
4. Call `pool.shutdown(wait=False)`.
5. Log cleanup failures but do not re-raise them from shutdown.

The key behavior change is that process cleanup happens before thread-pool
shutdown. This gives running worker threads a chance to exit because their
blocked subprocess wait has been interrupted by the forced kill.

## Affected Call Sites

Replace direct `subprocess.run(...)` only where the server can launch long-lived
Claude subprocess fallback work:

- `studio/llm/claude_roles.py`
  - `_generate_payload_via_subprocess`
  - `_chat_via_subprocess`
- `studio/llm/claude_worker.py`
  - `_generate_design_brief_via_subprocess`

Other short utility subprocess calls, such as Git commands in
`studio/storage/git_tracker.py`, can remain unchanged unless they become part
of a long-running server-owned execution path.

## Error Handling

`process_registry.run(...)` should preserve normal `subprocess.run(...)`
semantics used by current callers:

- Return a `subprocess.CompletedProcess[str]` on normal completion.
- Raise `subprocess.TimeoutExpired` on timeout.
- Raise `OSError` for launch failures.
- Preserve `stdout`, `stderr`, `returncode`, text mode, encoding, errors, cwd,
  env, and timeout behavior expected by current call sites.

During shutdown:

- `kill_all(...)` must not raise for already-exited processes.
- If killing one process fails, it should keep trying the rest.
- It should return or log a cleanup summary containing attempted and failed
  kills.

## Testing Strategy

Unit tests for `studio/runtime/process_registry.py`:

- `run(...)` registers a process and unregisters it after completion.
- `run(...)` passes through input, cwd, env, text, encoding, errors, and timeout.
- timeout triggers a force kill and raises `subprocess.TimeoutExpired`.
- `kill_all(...)` calls the platform kill function for every active process.
- `kill_all(...)` removes processes that have already exited.

Integration-style tests:

- `ClaudeRoleAdapter._generate_payload_via_subprocess` uses
  `process_registry.run`.
- `ClaudeRoleAdapter._chat_via_subprocess` uses `process_registry.run`.
- `ClaudeWorkerAdapter._generate_design_brief_via_subprocess` uses
  `process_registry.run`.
- FastAPI lifespan teardown calls `process_registry.kill_all(...)` before
  `pool.shutdown(wait=False)`.

Manual verification:

- Start the API server.
- Trigger a workflow that starts a live Claude subprocess.
- Stop the server while the subprocess is running.
- Confirm no server-started Claude/Python child process remains.
- Confirm unrelated manually started Claude Code sessions are still alive.

## Rollout

1. Add `studio/runtime/process_registry.py` with a testable registry and module
   level helpers.
2. Add unit tests for registry behavior using fake `Popen` and fake kill
   functions where possible.
3. Replace Claude subprocess fallback call sites with `process_registry.run`.
4. Update FastAPI lifespan teardown to call `kill_all` and
   `pool.shutdown(wait=False)`.
5. Add lifespan and Claude adapter regression tests.
6. Run focused tests for process registry, Claude adapters, and API lifespan.

## Risks

- Killing the subprocess tree may surface `ClaudeRoleError` or
  `ClaudeWorkerError` in tasks that were running during shutdown. This is
  acceptable because shutdown has begun.
- Windows `taskkill` availability is assumed. If it is unavailable, the
  registry should fall back to `Popen.kill()` for the root process and log that
  descendant cleanup may be incomplete.
- `pool.shutdown(wait=False)` means in-flight Python worker threads are not
  awaited by the lifespan teardown. This matches the requirement for decisive
  shutdown, but logs may still show late task cleanup as killed subprocesses
  unwind.
