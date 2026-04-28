# Claude Code Agent Langfuse Hook Design

## Context

Game Studio has two distinct Claude observability surfaces:

- Python runtime agents in `studio/agents/*`, which already have a Langfuse
  integration through the application runtime.
- Claude Code subagents under `.claude/agents/*`, each with its own
  `CLAUDE.md` and project-local `.claude/settings.local.json`.

This design covers only the Claude Code subagents. The goal is to add a
Claude Code `Stop` hook based on `douinc/langfuse-claudecode` so each subagent
session can be traced in Langfuse without changing the agent prompts or the
Python runtime telemetry.

Relevant references:

- `douinc/langfuse-claudecode`: https://github.com/douinc/langfuse-claudecode
- Langfuse Claude Code integration:
  https://langfuse.com/integrations/other/claude-code
- Claude Code hooks:
  https://code.claude.com/docs/en/hooks
- Claude Code settings:
  https://code.claude.com/docs/en/settings

## Goals

- Enable Langfuse tracing for every Claude Code subagent in `.claude/agents/*`.
- Keep each subagent's own `.claude/settings.local.json` as the place that
  declares its hook behavior.
- Maintain one shared hook implementation instead of copying hook code into
  every agent.
- Avoid committing Langfuse secrets to the repository.
- Capture enough metadata to distinguish agent role, project, session, cwd,
  and transcript source in Langfuse.
- Keep hook failures non-blocking so a tracing outage does not interrupt
  Claude Code sessions.

## Non-Goals

- Replacing the existing Python runtime Langfuse integration.
- Editing the text of agent `CLAUDE.md` prompts.
- Making Langfuse required for local agent use.
- Building a custom Langfuse dashboard in this phase.
- Storing Langfuse public or secret keys in committed files.

## Recommended Approach

Use a repository-local shared hook script and reference it from each agent's
project-local Claude settings.

The shape is:

```text
.claude/
  hooks/
    langfuse_hook.py
  agents/
    design/
      CLAUDE.md
      .claude/
        settings.local.json
    dev/
      CLAUDE.md
      .claude/
        settings.local.json
    ...
```

Each agent keeps its own settings file, but the `Stop` hook command points to
the shared script:

```json
{
  "permissions": {
    "allow": ["Bash(*)", "Edit(*)"]
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
            "command": "uv run python \"$CLAUDE_PROJECT_DIR/../../hooks/langfuse_hook.py\""
          }
        ]
      }
    ]
  }
}
```

The command path is resolved from the Claude Code project root for each agent.
For an agent project root such as `.claude/agents/design`,
`$CLAUDE_PROJECT_DIR/../../hooks/langfuse_hook.py` resolves to
`.claude/hooks/langfuse_hook.py`.

## Configuration

Committed agent settings should only include non-secret control variables:

```json
"env": {
  "TRACE_TO_LANGFUSE": "true"
}
```

Langfuse credentials should come from the user's environment or an uncommitted
local settings file:

```powershell
$env:LANGFUSE_PUBLIC_KEY = "pk-lf-..."
$env:LANGFUSE_SECRET_KEY = "sk-lf-..."
$env:LANGFUSE_BASE_URL = "https://cloud.langfuse.com"
```

`LANGFUSE_BASE_URL` should also support self-hosted Langfuse URLs. If the
external `langfuse-claudecode` hook expects `LANGFUSE_HOST` instead of
`LANGFUSE_BASE_URL`, the shared wrapper should normalize both names before
delegating.

## Hook Script Behavior

The shared hook script should:

1. Read the JSON hook payload from standard input.
2. Exit successfully without sending anything when `TRACE_TO_LANGFUSE` is not
   truthy.
3. Determine the agent role from `CLAUDE_PROJECT_DIR`, for example `design`
   from `.claude/agents/design`.
4. Normalize Langfuse environment variables:
   - accept `LANGFUSE_BASE_URL`
   - accept `LANGFUSE_HOST`
   - provide whichever name the underlying library needs
5. Delegate transcript parsing and Langfuse upload to the
   `langfuse-claudecode` implementation.
6. Add Game Studio metadata when supported:
   - `agent_role`
   - `claude_project_dir`
   - `repo_root`
   - `hook_source`
   - `session_id`
7. Catch all exceptions, write a concise diagnostic to stderr, and return zero
   unless a local debug flag asks for hard failures.

The wrapper should be intentionally thin. We should not fork or rewrite the
transcript parser unless the upstream package cannot be used cleanly.

## Agent Coverage

The hook should be added to every existing agent settings file:

- `.claude/agents/art/.claude/settings.local.json`
- `.claude/agents/delivery_planner/.claude/settings.local.json`
- `.claude/agents/design/.claude/settings.local.json`
- `.claude/agents/dev/.claude/settings.local.json`
- `.claude/agents/moderator/.claude/settings.local.json`
- `.claude/agents/qa/.claude/settings.local.json`
- `.claude/agents/quality/.claude/settings.local.json`
- `.claude/agents/requirement_clarifier/.claude/settings.local.json`
- `.claude/agents/reviewer/.claude/settings.local.json`
- `.claude/agents/worker/.claude/settings.local.json`

The top-level `.claude/settings.local.json` can remain unchanged for this
phase. It may be instrumented later if top-level Claude Code sessions also need
Langfuse tracing.

## Data Flow

1. A user runs a Claude Code session inside one agent project directory.
2. Claude Code completes a response.
3. Claude Code invokes the agent's `Stop` hook.
4. The hook receives the stop payload on stdin.
5. The shared hook script reads the payload and transcript reference.
6. `langfuse-claudecode` parses the transcript.
7. The script sends a Langfuse trace with session, messages, tool calls, and
   metadata.
8. The hook exits zero so Claude Code remains unaffected.

## Error Handling

- Missing Langfuse keys: log one concise warning and exit zero.
- Missing transcript path: log one concise warning and exit zero.
- Langfuse network/API failure: log one concise warning and exit zero.
- Invalid hook payload JSON: log one concise warning and exit zero.
- Unsupported upstream package version: log the version/problem and exit zero.

This keeps observability best-effort. Agent work should continue even when the
telemetry path is unavailable.

## Testing Strategy

Automated checks:

- Validate all touched `settings.local.json` files are valid JSON.
- Verify every agent settings file contains a `Stop` hook command that resolves
  to `.claude/hooks/langfuse_hook.py`.
- Unit test the shared wrapper's agent role detection.
- Unit test environment normalization for `LANGFUSE_BASE_URL` and
  `LANGFUSE_HOST`.
- Unit test missing credentials and malformed stdin exit successfully.

Manual checks:

- Set Langfuse credentials in the shell.
- Start Claude Code from one agent directory, for example
  `.claude/agents/design`.
- Run a short prompt.
- Confirm a trace appears in Langfuse with `agent_role=design`.
- Repeat for a second agent, for example `dev`, to confirm role separation.

## Rollout

1. Add the shared hook script under `.claude/hooks/langfuse_hook.py`.
2. Add minimal tests for wrapper behavior and JSON settings validation.
3. Update each agent `.claude/settings.local.json` to include
   `TRACE_TO_LANGFUSE=true` and the shared `Stop` hook.
4. Document local credential setup in README or `docs/agent-debugging.md`.
5. Manually verify with two representative agents before relying on the data.

## Open Implementation Notes

- Prefer using the upstream package directly if it exposes a CLI or importable
  entrypoint.
- If the upstream repository is script-only, vendor a small wrapper around the
  script rather than duplicating its parsing logic.
- Keep committed settings free of secrets.
- Keep hook execution fast and best-effort.
