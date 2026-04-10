from pathlib import Path

from studio.memory.store import MemoryStore


def test_memory_store_saves_project_and_run_entries(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.put("project", "world-rules", {"tone": "hopeful", "camera": "top-down"})
    store.put("run", "run-001-summary", {"summary": "planner selected the demo graph"})

    assert store.get("project", "world-rules")["tone"] == "hopeful"
    assert store.get("run", "run-001-summary")["summary"] == "planner selected the demo graph"
