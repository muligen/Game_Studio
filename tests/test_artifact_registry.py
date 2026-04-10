import sys
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    "bad_id",
    ["../escape", "..\\escape", "..", "a/b", "a\\b"],
)
def test_registry_rejects_path_traversal_in_artifact_id(tmp_path: Path, bad_id: str) -> None:
    registry = ArtifactRegistry(tmp_path / "artifacts")
    rec = ArtifactRecord(
        artifact_id="safe-001",
        artifact_type="design_brief",
        source_node="worker",
        payload={},
    )
    registry.save(rec)

    with pytest.raises(ValueError):
        registry.load(bad_id)

    evil = ArtifactRecord(
        artifact_id=bad_id,
        artifact_type="design_brief",
        source_node="worker",
        payload={},
    )
    with pytest.raises(ValueError):
        registry.save(evil)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows reserved path character")
def test_registry_rejects_colon_in_artifact_id_on_windows(tmp_path: Path) -> None:
    registry = ArtifactRegistry(tmp_path / "artifacts")
    evil = ArtifactRecord(
        artifact_id="c:evil",
        artifact_type="design_brief",
        source_node="worker",
        payload={},
    )
    with pytest.raises(ValueError):
        registry.save(evil)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows reserved device names")
def test_registry_rejects_windows_reserved_device_names(tmp_path: Path) -> None:
    registry = ArtifactRegistry(tmp_path / "artifacts")
    for reserved in ("NUL", "con", "COM1"):
        rec = ArtifactRecord(
            artifact_id=reserved,
            artifact_type="design_brief",
            source_node="worker",
            payload={},
        )
        with pytest.raises(ValueError, match="reserved"):
            registry.save(rec)


def test_registry_rejects_overwrite_of_existing_artifact_id(tmp_path: Path) -> None:
    registry = ArtifactRegistry(tmp_path / "artifacts")
    rec = ArtifactRecord(
        artifact_id="same-id",
        artifact_type="design_brief",
        source_node="worker",
        payload={"n": 1},
    )
    registry.save(rec)
    again = ArtifactRecord(
        artifact_id="same-id",
        artifact_type="design_brief",
        source_node="worker",
        payload={"n": 2},
    )
    with pytest.raises(FileExistsError):
        registry.save(again)


def test_registry_rejects_traversal_in_parent_artifact_id_on_save(tmp_path: Path) -> None:
    registry = ArtifactRegistry(tmp_path / "artifacts")
    child = ArtifactRecord(
        artifact_id="child-safe",
        artifact_type="design_brief",
        source_node="worker",
        parent_artifact_id="../root",
        payload={},
    )
    with pytest.raises(ValueError):
        registry.save(child)


def test_registry_assigns_distinct_versions_to_siblings_with_same_parent(tmp_path: Path) -> None:
    registry = ArtifactRegistry(tmp_path / "artifacts")
    parent = ArtifactRecord(
        artifact_id="root-001",
        artifact_type="design_brief",
        source_node="worker",
        payload={},
    )
    c1 = ArtifactRecord(
        artifact_id="child-001",
        artifact_type="design_brief",
        source_node="a",
        parent_artifact_id="root-001",
        payload={},
    )
    c2 = ArtifactRecord(
        artifact_id="child-002",
        artifact_type="design_brief",
        source_node="b",
        parent_artifact_id="root-001",
        payload={},
    )
    registry.save(parent)
    s1 = registry.save(c1)
    s2 = registry.save(c2)
    assert s1.version == 2
    assert s2.version == 3
