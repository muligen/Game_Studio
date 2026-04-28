# Claude Code Agent Langfuse Hook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Langfuse tracing to every Claude Code subagent under `.claude/agents/*` through a shared Stop hook that delegates to `douinc/langfuse-claudecode`.

**Architecture:** Put testable hook orchestration in `studio/observability/claude_code_hook.py`, keep `.claude/hooks/langfuse_hook.py` as a tiny entry script, and update each agent's own `.claude/settings.local.json` to call the shared script. The wrapper normalizes environment variables, derives agent role from the Claude project directory, and delegates transcript upload to the globally installed `langfuse-claudecode` hook.

**Tech Stack:** Python 3.12, Claude Code hooks, `uv`, `douinc/langfuse-claudecode`, `pytest`, JSON settings files.

---

## File Structure

- Create `studio/observability/claude_code_hook.py`
  - Owns all testable hook behavior: stdin parsing boundary, environment normalization, agent role detection, upstream hook command construction, fail-open execution.
- Create `.claude/hooks/langfuse_hook.py`
  - Thin script used by Claude Code settings. It imports and calls `studio.observability.claude_code_hook.main`.
- Modify all `.claude/agents/*/.claude/settings.local.json`
  - Preserve existing permissions.
  - Add `env.TRACE_TO_LANGFUSE=true`.
  - Add a `Stop` hook command pointing to `../../hooks/langfuse_hook.py`.
- Create `tests/test_claude_code_langfuse_hook.py`
  - Tests the wrapper without invoking real Langfuse or Claude Code.
- Modify `docs/agent-debugging.md`
  - Documents global `langfuse-claudecode` installation, credential setup, and manual verification.

---

### Task 1: Add Hook Wrapper Unit Tests

**Files:**
- Create: `tests/test_claude_code_langfuse_hook.py`
- Planned create in Task 2: `studio/observability/claude_code_hook.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_claude_code_langfuse_hook.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from studio.observability.claude_code_hook import (
    HookResult,
    agent_role_from_project_dir,
    build_upstream_command,
    normalize_env,
    run_hook,
)


def test_agent_role_from_nested_claude_agent_dir() -> None:
    project_dir = Path("F:/projs/Game_Studio/.claude/agents/design")

    assert agent_role_from_project_dir(project_dir) == "design"


def test_agent_role_falls_back_to_directory_name() -> None:
    project_dir = Path("F:/tmp/custom-agent")

    assert agent_role_from_project_dir(project_dir) == "custom-agent"


def test_normalize_env_maps_langfuse_host_and_agent_environment(tmp_path: Path) -> None:
    env = normalize_env(
        {
            "TRACE_TO_LANGFUSE": "true",
            "LANGFUSE_PUBLIC_KEY": "pk",
            "LANGFUSE_SECRET_KEY": "sk",
            "LANGFUSE_HOST": "https://langfuse.example",
            "CLAUDE_PROJECT_DIR": str(tmp_path / ".claude" / "agents" / "qa"),
        }
    )

    assert env["LANGFUSE_BASE_URL"] == "https://langfuse.example"
    assert env["LANGFUSE_HOST"] == "https://langfuse.example"
    assert env["CC_LANGFUSE_AGENT_ROLE"] == "qa"
    assert env["CC_LANGFUSE_ENVIRONMENT"] == "game-studio-qa"


def test_normalize_env_preserves_explicit_environment(tmp_path: Path) -> None:
    env = normalize_env(
        {
            "TRACE_TO_LANGFUSE": "true",
            "LANGFUSE_PUBLIC_KEY": "pk",
            "LANGFUSE_SECRET_KEY": "sk",
            "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
            "CC_LANGFUSE_ENVIRONMENT": "local",
            "CLAUDE_PROJECT_DIR": str(tmp_path / ".claude" / "agents" / "dev"),
        }
    )

    assert env["CC_LANGFUSE_ENVIRONMENT"] == "local"
    assert env["CC_LANGFUSE_AGENT_ROLE"] == "dev"


def test_build_upstream_command_uses_global_hook_project() -> None:
    env = {
        "USERPROFILE": "C:/Users/XSJ",
        "CC_LANGFUSE_HOOK_PROJECT": "C:/Users/XSJ/.claude/hooks/langfuse-claudecode",
    }

    command = build_upstream_command(env)

    assert command[:3] == ["uv", "run", "--project"]
    assert Path(command[3]) == Path("C:/Users/XSJ/.claude/hooks/langfuse-claudecode")
    assert command[4] == "python"
    assert Path(command[5]) == Path(
        "C:/Users/XSJ/.claude/hooks/langfuse-claudecode/langfuse_hook.py"
    )


def test_run_hook_exits_zero_when_disabled() -> None:
    result = run_hook(
        stdin_text=json.dumps({"session_id": "s1"}),
        environ={"TRACE_TO_LANGFUSE": "false"},
        runner=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("runner called")),
    )

    assert result == HookResult(exit_code=0, message="Langfuse tracing disabled")


def test_run_hook_exits_zero_when_credentials_missing() -> None:
    result = run_hook(
        stdin_text=json.dumps({"session_id": "s1"}),
        environ={"TRACE_TO_LANGFUSE": "true"},
        runner=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("runner called")),
    )

    assert result.exit_code == 0
    assert result.message == "Langfuse credentials missing"


def test_run_hook_delegates_payload_to_upstream(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []
    project = tmp_path / "langfuse-claudecode"
    project.mkdir()
    script = project / "langfuse_hook.py"
    script.write_text("print('hook')\n", encoding="utf-8")

    def fake_runner(command, *, input, text, env, capture_output):
        calls.append(
            {
                "command": command,
                "input": input,
                "text": text,
                "env": env,
                "capture_output": capture_output,
            }
        )

        class Completed:
            returncode = 0
            stderr = ""

        return Completed()

    result = run_hook(
        stdin_text='{"session_id":"s1"}',
        environ={
            "TRACE_TO_LANGFUSE": "true",
            "LANGFUSE_PUBLIC_KEY": "pk",
            "LANGFUSE_SECRET_KEY": "sk",
            "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
            "CC_LANGFUSE_HOOK_PROJECT": str(project),
            "CLAUDE_PROJECT_DIR": str(tmp_path / ".claude" / "agents" / "design"),
        },
        runner=fake_runner,
    )

    assert result == HookResult(exit_code=0, message="Langfuse hook delegated")
    assert calls[0]["input"] == '{"session_id":"s1"}'
    delegated_env = calls[0]["env"]
    assert delegated_env["CC_LANGFUSE_AGENT_ROLE"] == "design"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_claude_code_langfuse_hook.py -v
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'studio.observability.claude_code_hook'`.

