# Meeting Graph Context and Conflict Design

## Summary

Meeting Graph needs to consume the detailed requirement context produced by the frontend user discussion, keep participant selection bounded to known agents, and handle moderator-identified conflicts with a second discussion round before final minutes. This spec corrects the current first-pass behavior where the graph mostly discusses `user_intent`, allows arbitrary attendee names from the moderator, and records conflicts without resolving or escalating them.

## Problem

The current `studio_meeting_workflow` is useful for graph inspection, but it does not yet match the intended user flow.

Current behavior:

- Meeting input uses `user_intent` and requirement title/id, but does not load a detailed discussion-derived context object.
- `moderator_prepare` can return any attendee names.
- `route_to_agents` fans out to every attendee returned by the moderator.
- Unknown attendee names fall back to `DesignAgent`, which can create misleading "extra roles".
- `moderator_summarize` returns `conflict_resolution_needed`, but the graph drops it.
- There is no second-round discussion when conflicts need resolution.

Intended behavior:

- The frontend captures a rich user discussion before kickoff.
- Meeting Graph consumes that rich context as the meeting source of truth.
- Moderator may choose participants only from supported agent roles.
- Unknown or duplicate attendees are rejected or sanitized deterministically.
- Conflicts identified by the moderator trigger one bounded second-round discussion.
- Unresolved conflicts are recorded as pending user decisions in final minutes.

## Goals

- Add an explicit meeting context payload sourced from frontend user discussion.
- Ensure all meeting nodes receive the same detailed context.
- Restrict attendees to supported roles: `design`, `art`, `dev`, `qa`.
- Prevent unknown moderator-proposed roles from creating extra graph branches.
- Preserve `conflict_resolution_needed` in graph state.
- Add a second discussion round for conflicts that need more input.
- Save final minutes with consensus, conflicts, supplementary discussion, decisions, action items, and pending user decisions.

## Non-Goals

- Do not build the frontend discussion UI in this change.
- Do not implement project-level Claude session persistence here; that is covered by `2026-04-22-project-agent-session-design.md`.
- Do not support unlimited meeting rounds.
- Do not allow arbitrary dynamic agent roles.
- Do not turn Meeting Graph into a general chat system.

## Input Contract

The graph should accept a `meeting_context` object in addition to the existing fields.

Required invocation fields:

```json
{
  "workspace_root": "f:\\projs\\Game_Studio\\.runtime-data\\langgraph-dev\\.studio-data",
  "project_root": "f:\\projs\\Game_Studio",
  "requirement_id": "req_123",
  "user_intent": "User's concise kickoff intent",
  "meeting_context": {
    "summary": "A concise summary of the frontend discussion.",
    "raw_messages": [
      {
        "speaker": "user",
        "content": "I want turn-based combat with positioning and skill combos."
      }
    ],
    "goals": ["Turn-based combat", "Positioning", "Skill combos"],
    "constraints": ["Small MVP scope", "Readable UI"],
    "open_questions": ["How many unit classes in MVP?"],
    "references": ["Inspired by Into the Breach pacing"]
  }
}
```

`meeting_context` should be treated as the most detailed source of truth. `user_intent` remains a short instruction for the meeting. Requirement title remains a fallback label, not the full discussion context.

If `meeting_context` is missing, the graph may run in compatibility mode using `user_intent` and requirement title, but the output should clearly indicate that detailed context was unavailable.

## Graph State

Extend `_MeetingState` with:

```python
meeting_context: dict[str, object]
validated_attendees: list[str]
conflict_resolution_needed: list[str]
supplementary: dict[str, str]
context_warnings: list[str]
```

State meanings:

- `meeting_context`: discussion-derived context from frontend.
- `validated_attendees`: sanitized supported roles that will actually run.
- `conflict_resolution_needed`: conflicts selected by moderator for second-round discussion.
- `supplementary`: second-round discussion output keyed by conflict or role.
- `context_warnings`: non-fatal warnings, such as missing detailed context or ignored attendee names.

## Participant Policy

Supported meeting participants are:

- `design`
- `art`
- `dev`
- `qa`

Rules:

- The moderator may suggest attendees, but the graph must validate them.
- Duplicates are removed while preserving order.
- Unknown roles are ignored and recorded in `context_warnings`.
- If validation leaves no attendees, default to `design`, `dev`, and `qa`.
- The graph must never instantiate `DesignAgent` as a fallback for an unknown role.

This directly fixes the "10 roles joined the meeting" behavior.

## Graph Flow

Updated graph:

```text
START
  -> moderator_prepare
  -> validate_attendees
  -> agent_opinion fan-out
  -> moderator_summarize
  -> route_conflicts
      -> moderator_discuss, if conflict_resolution_needed is non-empty
      -> moderator_minutes, if no second round is needed
  -> moderator_minutes
  -> END
```

