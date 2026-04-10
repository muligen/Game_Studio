from __future__ import annotations

import json
from pathlib import Path

from studio.schemas.artifact import ArtifactRecord


class ArtifactRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, artifact: ArtifactRecord) -> ArtifactRecord:
        version = 1
        if artifact.parent_artifact_id is not None:
            parent = self.load(artifact.parent_artifact_id)
            version = parent.version + 1

        stored = artifact.model_copy(update={"version": version})
        target = self.root / f"{stored.artifact_id}.json"
        target.write_text(stored.model_dump_json(indent=2), encoding="utf-8")
        return stored

    def load(self, artifact_id: str) -> ArtifactRecord:
        target = self.root / f"{artifact_id}.json"
        payload = json.loads(target.read_text(encoding="utf-8"))
        return ArtifactRecord.model_validate(payload)
