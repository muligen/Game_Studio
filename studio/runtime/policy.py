# studio/runtime/policy.py
from __future__ import annotations

from enum import StrEnum


class RecoveryAction(StrEnum):
    RETRY = "retry"
    ESCALATE = "escalate"
    RESUME = "resume"
    STOP = "stop"


class RecoveryPolicy:
    def __init__(self, max_retries: int = 1) -> None:
        self.max_retries = max_retries

    def resolve(self, error_type: str, attempt: int) -> RecoveryAction:
        if error_type == "tool_failure" and attempt < self.max_retries:
            return RecoveryAction.RETRY
        if error_type in {"quality_gate_failure", "state_conflict"}:
            return RecoveryAction.ESCALATE
        if error_type == "missing_dependency":
            return RecoveryAction.STOP
        return RecoveryAction.RESUME
