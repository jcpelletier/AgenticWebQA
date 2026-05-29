#!/usr/bin/env python3
"""
Run a registered AgenticWebQA test.

Works on the host / CI and inside the Docker qa container.

Usage:
    agenticwebqa-run-test <test-name> [--model <model>] [--no-headless]
    agenticwebqa-run-test --list

Environment variables:
    TEST_SITE_URL      Base URL of the app under test.
                       Default: http://127.0.0.1:8000 (host / CI)
                       Set to http://test-site:8000 inside Docker Compose.
    AGENTQA_REGISTRY   Path to tests_registry.json.
                       Default: ./tests_registry.json in the current directory.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Registry: env var → ./tests_registry.json in CWD. The package install has no
# fixed repo root, so the consumer's project root is the natural default.
REGISTRY = Path(os.environ.get(
    "AGENTQA_REGISTRY",
    Path.cwd() / "tests_registry.json"
))

# Site URL: localhost by default (host / CI); Docker Compose sets http://test-site:8000
DEFAULT_SITE_URL = os.environ.get("TEST_SITE_URL", "http://127.0.0.1:8000")

# Maps the success_type field (both GUI-style and short-form) to CLI flags.
SUCCESS_FLAG_MAP: dict[str, str] = {
    "visual":          "--visual-llm-success",
    "Visual (LLM)":    "--visual-llm-success",
    "text":            "--text-present-success",
    "Text Present":    "--text-present-success",
    "selector":        "--selector-present-success",
    "Selector Present": "--selector-present-success",
    "url":             "--url-match-success",
    "URL Match":       "--url-match-success",
}


def load_registry() -> dict:
    if not REGISTRY.is_file():
        print(f"error: registry not found at {REGISTRY}", file=sys.stderr)
        print("hint: run `agenticwebqa-init` in your project root to create one.",
              file=sys.stderr)
        sys.exit(1)
    with REGISTRY.open() as f:
        return json.load(f)


def substitute_url(original: str, site_url: str) -> str:
    """Replace the origin (scheme + host + port) in *original* with *site_url*."""
    return re.sub(r"https?://[^/]+", site_url.rstrip("/"), original)


def main() -> None:
    p = argparse.ArgumentParser(description="Run a registered AgenticWebQA test")
    p.add_argument("name", nargs="?", help="Test name from tests_registry.json")
    p.add_argument("--list", action="store_true", help="List all registered tests and exit")
    p.add_argument("--site-url", default=DEFAULT_SITE_URL,
                   help="Base URL of the app under test (default: $TEST_SITE_URL)")
    p.add_argument("--model", default=None, help="Override the LLM model")
    p.add_argument("--no-headless", action="store_true", help="Run with a visible browser")
    p.add_argument("--max-steps", type=int, default=20)
    p.add_argument("--max-subactions", type=int, default=None,
                   help="Override max subactions per learned function (registry max_subactions field)")
    args = p.parse_args()

    registry = load_registry()

    if args.list:
        print(f"Registered tests ({len(registry)}):")
        for name, spec in sorted(registry.items()):
            stype = spec.get("success_type", "visual")
            print(f"  {name:35s}  model={spec.get('model','?'):15s}  "
                  f"success={stype:8s}  actions={spec.get('actions','')}")
        return

    if not args.name:
        p.print_help()
        sys.exit(1)

    if args.name not in registry:
        print(f"error: test '{args.name}' not found.", file=sys.stderr)
        print(f"Available: {sorted(registry)}", file=sys.stderr)
        sys.exit(1)

    spec = registry[args.name]
    start_url = substitute_url(spec["start_url"], args.site_url)
    model = args.model or spec.get("model", "gpt-4o-mini")

    success_type = spec.get("success_type", "visual")
    success_flag = SUCCESS_FLAG_MAP.get(success_type, "--visual-llm-success")

    # max_subactions: CLI arg overrides registry field, registry overrides default of 5
    max_subactions = args.max_subactions or spec.get("max_subactions", 5)

    print(f"Test:    {args.name}")
    print(f"URL:     {start_url}")
    print(f"Model:   {model}")
    print(f"Success: {success_flag}  =  {spec['success_criteria']!r}")
    print(f"Actions: {spec.get('actions') or '(none)'}")
    print(f"MaxSub:  {max_subactions}")
    print()

    cmd = [
        sys.executable, "-u", "-m", "agenticwebqa",
        "--start-url", start_url,
        "--prompt", spec["prompt"],
        success_flag, spec["success_criteria"],
        "--max-steps", str(args.max_steps),
        "--max-subactions-per-function", str(max_subactions),
        "--verbose",
        "--model", model,
    ]
    if spec.get("actions"):
        cmd += ["--actions", spec["actions"]]
    if not args.no_headless:
        cmd.append("--headless")

    sys.exit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    main()