- [ ] **Step 3: Commit the failing tests**

```powershell
git add tests/test_claude_code_langfuse_hook.py
git commit -m "test: add Claude Code Langfuse hook wrapper coverage"
```

---

### Task 2: Implement the Testable Hook Wrapper

**Files:**
- Create: `studio/observability/claude_code_hook.py`
- Test: `tests/test_claude_code_langfuse_hook.py`

- [ ] **Step 1: Add the wrapper implementation**

Create `studio/observability/claude_code_hook.py`:

```python
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

_TRUTHY = {"1", "true", "yes", "on"}
_FALSEY = {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class HookResult:
    exit_code: int
    message: str


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _is_truthy(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in _TRUTHY:
        return True
    if lowered in _FALSEY:
        return False
    return default


def agent_role_from_project_dir(project_dir: str | Path | None) -> str:
    if project_dir is None or not str(project_dir).strip():
        return "unknown"
    path = Path(project_dir)
    parts = path.parts
    for index, part in enumerate(parts[:-1]):
        if part == "agents" and index > 0 and parts[index - 1] == ".claude":
            return parts[index + 1]
    return path.name or "unknown"


def _safe_environment_name(role: str) -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", role.strip().lower()).strip("-")
    if not normalized:
        normalized = "unknown"
    return f"game-studio-{normalized}"[:40]


def normalize_env(environ: Mapping[str, str]) -> dict[str, str]:
    env = dict(environ)
    base_url = env.get("LANGFUSE_BASE_URL") or env.get("LANGFUSE_HOST")
    if base_url:
        env["LANGFUSE_BASE_URL"] = base_url
        env["LANGFUSE_HOST"] = base_url
    role = agent_role_from_project_dir(env.get("CLAUDE_PROJECT_DIR"))
    env.setdefault("CC_LANGFUSE_AGENT_ROLE", role)
    env.setdefault("CC_LANGFUSE_ENVIRONMENT", _safe_environment_name(role))
    return env


def _default_hook_project(environ: Mapping[str, str]) -> Path:
    explicit = environ.get("CC_LANGFUSE_HOOK_PROJECT")
    if explicit:
        return Path(explicit)
    home = environ.get("HOME") or environ.get("USERPROFILE")
    if home:
        return Path(home) / ".claude" / "hooks" / "langfuse-claudecode"
    return Path.home() / ".claude" / "hooks" / "langfuse-claudecode"


def build_upstream_command(environ: Mapping[str, str]) -> list[str]:
    project = _default_hook_project(environ)
    script = project / "langfuse_hook.py"
    return ["uv", "run", "--project", str(project), "python", str(script)]


def _credentials_present(environ: Mapping[str, str]) -> bool:
    return bool(environ.get("LANGFUSE_PUBLIC_KEY") and environ.get("LANGFUSE_SECRET_KEY"))


def run_hook(
    *,
    stdin_text: str,
    environ: Mapping[str, str] | None = None,
    runner: Runner = subprocess.run,
) -> HookResult:
    env = normalize_env(environ or os.environ)
    if not _is_truthy(env.get("TRACE_TO_LANGFUSE"), default=False):
        return HookResult(0, "Langfuse tracing disabled")
    if not _credentials_present(env):
        return HookResult(0, "Langfuse credentials missing")

    command = build_upstream_command(env)
    hard_fail = _is_truthy(env.get("CC_LANGFUSE_HARD_FAIL"), default=False)
    try:
        completed = runner(
            command,
            input=stdin_text,
            text=True,
            env=env,
            capture_output=True,
        )
    except Exception as exc:
        if hard_fail:
            return HookResult(1, f"Langfuse hook failed: {exc}")
        return HookResult(0, f"Langfuse hook failed open: {exc}")

    if completed.returncode != 0:
        stderr = getattr(completed, "stderr", "") or ""
        message = stderr.strip() or f"upstream hook exited {completed.returncode}"
        if hard_fail:
            return HookResult(completed.returncode, message)
        return HookResult(0, f"Langfuse hook failed open: {message}")

    return HookResult(0, "Langfuse hook delegated")


def main() -> int:
    stdin_text = sys.stdin.read()
    result = run_hook(stdin_text=stdin_text)
    if result.message:
        print(result.message, file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run wrapper tests**

Run:

```powershell
uv run pytest tests/test_claude_code_langfuse_hook.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit the wrapper**

