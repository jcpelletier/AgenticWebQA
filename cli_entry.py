#!/usr/bin/env python3
"""
CLI composition helpers for vision_playwright_openai_vision_poc.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import re
from typing import Callable, Optional, Sequence

from config_shared import (
    SuccessIndicatorConfig,
    SuccessIndicatorType,
    add_shared_cli_arguments,
)

_SUCCESS_INDICATOR_ARGS = (
    "--visual-llm-success",
    "--text-present-success",
    "--selector-present-success",
    "--url-match-success",
)

_INDICATOR_ARG_TO_TYPE: dict[str, SuccessIndicatorType] = {
    "visual_llm_success": SuccessIndicatorType.VISUAL_LLM,
    "text_present_success": SuccessIndicatorType.TEXT_PRESENT,
    "selector_present_success": SuccessIndicatorType.SELECTOR_PRESENT,
    "url_match_success": SuccessIndicatorType.URL_MATCH,
}

_SUCCESS_INDICATOR_HELP = "Provide exactly one of: " + ", ".join(
    _SUCCESS_INDICATOR_ARGS
)


def _check_deprecated_flag(argv: Sequence[str] | None) -> None:
    """Exit with a deprecation error if --success-criteria appears in argv."""
    check = list(argv) if argv is not None else sys.argv[1:]
    if "--success-criteria" in check:
        print(
            "Error: --success-criteria has been removed. "
            "Use --visual-llm-success instead.",
            file=sys.stderr,
        )
        sys.exit(1)


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
        "--visual-llm-success",
        default=None,
        help=(
            "Success criteria evaluated by the LLM via screenshot. "
            + _SUCCESS_INDICATOR_HELP
        ),
    )
    parser.add_argument(
        "--text-present-success",
        default=None,
        help=(
            "Pass when this text is present in visible page text. "
            "Prefix with 'regex:' for regex matching. " + _SUCCESS_INDICATOR_HELP
        ),
    )
    parser.add_argument(
        "--selector-present-success",
        default=None,
        help=(
            "Pass when this CSS selector matches at least one element. "
            + _SUCCESS_INDICATOR_HELP
        ),
    )
    parser.add_argument(
        "--url-match-success",
        default=None,
        help=(
            "Pass when the current URL contains this string. "
            "Prefix with 'regex:' for regex matching. " + _SUCCESS_INDICATOR_HELP
        ),
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

    # Resolve success indicator — exactly one must be provided.
    provided = {
        attr: getattr(args, attr, None)
        for attr in _INDICATOR_ARG_TO_TYPE
        if getattr(args, attr, None) is not None
    }
    if len(provided) == 0:
        print(
            "Error: a success indicator is required. "
            f"Provide exactly one of: {', '.join(_SUCCESS_INDICATOR_ARGS)}",
            file=sys.stderr,
        )
        sys.exit(1)
    if len(provided) > 1:
        flags = [f"--{k.replace('_', '-')}" for k in provided]
        print(
            f"Error: only one success indicator may be provided; got {', '.join(flags)}. "
            f"Provide exactly one of: {', '.join(_SUCCESS_INDICATOR_ARGS)}",
            file=sys.stderr,
        )
        sys.exit(1)

    attr, value = next(iter(provided.items()))
    args.success_indicator = SuccessIndicatorConfig(
        type=_INDICATOR_ARG_TO_TYPE[attr],
        value=str(value),
    )

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
    _check_deprecated_flag(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    return prepare_args(args, logger=logger)
