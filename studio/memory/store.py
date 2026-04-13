from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

_WINDOWS_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})

_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*$")


def _validate_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    if value.upper() in _WINDOWS_RESERVED:
        raise ValueError(f"{label} must not be a Windows reserved name: {value!r}")
    if ".." in value or "/" in value or "\\" in value:
        raise ValueError(f"{label} must not contain path separators or '..': {value!r}")
    if not _SAFE_ID_PATTERN.match(value):
        raise ValueError(f"{label} contains unsafe characters: {value!r}")
    return value


class MemoryStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, bucket: str, key: str, value: dict[str, object]) -> None:
        bucket = _validate_id(bucket, "bucket")
        key = _validate_id(key, "key")
        bucket_dir = self.root / bucket
        bucket_dir.mkdir(parents=True, exist_ok=True)
        target = bucket_dir / f"{key}.json"
        if target.exists():
            warnings.warn(
                f"Memory entry {bucket}/{key} already exists and will be overwritten",
                stacklevel=2,
            )
        target.write_text(
            json.dumps(value, indent=2),
            encoding="utf-8",
        )

    def get(self, bucket: str, key: str) -> dict[str, object]:
        bucket = _validate_id(bucket, "bucket")
        key = _validate_id(key, "key")
        target = self.root / bucket / f"{key}.json"
        if not target.exists():
            raise FileNotFoundError(f"Memory entry not found: {bucket}/{key}")
        return json.loads(target.read_text(encoding="utf-8"))
