from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

import studio.agents.profile_loader as profile_loader
from studio.agents.profile_loader import load_agent_profile
from studio.agents.profile_schema import (
    AgentProfile,
    AgentProfileNotFoundError,
    AgentProfileValidationError,
)


def test_repository_contains_profiles_for_all_managed_agents() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    managed_agents = ("worker", "reviewer", "design", "dev", "qa", "quality", "art", "moderator")
    profiles_root = repo_root / "studio" / "agents" / "profiles"
    claude_agents_root = repo_root / ".claude" / "agents"

    assert profiles_root.is_dir()
    assert claude_agents_root.is_dir()

    checked_in_profiles = {path.stem for path in profiles_root.glob("*.yaml")}
    checked_in_claude_roots = {
        path.name for path in claude_agents_root.iterdir() if path.is_dir()
    }

    assert checked_in_profiles == set(managed_agents)
    assert checked_in_claude_roots == set(managed_agents)

    for agent_name in managed_agents:
        profile_path = profiles_root / f"{agent_name}.yaml"
        claude_root = claude_agents_root / agent_name
        claude_markdown = claude_root / "CLAUDE.md"

        assert profile_path.is_file(), f"missing profile file for {agent_name}"
        assert claude_root.is_dir(), f"missing claude root for {agent_name}"
        assert claude_markdown.is_file(), f"missing CLAUDE.md for {agent_name}"
        claude_markdown_text = claude_markdown.read_text(encoding="utf-8")
        assert agent_name in claude_markdown_text
        assert "belongs only to" in claude_markdown_text

        profile = load_agent_profile(agent_name)

        assert profile.name == agent_name
        assert profile.system_prompt.strip()
        assert profile.claude_project_root == claude_root.resolve()

        raw_profile = profile_path.read_text(encoding="utf-8")
        for required_key in ("name", "enabled", "system_prompt", "claude_project_root", "model", "fallback_policy"):
            assert f"{required_key}:" in raw_profile, f"{required_key} missing for {agent_name}"


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
    claude_root = repo_root / ".claude" / "agents" / "demo"
    claude_root.mkdir(parents=True)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: builder",
                "system_prompt: Stay focused on the brief.",
                "claude_project_root: .claude/agents/demo",
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


def test_loader_rejects_non_mapping_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "- builder\n- still not a mapping\n",
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_loader_rejects_unknown_profile_key_with_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    (repo_root / ".claude" / "agents" / "demo").mkdir(parents=True)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: builder",
                "system_prompt: Stay focused on the brief.",
                "claude_project_root: .claude/agents/demo",
                "unexpected: nope",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError) as exc_info:
        load_agent_profile("builder")

    assert "unexpected" in str(exc_info.value)


def test_loader_rejects_malformed_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "name: [unterminated\n",
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_loader_rejects_empty_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    (repo_root / ".claude" / "agents" / "demo").mkdir(parents=True)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: ''",
                "system_prompt: Stay focused on the brief.",
                "claude_project_root: .claude/agents/demo",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_loader_rejects_name_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    (repo_root / ".claude" / "agents" / "demo").mkdir(parents=True)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: other",
                "system_prompt: Stay focused on the brief.",
                "claude_project_root: .claude/agents/demo",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_loader_rejects_non_string_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    (repo_root / ".claude" / "agents" / "demo").mkdir(parents=True)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: []",
                "system_prompt: Stay focused on the brief.",
                "claude_project_root: .claude/agents/demo",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_loader_rejects_missing_system_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    (repo_root / ".claude" / "agents" / "demo").mkdir(parents=True)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: builder",
                "claude_project_root: .claude/agents/demo",
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
    (repo_root / ".claude" / "agents" / "demo").mkdir(parents=True)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: builder",
                "system_prompt: ''",
                "claude_project_root: .claude/agents/demo",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_schema_rejects_empty_claude_project_root() -> None:
    with pytest.raises(ValidationError):
        AgentProfile.model_validate(
            {
                "name": "builder",
                "system_prompt": "Stay focused on the brief.",
                "claude_project_root": "",
            }
        )


def test_loader_rejects_profile_file_symlink_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    profile_path = repo_root / "studio" / "agents" / "profiles" / "builder.yaml"
    outside_profile = tmp_path / "outside" / "builder.yaml"
    outside_profile.parent.mkdir(parents=True)
    outside_profile.write_text(
        "\n".join(
            [
                "name: builder",
                "system_prompt: Stay focused on the brief.",
                "claude_project_root: .claude/agents/demo",
            ]
        ),
        encoding="utf-8",
    )

    original_resolve = profile_loader.Path.resolve

    def fake_resolve(self: Path, *args: object, **kwargs: object) -> Path:
        if self == profile_path:
            return outside_profile.resolve()
        return original_resolve(self, *args, **kwargs)

    profile_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(profile_loader.Path, "resolve", fake_resolve, raising=False)
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
                "claude_project_root: .claude/agents/missing",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_loader_wraps_unicode_decode_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    profile_path = repo_root / "studio" / "agents" / "profiles" / "builder.yaml"
    profile_path.write_bytes(b"\xff")
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_loader_wraps_os_error_on_profile_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    profile_path = repo_root / "studio" / "agents" / "profiles" / "builder.yaml"
    profile_path.write_text(
        "\n".join(
            [
                "name: builder",
                "system_prompt: Stay focused on the brief.",
                "claude_project_root: .claude/agents/demo",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / ".claude" / "agents" / "demo").mkdir(parents=True)
    _set_loader_module_path(monkeypatch, repo_root)

    original_read_text = profile_loader.Path.read_text

    def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == profile_path:
            raise OSError("boom")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(profile_loader.Path, "read_text", fake_read_text, raising=False)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_loader_wraps_claude_project_root_resolve_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    (repo_root / ".claude" / "agents" / "demo").mkdir(parents=True)
    profile_path = repo_root / "studio" / "agents" / "profiles" / "builder.yaml"
    profile_path.write_text(
        "\n".join(
            [
                "name: builder",
                "system_prompt: Stay focused on the brief.",
                "claude_project_root: .claude/agents/demo",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    original_resolve = profile_loader.Path.resolve
    expected_resolve_target = repo_root / ".claude" / "agents" / "demo"

    def fake_resolve(self: Path, *args: object, **kwargs: object) -> Path:
        if self == expected_resolve_target:
            raise OSError("resolve failed")
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(profile_loader.Path, "resolve", fake_resolve, raising=False)

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


def test_loader_rejects_non_string_agent_name() -> None:
    with pytest.raises(AgentProfileValidationError):
        load_agent_profile(123)  # type: ignore[arg-type]


def test_loader_rejects_directory_profile_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    profile_dir = repo_root / "studio" / "agents" / "profiles" / "builder.yaml"
    profile_dir.mkdir(parents=True)
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileNotFoundError):
        load_agent_profile("builder")


def test_loader_rejects_absolute_claude_root_outside_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: builder",
                "system_prompt: Stay focused on the brief.",
                f"claude_project_root: {outside_root}",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")


def test_loader_rejects_relative_claude_root_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _repo_root(tmp_path)
    (repo_root / "studio" / "agents" / "profiles" / "builder.yaml").write_text(
        "\n".join(
            [
                "name: builder",
                "system_prompt: Stay focused on the brief.",
                "claude_project_root: ../../outside",
            ]
        ),
        encoding="utf-8",
    )
    _set_loader_module_path(monkeypatch, repo_root)

    with pytest.raises(AgentProfileValidationError):
        load_agent_profile("builder")
