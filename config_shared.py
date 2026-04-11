#!/usr/bin/env python3
"""
Shared configuration defaults used by both CLI and UI entrypoints.
"""

from __future__ import annotations

import argparse
import enum
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Sequence


# Model defaults/options
DEFAULT_MODEL = "gpt-5.4"
OPENAI_MODEL_OPTIONS = [
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5.2",
    "gpt-5.1",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
]
CLAUDE_MODEL_OPTIONS = [
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
    "claude-sonnet-4-5",
    "claude-opus-4-5",
    "claude-opus-4-1",
    "claude-sonnet-4-0",
]
GEMINI_MODEL_OPTIONS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODEL_OPTIONS = OPENAI_MODEL_OPTIONS + CLAUDE_MODEL_OPTIONS + GEMINI_MODEL_OPTIONS

# Shared timing/token defaults
DEFAULT_MAX_TOKENS_MARGIN = 512
DEFAULT_VERIFY_WAIT_S = 2.0
DEFAULT_VERIFY_GUARD_MIN_CONFIDENCE = 0.8
DEFAULT_VIEWPORT_W = 1280
DEFAULT_VIEWPORT_H = 800
DEFAULT_PRE_CLICK_SLEEP_S = 0.35
DEFAULT_PRE_TYPE_SLEEP_S = 0.5
DEFAULT_POST_SHOT_SLEEP_S = 0.2
DEFAULT_POST_ACTION_SLEEP_S = 0.25
DEFAULT_POST_TYPE_SLEEP_S = 0.25

# Shared safety/cost defaults
DEFAULT_ARM_TIMEOUT_STEPS = 3
DEFAULT_KEEP_LAST_TURNS = 10
DEFAULT_KEEP_LAST_IMAGES = 1
DEFAULT_X_SIZE_PX = 18
DEFAULT_X_THICKNESS_PX = 4
DEFAULT_CONFIRM_TOKEN = "CONFIRM"
DEFAULT_SITE_HINTS_PATH = "site_hints.json"

# Shared run defaults
DEFAULT_SLOWMO_MS = 250
DEFAULT_MAX_STEPS = 40
DEFAULT_MAX_SUBACTIONS_PER_FUNCTION = 6
DEFAULT_SCREENSHOT_BASE = "run.png"
DEFAULT_AGENT_VIEW_DIR = "agent_view"


class SuccessIndicatorType(enum.Enum):
    VISUAL_LLM = "visual_llm"
    TEXT_PRESENT = "text_present"
    SELECTOR_PRESENT = "selector_present"
    URL_MATCH = "url_match"


@dataclass
class SuccessIndicatorConfig:
    type: SuccessIndicatorType
    value: str
    compiled_pattern: Optional[re.Pattern[str]] = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.value.startswith("regex:"):
            self.compiled_pattern = re.compile(self.value[len("regex:") :])


@dataclass(frozen=True)
class SharedArgSpec:
    flag: str
    kind: Literal["str", "int", "float", "bool"]
    default: Any
    help_text: str
    ui_key: Optional[str] = None
    ui_label: Optional[str] = None
    ui_emit_mode: Literal["always", "if_nonempty", "if_true"] = "always"
    min_value: Optional[float] = None
    max_value: Optional[float] = None


