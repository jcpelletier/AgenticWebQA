#!/usr/bin/env python
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
DEFAULT_MODEL = "claude-opus-4-6"


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
        "--success-criteria",
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
    print(f"== Run Login Flow ({phase}) ==")
    run(cmd, cwd=repo_root, tee_path=log_path)


def break_saved_selectors(models_dir: Path) -> None:
    print("== Break saved selectors (auto-heal prep) ==")
    changed = 0
    for p in models_dir.rglob("*"):
        if not p.is_file():
            continue
        raw = p.read_text(encoding="utf-8", errors="ignore")
        if "data-testid" in raw:
            updated = raw.replace("data-testid", "test-testid")
            if updated != raw:
                p.write_text(updated, encoding="utf-8")
                changed += 1
    if changed <= 0:
        raise RuntimeError(
            f"No saved selectors were modified in {models_dir} (expected at least one data-testid replacement)."
        )
    print(f"Modified {changed} file(s) in {models_dir}.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model override for AI runs (default: {DEFAULT_MODEL}).",
    )
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Missing ANTHROPIC_API_KEY environment variable.")

    repo_root = Path(__file__).resolve().parent.parent
    models_dir = repo_root / "Models"
    agent_view_dir = repo_root / "agent_view"
    site_hints = repo_root / "site_hints.json"
    reuse_log = repo_root / "reuse_run.log"
    auto_log = repo_root / "auto_heal_run.log"

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
    for p in (reuse_log, auto_log):
        if p.exists():
            p.unlink()

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

        run_agent_case(
            repo_root,
            phase="learn",
            prompt=PROMPT,
            success=SUCCESS,
            actions="login_demo",
            model=args.model,
        )
        break_saved_selectors(models_dir)

        reset_dir(agent_view_dir)
        run_agent_case(
            repo_root,
            phase="auto-heal",
            prompt=PROMPT,
            success=SUCCESS,
            actions="login_demo",
            model=args.model,
            log_path=auto_log,
        )

        reset_dir(agent_view_dir)
        run_agent_case(
            repo_root,
            phase="reuse",
            prompt=PROMPT,
            success=SUCCESS,
            actions="login_demo",
            model=args.model,
            log_path=reuse_log,
        )

        print("== Assert no vision fallback (reuse) ==")
        txt = reuse_log.read_text(encoding="utf-8", errors="ignore")
        for pattern in ("[playwright] Falling back to LLM.", "dom_fallback_error"):
            if pattern in txt:
                raise RuntimeError(
                    f"Vision fallback detected in reuse run. Pattern: {pattern}"
                )

        print("Local testlogin sequence passed.")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
