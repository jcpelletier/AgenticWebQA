#!/usr/bin/env python
"""
Display Name — AgenticWebQA smoke test.

Wipes saved model actions and site hints for 127.0.0.1:8000, then runs the
display name flow twice: run 1 learns the actions, run 2 verifies no LLM fallback.

Usage:
    python webtests/run_testdisplayname_local.py [--skip-install] [--no-wipe]
        [--require-feature] [--model MODEL]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

START_URL = "http://127.0.0.1:8000/index.html"
SITE_HINTS_KEY = "127.0.0.1"
SITE_MODEL_FILE = "http_127_0_0_1_8000_index_html.json"
LOG_NAME = "displayname_run.log"
DEFAULT_MODEL = "claude-sonnet-4-6"

FALLBACK_PATTERN = "[playwright] Falling back to LLM."

TEST_CASES = [
    (
        "DisplayName",
        (
            "1. Register an account with username user_{rand_string} and password pass1_{rand_string}.\n"
            "2. Open Profile from the header navigation.\n"
            "3. In the Display name field, enter: {rand_string}\n"
            "4. Click Save.\n"
            "5. Click Home in the header navigation.\n"
            "6. Confirm the welcome text shows {rand_string}.\n"
            "7. Click Profile in the header navigation.\n"
            "8. Clear the Display name field (select all and delete).\n"
            "9. Click Save.\n"
            "10. Click Home in the header navigation."
        ),
        "The home page welcome text shows 'Welcome, user_{rand_string}' using the username as fallback after the display name was cleared.",
        "register_account,profile_open,profile_displayname",
        DEFAULT_MODEL,
    ),
]


def run(cmd: list[str], cwd: Path, tee_path: Path | None = None) -> None:
    if tee_path is None:
        subprocess.run(cmd, cwd=str(cwd), check=True)
        return
    with tee_path.open("a", encoding="utf-8") as f:
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


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


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


def wipe_site_artifacts(repo_root: Path) -> None:
    print("== Wipe 127.0.0.1:8000 model and site hints ==")

    model_file = repo_root / "Models" / SITE_MODEL_FILE
    if model_file.exists():
        model_file.unlink()
        print(f"  Deleted {model_file.name}")
    else:
        print(f"  {model_file.name} not found, skipping.")

    hints_path = repo_root / "site_hints.json"
    if hints_path.exists():
        try:
            hints = json.loads(hints_path.read_text(encoding="utf-8"))
        except Exception:
            hints = {}
        if SITE_HINTS_KEY in hints:
            del hints[SITE_HINTS_KEY]
            hints_path.write_text(json.dumps(hints, indent=2), encoding="utf-8")
            print(f"  Removed '{SITE_HINTS_KEY}' from site_hints.json")
        else:
            print(f"  '{SITE_HINTS_KEY}' not in site_hints.json, skipping.")
    else:
        print("  site_hints.json not found, skipping.")


def run_test(
    repo_root: Path,
    *,
    title: str,
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
        "25",
        "--headless",
        "--verbose",
        "--max-subactions-per-function",
        "5",
        "--model",
        model,
    ]
    run(cmd, cwd=repo_root, tee_path=log_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Display Name AgenticWebQA smoke test")
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument(
        "--no-wipe",
        action="store_true",
        help="Skip wiping saved model actions and site hints before running.",
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

    if log_path.exists():
        log_path.unlink()

    if not args.no_wipe:
        wipe_site_artifacts(repo_root)

    if not site_dir.exists():
        raise RuntimeError(f"Missing test site at {site_dir}")

    print("== Start local test site ==")
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8000", "--directory", str(site_dir)],
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        print("== Wait for local test site ==")
        wait_for_site(START_URL, timeout_s=60)

        for title, prompt_template, success_template, actions, model in TEST_CASES:
            model = args.model or model
            rand_str = str(int(time.time()))
            prompt = prompt_template.replace("{rand_string}", rand_str)
            success = success_template.replace("{rand_string}", rand_str)

            # Run 1: learn actions (LLM fallback allowed)
            reset_dir(agent_view_dir)
            print(f"== {title} — run 1 (learn) ==")
            try:
                run_test(
                    repo_root,
                    title=title,
                    prompt=prompt,
                    success=success,
                    actions=actions,
                    model=model,
                    log_path=log_path,
                )
            except subprocess.CalledProcessError:
                raise SystemExit(f"FAIL (run 1): {title}  (log: {log_path.name})")
            print(f"  PASS run 1: {title}")

            # Run 2: verify no LLM fallback
            run2_start = log_path.stat().st_size if log_path.exists() else 0
            rand_str = str(int(time.time()))
            prompt = prompt_template.replace("{rand_string}", rand_str)
            success = success_template.replace("{rand_string}", rand_str)
            reset_dir(agent_view_dir)
            print(f"== {title} — run 2 (verify no fallback) ==")
            try:
                run_test(
                    repo_root,
                    title=title,
                    prompt=prompt,
                    success=success,
                    actions=actions,
                    model=model,
                    log_path=log_path,
                )
            except subprocess.CalledProcessError:
                raise SystemExit(f"FAIL (run 2): {title}  (log: {log_path.name})")
            run2_text = log_path.read_text(encoding="utf-8", errors="ignore")[
                run2_start:
            ]
            if FALLBACK_PATTERN in run2_text:
                raise SystemExit(
                    f"FAIL (run 2 fallback detected): {title}  (log: {log_path.name})"
                )
            print(f"  PASS run 2 (no fallback): {title}")

        print(f"\nAll {len(TEST_CASES)} display name smoke test(s) passed (both runs).")
        return 0

    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
