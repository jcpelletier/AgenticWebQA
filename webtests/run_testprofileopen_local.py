#!/usr/bin/env python
import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


START_URL = "http://127.0.0.1:8000/index.html"
PROFILE_OPEN_LOG = "profileopen_run.log"
DEFAULT_MODEL = "claude-sonnet-4-6"

PROMPT = "1. Register an account\n2. Open Profile from the header."
SUCCESS = "The user is on the profile page."


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


def profile_feature_available(site_dir: Path) -> bool:
    profile_html = site_dir / "profile.html"
    if not profile_html.exists():
        return False
    profile_text = profile_html.read_text(encoding="utf-8", errors="ignore")
    required_tokens = (
        'data-testid="site-header"',
        'data-testid="nav-profile"',
        'data-testid="profile-title"',
    )
    return all(token in profile_text for token in required_tokens)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--require-feature", action="store_true")
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
    profile_open_log = repo_root / PROFILE_OPEN_LOG

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

    print("== Prepare profile open smoke artifacts ==")
    reset_dir(agent_view_dir)
    profile_open_log = pick_writable_log_path(profile_open_log)

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
        print("== Wait for local test site ==")
        wait_for_site(START_URL, timeout_s=60)

        feature_found = profile_feature_available(site_dir)
        if not feature_found:
            message = "Profile page feature not detected in test-site; skipping profile open smoke."
            if args.require_feature:
                raise RuntimeError(message)
            print(f"== {message} ==")
            return 0

        script = repo_root / "vision_playwright_openai_vision_poc.py"
        cmd = [
            sys.executable,
            "-u",
            str(script),
            "--prompt",
            PROMPT,
            "--success-criteria",
            SUCCESS,
            "--start-url",
            START_URL,
            "--actions",
            "register_account,profile_open",
            "--max-steps",
            "20",
            "--headless",
            "--verbose",
            "--max-subactions-per-function",
            "5",
            "--model",
            args.model,
        ]
        print("== Run Profile Open Flow ==")
        run(cmd, cwd=repo_root, tee_path=profile_open_log)

        print("Local testprofileopen sequence passed.")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
