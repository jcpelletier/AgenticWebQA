#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class RunResult:
    run_number: int
    exit_code: int
    duration_seconds: float

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


def _positive_int(raw_value: str) -> int:
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("runs must be an integer.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("runs must be greater than zero.")
    return parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a target script or command repeatedly and summarize "
            "pass/fail consistency."
        )
    )
    parser.add_argument(
        "--model",
        help=(
            "Optional AI model override forwarded to the target as "
            "'--model <value>' when not already present in forwarded args."
        ),
    )
    parser.add_argument(
        "target",
        help="Path to script (for example precommit_smoketest.py) or command name.",
    )
    parser.add_argument(
        "runs",
        type=_positive_int,
        help="Number of repeated runs to execute.",
    )
    parser.add_argument(
        "target_args",
        nargs=argparse.REMAINDER,
        help=(
            "Arguments to forward to the target. "
            "Use '--' to clearly separate forwarded flags if needed."
        ),
    )
    return parser.parse_args(argv)


def _normalize_target_args(target_args: Sequence[str]) -> list[str]:
    normalized_args = list(target_args)
    if normalized_args and normalized_args[0] == "--":
        return normalized_args[1:]
    return normalized_args


def _resolve_target_path(target: str, repo_root: Path) -> Path | None:
    provided_path = Path(target)
    candidates = [provided_path]
    if not provided_path.is_absolute():
        candidates.append((repo_root / provided_path).resolve())

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def _is_webtest_e2e_target(target: str, target_path: Path | None) -> bool:
    candidate = target_path if target_path is not None else Path(target)
    normalized_parts = [part.lower() for part in candidate.parts]
    return (
        "webtests" in normalized_parts
        and candidate.name.lower().startswith("run_test")
        and candidate.name.lower().endswith("_local.py")
    )


def resolve_command(
    target: str, target_args: Sequence[str], repo_root: Path, model: str | None = None
) -> list[str]:
    forwarded_args = _normalize_target_args(target_args)
    target_path = _resolve_target_path(target, repo_root)
    if (
        _is_webtest_e2e_target(target, target_path)
        and "--skip-install" not in forwarded_args
    ):
        forwarded_args = [*forwarded_args, "--skip-install"]
    if model and "--model" not in forwarded_args:
        forwarded_args = [*forwarded_args, "--model", model]
    if target_path is not None:
        suffix = target_path.suffix.lower()
        if suffix == ".py":
            return [sys.executable, str(target_path), *forwarded_args]
        if suffix == ".ps1":
            return [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(target_path),
                *forwarded_args,
            ]
        return [str(target_path), *forwarded_args]

    lowered = target.lower()
    if lowered.endswith(".py") or lowered.endswith(".ps1"):
        raise FileNotFoundError(f"Target script not found: {target}")
    return [target, *forwarded_args]


def run_consistency(command: list[str], runs: int, repo_root: Path) -> list[RunResult]:
    results: list[RunResult] = []
    command_text = " ".join(command)
    for run_number in range(1, runs + 1):
        print(f"[consistency] Run {run_number}/{runs}: {command_text}")
        run_started = time.monotonic()
        try:
            completed = subprocess.run(command, cwd=repo_root, check=False)
        except OSError as exc:
            raise RuntimeError(f"Unable to run target command: {command_text}") from exc
        run_duration = time.monotonic() - run_started
        run_result = RunResult(
            run_number=run_number,
            exit_code=completed.returncode,
            duration_seconds=run_duration,
        )
        status = "PASS" if run_result.passed else "FAIL"
        print(
            f"[consistency] {status} run {run_number}/{runs} "
            f"(exit {run_result.exit_code}, {run_duration:.1f}s)"
        )
        results.append(run_result)
    return results


def print_summary(results: Sequence[RunResult], total_runtime_seconds: float) -> None:
    total_runs = len(results)
    passed = sum(1 for result in results if result.passed)
    failed = total_runs - passed
    pass_rate = (passed / total_runs) * 100
    fail_rate = (failed / total_runs) * 100
    average_runtime = total_runtime_seconds / total_runs

    print("")
    print("[consistency] Summary:")
    print(f"[consistency]   Passed: {passed}/{total_runs} ({pass_rate:.1f}%)")
    print(f"[consistency]   Failed: {failed}/{total_runs} ({fail_rate:.1f}%)")
    print(f"[consistency]   Avg runtime/run: {average_runtime:.1f}s")
    print(f"[consistency]   Total runtime: {total_runtime_seconds:.1f}s")
    if failed > 0:
        print("[consistency] Result: INCONSISTENT (one or more failures)")
    else:
        print("[consistency] Result: CONSISTENT (all runs passed)")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parent.parent
    try:
        command = resolve_command(
            args.target, args.target_args, repo_root, model=args.model
        )
        print(f"[consistency] Using command: {' '.join(command)}")
        suite_started = time.monotonic()
        results = run_consistency(command, args.runs, repo_root)
        total_runtime = time.monotonic() - suite_started
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"[consistency] ERROR: {exc}", file=sys.stderr)
        return 2

    print_summary(results, total_runtime)
    return 1 if any(not result.passed for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
