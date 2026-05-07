from __future__ import annotations

import json
from pathlib import Path

import pytest

from studio.agents.profile_schema import AgentProfile
from studio.llm.project_scope import (
    agent_prompt_context,
    load_agent_settings,
    resolve_agent_project_dir,
)


def _profile(root: Path) -> AgentProfile:
    return AgentProfile(
        name="dev",
        system_prompt="dev prompt",
        claude_project_root=root,
    )


def test_resolve_agent_project_dir_defaults_to_sibling_projects_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GAME_STUDIO_PROJECTS_ROOT", raising=False)

    project_dir = resolve_agent_project_dir(
        project_root=tmp_path / "Game_Studio",
        workspace_root=tmp_path / "Game_Studio" / ".studio-data",
        context={"goal": {"project_id": "proj_001"}},
    )

    assert project_dir == tmp_path / "GS_projects" / "proj_001"
    assert project_dir.exists()


def test_resolve_agent_project_dir_uses_env_configured_projects_root(
    tmp_path: Path, monkeypatch,
) -> None:
    configured = tmp_path / "configured-projects"
    monkeypatch.setenv("GAME_STUDIO_PROJECTS_ROOT", str(configured))

    project_dir = resolve_agent_project_dir(
        project_root=tmp_path / "Game_Studio",
        workspace_root=tmp_path / "Game_Studio" / ".studio-data",
        context={"project_id": "proj_002"},
    )

    assert project_dir == configured / "proj_002"
    assert project_dir.exists()


def test_resolve_agent_project_dir_accepts_explicit_goal_project_dir(tmp_path: Path) -> None:
    explicit = tmp_path / "custom" / "proj_003"

    project_dir = resolve_agent_project_dir(
        project_root=tmp_path / "Game_Studio",
        workspace_root=tmp_path / "Game_Studio" / ".studio-data",
        context={"goal": {"project_dir": str(explicit)}},
    )

    assert project_dir == explicit.resolve()
    assert project_dir.exists()


def test_resolve_agent_project_dir_requires_project_context(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing project context"):
        resolve_agent_project_dir(
            project_root=tmp_path / "Game_Studio",
            workspace_root=tmp_path / "Game_Studio" / ".studio-data",
            context={"goal": {"prompt": "Snake"}},
        )


def test_load_agent_settings_rewrites_relative_hook_commands(tmp_path: Path) -> None:
    agent_root = tmp_path / ".claude" / "agents" / "dev"
    settings_dir = agent_root / ".claude"
    settings_dir.mkdir(parents=True)
    hook = tmp_path / ".claude" / "hooks" / "langfuse_hook.py"
    hook.parent.mkdir(parents=True)
    hook.write_text("# hook\n", encoding="utf-8")
    (settings_dir / "settings.local.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": 'uv run python "../../hooks/langfuse_hook.py"',
                                }
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    settings = load_agent_settings(_profile(agent_root), tmp_path / "project")

    assert settings is not None
    payload = json.loads(settings)
    command = payload["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert str(hook.resolve()) in command
    assert "../../hooks/langfuse_hook.py" not in command


def test_agent_prompt_context_includes_config_and_project_dirs(tmp_path: Path) -> None:
    agent_root = tmp_path / ".claude" / "agents" / "dev"
    agent_root.mkdir(parents=True)
    (agent_root / "CLAUDE.md").write_text("Dev agent instructions", encoding="utf-8")
    project_dir = tmp_path / "projects" / "proj_001"

    text = agent_prompt_context(_profile(agent_root), project_dir)

    assert "Current working directory is the target project" in text
    assert str(project_dir.resolve()) in text
    assert str(agent_root.resolve()) in text
    assert "Dev agent instructions" in text
