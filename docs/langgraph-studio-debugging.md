# LangGraph Studio Debugging

This guide is a quick reminder for debugging Game Studio graphs in LangGraph Studio.

## Start Studio

From the repo root, prefer disabling hot reload while debugging long-running Claude nodes:

```powershell
$env:PYTHONIOENCODING='utf-8'
uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.12 langgraph dev --no-reload
```

If `langgraph` is already installed locally, this also works:

```powershell
langgraph dev --no-reload
```

Open the local Studio URL printed by the command.

`--no-reload` is important for this project. LangGraph dev writes checkpoint/store files under `.langgraph_api`, and graph runs write workspace files under `.runtime-data` or `.studio-data`. With hot reload enabled, `watchfiles` may detect those generated files and restart background workers while a node is waiting for Claude. That usually appears as `asyncio.exceptions.CancelledError`, often while `moderator_prepare`, `agent_opinion`, or `moderator_minutes` is still running.

## Available Graphs

Graphs are registered in `langgraph.json`.

- `game_studio_demo`: demo planner -> worker -> reviewer flow
- `studio_design_workflow`: design workflow
- `studio_delivery_workflow`: delivery workflow
- `studio_meeting_workflow`: multi-agent kickoff meeting graph

For meeting debugging, choose `studio_meeting_workflow`.

## Prepare Meeting Workspace

Create a requirement first. Example:

```powershell
$ws = ".runtime-data/langgraph-meeting-acceptance"

uv run python -m studio.interfaces.cli requirement create `
  --workspace $ws `
  --title "Turn-based combat kickoff acceptance"
```

Copy the printed requirement id, for example `req_8fab476c`.

The graph input expects `workspace_root` to point at the internal `.studio-data` directory:

```text
F:\projs\Game_Studio\.runtime-data\langgraph-meeting-acceptance\.studio-data
```

## Meeting Graph Input

Paste this into Studio when invoking `studio_meeting_workflow`.

Update `requirement_id` if your generated id is different.

```json
{
  "workspace_root": "F:\\projs\\Game_Studio\\.runtime-data\\langgraph-meeting-acceptance\\.studio-data",
  "project_root": "F:\\projs\\Game_Studio",
  "requirement_id": "req_8fab476c",
  "user_intent": "Run a kickoff meeting for a turn-based combat system. Focus on MVP scope, combat pacing, implementation boundaries, QA acceptance criteria, and known conflicts.",
  "meeting_context": {
    "summary": "The user wants a lightweight but strategic 3v3 turn-based combat system with attack, skill, defend, turn order, resource use, and battle result resolution.",
    "requirement": {
      "id": "req_8fab476c",
      "title": "Turn-based combat kickoff acceptance",
      "status": "draft",
      "priority": "medium"
    },
    "design_context": {
      "core_loop": "The player selects unit actions, uses attack, skill, or defend, defeats all enemies, and reaches a win/loss result.",
      "mvp_scope": [
        "3v3 turn-based combat",
        "basic deterministic turn order",
        "attack, skill, defend",
        "battle win/loss resolution"
      ],
      "out_of_scope": [
        "complex equipment affixes",
        "multiplayer networking",
        "large level editor"
      ]
    },
    "goals": [
      "Confirm whether the MVP needs an action timeline",
      "Confirm whether elemental counters belong in the first version",
      "Confirm measurable balance and QA acceptance criteria",
      "Confirm the smallest dev-deliverable scope"
    ],
    "constraints": [
      "First version should fit within two weeks",
      "Playable combat loop is higher priority than UI polish",
      "Avoid excessive UI and balance complexity"
    ],
    "open_questions": [
      "Is an action timeline required for MVP, or can deterministic turn order ship first?",
      "Do elemental counters significantly increase QA combination testing cost?",
      "Should skill balance acceptance use fixed sample battles or win-rate ranges?"
    ],
    "known_conflicts": [
      "Design wants action timeline and elemental counters in MVP.",
      "Dev wants to defer elemental counters and keep only deterministic turn order.",
      "QA needs measurable acceptance criteria before approving combat balance."
    ],
    "validated_attendees": [
      "design",
      "moderator",
      "producer",
      "dev",
      "qa",
      "design"
    ]
  }
}
```

## Fast Minimal Input

Use this when you only want to check whether the graph can run without waiting on a large prompt:

