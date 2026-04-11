#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StepResult:
    name: str
    command: list[str]
    exit_code: int
    duration_seconds: float

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


def run_step(name: str, cmd: list[str], repo_root: Path) -> StepResult:
    step_start = time.monotonic()
    print(f"[release-test] Running {name}...")
    completed = subprocess.run(cmd, cwd=repo_root, check=False)
    duration = time.monotonic() - step_start
    if completed.returncode == 0:
        print(f"[release-test] PASS: {name} ({duration:.1f}s)")
    else:
        print(
            f"[release-test] FAIL: {name} "
            f"(exit {completed.returncode}, {duration:.1f}s)"
        )
    return StepResult(
        name=name,
        command=cmd,
        exit_code=completed.returncode,
        duration_seconds=duration,
    )


def main() -> int:
    suite_start = time.monotonic()
    repo_root = Path(__file__).resolve().parent

    print(f"[release-test] Using Python: {sys.executable}")

    results = [
        run_step(
            "AgenticWebQA unit tests",
            [sys.executable, "-m", "pytest", "-q", "tests"],
            repo_root,
        ),
        run_step(
            "Login_demo e2e smoke test",
            [sys.executable, "./webtests/run_testlogin_local.py", "--skip-install"],
            repo_root,
        ),
        run_step(
            "Logout e2e smoke test",
            [sys.executable, "./webtests/run_testlogout_local.py", "--skip-install"],
            repo_root,
        ),
        run_step(
            "Register e2e smoke test",
            [
                sys.executable,
                "./webtests/run_testregister_local.py",
                "--skip-install",
                "--require-feature",
            ],
            repo_root,
        ),
        run_step(
            "ProfileOpen e2e smoke test",
            [
                sys.executable,
                "./webtests/run_testprofileopen_local.py",
                "--skip-install",
                "--require-feature",
            ],
            repo_root,
        ),
        run_step(
            "ProfileAboutEdit e2e smoke test",
            [
                sys.executable,
                "./webtests/run_testprofilepage_local.py",
                "--skip-install",
                "--require-feature",
            ],
            repo_root,
        ),
        run_step(
            "ProfileLocationCanada e2e smoke test",
            [
                sys.executable,
                "./webtests/run_testprofilelocation_local.py",
                "--skip-install",
                "--require-feature",
            ],
            repo_root,
        ),
        run_step(
            "ProfileLocationUSCalifornia e2e smoke test",
            [
                sys.executable,
                "./webtests/run_testprofilelocationus_local.py",
                "--skip-install",
                "--require-feature",
            ],
            repo_root,
        ),
        run_step(
            "ProfileMyDetails e2e smoke test",
            [
                sys.executable,
                "./webtests/run_testprofilemydetails_local.py",
                "--skip-install",
                "--require-feature",
            ],
            repo_root,
        ),
    ]

    print("")
    print("[release-test] Summary:")
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[release-test]   {status}: {result.name} (exit {result.exit_code})")

    passed_count = sum(1 for result in results if result.passed)
    failed_count = len(results) - passed_count
    print(
        f"[release-test] Totals: {passed_count} passed, "
        f"{failed_count} failed, {len(results)} total"
    )
    if failed_count > 0:
        print("[release-test] Release test suite completed with failures.")
    else:
        print("[release-test] All release tests passed.")

    elapsed = time.monotonic() - suite_start
    print(f"[release-test] Total runtime: {elapsed:.1f}s")
    return 1 if failed_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
