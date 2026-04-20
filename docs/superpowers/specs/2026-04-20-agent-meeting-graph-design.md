---
name: Agent Meeting Graph
type: project
---

# Agent Meeting Graph — Design Spec

**Date:** 2026-04-20
**Scope:** Phase 1 of 3 (core meeting graph with moderator agent)

## Context

The current design_graph runs a single DesignAgent to produce a design doc for a requirement. This is a single-perspective output that misses input from art, dev, and QA perspectives. The agent meeting graph replaces this with a moderator-driven structured review where multiple agents contribute from their professional viewpoint, the moderator synthesizes consensus and conflicts, and the output is a structured meeting minutes document.

**Core principle:** AI handles multi-perspective analysis; humans make final decisions.

**Read-only guarantee:** The meeting graph produces minutes but does not modify requirements, design docs, or any workspace files. It is purely an analysis and synthesis tool.

## Overall 3-Phase Plan

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Moderator agent + meeting graph + meeting minutes schema | This spec |
| 2 | Decompose minutes into multiple requirements with dependencies | Future |
| 3 | Replace design_graph + frontend meeting UI | Future |

## Phase 1 Design

### Graph Structure

```
START
  │
  ▼
moderator_prepare    — Analyze user intent, build agenda, decide attendees
  │
  ▼
fan_out_agents       — Parallel: each selected agent outputs structured opinion
  │
  ▼
moderator_summarize  — Synthesize consensus points, conflict points
  │
  ▼
moderator_discuss    — Supplementary round on key conflicts only
  │
  ▼
moderator_minutes    — Produce final meeting minutes
  │
  ▼
END
```

### Graph State Keys

| Key | Type | Description |
|-----|------|-------------|
| `workspace_root` | `str` | Workspace data directory path |
| `project_root` | `str` | Project root for .env resolution |
| `requirement_id` | `str` | The requirement being reviewed |
| `user_intent` | `str` | Raw user input (requirement title or custom prompt) |
| `agenda` | `list[str]` | Moderator-organized discussion topics |
| `attendees` | `list[str]` | Selected agent roles (subset of design/art/dev/qa) |
| `opinions` | `dict[str, AgentOpinion]` | Structured opinions keyed by agent role |
| `consensus_points` | `list[str]` | Points where all agents agree |
| `conflict_points` | `list[str]` | Points where agents disagree |
| `supplementary` | `dict[str, str]` | Additional input from supplementary discussion |
| `minutes` | `MeetingMinutes` | Final meeting output |

### New Components

| Component | File | Purpose |
|-----------|------|---------|
| `ModeratorAgent` | `studio/agents/moderator.py` | LLM-driven moderator with 4 phase methods |
| `ModeratorPreparePayload` | `studio/llm/claude_roles.py` | Agenda + attendees output schema |
| `ModeratorSummaryPayload` | `studio/llm/claude_roles.py` | Consensus/conflict output schema |
| `ModeratorMinutesPayload` | `studio/llm/claude_roles.py` | Final minutes output schema |
| `AgentOpinionPayload` | `studio/llm/claude_roles.py` | Per-agent structured opinion schema |
| `moderator.yaml` | `studio/agents/profiles/moderator.yaml` | Moderator agent profile |
| `.claude/agents/moderator/` | `.claude/agents/moderator/CLAUDE.md` | Moderator Claude context |
| `MeetingMinutes` | `studio/schemas/meeting.py` | Pydantic schema for meeting output |
| `AgentOpinion` | `studio/schemas/meeting.py` | Pydantic schema for agent opinions |
| `build_meeting_graph()` | `studio/runtime/graph.py` | LangGraph graph definition |

### Payload Schemas

```python
class ModeratorPreparePayload(BaseModel):
    agenda: list[str]           # Discussion topics
    attendees: list[str]        # Which agents to invite
    focus_questions: list[str]  # Specific questions for the meeting

class AgentOpinionPayload(BaseModel):
    summary: str                # Brief position summary
    proposals: list[str]        # Concrete suggestions
    risks: list[str]            # Risks from this perspective
    open_questions: list[str]   # Items needing clarification

class ModeratorSummaryPayload(BaseModel):
    consensus_points: list[str]      # Where agents agree
    conflict_points: list[str]       # Where agents disagree
    conflict_resolution_needed: list[str]  # Which conflicts need supplementary discussion

class ModeratorMinutesPayload(BaseModel):
    title: str
    summary: str
    decisions: list[str]               # Agreed-upon decisions
    action_items: list[str]            # Next steps
    pending_user_decisions: list[str]  # Items requiring human approval
```

