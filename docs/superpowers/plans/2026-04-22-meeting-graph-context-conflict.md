# Meeting Graph Context and Conflict Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `studio_meeting_workflow` so it consumes frontend-provided `meeting_context`, limits meeting participants to supported roles, filters unknown moderator attendees deterministically, and runs one bounded moderator conflict-discussion round before final minutes when needed.

**Architecture:** Keep the existing meeting graph shape and storage model, but repair the orchestration contract around it. The implementation adds a validated meeting-context source, an explicit attendee-validation node, a conditional `moderator_discuss` node, and moderator payload support for supplementary conflict discussion. Existing `MeetingMinutes` storage remains the persistence boundary; warnings and compatibility-mode notes flow through graph state and are folded into `supplementary` / `pending_user_decisions`.

**Tech Stack:** Python 3.12, LangGraph, Pydantic, pytest, uv

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `studio/runtime/graph.py` | Modify | Extend `_MeetingState`, validate `meeting_context`, sanitize attendees, preserve `conflict_resolution_needed`, add `validate_attendees` and `moderator_discuss` flow, record warnings, and build final minutes from validated state |
| `studio/agents/moderator.py` | Modify | Forward `meeting_context` into moderator phases and add `discuss()` with `moderator_discussion` telemetry |
| `studio/llm/claude_roles.py` | Modify | Register `ModeratorDiscussionPayload`, prompt text, output schema, and role parsing support |
| `tests/test_meeting_graph.py` | Modify | Cover `meeting_context` propagation, attendee filtering/defaulting, conflict routing, final minutes enrichment, and compatibility mode |
| `tests/test_moderator_agent.py` | Modify | Cover `discuss()` plus moderator context forwarding and telemetry keys |
| `tests/test_claude_roles.py` | Modify | Cover `moderator_discussion` payload parsing and active-role registry updates |

---

### Task 1: Extend Moderator Role Contracts

**Files:**
- Modify: `studio/llm/claude_roles.py`
- Modify: `tests/test_claude_roles.py`
- Modify: `tests/test_moderator_agent.py`

- [ ] **Step 1: Write failing role-schema and moderator-agent tests**

```python
# tests/test_claude_roles.py
from studio.llm import ClaudeRoleError, parse_role_payload
from studio.llm import claude_roles as claude_roles_module


def test_parse_role_payload_returns_moderator_discussion_payload() -> None:
    payload = parse_role_payload(
        "moderator_discussion",
        {
            "supplementary": {
                "combat scope": "Keep combos, defer elemental reactions to post-MVP.",
            },
            "unresolved_conflicts": ["final action-point budget still needs user input"],
        },
    )

    assert payload.supplementary == {
        "combat scope": "Keep combos, defer elemental reactions to post-MVP.",
    }
    assert payload.unresolved_conflicts == [
        "final action-point budget still needs user input",
    ]


def test_supported_role_registry_includes_moderator_discussion() -> None:
    assert "moderator_discussion" in claude_roles_module._ACTIVE_ROLE_NAMES
    assert "moderator_discussion" in claude_roles_module._ROLE_PAYLOAD_MODELS
    assert "moderator_discussion" in claude_roles_module._ROLE_OUTPUT_FORMATS
```

```python
# tests/test_moderator_agent.py
from pathlib import Path

from studio.agents.moderator import ModeratorAgent
from studio.schemas.runtime import RuntimeState


_REPO_ROOT = Path(__file__).resolve().parents[1]


class FakeClaudeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def generate(self, role_name: str, context: dict[str, object]):
        self.calls.append((role_name, context))
        if role_name == "moderator_prepare":
            return type(
                "Payload",
                (),
                {"agenda": ["Scope"], "attendees": ["design", "producer"], "focus_questions": []},
            )()
        if role_name == "moderator_summary":
            return type(
                "Payload",
                (),
                {
                    "consensus_points": ["Keep combo depth in MVP"],
                    "conflict_points": ["Need a smaller launch roster"],
                    "conflict_resolution_needed": ["launch roster size"],
                },
            )()
        if role_name == "moderator_discussion":
            return type(
                "Payload",
                (),
                {
                    "supplementary": {
                        "launch roster size": "Ship 4 units now and leave two variants for later."
                    },
                    "unresolved_conflicts": ["final roster count still needs user approval"],
                },
            )()
        if role_name == "moderator_minutes":
            return type(
                "Payload",
                (),
                {
                    "title": "Kickoff Minutes",
                    "summary": "Context-aware discussion completed.",
                    "decisions": ["Use the validated attendee list"],
                    "action_items": ["Prototype combat readability"],
                    "pending_user_decisions": ["Approve final roster count"],
                },
            )()
        raise AssertionError(f"unexpected role: {role_name}")

    def consume_debug_record(self) -> None:
        return None


def _state(goal: dict[str, object] | None = None) -> RuntimeState:
    return RuntimeState(
        project_id="meeting-project",
        run_id="run-001",
        task_id="task-001",
        goal=goal
        or {
            "prompt": "Run kickoff meeting",
            "requirement_id": "req_001",
            "meeting_context": {"summary": "Turn-based tactics with positioning"},
        },
    )


def test_discuss_returns_supplementary_and_unresolved_conflicts() -> None:
    runner = FakeClaudeRunner()
    agent = ModeratorAgent(claude_runner=runner, project_root=_REPO_ROOT)

    result = agent.discuss(
        _state(),
        conflicts=["launch roster size"],
        opinions={"design": {"summary": "Keep readability high"}},
        meeting_context={"summary": "Turn-based tactics with positioning"},
    )

    telemetry = result.state_patch["telemetry"]["moderator_discussion"]
    assert telemetry["supplementary"]["launch roster size"].startswith("Ship 4 units")
    assert telemetry["unresolved_conflicts"] == ["final roster count still needs user approval"]
    assert runner.calls[-1][0] == "moderator_discussion"


def test_prepare_and_summarize_forward_meeting_context_to_runner() -> None:
    runner = FakeClaudeRunner()
    agent = ModeratorAgent(claude_runner=runner, project_root=_REPO_ROOT)
    state = _state()

    agent.prepare(state)
    agent.summarize(
        state,
        opinions={"design": {"summary": "Keep readability high"}},
        meeting_context={"summary": "Turn-based tactics with positioning"},
    )

    prepare_context = runner.calls[0][1]
    summarize_context = runner.calls[1][1]
    assert prepare_context["goal"]["meeting_context"]["summary"] == "Turn-based tactics with positioning"
    assert summarize_context["meeting_context"]["summary"] == "Turn-based tactics with positioning"
```

