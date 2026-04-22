# Project Agent Session Design

## Summary

Game Studio needs a thin project-level session layer so each managed agent can keep Claude Agent SDK context across a real project. Sessions are created only when the user explicitly starts a project or runs a kickoff meeting. The goal is not to build a thick chat product. The goal is to let workflows reuse the same per-agent Claude sessions, and to let the user debug an individual agent inside that project's real context.

## Goals

- Create long-lived Claude Agent SDK sessions per project and per agent.
- Initialize sessions only after an explicit kickoff action.
- Reuse those sessions from meeting and delivery workflows.
- Let users open a direct CLI debug channel into one agent's project session.
- Keep LangGraph state focused on business state, not full chat history.
- Rely on Claude Agent SDK session management instead of storing local conversation history.

## Non-Goals

- Do not build a full chat UI.
- Do not implement custom history storage or transcript replay.
- Do not put full conversation history in LangGraph state.
- Do not create sessions for every draft requirement.
- Do not add fallback sessions when kickoff has not happened.

## Managed Agents

The first version initializes sessions for:

- `moderator`
- `design`
- `dev`
- `qa`
- `quality`
- `art`
- `reviewer`

Each agent still uses its checked-in profile from `studio/agents/profiles/<agent>.yaml` and its Claude project root under `.claude/agents/<agent>`.

## User Flow

Before kickoff:

1. User creates or discusses a requirement.
2. The requirement can remain draft/designing/pending review.
3. No project agent sessions are created.

At kickoff:

1. User explicitly starts the project or starts a kickoff meeting.
2. System creates a project id if one does not already exist.
3. System creates or binds one Claude session per managed agent.
4. System runs the kickoff meeting graph using these sessions.
5. System saves meeting minutes and the project-agent session mapping.

After kickoff:

1. Design, delivery, QA, quality, and meeting workflows look up the agent session by `project_id + agent`.
2. Each agent call resumes or continues its own Claude session.
3. The user can directly debug an agent with the same project context.

Example debug command:

```powershell
uv run python -m studio.interfaces.cli agent chat --agent qa --project-id proj_123 --interactive
```

If the project was not kicked off or the agent session does not exist, the command fails with a clear error.

## Data Model

Add a persisted `ProjectAgentSession` record:

```json
{
  "project_id": "proj_123",
  "requirement_id": "req_123",
  "agent": "qa",
  "session_id": "claude-session-id",
  "status": "active",
  "created_at": "2026-04-22T00:00:00Z",
  "last_used_at": "2026-04-22T00:00:00Z"
}
```

Storage location:

```text
.studio-data/project_agent_sessions/<project_id>_<agent>.json
```

The registry stores only identifiers and metadata. It does not store message history.

## Session Registry

Introduce a small registry service responsible for:

- Creating session records during kickoff.
- Finding a session by `project_id + agent`.
- Updating `last_used_at` after an agent call.
- Rejecting missing sessions instead of silently creating ad hoc sessions.

The registry should not know agent prompts or business workflow details. It only maps project-agent pairs to Claude session ids.

## Claude SDK Usage

Structured workflow calls should continue to use the existing output schema validation, but pass the project session into the SDK options when available.

Interactive debug calls should use Claude Agent SDK's stateful session support rather than manually concatenating local history. The preferred path is `ClaudeSDKClient` for interactive sessions, because it is designed for multi-turn conversations. Single-turn debug can remain lightweight, but project-scoped interactive debug should reuse the stored session.

Relevant SDK fields:

- `session_id`
- `resume`
- `continue_conversation`
- `fork_session`

The implementation should choose the minimal SDK mode that preserves project context and works reliably with the current Claude CLI integration.

## Kickoff Meeting Integration

The kickoff action is the first workflow that consumes project sessions.

Suggested graph behavior:

1. `moderator_prepare` uses the `moderator` project session.
2. Agent opinion fan-out uses each attendee agent's project session.
3. `moderator_summarize` uses the same `moderator` project session.
4. `moderator_minutes` uses the same `moderator` project session.
5. Meeting minutes are saved as they are today.

The meeting graph should not create missing sessions implicitly. Kickoff orchestration creates them first, then the graph consumes them.

## CLI Debug Entry

Extend `agent chat` with project session support:

```powershell
uv run python -m studio.interfaces.cli agent chat --agent qa --project-id proj_123 --interactive
```

Rules:

- `--project-id` means use the stored project session.
- Missing session is an error.
- `--interactive` uses SDK session continuity.
- `--verbose` prints profile path, Claude project root, project id, and session id.
- Without `--project-id`, the command remains a temporary profile/debug chat.

This keeps the debug entry thin while making it useful for real project diagnosis.

## Error Handling

- Missing project session: fail with `project agent session not found`.
- Missing profile: fail with the existing strict profile error.
- Missing Claude root: fail with the existing strict profile error.
- Claude SDK failure: fail clearly; do not fallback in debug mode.
- Workflow structured output failure: preserve existing workflow fallback policy where applicable, but record enough telemetry/logging to identify the session and agent involved.

## Testing

Required tests:

- Session registry creates one record per managed agent during kickoff.
- Registry rejects missing `project_id + agent` lookups.
- Meeting graph uses existing project sessions instead of creating ad hoc sessions.
- `agent chat --project-id --interactive` passes the expected session id into the SDK client.
- `agent chat --project-id` fails clearly when kickoff has not created a session.
- Existing profile-driven structured workflow tests remain green.

## Acceptance Criteria

- A user can explicitly kickoff a project and create project-agent sessions.
- Each managed agent has a persisted session id for that project.
- Kickoff meeting uses those sessions.
- Later workflows can reuse those sessions.
- The user can enter a single agent's project session from CLI for debugging.
- The system does not maintain its own chat history.
- No sessions are created before explicit kickoff.
