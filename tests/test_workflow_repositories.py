from pathlib import Path

import pytest
from pydantic import BaseModel

from studio.schemas.requirement import RequirementCard
from studio.storage.workspace import StudioWorkspace
from studio.storage.base import JsonRepository


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


@pytest.mark.parametrize(
    "object_id",
    [
        "CON",
        "prn",
        "NUL",
        "AUX",
        "COM1",
        "LPT9",
        "NUL.txt",
        "CON.foo",
        "COM1.bar",
        "LPT1.json",
    ],
)
def test_repository_rejects_reserved_windows_device_names(
    tmp_path: Path, object_id: str
) -> None:
    repo = JsonRepository(tmp_path / "repo", RequirementCard)

    with pytest.raises(ValueError, match="Windows reserved device name"):
        repo._path_for(object_id)


def test_repository_save_is_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = JsonRepository(tmp_path / "repo", RequirementCard)
    card = RequirementCard(id="req_001", title="Add relic system")

    original_write_text = Path.write_text

    def guarded_write_text(self: Path, data: str, encoding: str | None = None, errors: str | None = None):
        if self.suffix == ".json":
            raise AssertionError("save() wrote directly to the final file")
        return original_write_text(self, data, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "write_text", guarded_write_text)

    repo.save(card)

    assert repo.get("req_001").model_dump() == card.model_dump()


def test_repository_list_all_skips_malformed_json(tmp_path: Path) -> None:
    repo = JsonRepository(tmp_path / "repo", RequirementCard)
    valid = RequirementCard(id="req_001", title="Add relic system")
    repo.save(valid)
    (repo.root / "broken.json").write_text("{not-json", encoding="utf-8")

    assert [card.id for card in repo.list_all()] == ["req_001"]


def test_repository_save_rejects_models_without_id(tmp_path: Path) -> None:
    class NoIdCard(BaseModel):
        title: str

    repo = JsonRepository(tmp_path / "repo", NoIdCard)

    with pytest.raises(ValueError, match="must define an 'id' field"):
        repo.save(NoIdCard(title="oops"))
