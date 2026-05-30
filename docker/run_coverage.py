#!/usr/bin/env python3
"""
Coverage orchestrator: runs a learn + replay pair for each test with gpt-4o-mini,
then prints a report table comparing LLM-driven vs deterministic replay results.

Runs on the HOST (Windows / macOS / Linux) - invokes docker compose.

Usage:
    python docker/run_coverage.py
    python docker/run_coverage.py --rebuild          # rebuild qa image first
    python docker/run_coverage.py --tests login_demo register   # subset
    python docker/run_coverage.py --max-steps 25     # global step override
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = str(REPO_ROOT / "docker-compose.yml")

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MAX_STEPS = 20
TEST_TIMEOUT_SECS = 600  # 10 min hard cap per individual run

# Tests that need a pre-existing model seeded before their learn run.
# The listed prereqs are run (learn only, not counted in the report) so that
# their actions exist in the volume before the test's own LLM session starts.
# This ensures the test's LLM session only needs to learn ONE new action,
# preventing the duplicate-function corruption that occurs when multiple new
# actions are learned in a single fallback session.
PRE_WARM: dict[str, list[str]] = {
    "profile_all_fields": ["login_demo"],
}

# Per-test step overrides (profile + quiz need a bit more headroom)
MAX_STEPS_OVERRIDE: dict[str, int] = {
    "quiz_all_correct":           25,
    "profile_about_edit":         20,
    "profile_all_fields":         25,   # needs scroll to find Occupation + Save
    "profile_location_and_social": 25,
    "display_name":               25,
}

# The 10 tests for the gpt-4o-mini coverage run (ordered: simple to complex)
DEFAULT_TESTS = [
    "login_demo",
    "register",
    "login_invalid_credentials",
    "unauthenticated_redirect",
    "logout",
    "activity_feed_lifecycle",
    "quiz_all_correct",
    "profile_about_edit",
    "profile_all_fields",
    "profile_location_and_social",
]

LLM_FALLBACK_MARKER = "[playwright] Falling back to LLM."


# ---------------------------------------------------------------------------
# Docker helpers
# ---------------------------------------------------------------------------

def _compose(extra_args: list[str], timeout: int = TEST_TIMEOUT_SECS) -> tuple[int, str]:
    """
    Run: docker compose -f <compose> run --rm <extra_args>
    Returns (returncode, combined stdout+stderr).
    """
    cmd = ["docker", "compose", "-f", COMPOSE_FILE, "run", "--rm"] + extra_args
    abbreviated = " ".join(extra_args[:6])  # first few tokens for logging
    print(f"  >> docker compose run --rm {abbreviated} ...")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO_ROOT),
        )
        return result.returncode, result.stdout + "\n" + result.stderr
    except subprocess.TimeoutExpired:
        return -1, f"(TIMEOUT after {timeout}s)"


def clear_models() -> None:
    """Wipe /workspace/Models inside the container so the next run is a clean learn."""
    print("  Clearing learned models from volume...")
    rc, out = _compose(
        ["--no-deps", "qa", "sh", "-c",
         "rm -rf /workspace/Models/* 2>/dev/null; mkdir -p /workspace/Models"],
        timeout=60,
    )
    if rc != 0:
        print(f"  [WARN] model clear exited {rc}: {out[:300]}")
    else:
        print("  [OK]  models cleared")


def run_test_container(name: str, max_steps: int, model: str = DEFAULT_MODEL) -> tuple[bool, bool, str]:
    """
    Spin up the qa container and run one test.
    Returns (passed, used_llm_fallback, full_output).
    """
    rc, output = _compose([
        "qa",
        "python", "/usr/local/bin/run_test.py",
        name,
        "--model", model,
        "--max-steps", str(max_steps),
    ])
    if rc == -1:
        return False, False, output  # timeout
    passed = rc == 0
    used_llm = LLM_FALLBACK_MARKER in output
    return passed, used_llm, output


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"
TIMEOUT = "TIMEOUT"


def _status(passed: bool, output: str) -> str:
    if output.startswith("(TIMEOUT"):
        return TIMEOUT
    return PASS if passed else FAIL


def _icon(status: str) -> str:
    return {"PASS": "[PASS]", "FAIL": "[FAIL]", "TIMEOUT": "[TIME]"}.get(status, "[?]")


def print_separator(char: str = "-", width: int = 80) -> None:
    print(char * width)


def print_summary(results: list[dict], model: str, timestamp: str) -> None:
    W = 80
    print()
    print("=" * W)
    print("  COVERAGE REPORT")
    print(f"  Model: {model}  |  Date: {timestamp}")
    print("=" * W)

    col_test = 36
    col_status = 7
    col_llm = 6
    header = (
        f"{'Test':<{col_test}}"
        f"{'LEARN':>{col_status}} {'LLM?':>{col_llm}}"
        f"  |  "
        f"{'REPLAY':>{col_status}} {'LLM?':>{col_llm}}"
    )
    print(header)
    print("-" * W)

    for r in results:
        ls = _status(r["learn_pass"], r["learn_out"])
        rs = _status(r["replay_pass"], r["replay_out"])
        ll = "yes" if r["learn_llm"] else "no"
        rl = "yes" if r["replay_llm"] else "no"
        print(
            f"{r['name']:<{col_test}}"
            f"{ls:>{col_status}} {ll:>{col_llm}}"
            f"  |  "
            f"{rs:>{col_status}} {rl:>{col_llm}}"
        )

    print("=" * W)

    n = len(results)
    learn_passed  = sum(1 for r in results if r["learn_pass"])
    replay_passed = sum(1 for r in results if r["replay_pass"])
    replay_det    = sum(1 for r in results if r["replay_pass"] and not r["replay_llm"])
    replay_fail_det = [r["name"] for r in results
                       if not r["replay_pass"] and r["learn_pass"]]
    replay_fail_llm = [r["name"] for r in results
                       if not r["replay_pass"] and r["learn_pass"] and r["replay_llm"]]

    print(f"\n  Learn  runs : {learn_passed}/{n} passed")
    print(f"  Replay runs : {replay_passed}/{n} passed")
    print(f"    of which  : {replay_det} passed with ZERO LLM fallback (pure deterministic)")

    if replay_fail_det:
        print(f"\n  Tests that LEARNED OK but FAILED on replay ({len(replay_fail_det)}):")
        for name in replay_fail_det:
            print(f"    * {name}")

    print()


def save_report(results: list[dict], model: str, timestamp: str) -> Path:
    W = 80
    path = REPO_ROOT / f"coverage_report_{timestamp}.txt"
    with path.open("w", encoding="utf-8") as f:
        f.write(f"AgenticWebQA Coverage Report\n")
        f.write(f"Model: {model}  |  Date: {timestamp}\n")
        f.write("=" * W + "\n")

        col_test = 36
        col_status = 7
        col_llm = 6
        f.write(
            f"{'Test':<{col_test}}"
            f"{'LEARN':>{col_status}} {'LLM?':>{col_llm}}"
            f"  |  "
            f"{'REPLAY':>{col_status}} {'LLM?':>{col_llm}}\n"
        )
        f.write("-" * W + "\n")
        for r in results:
            ls = _status(r["learn_pass"], r["learn_out"])
            rs = _status(r["replay_pass"], r["replay_out"])
            ll = "yes" if r["learn_llm"] else "no"
            rl = "yes" if r["replay_llm"] else "no"
            f.write(
                f"{r['name']:<{col_test}}"
                f"{ls:>{col_status}} {ll:>{col_llm}}"
                f"  |  "
                f"{rs:>{col_status}} {rl:>{col_llm}}\n"
            )
        f.write("=" * W + "\n\n")

        n = len(results)
        learn_passed  = sum(1 for r in results if r["learn_pass"])
        replay_passed = sum(1 for r in results if r["replay_pass"])
        replay_det    = sum(1 for r in results if r["replay_pass"] and not r["replay_llm"])
        f.write(f"Learn  runs : {learn_passed}/{n} passed\n")
        f.write(f"Replay runs : {replay_passed}/{n} passed\n")
        f.write(f"  of which  : {replay_det} passed with ZERO LLM fallback\n\n")

        # Full output per test
        for r in results:
            f.write(f"\n{'='*60}\n")
            f.write(f"{r['name']}  -- LEARN  (steps={r['learn_steps']})\n")
            f.write("=" * 60 + "\n")
            f.write(r["learn_out"])
            f.write(f"\n{'='*60}\n")
            f.write(f"{r['name']}  -- REPLAY  (steps={r['replay_steps']})\n")
            f.write("=" * 60 + "\n")
            f.write(r["replay_out"])

    return path


def _count_steps(output: str) -> int:
    """Count how many agent steps appeared in the output."""
    return output.count("Step ")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Learn+replay coverage run with gpt-4o-mini")
    ap.add_argument("--rebuild", action="store_true",
                    help="Rebuild the qa Docker image before running")
    ap.add_argument("--tests", nargs="*", default=DEFAULT_TESTS,
                    metavar="TEST", help="Subset of tests to run (default: all 10)")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"LLM model to use (default: {DEFAULT_MODEL})")
    ap.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS,
                    help=f"Global step limit (default: {DEFAULT_MAX_STEPS}; "
                         "per-test overrides still apply)")
    args = ap.parse_args()

    if args.rebuild:
        print("Rebuilding qa image...")
        subprocess.run(
            ["docker", "compose", "-f", COMPOSE_FILE, "build", "qa"],
            cwd=str(REPO_ROOT),
            check=True,
        )
        print()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results: list[dict] = []

    model = args.model

    print(f"+===============================================================+")
    print(f"|  AgenticWebQA Coverage -- {model:<36s} |")
    print(f"|  {len(args.tests)} tests  |  base max-steps={args.max_steps}  |  {timestamp}  |")
    print(f"+===============================================================+")
    print()

    for i, test_name in enumerate(args.tests, 1):
        max_steps = MAX_STEPS_OVERRIDE.get(test_name, args.max_steps)

        print()
        print_separator("=")
        print(f"  [{i}/{len(args.tests)}]  {test_name}  (max-steps={max_steps})")
        print_separator("=")

        # Wipe all learned models so this is a fully clean learn run
        clear_models()

        # Pre-warm: seed required prerequisite models before this test's learn.
        # This ensures the LLM session only needs to learn one new action,
        # avoiding the duplicate-function corruption from multi-action sessions.
        for prereq in PRE_WARM.get(test_name, []):
            print(f"\n  -- PRE-WARM: seeding '{prereq}' --")
            prereq_steps = MAX_STEPS_OVERRIDE.get(prereq, args.max_steps)
            run_test_container(prereq, prereq_steps, model)

        # -- LEARN ------------------------------------------------------------
        print("\n  -- LEARN RUN --")
        learn_pass, learn_llm, learn_out = run_test_container(test_name, max_steps, model)
        learn_status = _status(learn_pass, learn_out)
        learn_steps  = _count_steps(learn_out)
        print(f"  {_icon(learn_status)} {learn_status}"
              f"  {'(used LLM fallback)' if learn_llm else '(no fallback)'}"
              f"  steps~{learn_steps}")

        # -- REPLAY -----------------------------------------------------------
        print("\n  -- REPLAY RUN --")
        replay_pass, replay_llm, replay_out = run_test_container(test_name, max_steps, model)
        replay_status = _status(replay_pass, replay_out)
        replay_steps  = _count_steps(replay_out)
        print(f"  {_icon(replay_status)} {replay_status}"
              f"  {'(used LLM fallback)' if replay_llm else '(no fallback)'}"
              f"  steps~{replay_steps}")

        results.append({
            "name":         test_name,
            "learn_pass":   learn_pass,
            "learn_llm":    learn_llm,
            "learn_out":    learn_out,
            "learn_steps":  learn_steps,
            "replay_pass":  replay_pass,
            "replay_llm":   replay_llm,
            "replay_out":   replay_out,
            "replay_steps": replay_steps,
        })

    print_summary(results, model, timestamp)

    report_path = save_report(results, model, timestamp)
    print(f"  Full output saved: {report_path}")

    # Exit non-zero if any test failed both runs
    any_fail = any(not r["learn_pass"] or not r["replay_pass"] for r in results)
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
