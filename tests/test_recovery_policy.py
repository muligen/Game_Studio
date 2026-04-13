# tests/test_recovery_policy.py
from pathlib import Path

from studio.runtime.checkpoints import CheckpointManager
from studio.runtime.policy import RecoveryAction, RecoveryPolicy
from studio.schemas.runtime import RuntimeState


def test_checkpoint_manager_round_trips_runtime_state(tmp_path: Path) -> None:
    manager = CheckpointManager(tmp_path / "checkpoints")
    state = RuntimeState(
        project_id="demo-project",
        run_id="run-001",
        task_id="task-001",
        goal={"prompt": "Design a game"},
    )
    manager.save("planner", state)
    restored = manager.load("planner")
    assert restored.run_id == "run-001"


def test_recovery_policy_maps_error_types_to_actions() -> None:
    policy = RecoveryPolicy(max_retries=1)
    assert policy.resolve("tool_failure", attempt=0) is RecoveryAction.RETRY
    assert policy.resolve("quality_gate_failure", attempt=1) is RecoveryAction.ESCALATE
