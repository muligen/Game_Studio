# Agent Debugging Guide

This guide collects the commands for debugging one agent directly from the CLI.

## When To Use This

Use `agent chat` when you want to verify an agent's profile, prompt, Claude context directory, or project-specific memory without running the full workflow again.

Supported agents:

- `moderator`
- `design`
- `dev`
- `qa`
- `quality`
- `art`
- `reviewer`
- `worker`

## Temporary Agent Debugging

Use this when you only want to check whether an agent profile works. This does not use a project session.

```powershell
uv run python -m studio.interfaces.cli agent chat --agent reviewer --message "Briefly explain your role." --verbose
```

`--verbose` prints:

- agent name
- profile path
- Claude project root
- system prompt

## Project Session Debugging

Use this after project kickoff. This enters the agent's project-specific Claude session.

First create or reuse a kicked off project:

```powershell
uv run python -m studio.interfaces.cli project kickoff --workspace .runtime-data/project-session-demo --requirement-id req_xxxxxxxx --user-intent "Run a kickoff meeting for this project."
```

The command prints a project id:

```text
proj_xxxxxxxx kickoff_complete
```

Then debug one agent in that project:

```powershell
uv run python -m studio.interfaces.cli agent chat --agent qa --project-id proj_xxxxxxxx --workspace .runtime-data/project-session-demo --message "What do you know about this project so far?" --verbose
```

## Continuous Conversation

Use `--interactive` for an ongoing debug conversation.

```powershell
uv run python -m studio.interfaces.cli agent chat --agent qa --project-id proj_xxxxxxxx --workspace .runtime-data/project-session-demo --interactive --verbose
```

Then type questions at the prompt:

```text
qa> What do you know about this project so far?
qa> If you owned acceptance testing, which risks would you test first?
```

Exit with:

```text
quit
```

or:

```text
exit
```

## Check Session Files

Project agent sessions are stored under the workspace:

```powershell
Get-ChildItem .runtime-data/project-session-demo/.studio-data/project_agent_sessions
```

Each file maps a project and agent to a Claude session id:

```powershell
Get-Content -Raw .runtime-data/project-session-demo/.studio-data/project_agent_sessions/proj_xxxxxxxx_qa.json
```

## Common Errors

### `--workspace is required when --project-id is set`

You used `--project-id` without telling the CLI which workspace stores the session files.

Fix:

```powershell
uv run python -m studio.interfaces.cli agent chat --agent qa --project-id proj_xxxxxxxx --workspace .runtime-data/project-session-demo --message "hello"
```

### `project agent session not found`

The project was not kicked off, the project id is wrong, or that agent has no session record.

Check:

```powershell
Get-ChildItem .runtime-data/project-session-demo/.studio-data/project_agent_sessions
```

### `claude_disabled`

Claude is disabled in `.env`.

Check `.env`:

```env
GAME_STUDIO_CLAUDE_ENABLED=true
ANTHROPIC_API_KEY=...
```

### Agent Has No Project Context

Make sure you are using `--project-id` and `--workspace`. Without them, `agent chat` starts temporary profile debugging instead of entering the project session.

## Quick Recipes

Debug reviewer profile only:

```powershell
uv run python -m studio.interfaces.cli agent chat --agent reviewer --message "Explain your role." --verbose
```

Debug QA in a project:

```powershell
uv run python -m studio.interfaces.cli agent chat --agent qa --project-id proj_xxxxxxxx --workspace .runtime-data/project-session-demo --message "How would you accept-test the current project?" --verbose
```

Talk continuously with design agent:

```powershell
uv run python -m studio.interfaces.cli agent chat --agent design --project-id proj_xxxxxxxx --workspace .runtime-data/project-session-demo --interactive --verbose
```
