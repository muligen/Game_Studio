import warnings
from pathlib import Path

from studio.memory.store import MemoryStore


def test_memory_store_saves_project_and_run_entries(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.put("project", "world-rules", {"tone": "hopeful", "camera": "top-down"})
    store.put("run", "run-001-summary", {"summary": "planner selected the demo graph"})

    assert store.get("project", "world-rules")["tone"] == "hopeful"
    assert store.get("run", "run-001-summary")["summary"] == "planner selected the demo graph"


def test_put_warns_on_overwrite(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.put("project", "key-a", {"v": 1})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        store.put("project", "key-a", {"v": 2})
    assert len(caught) == 1
    assert "overwritten" in str(caught[0].message).lower()
    assert store.get("project", "key-a")["v"] == 2


def test_get_raises_on_missing_entry(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    import pytest

    with pytest.raises(FileNotFoundError, match="not found"):
        store.get("missing-bucket", "missing-key")


def test_rejects_path_traversal_bucket(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    import pytest

    with pytest.raises(ValueError, match="path separators"):
        store.put("../escape", "key", {"bad": True})


def test_rejects_path_traversal_key(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    import pytest

    with pytest.raises(ValueError, match="path separators"):
        store.put("bucket", "../../etc/passwd", {"bad": True})


def test_rejects_windows_reserved_name(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    import pytest

    with pytest.raises(ValueError, match="reserved"):
        store.put("CON", "key", {"bad": True})


def test_rejects_empty_bucket(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    import pytest

    with pytest.raises(ValueError, match="non-empty"):
        store.put("", "key", {"bad": True})
