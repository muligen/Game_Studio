from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
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
        static_html_entry = _find_static_html_entry(project_dir)
        if static_html_entry is not None:
            evidence = [
                AcceptanceEvidence(
                    id="ev_standalone_html_detected",
                    evidence_type="command",
                    summary=f"Standalone HTML entry was detected: {static_html_entry.relative_to(project_dir).as_posix()}",
                    artifact_path=str(static_html_entry),
                )
            ]
            browser_ok, browser_evidence, browser_errors = _run_static_html_smoke(
                project_dir,
                artifacts_dir,
                static_html_entry,
            )
            evidence.extend(browser_evidence)
            return VerificationResult(
                startup_ok=not browser_errors,
                browser_ok=browser_ok,
                evidence=evidence,
                errors=browser_errors,
            )
        evidence = AcceptanceEvidence(
            id="ev_package_missing",
            evidence_type="file",
            summary="Neither package.json nor index.html was found in the target project directory.",
            artifact_path=None,
        )
        return VerificationResult(
            startup_ok=False,
            browser_ok=False,
            evidence=[evidence],
            errors=["package.json or index.html missing from project_dir"],
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
    port = _free_port()
    command = _resolve_windows_command([*preview_command, "--", "--host", "127.0.0.1", "--port", str(port)])
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
        browser_ok, browser_evidence, browser_errors = _run_node_playwright_smoke(
            artifacts_dir=artifacts_dir,
            url=f"http://127.0.0.1:{port}",
            evidence_id="ev_playwright_startup",
            summary="Playwright opened the game page and captured startup state.",
            screenshot_name="startup.png",
        )
        evidence.extend(browser_evidence)
        errors.extend(browser_errors)
        return browser_ok and not errors, evidence, errors
    finally:
        process.terminate()
        try:
            stdout, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, _ = process.communicate(timeout=5)
        log_path.write_text(stdout or "", encoding="utf-8")


def _run_controlled_static_server_smoke(
    project_dir: Path,
    artifacts_dir: Path,
    index_path: Path,
) -> tuple[bool, list[AcceptanceEvidence], list[str]]:
    port = _free_port()
    rel_path = index_path.relative_to(project_dir).as_posix()
    process = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=project_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    log_path = artifacts_dir / "static-server.log"
    try:
        return _run_node_playwright_smoke(
            artifacts_dir=artifacts_dir,
            url=f"http://127.0.0.1:{port}/{rel_path}",
            evidence_id="ev_playwright_static_html",
            summary="Playwright opened standalone index.html through a controlled local server.",
            screenshot_name="startup.png",
        )
    finally:
        process.terminate()
        try:
            stdout, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, _ = process.communicate(timeout=5)
        log_path.write_text(stdout or "", encoding="utf-8")


def _run_node_playwright_smoke(
    *,
    artifacts_dir: Path,
    url: str,
    evidence_id: str,
    summary: str,
    screenshot_name: str,
) -> tuple[bool, list[AcceptanceEvidence], list[str]]:
    repo_root = Path(__file__).resolve().parents[2]
    web_dir = repo_root / "web"
    playwright_dir = web_dir / "node_modules" / "playwright"
    screenshot_path = artifacts_dir / screenshot_name
    result_path = artifacts_dir / "playwright-result.json"
    log_path = artifacts_dir / "playwright.log"
    video_dir = artifacts_dir / "videos"
    script_path = artifacts_dir / "playwright-smoke.mjs"

    if not playwright_dir.exists():
        evidence = AcceptanceEvidence(
            id=evidence_id,
            evidence_type="playwright",
            summary="Node Playwright dependency was not found.",
            artifact_path=None,
            metadata={"expected_path": str(playwright_dir)},
        )
        return False, [evidence], [f"Node Playwright dependency missing: {playwright_dir}"]

    video_dir.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        """
import { chromium } from 'playwright';
import fs from 'node:fs';

const [url, screenshotPath, videoDir, resultPath] = process.argv.slice(2);
const browser = await chromium.launch();
const context = await browser.newContext({ recordVideo: { dir: videoDir } });
const page = await context.newPage();
const consoleErrors = [];
const pageErrors = [];
page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
page.on('pageerror', err => pageErrors.push(String(err)));

let loaded = false;
let lastError = '';
for (let attempt = 0; attempt < 30; attempt += 1) {
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 3000 });
    loaded = true;
    break;
  } catch (error) {
    lastError = String(error && error.message ? error.message : error);
    await page.waitForTimeout(1000);
  }
}
if (!loaded) {
  throw new Error(lastError || `Failed to open ${url}`);
}

await page.waitForTimeout(1000);
const visibleSurface = await page.locator('canvas, #root, main, [data-game-root]').count() > 0;
await page.screenshot({ path: screenshotPath, fullPage: true });
await context.close();
await browser.close();

fs.writeFileSync(
  resultPath,
  JSON.stringify({ consoleErrors, pageErrors, visibleSurface }, null, 2),
  'utf8',
);
""".strip(),
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["node", str(script_path), url, str(screenshot_path), str(video_dir), str(result_path)],
        cwd=web_dir,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    log_path.write_text((completed.stdout or "") + "\n" + (completed.stderr or ""), encoding="utf-8")
    if completed.returncode != 0:
        evidence = AcceptanceEvidence(
            id=evidence_id,
            evidence_type="playwright",
            summary="Playwright smoke check failed before producing browser evidence.",
            artifact_path=str(log_path),
            metadata={"url": url, "returncode": completed.returncode},
        )
        return False, [evidence], [f"playwright smoke failed with exit code {completed.returncode}"]

    data = json.loads(result_path.read_text(encoding="utf-8"))
    console_errors = [str(item) for item in data.get("consoleErrors", [])]
    page_errors = [str(item) for item in data.get("pageErrors", [])]
    visible_surface = bool(data.get("visibleSurface"))

    errors: list[str] = []
    if page_errors:
        errors.extend(f"pageerror: {item}" for item in page_errors)
    fatal_console = [item for item in console_errors if _is_fatal_console_error(item)]
    if fatal_console:
        errors.extend(f"console: {item}" for item in fatal_console)
    if not visible_surface:
        errors.append("no visible game surface found")

    return not errors, [
        AcceptanceEvidence(
            id=evidence_id,
            evidence_type="playwright",
            summary=summary,
            artifact_path=str(screenshot_path),
            metadata={
                "url": url,
                "console_errors": console_errors,
                "page_errors": page_errors,
                "visible_surface": visible_surface,
                "result_path": str(result_path),
                "log_path": str(log_path),
            },
        )
    ], errors


def _find_static_html_entry(project_dir: Path) -> Path | None:
    for rel_path in ("index.html", "game/index.html"):
        candidate = project_dir / rel_path
        if candidate.exists():
            return candidate
    return None


def _run_static_html_smoke(
    project_dir: Path,
    artifacts_dir: Path,
    index_path: Path,
) -> tuple[bool, list[AcceptanceEvidence], list[str]]:
    evidence: list[AcceptanceEvidence] = []
    errors: list[str] = []
    index_path = index_path.resolve()
    evidence.append(
        AcceptanceEvidence(
            id="ev_static_html_server",
            evidence_type="command",
            summary="Standalone HTML project was served through a bounded local server for browser validation.",
            artifact_path=str(index_path),
        )
    )
    browser_ok, browser_evidence, browser_errors = _run_controlled_static_server_smoke(
        project_dir,
        artifacts_dir,
        index_path,
    )
    evidence.extend(browser_evidence)
    errors.extend(browser_errors)
    return browser_ok and not errors, evidence, errors


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
    command = _resolve_windows_command(command)
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


def _resolve_windows_command(command: list[str]) -> list[str]:
    if os.name != "nt" or not command:
        return command
    resolved = shutil.which(command[0])
    if not resolved:
        return command
    return [resolved, *command[1:]]


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _is_fatal_console_error(message: str) -> bool:
    lowered = message.lower()
    fatal_markers = ["uncaught", "syntaxerror", "referenceerror", "typeerror", "failed to fetch dynamically imported module"]
    return any(marker in lowered for marker in fatal_markers)
