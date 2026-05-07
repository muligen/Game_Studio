from __future__ import annotations

from typing import Any

_WORKER_EXPORTS = {
    "ClaudeWorkerAdapter",
    "ClaudeWorkerConfig",
    "ClaudeWorkerError",
    "ClaudeWorkerPayload",
}
_ROLE_EXPORTS = {
    "ArtPayload",
    "ClaudeRoleAdapter",
    "ClaudeRoleConfig",
    "ClaudeRoleError",
    "DeliveryPlannerPayload",
    "DesignPayload",
    "DevPayload",
    "QaPayload",
    "QualityPayload",
    "RequirementClarifierPayload",
    "ReviewerPayload",
    "WorkerPayload",
    "parse_role_payload",
}

__all__ = sorted([*_WORKER_EXPORTS, *_ROLE_EXPORTS])


def __getattr__(name: str) -> Any:
    if name in _WORKER_EXPORTS:
        from . import claude_worker

        return getattr(claude_worker, name)
    if name in _ROLE_EXPORTS:
        from . import claude_roles

        return getattr(claude_roles, name)
    raise AttributeError(f"module 'studio.llm' has no attribute {name!r}")
