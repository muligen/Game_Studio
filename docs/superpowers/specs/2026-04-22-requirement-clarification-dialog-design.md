# Requirement Clarification Dialog Design

## Summary

Add a web dialog where the user can discuss a draft requirement with a dedicated requirement-clarification agent before kickoff. The dialog turns natural conversation into a structured `meeting_context`, shows the user what has been understood, and starts the kickoff meeting only when enough context has been collected.

This closes the current gap between the frontend user discussion and `studio_meeting_workflow`, which already accepts `meeting_context` but currently requires callers to construct it manually.

## Problem

The intended flow is:

1. User explains a game feature or system idea.
2. An agent asks follow-up questions until the requirement is clear.
3. The system starts a kickoff meeting with all relevant agents using that detailed context.

Current behavior:

- The web UI can create a requirement with only a title.
- `project kickoff` can create project-agent sessions and run Meeting Graph.
- Meeting Graph can consume `meeting_context`, filter attendees, and run conflict discussion.
- There is no frontend path that produces `meeting_context`.
- Users must manually craft graph input to debug or validate the meeting context path.

## Goals

- Add a web dialog for clarifying a requirement before kickoff.
- Let the user chat with one requirement-clarification agent.
- Persist the conversation and structured draft context in workspace storage.
- Show a live structured context preview: summary, goals, constraints, open questions, acceptance criteria, risks, references, and attendees.
- Require a valid structured `meeting_context` before starting kickoff from the web UI.
- Start kickoff from the dialog and pass `meeting_context` into Meeting Graph.
- Keep the feature thin: no custom long-term chat memory system, no full product-management suite.

## Non-Goals

- Do not build a general multi-agent chat product.
- Do not store or replay full Claude SDK history beyond the local clarification transcript needed for audit/debug.
- Do not replace the existing requirement board.
- Do not run the full Meeting Graph on every chat turn.
- Do not create project-agent sessions before the user explicitly starts kickoff.
- Do not silently fallback to placeholder requirement context if the clarification agent fails.

## Recommended Approach

Use a thin "clarification session" layer:

- Frontend opens a modal from the requirement board.
- Backend creates or resumes a `RequirementClarificationSession`.
- Each user message is sent to a strict clarification agent.
- The agent returns both a conversational reply and a structured context draft.
- The frontend displays the reply and a context preview.
- The user clicks `Start Kickoff` when required context fields are complete.
- Backend creates project-agent sessions, invokes Meeting Graph with `meeting_context`, saves meeting minutes, and returns `project_id`.

This approach keeps the conversation feature focused and directly serves Meeting Graph.

## Alternatives Considered

### Option 1: Form-Only Clarification

Use a long structured form for summary, goals, constraints, risks, and acceptance criteria.

Pros:

- Easy to implement.
- Deterministic validation.
- No LLM failure mode.

Cons:

- Does not match the desired "talk to an agent" workflow.
- More effort for the user.
- Does not help uncover missing requirement details.

### Option 2: Full Project Chat System

Build a persistent project chat with multiple agents, session tabs, transcript search, and manual agent selection.

Pros:

- Powerful long-term direction.
- Could cover requirement clarification, debugging, and project communication.

Cons:

- Too large for this feature.
- Risks duplicating Claude Agent SDK session management.
- Delays the immediate Meeting Graph integration.

### Option 3: Thin Clarification Dialog

Build a focused dialog that produces `meeting_context` and starts kickoff.

Pros:

- Directly solves the current missing link.
- Small enough for one branch.
- Keeps LangGraph state clean.
- Reuses the existing Meeting Graph and project session model.

Cons:

- Not a full chat product.
- Requires a new structured LLM contract for the clarification agent.

Recommendation: Option 3.

## User Flow

### Entry Points

On the Requirements Board:

- Each draft requirement card gets a `Clarify` action.
- The create requirement dialog can optionally add a `Create & Clarify` path, but this is secondary.

The first implementation should focus on existing draft requirements. This avoids mixing requirement creation with clarification complexity.

### Dialog Flow

1. User clicks `Clarify` on a draft requirement.
2. Dialog opens with the requirement title and current status.
3. Backend creates or resumes a clarification session for that requirement.
4. User sends a message describing the feature.
5. Agent replies with one focused follow-up question or a confirmation.
6. Agent also returns a structured draft `meeting_context`.
7. UI updates a right-side "Context Preview" panel.
8. Required fields show checkmarks when complete.
9. `Start Kickoff Meeting` is disabled until required fields are present.
10. User starts kickoff.
11. Backend creates project-agent sessions and runs Meeting Graph with the approved `meeting_context`.
12. Dialog shows `project_id`, kickoff status, and link/summary for saved meeting minutes.

