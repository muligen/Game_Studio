from __future__ import annotations

import json

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
