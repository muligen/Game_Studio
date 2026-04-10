from pathlib import Path

from studio.artifacts.registry import ArtifactRegistry
from studio.schemas.artifact import ArtifactRecord


def test_registry_versions_artifacts_by_parent(tmp_path: Path) -> None:
    registry = ArtifactRegistry(tmp_path / "artifacts")
    first = ArtifactRecord(
        artifact_id="concept-001",
        artifact_type="design_brief",
        source_node="worker",
        payload={"title": "Dungeon Bloom"},
    )
    second = ArtifactRecord(
        artifact_id="concept-002",
        artifact_type="design_brief",
        source_node="reviewer",
        parent_artifact_id="concept-001",
        payload={"title": "Dungeon Bloom Revised"},
    )

    stored_first = registry.save(first)
    stored_second = registry.save(second)

    assert stored_first.version == 1
    assert stored_second.version == 2
    assert registry.load("concept-002").parent_artifact_id == "concept-001"