- [ ] **Step 2: Run the targeted tests to confirm the new gaps**

Run: `uv run pytest tests/test_claude_roles.py tests/test_moderator_agent.py -v`
Expected: FAIL with `unsupported_role:moderator_discussion` and/or `AttributeError: 'ModeratorAgent' object has no attribute 'discuss'`

- [ ] **Step 3: Add the new moderator-discussion payload contract in `studio/llm/claude_roles.py`**

```python
class ModeratorDiscussionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplementary: dict[str, str]
    unresolved_conflicts: list[str]
```

```python
_ROLE_PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "agent_opinion": AgentOpinionPayload,
    "art": ArtPayload,
    "dev": DevPayload,
    "design": DesignPayload,
    "moderator_discussion": ModeratorDiscussionPayload,
    "moderator_minutes": ModeratorMinutesPayload,
    "moderator_prepare": ModeratorPreparePayload,
    "moderator_summary": ModeratorSummaryPayload,
    "qa": QaPayload,
    "quality": QualityPayload,
    "reviewer": ReviewerPayload,
    "worker": WorkerPayload,
}
```

```python
_ROLE_PROMPTS["moderator_discussion"] = (
    "You are the meeting moderator.\n"
    "You are running one bounded follow-up round on the conflicts that still need resolution.\n"
    "Return only JSON with supplementary (per-conflict notes or escalation guidance) "
    "and unresolved_conflicts (items that still need a user decision).\n"
)
```

```python
_ROLE_OUTPUT_FORMATS["moderator_discussion"] = {
    "type": "object",
    "properties": {
        "supplementary": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
        "unresolved_conflicts": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["supplementary", "unresolved_conflicts"],
    "additionalProperties": False,
}
```

```python
def parse_role_payload(
    role_name: str, data: object
) -> (
    ReviewerPayload
    | DesignPayload
    | DevPayload
    | QaPayload
    | QualityPayload
    | ArtPayload
    | WorkerPayload
    | ModeratorPreparePayload
    | AgentOpinionPayload
    | ModeratorSummaryPayload
    | ModeratorDiscussionPayload
    | ModeratorMinutesPayload
):
    ...
        (
            ReviewerPayload,
            DesignPayload,
            DevPayload,
            QaPayload,
            QualityPayload,
            ArtPayload,
            WorkerPayload,
            ModeratorPreparePayload,
            AgentOpinionPayload,
            ModeratorSummaryPayload,
            ModeratorDiscussionPayload,
            ModeratorMinutesPayload,
        ),
    ):
        return parsed
```

- [ ] **Step 4: Add `discuss()` and `meeting_context` forwarding to `studio/agents/moderator.py`**

```python
def prepare(self, state: RuntimeState) -> NodeResult:
    trace: dict[str, object] = {"node": "moderator_prepare", "llm_provider": "claude", "fallback_used": True}
    state_patch: dict[str, object] = {"plan": {"current_node": "moderator_prepare"}, "telemetry": {}}

    context = {"goal": state.goal, "phase": "prepare"}
    try:
        payload = self._claude_runner.generate("moderator_prepare", context)
        state_patch["telemetry"] = {"moderator_prepare": self._prepare_payload(payload)}
        trace["fallback_used"] = False
    except ClaudeRoleError as exc:
        trace["fallback_reason"] = str(exc)
        state_patch["telemetry"] = {"moderator_prepare": self._fallback_prepare(state)}

    return NodeResult(decision=NodeDecision.CONTINUE, state_patch=state_patch, trace=trace)
```

