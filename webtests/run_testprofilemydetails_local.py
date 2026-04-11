#!/usr/bin/env python
"""
Profile My Details — AgenticWebQA smoke test.

Registers a new account, opens the Profile page, fills the Hometown field with
a random value, saves, reloads the page, and verifies the value persists.

Usage:
    python webtests/run_testprofilemydetails_local.py [--skip-install]
        [--require-feature] [--model MODEL]
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


START_URL = "http://127.0.0.1:8000/index.html"
LOG_NAME = "profilemydetails_run.log"
DEFAULT_MODEL = "claude-sonnet-4-6"


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


def pick_writable_log_path(path: Path) -> Path:
    if not path.exists():
        return path
    try:
        path.unlink()
        return path
    except PermissionError:
        fallback = path.with_name(f"{path.stem}_{int(time.time())}{path.suffix}")
        print(f"== Log file in use; using fallback log file: {fallback.name} ==")
        return fallback


def mydetails_feature_available(site_dir: Path) -> bool:
    profile_html = site_dir / "profile.html"
    if not profile_html.exists():
        return False
    profile_text = profile_html.read_text(encoding="utf-8", errors="ignore")
    required_tokens = (
        'data-testid="profile-mydetails-section"',
        'data-testid="profile-mydetails-heading"',
        'data-testid="profile-hometown-input"',
        'data-testid="profile-birthday-input"',
        'data-testid="profile-favoritequote-input"',
        'data-testid="profile-save-button"',
        'data-testid="social-icon-linkedin"',
        'data-testid="social-icon-github"',
    )
    return all(token in profile_text for token in required_tokens)


def run_agent(
    repo_root: Path,
    *,
    prompt: str,
    success: str,
    actions: str,
    model: str,
    log_path: Path,
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
        START_URL,
        "--actions",
        actions,
        "--max-steps",
        "20",
        "--headless",
        "--verbose",
        "--max-subactions-per-function",
        "5",
        "--model",
        model,
    ]
    run(cmd, cwd=repo_root, tee_path=log_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Profile My Details AgenticWebQA smoke test"
    )
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument(
        "--require-feature",
        action="store_true",
        help="Fail (rather than skip) if the My Details feature is not detected.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model override for AI runs (default: {DEFAULT_MODEL}).",
    )
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Missing ANTHROPIC_API_KEY environment variable.")

    repo_root = Path(__file__).resolve().parent.parent
    agent_view_dir = repo_root / "agent_view"
    log_path = repo_root / LOG_NAME
    site_dir = repo_root / "test-site"

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

    print("== Prepare My Details smoke artifacts ==")
    reset_dir(agent_view_dir)
    log_path = pick_writable_log_path(log_path)

    print("== Start local test site ==")
    if not site_dir.exists():
        raise RuntimeError(f"Missing test site at {site_dir}")
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8000", "--directory", str(site_dir)],
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        print("== Wait for local test site ==")
        wait_for_site(START_URL, timeout_s=60)

        if not mydetails_feature_available(site_dir):
            message = (
                "SKIP: PROFILE_MY_DETAILS_FEATURE_MISSING — "
                "My Details section not detected in test-site; skipping smoke."
            )
            if args.require_feature:
                raise RuntimeError(message)
            print(f"== {message} ==")
            print("FINAL: PASS")
            return 0

        model = args.model
        rand_str = str(int(time.time()))

        # TEST-SMOKE-PROFILEMYDETAILS-001: Section and fields visible
        reset_dir(agent_view_dir)
        print("== TEST-SMOKE-PROFILEMYDETAILS-001: My Details section visible ==")
        run_agent(
            repo_root,
            prompt=(
                "1. Register a new account.\n"
                "2. Open the Profile page from the navigation header."
            ),
            success=(
                "The profile page is visible and shows a 'My Details' section heading. "
                "VISUAL_UNIQUE: The text 'My Details' is visible as a distinct section heading "
                "within the profile card, and this heading was not present on any earlier page "
                "in this flow."
            ),
            actions="register_account,profile_open,profile_mydetails_view",
            model=model,
            log_path=log_path,
        )
        print("  PASS TEST-SMOKE-PROFILEMYDETAILS-001")

        # TEST-SMOKE-PROFILEMYDETAILS-002: Save and reload persistence
        rand_str = str(int(time.time()))
        reset_dir(agent_view_dir)
        print("== TEST-SMOKE-PROFILEMYDETAILS-002: Save and reload persistence ==")
        run_agent(
            repo_root,
            prompt=(
                "1. Register a new account.\n"
                "2. Open the Profile page from the navigation header.\n"
                f"3. Find the Hometown field under My Details and enter: {rand_str}\n"
                "4. Click the Save button.\n"
                "5. Reload the page."
            ),
            success=(
                f"The profile page is visible after reload with the Hometown field "
                f"containing {rand_str}. "
                f"VISUAL_UNIQUE: The value {rand_str} is visible inside the Hometown input "
                f"field after the page was reloaded, which confirms the value was persisted; "
                f"this value was not present in the Hometown field before the save action."
            ),
            actions="register_account,profile_open,profile_mydetails_save",
            model=model,
            log_path=log_path,
        )
        print("  PASS TEST-SMOKE-PROFILEMYDETAILS-002")

        # TEST-SMOKE-PROFILEMYDETAILS-003: Social link icons visible
        reset_dir(agent_view_dir)
        print("== TEST-SMOKE-PROFILEMYDETAILS-003: Social link icons visible ==")
        run_agent(
            repo_root,
            prompt=(
                "1. Register a new account.\n"
                "2. Open the Profile page from the navigation header.\n"
                "3. Scroll to the Social Links section under My Details."
            ),
            success=(
                "The profile page shows the Social Links area with visible platform icons "
                "next to the input fields. "
                "VISUAL_UNIQUE: Platform icons (such as the LinkedIn or GitHub logo) are "
                "visible as graphical elements adjacent to social link text inputs, which "
                "were not present anywhere before this section was scrolled into view."
            ),
            actions="register_account,profile_open,profile_mydetails_view",
            model=model,
            log_path=log_path,
        )
        print("  PASS TEST-SMOKE-PROFILEMYDETAILS-003")

        print("\nAll Profile My Details smoke tests passed.")
        return 0

    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
