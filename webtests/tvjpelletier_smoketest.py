#!/usr/bin/env python
"""
tv.jpelletier.com — AgenticWebQA smoke test suite.

Wipes saved model actions and site hints for tv.jpelletier.com,
then runs all tests in order.

Usage:
    python webtests/tvjpelletier_smoketest.py [--skip-install] [--test TITLE]
        [--username USER] [--password PASS] [--model MODEL] [--no-wipe]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SITE_URL = "https://tv.jpelletier.com/"
SITE_HINTS_KEY = "tv.jpelletier.com"
SITE_MODEL_FILE = "https_tv_jpelletier_com.json"

DEFAULT_USERNAME = "demo"
DEFAULT_PASSWORD = "demo123"

# Tests in order from the GUI .tmp file.
# Each entry: (title, prompt, success_criteria, actions, model)
TEST_CASES = [
    (
        "Login",
        (
            "1. Select Username field\n"
            "2. Input {username}\n"
            "3. Select Password field\n"
            "4. Input {password}\n"
            "5. Click the Sign In button"
        ),
        "The user is logged in.",
        "login",
        "claude-sonnet-4-6",
    ),
    (
        "SearchForMovie",
        (
            "1. Login\n"
            "2. Open the search via the search UI element in the top right.\n"
            "3. Search for 'Matilda'"
        ),
        "A poster image for 'Matilda' appears",
        "login, search_movie",
        "claude-sonnet-4-6",
    ),
    (
        "OpenMovieDetails",
        (
            "1. Login\n"
            "2. Search for 'Chicago'\n"
            "3. Open the Movie Details screen for the movie"
        ),
        "The Movie Details screen for 'Chicago' is visible.",
        "login, search_movie, open_moviedetails",
        "claude-sonnet-4-6",
    ),
    (
        "CheckForSubs",
        (
            "1. Login\n"
            "2. Search for 'Annie'\n"
            "3. Open the Movie Details screen for the movie"
        ),
        "The Movie 'Annie' has subtitles available.",
        "login, search_movie, open_moviedetails",
        "claude-sonnet-4-6",
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


def wipe_site_artifacts(repo_root: Path) -> None:
    print("== Wipe tv.jpelletier.com model and site hints ==")

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


FALLBACK_PATTERN = "[playwright] Falling back to LLM."


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
        SITE_URL,
        "--actions",
        actions,
        "--max-steps",
        "40",
        "--headless",
        "--verbose",
        "--slowmo",
        "250",
        "--max-subactions-per-function",
        "10",
        "--model",
        model,
    ]
    run(cmd, cwd=repo_root, tee_path=log_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="tv.jpelletier.com AgenticWebQA smoke tests"
    )
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument(
        "--test",
        metavar="TITLE",
        help="Run a single test by title (e.g. Login). Omit to run all.",
    )
    parser.add_argument(
        "--model",
        metavar="MODEL",
        default=None,
        help="Override the model for all tests (e.g. claude-opus-4-6).",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("WEBQA_USERNAME", DEFAULT_USERNAME),
        help="Username for login tests (env: WEBQA_USERNAME, default: %(default)s).",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("WEBQA_PASSWORD", DEFAULT_PASSWORD),
        help="Password for login tests (env: WEBQA_PASSWORD, default: %(default)s).",
    )
    parser.add_argument(
        "--no-wipe",
        action="store_true",
        help="Skip wiping saved model actions and site hints before running.",
    )
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Missing ANTHROPIC_API_KEY environment variable.")

    repo_root = Path(__file__).resolve().parent.parent
    agent_view_dir = repo_root / "agent_view"
    log_path = repo_root / "tvjpelletier_smoketest.log"

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

    test_cases = TEST_CASES
    if args.test:
        target = args.test.lower()
        test_cases = [tc for tc in TEST_CASES if tc[0].lower() == target]
        if not test_cases:
            valid = ", ".join(tc[0] for tc in TEST_CASES)
            raise SystemExit(f"Unknown test title '{args.test}'. Valid titles: {valid}")

    for title, prompt_template, success, actions, model in test_cases:
        model = args.model or model
        prompt = prompt_template.format(username=args.username, password=args.password)

        # Run 1: build actions (LLM fallback allowed)
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

        # Run 2: confirm no LLM fallback
        run2_start = log_path.stat().st_size if log_path.exists() else 0
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
        run2_text = log_path.read_text(encoding="utf-8", errors="ignore")[run2_start:]
        if FALLBACK_PATTERN in run2_text:
            raise SystemExit(
                f"FAIL (run 2 fallback detected): {title}  (log: {log_path.name})"
            )
        print(f"  PASS run 2 (no fallback): {title}")

    total = len(test_cases)
    print(f"\nAll {total} tv.jpelletier.com smoke test(s) passed (both runs).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
