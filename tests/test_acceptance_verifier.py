from __future__ import annotations

import json
import subprocess
from pathlib import Path

from studio.runtime import acceptance_verifier
from studio.runtime.acceptance_verifier import detect_node_commands, verify_project


def test_detect_node_commands_prefers_npm_ci_for_package_lock(tmp_path):
    project_dir = tmp_path / "proj_001"
    project_dir.mkdir()
    (project_dir / "package-lock.json").write_text("{}", encoding="utf-8")
    (project_dir / "package.json").write_text(
        json.dumps({"scripts": {"build": "vite build", "test": "vitest run", "preview": "vite preview"}}),
        encoding="utf-8",
    )

    commands = detect_node_commands(project_dir)

    assert commands.install == ["npm", "ci"]
    assert commands.build == ["npm", "run", "build"]
    assert commands.test == ["npm", "run", "test"]
    assert commands.preview == ["npm", "run", "preview"]


def test_verify_project_fails_when_package_json_missing(tmp_path):
    project_dir = tmp_path / "proj_001"
    project_dir.mkdir()

    result = verify_project(project_dir, artifacts_root=tmp_path / "artifacts", run_id="acc_run_001")

    assert result.startup_ok is False
    assert any("package.json" in error for error in result.errors)
    assert result.evidence


def test_verify_project_accepts_standalone_html_project(tmp_path, monkeypatch):
    from studio.schemas.acceptance import AcceptanceEvidence

    project_dir = tmp_path / "proj_001"
    project_dir.mkdir()
    (project_dir / "index.html").write_text("<main data-game-root>Ready</main>", encoding="utf-8")

    def fake_static_browser(*args, **kwargs):
        return True, [
            AcceptanceEvidence(
                id="ev_static_html",
                evidence_type="playwright",
                summary="Playwright opened standalone index.html.",
            )
        ], []

    monkeypatch.setattr(
        "studio.runtime.acceptance_verifier._run_static_html_smoke",
        fake_static_browser,
        raising=False,
    )

    result = verify_project(project_dir, artifacts_root=tmp_path / "artifacts", run_id="acc_run_static")

    assert result.startup_ok is True
    assert result.browser_ok is True
    assert any(e.id == "ev_static_html" for e in result.evidence)


def test_verify_project_accepts_nested_game_index_html_project(tmp_path, monkeypatch):
    from studio.schemas.acceptance import AcceptanceEvidence

    project_dir = tmp_path / "proj_001"
    game_dir = project_dir / "game"
    game_dir.mkdir(parents=True)
    (game_dir / "index.html").write_text("<canvas data-game-root></canvas>", encoding="utf-8")
    opened_paths: list[Path] = []

    def fake_static_browser(project_dir_arg, artifacts_dir_arg, index_path):
        opened_paths.append(index_path)
        return True, [
            AcceptanceEvidence(
                id="ev_nested_static_html",
                evidence_type="playwright",
                summary="Playwright opened nested game/index.html.",
            )
        ], []

    monkeypatch.setattr(
        "studio.runtime.acceptance_verifier._run_static_html_smoke",
        fake_static_browser,
        raising=False,
    )

    result = verify_project(project_dir, artifacts_root=tmp_path / "artifacts", run_id="acc_run_nested_static")

    assert result.startup_ok is True
    assert result.browser_ok is True
    assert opened_paths == [game_dir / "index.html"]
    assert any(e.id == "ev_nested_static_html" for e in result.evidence)


def test_verify_project_uses_browser_result(tmp_path, monkeypatch):
    from studio.schemas.acceptance import AcceptanceEvidence

    project_dir = tmp_path / "proj_001"
    project_dir.mkdir()
    (project_dir / "package.json").write_text(
        json.dumps({"scripts": {"preview": "vite preview"}}),
        encoding="utf-8",
    )

    def fake_browser(*args, **kwargs):
        return True, [
            AcceptanceEvidence(
                id="ev_browser_opened",
                evidence_type="playwright",
                summary="Browser opened the page.",
            )
        ], []

    monkeypatch.setattr("studio.runtime.acceptance_verifier._run_playwright_smoke", fake_browser)

    result = verify_project(project_dir, artifacts_root=tmp_path / "artifacts", run_id="acc_run_001")

    assert result.browser_ok is True
    assert result.startup_ok is True


def test_optional_command_resolves_windows_npm_shim(tmp_path, monkeypatch):
    from studio.schemas.acceptance import AcceptanceEvidence

    project_dir = tmp_path / "proj_001"
    artifacts_dir = tmp_path / "artifacts"
    project_dir.mkdir()
    artifacts_dir.mkdir()
    captured: dict[str, list[str]] = {}
    captured_kwargs: dict[str, object] = {}

    def fake_which(executable: str) -> str | None:
        if executable == "npm":
            return "C:/node/npm.cmd"
        return None

    def fake_run(command, **kwargs):
        captured["command"] = [str(item) for item in command]
        captured_kwargs.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout=None, stderr=None)

    monkeypatch.setattr(acceptance_verifier.os, "name", "nt")
    monkeypatch.setattr(acceptance_verifier.shutil, "which", fake_which)
    monkeypatch.setattr(acceptance_verifier.subprocess, "run", fake_run)

    evidence: list[AcceptanceEvidence] = []
    errors: list[str] = []
    ok = acceptance_verifier._run_optional_command(
        project_dir,
        artifacts_dir,
        "test",
        ["npm", "run", "test"],
        evidence,
        errors,
    )

    assert ok is True
    assert captured["command"][0] == "C:/node/npm.cmd"
    assert captured_kwargs["encoding"] == "utf-8"
    assert captured_kwargs["errors"] == "replace"
    assert (artifacts_dir / "test.log").read_text(encoding="utf-8") == "\n"
    assert errors == []