### Storage Schema (MeetingMinutes)

```python
class AgentOpinion(BaseModel):
    agent_role: str
    summary: str
    proposals: list[str]
    risks: list[str]
    open_questions: list[str]

class MeetingMinutes(BaseModel):
    id: str                          # meeting_{requirement_id_suffix}
    requirement_id: str              # Linked requirement
    title: str
    agenda: list[str]
    attendees: list[str]
    opinions: list[AgentOpinion]
    consensus_points: list[str]
    conflict_points: list[str]
    supplementary: dict[str, str]
    decisions: list[str]
    action_items: list[str]
    pending_user_decisions: list[str]
    status: Literal["draft", "completed"]
```

Stored as JSON in `workspace/meetings/` via `JsonRepository`.

### ModeratorAgent Design

The moderator has 4 methods corresponding to the 4 graph nodes:

```python
class ModeratorAgent:
    def prepare(self, state: RuntimeState) -> NodeResult:
        # Input: user_intent
        # Output: agenda, attendees, focus_questions
        # LLM call with "moderator" role

    def summarize(self, state: RuntimeState, opinions: dict) -> NodeResult:
        # Input: all agent opinions
        # Output: consensus_points, conflict_points, conflict_resolution_needed

    def discuss(self, state: RuntimeState, conflicts: list[str], opinions: dict) -> NodeResult:
        # Input: conflict points + relevant agent opinions
        # Output: supplementary resolution suggestions

    def minutes(self, state: RuntimeState, all_context: dict) -> NodeResult:
        # Input: everything from previous nodes
        # Output: final MeetingMinutes
```

Each method calls `ClaudeRoleAdapter.generate("moderator", context)` with different context payloads, reusing the existing moderator profile.

### MeetingOpinionAgent Pattern

The fan-out nodes run existing agents (DesignAgent, DevAgent, QaAgent, ArtAgent) but with a different prompt framing — instead of generating a design doc or running code, they provide a structured opinion on the agenda items.

**Option (to implement):** Add a generic "opinion mode" to existing agents via a context flag, or create lightweight wrapper that calls `ClaudeRoleAdapter.generate(role, {"mode": "opinion", "agenda": [...], "user_intent": ...})`.

**Decision:** Reuse existing agent classes with opinion-framed context in the goal dict. No new agent classes needed for the participants.

### Fan-Out Implementation

Use LangGraph's `Send` API for parallel agent execution:

```python
from langgraph.types import Send

def route_to_agents(state):
    attendees = state.get("attendees", [])
    return [Send("agent_opinion", {**state, "_target_role": role}) for role in attendees]

graph.add_conditional_edges("moderator_prepare", route_to_agents)
```

Each `agent_opinion` node invocation:
1. Reads `_target_role` from state
2. Instantiates the corresponding agent (DesignAgent, DevAgent, etc.)
3. Calls agent.run() with opinion-framed goal
4. Stores result in state.opinions[role]

### Error Handling

- If an individual agent fails in the fan-out, its opinion is omitted with a warning. The meeting continues with available opinions.
- If the moderator fails at any stage, the entire graph fails and the poller rolls back the requirement status.
- All errors are logged via the existing trace/telemetry system.

### Integration Points

- **Poller:** Picks up requirements in `draft`/`designing` status and runs the meeting graph instead of the old design_graph.
- **Storage:** Meeting minutes saved to `workspace/meetings/` as JSON files.
- **API:** New endpoint `GET /api/meetings` and `GET /api/meetings/{id}` for frontend access.
- **WebSocket:** Broadcasts `meeting` entity changes.

### Non-Goals for Phase 1

- Frontend UI for meetings (Phase 3)
- Decomposing minutes into multiple requirements (Phase 2)
- Interactive/iterative meetings (one-shot for now)
- Meeting history/versioning
- Multiple meeting rounds

### Acceptance Criteria

1. `build_meeting_graph()` compiles and invokes successfully
2. Given a requirement in `draft` status, the meeting graph runs to completion
3. Output includes structured opinions from at least 2 agent roles
4. Meeting minutes are saved to workspace as JSON
5. All existing tests continue to pass
6. Moderator has a valid YAML profile and Claude context directory