SHARED_ARG_SPECS: Sequence[SharedArgSpec] = (
    SharedArgSpec(
        "--actions",
        "str",
        "",
        "Comma-separated action names to run in order (e.g., login, search).",
        ui_key="-ACTIONS-",
        ui_label="Actions",
        ui_emit_mode="if_nonempty",
    ),
    SharedArgSpec(
        "--model",
        "str",
        DEFAULT_MODEL,
        f"LLM model (OpenAI/Claude) (default: {DEFAULT_MODEL})",
        ui_key="-MODEL-",
        ui_label="Model",
    ),
    SharedArgSpec(
        "--width",
        "int",
        DEFAULT_VIEWPORT_W,
        f"ACTUAL viewport width (default: {DEFAULT_VIEWPORT_W})",
        ui_key="-WIDTH-",
        ui_label="Width",
        min_value=1,
    ),
    SharedArgSpec(
        "--height",
        "int",
        DEFAULT_VIEWPORT_H,
        f"ACTUAL viewport height (default: {DEFAULT_VIEWPORT_H})",
        ui_key="-HEIGHT-",
        ui_label="Height",
        min_value=1,
    ),
    SharedArgSpec(
        "--model-width",
        "int",
        0,
        "MODEL screenshot/tool width. If 0, uses --width. (e.g. 960)",
        ui_key="-MODEL-W-",
        ui_label="Model width",
        min_value=0,
    ),
    SharedArgSpec(
        "--model-height",
        "int",
        0,
        "MODEL screenshot/tool height. If 0, uses --height. (e.g. 900)",
        ui_key="-MODEL-H-",
        ui_label="Model height",
        min_value=0,
    ),
    SharedArgSpec(
        "--headless",
        "bool",
        True,
        "Run browser headless (default: headless)",
        ui_key="-HEADLESS-",
        ui_emit_mode="if_true",
    ),
    SharedArgSpec(
        "--step-training",
        "bool",
        False,
        "Pause before committing LLM actions (headed only).",
        ui_key="-STEP-TRAIN-",
        ui_emit_mode="if_true",
    ),
    SharedArgSpec(
        "--step-training-signal",
        "str",
        "",
        "Signal file path used to continue Step Training.",
    ),
    SharedArgSpec(
        "--slowmo",
        "int",
        DEFAULT_SLOWMO_MS,
        f"Playwright slowmo in ms (default: {DEFAULT_SLOWMO_MS})",
        ui_key="-SLOWMO-",
        ui_label="Slowmo",
        min_value=0,
    ),
    SharedArgSpec(
        "--max-steps",
        "int",
        DEFAULT_MAX_STEPS,
        f"Max agent loop iterations (default: {DEFAULT_MAX_STEPS})",
        ui_key="-MAX-STEPS-",
        ui_label="Max steps",
        min_value=1,
    ),
    SharedArgSpec(
        "--max-tokens",
        "int",
        0,
        "Max tokens for model response. If 0, uses low default (384).",
        ui_key="-MAX-TOKENS-",
        ui_label="Max tokens",
        min_value=0,
    ),
    SharedArgSpec(
        "--max-tokens-margin",
        "int",
        DEFAULT_MAX_TOKENS_MARGIN,
        "Thinking margin.",
        ui_key="-MAX-TOK-MARGIN-",
        ui_label="Max tokens margin",
        min_value=0,
    ),
    SharedArgSpec(
        "--verify-wait",
        "float",
        DEFAULT_VERIFY_WAIT_S,
        "Seconds to wait before LLM verification (default: 2.0).",
        ui_key="-VERIFY-WAIT-",
        ui_label="Verify wait",
        min_value=0,
    ),
    SharedArgSpec(
        "--verify-guard-min-confidence",
        "float",
        DEFAULT_VERIFY_GUARD_MIN_CONFIDENCE,
        "Minimum confidence (0.0-1.0) for the in-step verify guard to accept PASS. "
        "Low-confidence passes are treated as FAIL to prevent premature termination (default: 0.8).",
        ui_key="-VERIFY-GUARD-CONF-",
        ui_label="Verify guard min confidence",
        min_value=0.0,
        max_value=1.0,
    ),
    SharedArgSpec(
        "--pre-click-sleep",
        "float",
        DEFAULT_PRE_CLICK_SLEEP_S,
        "Sleep before click-like actions.",
        ui_key="-PRECLICK-",
        ui_label="Pre-click sleep",
        min_value=0,
    ),
    SharedArgSpec(
        "--pre-type-sleep",
        "float",
        DEFAULT_PRE_TYPE_SLEEP_S,
        "Sleep before Playwright type actions.",
        ui_key="-PRETYPE-",
        ui_label="Pre-type sleep",
        min_value=0,
    ),
    SharedArgSpec(
        "--post-shot-sleep",
        "float",
        DEFAULT_POST_SHOT_SLEEP_S,
        "Sleep after each model screenshot.",
        ui_key="-POST-SHOT-",
        ui_label="Post-shot sleep",
        min_value=0,
    ),
    SharedArgSpec(
        "--post-action-sleep",
        "float",
        DEFAULT_POST_ACTION_SLEEP_S,
        "Sleep after each Playwright action.",
        ui_key="-POST-ACTION-",
        ui_label="Post-action sleep",
        min_value=0,
    ),
    SharedArgSpec(
        "--post-type-sleep",
        "float",
        DEFAULT_POST_TYPE_SLEEP_S,
        "Sleep after Playwright type actions.",
        ui_key="-POST-TYPE-",
        ui_label="Post-type sleep",
        min_value=0,
    ),
    SharedArgSpec(
        "--arm-commit",
        "bool",
        False,
        "Enable Arm/Commit gating for left_click/double_click.",
        ui_key="-ARM-COMMIT-",
        ui_emit_mode="if_true",
    ),
    SharedArgSpec(
        "--confirm-token",
        "str",
        DEFAULT_CONFIRM_TOKEN,
        f"Token required in WHY line to commit (default: {DEFAULT_CONFIRM_TOKEN}).",
        ui_key="-CONFIRM-",
        ui_label="Confirm token",
    ),
    SharedArgSpec(
        "--arm-timeout-steps",
        "int",
        DEFAULT_ARM_TIMEOUT_STEPS,
        "Expire armed click after N steps.",
        ui_key="-ARM-TIMEOUT-",
        ui_label="Arm timeout steps",
        min_value=1,
    ),
    SharedArgSpec(
        "--keep-last-turns",
        "int",
        DEFAULT_KEEP_LAST_TURNS,
        "Cost control: keep last N messages.",
        ui_key="-KEEP-TURNS-",
        ui_label="Keep last turns",
        min_value=0,
    ),
    SharedArgSpec(
        "--keep-last-images",
        "int",
        DEFAULT_KEEP_LAST_IMAGES,
        "Cost control: keep last N screenshot tool_results with images (capped at 1).",
        ui_key="-KEEP-IMAGES-",
        ui_label="Keep last images",
        min_value=0,
    ),
    SharedArgSpec(
        "--x-size", "int", DEFAULT_X_SIZE_PX, "Red X half-size px.", min_value=1
    ),
    SharedArgSpec(
        "--x-thickness",
        "int",
        DEFAULT_X_THICKNESS_PX,
        "Red X thickness px.",
        min_value=1,
    ),
    SharedArgSpec(
        "--max-subactions-per-function",
        "int",
        DEFAULT_MAX_SUBACTIONS_PER_FUNCTION,
        f"Hard cap on actions per learned function (default: {DEFAULT_MAX_SUBACTIONS_PER_FUNCTION}).",
        ui_key="-MAX-SUBACTIONS-",
        ui_label="Max subactions per function",
        min_value=1,
    ),
    SharedArgSpec(
        "--verbose",
        "bool",
        False,
        "Verbose logging",
        ui_key="-VERBOSE-",
        ui_emit_mode="if_true",
    ),
    SharedArgSpec(
        "--log-file",
        "str",
        "",
        "Optional log file path; duplicates stdout/stderr to this file.",
        ui_key="-LOG-FILE-",
        ui_label="Log file",
        ui_emit_mode="if_nonempty",
    ),
    SharedArgSpec(
        "--Azure-Logging",
        "bool",
        False,
        "Enable Azure Application Insights logging (best-effort).",
        ui_key="-AZURE-",
        ui_emit_mode="if_true",
    ),
    SharedArgSpec(
        "--screenshot-base",
        "str",
        DEFAULT_SCREENSHOT_BASE,
        'Base screenshot path; writes "<base>.success.png" or "<base>.failure.png"',
        ui_key="-SCREENSHOT-",
        ui_label="Screenshot base",
    ),
    SharedArgSpec(
        "--agent-view-dir",
        "str",
        DEFAULT_AGENT_VIEW_DIR,
        "Directory for per-step agent_view screenshots",
        ui_key="-AGENT-DIR-",
        ui_label="Agent view dir",
    ),
    SharedArgSpec(
        "--no-agent-view",
        "bool",
        False,
        "Disable extra agent_view debug captures",
        ui_key="-NO-AGENT-",
        ui_emit_mode="if_true",
    ),
    SharedArgSpec(
        "--site-hints-path",
        "str",
        DEFAULT_SITE_HINTS_PATH,
        "JSON file for per-site DOM hints.",
        ui_key="-SITE-HINTS-",
        ui_label="Site hints path",
    ),
)