```json
{
  "workspace_root": "F:\\projs\\Game_Studio\\.runtime-data\\langgraph-meeting-acceptance\\.studio-data",
  "project_root": "F:\\projs\\Game_Studio",
  "requirement_id": "req_8fab476c",
  "user_intent": "Run a kickoff meeting for a small turn-based combat MVP.",
  "meeting_context": {
    "summary": "Small 3v3 turn-based combat MVP.",
    "goals": ["Confirm MVP scope"],
    "constraints": ["Two-week first version"],
    "open_questions": ["Whether elemental counters are in MVP"],
    "validated_attendees": ["design"]
  }
}
```

## What To Inspect

Use Studio's node state/output panels after each node.

- After `moderator_prepare`, inspect `attendees`.
- Expected attendee result: only registered participant agents remain, usually `design`, `dev`, `qa`.
- `moderator` and `producer` should be filtered out because they are not participant agents in the meeting fan-out.
- Duplicate `design` should be removed.
- After `agent_opinion`, inspect `opinions`.
- Expected opinions keys should match the filtered attendees.
- After `moderator_summarize`, inspect `conflict_resolution_needed`.
- If it is truthy/non-empty, the next node should be `moderator_discussion`.
- After `moderator_discussion`, inspect `supplementary` and `unresolved_conflicts`.
- After `moderator_minutes`, inspect `minutes.pending_user_decisions` and `minutes.supplementary`.

## Saved Output

Meeting minutes are saved under:

```text
<workspace>/.studio-data/meetings/
```

For the example workspace:

```powershell
Get-ChildItem .runtime-data/langgraph-meeting-acceptance/.studio-data/meetings
Get-Content (Get-ChildItem .runtime-data/langgraph-meeting-acceptance/.studio-data/meetings/*.json | Select-Object -First 1).FullName
```

## LLM Prompt Logs

Workflow LLM prompt/reply logs are stored when the graph path records them.

For demo runtime logs:

```text
<workspace>/logs/
```

For graph-specific or workflow-specific logs, check the workspace runtime folders first:

```powershell
Get-ChildItem .runtime-data -Recurse -Filter *.json | Where-Object { $_.FullName -match "llm|log" } | Select-Object FullName
```

If a node used deterministic fallback because Claude failed, the LLM call may not have produced a useful prompt/reply log. In Studio, inspect node output for `fallback_used` or missing LLM telemetry.

## Common Problems

### `watchfiles` Keeps Printing `changes detected`

This is the LangGraph dev file watcher. It may print logs like:

```text
10 changes detected [watchfiles.main]
1 change detected [watchfiles.main]
```

In this project, those changes are often generated by LangGraph itself:

```text
.langgraph_api/.langgraph_checkpoint.*.pckl
.langgraph_api/store.pckl
.runtime-data/**/.studio-data/meetings/*.json
.runtime-data/**/.studio-data/project_agent_sessions/*.json
```

If hot reload is enabled, these generated files can cause worker shutdown/reload during a long Claude call. The symptom is usually:

```text
Background run failed, will retry.
asyncio.exceptions.CancelledError
```

Use `--no-reload` while debugging graphs. If `CancelledError` still appears with `--no-reload`, then investigate the node itself. Without `--no-reload`, first assume hot reload interrupted the run.

### `moderator_prepare` Is Slow

`moderator_prepare` runs only one agent: `ModeratorAgent`.

It calls Claude with:

- moderator system prompt
- `moderator_prepare` JSON output schema
- `goal.prompt`
- `requirement_id`
- full `meeting_context`

It can be slow because Claude Code CLI may cold-start, structured JSON output takes longer than chat, and large `meeting_context` objects increase prompt size.

If Studio says `requirement_id` cannot be loaded, check that `workspace_root` points to `.studio-data`, not the outer workspace directory.

If `moderator_discussion` does not run, inspect `moderator_summarize.conflict_resolution_needed`. The graph only enters the second discussion round when that value is truthy.

If all unknown attendees disappear and the graph still runs `design/dev/qa`, that is expected. Empty attendee validation falls back to the default supported attendees.

## Project-Scoped Agent Debugging

If you want project-scoped Claude sessions, initialize through:

```powershell
uv run python -m studio.interfaces.cli project kickoff `
  --workspace .runtime-data/project-session-demo `
  --requirement-id <req_id> `
  --user-intent "Run a kickoff meeting for this project."
```

Then debug an individual agent with:

```powershell
uv run python -m studio.interfaces.cli agent chat `
  --agent design `
  --workspace .runtime-data/project-session-demo `
  --project-id <project_id> `
  --message "What was my responsibility in the kickoff meeting?" `
  --verbose
```
