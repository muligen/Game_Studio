# Meeting Transcript And Debug View Design

## Goal

Make the kickoff meeting process inspectable to product users and debuggable to builders.

After a meeting completes, users should be able to:

1. See what each participating agent said during the meeting in a readable chat-style transcript.
2. Inspect the underlying prompt and raw reply for each meeting step when deeper debugging is needed.

## Problem

The current system only persists final meeting artifacts well enough for workflow continuation:

- final meeting minutes
- aggregated agent opinions
- consensus/conflict summaries
- pending user decisions

What is missing is the actual discussion trace.

From a user perspective, this makes the meeting feel opaque:

- "Which agents participated?"
- "What did `design` actually propose?"
- "What did `qa` object to?"
- "Did `moderator` summarize fairly?"

From a debugging perspective, this is also insufficient:

- we cannot easily see the per-agent input prompt
- we cannot easily compare raw reply vs extracted structured payload
- we cannot explain bad meeting quality without manually digging through logs or replaying agents

## Product Decision

The system should support two layers of meeting visibility:

### 1. Default Layer: Chat-Style Meeting Transcript

This is the primary user-facing experience.

Users should see a chronological transcript that looks like a team chat rather than a raw debug dump.

Each transcript entry should include:

- `speaker`
- `phase`
- rendered message content
- timestamp or sequence order

This answers the main user question:

"What did the meeting actually discuss?"

### 2. Debug Layer: Expand For Prompt / Raw Reply / Parsed Output

This is a secondary debugging layer.

Each transcript entry should optionally expand to show:

- input prompt sent to the model
- raw LLM reply
- parsed structured payload if applicable

This answers the builder question:

"Was the problem caused by the prompt, the model reply, or the parser?"

## Scope

In scope:

- persist per-step meeting transcript events
- store enough metadata to reconstruct the discussion timeline
- expose a transcript API
- render a chat-style transcript UI
- allow per-entry prompt/reply expansion

Out of scope:

- live streaming transcript while the meeting is still running
- node-by-node LangGraph visualization in the web app
- redesigning meeting prompts
- changing the meeting graph flow itself

## Current System Constraints

The current meeting workflow already has natural capture points:

- `moderator_prepare`
- `agent_opinion` for each participating role
- `moderator_summarize`
- `moderator_discussion`
- `moderator_minutes`

Each agent wrapper already exposes `consume_llm_log_entry()` or equivalent prompt/reply debug records through `ClaudeRoleAdapter.consume_debug_record()`.

That means we do not need to invent a new prompt capture mechanism from scratch. We mainly need to:

1. collect those records at graph execution time
2. normalize them into transcript events
3. persist them
4. expose them in the API/UI

## Data Model

Add a new persisted artifact for meeting transcripts.

### `MeetingTranscript`

One record per meeting:

```json
{
  "id": "transcript_<meeting_id>",
  "meeting_id": "meeting_xxx",
  "requirement_id": "req_xxx",
  "project_id": "proj_xxx",
  "events": [...]
}
```

### `MeetingTranscriptEvent`

One record per meaningful model interaction:

```json
{
  "id": "evt_xxx",
  "meeting_id": "meeting_xxx",
  "sequence": 3,
  "phase": "agent_opinion",
  "speaker": "design",
  "event_type": "llm_exchange",
  "summary": "Design agent proposed a browser Snake MVP with classic rules.",
  "prompt": "...full prompt...",
  "raw_reply": "...raw text reply or structured output serialization...",
  "parsed_payload": {
    "summary": "...",
    "proposals": ["..."]
  },
  "created_at": "2026-04-23T..."
}
```

### Event Semantics

Use `phase` values aligned with the graph:

- `moderator_prepare`
- `agent_opinion`
- `moderator_summary`
- `moderator_discussion`
- `moderator_minutes`

Use `speaker` values aligned with the real role that produced the model output:

- `moderator`
- `design`
- `dev`
- `qa`
- `art`

`summary` should be a short display-friendly string extracted from parsed payload when possible.

## Backend Design

### 1. Persist Transcript Events During Meeting Graph Execution

Update meeting graph nodes so that after each agent/moderator model call:

- retrieve the latest debug record from the agent
- normalize it into a transcript event
- append it to in-memory meeting state

