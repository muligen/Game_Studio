# studio/runtime/checkpoints.py
from __future__ import annotations

import json
from pathlib import Path

from studio.schemas.runtime import RuntimeState


class CheckpointManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, node_name: str, state: RuntimeState) -> None:
        target = self.root / f"{node_name}.json"
        target.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    def load(self, node_name: str) -> RuntimeState:
        payload = json.loads((self.root / f"{node_name}.json").read_text(encoding="utf-8"))
        return RuntimeState.model_validate(payload)