```python
def summarize(
    self,
    state: RuntimeState,
    *,
    opinions: dict[str, dict[str, object]],
    meeting_context: dict[str, object],
) -> NodeResult:
    trace: dict[str, object] = {"node": "moderator_summarize", "llm_provider": "claude", "fallback_used": True}
    state_patch: dict[str, object] = {"plan": {"current_node": "moderator_summarize"}, "telemetry": {}}

    context = {
        "goal": state.goal,
        "phase": "summarize",
        "opinions": opinions,
        "meeting_context": meeting_context,
    }
    try:
        payload = self._claude_runner.generate("moderator_summary", context)
        state_patch["telemetry"] = {"moderator_summary": self._summary_payload(payload)}
        trace["fallback_used"] = False
    except ClaudeRoleError as exc:
        trace["fallback_reason"] = str(exc)
        state_patch["telemetry"] = {"moderator_summary": self._fallback_summary()}

    return NodeResult(decision=NodeDecision.CONTINUE, state_patch=state_patch, trace=trace)
```

```python
def discuss(
    self,
    state: RuntimeState,
    *,
    conflicts: list[str],
    opinions: dict[str, dict[str, object]],
    meeting_context: dict[str, object],
) -> NodeResult:
    trace: dict[str, object] = {"node": "moderator_discussion", "llm_provider": "claude", "fallback_used": True}
    state_patch: dict[str, object] = {"plan": {"current_node": "moderator_discussion"}, "telemetry": {}}

    context = {
        "goal": state.goal,
        "phase": "discussion",
        "conflicts": conflicts,
        "opinions": opinions,
        "meeting_context": meeting_context,
    }
    try:
        payload = self._claude_runner.generate("moderator_discussion", context)
        state_patch["telemetry"] = {"moderator_discussion": self._discussion_payload(payload)}
        trace["fallback_used"] = False
    except ClaudeRoleError as exc:
        trace["fallback_reason"] = str(exc)
        state_patch["telemetry"] = {"moderator_discussion": self._fallback_discussion(conflicts)}

    return NodeResult(decision=NodeDecision.CONTINUE, state_patch=state_patch, trace=trace)
```

```python
@staticmethod
def _discussion_payload(payload: object) -> dict[str, object]:
    return {
        "supplementary": dict(payload.supplementary),
        "unresolved_conflicts": list(payload.unresolved_conflicts),
    }


@staticmethod
def _fallback_discussion(conflicts: list[str]) -> dict[str, object]:
    return {
        "supplementary": {
            conflict: "Moderator fallback: needs explicit user decision."
            for conflict in conflicts
        },
        "unresolved_conflicts": list(conflicts),
    }
```

```python
def minutes(self, state: RuntimeState, *, all_context: dict) -> NodeResult:
    ...
    context = {"goal": state.goal, "phase": "minutes", **all_context}
    ...
```

- [ ] **Step 5: Re-run the targeted tests**

Run: `uv run pytest tests/test_claude_roles.py tests/test_moderator_agent.py -v`
Expected: PASS

- [ ] **Step 6: Commit the contract-layer changes**

```bash
git add studio/llm/claude_roles.py studio/agents/moderator.py tests/test_claude_roles.py tests/test_moderator_agent.py
git commit -m "fix: add moderator discussion contract for meeting conflicts"
```

---

### Task 2: Lock Down Meeting Graph Behavior with Tests

**Files:**
- Modify: `tests/test_meeting_graph.py`

- [ ] **Step 1: Add failing graph-behavior tests for the new requirements**

```python
def test_meeting_graph_uses_meeting_context_and_filters_unknown_attendees(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / ".studio-data"
    workspace = StudioWorkspace(workspace_root)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Combat meeting"))

    prepare_calls: list[dict[str, object]] = []
    participant_calls: list[dict[str, object]] = []

    class FakeModerator:
        def __init__(self, project_root: Path) -> None:
            pass

        def prepare(self, state):
            prepare_calls.append(dict(state.goal))
            return type(
                "Result",
                (),
                {
                    "state_patch": {
                        "telemetry": {
                            "moderator_prepare": {
                                "agenda": ["Combat scope"],
                                "attendees": ["design", "producer", "design", "qa"],
                            }
                        }
                    }
                },
            )()

        def summarize(self, state, *, opinions, meeting_context):
            assert meeting_context["summary"] == "Detailed frontend context"
            return type(
                "Result",
                (),
                {
                    "state_patch": {
                        "telemetry": {
                            "moderator_summary": {
                                "consensus_points": ["Use readable combos"],
                                "conflict_points": [],
                                "conflict_resolution_needed": [],
                            }
                        }
                    }
                },
            )()

        def discuss(self, *args, **kwargs):
            raise AssertionError("discussion should not run")

        def minutes(self, state, *, all_context):
            assert all_context["context_warnings"] == [
                "Ignored unsupported attendee roles: producer"
            ]
            return type(
                "Result",
                (),
                {
                    "state_patch": {
                        "telemetry": {
                            "moderator_minutes": {
                                "title": "Combat kickoff",
                                "summary": "Validated roles only",
                                "decisions": ["Proceed with validated attendees"],
                                "action_items": ["Prototype combo UI"],
                                "pending_user_decisions": [],
                            }
                        }
                    }
                },
            )()

    class FakeRoleAgent:
        def __init__(self, project_root: Path) -> None:
            pass

        def run(self, state):
            participant_calls.append(dict(state.goal))
            role = state.goal["role"]
            return type(
                "Result",
                (),
                {
                    "state_patch": {
                        "telemetry": {
                            f"{role}_report": {
                                "summary": f"{role} summary",
                                "proposals": [f"{role} proposal"],
                                "risks": [],
                                "open_questions": [],
                            }
                        }
                    }
                },
            )()

    monkeypatch.setattr("studio.runtime.graph.ModeratorAgent", FakeModerator)
    monkeypatch.setattr("studio.runtime.graph.DesignAgent", FakeRoleAgent)
    monkeypatch.setattr("studio.runtime.graph.ArtAgent", FakeRoleAgent)
    monkeypatch.setattr("studio.runtime.graph.DevAgent", FakeRoleAgent)
    monkeypatch.setattr("studio.runtime.graph.QaAgent", FakeRoleAgent)

    result = build_meeting_graph().invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(_REPO_ROOT),
            "requirement_id": "req_001",
            "user_intent": "Kick off combat discussion",
            "meeting_context": {"summary": "Detailed frontend context", "goals": ["Readable combos"]},
        }
    )

    assert prepare_calls[0]["meeting_context"]["summary"] == "Detailed frontend context"
    assert [call["role"] for call in participant_calls] == ["design", "qa"]
    assert result["minutes"]["attendees"] == ["design", "qa"]
```

