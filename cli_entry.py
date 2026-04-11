#!/usr/bin/env python3
"""
CLI composition helpers for vision_playwright_openai_vision_poc.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
from typing import Callable, Optional, Sequence

from config_shared import add_shared_cli_arguments


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="POC: Playwright + OpenAI Vision (no tool) (vision-only)"
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help='Test prompt, e.g. "Go to https://example.com and log in..."',
    )
    parser.add_argument(
        "--success-criteria",
        required=True,
        help="Text describing what must be visible for FINAL: PASS.",
    )
    parser.add_argument(
        "--start-url", required=True, help="Start URL to open before running the test."
    )
    add_shared_cli_arguments(parser)
    return parser


def prepare_args(
    args: argparse.Namespace,
    *,
    logger: Optional[Callable[[str], None]] = None,
) -> argparse.Namespace:
    log = logger or (lambda _msg: None)

    if args.headless and args.step_training:
        log("[step-training] Disabled because headless mode is enabled.")
        args.step_training = False

    if args.step_training and not args.step_training_signal:
        args.step_training_signal = str(Path(".step_training_signal").resolve())

    if args.step_training and args.step_training_signal:
        try:
            signal_path = Path(args.step_training_signal)
            if not signal_path.exists():
                signal_path.write_text("0", encoding="utf-8")
        except Exception as exc:
            log(f"[step-training] Failed to initialize signal file: {exc}")
            args.step_training = False

    if args.start_url and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", args.start_url):
        args.start_url = f"https://{args.start_url}"

    return args


def parse_cli_args(
    argv: Optional[Sequence[str]] = None,
    *,
    logger: Optional[Callable[[str], None]] = None,
) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    return prepare_args(args, logger=logger)
