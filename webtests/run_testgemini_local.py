#!/usr/bin/env python
"""
Smoke test: Gemini provider — login flow against the local test site.

Validates REQ-7, REQ-8, REQ-9 (GeminiProviderSupport TDD).

Usage:
    python ./webtests/run_testgemini_local.py --skip-install --model gemini-2.0-flash

Exits with code 0 on success, non-zero on failure.
Skips gracefully with SKIP: GEMINI_API_KEY_NOT_SET when the key is absent.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


PROMPT = (
    "Log in with username 'demo' and password 'demo123'.\n"
    "1. Fill in the username field\n"
    "2. Fill in the password field\n"
    "3. Click Log in"
)
SUCCESS = "You are on the Home page and see 'Welcome, demo'."
START_URL = "http://127.0.0.1:8000/index.html"
DEFAULT_MODEL = "gemini-2.5-flash"


def run(cmd: list[str], cwd: Path, tee_path: Path | None = None) -> None:
    if tee_path is None:
        subprocess.run(cmd, cwd=str(cwd), check=True)
        return
    with tee_path.open("w", encoding="utf-8") as f:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            try:
                sys.stdout.write(line)
            except UnicodeEncodeError:
                console_encoding = sys.stdout.encoding or "utf-8"
                safe_line = line.encode("utf-8", errors="replace").decode(
                    console_encoding, errors="replace"
                )
                sys.stdout.write(safe_line)
            f.write(line)
        rc = proc.wait()
        if rc != 0:
            raise subprocess.CalledProcessError(rc, cmd)


def wait_for_site(url: str, timeout_s: int = 45) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"Local test site not reachable at {url}")


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def run_agent_case(
    repo_root: Path,
    *,
    phase: str,
    prompt: str,
    success: str,
    actions: str,
    model: str,
    start_url: str = START_URL,
    max_steps: int = 20,
    log_path: Path | None = None,
) -> None:
    script = repo_root / "vision_playwright_openai_vision_poc.py"
    cmd = [
        sys.executable,
        "-u",
        str(script),
        "--prompt",
        prompt,
        "--visual-llm-success",
        success,
        "--start-url",
        start_url,
        "--actions",
        actions,
        "--max-steps",
        str(max_steps),
        "--headless",
        "--verbose",
        "--max-subactions-per-function",
        "5",
        "--model",
        model,
    ]
    print(f"== Run Gemini Login Flow ({phase}) ==")
    run(cmd, cwd=repo_root, tee_path=log_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini model override (default: {DEFAULT_MODEL}).",
    )
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("SKIP: GEMINI_API_KEY_NOT_SET")
        return 0

    repo_root = Path(__file__).resolve().parent.parent
    models_dir = repo_root / "Models"
    agent_view_dir = repo_root / "agent_view"
    site_hints = repo_root / "site_hints.json"
    gemini_log = repo_root / "gemini_run.log"

    if not args.skip_install:
        print("== Install dependencies ==")
        run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], cwd=repo_root)
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(repo_root / "requirements.txt"),
            ],
            cwd=repo_root,
        )
        run([sys.executable, "-m", "playwright", "install", "chromium"], cwd=repo_root)

    print("== Reset learned artifacts ==")
    reset_dir(models_dir)
    reset_dir(agent_view_dir)
    if site_hints.exists():
        site_hints.unlink()
    if gemini_log.exists():
        gemini_log.unlink()

    print("== Start local test site ==")
    site_dir = repo_root / "test-site"
    if not site_dir.exists():
        raise RuntimeError(f"Missing test site at {site_dir}")
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8000", "--directory", str(site_dir)],
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_site(START_URL)

        run_agent_case(
            repo_root,
            phase="learn",
            prompt=PROMPT,
            success=SUCCESS,
            actions="login",
            model=args.model,
            log_path=gemini_log,
        )

        print("== Verify run log contains FINAL: PASS ==")
        log_text = gemini_log.read_text(encoding="utf-8", errors="replace")
        final_tokens = [
            line.strip() for line in log_text.splitlines() if "FINAL:" in line
        ]
        if not final_tokens:
            raise RuntimeError("No FINAL: token found in gemini_run.log")
        if len(final_tokens) > 1:
            raise RuntimeError(
                f"Expected exactly one FINAL: token, found {len(final_tokens)}: {final_tokens}"
            )
        if "FINAL: PASS" not in final_tokens[0]:
            raise RuntimeError(f"Expected FINAL: PASS but got: {final_tokens[0]}")

    finally:
        server.terminate()
        server.wait()

    print("== Gemini smoke test passed ==")
    print("VISUAL_UNIQUE: GEMINI_PROVIDER_SMOKE_COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