def test_playwright_smoke_resolves_windows_preview_shim(tmp_path, monkeypatch):
    from studio.schemas.acceptance import AcceptanceEvidence

    project_dir = tmp_path / "proj_001"
    artifacts_dir = tmp_path / "artifacts"
    project_dir.mkdir()
    artifacts_dir.mkdir()
    captured: dict[str, list[str]] = {}
    captured_kwargs: dict[str, object] = {}

    class FakeProcess:
        def terminate(self):
            return None

        def communicate(self, timeout=None):
            return "preview log", None

    def fake_which(executable: str) -> str | None:
        if executable == "npm":
            return "C:/node/npm.cmd"
        return None

    def fake_popen(command, **kwargs):
        captured["command"] = [str(item) for item in command]
        captured_kwargs.update(kwargs)
        return FakeProcess()

    def fake_node_smoke(**kwargs):
        return True, [
            AcceptanceEvidence(
                id=kwargs["evidence_id"],
                evidence_type="playwright",
                summary=kwargs["summary"],
            )
        ], []

    monkeypatch.setattr(acceptance_verifier.os, "name", "nt")
    monkeypatch.setattr(acceptance_verifier.shutil, "which", fake_which)
    monkeypatch.setattr(acceptance_verifier.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(acceptance_verifier, "_run_node_playwright_smoke", fake_node_smoke)

    ok, _evidence, errors = acceptance_verifier._run_playwright_smoke(
        project_dir,
        artifacts_dir,
        ["npm", "run", "preview"],
    )

    assert ok is True
    assert captured["command"][0] == "C:/node/npm.cmd"
    assert captured_kwargs["encoding"] == "utf-8"
    assert captured_kwargs["errors"] == "replace"
    assert errors == []


def test_node_playwright_smoke_runs_artifact_script_by_absolute_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir()
    captured: dict[str, list[str]] = {}

    def fake_run(command, **kwargs):
        captured["command"] = [str(item) for item in command]
        result_path = Path(command[-1])
        result_path.write_text(
            json.dumps({"consoleErrors": [], "pageErrors": [], "visibleSurface": True}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(acceptance_verifier.subprocess, "run", fake_run)

    ok, _evidence, errors = acceptance_verifier._run_node_playwright_smoke(
        artifacts_dir=artifacts_dir,
        url="http://127.0.0.1:1234",
        evidence_id="ev_playwright",
        summary="smoke",
        screenshot_name="startup.png",
    )

    assert ok is True
    assert Path(captured["command"][1]).is_absolute()
    assert captured["command"][1].endswith("playwright-smoke.mjs")
    script_text = (artifacts_dir / "playwright-smoke.mjs").read_text(encoding="utf-8")
    assert "createRequire" in script_text
    assert "require('playwright')" in script_text
    assert errors == []


def test_node_playwright_smoke_reports_timeout_as_validation_failure(tmp_path, monkeypatch):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(acceptance_verifier.subprocess, "run", fake_run)

    ok, evidence, errors = acceptance_verifier._run_node_playwright_smoke(
        artifacts_dir=artifacts_dir,
        url="http://127.0.0.1:1234",
        evidence_id="ev_playwright",
        summary="smoke",
        screenshot_name="startup.png",
    )

    assert ok is False
    assert "timed out" in errors[0]
    assert evidence[0].id == "ev_playwright"
    assert evidence[0].artifact_path is not None


def test_static_html_smoke_uses_bounded_local_server(tmp_path, monkeypatch):
    from studio.schemas.acceptance import AcceptanceEvidence

    project_dir = tmp_path / "proj_001"
    project_dir.mkdir()
    index_path = project_dir / "index.html"
    index_path.write_text("<script type='module' src='js/app.js'></script><main></main>", encoding="utf-8")
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    popen_calls: list[list[str]] = []
    opened_urls: list[str] = []

    class FakeProcess:
        terminated = False
        killed = False

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

        def communicate(self, timeout=None):
            return "server log", None

    fake_process = FakeProcess()

    def fake_popen(command, **kwargs):
        popen_calls.append([str(item) for item in command])
        return fake_process

    def fake_node_smoke(*, artifacts_dir, url, evidence_id, summary, screenshot_name):
        opened_urls.append(url)
        return True, [
            AcceptanceEvidence(
                id=evidence_id,
                evidence_type="playwright",
                summary=summary,
                artifact_path=str(artifacts_dir / screenshot_name),
            )
        ], []

    monkeypatch.setattr(acceptance_verifier.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(acceptance_verifier, "_run_node_playwright_smoke", fake_node_smoke)

    ok, evidence, errors = acceptance_verifier._run_static_html_smoke(
        project_dir,
        artifacts_dir,
        index_path,
    )

    assert ok is True
    assert errors == []
    assert popen_calls[0][1:3] == ["-m", "http.server"]
    assert "--bind" in popen_calls[0]
    assert opened_urls[0].startswith("http://127.0.0.1:")
    assert opened_urls[0].endswith("/index.html")
    assert fake_process.terminated is True
    assert (artifacts_dir / "static-server.log").read_text(encoding="utf-8") == "server log"
    assert any(item.id == "ev_static_html_server" for item in evidence)
