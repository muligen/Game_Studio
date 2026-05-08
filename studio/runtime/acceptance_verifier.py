from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from studio.schemas.acceptance import AcceptanceEvidence


@dataclass(frozen=True)
class NodeCommands:
    install: list[str] | None
    build: list[str] | None
    test: list[str] | None
    preview: list[str] | None


@dataclass
class VerificationResult:
    startup_ok: bool
    build_ok: bool | None = None
    test_ok: bool | None = None
    browser_ok: bool | None = None
    evidence: list[AcceptanceEvidence] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def detect_node_commands(project_dir: Path) -> NodeCommands:
    package_json = project_dir / "package.json"
    if not package_json.exists():
        return NodeCommands(install=None, build=None, test=None, preview=None)
    data = json.loads(package_json.read_text(encoding="utf-8"))
    scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
    package_manager = _package_manager(project_dir)
    install = _install_command(project_dir, package_manager)
    build = [package_manager, "run", "build"] if "build" in scripts else None
    test = [package_manager, "run", "test"] if _has_real_test_script(scripts) else None
    preview_script = next((name for name in ("preview", "start", "dev") if name in scripts), None)
    preview = [package_manager, "run", preview_script] if preview_script else None
    return NodeCommands(install=install, build=build, test=test, preview=preview)


def verify_project(project_dir: Path, *, artifacts_root: Path, run_id: str) -> VerificationResult:
    artifacts_dir = artifacts_root / run_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    if not (project_dir / "package.json").exists():
        evidence = AcceptanceEvidence(
            id="ev_package_missing",
            evidence_type="file",
            summary="package.json was not found in the target project directory.",
            artifact_path=None,
        )
        return VerificationResult(
            startup_ok=False,
            browser_ok=False,
            evidence=[evidence],
            errors=["package.json missing from project_dir"],
        )

    commands = detect_node_commands(project_dir)
    evidence: list[AcceptanceEvidence] = []
    errors: list[str] = []
    build_ok = _run_optional_command(project_dir, artifacts_dir, "build", commands.build, evidence, errors)
    test_ok = _run_optional_command(project_dir, artifacts_dir, "test", commands.test, evidence, errors)
    if commands.preview is None:
        evidence.append(
            AcceptanceEvidence(
                id="ev_preview_missing",
                evidence_type="command",
                summary="No preview, start, or dev script was found.",
            )
        )
        errors.append("preview command missing")
        return VerificationResult(
            startup_ok=False,
            build_ok=build_ok,
            test_ok=test_ok,
            browser_ok=False,
            evidence=evidence,
            errors=errors,
        )
    evidence.append(
        AcceptanceEvidence(
            id="ev_preview_detected",
            evidence_type="command",
            summary=f"Preview command detected: {' '.join(commands.preview)}",
        )
    )
    browser_ok, browser_evidence, browser_errors = _run_playwright_smoke(project_dir, artifacts_dir, commands.preview)
    evidence.extend(browser_evidence)
    errors.extend(browser_errors)
    return VerificationResult(
        startup_ok=not errors,
        build_ok=build_ok,
        test_ok=test_ok,
        browser_ok=browser_ok,
        evidence=evidence,
        errors=errors,
    )


def _run_playwright_smoke(
    project_dir: Path, artifacts_dir: Path, preview_command: list[str],
) -> tuple[bool, list[AcceptanceEvidence], list[str]]:
    from playwright.sync_api import sync_playwright

    port = _free_port()
    command = [*preview_command, "--", "--host", "127.0.0.1", "--port", str(port)]
    process = subprocess.Popen(
        command,
        cwd=project_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    evidence: list[AcceptanceEvidence] = []
    errors: list[str] = []
    log_path = artifacts_dir / "preview.log"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(record_video_dir=str(artifacts_dir / "videos"))
            page = context.new_page()
            console_errors: list[str] = []
            page_errors: list[str] = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))
            page.goto(f"http://127.0.0.1:{port}", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1000)
            screenshot_path = artifacts_dir / "startup.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            visible_surface = page.locator("canvas, #root, main, [data-game-root]").count() > 0
            context.close()
            browser.close()
            if page_errors:
                errors.extend(f"pageerror: {item}" for item in page_errors)
            fatal_console = [item for item in console_errors if _is_fatal_console_error(item)]
            if fatal_console:
                errors.extend(f"console: {item}" for item in fatal_console)
            if not visible_surface:
                errors.append("no visible game surface found")
            evidence.append(
                AcceptanceEvidence(
                    id="ev_playwright_startup",
                    evidence_type="playwright",
                    summary="Playwright opened the game page and captured startup state.",
                    artifact_path=str(screenshot_path),
                    metadata={"console_errors": console_errors, "page_errors": page_errors, "visible_surface": visible_surface},
                )
            )
    finally:
        process.terminate()
        try:
            stdout, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, _ = process.communicate(timeout=5)
        log_path.write_text(stdout or "", encoding="utf-8")
    return not errors, evidence, errors


def _package_manager(project_dir: Path) -> str:
    if (project_dir / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (project_dir / "yarn.lock").exists():
        return "yarn"
    return "npm"


def _install_command(project_dir: Path, package_manager: str) -> list[str] | None:
    if package_manager == "pnpm":
        return ["pnpm", "install", "--frozen-lockfile"]
    if package_manager == "yarn":
        return ["yarn", "install", "--frozen-lockfile"]
    if (project_dir / "package-lock.json").exists():
        return ["npm", "ci"]
    return ["npm", "install"]


def _has_real_test_script(scripts: object) -> bool:
    if not isinstance(scripts, dict) or "test" not in scripts:
        return False
    script = str(scripts["test"]).strip().lower()
    placeholder_parts = ["no test specified", "exit 1"]
    return not all(part in script for part in placeholder_parts)


def _run_optional_command(
    project_dir: Path,
    artifacts_dir: Path,
    name: str,
    command: list[str] | None,
    evidence: list[AcceptanceEvidence],
    errors: list[str],
) -> bool | None:
    if command is None:
        evidence.append(
            AcceptanceEvidence(
                id=f"ev_{name}_absent",
                evidence_type="command",
                summary=f"No {name} command was defined.",
            )
        )
        return None
    log_path = artifacts_dir / f"{name}.log"
    completed = subprocess.run(
        command,
        cwd=project_dir,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    log_path.write_text(completed.stdout + "\n" + completed.stderr, encoding="utf-8")
    passed = completed.returncode == 0
    evidence.append(
        AcceptanceEvidence(
            id=f"ev_{name}",
            evidence_type="command",
            summary=f"{name} command exited with code {completed.returncode}.",
            artifact_path=str(log_path),
            metadata={"command": command, "returncode": completed.returncode},
        )
    )
    if not passed:
        errors.append(f"{name} command failed with exit code {completed.returncode}")
    return passed


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _is_fatal_console_error(message: str) -> bool:
    lowered = message.lower()
    fatal_markers = ["uncaught", "syntaxerror", "referenceerror", "typeerror", "failed to fetch dynamically imported module"]
    return any(marker in lowered for marker in fatal_markers)