```python
def test_meeting_graph_defaults_attendees_when_validation_removes_everything(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / ".studio-data"
    workspace = StudioWorkspace(workspace_root)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Combat meeting"))

    seen_roles: list[str] = []

    class FakeModerator:
        def __init__(self, project_root: Path) -> None:
            pass

        def prepare(self, state):
            return type(
                "Result",
                (),
                {
                    "state_patch": {
                        "telemetry": {
                            "moderator_prepare": {"agenda": ["Combat scope"], "attendees": ["producer", "ops"]}
                        }
                    }
                },
            )()

        def summarize(self, state, *, opinions, meeting_context):
            return type(
                "Result",
                (),
                {
                    "state_patch": {
                        "telemetry": {
                            "moderator_summary": {
                                "consensus_points": [],
                                "conflict_points": [],
                                "conflict_resolution_needed": [],
                            }
                        }
                    }
                },
            )()

        def discuss(self, *args, **kwargs):
            raise AssertionError("discussion should not run")

        def minutes(self, state, *, all_context):
            return type(
                "Result",
                (),
                {
                    "state_patch": {
                        "telemetry": {
                            "moderator_minutes": {
                                "title": "Fallback attendees",
                                "summary": "Used default attendees",
                                "decisions": [],
                                "action_items": [],
                                "pending_user_decisions": [],
                            }
                        }
                    }
                },
            )()

    class FakeRoleAgent:
        def __init__(self, project_root: Path) -> None:
            pass

        def run(self, state):
            seen_roles.append(str(state.goal["role"]))
            role = state.goal["role"]
            return type(
                "Result",
                (),
                {
                    "state_patch": {
                        "telemetry": {
                            f"{role}_report": {
                                "summary": f"{role} summary",
                                "proposals": [],
                                "risks": [],
                                "open_questions": [],
                            }
                        }
                    }
                },
            )()

    monkeypatch.setattr("studio.runtime.graph.ModeratorAgent", FakeModerator)
    monkeypatch.setattr("studio.runtime.graph.DesignAgent", FakeRoleAgent)
    monkeypatch.setattr("studio.runtime.graph.ArtAgent", FakeRoleAgent)
    monkeypatch.setattr("studio.runtime.graph.DevAgent", FakeRoleAgent)
    monkeypatch.setattr("studio.runtime.graph.QaAgent", FakeRoleAgent)

    build_meeting_graph().invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(_REPO_ROOT),
            "requirement_id": "req_001",
            "user_intent": "Kick off combat discussion",
            "meeting_context": {"summary": "Detailed frontend context"},
        }
    )

    assert seen_roles == ["design", "dev", "qa"]
```

