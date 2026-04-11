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
REGISTER_LOG = "register_run.log"
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
            sys.stdout.write(line)
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


def register_feature_available(site_dir: Path) -> bool:
    register_html = site_dir / "register.html"
    if register_html.exists():
        return True

    index_html = site_dir / "index.html"
    if not index_html.exists():
        return False
    index_text = index_html.read_text(encoding="utf-8", errors="ignore")
    return (
        "register-link" in index_text
        or "register-button" in index_text
        or "create-account" in index_text
        or "register-form" in index_text
    )


def register_flow_prompt(username: str, password: str) -> str:
    return (
        f"Register a new account with username {username} and password {password}, "
        "log out, then log back in with the same credentials.\n"
        "1. Click on the registration link\n"
        "2. Select the username field\n"
        "3. Fill username\n"
        "4. Select the password field\n"
        "5. Fill password\n"
        "6. Press the Register button"
    )


def register_flow_success(username: str) -> str:
    return (
        "You are on the Home page after logging in with the newly registered account "
        f'and the page shows "Welcome, {username}".'
    )


def run_register_integration(
    repo_root: Path, *, username: str, password: str, model: str, log_path: Path
) -> None:
    script = repo_root / "vision_playwright_openai_vision_poc.py"
    cmd = [
        sys.executable,
        "-u",
        str(script),
        "--prompt",
        register_flow_prompt(username, password),
        "--visual-llm-success",
        register_flow_success(username),
        "--start-url",
        START_URL,
        "--actions",
        "register_account",
        "--max-steps",
        "20",
        "--headless",
        "--verbose",
        "--max-subactions-per-function",
        "5",
        "--model",
        model,
    ]
    print("== Run Register Integration Flow ==")
    run(cmd, cwd=repo_root, tee_path=log_path)


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
    register_log = repo_root / REGISTER_LOG

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

    print("== Prepare register smoke artifacts ==")
    reset_dir(agent_view_dir)
    if register_log.exists():
        register_log.unlink()

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

        feature_found = register_feature_available(site_dir)
        if not feature_found:
            message = "Register feature not detected in test-site; skipping register integration smoke."
            if args.require_feature:
                raise RuntimeError(message)
            print(f"== {message} ==")
            return 0

        rand_str = str(int(time.time()))
        register_username = f"user_{rand_str}"
        register_password = f"pass1_{rand_str}"
        run_register_integration(
            repo_root,
            username=register_username,
            password=register_password,
            model=args.model,
            log_path=register_log,
        )
        print("Local testregister sequence passed.")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
