from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return _json_ready(value.model_dump())
    if hasattr(value, "__dict__"):
        return _json_ready(vars(value))
    return str(value)


class LlmRunLogger:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        run_id: str,
        node_name: str,
        prompt: str,
        context: dict[str, object],
        reply: Any,
        metadata: dict[str, object] | None = None,
    ) -> None:
        target = self.root / f"{run_id}.json"
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "node_name": node_name,
            "prompt": _json_ready(prompt),
            "context": _json_ready(context),
            "reply": _json_ready(reply),
        }
        if metadata:
            payload["metadata"] = _json_ready(metadata)
        if target.exists():
            entries = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        else:
            entries = []
        entries.append(payload)
        target.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