## Required Context Fields

The kickoff button should require these fields:

- `summary`: concise feature/system summary.
- `goals`: at least one goal.
- `constraints`: can be empty only if the agent explicitly records `"No constraints identified yet."`.
- `open_questions`: can be empty only if the agent explicitly records no open questions.
- `acceptance_criteria`: at least one testable acceptance criterion.
- `risks`: at least one risk or `"No major risks identified yet."`.
- `validated_attendees`: subset of supported meeting participants.

Supported attendees:

- `design`
- `art`
- `dev`
- `qa`

Unknown attendees must be rejected by the API validation before kickoff, not silently passed through.

## Data Model

Add `RequirementClarificationSession`.

Storage:

```text
.studio-data/requirement_clarifications/<session_id>.json
```

Example:

```json
{
  "id": "clar_req_123",
  "requirement_id": "req_123",
  "status": "collecting",
  "messages": [
    {
      "role": "user",
      "content": "I want a turn-based combat system.",
      "created_at": "2026-04-22T12:00:00Z"
    },
    {
      "role": "assistant",
      "content": "Should the MVP include elemental counters?",
      "created_at": "2026-04-22T12:00:05Z"
    }
  ],
  "meeting_context": {
    "summary": "A lightweight turn-based combat system.",
    "goals": ["Define MVP combat loop"],
    "constraints": ["Keep first version small"],
    "open_questions": ["Whether elemental counters are in MVP"],
    "acceptance_criteria": ["A sample 3v3 battle can complete with win/loss result"],
    "risks": ["Scope can grow if counters and complex UI are included"],
    "references": [],
    "validated_attendees": ["design", "dev", "qa"]
  },
  "readiness": {
    "ready": false,
    "missing_fields": ["acceptance_criteria"],
    "notes": ["Need at least one measurable acceptance criterion."]
  },
  "project_id": null,
  "created_at": "2026-04-22T12:00:00Z",
  "updated_at": "2026-04-22T12:00:05Z"
}
```

Statuses:

- `collecting`: user and agent are still clarifying.
- `ready`: structured context passes validation.
- `kickoff_started`: kickoff has created project sessions and invoked Meeting Graph.
- `completed`: kickoff completed and meeting minutes were saved.
- `failed`: last operation failed and needs user retry.

## Agent Contract

Add a requirement clarification role, preferably named `requirement_clarifier`.

The role should be profile-backed and strict, matching the existing agent configuration direction.

Possible profile:

```text
studio/agents/profiles/requirement_clarifier.yaml
```

The clarification agent must return structured JSON:

```json
{
  "reply": "One concise follow-up question or confirmation for the user.",
  "meeting_context": {
    "summary": "...",
    "goals": ["..."],
    "constraints": ["..."],
    "open_questions": ["..."],
    "acceptance_criteria": ["..."],
    "risks": ["..."],
    "references": ["..."],
    "validated_attendees": ["design", "dev", "qa"]
  },
  "readiness": {
    "ready": false,
    "missing_fields": ["acceptance_criteria"],
    "notes": ["Need measurable success criteria."]
  }
}
```

Behavior rules:

- Ask one focused question at a time.
- Prefer concrete acceptance criteria over vague statements.
- Keep scope small enough for kickoff.
- Do not invent user decisions.
- If information is missing, mark it in `readiness.missing_fields`.
- Do not return unsupported attendees.
- Do not fallback to fake context if Claude fails.

## Backend API

Add a new route module:

```text
studio/api/routes/clarifications.py
```

Register it under `/api`.

### Start Or Get Session

```http
POST /api/requirements/{req_id}/clarification
```

Query:

```text
workspace=<workspace>
```

Response:

```json
{
  "session": { "...": "RequirementClarificationSession" }
}
```

Rules:

- If an active session already exists for the requirement, return it.
- If none exists, create one.
- Requirement must exist.

### Send Message

```http
POST /api/requirements/{req_id}/clarification/messages
```

Body:

```json
{
  "message": "I want combat to be fast, maybe 3v3.",
  "session_id": "clar_req_123"
}
```

Response:

```json
{
  "session": { "...": "RequirementClarificationSession" },
  "assistant_message": "Should the MVP include elemental counters?"
}
```

Rules:

- Append the user message.
- Call the clarification agent.
- Parse strict JSON output.
- Append assistant reply.
- Replace `meeting_context` with the latest structured draft.
- Recompute readiness.
- Save the session.
- Return validation errors clearly.
- Do not return a deterministic fake assistant reply on LLM failure.

### Start Kickoff From Clarification

```http
POST /api/requirements/{req_id}/clarification/kickoff
```

Body:

```json
{
  "session_id": "clar_req_123"
}
```

Response:

```json
{
  "project_id": "proj_123",
  "requirement_id": "req_123",
  "meeting_id": "meeting_123",
  "status": "kickoff_complete"
}
```

Rules:

- Session must exist.
- Session must be ready.
- `meeting_context` must pass server-side validation.
- Create project-agent sessions using `SessionRegistry`.
- Invoke `build_meeting_graph()` with `meeting_context` and `project_id`.
- Save meeting minutes.
- Store `project_id` back on the clarification session.
- Broadcast workspace entity updates for meetings and requirements where applicable.

## Frontend Design

Add a new component:

```text
web/src/components/common/RequirementClarificationDialog.tsx
```

Suggested layout:

- Header: requirement title, status, readiness badge.
- Left column: chat transcript and message composer.
- Right column: structured context preview.
- Footer: `Save Draft`, `Start Kickoff Meeting`, `Close`.

Context preview sections:

- Summary
- Goals
- Constraints
- Open Questions
- Acceptance Criteria
- Risks
- Suggested Attendees

Visual states:

- Missing required fields show amber labels.
- Unsupported attendees show red validation error.
- Ready state enables `Start Kickoff Meeting`.
- Kickoff success shows project id and meeting id.

Integrate into:

```text
web/src/components/board/RequirementCard.tsx
```

Add a `Clarify` action for draft/designing requirements.

Add API methods in:

```text
web/src/lib/api.ts
```

Suggested methods:

```ts
clarificationsApi.start(workspace, requirementId)
clarificationsApi.sendMessage(workspace, requirementId, sessionId, message)
clarificationsApi.kickoff(workspace, requirementId, sessionId)
```

## Meeting Graph Integration

The kickoff endpoint must invoke Meeting Graph with:

```json
{
  "workspace_root": "<workspace>/.studio-data",
  "project_root": "<repo root>",
  "requirement_id": "req_123",
  "user_intent": "Run kickoff meeting for this clarified requirement.",
  "project_id": "proj_123",
  "meeting_context": { "...": "validated structured context" }
}
```

This is the key handoff. The frontend dialog owns producing `meeting_context`; Meeting Graph owns multi-agent discussion and minutes.

## Validation

Server-side validation must reject:

- Empty user messages.
- Missing session id when sending a message.
- Missing requirement.
- Missing or malformed `meeting_context` at kickoff.
- Unsupported `validated_attendees`.
- Kickoff when readiness is false.
- Re-kickoff of a completed clarification session unless an explicit `rerun` behavior is later added.

The first implementation should not include `rerun`.

## Error Handling

- Clarification LLM failure: return HTTP 502 or 500 with a clear message; keep the user message saved with session status `failed`.
- Invalid agent JSON: return clear parse error and do not mutate `meeting_context`.
- Kickoff graph failure: set session status `failed`, preserve error detail, and allow retry after the issue is fixed.
- Missing project sessions after kickoff creation: fail clearly; do not create ad hoc sessions inside graph nodes.
- WebSocket broadcast failure should not fail the primary request.

## Testing

Backend tests:

- Starting clarification creates a session for an existing requirement.
- Starting twice returns the active session.
- Sending a message appends user and assistant messages.
- Clarification agent JSON updates `meeting_context`.
- Invalid agent JSON returns an error without fake fallback.
- Kickoff rejects unready sessions.
- Kickoff rejects unsupported attendees.
- Kickoff creates project-agent sessions and invokes Meeting Graph with `meeting_context`.
- Kickoff stores `project_id` on the clarification session.

Frontend tests:

- Requirement card shows `Clarify` action.
- Dialog loads or starts a clarification session.
- Sending a message updates transcript and context preview.
- Missing required context disables kickoff.
- Ready context enables kickoff.
- Kickoff success displays project id/meeting id and invalidates relevant queries.

Manual acceptance:

- Create a draft requirement in the web board.
- Open `Clarify`.
- Talk through a small game feature.
- Confirm the context preview becomes ready.
- Start kickoff.
- Inspect saved meeting minutes.
- Open LangGraph Studio and verify the same `meeting_context` reaches Meeting Graph nodes.

## Acceptance Criteria

- User can clarify a draft requirement from the web board.
- Clarification conversation persists in workspace storage.
- Agent returns a real structured context; no fake fallback context is generated.
- UI shows a clear structured preview before kickoff.
- Kickoff cannot start until required context is ready.
- Kickoff passes the structured `meeting_context` into Meeting Graph.
- Meeting Graph produces minutes using the clarified context.
- Project-agent sessions are created only at kickoff.
- Existing requirement board, workflow API, Meeting Graph, and agent debug tests remain green.