```python
def test_meeting_graph_runs_single_conflict_discussion_round(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / ".studio-data"
    workspace = StudioWorkspace(workspace_root)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Combat meeting"))

    discuss_calls: list[dict[str, object]] = []

    class FakeModerator:
        def __init__(self, project_root: Path) -> None:
            pass

        def prepare(self, state):
            return type(
                "Result",
                (),
                {
                    "state_patch": {
                        "telemetry": {
                            "moderator_prepare": {"agenda": ["Combat scope"], "attendees": ["design", "dev"]}
                        }
                    }
                },
            )()

        def summarize(self, state, *, opinions, meeting_context):
            return type(
                "Result",
                (),
                {
                    "state_patch": {
                        "telemetry": {
                            "moderator_summary": {
                                "consensus_points": ["Readable combos matter"],
                                "conflict_points": ["How many unit classes fit MVP"],
                                "conflict_resolution_needed": ["How many unit classes fit MVP"],
                            }
                        }
                    }
                },
            )()

        def discuss(self, state, *, conflicts, opinions, meeting_context):
            discuss_calls.append(
                {
                    "conflicts": list(conflicts),
                    "meeting_context": dict(meeting_context),
                    "opinions": dict(opinions),
                }
            )
            return type(
                "Result",
                (),
                {
                    "state_patch": {
                        "telemetry": {
                            "moderator_discussion": {
                                "supplementary": {
                                    "How many unit classes fit MVP": "Start with four distinct classes."
                                },
                                "unresolved_conflicts": ["Final class count needs user approval"],
                            }
                        }
                    }
                },
            )()

        def minutes(self, state, *, all_context):
            assert all_context["supplementary"] == {
                "How many unit classes fit MVP": "Start with four distinct classes."
            }
            assert all_context["pending_user_decisions"] == ["Final class count needs user approval"]
            return type(
                "Result",
                (),
                {
                    "state_patch": {
                        "telemetry": {
                            "moderator_minutes": {
                                "title": "Conflict Minutes",
                                "summary": "Included supplementary moderation",
                                "decisions": ["Start with four classes for prototyping"],
                                "action_items": ["Mock up class readability"],
                                "pending_user_decisions": ["Final class count needs user approval"],
                            }
                        }
                    }
                },
            )()

    class FakeRoleAgent:
        def __init__(self, project_root: Path) -> None:
            pass

        def run(self, state):
            role = state.goal["role"]
            return type(
                "Result",
                (),
                {
                    "state_patch": {
                        "telemetry": {
                            f"{role}_report": {
                                "summary": f"{role} summary",
                                "proposals": [f"{role} proposal"],
                                "risks": [],
                                "open_questions": [],
                            }
                        }
                    }
                },
            )()

    monkeypatch.setattr("studio.runtime.graph.ModeratorAgent", FakeModerator)
    monkeypatch.setattr("studio.runtime.graph.DesignAgent", FakeRoleAgent)
    monkeypatch.setattr("studio.runtime.graph.ArtAgent", FakeRoleAgent)
    monkeypatch.setattr("studio.runtime.graph.DevAgent", FakeRoleAgent)
    monkeypatch.setattr("studio.runtime.graph.QaAgent", FakeRoleAgent)

    result = build_meeting_graph().invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(_REPO_ROOT),
            "requirement_id": "req_001",
            "user_intent": "Kick off combat discussion",
            "meeting_context": {"summary": "Detailed frontend context"},
        }
    )

    assert len(discuss_calls) == 1
    assert result["minutes"]["supplementary"]["How many unit classes fit MVP"] == "Start with four distinct classes."
    assert result["minutes"]["pending_user_decisions"] == ["Final class count needs user approval"]
```

```python
def test_meeting_graph_compatibility_mode_warns_when_meeting_context_missing(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / ".studio-data"
    workspace = StudioWorkspace(workspace_root)
    workspace.ensure_layout()
    workspace.requirements.save(RequirementCard(id="req_001", title="Combat meeting"))

    result = build_meeting_graph().invoke(
        {
            "workspace_root": str(workspace_root),
            "project_root": str(_REPO_ROOT),
            "requirement_id": "req_001",
            "user_intent": "Kick off combat discussion",
        }
    )

    assert result["minutes"]["supplementary"]["context_warning"].startswith(
        "Detailed meeting_context was unavailable"
    )
```

- [ ] **Step 2: Run the graph tests and confirm the current implementation fails**

Run: `uv run pytest tests/test_meeting_graph.py -v`
Expected: FAIL because the graph does not yet validate attendees, does not preserve `conflict_resolution_needed`, does not call `moderator_discuss`, and does not emit compatibility warnings

- [ ] **Step 3: Commit the failing-tests checkpoint**

```bash
git add tests/test_meeting_graph.py
git commit -m "test: cover meeting graph context and conflict behavior"
```

---

### Task 3: Repair the Meeting Graph Runtime

**Files:**
- Modify: `studio/runtime/graph.py`
- Modify: `studio/agents/moderator.py`

- [ ] **Step 1: Extend `_MeetingState` and add graph helpers in `studio/runtime/graph.py`**

```python
class _MeetingState(TypedDict, total=False):
    workspace_root: str
    project_root: str
    requirement_id: str
    user_intent: str
    meeting_context: dict[str, object]
    agenda: list[str]
    attendees: list[str]
    validated_attendees: list[str]
    opinions: Annotated[dict[str, dict[str, object]], operator.or_]
    consensus_points: list[str]
    conflict_points: list[str]
    conflict_resolution_needed: list[str]
    supplementary: dict[str, str]
    context_warnings: list[str]
    pending_user_decisions: list[str]
    node_name: str
    minutes: dict[str, object]
```

