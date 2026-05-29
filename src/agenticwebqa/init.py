#!/usr/bin/env python3
"""Initialize an AgenticWebQA project in the current directory.

Creates `tests_registry.json` (empty registry) and an empty `Models/` directory
so a fresh project has the scaffolding the engine and skills expect.

Usage:
    agenticwebqa-init [--force]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REGISTRY_NAME = "tests_registry.json"
MODELS_DIR = "Models"


def main() -> None:
    p = argparse.ArgumentParser(description="Initialize an AgenticWebQA project")
    p.add_argument("--force", action="store_true",
                   help="Overwrite an existing tests_registry.json")
    p.add_argument("--path", default=".",
                   help="Project root to initialize (default: current directory)")
    args = p.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    registry = root / REGISTRY_NAME
    if registry.exists() and not args.force:
        print(f"{REGISTRY_NAME} already exists at {registry} (use --force to overwrite)")
    else:
        registry.write_text(json.dumps({}, indent=2) + "\n", encoding="utf-8")
        print(f"created {registry}")

    models = root / MODELS_DIR
    models.mkdir(exist_ok=True)
    gitkeep = models / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()
    print(f"created {models}/ (with .gitkeep)")

    print()
    print("Next steps:")
    print("  1. Add a test with the qa-test-authoring skill, or hand-edit "
          f"{REGISTRY_NAME}.")
    print("  2. Run it:  agenticwebqa-run-test <test-name>")
    print("  3. Commit tests_registry.json and Models/ so CI can replay learned actions.")


if __name__ == "__main__":
    main()
