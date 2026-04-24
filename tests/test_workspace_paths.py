from __future__ import annotations

from pathlib import Path

from studio.api.workspace_paths import resolve_project_root, resolve_workspace_root


def test_resolve_relative_workspace_against_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    assert resolve_project_root(".") == repo_root
    assert resolve_workspace_root(".") == repo_root / ".studio-data"


def test_resolve_relative_studio_data_against_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    assert resolve_project_root(".studio-data") == repo_root
    assert resolve_workspace_root(".studio-data") == repo_root / ".studio-data"


def test_preserves_absolute_workspace_paths() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    studio_data = repo_root / ".studio-data"

    assert resolve_project_root(str(repo_root)) == repo_root
    assert resolve_workspace_root(str(repo_root)) == studio_data
    assert resolve_project_root(str(studio_data)) == repo_root
    assert resolve_workspace_root(str(studio_data)) == studio_data