```python
_SUPPORTED_MEETING_ROLES = ("design", "art", "dev", "qa")
_DEFAULT_VALIDATED_ATTENDEES = ["design", "dev", "qa"]


def _append_warning(state: _MeetingState, warning: str) -> list[str]:
    warnings = [str(item) for item in state.get("context_warnings", [])]
    if warning not in warnings:
        warnings.append(warning)
    return warnings


def _normalize_string_list(value: object, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} entries must be strings")
        text = item.strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_raw_messages(value: object) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("meeting_context.raw_messages must be a list")
    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("meeting_context.raw_messages entries must be objects")
        speaker = item.get("speaker")
        content = item.get("content")
        if not isinstance(speaker, str) or not speaker.strip():
            raise ValueError("meeting_context.raw_messages.speaker must be a non-empty string")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("meeting_context.raw_messages.content must be a non-empty string")
        normalized.append({"speaker": speaker.strip(), "content": content.strip()})
    return normalized


def _coerce_meeting_context(state: _MeetingState, requirement_title: str) -> tuple[dict[str, object], list[str]]:
    raw_context = state.get("meeting_context")
    if raw_context is None:
        return (
            {
                "summary": str(state.get("user_intent") or requirement_title),
                "raw_messages": [],
                "goals": [],
                "constraints": [],
                "open_questions": [],
                "references": [],
            },
            [
                "Detailed meeting_context was unavailable; meeting ran in compatibility mode using user_intent and requirement title."
            ],
        )
    if not isinstance(raw_context, dict):
        raise ValueError("meeting_context must be an object")
    summary = raw_context.get("summary", state.get("user_intent") or requirement_title)
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("meeting_context.summary must be a non-empty string")
    return (
        {
            "summary": summary.strip(),
            "raw_messages": _normalize_raw_messages(raw_context.get("raw_messages")),
            "goals": _normalize_string_list(raw_context.get("goals"), "meeting_context.goals"),
            "constraints": _normalize_string_list(raw_context.get("constraints"), "meeting_context.constraints"),
            "open_questions": _normalize_string_list(raw_context.get("open_questions"), "meeting_context.open_questions"),
            "references": _normalize_string_list(raw_context.get("references"), "meeting_context.references"),
        },
        [],
    )


def _validate_attendee_roles(attendees: list[object]) -> tuple[list[str], list[str]]:
    validated: list[str] = []
    ignored: list[str] = []
    seen: set[str] = set()
    for attendee in attendees:
        role = str(attendee).strip().lower()
        if not role:
            continue
        if role not in _SUPPORTED_MEETING_ROLES:
            ignored.append(role)
            continue
        if role in seen:
            continue
        seen.add(role)
        validated.append(role)
    if not validated:
        validated = list(_DEFAULT_VALIDATED_ATTENDEES)
    return validated, ignored
```

- [ ] **Step 2: Update `moderator_prepare_node` and add `validate_attendees_node`**

```python
def moderator_prepare_node(state: _MeetingState) -> dict[str, object]:
    workspace_root = _require_state_str(state, "workspace_root")
    project_root = _require_state_str(state, "project_root")
    requirement_id = _require_state_str(state, "requirement_id")
    user_intent = state.get("user_intent", "")

    workspace = StudioWorkspace(Path(workspace_root))
    requirement = workspace.requirements.get(requirement_id)
    meeting_context, compatibility_warnings = _coerce_meeting_context(state, requirement.title)
    intent = str(user_intent) if user_intent else requirement.title

    moderator = ModeratorAgent(project_root=Path(project_root))
    runtime_state = RuntimeState(
        project_id="meeting-project",
        run_id=_new_run_id(),
        task_id=f"meeting-prepare-{requirement_id}",
        goal={
            "prompt": intent,
            "requirement_id": requirement_id,
            "requirement_title": requirement.title,
            "meeting_context": meeting_context,
        },
    )
    result = moderator.prepare(runtime_state)
    prep = result.state_patch.get("telemetry", {}).get("moderator_prepare", {})

    return {
        "node_name": "moderator_prepare",
        "user_intent": intent,
        "meeting_context": meeting_context,
        "agenda": prep.get("agenda", [intent]),
        "attendees": prep.get("attendees", list(_DEFAULT_VALIDATED_ATTENDEES)),
        "context_warnings": compatibility_warnings,
    }
```

```python
def validate_attendees_node(state: _MeetingState) -> dict[str, object]:
    raw_attendees = list(state.get("attendees", []))
    validated_attendees, ignored_roles = _validate_attendee_roles(raw_attendees)

    warnings = [str(item) for item in state.get("context_warnings", [])]
    if ignored_roles:
        warnings.append(
            f"Ignored unsupported attendee roles: {', '.join(ignored_roles)}"
        )
    if not any(str(role).strip().lower() in _SUPPORTED_MEETING_ROLES for role in raw_attendees):
        warnings.append("No supported attendees were proposed; defaulted to design, dev, qa.")

    return {
        "node_name": "validate_attendees",
        "validated_attendees": validated_attendees,
        "context_warnings": warnings,
    }
```

- [ ] **Step 3: Update `agent_opinion_node` and `moderator_summarize_node` to use validated state only**