```powershell
git add studio/observability/claude_code_hook.py tests/test_claude_code_langfuse_hook.py
git commit -m "feat: add Claude Code Langfuse hook wrapper"
```

---

### Task 3: Add the Shared Claude Hook Entry Script

**Files:**
- Create: `.claude/hooks/langfuse_hook.py`
- Test: `tests/test_claude_code_langfuse_hook.py`

- [ ] **Step 1: Write a test that the hook script exists and imports the wrapper**

Append to `tests/test_claude_code_langfuse_hook.py`:

```python
def test_shared_hook_script_exists_and_uses_wrapper() -> None:
    script = Path(".claude/hooks/langfuse_hook.py")

    assert script.exists()
    content = script.read_text(encoding="utf-8")
    assert "from studio.observability.claude_code_hook import main" in content
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:

```powershell
uv run pytest tests/test_claude_code_langfuse_hook.py::test_shared_hook_script_exists_and_uses_wrapper -v
```

Expected: FAIL because `.claude/hooks/langfuse_hook.py` does not exist.

- [ ] **Step 3: Create the shared hook script**

Create `.claude/hooks/langfuse_hook.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from studio.observability.claude_code_hook import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run hook script tests**

Run:

```powershell
uv run pytest tests/test_claude_code_langfuse_hook.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the shared script**

`.claude/` is ignored by `.gitignore`, so force-add only this new hook script.

```powershell
git add -f .claude/hooks/langfuse_hook.py
git add tests/test_claude_code_langfuse_hook.py
git commit -m "feat: add shared Claude Code Langfuse hook entrypoint"
```

---

### Task 4: Wire Every Agent Settings File to the Shared Stop Hook

**Files:**
- Modify: `.claude/agents/art/.claude/settings.local.json`
- Modify: `.claude/agents/delivery_planner/.claude/settings.local.json`
- Modify: `.claude/agents/design/.claude/settings.local.json`
- Modify: `.claude/agents/dev/.claude/settings.local.json`
- Modify: `.claude/agents/moderator/.claude/settings.local.json`
- Modify: `.claude/agents/qa/.claude/settings.local.json`
- Modify: `.claude/agents/quality/.claude/settings.local.json`
- Modify: `.claude/agents/requirement_clarifier/.claude/settings.local.json`
- Modify: `.claude/agents/reviewer/.claude/settings.local.json`
- Modify: `.claude/agents/worker/.claude/settings.local.json`
- Test: `tests/test_claude_code_langfuse_hook.py`

- [ ] **Step 1: Add settings validation tests**

Append to `tests/test_claude_code_langfuse_hook.py`:

```python
AGENT_NAMES = [
    "art",
    "delivery_planner",
    "design",
    "dev",
    "moderator",
    "qa",
    "quality",
    "requirement_clarifier",
    "reviewer",
    "worker",
]


