#!/usr/bin/env python
"""
NSA Account Date Calculator — AgenticWebQA test suite.

Covers TC-01 through TC-09 (all nine radial button flows) plus edge cases
TC-E01, TC-E02, TC-E05, which have unambiguous expected outcomes.

TBD edge cases (TC-E03, TC-E04, TC-E06, TC-E07, TC-E08) are excluded
because expected behavior has not been confirmed with the product owner.

Usage:
    python webtests/run_nsa_calculator.py --url https://your-calculator-url.com
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ── Update this to the real calculator URL ──────────────────────────────────
DEFAULT_CALC_URL = "https://lifelink-calculator.vercel.app"
# ────────────────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "claude-sonnet-4-6"

# ── Test definitions ─────────────────────────────────────────────────────────
# Each entry: (test_id, title, action, prompt, success_criteria)
TEST_CASES = [
    (
        "TC-01",
        "Open Negotiation Initiation Window",
        "nsa_open_neg_init_window",
        (
            "Select the 'Open Negotiation Initiation Window' radio option.\n"
            "Enter 3/9/2026 as the Remit Receipt Date in the dropdown above the calendar.\n"
            "Read the displayed Open Negotiation Initiation Window dates."
        ),
        (
            "The Open Negotiation Initiation Window is shown with start date 3/9/2026 "
            "and end date 4/20/2026 (remit receipt date + 30 business days). "
            "Both dates are visible on the page."
        ),
    ),
    (
        "TC-02",
        "Open Negotiation Period",
        "nsa_open_neg_period",
        (
            "Select the 'Open Negotiation Period' radio option.\n"
            "Enter 3/9/2026 as the Open Negotiation Initiation Date in the dropdown above the calendar.\n"
            "Read the displayed Open Negotiation Period dates."
        ),
        (
            "The Open Negotiation Period is shown. "
            "The start date is 3/10/2026 (one calendar day after 3/9/2026). "
            "The end date is 30 calendar days after 3/9/2026, extended by any "
            "federal holidays that fall within the period. "
            "Both dates are visible and the end date is on or after 4/8/2026."
        ),
    ),
    (
        "TC-03",
        "IDR Initiation Window",
        "nsa_idr_init_window",
        (
            "Select the 'IDR Initiation Window' radio option.\n"
            "Enter 3/9/2026 as the Open Negotiation Initiation Date in the dropdown above the calendar.\n"
            "Read the displayed IDR Initiation Window dates."
        ),
        (
            "The IDR Initiation Window is shown with a start date and end date. "
            "The start date equals the end of the Open Negotiation Period plus 1 business day "
            "(Open Neg. Initiation Date + 30 cal. days + federal holidays + 1 business day). "
            "The end date is 3 business days after the start date. "
            "Both dates are visible weekdays."
        ),
    ),
    (
        "TC-04",
        "IDRE Selection Window",
        "nsa_idre_selection_window",
        (
            "Select the 'IDRE Selection Window' radio option.\n"
            "Enter 4/9/2026 as the IDR Initiation Date in the dropdown above the calendar.\n"
            "Read the displayed IDRE Selection Window dates."
        ),
        (
            "The IDRE Selection Window is shown with start date 4/9/2026 "
            "and end date 4/14/2026 (IDR Initiation Date + 3 business days). "
            "Both dates are visible weekdays."
        ),
    ),
    (
        "TC-05",
        "IDR Offer Submission Window",
        "nsa_idr_offer_submission",
        (
            "Select the 'IDR Offer Submission Window' radio option.\n"
            "Enter 4/14/2026 as the IDRE Selection Date in the dropdown above the calendar.\n"
            "Read the displayed IDR Offer Submission Window dates."
        ),
        (
            "The IDR Offer Submission Window is shown with start date 4/14/2026 "
            "and end date 4/28/2026 (IDRE Selection Date + 10 business days). "
            "Both dates are visible weekdays."
        ),
    ),
    (
        "TC-06",
        "Written Determination Due Date",
        "nsa_written_determination",
        (
            "Select the 'Written Determination Due Date' radio option.\n"
            "Enter 4/14/2026 as the IDRE Selection Date in the dropdown above the calendar.\n"
            "Read the displayed Written Determination Due Date."
        ),
        (
            "A single Written Determination Due Date is shown. "
            "It equals 4/14/2026 + 30 business days. "
            "Counting from 4/14/2026, skipping weekends and the Memorial Day holiday "
            "(5/25/2026), the date should be 5/27/2026. "
            "The displayed date is a weekday."
        ),
    ),
    (
        "TC-07",
        "Payor Payment Due Date",
        "nsa_payor_payment_due",
        (
            "Select the 'Payor Payment Due Date' radio option.\n"
            "Enter 5/27/2026 as the Written Determination Date in the dropdown above the calendar.\n"
            "Read the displayed Payor Payment Due Date."
        ),
        (
            "A single Payor Payment Due Date is shown. "
            "It equals 5/27/2026 + 30 calendar days = 6/26/2026. "
            "The displayed date is 6/26/2026."
        ),
    ),
    (
        "TC-08",
        "Cooling-Off Period",
        "nsa_cooling_off_period",
        (
            "Select the 'Cooling-Off Period' radio option.\n"
            "Enter 5/27/2026 as the Written Determination Date in the dropdown above the calendar.\n"
            "Read the displayed Cooling-Off Period dates."
        ),
        (
            "The Cooling-Off Period is shown with start date 5/27/2026 "
            "and end date 8/25/2026 (Written Determination Date + 90 calendar days). "
            "Both dates are visible."
        ),
    ),
    (
        "TC-09",
        "Post-Cooling-Off-Period IDR Initiation Window",
        "nsa_post_cooling_off_idr",
        (
            "Select the 'Post-Cooling-Off-Period IDR Initiation Window' radio option.\n"
            "Enter 5/27/2026 as the Written Determination Date in the dropdown above the calendar.\n"
            "Read the displayed Post-Cooling-Off-Period IDR Initiation Window dates."
        ),
        (
            "The Post-Cooling-Off-Period IDR Initiation Window is shown. "
            "The start date is 5/27/2026 + 91 calendar days = 8/26/2026. "
            "The end date is 5/27/2026 + 90 calendar days + 30 business days "
            "(= 8/25/2026 + 30 business days). "
            "Both dates are visible and the end date is a weekday after the start date."
        ),
    ),
    # ── Edge cases with unambiguous expected outcomes ─────────────────────────
    (
        "TC-E01",
        "Edge: End Date on Saturday Rolls to Monday",
        "nsa_edge_saturday_boundary",
        (
            "Select the 'Open Negotiation Initiation Window' radio option.\n"
            "Enter 2/7/2026 as the Remit Receipt Date in the dropdown above the calendar.\n"
            "Read the displayed end date of the Open Negotiation Initiation Window."
        ),
        (
            "The Open Negotiation Initiation Window end date is displayed. "
            "The displayed end date must be a Monday or any other weekday — "
            "it must NOT be a Saturday. "
            "If the 30th business day would land on a Saturday, the tool correctly "
            "rolls the end date forward to the following Monday."
        ),
    ),
    (
        "TC-E02",
        "Edge: End Date on Sunday Rolls to Monday",
        "nsa_edge_sunday_boundary",
        (
            "Select the 'Open Negotiation Initiation Window' radio option.\n"
            "Enter 2/8/2026 as the Remit Receipt Date in the dropdown above the calendar.\n"
            "Read the displayed end date of the Open Negotiation Initiation Window."
        ),
        (
            "The Open Negotiation Initiation Window end date is displayed. "
            "The displayed end date must NOT be a Sunday. "
            "If the 30th business day calculation results in a Sunday, the tool "
            "correctly advances the end date to the following Monday."
        ),
    ),
    (
        "TC-E05",
        "Edge: End Date on Federal Holiday Rolls Forward",
        "nsa_edge_holiday_boundary",
        (
            "Select the 'Open Negotiation Initiation Window' radio option.\n"
            "Enter 7/15/2026 as the Remit Receipt Date in the dropdown above the calendar.\n"
            "Read the displayed end date of the Open Negotiation Initiation Window."
        ),
        (
            "The Open Negotiation Initiation Window end date is displayed. "
            "The displayed end date must NOT be a federal holiday. "
            "If the 30th business day lands on a federal holiday such as Labor Day "
            "(9/7/2026) or any other federal holiday, the tool must advance the end date "
            "to the next business day. Verify the displayed date is a non-holiday weekday."
        ),
    ),
]
# ─────────────────────────────────────────────────────────────────────────────


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


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def run_agent_case(
    repo_root: Path,
    *,
    test_id: str,
    action: str,
    prompt: str,
    success: str,
    start_url: str,
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
        start_url,
        "--actions",
        action,
        "--max-steps",
        "15",
        "--headless",
        "--verbose",
        "--max-subactions-per-function",
        "5",
        "--model",
        model,
    ]
    print(f"== Run {test_id} ==")
    run(cmd, cwd=repo_root, tee_path=log_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="NSA Calculator AgenticWebQA tests")
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument(
        "--url",
        default=DEFAULT_CALC_URL,
        help="URL of the NSA Account Date Calculator.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model override for AI runs (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--test",
        metavar="ID",
        help="Run a single test by ID (e.g. TC-01, TC-E02). Omit to run all.",
    )
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Missing ANTHROPIC_API_KEY environment variable.")

    repo_root = Path(__file__).resolve().parent.parent
    agent_view_dir = repo_root / "agent_view"

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

    test_cases = TEST_CASES
    if args.test:
        target = args.test.upper()
        test_cases = [tc for tc in TEST_CASES if tc[0].upper() == target]
        if not test_cases:
            raise SystemExit(
                f"Unknown test ID '{args.test}'. "
                f"Valid IDs: {', '.join(tc[0] for tc in TEST_CASES)}"
            )

    failures: list[str] = []

    for test_id, title, action, prompt, success in test_cases:
        log_name = f"nsa_{test_id.lower().replace('-', '_')}.log"
        log_path = repo_root / log_name
        if log_path.exists():
            log_path.unlink()
        reset_dir(agent_view_dir)
        try:
            run_agent_case(
                repo_root,
                test_id=test_id,
                action=action,
                prompt=prompt,
                success=success,
                start_url=args.url,
                model=args.model,
                log_path=log_path,
            )
            print(f"  PASS: {test_id} — {title}")
        except subprocess.CalledProcessError:
            print(f"  FAIL: {test_id} — {title}  (log: {log_name})")
            failures.append(test_id)

    print()
    if failures:
        print(f"Failed tests: {', '.join(failures)}")
        return 1

    total = len(test_cases)
    print(f"All {total} NSA calculator test(s) passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
