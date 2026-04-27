"""Git-based file change tracking for agent execution.

Captures file state before and after agent runs, detects changes,
and commits them with descriptive messages.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileChange:
    path: str
    status: str  # "added", "modified", "deleted"

    def __str__(self) -> str:
        return f"{self.status}: {self.path}"


@dataclass(frozen=True)
class GitDiffResult:
    changed_files: list[FileChange] = field(default_factory=list)

    @property
    def files_added(self) -> int:
        return sum(1 for c in self.changed_files if c.status == "added")

    @property
    def files_modified(self) -> int:
        return sum(1 for c in self.changed_files if c.status == "modified")

    @property
    def files_deleted(self) -> int:
        return sum(1 for c in self.changed_files if c.status == "deleted")

    @property
    def has_changes(self) -> bool:
        return len(self.changed_files) > 0


class GitTracker:
    """Tracks file changes in a project directory using git."""

    def __init__(self, repo_root: Path, project_id: str) -> None:
        self.repo_root = repo_root.resolve()
        self.project_id = project_id
        self.project_dir = self.repo_root / "projects" / project_id

    def ensure_project_dir(self) -> Path:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        return self.project_dir

    def _run_git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(self.repo_root),
            check=True,
            capture_output=True,
            text=True,
        )

    def _git_init_if_needed(self) -> None:
        if not (self.repo_root / ".git").exists():
            self._run_git("init")
            logger.info("Initialized git repo at %s", self.repo_root)

    def _git_ls_files(self, pathspec: str) -> dict[str, str]:
        try:
            proc = self._run_git("ls-files", "-s", "--", pathspec)
        except subprocess.CalledProcessError:
            return {}

        state: dict[str, str] = {}
        for line in proc.stdout.splitlines():
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            meta, filepath = parts
            stage_parts = meta.split()
            if len(stage_parts) >= 2:
                state[filepath] = stage_parts[1]
        return state

    def _git_add_untracked(self, pathspec: str) -> None:
        try:
            self._run_git("add", "--intent-to-add", "--", pathspec)
        except subprocess.CalledProcessError:
            pass

    def capture_state(self) -> dict[str, str]:
        self._git_init_if_needed()

        rel = f"projects/{self.project_id}"
        self._git_add_untracked(rel)
        return self._git_ls_files(rel)

    def detect_changes(self, pre_state: dict[str, str]) -> GitDiffResult:
        post_state = self.capture_state()

        changed: list[FileChange] = []
        for path in sorted(set(pre_state) | set(post_state)):
            pre_hash = pre_state.get(path)
            post_hash = post_state.get(path)

            if pre_hash is None and post_hash is not None:
                changed.append(FileChange(path=path, status="added"))
            elif pre_hash is not None and post_hash is None:
                changed.append(FileChange(path=path, status="deleted"))
            elif pre_hash != post_hash:
                changed.append(FileChange(path=path, status="modified"))

        return GitDiffResult(changed_files=changed)

    def add_and_commit(self, message: str) -> str:
        rel = f"projects/{self.project_id}"
        self._run_git("add", "--", rel)

        try:
            proc = self._run_git("commit", "-m", message, "--", rel)
        except subprocess.CalledProcessError as exc:
            if "nothing to commit" in (exc.stdout or "") + (exc.stderr or ""):
                logger.debug("Nothing to commit for %s", rel)
                return ""
            raise

        for line in proc.stdout.splitlines():
            if line.startswith("["):
                tokens = line.split()
                if len(tokens) >= 2:
                    return tokens[1].rstrip("]")
        return ""