def test_all_agent_settings_have_langfuse_stop_hook() -> None:
    expected_command = 'uv run python "../../hooks/langfuse_hook.py"'

    for agent_name in AGENT_NAMES:
        path = Path(".claude") / "agents" / agent_name / ".claude" / "settings.local.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        assert data["env"]["TRACE_TO_LANGFUSE"] == "true"
        assert data["hooks"]["Stop"][0]["hooks"][0] == {
            "type": "command",
            "command": expected_command,
        }


def test_all_agent_settings_preserve_permissions() -> None:
    for agent_name in AGENT_NAMES:
        path = Path(".claude") / "agents" / agent_name / ".claude" / "settings.local.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        assert data["permissions"]["allow"] == ["Bash(*)", "Edit(*)"]
```

- [ ] **Step 2: Run settings tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_claude_code_langfuse_hook.py::test_all_agent_settings_have_langfuse_stop_hook -v
```

Expected: FAIL with `KeyError: 'env'` on the first unmodified agent settings file.

- [ ] **Step 3: Update each agent settings file**

Replace the content of each listed `.claude/agents/<agent>/.claude/settings.local.json` with:

```json
{
  "permissions": {
    "allow": [
      "Bash(*)",
      "Edit(*)"
    ]
  },
  "env": {
    "TRACE_TO_LANGFUSE": "true"
  },
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run python \"../../hooks/langfuse_hook.py\""
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: Run JSON and settings validation tests**

Run:

```powershell
uv run pytest tests/test_claude_code_langfuse_hook.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit agent settings wiring**

These files are under ignored `.claude/`, so force-add the tracked settings files explicitly.

```powershell
git add -f .claude/agents/art/.claude/settings.local.json
git add -f .claude/agents/delivery_planner/.claude/settings.local.json
git add -f .claude/agents/design/.claude/settings.local.json
git add -f .claude/agents/dev/.claude/settings.local.json
git add -f .claude/agents/moderator/.claude/settings.local.json
git add -f .claude/agents/qa/.claude/settings.local.json
git add -f .claude/agents/quality/.claude/settings.local.json
git add -f .claude/agents/requirement_clarifier/.claude/settings.local.json
git add -f .claude/agents/reviewer/.claude/settings.local.json
git add -f .claude/agents/worker/.claude/settings.local.json
git add tests/test_claude_code_langfuse_hook.py
git commit -m "chore: wire Claude Code agents to Langfuse Stop hook"
```

---

### Task 5: Document Installation and Local Credentials

**Files:**
- Modify: `docs/agent-debugging.md`

- [ ] **Step 1: Add documentation**

Add this section to `docs/agent-debugging.md`:

```markdown
## Claude Code Agent Langfuse Tracing

Claude Code subagents under `.claude/agents/*` use a shared `Stop` hook at
`.claude/hooks/langfuse_hook.py`. Each agent's own
`.claude/settings.local.json` enables the hook with:

```json
"env": {
  "TRACE_TO_LANGFUSE": "true"
}
```

The shared script delegates to the globally installed
`douinc/langfuse-claudecode` hook. Install it once:

```powershell
curl.exe -fsSL https://raw.githubusercontent.com/douinc/langfuse-claudecode/main/install.sh | bash
```

For Windows shells without `bash`, manually install the hook in
`$HOME/.claude/hooks/langfuse-claudecode`:

```powershell
New-Item -ItemType Directory -Force "$HOME/.claude/hooks" | Out-Null
git clone https://github.com/douinc/langfuse-claudecode "$HOME/.claude/hooks/langfuse-claudecode"
uv sync --project "$HOME/.claude/hooks/langfuse-claudecode"
```

Set credentials in the shell before starting Claude Code:

```powershell
$env:LANGFUSE_PUBLIC_KEY = "pk-lf-..."
$env:LANGFUSE_SECRET_KEY = "sk-lf-..."
$env:LANGFUSE_BASE_URL = "https://cloud.langfuse.com"
```

Optional variables:

```powershell
$env:CC_LANGFUSE_USER_ID = "you@example.com"
$env:CC_LANGFUSE_ENVIRONMENT = "local"
$env:CC_LANGFUSE_DEBUG = "true"
```

Manual verification:

1. Open Claude Code from an agent directory, for example
   `.claude/agents/design`.
2. Send a short prompt.
3. Confirm Langfuse shows a Claude Code trace.
4. Check `host_cwd`, `CC_LANGFUSE_ENVIRONMENT`, or local hook logs to identify
   the agent role.

The hook fails open. If Langfuse is down or credentials are missing, Claude Code
continues normally and the hook prints a concise stderr message.
```

- [ ] **Step 2: Run documentation grep checks**

Run:

```powershell
rg -n "Claude Code Agent Langfuse Tracing|langfuse-claudecode|TRACE_TO_LANGFUSE" docs/agent-debugging.md
```

Expected: output includes the new section heading, upstream repository name, and `TRACE_TO_LANGFUSE`.

- [ ] **Step 3: Commit documentation**

```powershell
git add docs/agent-debugging.md
git commit -m "docs: document Claude Code Langfuse hook setup"
```

---

### Task 6: Final Verification

**Files:**
- Verify: `.claude/hooks/langfuse_hook.py`
- Verify: `.claude/agents/*/.claude/settings.local.json`
- Verify: `tests/test_claude_code_langfuse_hook.py`
- Verify: `docs/agent-debugging.md`

- [ ] **Step 1: Run focused tests**

Run:

```powershell
uv run pytest tests/test_claude_code_langfuse_hook.py -v
```

Expected: PASS.

- [ ] **Step 2: Validate all agent JSON settings**

Run:

```powershell
Get-ChildItem .claude\agents -Directory | ForEach-Object {
  $path = Join-Path $_.FullName ".claude\settings.local.json"
  Get-Content $path -Raw | ConvertFrom-Json | Out-Null
  Write-Output "ok $path"
}
```

Expected: ten `ok` lines, one for each agent.

- [ ] **Step 3: Smoke test disabled hook path**

Run:

```powershell
$env:TRACE_TO_LANGFUSE = "false"
'{"session_id":"manual"}' | uv run python .claude\hooks\langfuse_hook.py
```

Expected: command exits with code `0` and prints `Langfuse tracing disabled` to stderr.

- [ ] **Step 4: Smoke test missing credentials path**

Run:

```powershell
$env:TRACE_TO_LANGFUSE = "true"
Remove-Item Env:\LANGFUSE_PUBLIC_KEY -ErrorAction SilentlyContinue
Remove-Item Env:\LANGFUSE_SECRET_KEY -ErrorAction SilentlyContinue
'{"session_id":"manual"}' | uv run python .claude\hooks\langfuse_hook.py
```

Expected: command exits with code `0` and prints `Langfuse credentials missing` to stderr.

- [ ] **Step 5: Inspect git status**

Run:

```powershell
git status --short
```

Expected: only pre-existing user changes remain, such as unrelated `CLAUDE.md` or frontend edits. No uncommitted files from this implementation should remain.

---

## Implementation Notes

- Do not commit Langfuse keys.
- Do not edit `.claude/agents/*/CLAUDE.md`; the current request only affects hook wiring.
- The top-level `.claude/settings.local.json` remains unchanged in this plan.
- The upstream hook stores incremental state in `~/.claude/state/`, not in this repository.
- The wrapper sets `CC_LANGFUSE_AGENT_ROLE` for future compatibility. Current upstream behavior can still be identified through `host_cwd` and the derived default `CC_LANGFUSE_ENVIRONMENT`.
