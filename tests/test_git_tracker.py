from __future__ import annotations

from pathlib import Path
import subprocess

from studio.storage.git_tracker import GitTracker


def test_git_tracker_detects_files_under_ignored_projects_dir(tmp_path: Path) -> None:
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