```python
def agent_opinion_node(state: _MeetingState) -> dict[str, object]:
    project_root = _require_state_str(state, "project_root")
    target_role = str(state.get("_target_role", "")).strip().lower()
    if target_role not in _SUPPORTED_MEETING_ROLES:
        return {
            "context_warnings": _append_warning(
                state,
                f"Skipped unsupported attendee role during fan-out: {target_role or '<blank>'}",
            )
        }

    agent_cls = _AGENT_MAP[target_role]
    agent = agent_cls(project_root=Path(project_root))
    runtime_state = RuntimeState(
        project_id="meeting-project",
        run_id=_new_run_id(),
        task_id=f"meeting-{target_role}",
        goal={
            "prompt": str(state.get("user_intent", "")),
            "phase": "opinion",
            "agenda": list(state.get("agenda", [])),
            "role": target_role,
            "meeting_context": dict(state.get("meeting_context", {})),
        },
    )
    try:
        result = agent.run(runtime_state)
    except Exception as exc:
        return {
            "context_warnings": _append_warning(
                state,
                f"Participant agent '{target_role}' failed and its opinion was omitted: {exc}",
            )
        }
    telemetry = result.state_patch.get("telemetry", {})
    report_key = next(
        (key for key in telemetry if key.endswith("_report") or key.endswith("_brief")),
        None,
    )
    report = telemetry.get(report_key, {}) if report_key else {}

    opinion: dict[str, object] = {
        "agent_role": target_role,
        "summary": str(report.get("summary", f"{target_role} opinion")),
        "proposals": [str(item) for item in report.get("core_rules", report.get("proposals", report.get("changes", [])))],
        "risks": [str(item) for item in report.get("risks", report.get("open_questions", []))],
        "open_questions": [str(item) for item in report.get("open_questions", report.get("acceptance_criteria", []))],
    }
    return {"opinions": {target_role: opinion}}
```

```python
def moderator_summarize_node(state: _MeetingState) -> dict[str, object]:
    project_root = _require_state_str(state, "project_root")
    requirement_id = _require_state_str(state, "requirement_id")
    opinions = state.get("opinions", {})
    meeting_context = dict(state.get("meeting_context", {}))

    moderator = ModeratorAgent(project_root=Path(project_root))
    runtime_state = RuntimeState(
        project_id="meeting-project",
        run_id=_new_run_id(),
        task_id=f"meeting-summarize-{requirement_id}",
        goal={
            "prompt": str(state.get("user_intent", "")),
            "requirement_id": requirement_id,
            "meeting_context": meeting_context,
        },
    )
    result = moderator.summarize(
        runtime_state,
        opinions=opinions,
        meeting_context=meeting_context,
    )
    summary = result.state_patch.get("telemetry", {}).get("moderator_summary", {})

    return {
        "node_name": "moderator_summarize",
        "consensus_points": summary.get("consensus_points", []),
        "conflict_points": summary.get("conflict_points", []),
        "conflict_resolution_needed": summary.get("conflict_resolution_needed", []),
    }
```

- [ ] **Step 4: Add `moderator_discuss_node`, conflict routing, and validated fan-out**

```python
def moderator_discuss_node(state: _MeetingState) -> dict[str, object]:
    project_root = _require_state_str(state, "project_root")
    requirement_id = _require_state_str(state, "requirement_id")
    conflicts = [str(item) for item in state.get("conflict_resolution_needed", [])]
    meeting_context = dict(state.get("meeting_context", {}))

    moderator = ModeratorAgent(project_root=Path(project_root))
    runtime_state = RuntimeState(
        project_id="meeting-project",
        run_id=_new_run_id(),
        task_id=f"meeting-discuss-{requirement_id}",
        goal={
            "prompt": str(state.get("user_intent", "")),
            "requirement_id": requirement_id,
            "meeting_context": meeting_context,
        },
    )
    result = moderator.discuss(
        runtime_state,
        conflicts=conflicts,
        opinions=dict(state.get("opinions", {})),
        meeting_context=meeting_context,
    )
    discussion = result.state_patch.get("telemetry", {}).get("moderator_discussion", {})
    return {
        "node_name": "moderator_discussion",
        "supplementary": {
            str(key): str(value)
            for key, value in dict(discussion.get("supplementary", {})).items()
        },
        "pending_user_decisions": [
            str(item) for item in discussion.get("unresolved_conflicts", [])
        ],
    }


def route_to_agents(state: _MeetingState) -> list[Send]:
    attendees = [str(role) for role in state.get("validated_attendees", [])]
    if not attendees:
        return [Send("moderator_summarize", dict(state))]
    return [Send("agent_opinion", {**state, "_target_role": role}) for role in attendees]


def route_conflicts(state: _MeetingState) -> str:
    conflicts = [str(item) for item in state.get("conflict_resolution_needed", [])]
    return "moderator_discussion" if conflicts else "moderator_minutes"
```

```python
graph.add_node("validate_attendees", validate_attendees_node)
graph.add_node("moderator_discussion", moderator_discuss_node)

graph.add_edge(START, "moderator_prepare")
graph.add_edge("moderator_prepare", "validate_attendees")
graph.add_conditional_edges("validate_attendees", route_to_agents, ["agent_opinion", "moderator_summarize"])
graph.add_edge("agent_opinion", "moderator_summarize")
graph.add_conditional_edges("moderator_summarize", route_conflicts, ["moderator_discussion", "moderator_minutes"])
graph.add_edge("moderator_discussion", "moderator_minutes")
graph.add_edge("moderator_minutes", END)
```

- [ ] **Step 5: Update `moderator_minutes_node` to persist warnings, supplementary discussion, and unresolved conflicts**