def infer_model_provider(model_name: str) -> Literal["openai", "anthropic", "gemini"]:
    model = (model_name or "").strip().lower()
    if model.startswith("claude") or model.startswith("anthropic."):
        return "anthropic"
    if model.startswith("gemini"):
        return "gemini"
    return "openai"


def model_api_env_var(model_name: str) -> str:
    provider = infer_model_provider(model_name)
    if provider == "anthropic":
        return "ANTHROPIC_API_KEY"
    if provider == "gemini":
        return "GEMINI_API_KEY"
    return "OPENAI_API_KEY"


def _spec_by_flag(flag: str) -> SharedArgSpec:
    for spec in SHARED_ARG_SPECS:
        if spec.flag == flag:
            return spec
    raise KeyError(flag)


def ui_spec_by_key(ui_key: str) -> SharedArgSpec:
    for spec in SHARED_ARG_SPECS:
        if spec.ui_key == ui_key:
            return spec
    raise KeyError(ui_key)


def _python_type(kind: str):
    if kind == "int":
        return int
    if kind == "float":
        return float
    return str


def _format_bounds_message(
    label: str, *, min_value: Optional[float], max_value: Optional[float]
) -> str:
    if min_value is not None and max_value is not None:
        return f"{label} must be between {min_value:g} and {max_value:g}."
    if min_value is not None:
        return f"{label} must be >= {min_value:g}."
    if max_value is not None:
        return f"{label} must be <= {max_value:g}."
    return f"{label} has invalid value."


