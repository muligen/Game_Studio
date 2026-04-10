from __future__ import annotations

import json
import sys
from pathlib import Path

from studio.schemas.artifact import ArtifactRecord

_WIN_RESERVED_DEVICE_NAMES = frozenset(
    ("CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10)))
)


class ArtifactRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _validate_artifact_id(self, artifact_id: str) -> None:
        if artifact_id in (".", ".."):
            raise ValueError("artifact_id must not be a path component '.' or '..'")
        if "/" in artifact_id or "\\" in artifact_id:
            raise ValueError("artifact_id must not contain path separators")
        if sys.platform == "win32" and ":" in artifact_id:
            raise ValueError("artifact_id must not contain ':'")
        if Path(artifact_id).name != artifact_id:
            raise ValueError("artifact_id must be a single path segment")
        if sys.platform == "win32" and artifact_id.upper() in _WIN_RESERVED_DEVICE_NAMES:
            raise ValueError("artifact_id must not be a Windows reserved device name")

    def _artifact_file(self, artifact_id: str) -> Path:
        self._validate_artifact_id(artifact_id)
        root = self.root.resolve()
        target = (root / f"{artifact_id}.json").resolve()
        if target.parent != root:
            raise ValueError("artifact_id resolves outside the registry root")
        return target

    def _load_from_path(self, path: Path) -> ArtifactRecord:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ArtifactRecord.model_validate(payload)

    def _max_version_for_parent(self, parent_id: str) -> int:
        m = 0
        for path in self.root.glob("*.json"):
            try:
                rec = self._load_from_path(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if rec.parent_artifact_id == parent_id:
                m = max(m, rec.version)
        return m

    def save(self, artifact: ArtifactRecord) -> ArtifactRecord:
        target = self._artifact_file(artifact.artifact_id)
        if target.exists():
            raise FileExistsError(str(target))

        version = 1
        if artifact.parent_artifact_id is not None:
            self._validate_artifact_id(artifact.parent_artifact_id)
            parent = self.load(artifact.parent_artifact_id)
            sibling_max = self._max_version_for_parent(artifact.parent_artifact_id)
            version = max(parent.version, sibling_max) + 1

        stored = artifact.model_copy(update={"version": version})
        target.write_text(stored.model_dump_json(indent=2), encoding="utf-8")
        return stored

    def load(self, artifact_id: str) -> ArtifactRecord:
        target = self._artifact_file(artifact_id)
        payload = json.loads(target.read_text(encoding="utf-8"))
        return ArtifactRecord.model_validate(payload)