```python
def moderator_minutes_node(state: _MeetingState) -> dict[str, object]:
    workspace_root = _require_state_str(state, "workspace_root")
    project_root = _require_state_str(state, "project_root")
    requirement_id = _require_state_str(state, "requirement_id")

    workspace = StudioWorkspace(Path(workspace_root))
    moderator = ModeratorAgent(project_root=Path(project_root))
    runtime_state = RuntimeState(
        project_id="meeting-project",
        run_id=_new_run_id(),
        task_id=f"meeting-minutes-{requirement_id}",
        goal={
            "prompt": str(state.get("user_intent", "")),
            "requirement_id": requirement_id,
            "meeting_context": dict(state.get("meeting_context", {})),
        },
    )
    all_context: dict[str, object] = {
        "agenda": list(state.get("agenda", [])),
        "attendees": list(state.get("validated_attendees", [])),
        "opinions": dict(state.get("opinions", {})),
        "consensus_points": list(state.get("consensus_points", [])),
        "conflict_points": list(state.get("conflict_points", [])),
        "supplementary": dict(state.get("supplementary", {})),
        "context_warnings": list(state.get("context_warnings", [])),
        "meeting_context": dict(state.get("meeting_context", {})),
        "pending_user_decisions": list(state.get("pending_user_decisions", [])),
    }
    result = moderator.minutes(runtime_state, all_context=all_context)
    minutes_data = result.state_patch.get("telemetry", {}).get("moderator_minutes", {})

    warnings = [str(item) for item in state.get("context_warnings", [])]
    supplementary = {
        **{str(k): str(v) for k, v in dict(state.get("supplementary", {})).items()},
        "moderator_summary": str(minutes_data.get("summary", "")),
    }
    if warnings:
        supplementary["context_warning"] = " | ".join(warnings)

    pending_user_decisions = [
        *[str(item) for item in minutes_data.get("pending_user_decisions", [])],
        *[str(item) for item in state.get("pending_user_decisions", [])],
    ]

    req_suffix = requirement_id.split("_")[-1]
    minutes = MeetingMinutes(
        id=f"meeting_{req_suffix}",
        requirement_id=requirement_id,
        title=str(minutes_data.get("title", "Meeting Notes")),
        agenda=[str(item) for item in state.get("agenda", [])],
        attendees=[str(item) for item in state.get("validated_attendees", [])],
        opinions=[
            AgentOpinion(
                agent_role=str(opinion["agent_role"]),
                summary=str(opinion["summary"]),
                proposals=[str(item) for item in opinion.get("proposals", [])],
                risks=[str(item) for item in opinion.get("risks", [])],
                open_questions=[str(item) for item in opinion.get("open_questions", [])],
            )
            for opinion in state.get("opinions", {}).values()
        ],
        consensus_points=[str(item) for item in state.get("consensus_points", [])],
        conflict_points=[str(item) for item in state.get("conflict_points", [])],
        supplementary=supplementary,
        decisions=[str(item) for item in minutes_data.get("decisions", [])],
        action_items=[str(item) for item in minutes_data.get("action_items", [])],
        pending_user_decisions=pending_user_decisions,
        status="completed",
    )

    workspace.meetings.save(minutes)
    return {"node_name": "moderator_minutes", "minutes": minutes.model_dump()}
```

- [ ] **Step 6: Run the focused graph and moderator tests**

Run: `uv run pytest tests/test_meeting_graph.py tests/test_moderator_agent.py tests/test_claude_roles.py -v`
Expected: PASS

- [ ] **Step 7: Commit the runtime repair**

```bash
git add studio/runtime/graph.py studio/agents/moderator.py
git commit -m "fix: repair meeting graph context and conflict flow"
```

---

### Task 4: Verification and Regression Sweep

**Files:**
- Modify: `tests/test_meeting_graph.py`
- Modify: `tests/test_moderator_agent.py`
- Modify: `tests/test_claude_roles.py`

- [ ] **Step 1: Re-run the targeted verification commands**

Run: `uv run pytest tests/test_claude_roles.py tests/test_moderator_agent.py tests/test_meeting_graph.py -v`
Expected: PASS

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest -v`
Expected: PASS (baseline before implementation was `317 passed`; after the feature it should still be fully green, with a higher total test count)

- [ ] **Step 3: Confirm the worktree only contains the intended changes**

Run: `git status --short`
Expected:
```text
 M studio/agents/moderator.py
 M studio/llm/claude_roles.py
 M studio/runtime/graph.py
 M tests/test_claude_roles.py
 M tests/test_meeting_graph.py
 M tests/test_moderator_agent.py
```

- [ ] **Step 4: Commit the final verification pass**

```bash
git add studio/agents/moderator.py studio/llm/claude_roles.py studio/runtime/graph.py tests/test_claude_roles.py tests/test_meeting_graph.py tests/test_moderator_agent.py
git commit -m "test: verify meeting graph context and conflict coverage"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** The plan covers `meeting_context`, attendee validation, unknown-role filtering, compatibility mode warnings, `conflict_resolution_needed`, one `moderator_discussion` round, enriched final minutes, and the test matrix called out in the spec.
- [x] **Placeholder scan:** No `TODO`, `TBD`, or “handle later” placeholders remain; each task lists concrete files, code, and commands.
- [x] **Type consistency:** The plan uses one role key, `moderator_discussion`, one state key set (`meeting_context`, `validated_attendees`, `conflict_resolution_needed`, `supplementary`, `context_warnings`, `pending_user_decisions`), and one supported-role list (`design`, `art`, `dev`, `qa`) throughout.