def _validate_numeric_bounds(value: float, spec: SharedArgSpec, *, label: str) -> None:
    if spec.min_value is not None and value < spec.min_value:
        raise ValueError(
            _format_bounds_message(
                label, min_value=spec.min_value, max_value=spec.max_value
            )
        )
    if spec.max_value is not None and value > spec.max_value:
        raise ValueError(
            _format_bounds_message(
                label, min_value=spec.min_value, max_value=spec.max_value
            )
        )


def _coerce_cli_numeric(raw: str, spec: SharedArgSpec):
    assert spec.kind in ("int", "float")
    label = spec.ui_label or spec.flag
    try:
        value = int(raw) if spec.kind == "int" else float(raw)
    except Exception as exc:
        if spec.kind == "int":
            raise argparse.ArgumentTypeError(f"{label} must be an integer.") from exc
        raise argparse.ArgumentTypeError(f"{label} must be a number.") from exc
    try:
        _validate_numeric_bounds(float(value), spec, label=label)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return value


def add_shared_cli_arguments(parser: argparse.ArgumentParser) -> None:
    for spec in SHARED_ARG_SPECS:
        kwargs: Dict[str, Any] = {"help": spec.help_text}
        if spec.kind == "bool":
            kwargs["action"] = "store_true"
        elif spec.kind in ("int", "float"):
            kwargs["type"] = lambda raw, _spec=spec: _coerce_cli_numeric(raw, _spec)
            kwargs["default"] = spec.default
        else:
            kwargs["type"] = _python_type(spec.kind)
            kwargs["default"] = spec.default
        parser.add_argument(spec.flag, **kwargs)


def parse_ui_value(raw: Any, *, flag: str) -> Any:
    spec = _spec_by_flag(flag)
    if spec.kind == "bool":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.strip().lower() in ("1", "true", "yes", "on")
        return bool(raw)

    text = "" if raw is None else str(raw).strip()
    if text == "":
        text = str(spec.default)

    label = spec.ui_label or spec.flag
    if spec.kind == "int":
        try:
            value = int(text)
        except Exception as exc:
            raise ValueError(f"{label} must be an integer.") from exc
        _validate_numeric_bounds(float(value), spec, label=label)
        return value
    if spec.kind == "float":
        try:
            float_value = float(text)
        except Exception as exc:
            raise ValueError(f"{label} must be a number.") from exc
        _validate_numeric_bounds(float_value, spec, label=label)
        return float_value
    return text


def build_shared_ui_cli_args(values: Dict[str, Any]) -> List[str]:
    args: List[str] = []
    for spec in SHARED_ARG_SPECS:
        if not spec.ui_key:
            continue
        raw = values.get(spec.ui_key)
        if spec.kind == "bool":
            if parse_ui_value(raw, flag=spec.flag):
                args.append(spec.flag)
            continue

        text = "" if raw is None else str(raw).strip()
        if spec.ui_emit_mode == "if_nonempty" and text == "":
            continue
        parsed = parse_ui_value(raw, flag=spec.flag)
        args.extend([spec.flag, str(parsed)])
    return args


def build_shared_ui_defaults(
    include_keys: Optional[Sequence[str]] = None,
    *,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    selected = set(include_keys) if include_keys is not None else None
    out: Dict[str, Any] = {}
    for spec in SHARED_ARG_SPECS:
        key = spec.ui_key
        if not key:
            continue
        if selected is not None and key not in selected:
            continue
        out[key] = spec.default
    if overrides:
        out.update(overrides)
    return out
