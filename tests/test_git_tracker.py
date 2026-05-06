from __future__ import annotations

from pathlib import Path
import subprocess

from studio.storage.git_tracker import GitTracker


def test_git_tracker_defaults_to_sibling_gs_projects_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GAME_STUDIO_PROJECTS_ROOT", raising=False)

    tracker = GitTracker(repo_root=tmp_path, project_id="proj_001")

    assert tracker.repo_root == tmp_path.parent / "GS_projects"
    assert tracker.project_dir == tmp_path.parent / "GS_projects" / "proj_001"


def test_git_tracker_uses_configured_projects_root(tmp_path: Path, monkeypatch) -> None:
    projects_root = tmp_path / "custom-projects"
    monkeypatch.setenv("GAME_STUDIO_PROJECTS_ROOT", str(projects_root))

    tracker = GitTracker(repo_root=tmp_path, project_id="proj_001")

    assert tracker.repo_root == projects_root
    assert tracker.project_dir == projects_root / "proj_001"


def test_git_tracker_reads_projects_root_from_dotenv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GAME_STUDIO_PROJECTS_ROOT", raising=False)
    projects_root = tmp_path / "dotenv-projects"
    (tmp_path / ".env").write_text(f"GAME_STUDIO_PROJECTS_ROOT={projects_root}\n", encoding="utf-8")

    tracker = GitTracker(repo_root=tmp_path, project_id="proj_001")

    assert tracker.repo_root == projects_root
    assert tracker.project_dir == projects_root / "proj_001"


def test_git_tracker_process_env_overrides_dotenv(tmp_path: Path, monkeypatch) -> None:
    dotenv_root = tmp_path / "dotenv-projects"
    env_root = tmp_path / "env-projects"
    (tmp_path / ".env").write_text(f"GAME_STUDIO_PROJECTS_ROOT={dotenv_root}\n", encoding="utf-8")
    monkeypatch.setenv("GAME_STUDIO_PROJECTS_ROOT", str(env_root))

    tracker = GitTracker(repo_root=tmp_path, project_id="proj_001")

    assert tracker.repo_root == env_root
    assert tracker.project_dir == env_root / "proj_001"


def test_git_tracker_detects_files_under_configured_projects_dir(tmp_path: Path, monkeypatch) -> None:
    projects_root = tmp_path / "external-projects"
    monkeypatch.setenv("GAME_STUDIO_PROJECTS_ROOT", str(projects_root))
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / ".gitignore").write_text("projects/\n", encoding="utf-8")

    tracker = GitTracker(repo_root=tmp_path, project_id="proj_001")
    tracker.ensure_project_dir()
    before = tracker.capture_state()

    art_dir = tracker.project_dir / "art"
    art_dir.mkdir(parents=True)
    (art_dir / "ART_GUIDE.md").write_text("# Pixel guide\n", encoding="utf-8")

    diff = tracker.detect_changes(before)

    assert [(change.status, change.path) for change in diff.changed_files] == [
        ("added", "art/ART_GUIDE.md")
    ]


def test_git_tracker_commits_to_projects_repo_not_studio_repo(tmp_path: Path, monkeypatch) -> None:
    studio_root = tmp_path / "Game_Studio"
    studio_root.mkdir()
    subprocess.run(["git", "init"], cwd=studio_root, check=True, capture_output=True, text=True)
    projects_root = tmp_path / "GS_projects"
    monkeypatch.setenv("GAME_STUDIO_PROJECTS_ROOT", str(projects_root))

    tracker = GitTracker(repo_root=studio_root, project_id="proj_001")
    tracker.ensure_project_dir()
    (tracker.project_dir / "README.md").write_text("# Project\n", encoding="utf-8")

    commit = tracker.add_and_commit("Add project")

    assert commit
    assert (projects_root / ".git").exists()
    assert not (studio_root / "projects").exists()
    studio_status = subprocess.run(
        ["git", "status", "--short"],
        cwd=studio_root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert studio_status.stdout == ""
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=projects_root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert tracked.stdout.splitlines() == ["proj_001/README.md"]


def test_git_tracker_adds_configured_remote_without_pushing(tmp_path: Path, monkeypatch) -> None:
    projects_root = tmp_path / "GS_projects"
    monkeypatch.setenv("GAME_STUDIO_PROJECTS_ROOT", str(projects_root))
    monkeypatch.setenv("GAME_STUDIO_PROJECTS_GIT_REMOTE", "https://example.invalid/game-projects.git")

    tracker = GitTracker(repo_root=tmp_path / "Game_Studio", project_id="proj_001")
    tracker.ensure_project_dir()

    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=projects_root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert remote.stdout.strip() == "https://example.invalid/game-projects.git"


def test_git_tracker_reads_remote_from_dotenv(tmp_path: Path, monkeypatch) -> None:
    projects_root = tmp_path / "GS_projects"
    monkeypatch.setenv("GAME_STUDIO_PROJECTS_ROOT", str(projects_root))
    monkeypatch.delenv("GAME_STUDIO_PROJECTS_GIT_REMOTE", raising=False)
    (tmp_path / ".env").write_text(
        "GAME_STUDIO_PROJECTS_GIT_REMOTE=https://example.invalid/dotenv-projects.git\n",
        encoding="utf-8",
    )

    tracker = GitTracker(repo_root=tmp_path, project_id="proj_001")
    tracker.ensure_project_dir()

    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=projects_root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert remote.stdout.strip() == "https://example.invalid/dotenv-projects.git"
