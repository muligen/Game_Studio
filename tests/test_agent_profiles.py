from __future__ import annotations

from pathlib import Path

import pytest

import studio.agents.profile_loader as profile_loader
from studio.agents.profile_loader import load_agent_profile
from studio.agents.profile_schema import (
    AgentProfile,
    AgentProfileNotFoundError,
    AgentProfileValidationError,
)


def _repo_root(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "studio" / "agents" / "profiles").mkdir(parents=True)
    return repo_root


def _set_loader_module_path(monkeypatch: pytest.MonkeyPatch, repo_root: Path) -> None:
    monkeypatch.setattr(
        profile_loader,
        "__file__",
        str(repo_root / "studio" / "agents" / "profile_loader.py"),
    )


def test_loader_reads_valid_profile_and_resolves_relative_claude_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    claude_root = repo_root / ".claude" / "profiles" / "demo"
    claude_root.mkdir(parents=True)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: builder",
                "system_prompt: Stay focused on the brief.",
                "claude_project_root: .claude/profiles/demo",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    profile = load_agent_profile("builder")

    assert isinstance(profile, AgentProfile)
    assert profile.name == "builder"
    assert profile.system_prompt == "Stay focused on the brief."
    assert profile.claude_project_root == claude_root.resolve()


def test_loader_rejects_missing_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileNotFoundError):
        load_agent_profile("missing")


def test_loader_rejects_missing_system_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    (repo_root / ".claude" / "profiles" / "demo").mkdir(parents=True)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: builder",
                "claude_project_root: .claude/profiles/demo",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_loader_rejects_empty_system_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    (repo_root / ".claude" / "profiles" / "demo").mkdir(parents=True)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: builder",
                "system_prompt: ''",
                "claude_project_root: .claude/profiles/demo",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_loader_rejects_missing_claude_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: builder",
                "system_prompt: Stay focused on the brief.",
                "claude_project_root: .claude/profiles/missing",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_loader_rejects_empty_claude_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: builder",
                "system_prompt: Stay focused on the brief.",
                "claude_project_root: ''",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_loader_rejects_malformed_claude_project_root_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: builder",
                "system_prompt: Stay focused on the brief.",
                "claude_project_root: []",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_loader_rejects_agent_name_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("../builder")


def test_loader_rejects_directory_profile_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    profile_dir = repo_root / "studio" / "agents" / "profiles" / "builder.yaml"
    profile_dir.mkdir(parents=True)
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileNotFoundError):
        load_agent_profile("builder")
