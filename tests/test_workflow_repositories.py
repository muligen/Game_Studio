from pathlib import Path

from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace


def test_workspace_creates_expected_directories(tmp_path: Path) -> None:
    workspace = StudioWorkspace(tmp_path / ".studio-data")
    workspace.ensure_layout()

    assert (tmp_path / ".studio-data" / "requirements").is_dir()
    assert (tmp_path / ".studio-data" / "design_docs").is_dir()
    assert (tmp_path / ".studio-data" / "bugs").is_dir()


def test_requirement_repository_round_trips_cards(tmp_path: Path) -> None:
    workspace = StudioWorkspace(tmp_path / ".studio-data")
    repo = workspace.requirements
    card = RequirementCard(id="req_001", title="Add relic system")

    repo.save(card)
    loaded = repo.get("req_001")

    assert loaded.model_dump() == card.model_dump()


def test_log_repository_lists_saved_entries(tmp_path: Path) -> None:
    workspace = StudioWorkspace(tmp_path / ".studio-data")
    log = workspace.logs.new(
        actor="user",
        action="approve",
        target_type="design_doc",
        target_id="design_001",
        message="approved",
        metadata={},
    )
    workspace.logs.save(log)

    assert [entry.id for entry in workspace.logs.list_all()] == [log.id]