After `moderator_minutes` succeeds, persist the accumulated transcript to workspace storage.

### 2. Do Not Block Meeting Completion On Transcript Failure

Transcript capture is important but secondary to core meeting completion.

If transcript persistence fails:

- do not fail the entire meeting
- add a lightweight warning in logs or supplementary metadata

Meeting completion should remain the primary success path.

### 3. API Endpoints

Add:

- `GET /api/meetings/{meeting_id}/transcript`

Optional later:

- `GET /api/meetings/{meeting_id}/transcript/events/{event_id}`

The first iteration only needs the full transcript endpoint.

### 4. Storage Layout

Persist transcripts under:

- `.studio-data/meeting_transcripts/`

This keeps transcript data adjacent to meeting minutes while remaining a separate artifact.

## Frontend Design

### 1. Meeting Transcript Entry Point

Add a visible entry from the meeting result state:

- `View Meeting Transcript`

Possible entry points:

- kickoff completion result panel
- delivery gate / meeting summary panel
- future meeting detail page

First iteration can start with the kickoff completion dialog and later be reused elsewhere.

### 2. Transcript View Layout

Render as a chat-like timeline.

Each event card should show:

- speaker badge
- phase label
- short message body derived from `summary` or parsed payload

Example:

```text
[design] agent_opinion
I propose a browser-based Snake MVP with classic movement, growth, collision, and scoring.
```

When expanded, show:

- Prompt
- Raw Reply
- Parsed Output

### 3. Default Readability Rules

Default transcript should optimize for readability:

- show concise summary first
- hide raw prompt/reply behind disclosure
- pretty-print parsed JSON

Users should not have to read raw prompts unless they want to debug.

## Event Normalization Rules

Because different agents return different payload shapes, we need a small normalization layer.

### Moderator Events

Use:

- `agenda` / `focus_questions` for prepare
- `consensus_points` / `conflict_points` for summarize
- `supplementary` / `unresolved_conflicts` for discussion
- `summary` / `decisions` / `pending_user_decisions` for minutes

### Opinion Events

Use:

- `summary` as the primary body
- `proposals` as supporting bullets
- `risks` / `open_questions` as supporting metadata

### Raw Reply Storage

If reply is structured JSON, store:

- `raw_reply` as original serialized reply when available
- `parsed_payload` as normalized parsed object

If only parsed output is available, store that and leave `raw_reply` nullable.

## Debugging Benefits

This spec directly supports several recurring debugging needs:

- explain why a meeting produced weak decisions
- compare what `qa` objected to versus what `moderator` summarized
- inspect whether `design` or `dev` misunderstood the clarified requirement
- audit which conflicts turned into decision gates
- distinguish bad prompt design from parsing problems

## Acceptance Criteria

1. After a meeting completes, the system persists a transcript artifact separate from final meeting minutes.
2. The transcript contains one event for each major LLM exchange in the meeting graph.
3. Each event records at least `speaker`, `phase`, `summary`, and ordered sequence.
4. Prompt and raw reply are available for debugging when capture exists.
5. Users can open a transcript view from the product UI and read the meeting as a chat-style conversation.
6. Users can expand an event to inspect prompt and raw reply details.
7. Transcript persistence failure does not fail the overall meeting workflow.

## Files Likely To Change

Backend:

- `studio/runtime/graph.py`
- `studio/agents/moderator.py`
- `studio/agents/design.py`
- `studio/agents/dev.py`
- `studio/agents/qa.py`
- `studio/storage/workspace.py`
- new transcript schema file under `studio/schemas/`
- new meeting transcript API route or extension to `studio/api/routes/meetings.py`

Frontend:

- kickoff result / meeting result UI component
- new transcript viewer component
- `web/src/lib/api.ts`

Tests:

- meeting graph tests
- transcript persistence tests
- transcript API tests

## Recommended Implementation Order

1. Add transcript schema and storage repository
2. Capture per-node prompt/reply events in meeting graph
3. Persist transcript on successful meeting completion
4. Add transcript API
5. Add chat-style transcript viewer UI
6. Add per-event prompt/reply expansion

## Notes

This is intentionally not a live observability system.

The first version should optimize for:

- post-run inspectability
- readable meeting transparency
- prompt/reply debugging

Live streaming and richer LangGraph visual debugging can be layered on later if needed.