`moderator_prepare`

- Loads requirement by `requirement_id`.
- Reads `meeting_context` from state.
- Sends requirement id/title, user intent, and full meeting context to ModeratorAgent.
- Outputs agenda and proposed attendees.

`validate_attendees`

- Applies the participant policy.
- Writes `validated_attendees`.
- Writes ignored roles to `context_warnings`.

`agent_opinion`

- Runs only for `validated_attendees`.
- Sends each participant the same meeting context, agenda, requirement info, and role.
- Does not run unknown roles.

`moderator_summarize`

- Sends all opinions and meeting context to ModeratorAgent.
- Outputs `consensus_points`, `conflict_points`, and `conflict_resolution_needed`.

`moderator_discuss`

- Runs only when `conflict_resolution_needed` is non-empty.
- Sends conflicts, opinions, and meeting context to ModeratorAgent.
- Produces `supplementary` resolution notes.
- Does not perform another fan-out in this version.

`moderator_minutes`

- Receives agenda, attendees, opinions, consensus, conflicts, conflict resolution notes, context warnings, and meeting context.
- Saves final `MeetingMinutes`.
- Unresolved conflicts must appear in `pending_user_decisions`.

## ModeratorAgent Changes

Add or complete a `discuss` method:

```python
def discuss(
    self,
    state: RuntimeState,
    *,
    conflicts: list[str],
    opinions: dict[str, dict[str, object]],
    meeting_context: dict[str, object],
) -> NodeResult:
    ...
```

Expected telemetry key:

```python
telemetry["moderator_discussion"] = {
    "supplementary": {
        "conflict topic": "resolution notes or escalation guidance"
    },
    "unresolved_conflicts": ["items still requiring user decision"]
}
```

Add a corresponding role payload schema in `studio/llm/claude_roles.py`:

```python
class ModeratorDiscussionPayload(BaseModel):
    supplementary: dict[str, str]
    unresolved_conflicts: list[str]
```

Register it as `moderator_discussion`.

## Meeting Minutes

The existing `MeetingMinutes` schema can remain mostly unchanged.

Use existing fields as follows:

- `agenda`: moderator agenda.
- `attendees`: validated attendees, not raw moderator output.
- `opinions`: validated agent opinions only.
- `consensus_points`: moderator summary consensus.
- `conflict_points`: all identified conflict points.
- `supplementary`: second-round discussion output and context warnings.
- `decisions`: moderator-confirmed decisions.
- `action_items`: next steps.
- `pending_user_decisions`: unresolved conflicts and user decisions needed.

If additional structure is needed later, add it in a separate schema migration. This change should keep storage simple.

## API and Frontend Boundary

The frontend is responsible for collecting the detailed user discussion and passing it as `meeting_context`.

This backend change should not build the discussion UI, but it should make the graph input contract explicit enough for frontend integration.

Future frontend call shape:

```json
{
  "requirement_id": "req_123",
  "user_intent": "Run kickoff meeting for this requirement.",
  "meeting_context": {
    "summary": "...",
    "raw_messages": [...],
    "goals": [...],
    "constraints": [...],
    "open_questions": [...],
    "references": [...]
  }
}
```

## Error Handling

- Missing `workspace_root`, `project_root`, or `requirement_id`: fail as today.
- Missing requirement file: fail clearly.
- Missing `meeting_context`: compatibility mode with a warning.
- Malformed `meeting_context`: fail with a validation error.
- Unknown attendees: ignore and record a warning.
- Empty validated attendees: default to `design`, `dev`, and `qa`.
- Moderator failure: use existing fallback behavior, but still validate attendees and keep warnings.
- Participant agent failure: omit that opinion and record a warning; the meeting continues with available opinions.

## Tests

Required test coverage:

- Meeting graph passes `meeting_context` into moderator prepare and participant opinions.
- Unknown moderator attendees are ignored and do not create extra graph branches.
- Duplicate attendees are deduplicated.
- Empty validated attendees default to `design`, `dev`, and `qa`.
- `conflict_resolution_needed` triggers `moderator_discuss`.
- No conflict skips `moderator_discuss`.
- Final minutes include `supplementary` discussion output.
- Unresolved conflicts appear in `pending_user_decisions`.
- Compatibility mode works without `meeting_context` and records a warning.

## Acceptance Criteria

- A kickoff meeting can be run with detailed frontend discussion context.
- Only supported roles participate in the meeting.
- The graph never creates branches for unknown moderator-proposed roles.
- The final minutes clearly show what context was discussed.
- Conflict points that require resolution trigger one second-round moderator discussion.
- Unresolved conflicts are preserved for the user as pending decisions.
- Existing meeting graph, moderator agent, and profile tests remain green.
