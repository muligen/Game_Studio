from __future__ import annotations

import json
from pathlib import Path


class MemoryStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, bucket: str, key: str, value: dict[str, object]) -> None:
        bucket_dir = self.root / bucket
        bucket_dir.mkdir(parents=True, exist_ok=True)
        (bucket_dir / f"{key}.json").write_text(
            json.dumps(value, indent=2),
            encoding="utf-8",
        )

    def get(self, bucket: str, key: str) -> dict[str, object]:
        target = self.root / bucket / f"{key}.json"
        return json.loads(target.read_text(encoding="utf-8"))
