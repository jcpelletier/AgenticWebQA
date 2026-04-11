#!/usr/bin/env python
"""
Lifelink Calculator — AgenticWebQA test suite.

Wipes saved model actions and site hints for lifelink-calculator.vercel.app,
then runs all tests in order (Select_Calendar first, then all Radial flows).

Usage:
    python webtests/lifelink_calculator.py [--skip-install] [--test TITLE]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CALC_URL = "https://lifelink-calculator.vercel.app"
LIFELINK_HINTS_KEY = "lifelink-calculator.vercel.app"
LIFELINK_MODEL_FILE = "https_lifelink_calculator_vercel_app.json"

# Tests in order from the GUI tmp file, starting with Select_Calendar.
# Each entry: (title, prompt, success_criteria, actions, model)
TEST_CASES = [
    (
        "Select_Calendar",
        "Select Calendar input field at the top of the screen.",
        "The Calendar input field at the top of the screen is in focus.",
        "select_calendar",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_01_Select",
        "Select the 'Open Negotiation Initiation Window' radio option.",
        "The 'Open Negotiation Initiation Window' radio option is selected.",
        "radial_01_select",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_01_Dates",
        "Enter 3/9/2026 as the Remit Receipt Date in the dropdown above the calendar.",
        (
            "The Open Negotiation Initiation Window is shown with start date 3/9/2026 "
            "and end date 4/20/2026 (remit receipt date + 30 business days). "
            "Both dates are visible on the page."
        ),
        "radial_01_select,select_calendar,radial_01_dates",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_02_Select",
        "Select the 'Open negotiation period' radio option.",
        "The 'Open negotiation period' radio option is selected.",
        "radial_02_select",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_02_Dates",
        "Enter 3/9/2026 as the negotiation initiation date in the dropdown above the calendar.",
        (
            "The Open Negotiation Period is shown with start date 3/10/2026 "
            "and end date 4/8/2026 (remit receipt date + 30 business days). "
            "Both dates are visible on the page."
        ),
        "radial_02_select,select_calendar,radial_02_dates",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_03_Select",
        "Select the 'IDR initiation window' radio option.",
        "The 'IDR initiation window' radio option is selected.",
        "radial_03_select",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_03_Dates",
        "Enter 3/9/2026 as the Open negotiation initiation date in the dropdown above the calendar.",
        (
            "The IDR Initiation Window is shown with start date 4/9/2026 "
            "and end date 4/14/2026 (open negotiation initiation date + 30 cal. days "
            "+ federal holidays + 4 business days). Both dates are visible on the page."
        ),
        "radial_03_select,select_calendar,radial_03_dates",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_04_Select",
        "Select the 'IDRE selection window' radio option.",
        "The 'IDRE selection window' radio option is selected.",
        "radial_04_select",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_04_Dates",
        (
            "Select the 'IDRE selection window' radio option. "
            "Enter 4/9/2026 as the IDR Initiation Date in the dropdown above the calendar."
        ),
        (
            "The IDRE Selection Window is shown with start date 4/9/2026 "
            "and end date 4/14/2026 (IDR Initiation Date + 3 business days). "
            "Both dates are visible weekdays."
        ),
        "radial_04_select,select_calendar,radial_04_dates",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_05_Select",
        "Select the 'IDR offer submission window' radio option.",
        "The 'IDR offer submission window' radio option is selected.",
        "radial_05_select",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_05_Dates",
        (
            "Select the 'IDR offer submission window' radio option. "
            "Enter 4/14/2026 as the IDRE Selection Date in the dropdown above the calendar. "
            "Read the displayed IDR Offer Submission Window dates."
        ),
        (
            "The IDR Offer Submission Window is shown with start date 4/14/2026 "
            "and end date 4/28/2026 (IDRE Selection Date + 10 business days). "
            "Both dates are visible weekdays."
        ),
        "radial_05_select,select_calendar,radial_05_dates",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_06_Select",
        "Select the 'Written determination due date' radio option.",
        "The 'Written determination due date' radio option is selected.",
        "radial_06_select",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_06_Dates",
        (
            "Select the 'Written determination due date' radio option. "
            "Enter 4/14/2026 as the IDRE Selection Date in the dropdown above the calendar. "
            "Read the displayed Written Determination Due Date."
        ),
        "Written Determination Due Date is listed as 5/27/2026",
        "radial_06_select,select_calendar,radial_06_dates",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_07_Select",
        "Select the 'Payor payment due date' radio option.",
        "The 'Payor payment due date' radio option is selected.",
        "radial_07_select",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_07_Dates",
        (
            "Select the 'Payor payment due date' radio option. "
            "Enter 5/27/2026 as the Written Determination Date in the dropdown above the calendar. "
            "Read the displayed Payor Payment Due Date."
        ),
        "The displayed Payor Payment Due Date is 6/26/2026.",
        "radial_07_select,select_calendar,radial_07_dates",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_08_Select",
        "Select the 'Cooling-off period' radio option.",
        "The 'Cooling-off period' radio option is selected.",
        "radial_08_select",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_08_Dates",
        (
            "Select the 'Cooling-off period' radio option. "
            "Enter 5/27/2026 as the Written Determination Date in the dropdown above the calendar. "
            "Read the displayed Cooling-Off Period dates."
        ),
        (
            "The Cooling-Off Period is shown with start date 5/27/2026 "
            "and end date 8/25/2026 (Written Determination Date + 90 calendar days). "
            "Both dates are visible."
        ),
        "radial_08_select,select_calendar,radial_08_dates",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_09_Select",
        "Select the 'Post-cooling-off-period IDR initiation window' radio option.",
        "The 'Post-cooling-off-period IDR initiation window' radio option is selected.",
        "radial_09_select",
        "claude-sonnet-4-6",
    ),
    (
        "Radial_09_Dates",
        (
            "Select the 'Post-cooling-off-period IDR initiation window' radio option. "
            "Enter 5/27/2026 as the Written Determination Date in the dropdown above the calendar. "
            "Read the displayed Post-Cooling-Off-Period IDR Initiation Window dates."
        ),
        "The Post-Cooling-Off-Period IDR Initiation Window is shown. The listed date range is 8/26/2026 to 10/7/2026.",
        "radial_09_select,select_calendar,radial_09_dates",
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


def wipe_lifelink_artifacts(repo_root: Path) -> None:
    print("== Wipe lifelink model and site hints ==")

    model_file = repo_root / "Models" / LIFELINK_MODEL_FILE
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
        if LIFELINK_HINTS_KEY in hints:
            del hints[LIFELINK_HINTS_KEY]
            hints_path.write_text(json.dumps(hints, indent=2), encoding="utf-8")
            print(f"  Removed '{LIFELINK_HINTS_KEY}' from site_hints.json")
        else:
            print(f"  '{LIFELINK_HINTS_KEY}' not in site_hints.json, skipping.")
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
        "--success-criteria",
        success,
        "--start-url",
        CALC_URL,
        "--actions",
        actions,
        "--max-steps",
        "20",
        "--headless",
        "--verbose",
        "--slowmo",
        "250",
        "--max-subactions-per-function",
        "3",
        "--model",
        model,
    ]
    run(cmd, cwd=repo_root, tee_path=log_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lifelink Calculator AgenticWebQA tests"
    )
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument(
        "--test",
        metavar="TITLE",
        help="Run a single test by title (e.g. Select_Calendar, Radial_01_Dates). Omit to run all.",
    )
    parser.add_argument(
        "--model",
        metavar="MODEL",
        default=None,
        help="Override the model for all tests (e.g. claude-opus-4-6).",
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
    log_path = repo_root / "lifelink_calculator.log"

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
        wipe_lifelink_artifacts(repo_root)

    test_cases = TEST_CASES
    if args.test:
        target = args.test.lower()
        test_cases = [tc for tc in TEST_CASES if tc[0].lower() == target]
        if not test_cases:
            valid = ", ".join(tc[0] for tc in TEST_CASES)
            raise SystemExit(f"Unknown test title '{args.test}'. Valid titles: {valid}")

    for title, prompt, success, actions, model in test_cases:
        model = args.model or model
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
    print(f"\nAll {total} lifelink calculator test(s) passed (both runs).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
