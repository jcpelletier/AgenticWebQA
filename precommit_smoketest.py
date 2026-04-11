#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


def run_step(name: str, cmd: list[str], repo_root: Path) -> None:
    print(f"[pre-commit] Running {name}...")
    completed = subprocess.run(cmd, cwd=repo_root, check=False)
    if completed.returncode != 0:
        joined = " ".join(cmd)
        raise RuntimeError(
            f"Command failed with exit code {completed.returncode}: {joined}"
        )


def main() -> int:
    started = time.monotonic()
    repo_root = Path(__file__).resolve().parent

    print(f"[pre-commit] Using Python: {sys.executable}")

    run_step(
        "AgenticWebQA format",
        [sys.executable, "-m", "ruff", "format", "."],
        repo_root,
    )
    run_step(
        "AgenticWebQA type checks",
        [sys.executable, "-m", "mypy", "."],
        repo_root,
    )
    run_step(
        "AgenticWebQA unit tests",
        [sys.executable, "-m", "pytest", "-q", "tests"],
        repo_root,
    )
    run_step(
        "AgenticWebQA login integration smoke test",
        [sys.executable, "./webtests/run_testlogin_local.py", "--skip-install"],
        repo_root,
    )

    elapsed = time.monotonic() - started
    print("[pre-commit] All checks passed.")
    print(f"[pre-commit] Total runtime: {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
