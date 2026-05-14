#!/usr/bin/env python3
"""
vision_playwright_openai_vision_poc.py

Vision-only browser automation using:
- Playwright (Chromium) for real browser rendering/control
- OpenAI vision model for screenshot-based UI actions (no Computer Use tool)

Reliability improvements:
- scale="css" screenshots so pixel coords match Playwright CSS pixel coordinates
- stability waits before click-like actions to reduce layout-shift misclicks
- red X annotations on saved screenshots for click-like actions
- Arm/Commit gating for left_click/double_click (preview first; require CONFIRM token to commit)

Cost reductions:
- Lower default max tokens (384)
- Optional screenshot downscaling sent to model (--model-width/--model-height)

Notes:
- Playwright page screenshots do NOT include browser chrome (tabs/address bar).
- The agent must use in-page UI; it cannot click the address bar.

FINAL VERDICT PROTOCOL (strict):
- Model MUST finish with exactly one of:
    FINAL: PASS
    FINAL: FAIL
"""

import atexit
import base64
import copy
import datetime
import io
import os
import random
import re
import string
import sys
import time
import json
import logging
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TextIO,
    Tuple,
    cast,
)

import openai
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, Locator
from cli_entry import parse_cli_args
from config_shared import (
    DEFAULT_MAX_SUBACTIONS_PER_FUNCTION,
    DEFAULT_MODEL,
    DEFAULT_X_SIZE_PX,
    DEFAULT_X_THICKNESS_PX,
    GEMINI_BASE_URL,
    SuccessIndicatorConfig,
    SuccessIndicatorType,
    infer_model_provider,
    model_api_env_var,
)

OpenAIClient = Any
OpenAI = getattr(openai, "OpenAI", None)
anthropic_mod: Any = None
try:
    import anthropic as _anthropic_mod

    anthropic_mod = _anthropic_mod
except Exception:
    pass
AnthropicClient = Any


def _new_openai_client(api_key: str) -> OpenAIClient:
    client_factory = OpenAI
    if client_factory is None:
        raise RuntimeError(
            "openai.OpenAI is unavailable. Upgrade the openai package to a version that provides OpenAI client."
        )
    return cast(OpenAIClient, client_factory(api_key=api_key))


def _new_gemini_client(api_key: str) -> OpenAIClient:
    client_factory = OpenAI
    if client_factory is None:
        raise RuntimeError(
            "openai.OpenAI is unavailable. Upgrade the openai package to a version that provides OpenAI client."
        )
    return cast(OpenAIClient, client_factory(api_key=api_key, base_url=GEMINI_BASE_URL))


def _new_anthropic_client(api_key: str) -> AnthropicClient:
    if anthropic_mod is None or getattr(anthropic_mod, "Anthropic", None) is None:
        raise RuntimeError(
            "anthropic.Anthropic is unavailable. Install/upgrade the anthropic package."
        )
    return cast(AnthropicClient, anthropic_mod.Anthropic(api_key=api_key))


@dataclass
class _UnifiedUsage:
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None


@dataclass
class _UnifiedResponse:
    output_text: str
    output: List[Dict[str, Any]]
    usage: Optional[_UnifiedUsage]
    provider: str
    raw_response: Any = None

    def model_dump(self) -> Dict[str, Any]:
        usage: Dict[str, Any] = {}
        if self.usage is not None:
            usage = {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
                "cache_creation_input_tokens": self.usage.cache_creation_input_tokens,
                "cache_read_input_tokens": self.usage.cache_read_input_tokens,
            }
        return {
            "output_text": self.output_text,
            "output": self.output,
            "usage": usage,
            "provider": self.provider,
        }


def _responses_req_to_chat_completions_req(req: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a Responses API request dict to a Chat Completions request dict.

    Gemini's OpenAI-compatible endpoint only supports /chat/completions, not
    /responses.  This function translates the request shape so we can call
    client.chat.completions.create() instead.
    """
    chat_req: Dict[str, Any] = {}

    chat_req["model"] = req.get("model")

    # max_output_tokens (Responses API) → max_tokens (Chat Completions)
    if "max_output_tokens" in req:
        chat_req["max_tokens"] = int(req["max_output_tokens"])

    # Convert input list → messages list
    input_items = req.get("input") or []
    messages: List[Dict[str, Any]] = []
    for item in input_items:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user").strip().lower()
        raw_content = item.get("content")
        if isinstance(raw_content, str):
            messages.append({"role": role, "content": raw_content})
            continue
        if not isinstance(raw_content, list):
            continue
        parts: List[Dict[str, Any]] = []
        for block in raw_content:
            if not isinstance(block, dict):
                continue
            btype = str(block.get("type") or "").strip().lower()
            if btype in ("input_text", "output_text", "text"):
                parts.append({"type": "text", "text": str(block.get("text") or "")})
            elif btype == "input_image":
                image_url = str(block.get("image_url") or "")
                parts.append({"type": "image_url", "image_url": {"url": image_url}})
        if not parts:
            continue
        # Simplify to a plain string for non-user/single-text messages
        if len(parts) == 1 and parts[0]["type"] == "text" and role != "user":
            messages.append({"role": role, "content": parts[0]["text"]})
        else:
            messages.append({"role": role, "content": parts})
    if messages:
        chat_req["messages"] = messages

    # response_format: Gemini's OpenAI-compatible endpoint supports json_object
    # but not the full json_schema type (additionalProperties etc. are ignored/broken).
    # Convert json_schema → json_object so the model returns valid JSON without
    # schema enforcement; the prompts already specify the expected structure.
    if "response_format" in req:
        rf = req["response_format"]
        if isinstance(rf, dict) and rf.get("type") == "json_schema":
            chat_req["response_format"] = {"type": "json_object"}
        else:
            chat_req["response_format"] = rf

    # Gemini needs more headroom than gpt-style models for JSON output.
    # Bump small token budgets so the model can complete structured responses.
    _GEMINI_MIN_JSON_TOKENS = 256
    if (
        "max_tokens" in chat_req
        and int(chat_req["max_tokens"]) < _GEMINI_MIN_JSON_TOKENS
    ):
        has_json_output = "response_format" in chat_req
        if has_json_output:
            chat_req["max_tokens"] = _GEMINI_MIN_JSON_TOKENS

    # Drop Responses-API-only fields: reasoning, previous_response_id
    return chat_req


class _ChatCompletionsUsageWrapper:
    """Adapts a Chat Completions usage object to look like a Responses API usage."""

    def __init__(self, usage: Any) -> None:
        pt = getattr(usage, "prompt_tokens", None) if usage is not None else None
        ct = getattr(usage, "completion_tokens", None) if usage is not None else None
        self.input_tokens: Optional[int] = (
            int(pt) if isinstance(pt, (int, float)) else None
        )
        self.output_tokens: Optional[int] = (
            int(ct) if isinstance(ct, (int, float)) else None
        )
        self.cache_creation_input_tokens: Optional[int] = None
        self.cache_read_input_tokens: Optional[int] = None


class _ChatCompletionsResponseWrapper:
    """Wraps a Chat Completions response to look like a Responses API response.

    This lets extract_openai_response_text(), print_usage_tokens(), and all
    other Responses-API consumers work unchanged when talking to Gemini.
    """

    def __init__(self, cc_resp: Any) -> None:
        choice = (
            (cc_resp.choices[0] if cc_resp.choices else None)
            if hasattr(cc_resp, "choices")
            else None
        )
        content = ""
        if choice is not None:
            msg = getattr(choice, "message", None)
            if msg is not None:
                content = getattr(msg, "content", None) or ""
        self.output_text: str = content if isinstance(content, str) else ""
        self.output: List[Dict[str, Any]] = [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": self.output_text}],
            }
        ]
        self.usage = _ChatCompletionsUsageWrapper(getattr(cc_resp, "usage", None))
        self.id: Optional[str] = getattr(cc_resp, "id", None)


class _ResponsesAdapter:
    def __init__(self, provider: str, client: Any) -> None:
        self._provider = provider
        self._client = client

    def create(self, **req: Any) -> Any:
        if self._provider == "gemini":
            chat_req = _responses_req_to_chat_completions_req(req)
            cc_resp = self._client.chat.completions.create(**chat_req)
            return _ChatCompletionsResponseWrapper(cc_resp)
        if self._provider == "openai":
            return self._client.responses.create(**req)
        return _anthropic_create_normalized_response(self._client, req)


class _ModelClientAdapter:
    def __init__(self, provider: str, client: Any) -> None:
        self.provider = provider
        self.responses = _ResponsesAdapter(provider, client)


def _extract_b64_from_data_url(url: str) -> Optional[str]:
    marker = "base64,"
    idx = url.find(marker)
    if idx < 0:
        return None
    return url[idx + len(marker) :].strip() or None


def _coerce_openai_input_to_anthropic(
    input_items: Any,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    messages: List[Dict[str, Any]] = []
    system_parts: List[str] = []
    if not isinstance(input_items, list):
        return messages, None

    for item in input_items:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user").strip().lower()
        if role == "system":
            content = item.get("content")
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    text = str(block.get("text") or "").strip()
                    if text:
                        system_parts.append(text)
            continue
        if role not in ("user", "assistant"):
            role = "user"

        raw_content = item.get("content")
        blocks: List[Dict[str, Any]] = []
        if isinstance(raw_content, list):
            for block in raw_content:
                if not isinstance(block, dict):
                    continue
                btype = str(block.get("type") or "").strip().lower()
                if btype in ("input_text", "output_text", "text"):
                    text = str(block.get("text") or "").strip()
                    if text:
                        blocks.append({"type": "text", "text": text})
                    continue
                if btype == "input_image":
                    image_url = str(block.get("image_url") or "").strip()
                    b64 = _extract_b64_from_data_url(image_url)
                    if b64:
                        blocks.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b64,
                                },
                            }
                        )
                    continue
                if btype == "tool_output":
                    tool_call_id = str(block.get("tool_call_id") or "").strip()
                    output_text = str(block.get("output") or "").strip()
                    summary = f"tool_output[{tool_call_id}]: {output_text}".strip()
                    if summary:
                        blocks.append({"type": "text", "text": summary})
        elif isinstance(raw_content, str):
            txt = raw_content.strip()
            if txt:
                blocks.append({"type": "text", "text": txt})

        if blocks:
            messages.append({"role": role, "content": blocks})

    system_text = "\n\n".join([p for p in system_parts if p]).strip() or None
    return messages, system_text


def _anthropic_create_normalized_response(
    client: AnthropicClient, req: Dict[str, Any]
) -> _UnifiedResponse:
    model_name = str(req.get("model") or "").strip()
    max_tokens = int(req.get("max_output_tokens") or req.get("max_tokens") or 384)
    input_items = req.get("input") or []
    messages, system_text = _coerce_openai_input_to_anthropic(input_items)
    if not messages:
        messages = [{"role": "user", "content": [{"type": "text", "text": ""}]}]
    anth_req: Dict[str, Any] = {
        "model": model_name,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system_text:
        anth_req["system"] = system_text
    resp = client.messages.create(**cast(Any, anth_req))

    content_items = getattr(resp, "content", None) or []
    text_parts: List[str] = []
    output_content: List[Dict[str, Any]] = []
    output_types: List[Dict[str, Any]] = []
    for block in content_items if isinstance(content_items, list) else []:
        btype = getattr(block, "type", None)
        if btype is None and isinstance(block, dict):
            btype = block.get("type")
        btype_str = str(btype or "")
        text_val = ""
        if isinstance(block, dict):
            text_val = str(block.get("text") or "").strip()
        else:
            text_val = str(getattr(block, "text", "") or "").strip()
        if btype_str == "text" and text_val:
            text_parts.append(text_val)
            output_content.append({"type": "output_text", "text": text_val})
        elif btype_str:
            output_types.append({"type": "reasoning", "text": text_val})

    usage_raw = getattr(resp, "usage", None)
    usage = None
    if usage_raw is not None:
        usage = _UnifiedUsage(
            input_tokens=_get_usage_value(usage_raw, "input_tokens"),
            output_tokens=_get_usage_value(usage_raw, "output_tokens"),
            cache_creation_input_tokens=_get_usage_value(
                usage_raw, "cache_creation_input_tokens"
            ),
            cache_read_input_tokens=_get_usage_value(
                usage_raw, "cache_read_input_tokens"
            ),
        )
    output: List[Dict[str, Any]] = [{"type": "message", "content": output_content}]
    output.extend(output_types)
    return _UnifiedResponse(
        output_text="\n".join([p for p in text_parts if p]).strip(),
        output=output,
        usage=usage,
        provider="anthropic",
        raw_response=resp,
    )


def _new_model_client(model_name: str, api_key: str) -> _ModelClientAdapter:
    provider = infer_model_provider(model_name)
    if provider == "anthropic":
        return _ModelClientAdapter("anthropic", _new_anthropic_client(api_key))
    if provider == "gemini":
        return _ModelClientAdapter("gemini", _new_gemini_client(api_key))
    return _ModelClientAdapter("openai", _new_openai_client(api_key))


Image: Any
ImageDraw: Any
try:
    from PIL import Image, ImageDraw

    PIL_OK = True
except Exception:
    Image = None
    ImageDraw = None
    PIL_OK = False


# -----------------------------
# Logging helpers
# -----------------------------

_LOG_FILE_HANDLE: Optional[TextIO] = None
LOGGER = logging.getLogger("vision_poc")


def _init_logger() -> None:
    if getattr(LOGGER, "_configured", False):
        return
    LOGGER.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    # Reconfigure stream to utf-8 so Unicode chars like ✓ don't crash on cp1252 consoles
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except AttributeError:
        pass
    LOGGER.addHandler(handler)
    LOGGER.propagate = False
    setattr(LOGGER, "_configured", True)


def _refresh_logger_stream() -> None:
    if not getattr(LOGGER, "_configured", False):
        return
    for handler in LOGGER.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.stream = sys.stdout


def _squelch_final_tokens(message: str) -> str:
    return re.sub(r"(?im)^[^\n]*FINAL:\s*(PASS|FAIL)[^\n]*\n?", "", message).rstrip(
        "\n"
    )


def _log_info(message: str, *, allow_final: bool = False) -> None:
    _init_logger()
    if not allow_final:
        message = _squelch_final_tokens(message)
    LOGGER.info(message)


def _log_warn(message: str, *, allow_final: bool = False) -> None:
    _init_logger()
    if not allow_final:
        message = _squelch_final_tokens(message)
    LOGGER.warning(message)


def _log_error(message: str, *, allow_final: bool = False) -> None:
    _init_logger()
    if not allow_final:
        message = _squelch_final_tokens(message)
    LOGGER.error(message)


def _log_timing(
    label: str,
    seconds: float,
    *,
    verbose: bool = False,
    warn_threshold_s: float = 2.0,
    extra: str = "",
) -> None:
    if verbose or seconds >= warn_threshold_s:
        suffix = f" {extra}" if extra else ""
        _log_info(f"[timing] {label} {seconds:.3f}s{suffix}")


@dataclass
class FinalTokenState:
    logged: bool = False


def _log_final(verdict: str, state: FinalTokenState) -> None:
    if state.logged:
        return
    state.logged = True
    _log_info(f"\nFINAL: {verdict}", allow_final=True)


class _TeeStream:
    def __init__(self, primary: TextIO, secondary: TextIO) -> None:
        self._primary = primary
        self._secondary = secondary

    def write(self, text: str) -> int:
        written = 0
        if self._primary:
            written = self._primary.write(text)
        if self._secondary:
            self._secondary.write(text)
        return written

    def flush(self) -> None:
        if self._primary:
            self._primary.flush()
        if self._secondary:
            self._secondary.flush()

    def isatty(self) -> bool:
        if hasattr(self._primary, "isatty"):
            return bool(self._primary.isatty())
        return False


def _init_log_file(log_path: str) -> None:
    global _LOG_FILE_HANDLE
    path = Path(log_path).expanduser()
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    _LOG_FILE_HANDLE = path.open("a", encoding="utf-8", buffering=1)
    sys.stdout = _TeeStream(sys.stdout, _LOG_FILE_HANDLE)
    sys.stderr = _TeeStream(sys.stderr, _LOG_FILE_HANDLE)
    _refresh_logger_stream()
    _log_info(f"[log] Writing log to {path}")


def _init_azure_logging(enabled: bool) -> None:
    if not enabled:
        return
    _init_logger()
    LOGGER.propagate = True
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
    except Exception as exc:
        _log_warn(
            f"[azure] Azure-Logging requested but azure-monitor-opentelemetry is not available: {exc}"
        )
        return
    conn = (
        os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
        or os.environ.get("AZURE_MONITOR_CONNECTION_STRING")
        or ""
    ).strip()
    if not conn:
        _log_warn(
            "[azure] Azure-Logging requested but APPLICATIONINSIGHTS_CONNECTION_STRING is not set."
        )
        return
    try:
        configure_azure_monitor(connection_string=conn)
        _log_info("[azure] Azure Monitor logging enabled.")
    except Exception as exc:
        _log_error(f"[azure] Failed to configure Azure Monitor logging: {exc}")


# -----------------------------
# Config
# -----------------------------

DEFAULT_MAX_TOKENS_NO_THINKING = 768  # reduced to cut spend

FINAL_RE = re.compile(r"^\s*FINAL:\s*(PASS|FAIL)\s*$", re.IGNORECASE | re.MULTILINE)

# Click stability / settling
DEFAULT_ACTION_SLEEP_S = 0.5
DEFAULT_LOADSTATE_TIMEOUT_MS = 1200
DEFAULT_NETWORKIDLE_TIMEOUT_MS = 800

# Red X annotation
DEFAULT_GRID_PX = 80

# Arm/commit behavior
DEFAULT_REWRITE_CONFIDENCE = 0.7

# Site hints map
DEFAULT_SCREENSHOT_ATTEMPTS = 3
DEFAULT_SCREENSHOT_RETRY_SLEEP_S = 0.5
DEFAULT_TIMING_WARN_S = 2.0


# -----------------------------
# Helpers
# -----------------------------


def b64_png(png_bytes: bytes) -> str:
    return base64.b64encode(png_bytes).decode("utf-8")


def clamp(n: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, n))


@dataclass
class Viewport:
    width: int
    height: int


@dataclass
class CoordinateTransform:
    model_w: int
    model_h: int
    actual_w: int
    actual_h: int

    def to_actual(self, x: float, y: float) -> Tuple[float, float]:
        sx = self.actual_w / self.model_w
        sy = self.actual_h / self.model_h
        return x * sx, y * sy

    def to_model(self, ax: float, ay: float) -> Tuple[float, float]:
        sx = self.model_w / self.actual_w
        sy = self.model_h / self.actual_h
        return ax * sx, ay * sy


@dataclass
class RunOutcome:
    verdict: Optional[str]
    actions: List[Dict[str, Any]]
    error: Optional[str] = None


def _check_text_present(
    page: Page, config: SuccessIndicatorConfig, *, timeout_ms: int = 0
) -> bool:
    """True if config.value (or compiled regex) found in page visible text.

    When timeout_ms > 0 and the value is a plain string, uses wait_for_function so
    the check succeeds as soon as the text appears rather than at the instant of the call.
    Regex patterns fall back to a point-in-time inner_text read.
    """
    if timeout_ms > 0 and config.compiled_pattern is None:
        try:
            page.wait_for_function(
                "text => document.body.innerText.includes(text)",
                arg=config.value,
                timeout=timeout_ms,
            )
            return True
        except Exception:
            pass
    try:
        body_text = page.inner_text("body", timeout=5000)
    except Exception:
        return False
    if config.compiled_pattern is not None:
        return bool(config.compiled_pattern.search(body_text))
    return config.value in body_text


def _check_selector_present(
    page: Page, config: SuccessIndicatorConfig, *, timeout_ms: int = 0
) -> bool:
    """True if the CSS selector in config.value matches at least one element.

    When timeout_ms > 0, waits up to that many ms for the element to appear in the
    DOM (handles dynamically rendered content after navigation).
    """
    try:
        if timeout_ms > 0:
            page.wait_for_selector(config.value, state="attached", timeout=timeout_ms)
            return True
        return page.locator(config.value).count() > 0
    except Exception:
        return False


def _check_url_match(
    page: Page, config: SuccessIndicatorConfig, *, timeout_ms: int = 0
) -> bool:
    """True if config.value (or compiled regex) matches the current page URL.

    When timeout_ms > 0, uses wait_for_url so SPA hash-routing changes are caught
    before falling back to a point-in-time URL read.
    """
    if timeout_ms > 0:
        try:
            if config.compiled_pattern is not None:
                page.wait_for_url(config.compiled_pattern, timeout=timeout_ms)
            else:
                page.wait_for_url(
                    re.compile(re.escape(config.value)), timeout=timeout_ms
                )
            return True
        except Exception:
            pass
    url = page.url
    if config.compiled_pattern is not None:
        matched = bool(config.compiled_pattern.search(url))
        if not matched:
            _log_info(
                f"[deterministic] url_match: pattern {config.value!r} did not match URL {url!r}"
            )
        return matched
    matched = config.value in url
    if not matched:
        _log_info(
            f"[deterministic] url_match: {config.value!r} not found in URL {url!r}"
        )
    return matched


def check_deterministic_success(
    page: Page, config: SuccessIndicatorConfig, *, timeout_ms: int = 0
) -> bool:
    """Dispatch to the correct deterministic Playwright check.

    Returns True when the success condition is met.
    Always returns False for VISUAL_LLM (handled by LLM verify guard instead).
    When timeout_ms > 0, each check uses Playwright-native waiting so async page
    changes (SPA routing, dynamic rendering) are caught before the verdict is made.
    """
    if config.type == SuccessIndicatorType.TEXT_PRESENT:
        return _check_text_present(page, config, timeout_ms=timeout_ms)
    if config.type == SuccessIndicatorType.SELECTOR_PRESENT:
        return _check_selector_present(page, config, timeout_ms=timeout_ms)
    if config.type == SuccessIndicatorType.URL_MATCH:
        return _check_url_match(page, config, timeout_ms=timeout_ms)
    return False


def ensure_dir(path: str) -> str:
    abs_path = os.path.abspath(path)
    os.makedirs(abs_path, exist_ok=True)
    return abs_path


def ensure_dir_for_file(path: str) -> str:
    abs_path = os.path.abspath(path)
    out_dir = os.path.dirname(abs_path) or "."
    os.makedirs(out_dir, exist_ok=True)
    return abs_path


def stamp_path(base_path: str, suffix: str) -> str:
    base_path = base_path.strip()
    root, ext = os.path.splitext(base_path)
    if not ext:
        ext = ".png"
    return f"{root}.{suffix}{ext}"


def final_stamp_path(base_path: str, suffix: str) -> str:
    base_path = base_path.strip()
    root, ext = os.path.splitext(base_path)
    if not ext:
        ext = ".png"
    return f"{root}.zz_{suffix}{ext}"


def compute_effective_max_tokens(
    user_max_tokens: int,
    thinking_budget: Optional[int],
    margin: int,
) -> int:
    if thinking_budget is None:
        return (
            user_max_tokens
            if user_max_tokens and user_max_tokens > 0
            else DEFAULT_MAX_TOKENS_NO_THINKING
        )

    minimum = int(thinking_budget) + int(max(64, margin))
    if user_max_tokens and user_max_tokens > 0:
        if user_max_tokens <= thinking_budget:
            return minimum
        return max(user_max_tokens, minimum)

    return minimum


def normalize_reasoning_effort(model_name: str, effort: Optional[str]) -> Optional[str]:
    if effort is None:
        return None
    clean = str(effort).strip().lower()
    if not clean:
        return None
    # Newer GPT-5 variants reject "minimal"; use "low" instead.
    if clean == "minimal" and str(model_name).lower().startswith("gpt-5"):
        return "low"
    return clean


def _safe_json_load(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _safe_json_write(path: str, data: Dict[str, Any]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, path)


def load_site_hints(path: str) -> Dict[str, Any]:
    abs_path = os.path.abspath(path)
    data = _safe_json_load(abs_path)
    if not isinstance(data, dict):
        data = {}
    if not os.path.exists(abs_path):
        ensure_dir_for_file(abs_path)
        _safe_json_write(abs_path, data)
    return data


def save_site_hints(path: str, data: Dict[str, Any]) -> None:
    abs_path = os.path.abspath(path)
    ensure_dir_for_file(abs_path)
    _safe_json_write(abs_path, data)


def normalize_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if ":" in host:
            host = host.split(":", 1)[0]
        return host
    except Exception:
        return ""


def _sanitize_filename(raw: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", raw.strip()).strip("_")
    return s or "model"


def _prompt_to_func_name(prompt: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "_", (prompt or "").strip()).strip("_")
    if not base:
        return "Flow"
    return base[:48].rstrip("_")


def _is_generic_function_name(name: str) -> bool:
    lowered = (name or "").strip().lower()
    return lowered in {"flow", "action", "task", "steps", "step"}


def _normalize_function_name(name: str) -> str:
    if not name:
        return "flow"
    lowered = name.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    if not lowered:
        return "flow"
    parts = [p for p in lowered.split("_") if p]
    if not parts:
        return "flow"
    if len(parts) > 3:
        parts = parts[:3]
    return "_".join(parts)


def _suggest_function_name(
    steps: List[Dict[str, Any]], prompt: str, start_url: str
) -> str:
    meta = _infer_function_metadata(steps, prompt, start_url)
    tags = meta.get("tags") or []
    if "login" in tags and "search" in tags:
        return "login_search"
    if "login" in tags:
        return "login"
    if "search" in tags:
        return "search"
    generic_prompt = _replace_quoted_value(prompt or "", "query")
    candidate = _normalize_function_name(_prompt_to_func_name(generic_prompt))
    if not candidate or _is_generic_function_name(candidate):
        return "action"
    return candidate


def _extract_quoted_value(prompt: str) -> Optional[str]:
    if not prompt:
        return None
    m = re.search(r"'([^']+)'|\"([^\"]+)\"", prompt)
    if not m:
        return None
    return m.group(1) or m.group(2)


def _extract_named_value_from_prompt(prompt: str, name: str) -> Optional[str]:
    """Extract a named value from a prompt like 'username foo' or "username 'foo'"."""
    if not prompt or not name:
        return None
    pattern = re.compile(
        r"\b" + re.escape(name) + r"\s+['\"]?([^\s'\"]+)['\"]?",
        re.IGNORECASE,
    )
    m = pattern.search(prompt)
    return m.group(1) if m else None


def _replace_quoted_value(prompt: str, replacement: str) -> str:
    if not prompt:
        return prompt
    return re.sub(r"'([^']+)'|\"([^\"]+)\"", replacement, prompt, count=1)


def _parse_actions_arg(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    return [p for p in parts if p]


def _function_reliability(success_count: int, fail_count: int) -> float:
    total = max(0, int(success_count)) + max(0, int(fail_count))
    return (int(success_count) + 1) / (total + 2)


def _step_signature(step: Dict[str, Any]) -> str:
    action = str(step.get("action", "")).lower().strip()
    if action in ("click", "double_click", "type"):
        selector = step.get("selector")
        role = step.get("role")
        name = step.get("name")
        target_text = step.get("target_text")
        if selector:
            return f"{action}:selector={selector}"
        if role and name:
            return f"{action}:role={role},name={name}"
        if target_text:
            return f"{action}:text={_clean_dom_text(str(target_text))}"
    if action in ("press", "key"):
        key = step.get("key") or step.get("text")
        return f"{action}:{key}"
    if action == "wait":
        return "wait"
    if action == "goto":
        return "goto"
    if action == "reload":
        return "reload"
    return action or "unknown"


def _summarize_steps(steps: List[Any], limit: int = 8) -> List[str]:
    out: List[str] = []
    for step in steps[: max(0, int(limit))]:
        if not isinstance(step, dict):
            continue
        out.append(_step_signature(step))
    return out


def _strip_known_prefix_steps(
    steps: List[Dict[str, Any]],
    model_data: Dict[str, Any],
    completed_sequence: List[str],
) -> List[Dict[str, Any]]:
    if not steps or not completed_sequence:
        return steps
    funcs = {
        str(f.get("name")): f
        for f in model_data.get("functions", [])
        if isinstance(f, dict)
    }
    prefix_steps: List[Dict[str, Any]] = []
    for name in completed_sequence:
        func = funcs.get(name)
        if not func:
            continue
        func_steps = func.get("steps")
        if isinstance(func_steps, list) and func_steps:
            prefix_steps.extend([s for s in func_steps if isinstance(s, dict)])
    if not prefix_steps:
        return steps
    prefix_sigs = [_step_signature(s) for s in prefix_steps]
    step_sigs = [_step_signature(s) for s in steps]
    if (
        len(step_sigs) >= len(prefix_sigs)
        and step_sigs[: len(prefix_sigs)] == prefix_sigs
    ):
        return steps[len(prefix_sigs) :]
    return steps


def _merge_existing_action_with_fallback_steps(
    model_data: Dict[str, Any], action_name: str, fallback_steps: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    if not fallback_steps:
        return fallback_steps
    functions = model_data.get("functions", [])
    if not isinstance(functions, list):
        return fallback_steps
    existing_steps: List[Dict[str, Any]] = []
    for func in functions:
        if not isinstance(func, dict):
            continue
        if str(func.get("name") or "").strip().lower() != action_name.strip().lower():
            continue
        raw_steps = func.get("steps")
        if isinstance(raw_steps, list):
            existing_steps = [s for s in raw_steps if isinstance(s, dict)]
        break
    if not existing_steps:
        return fallback_steps
    existing_sigs = [_step_signature(s) for s in existing_steps]
    fallback_sigs = [_step_signature(s) for s in fallback_steps]
    if (
        len(fallback_sigs) >= len(existing_sigs)
        and fallback_sigs[: len(existing_sigs)] == existing_sigs
    ):
        return fallback_steps
    max_overlap = min(len(existing_sigs), len(fallback_sigs))
    overlap = 0
    for size in range(max_overlap, 0, -1):
        if existing_sigs[-size:] == fallback_sigs[:size]:
            overlap = size
            break
    if overlap:
        return existing_steps + fallback_steps[overlap:]
    return existing_steps + fallback_steps


MAX_SUBACTIONS_PER_FUNCTION = DEFAULT_MAX_SUBACTIONS_PER_FUNCTION


def _is_capped_interaction(step: Dict[str, Any]) -> bool:
    action = str(step.get("action", "")).lower().strip()
    if not action:
        return False
    # Exclude passive captures from the cap.
    if action in ("screenshot",):
        return False
    return True


def _split_steps_by_action_cap(
    steps: List[Any], cap: int
) -> List[List[Dict[str, Any]]]:
    if cap <= 0:
        return [steps] if steps else []
    chunks: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    action_count = 0
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_is_capped = _is_capped_interaction(step)
        if step_is_capped and action_count >= cap and current:
            chunks.append(current)
            current = []
            action_count = 0
        current.append(step)
        if step_is_capped:
            action_count += 1
    if current:
        chunks.append(current)
    return chunks


_FUNCTION_METADATA_KEYS = {
    "tags",
    "inputs",
    "selectors",
    "site",
    "examples",
    "preconditions",
    "postconditions",
    "scope",
    "composes",
    "avoid_with",
    "deprioritize_when",
    "notes",
}


def _extract_function_metadata(func: Dict[str, Any]) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    for key in _FUNCTION_METADATA_KEYS:
        val = func.get(key)
        if val:
            meta[key] = val
    return meta


def _merge_function_metadata(
    base: Dict[str, Any], override: Dict[str, Any]
) -> Dict[str, Any]:
    merged = dict(base or {})
    for key, val in (override or {}).items():
        if val:
            merged[key] = val
    return merged


def _infer_function_metadata(
    steps: List[Any],
    prompt: str,
    start_url: str,
) -> Dict[str, Any]:
    inputs: List[str] = []
    selectors: List[str] = []
    tags: List[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        text = str(step.get("text", ""))
        if "{username}" in text and "username" not in inputs:
            inputs.append("username")
        if "{password}" in text and "password" not in inputs:
            inputs.append("password")
        if "{query}" in text and "query" not in inputs:
            inputs.append("query")
        selector = step.get("selector")
        role = step.get("role")
        name = step.get("name")
        target_text = step.get("target_text")
        if selector:
            selectors.append(str(selector))
        elif role and name:
            selectors.append(f"role:{role} name:{name}")
        elif target_text:
            selectors.append(f"text:{_clean_dom_text(str(target_text))}")
    if any("username" in s for s in inputs) or any("password" in s for s in inputs):
        tags.append("login")
    if any("query" in s for s in inputs):
        tags.append("search")
    preconditions: List[str] = []
    postconditions: List[str] = []
    composes: List[str] = []
    scope = "atomic"
    has_login = "login" in tags
    has_search = "search" in tags
    if has_login and has_search:
        scope = "composite"
        composes = ["login", "search"]
    if has_login:
        if "logged_in" not in postconditions:
            postconditions.append("logged_in")
    if has_search:
        if not has_login and "logged_in" not in preconditions:
            preconditions.append("logged_in")
        if "search_results" not in postconditions:
            postconditions.append("search_results")
    deprioritize_when: List[str] = []
    if scope == "composite" and composes:
        deprioritize_when = composes[:]

    meta: Dict[str, Any] = {
        "tags": tags,
        "inputs": inputs,
        "selectors": selectors[:6],
        "site": normalize_domain(start_url) if start_url else "",
        "examples": [_replace_quoted_value(prompt, "{query}")] if prompt else [],
    }
    if preconditions:
        meta["preconditions"] = preconditions
    if postconditions:
        meta["postconditions"] = postconditions
    if scope:
        meta["scope"] = scope
    if composes:
        meta["composes"] = composes
    if deprioritize_when:
        meta["deprioritize_when"] = deprioritize_when
    return meta


def _format_function_metadata_for_prompt(func: Dict[str, Any]) -> str:
    parts: List[str] = []
    tags = func.get("tags")
    inputs = func.get("inputs")
    pre = func.get("preconditions")
    post = func.get("postconditions")
    composes = func.get("composes")
    avoid_with = func.get("avoid_with")
    deprioritize_when = func.get("deprioritize_when")
    notes = func.get("notes")
    site = func.get("site")
    selectors = func.get("selectors")
    scope = func.get("scope")
    examples = func.get("examples")
    if tags:
        parts.append(f"tags={tags}")
    if inputs:
        parts.append(f"inputs={inputs}")
    if pre:
        parts.append(f"pre={pre}")
    if post:
        parts.append(f"post={post}")
    if site:
        parts.append(f"site={site}")
    if scope:
        parts.append(f"scope={scope}")
    if composes:
        parts.append(f"composes={composes}")
    if deprioritize_when:
        parts.append(f"deprioritize_when={deprioritize_when}")
    if avoid_with:
        parts.append(f"avoid_with={avoid_with}")
    if notes:
        parts.append(f"notes={notes}")
    if selectors:
        parts.append(f"selectors={selectors}")
    if examples:
        parts.append(f"examples={examples}")
    return " | ".join(parts)


def _has_login_action(functions_list: List[Any]) -> bool:
    for f in functions_list:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name", "")).strip().lower()
        tags = f.get("tags") or []
        if "login" in name:
            return True
        if isinstance(tags, list) and any(str(t).lower() == "login" for t in tags):
            return True
    return False


def _normalize_prompt_for_routes(prompt: str, functions_list: List[Any]) -> str:
    if not prompt:
        return prompt
    if not _has_login_action(functions_list):
        return prompt
    lines = [str(l) for l in prompt.splitlines()]
    normalized: List[str] = []
    for line in lines:
        cleaned = re.sub(r"^\s*[-*]\s*", "", line).strip()
        if not cleaned:
            continue
        cleaned = re.sub(
            r"^\s*(after|once)\s+logging\s+in[,;:]*\s*", "", cleaned, flags=re.I
        )
        cleaned = re.sub(r"^\s*(after|once)\s+login[,;:]*\s*", "", cleaned, flags=re.I)
        if re.search(r"\b(username|password)\b", cleaned, re.I):
            continue
        if re.search(r"\b(log\s*in|login|sign\s*in)\b", cleaned, re.I):
            continue
        if re.search(r"\bpress\b.*\b(tab|enter)\b", cleaned, re.I):
            continue
        normalized.append(cleaned)
    if not normalized:
        return prompt
    return "\n".join(normalized).strip()


def _expand_composite_sequence(
    sequence: List[str],
    functions_list: List[Any],
) -> List[str]:
    if not sequence:
        return sequence
    func_map: Dict[str, Dict[str, Any]] = {}
    for f in functions_list:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name", "")).strip()
        if name:
            func_map[name] = f
    expanded: List[str] = []
    for name in sequence:
        func = func_map.get(name)
        if not func:
            expanded.append(name)
            continue
        composes = func.get("composes")
        scope = str(func.get("scope", "")).strip().lower()
        if isinstance(composes, list) and composes:
            sub = [str(n).strip() for n in composes if str(n).strip()]
            if (
                sub
                and all(n in func_map for n in sub)
                and (scope == "composite" or name not in sub)
            ):
                expanded.extend(sub)
                continue
        expanded.append(name)
    return expanded


def split_steps_with_existing_functions(
    steps: List[Any],
    functions_list: List[Any],
    *,
    min_match: float = 0.75,
) -> Optional[List[Dict[str, Any]]]:
    if not steps or not functions_list:
        return None
    step_sigs = [
        _step_signature(s) if isinstance(s, dict) else "unknown" for s in steps
    ]

    func_sigs: Dict[str, List[str]] = {}
    func_reliability: Dict[str, float] = {}
    for f in functions_list:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name", "")).strip()
        if not name:
            continue
        f_steps = f.get("steps", [])
        if not isinstance(f_steps, list) or not f_steps:
            continue
        sigs = [
            _step_signature(s) if isinstance(s, dict) else "unknown" for s in f_steps
        ]
        if not sigs:
            continue
        func_sigs[name] = sigs
        reliability = _function_reliability(
            int(f.get("success_count", 0) or 0),
            int(f.get("fail_count", 0) or 0),
        )
        if str(f.get("scope", "")).strip().lower() == "composite":
            reliability = max(0.0, reliability - 0.2)
        func_reliability[name] = reliability

    if not func_sigs:
        return None

    segments: List[Dict[str, Any]] = []
    buffer: List[Dict[str, Any]] = []
    i = 0
    while i < len(steps):
        best_name = None
        best_len = 0
        best_match = 0.0
        best_reliability = 0.0
        for name, sigs in func_sigs.items():
            n = len(sigs)
            if n == 0 or i + n > len(step_sigs):
                continue
            window = step_sigs[i : i + n]
            matches = sum(1 for a, b in zip(window, sigs) if a == b)
            ratio = matches / float(n)
            if ratio < min_match:
                continue
            reliability = func_reliability.get(name, 0.5)
            if (
                ratio > best_match
                or (ratio == best_match and reliability > best_reliability)
                or (
                    ratio == best_match
                    and reliability == best_reliability
                    and n > best_len
                )
            ):
                best_name = name
                best_len = n
                best_match = ratio
                best_reliability = reliability
        if best_name:
            if buffer:
                segments.append({"type": "new", "steps": buffer})
                buffer = []
            segments.append(
                {"type": "existing", "name": best_name, "match": best_match}
            )
            i += best_len
            continue
        buffer.append(steps[i])
        i += 1
    if buffer:
        segments.append({"type": "new", "steps": buffer})
    if not any(seg.get("type") == "existing" for seg in segments):
        return None
    return segments


def model_path_for_url(start_url: str, models_dir: str) -> str:
    parsed = urlparse(start_url)
    base = f"{parsed.scheme}_{parsed.netloc}{parsed.path}"
    filename = _sanitize_filename(base) + ".json"
    return os.path.join(models_dir, filename)


def load_page_model(path: str, start_url: str) -> Dict[str, Any]:
    data = _safe_json_load(path)
    if not isinstance(data, dict):
        data = {}
    if not data:
        data = {"start_url": start_url, "functions": [], "prompt_routes": []}
    if "functions" not in data:
        data["functions"] = []
    if "prompt_routes" not in data:
        data["prompt_routes"] = []
    return data


def save_page_model(path: str, data: Dict[str, Any]) -> None:
    abs_path = os.path.abspath(path)
    ensure_dir_for_file(abs_path)
    _safe_json_write(abs_path, data)


def extract_final_verdict(assistant_blocks: List[Any]) -> Optional[str]:
    for b in assistant_blocks:
        if getattr(b, "type", None) == "text":
            m = FINAL_RE.search(b.text or "")
            if m:
                return m.group(1).upper()
    return None


def extract_assistant_text_blocks(assistant_blocks: List[Any]) -> str:
    parts: List[str] = []
    for b in assistant_blocks:
        if getattr(b, "type", None) == "text":
            t = (b.text or "").strip()
            if t:
                parts.append(t)
    return "\n".join(parts)


def extract_final_verdict_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    m = FINAL_RE.search(text)
    if m:
        return m.group(1).upper()
    return None


def extract_openai_response_text(resp: Any) -> str:
    def _coerce_text(val: Any) -> str:
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            inner = val.get("value") or val.get("text") or ""
            return inner if isinstance(inner, str) else ""
        inner = getattr(val, "value", None)
        if isinstance(inner, str):
            return inner
        inner = getattr(val, "text", None)
        return inner if isinstance(inner, str) else ""

    text = getattr(resp, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text
    if isinstance(text, list):
        joined = "\n".join(
            [_coerce_text(t).strip() for t in text if _coerce_text(t).strip()]
        )
        if joined:
            return joined
    parts: List[str] = []
    output = getattr(resp, "output", None) or []
    for item in output:
        itype = getattr(item, "type", None)
        if itype is None and isinstance(item, dict):
            itype = item.get("type")
        if itype == "message":
            content = getattr(item, "content", None)
            if content is None and isinstance(item, dict):
                content = item.get("content")
            if isinstance(content, list):
                for c in content:
                    ctype = getattr(c, "type", None)
                    if ctype is None and isinstance(c, dict):
                        ctype = c.get("type")
                    if ctype in ("output_text", "text"):
                        txt = (
                            getattr(c, "text", None)
                            if not isinstance(c, dict)
                            else c.get("text")
                        )
                        coerced = _coerce_text(txt).strip()
                        if coerced:
                            parts.append(coerced)
        elif itype in ("output_text", "text"):
            txt = (
                getattr(item, "text", None)
                if not isinstance(item, dict)
                else item.get("text")
            )
            coerced = _coerce_text(txt).strip()
            if coerced:
                parts.append(coerced)
    return "\n".join([p.strip() for p in parts if p and p.strip()])


def debug_openai_response_summary(resp: Any) -> str:
    def _preview(val: Any, limit: int = 200) -> str:
        if val is None:
            return ""
        s = str(val).strip()
        if not s:
            return ""
        return s if len(s) <= limit else s[:limit] + "..."

    dump: Dict[str, Any] = {}
    try:
        md = getattr(resp, "model_dump", None)
        if callable(md):
            dump = md()
    except Exception:
        dump = {}

    output_text = getattr(resp, "output_text", None)
    if output_text is None and isinstance(dump, dict):
        output_text = dump.get("output_text")

    output = getattr(resp, "output", None)
    if output is None and isinstance(dump, dict):
        output = dump.get("output")
    output = output or []

    output_types: List[str] = []
    content_types: List[str] = []
    content_previews: List[str] = []

    for item in output if isinstance(output, list) else []:
        itype = getattr(item, "type", None)
        if itype is None and isinstance(item, dict):
            itype = item.get("type")
        if itype:
            output_types.append(str(itype))
        content = getattr(item, "content", None)
        if content is None and isinstance(item, dict):
            content = item.get("content")
        if isinstance(content, list):
            for c in content:
                ctype = getattr(c, "type", None)
                if ctype is None and isinstance(c, dict):
                    ctype = c.get("type")
                if ctype:
                    content_types.append(str(ctype))
                txt = None
                if isinstance(c, dict):
                    txt = c.get("text") or c.get("value")
                else:
                    txt = getattr(c, "text", None) or getattr(c, "value", None)
                pv = _preview(txt)
                if pv:
                    content_previews.append(pv)

    parts = [
        f"[debug] output_text_type={type(output_text).__name__}",
        f"[debug] output_types={output_types[:8]}",
        f"[debug] content_types={content_types[:12]}",
    ]
    ot_preview = _preview(output_text)
    if ot_preview:
        parts.append(f"[debug] output_text_preview={ot_preview}")
    if content_previews:
        parts.append(f"[debug] content_preview={content_previews[0]}")
    return "\n".join(parts)


def extract_openai_output_types(resp: Any) -> List[str]:
    dump: Dict[str, Any] = {}
    try:
        md = getattr(resp, "model_dump", None)
        if callable(md):
            dump = md()
    except Exception:
        dump = {}

    output = getattr(resp, "output", None)
    if output is None and isinstance(dump, dict):
        output = dump.get("output")
    if not isinstance(output, list):
        return []

    types: List[str] = []
    for item in output:
        itype = getattr(item, "type", None)
        if itype is None and isinstance(item, dict):
            itype = item.get("type")
        if itype:
            types.append(str(itype))
    return types


def _coerce_tool_input(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def extract_openai_tool_calls(resp: Any) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    output = getattr(resp, "output", None) or []
    for item in output:
        itype = getattr(item, "type", None)
        if itype is None and isinstance(item, dict):
            itype = item.get("type")
        if itype in ("tool_call", "computer_call"):
            tool_name = getattr(item, "name", None)
            if tool_name is None and isinstance(item, dict):
                tool_name = item.get("name") or item.get("tool_name")
            if not tool_name and itype == "computer_call":
                tool_name = "computer"
            raw_input = getattr(item, "arguments", None)
            if raw_input is None:
                raw_input = getattr(item, "input", None)
            if raw_input is None:
                raw_input = getattr(item, "action", None)
            if isinstance(item, dict) and raw_input is None:
                raw_input = (
                    item.get("arguments") or item.get("input") or item.get("action")
                )
            tool_input = _coerce_tool_input(raw_input)
            tool_id = getattr(item, "id", None)
            if tool_id is None and isinstance(item, dict):
                tool_id = item.get("id")
            calls.append(
                {"id": tool_id, "name": tool_name or "computer", "input": tool_input}
            )
            continue
        if itype == "message":
            tool_calls = getattr(item, "tool_calls", None)
            if tool_calls is None and isinstance(item, dict):
                tool_calls = item.get("tool_calls")
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    tool_name = getattr(tc, "name", None)
                    if tool_name is None and isinstance(tc, dict):
                        tool_name = tc.get("name")
                    raw_input = getattr(tc, "arguments", None)
                    if raw_input is None and isinstance(tc, dict):
                        raw_input = tc.get("arguments")
                    tool_input = _coerce_tool_input(raw_input)
                    tool_id = getattr(tc, "id", None)
                    if tool_id is None and isinstance(tc, dict):
                        tool_id = tc.get("id")
                    calls.append(
                        {
                            "id": tool_id,
                            "name": tool_name or "computer",
                            "input": tool_input,
                        }
                    )
    return calls


def _map_openai_action(action: str) -> str:
    mapping = {
        "click": "left_click",
        "left_click": "left_click",
        "double_click": "double_click",
        "right_click": "right_click",
        "move": "mouse_move",
        "mouse_move": "mouse_move",
        "scroll": "scroll",
        "drag": "drag",
        "type": "type",
        "keypress": "key",
        "key": "key",
        "wait": "wait",
        "screenshot": "screenshot",
        "reload": "reload",
        "refresh": "reload",
        "select_option": "select_option",
    }
    return mapping.get(action, action)


def normalize_action_name(action_raw: str) -> str:
    a = (action_raw or "").strip()
    if not a:
        return ""
    compact = re.sub(r"[^a-z0-9]+", "", a.lower())
    mapping = {
        "click": "left_click",
        "leftclick": "left_click",
        "left_click": "left_click",
        "rightclick": "right_click",
        "right_click": "right_click",
        "contextclick": "right_click",
        "contextmenu": "right_click",
        "doubleclick": "double_click",
        "double_click": "double_click",
        "dblclick": "double_click",
        "press": "key",
        "keypress": "key",
        "keydown": "key",
        "key": "key",
        "type": "type",
        "input": "type",
        "scroll": "scroll",
        "wait": "wait",
        "pause": "wait",
        "hover": "mouse_move",
        "mousemove": "mouse_move",
        "mouse_move": "mouse_move",
        "drag": "left_click_drag",
        "leftclickdrag": "left_click_drag",
        "left_click_drag": "left_click_drag",
        "screenshot": "screenshot",
        "reload": "reload",
        "refresh": "reload",
        "reloadpage": "reload",
        "refreshpage": "reload",
        "selectoption": "select_option",
        "chooseoption": "select_option",
    }
    return mapping.get(compact, a.lower())


def normalize_openai_action_input(tool_input: Any) -> Tuple[str, Dict[str, Any]]:
    if not isinstance(tool_input, dict):
        return "", {}
    if "action" in tool_input:
        action_val = tool_input.get("action")
        if isinstance(action_val, dict):
            action_name = str(
                action_val.get("type") or action_val.get("action") or ""
            ).lower()
            args = dict(tool_input)
            args.pop("action", None)
            for k, v in action_val.items():
                if k != "type":
                    args.setdefault(k, v)
            return normalize_action_name(_map_openai_action(action_name)), args
        action_name = str(action_val).lower()
        args = dict(tool_input)
        args.pop("action", None)
        return normalize_action_name(_map_openai_action(action_name)), args
    if "type" in tool_input:
        action_name = str(tool_input.get("type") or "").lower()
        args = dict(tool_input)
        args.pop("type", None)
        return normalize_action_name(_map_openai_action(action_name)), args
    return "", dict(tool_input)


def _has_nonempty_arg(args: Dict[str, Any], key: str) -> bool:
    if key not in args:
        return False
    val = args.get(key)
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, (list, tuple, dict)):
        return bool(val)
    return True


def _normalize_action_args_for_schema(
    action: str, args: Any
) -> Tuple[Dict[str, Any], List[str]]:
    if not isinstance(args, dict):
        return {}, []
    notes: List[str] = []
    normalized = dict(args)
    if action == "key":
        if not any(
            _has_nonempty_arg(normalized, k)
            for k in ("key", "keys", "combo", "key_combo", "text")
        ):
            for alias in (
                "press",
                "keypress",
                "key_press",
                "keystroke",
                "key_stroke",
                "keyStroke",
            ):
                if _has_nonempty_arg(normalized, alias):
                    normalized["key"] = normalized.get(alias)
                    notes.append(f"{alias} -> key")
                    break
    if action == "type":
        if not _has_nonempty_arg(normalized, "text"):
            for alias in ("value", "input", "text_value", "typed", "string"):
                if _has_nonempty_arg(normalized, alias):
                    normalized["text"] = normalized.get(alias)
                    notes.append(f"{alias} -> text")
                    break
    if action in ("left_click", "double_click", "right_click", "mouse_move"):
        if not (
            _has_nonempty_arg(normalized, "x") and _has_nonempty_arg(normalized, "y")
        ):
            for alias in ("point", "xy", "pos", "position"):
                val = normalized.get(alias)
                if (
                    isinstance(val, (list, tuple))
                    and len(val) >= 2
                    and None not in val[:2]
                ):
                    normalized["x"], normalized["y"] = val[0], val[1]
                    notes.append(f"{alias} -> x,y")
                    break
        if action in ("left_click", "double_click", "right_click"):
            if not _has_nonempty_arg(normalized, "selector"):
                for alias in ("css", "css_selector", "cssSelector"):
                    if _has_nonempty_arg(normalized, alias):
                        normalized["selector"] = normalized.get(alias)
                        notes.append(f"{alias} -> selector")
                        break
            if not _has_nonempty_arg(normalized, "target_text"):
                for alias in (
                    "text",
                    "text_value",
                    "visible_text",
                    "target",
                    "label_text",
                ):
                    if _has_nonempty_arg(normalized, alias):
                        normalized["target_text"] = normalized.get(alias)
                        notes.append(f"{alias} -> target_text")
                        break
    if action == "left_click_drag":
        if not _has_nonempty_arg(normalized, "start_coordinate"):
            for alias in ("start", "from", "start_point", "start_pos"):
                val = normalized.get(alias)
                if (
                    isinstance(val, (list, tuple))
                    and len(val) >= 2
                    and None not in val[:2]
                ):
                    normalized["start_coordinate"] = val
                    notes.append(f"{alias} -> start_coordinate")
                    break
        if not _has_nonempty_arg(normalized, "end_coordinate"):
            for alias in ("end", "to", "end_point", "end_pos"):
                val = normalized.get(alias)
                if (
                    isinstance(val, (list, tuple))
                    and len(val) >= 2
                    and None not in val[:2]
                ):
                    normalized["end_coordinate"] = val
                    notes.append(f"{alias} -> end_coordinate")
                    break
    return normalized, notes


def _schema_error_for_action(action: str, args: Dict[str, Any]) -> Optional[str]:
    if action == "key":
        if not any(
            _has_nonempty_arg(args, k)
            for k in ("key", "keys", "combo", "key_combo", "text")
        ):
            return "Key action requires args.key (preferred) or args.keys/args.combo/args.key_combo/args.text."
    if action == "type":
        if not _has_nonempty_arg(args, "text"):
            return "Type action requires args.text."
    if action in ("left_click", "double_click", "right_click"):
        has_xy = _has_nonempty_arg(args, "x") and _has_nonempty_arg(args, "y")
        coord = args.get("coordinate") or args.get("coordinates")
        has_coord = (
            isinstance(coord, (list, tuple))
            and len(coord) >= 2
            and None not in coord[:2]
        )
        has_dom_hint = any(
            _has_nonempty_arg(args, k)
            for k in ("selector", "role", "name", "label", "target_text")
        )
        if not (has_xy or has_coord or has_dom_hint):
            return "Click action requires x,y (preferred) or args.coordinate(s) or a DOM hint (selector/role/name/label/target_text)."
    if action == "mouse_move":
        has_xy = _has_nonempty_arg(args, "x") and _has_nonempty_arg(args, "y")
        coord = args.get("coordinate") or args.get("coordinates")
        has_coord = (
            isinstance(coord, (list, tuple))
            and len(coord) >= 2
            and None not in coord[:2]
        )
        if not (has_xy or has_coord):
            return "Mouse move requires x,y or args.coordinate(s)."
    if action == "left_click_drag":
        start = args.get("start_coordinate") or args.get("start")
        end = args.get("end_coordinate") or args.get("end")
        ok_start = (
            isinstance(start, (list, tuple))
            and len(start) >= 2
            and None not in start[:2]
        )
        ok_end = (
            isinstance(end, (list, tuple)) and len(end) >= 2 and None not in end[:2]
        )
        if not (ok_start and ok_end):
            return "Drag requires start/end coordinates (start_coordinate/end_coordinate or start/end)."
    if action == "select_option":
        if not _has_nonempty_arg(args, "selector"):
            return "select_option requires args.selector (CSS selector for the <select> element)."
        if not any(
            _has_nonempty_arg(args, k) for k in ("label", "value", "text", "option")
        ):
            return (
                "select_option requires args.label (visible option text) or args.value."
            )
    return None


def build_openai_tool_output_inputs(
    tool_call_id: Optional[str],
    *,
    text: Optional[str] = None,
    image_b64: Optional[str] = None,
) -> List[Dict[str, Any]]:
    inputs: List[Dict[str, Any]] = []
    if tool_call_id:
        inputs.append(
            {"type": "tool_output", "tool_call_id": tool_call_id, "output": text or ""}
        )
    if image_b64:
        content = [
            {"type": "input_image", "image_url": f"data:image/png;base64,{image_b64}"}
        ]
        if text:
            content.append({"type": "input_text", "text": text})
        inputs.append({"role": "user", "content": content})
    elif text and not tool_call_id:
        inputs.append(
            {"role": "user", "content": [{"type": "input_text", "text": text}]}
        )
    return inputs


def _redact_secret_text(text: str, secret: Optional[str]) -> str:
    if not secret:
        return text
    return text.replace(secret, "[REDACTED]")


def print_assistant_text(
    assistant_blocks: List[Any],
    secret: Optional[str] = None,
    prefix: str = "",
) -> None:
    txt = extract_assistant_text_blocks(assistant_blocks)
    txt = _redact_secret_text(txt, secret)
    if txt:
        if prefix:
            lines = txt.splitlines()
            txt = "\n".join(f"{prefix} {line}" for line in lines)
        _log_info(txt)


def _get_usage_value(usage: Any, key: str) -> Optional[int]:
    if usage is None:
        return None
    if isinstance(usage, dict):
        v = usage.get(key)
        return int(v) if isinstance(v, (int, float)) else None
    v = getattr(usage, key, None)
    return int(v) if isinstance(v, (int, float)) else None


def print_usage_tokens(resp: Any) -> None:
    usage = getattr(resp, "usage", None)
    if usage is None:
        return
    input_tokens = _get_usage_value(usage, "input_tokens")
    output_tokens = _get_usage_value(usage, "output_tokens")
    cache_create = _get_usage_value(usage, "cache_creation_input_tokens")
    cache_read = _get_usage_value(usage, "cache_read_input_tokens")
    total = None
    if input_tokens is not None and output_tokens is not None:
        total = input_tokens + output_tokens
    parts = []
    if input_tokens is not None:
        parts.append(f"input={input_tokens}")
    if output_tokens is not None:
        parts.append(f"output={output_tokens}")
    if total is not None:
        parts.append(f"total={total}")
    if cache_create is not None:
        parts.append(f"cache_create={cache_create}")
    if cache_read is not None:
        parts.append(f"cache_read={cache_read}")
    if parts:
        _log_info(f"[tokens] {' '.join(parts)}")


def normalize_playwright_key_combo(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return s

    s = s.replace("-", "+").replace(" ", "")
    sl = s.lower()

    blocked_exact = {"alt+tab", "meta+tab", "control+alt+delete", "ctrl+alt+delete"}
    if sl in blocked_exact:
        raise ValueError(f"Blocked OS-level key combo: {raw}")

    tokens = [t for t in s.split("+") if t]
    single_key_aliases = {
        "home": "Home",
        "end": "End",
        "pageup": "PageUp",
        "pagedown": "PageDown",
        "insert": "Insert",
        "capslock": "CapsLock",
        "numlock": "NumLock",
        "scrolllock": "ScrollLock",
        "printscreen": "PrintScreen",
        "prtsc": "PrintScreen",
        "pause": "Pause",
        "contextmenu": "ContextMenu",
        "menu": "ContextMenu",
    }

    mapped: List[str] = []
    for t in tokens:
        tl = t.lower()
        if tl in ("ctrl", "control"):
            mapped.append("Control")
            continue
        if tl in ("alt", "option"):
            mapped.append("Alt")
            continue
        if tl == "shift":
            mapped.append("Shift")
            continue
        if tl in ("super", "win", "windows", "cmd", "meta"):
            mapped.append("Meta")
            continue
        if tl in ("enter", "return"):
            mapped.append("Enter")
            continue
        if tl in ("esc", "escape"):
            mapped.append("Escape")
            continue
        if tl == "tab":
            mapped.append("Tab")
            continue
        if tl == "backspace":
            mapped.append("Backspace")
            continue
        if tl in ("delete", "del"):
            mapped.append("Delete")
            continue
        if tl in ("space", "spacebar"):
            mapped.append("Space")
            continue
        if tl in ("arrowup", "up"):
            mapped.append("ArrowUp")
            continue
        if tl in ("arrowdown", "down"):
            mapped.append("ArrowDown")
            continue
        if tl in ("arrowleft", "left"):
            mapped.append("ArrowLeft")
            continue
        if tl in ("arrowright", "right"):
            mapped.append("ArrowRight")
            continue
        if tl in single_key_aliases:
            mapped.append(single_key_aliases[tl])
            continue

        if re.fullmatch(r"f\d{1,2}", tl):
            mapped.append(tl.upper())
            continue
        if len(t) == 1:
            mapped.append(t.upper())
            continue

        if t.isupper():
            mapped.append(t[0].upper() + t[1:].lower())
            continue
        mapped.append(t[0].upper() + t[1:])

    combo = "+".join(mapped)
    if combo == "Meta":
        raise ValueError("Blocked OS-level key: Meta/Super/Win")
    return combo


def build_verify_reminder_text(success_criteria: str) -> str:
    return f"VERIFY: If criteria met in screenshot, output FINAL: PASS. Criteria: {success_criteria}"


def _is_criteria_visible(success_criteria: str, verify_reason: str) -> bool:
    crit = (success_criteria or "").lower()
    reason = (verify_reason or "").lower()
    # Require at least one distinctive token from the criteria to appear in the reason.
    tokens = [t for t in re.split(r"[^a-z0-9]+", crit) if len(t) >= 4]
    if not tokens:
        return False
    return any(t in reason for t in tokens)


def settle_before_precise_action(page: Page, sleep_s: float) -> None:
    try:
        page.wait_for_load_state(
            "domcontentloaded", timeout=DEFAULT_LOADSTATE_TIMEOUT_MS
        )
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=DEFAULT_NETWORKIDLE_TIMEOUT_MS)
    except Exception:
        pass
    time.sleep(max(0.0, float(sleep_s)))


def _draw_red_x_on_png_bytes(
    png_bytes: bytes,
    points: List[Tuple[float, float]],
    *,
    x_size_px: int,
    thickness_px: int,
) -> bytes:
    if not PIL_OK:
        return png_bytes

    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(img)

    for x, y in points:
        cx = float(x)
        cy = float(y)
        s = int(x_size_px)
        t = int(thickness_px)
        draw.line((cx - s, cy - s, cx + s, cy + s), fill=(255, 0, 0, 255), width=t)
        draw.line((cx - s, cy + s, cx + s, cy - s), fill=(255, 0, 0, 255), width=t)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _resize_png_bytes(png_bytes: bytes, target_w: int, target_h: int) -> bytes:
    if not PIL_OK:
        raise RuntimeError(
            "Pillow (PIL) is required for screenshot downscaling but is not available."
        )
    if Image is None:
        raise RuntimeError(
            "Pillow (PIL) is required for screenshot downscaling but is not available."
        )
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    resampling = getattr(Image, "Resampling", None)
    if resampling is not None:
        resample_filter = resampling.BICUBIC
    else:
        resample_filter = getattr(Image, "BICUBIC", Image.BILINEAR)
    img2 = img.resize((int(target_w), int(target_h)), resample=resample_filter)
    out = io.BytesIO()
    img2.save(out, format="PNG")
    return out.getvalue()


def _overlay_grid_on_png_bytes(png_bytes: bytes, grid_px: int) -> bytes:
    if not PIL_OK or grid_px <= 0:
        return png_bytes
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    step = int(max(20, grid_px))
    for x in range(0, w, step):
        draw.line((x, 0, x, h), fill=(255, 255, 255, 90), width=1)
        draw.text((x + 2, 2), str(x), fill=(255, 255, 255, 180))
    for y in range(0, h, step):
        draw.line((0, y, w, y), fill=(255, 255, 255, 90), width=1)
        draw.text((2, y + 2), str(y), fill=(255, 255, 255, 180))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _capture_screenshot_png_with_retry(
    page: Page,
    *,
    attempts: int = DEFAULT_SCREENSHOT_ATTEMPTS,
    retry_sleep_s: float = DEFAULT_SCREENSHOT_RETRY_SLEEP_S,
) -> bytes:
    attempts = max(1, int(attempts))
    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return page.screenshot(type="png", full_page=False, scale="css")
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                _log_warn(
                    f"[screenshot] capture failed (attempt {attempt}/{attempts}): {exc}. "
                    f"Retrying in {retry_sleep_s:.2f}s."
                )
                time.sleep(max(0.0, float(retry_sleep_s)))
                continue
            break
    if last_error is None:
        raise RuntimeError("screenshot_failed_without_exception")
    raise last_error


def _github_run_prefix() -> str:
    if os.getenv("GITHUB_ACTIONS", "").lower() != "true":
        return ""
    run_number = os.getenv("GITHUB_RUN_NUMBER") or os.getenv("GITHUB_RUN_ID") or ""
    if not run_number:
        return ""
    return f"{run_number}_"


def _prefix_path_for_github_run(path: str) -> str:
    prefix = _github_run_prefix()
    if not prefix:
        return path
    dirname = os.path.dirname(path)
    basename = os.path.basename(path)
    if basename.startswith(prefix):
        return path
    return os.path.join(dirname, f"{prefix}{basename}")


def save_agent_view(
    page: Page,
    out_dir: str,
    step: int,
    label: str,
    *,
    mark_points: Optional[List[Tuple[float, float]]] = None,  # ACTUAL CSS px points
    x_size_px: int = DEFAULT_X_SIZE_PX,
    thickness_px: int = DEFAULT_X_THICKNESS_PX,
) -> str:
    ensure_dir(out_dir)
    filename = os.path.join(out_dir, f"step_{step:03d}.{label}.png")
    filename = _prefix_path_for_github_run(filename)
    filename = ensure_dir_for_file(filename)

    try:
        png = _capture_screenshot_png_with_retry(page)
        if not mark_points:
            with open(filename, "wb") as f:
                f.write(png)
            _log_info(f"[agent_view] saved: {filename}")
            return filename

        png = _overlay_grid_on_png_bytes(png, DEFAULT_GRID_PX)
        png2 = _draw_red_x_on_png_bytes(
            png, mark_points, x_size_px=x_size_px, thickness_px=thickness_px
        )
        with open(filename, "wb") as f:
            f.write(png2)
        _log_info(f"[agent_view] saved: {filename}")
        return filename
    except Exception as exc:
        _log_warn(
            f"[agent_view] Failed to save screenshot step={step} label={label}: {exc}"
        )
        return ""


def maybe_save_agent_view(
    enabled: bool,
    page: Page,
    out_dir: str,
    step: int,
    label: str,
    *,
    mark_points: Optional[List[Tuple[float, float]]] = None,  # ACTUAL CSS px points
    x_size_px: int = DEFAULT_X_SIZE_PX,
    thickness_px: int = DEFAULT_X_THICKNESS_PX,
) -> str:
    if not enabled:
        return ""
    return save_agent_view(
        page,
        out_dir,
        step,
        label,
        mark_points=mark_points,
        x_size_px=x_size_px,
        thickness_px=thickness_px,
    )


def capture_model_screenshot_png(
    page: Page,
    *,
    actual_w: int,
    actual_h: int,
    model_w: int,
    model_h: int,
) -> bytes:
    png = _capture_screenshot_png_with_retry(page)
    if int(model_w) == int(actual_w) and int(model_h) == int(actual_h):
        return png
    return _resize_png_bytes(png, model_w, model_h)


# -----------------------------
# Cost pruning (FIXED)
# -----------------------------


def _message_has_tool_result_image(m: Dict[str, Any]) -> bool:
    if m.get("role") != "user":
        return False
    content = m.get("content")
    if not isinstance(content, list):
        return False
    for c in content:
        if not isinstance(c, dict):
            continue
        if c.get("type") != "tool_result":
            continue
        inner = c.get("content", [])
        if not isinstance(inner, list):
            continue
        for cc in inner:
            if isinstance(cc, dict) and cc.get("type") == "image":
                return True
    return False


def _message_has_tool_result(m: Dict[str, Any]) -> bool:
    if m.get("role") != "user":
        return False
    content = m.get("content")
    if not isinstance(content, list):
        return False
    for c in content:
        if isinstance(c, dict) and c.get("type") == "tool_result":
            return True
    return False


def _strip_images_inside_tool_results(m: Dict[str, Any]) -> Dict[str, Any]:
    """
    IMPORTANT: Keep tool_result blocks + tool_use_id, but replace image payloads with a small text stub.
    This preserves the required tool_use -> tool_result adjacency/protocol.
    """
    if m.get("role") != "user":
        return m
    content = m.get("content")
    if not isinstance(content, list):
        return m

    new_content: List[Any] = []
    for c in content:
        if not isinstance(c, dict) or c.get("type") != "tool_result":
            new_content.append(c)
            continue

        inner = c.get("content", [])
        if not isinstance(inner, list):
            inner = []

        new_inner: List[Any] = []
        removed_any = False
        for cc in inner:
            if isinstance(cc, dict) and cc.get("type") == "image":
                removed_any = True
                continue
            new_inner.append(cc)

        if removed_any:
            new_inner.append(
                {
                    "type": "text",
                    "text": "(Earlier screenshot omitted to reduce tokens.)",
                }
            )

        c2 = dict(c)
        c2["content"] = new_inner
        new_content.append(c2)

    m2 = dict(m)
    m2["content"] = new_content
    return m2


def prune_messages_for_cost(
    messages: List[Dict[str, Any]],
    *,
    keep_last_turns: int,
    keep_last_images: int,
) -> List[Dict[str, Any]]:
    """
    Safe pruning that preserves tool_use -> tool_result pairing.

    Strategy:
    - Always keep messages[0] (the initial instruction).
    - Keep the last `keep_last_turns` messages from the end (working backwards),
      so adjacency is preserved.
    - Images: keep only the most recent screenshot tool_result image and strip older ones
      (text stub retained).
    """
    if not messages:
        return messages

    if len(messages) == 1:
        return [messages[0]]

    keep_last_turns = max(0, int(keep_last_turns))
    keep_indices = {0}

    # Start with the last N messages.
    for idx in range(len(messages) - 1, 0, -1):
        if len(keep_indices) - 1 >= keep_last_turns:
            break
        keep_indices.add(idx)

    # Ensure tool_result messages have their preceding tool_use message.
    # If we keep a tool_result, always keep the immediately previous message.
    # This avoids "unexpected tool_use_id" errors after pruning.
    for idx in sorted(keep_indices):
        if idx <= 0:
            continue
        if _message_has_tool_result(messages[idx]) and (idx - 1) not in keep_indices:
            keep_indices.add(idx - 1)

    pruned = [messages[i] for i in sorted(keep_indices)]

    # Identify user messages in pruned list that contain tool_result images
    image_msgs_idx = [
        i for i, m in enumerate(pruned) if _message_has_tool_result_image(m)
    ]

    # Trim image history: keep the most recent N image tool_result payloads.
    effective_keep_images = max(0, int(keep_last_images))

    if effective_keep_images >= 0 and len(image_msgs_idx) > effective_keep_images:
        to_strip = set(image_msgs_idx[:-effective_keep_images])
        new_pruned: List[Dict[str, Any]] = []
        for i, m in enumerate(pruned):
            if i in to_strip:
                new_pruned.append(_strip_images_inside_tool_results(m))
            else:
                new_pruned.append(m)
        pruned = new_pruned

    return pruned


# -----------------------------
# Tab/Popup Following (Option 1)
# -----------------------------


def pick_active_page(context: BrowserContext, current: Page) -> Page:
    pages = [p for p in context.pages if not p.is_closed()]
    if not pages:
        return current
    return pages[-1]


def maybe_switch_to_new_tab(
    context: BrowserContext, current: Page, verbose: bool = False
) -> Page:
    new_page = pick_active_page(context, current)
    if new_page is not current:
        try:
            new_page.bring_to_front()
        except Exception:
            pass
        if verbose:
            try:
                _log_info(f"[tab] Switched active page -> {new_page.url}")
            except Exception:
                _log_info("[tab] Switched active page")
    return new_page


# -----------------------------
# Tool execution in Playwright
# -----------------------------

CLICKLIKE_ACTIONS = {"left_click", "double_click", "right_click", "left_click_drag"}
ARM_COMMIT_ELIGIBLE = {"left_click", "double_click", "right_click"}


def extract_action_points_for_marking(
    action: str,
    action_input: Dict[str, Any],
    xform: CoordinateTransform,
) -> List[Tuple[float, float]]:
    a = action.lower().strip()

    if a in ("left_click", "double_click", "right_click", "mouse_move"):
        if "x" in action_input and "y" in action_input:
            x, y = action_input.get("x"), action_input.get("y")
        else:
            x, y = action_input.get(
                "coordinate", action_input.get("coordinates", [None, None])
            )
        if x is None or y is None:
            return []
        ax, ay = xform.to_actual(float(x), float(y))
        return [(ax, ay)]

    if a == "left_click_drag":
        start = (
            action_input.get("start_coordinate")
            or action_input.get("start")
            or [None, None]
        )
        end = (
            action_input.get("end_coordinate")
            or action_input.get("end")
            or [None, None]
        )
        sx, sy = start
        ex, ey = end
        if None in (sx, sy, ex, ey):
            return []
        asx, asy = xform.to_actual(float(sx), float(sy))
        aex, aey = xform.to_actual(float(ex), float(ey))
        return [(asx, asy), (aex, aey)]

    return []


def _looks_like_css_selector(s: str) -> bool:
    """Return True if s looks like a CSS selector rather than plain text."""
    import re

    s = s.strip()
    if not s:
        return False
    # CSS selectors start with #id, .class, [attr, :pseudo, *, or a lowercase tag name
    if s[0] in ("#", ".", "[", ":", "*"):
        return True
    # Tag names: short lowercase word optionally followed by CSS combinator characters
    return bool(re.match(r"^[a-z][a-z0-9]*(\s*[\[:#\.>\+~\s]|$)", s))


def _dom_locator_from_action_input(
    page: Page,
    action_input: Dict[str, Any],
    *,
    allow_text_key: bool,
):
    selector = action_input.get("selector")
    if selector:
        selector_str = str(selector)
        if _looks_like_css_selector(selector_str):
            return page.locator(selector_str)
        # Selector looks like plain text — treat as get_by_text fallback
        exact = bool(action_input.get("exact", False))
        return page.get_by_text(selector_str, exact=exact)

    role = action_input.get("role")
    name = (
        action_input.get("name")
        or action_input.get("label")
        or action_input.get("target_text")
    )
    if role:
        role_name = cast(Any, str(role))
        if name:
            return page.get_by_role(role_name, name=str(name))
        return page.get_by_role(role_name)

    text_value = (
        action_input.get("target_text")
        or action_input.get("label")
        or action_input.get("name")
    )
    if allow_text_key and not text_value:
        text_value = action_input.get("text")
    if text_value:
        exact = bool(action_input.get("exact", False))
        return page.get_by_text(str(text_value), exact=exact)

    return None


def _extract_dom_hint(action_input: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    selector = action_input.get("selector")
    if selector:
        selector_str = str(selector)
        if _looks_like_css_selector(selector_str):
            return {"type": "selector", "value": selector_str}
        # Plain-text label stored as selector — downgrade to text hint so it
        # replays via get_by_text rather than a broken CSS locator.
        return {"type": "text", "value": selector_str}
    role = action_input.get("role")
    name = (
        action_input.get("name")
        or action_input.get("label")
        or action_input.get("target_text")
    )
    if role and name:
        return {"type": "role_name", "role": str(role), "name": str(name)}
    text_value = (
        action_input.get("target_text")
        or action_input.get("label")
        or action_input.get("name")
    )
    if text_value:
        return {"type": "text", "value": str(text_value)}
    return None


def _has_explicit_dom_target(action_input: Dict[str, Any]) -> bool:
    return any(_has_nonempty_arg(action_input, k) for k in ("selector", "role"))


def _try_dom_click(
    page: Page,
    action: str,
    action_input: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    locator = _dom_locator_from_action_input(page, action_input, allow_text_key=True)
    if locator is None:
        return None
    try:
        if locator.count() == 0:
            return None
        loc = locator.first
        try:
            tag = loc.evaluate("el => el.tagName.toLowerCase()", timeout=2000)
            if tag == "select" and action in ("left_click", "click"):
                selector = action_input.get("selector", "")
                return {
                    "ok": False,
                    "action": action,
                    "dom": True,
                    "terminal": True,
                    "error": (
                        f"Target is a native <select> element — clicking it opens a "
                        f"browser dropdown that cannot be scrolled. "
                        f"Use select_option instead: "
                        f'{{"action":"select_option","args":{{"selector":"{selector}","label":"<desired option text>"}}}}'
                    ),
                }
        except Exception:
            pass
        loc.scroll_into_view_if_needed(timeout=10000)
        if action == "double_click":
            loc.dblclick(timeout=10000)
        elif action == "right_click":
            loc.click(timeout=10000, button="right")
        else:
            loc.click(timeout=10000)
        return {
            "ok": True,
            "action": action,
            "dom": True,
            "dom_hint": _extract_dom_hint(action_input),
        }
    except Exception as e:
        return {"ok": False, "action": action, "dom": True, "error": str(e)}


def _read_locator_value(loc: Locator) -> Optional[str]:
    try:
        return loc.input_value(timeout=10000)
    except Exception:
        try:
            return loc.evaluate(
                "el => (el && (el.isContentEditable ? (el.innerText ?? '') : ((el.value ?? el.textContent) ?? '')))"
            )
        except Exception:
            return None


def _type_and_verify_locator(
    loc: Locator, text: str, retries: int = 1
) -> Tuple[bool, Optional[str], str]:
    text = str(text)
    try:
        loc.scroll_into_view_if_needed(timeout=10000)
    except Exception:
        pass

    attempts = max(0, int(retries)) + 1
    last_observed: Optional[str] = None
    last_method = "fill"
    for _ in range(attempts):
        try:
            loc.fill(text, timeout=10000)
        except Exception:
            pass
        last_observed = _read_locator_value(loc)
        if last_observed == text:
            time.sleep(0.2)
            stable = _read_locator_value(loc)
            if stable == text:
                return True, last_observed, "fill"
            last_observed = stable
        last_method = "type"
        try:
            loc.click(timeout=10000)
            loc.press("Control+A")
            loc.press("Backspace")
            loc.type(text, delay=20, timeout=10000)
        except Exception:
            pass
        last_observed = _read_locator_value(loc)
        if last_observed == text:
            time.sleep(0.2)
            stable = _read_locator_value(loc)
            if stable == text:
                return True, last_observed, "type"
            last_observed = stable
    return False, last_observed, last_method


def _read_active_element_value(page: Page) -> str:
    try:
        return page.evaluate(
            "() => { const el=document.activeElement; if (!el) return ''; "
            "if (el.isContentEditable) return el.innerText ?? ''; "
            "if ('value' in el) return el.value ?? ''; "
            "return el.textContent ?? ''; }"
        )
    except Exception:
        return ""


def _active_element_is_editable(page: Page) -> bool:
    try:
        return bool(
            page.evaluate(
                "() => { const el=document.activeElement; if (!el) return false; "
                "const tag=(el.tagName||'').toLowerCase(); "
                "if (el.isContentEditable) return true; "
                "if (tag === 'input' || tag === 'textarea') return !el.disabled && !el.readOnly; "
                "return false; }"
            )
        )
    except Exception:
        return False


def _type_and_verify_active_element(
    page: Page, text: str, retries: int = 1
) -> Tuple[bool, str]:
    text = str(text)
    attempts = max(0, int(retries)) + 1
    last_observed = ""
    for _ in range(attempts):
        try:
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(text, delay=20)
        except Exception:
            pass
        last_observed = _read_active_element_value(page)
        if last_observed == text:
            time.sleep(0.2)
            stable = _read_active_element_value(page)
            if stable == text:
                return True, last_observed
            last_observed = stable
        try:
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.insert_text(text)
        except Exception:
            pass
        last_observed = _read_active_element_value(page)
        if last_observed == text:
            time.sleep(0.2)
            stable = _read_active_element_value(page)
            if stable == text:
                return True, last_observed
            last_observed = stable
    return False, last_observed


def _try_dom_type(
    page: Page,
    action_input: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    locator = _dom_locator_from_action_input(page, action_input, allow_text_key=False)
    if locator is None:
        return None
    try:
        if locator.count() == 0:
            return None
        loc = locator.first
        text = str(action_input.get("text", ""))
        ok, observed, method = _type_and_verify_locator(loc, text)
        if not ok:
            return {
                "ok": False,
                "action": "type",
                "dom": True,
                "error": f"typed_value_mismatch (method={method})",
                "observed": observed,
                "expected": text,
            }
        return {
            "ok": True,
            "action": "type",
            "dom": True,
            "len": len(text),
            "verified": True,
            "dom_hint": _extract_dom_hint(action_input),
        }
    except Exception as e:
        return {"ok": False, "action": "type", "dom": True, "error": str(e)}


def _hint_list(d: Dict[str, Any], key: str) -> List[Any]:
    v = d.get(key)
    if isinstance(v, list):
        return v
    return []


def _apply_site_hints(
    page: Page,
    action: str,
    action_input: Dict[str, Any],
    site_hints: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not site_hints:
        return None

    for item in _hint_list(site_hints, "role_name"):
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        name = item.get("name")
        if not role or not name:
            continue
        hint_input = dict(action_input)
        hint_input["role"] = role
        hint_input["name"] = name
        if action == "type":
            res = _try_dom_type(page, hint_input)
        else:
            res = _try_dom_click(page, action, hint_input)
        if res and res.get("ok"):
            res["dom_hint_source"] = "site_map"
            return res

    for selector in _hint_list(site_hints, "selectors"):
        if not isinstance(selector, str):
            continue
        hint_input = dict(action_input)
        hint_input["selector"] = selector
        if action == "type":
            res = _try_dom_type(page, hint_input)
        else:
            res = _try_dom_click(page, action, hint_input)
        if res and res.get("ok"):
            res["dom_hint_source"] = "site_map"
            return res

    for text_value in _hint_list(site_hints, "text"):
        if not isinstance(text_value, str):
            continue
        hint_input = dict(action_input)
        hint_input["target_text"] = text_value
        if action == "type":
            res = _try_dom_type(page, hint_input)
        else:
            res = _try_dom_click(page, action, hint_input)
        if res and res.get("ok"):
            res["dom_hint_source"] = "site_map"
            return res

    return None


def _apply_dom_heuristics(
    page: Page,
    action: str,
    action_input: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if action not in ("left_click", "double_click", "right_click", "type"):
        return None

    common_selectors = [
        "[role='searchbox']",
        "input[type='search']",
        "input[name='q']",
        "input[aria-label*='search' i]",
        "input[placeholder*='search' i]",
        "input[type='text']",
        "textarea",
    ]
    for selector in common_selectors:
        hint_input = dict(action_input)
        hint_input["selector"] = selector
        if action == "type":
            res = _try_dom_type(page, hint_input)
        else:
            res = _try_dom_click(page, action, hint_input)
        if res and res.get("ok"):
            res["dom_hint_source"] = "heuristic"
            return res

    return None


def update_site_hints(
    site_map: Dict[str, Any],
    domain: str,
    dom_hint: Dict[str, Any],
) -> bool:
    if not domain or not dom_hint:
        return False
    entry = site_map.get(domain)
    if not isinstance(entry, dict):
        entry = {}
        site_map[domain] = entry

    updated = False
    hint_type = dom_hint.get("type")
    if hint_type == "selector":
        selectors = entry.setdefault("selectors", [])
        if isinstance(selectors, list) and dom_hint.get("value") not in selectors:
            selectors.append(dom_hint.get("value"))
            updated = True
    elif hint_type == "role_name":
        role_name = entry.setdefault("role_name", [])
        if isinstance(role_name, list):
            item = {"role": dom_hint.get("role"), "name": dom_hint.get("name")}
            if item not in role_name:
                role_name.append(item)
                updated = True
    elif hint_type == "text":
        texts = entry.setdefault("text", [])
        if isinstance(texts, list) and dom_hint.get("value") not in texts:
            texts.append(dom_hint.get("value"))
            updated = True

    return updated


def _css_attr_selector(attr: str, value: str) -> str:
    safe = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'[{attr}="{safe}"]'


def _infer_role_from_tag(tag: str, input_type: str) -> str:
    tag = (tag or "").lower().strip()
    input_type = (input_type or "").lower().strip()
    if tag == "button":
        return "button"
    if tag == "a":
        return "link"
    if tag == "textarea":
        return "textbox"
    if tag == "select":
        return "combobox"
    if tag == "input":
        if input_type in ("button", "submit", "reset"):
            return "button"
        if input_type == "checkbox":
            return "checkbox"
        if input_type == "radio":
            return "radio"
        if input_type in (
            "text",
            "search",
            "email",
            "password",
            "url",
            "tel",
            "number",
        ):
            return "textbox"
    return ""


def _build_dom_hint_from_element_info(info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    role = (info.get("role") or "").strip()
    tag = (info.get("tag") or "").strip()
    input_type = (info.get("type") or "").strip()
    aria_label = (info.get("ariaLabel") or "").strip()
    title = (info.get("title") or "").strip()
    alt = (info.get("alt") or "").strip()
    placeholder = (info.get("placeholder") or "").strip()
    name_attr = (info.get("nameAttr") or "").strip()
    elem_id = (info.get("id") or "").strip()
    data_testid = (info.get("dataTestId") or "").strip()
    data_test = (info.get("dataTest") or "").strip()
    data_qa = (info.get("dataQa") or "").strip()
    data_action = (info.get("dataAction") or "").strip()
    href = (info.get("href") or "").strip()
    text = (info.get("text") or "").strip()

    if not role:
        role = _infer_role_from_tag(tag, input_type)

    name = ""
    for candidate in (aria_label, title, alt, placeholder, text, name_attr):
        if candidate:
            name = candidate
            break
    if name and len(name) > 100:
        name = name[:100].rstrip()

    if role and name:
        return {"type": "role_name", "role": role, "name": name}

    selector = ""
    if data_testid:
        selector = _css_attr_selector("data-testid", data_testid)
    elif data_test:
        selector = _css_attr_selector("data-test", data_test)
    elif data_qa:
        selector = _css_attr_selector("data-qa", data_qa)
    elif data_action:
        selector = _css_attr_selector("data-action", data_action)
    elif elem_id:
        selector = _css_attr_selector("id", elem_id)
    elif name_attr:
        selector = _css_attr_selector("name", name_attr)
    elif aria_label:
        selector = _css_attr_selector("aria-label", aria_label)
    elif href and len(href) <= 120:
        selector = f'a[href^="{href}"]'

    if selector:
        return {"type": "selector", "value": selector}

    if text:
        value = text if len(text) <= 80 else text[:80].rstrip()
        return {"type": "text", "value": value}

    return None


def infer_dom_hint_from_point(
    page: Page, x: float, y: float
) -> Optional[Dict[str, Any]]:
    try:
        info = page.evaluate(
            """
            ({ x, y }) => {
                const start = document.elementFromPoint(x, y);
                if (!start) return null;
                const labelFrom = (el) => {
                  if (!el) return "";
                  const aria = el.getAttribute("aria-label") || "";
                  if (aria) return aria;
                  const labelledby = el.getAttribute("aria-labelledby") || "";
                  if (labelledby) {
                    const ids = labelledby.split(/\\s+/).filter(Boolean);
                    const texts = ids.map((id) => {
                      const node = document.getElementById(id);
                      return node ? (node.innerText || node.textContent || "") : "";
                    }).filter(Boolean);
                    if (texts.length) return texts.join(" ").trim();
                  }
                  const title = el.getAttribute("title") || "";
                  if (title) return title;
                  const alt = el.getAttribute("alt") || "";
                  return alt || "";
                };
                const isUseful = (el) => {
                  if (!el) return false;
                  if (el.id) return true;
                  if (el.getAttribute("data-testid") || el.getAttribute("data-test") || el.getAttribute("data-qa")) return true;
                  if (labelFrom(el) || el.getAttribute("role") || el.getAttribute("name")) return true;
                  if ((el.innerText || el.textContent || "").trim()) return true;
                  return false;
                };
                let cur = start;
                let i = 0;
                while (cur && i < 8 && !isUseful(cur)) {
                  cur = cur.parentElement;
                  i += 1;
                }
                const el = cur || start;
                const attr = (n) => el.getAttribute(n);
                const text = (el.innerText || el.textContent || "").trim();
                return {
                  tag: el.tagName ? el.tagName.toLowerCase() : "",
                  type: attr("type") || "",
                  role: attr("role") || "",
                  ariaLabel: labelFrom(el) || "",
                  title: attr("title") || "",
                  alt: attr("alt") || "",
                  placeholder: attr("placeholder") || "",
                  nameAttr: attr("name") || "",
                  id: el.id || "",
                  dataTestId: attr("data-testid") || "",
                  dataTest: attr("data-test") || "",
                  dataQa: attr("data-qa") || "",
                  dataAction: attr("data-action") || "",
                  href: attr("href") || "",
                  text
                };
            }
            """,
            {"x": x, "y": y},
        )
    except Exception:
        return None
    if not isinstance(info, dict):
        return None
    return _build_dom_hint_from_element_info(info)


def infer_clickable_hint_from_point(
    page: Page, x: float, y: float
) -> Optional[Dict[str, Any]]:
    try:
        info = page.evaluate(
            """
            ({ x, y }) => {
                const start = document.elementFromPoint(x, y);
                if (!start) return null;
                const clickableSelector = "a,button,[role='button'],[role='link'],[role='tab'],input[type='button'],input[type='submit'],input[type='reset'],input[type='checkbox'],input[type='radio'],[onclick],[data-action]";
                const labelFrom = (el) => {
                  if (!el) return "";
                  const aria = el.getAttribute("aria-label") || "";
                  if (aria) return aria;
                  const labelledby = el.getAttribute("aria-labelledby") || "";
                  if (labelledby) {
                    const ids = labelledby.split(/\\s+/).filter(Boolean);
                    const texts = ids.map((id) => {
                      const node = document.getElementById(id);
                      return node ? (node.innerText || node.textContent || "") : "";
                    }).filter(Boolean);
                    if (texts.length) return texts.join(" ").trim();
                  }
                  const title = el.getAttribute("title") || "";
                  if (title) return title;
                  const alt = el.getAttribute("alt") || "";
                  return alt || "";
                };
                const isClickable = (el) => {
                const tag = (el.tagName || '').toLowerCase();
                if (tag === 'a' || tag === 'button') return true;
                if (tag === 'input') {
                  const t = (el.getAttribute('type') || '').toLowerCase();
                  if (['button','submit','reset','checkbox','radio'].includes(t)) return true;
                }
                const role = (el.getAttribute('role') || '').toLowerCase();
                if (role === 'button' || role === 'link' || role === 'tab') return true;
                if (el.getAttribute('onclick')) return true;
                const tabindex = el.getAttribute('tabindex');
                if (tabindex !== null && String(tabindex) !== '-1') return true;
                  return false;
                };
                const isUseful = (el) => {
                  if (!el) return false;
                  if (el.id) return true;
                  if (el.getAttribute("data-testid") || el.getAttribute("data-test") || el.getAttribute("data-qa")) return true;
                  if (labelFrom(el) || el.getAttribute("role") || el.getAttribute("name")) return true;
                  if ((el.innerText || el.textContent || "").trim()) return true;
                  return false;
                };
                let cur = start.closest ? start.closest(clickableSelector) : null;
                if (!cur) cur = start;
                let i = 0;
                while (cur && i < 6 && !isClickable(cur)) {
                  cur = cur.parentElement;
                  i += 1;
                }
                let el = cur || start;
                let j = 0;
                while (el && j < 8 && !isUseful(el)) {
                  el = el.parentElement;
                  j += 1;
                }
                el = el || cur || start;
                const attr = (n) => el.getAttribute(n);
                const text = (el.innerText || el.textContent || "").trim();
                return {
                tag: el.tagName ? el.tagName.toLowerCase() : "",
                type: attr("type") || "",
                role: attr("role") || "",
                ariaLabel: labelFrom(el) || "",
                title: attr("title") || "",
                alt: attr("alt") || "",
                placeholder: attr("placeholder") || "",
                nameAttr: attr("name") || "",
                id: el.id || "",
                dataTestId: attr("data-testid") || "",
                dataTest: attr("data-test") || "",
                dataQa: attr("data-qa") || "",
                dataAction: attr("data-action") || "",
                href: attr("href") || "",
                text
              };
            }
            """,
            {"x": x, "y": y},
        )
    except Exception:
        return None
    if not isinstance(info, dict):
        return None
    return _build_dom_hint_from_element_info(info)


def _init_manual_click_capture(
    page: Page, enabled: bool, verbose: bool = False
) -> None:
    if not enabled:
        return
    try:
        initialized = page.evaluate(
            r"""
            () => {
              try {
                window.__cuaManualClicks = [];
                window.__cuaIgnoreManualClicks = false;
                if (window.__cuaManualClickInit) return true;
                const clean = (s) => (s || "").toString().replace(/\s+/g, " ").trim().slice(0, 200);
                const handler = (ev) => {
                  if (window.__cuaIgnoreManualClicks) return;
                  const x = Number(ev.clientX || 0);
                  const y = Number(ev.clientY || 0);
                  const path = (typeof ev.composedPath === "function") ? ev.composedPath() : [];
                  let el = null;
                  for (const node of path) {
                    if (node && node.nodeType === 1 && node.tagName) { el = node; break; }
                  }
                  el = el || document.elementFromPoint(x, y) || ev.target;
                  if (el && el.closest) {
                    const clickable = el.closest("a,button,[role='button'],[role='link'],[role='tab'],[data-action]");
                    el = clickable || el;
                  }
                  if (!el) return;
                  const labelFrom = (node) => {
                    if (!node) return "";
                    const aria = (node.getAttribute && node.getAttribute("aria-label")) || "";
                    if (aria) return aria;
                    const labelledby = (node.getAttribute && node.getAttribute("aria-labelledby")) || "";
                    if (labelledby) {
                      const ids = labelledby.split(/\\s+/).filter(Boolean);
                      const texts = ids.map((id) => {
                        const ref = document.getElementById(id);
                        return ref ? (ref.innerText || ref.textContent || "") : "";
                      }).filter(Boolean);
                      if (texts.length) return texts.join(" ").trim();
                    }
                    const title = (node.getAttribute && node.getAttribute("title")) || "";
                    if (title) return title;
                    const alt = (node.getAttribute && node.getAttribute("alt")) || "";
                    return alt || "";
                  };
                  const isClickable = (node) => {
                    if (!node || !node.tagName) return false;
                    const tag = node.tagName.toLowerCase();
                    if (tag === "a" || tag === "button") return true;
                    if (tag === "input") {
                      const t = (node.getAttribute("type") || "").toLowerCase();
                      if (["button", "submit", "reset", "checkbox", "radio"].includes(t)) return true;
                    }
                    const role = (node.getAttribute("role") || "").toLowerCase();
                    if (role === "button" || role === "link" || role === "tab") return true;
                    if (node.getAttribute("onclick")) return true;
                    const tabindex = node.getAttribute("tabindex");
                    if (tabindex !== null && String(tabindex) !== "-1") return true;
                    return false;
                  };
                  let cur = el;
                  let i = 0;
                  while (cur && i < 6 && !isClickable(cur)) {
                    cur = cur.parentElement;
                    i += 1;
                  }
                  el = cur || el;
                  const attr = (n) => (el.getAttribute && el.getAttribute(n)) || "";
                  const text = clean(el.innerText || el.textContent || "");
                  const payload = {
                    ts: Date.now(),
                    x,
                    y,
                    tag: el.tagName ? el.tagName.toLowerCase() : "",
                    role: attr("role") || "",
                    id: el.id || "",
                    nameAttr: attr("name") || "",
                    ariaLabel: labelFrom(el) || "",
                    title: attr("title") || "",
                    alt: attr("alt") || "",
                    href: attr("href") || "",
                    dataAction: attr("data-action") || "",
                    placeholder: attr("placeholder") || "",
                    text,
                  };
                  window.__cuaManualClicks.push(payload);
                  if (window.__cuaManualClicks.length > 60) window.__cuaManualClicks.shift();
                };
                window.addEventListener("pointerdown", handler, true);
                window.__cuaManualClickHandler = handler;
                window.__cuaManualClickInit = true;
                return true;
              } catch (e) {
                return false;
              }
            }
            """
        )
        if verbose and initialized:
            _log_info("[manual] Manual click capture enabled (headed mode).")
    except Exception:
        return


def _set_manual_click_ignore(page: Page, ignore: bool) -> None:
    try:
        page.evaluate(
            r"""
            (flag) => {
              try { window.__cuaIgnoreManualClicks = !!flag; } catch (e) {}
            }
            """,
            bool(ignore),
        )
    except Exception:
        return


def _poll_manual_clicks(
    page: Page, since_ts: float
) -> Tuple[List[Dict[str, Any]], float]:
    try:
        result = page.evaluate(
            """
            (sinceTs) => {
              const clicks = Array.isArray(window.__cuaManualClicks) ? window.__cuaManualClicks : [];
              const fresh = clicks.filter((c) => Number(c.ts || 0) > Number(sinceTs || 0));
              let lastTs = Number(sinceTs || 0);
              for (const c of fresh) {
                const ts = Number(c.ts || 0);
                if (ts > lastTs) lastTs = ts;
              }
              return { fresh, lastTs };
            }
            """,
            float(since_ts or 0),
        )
    except Exception:
        return [], since_ts
    if not isinstance(result, dict):
        return [], since_ts
    fresh = result.get("fresh")
    last_ts = result.get("lastTs")
    clicks: List[Dict[str, Any]] = (
        [c for c in fresh if isinstance(c, dict)] if isinstance(fresh, list) else []
    )
    if isinstance(last_ts, (int, float, str)):
        try:
            last_val = float(last_ts)
        except Exception:
            last_val = since_ts
    else:
        last_val = since_ts
    return clicks, max(since_ts, last_val)


def _read_step_training_token(signal_path: str) -> int:
    if not signal_path:
        return 0
    try:
        raw = Path(signal_path).read_text(encoding="utf-8").strip()
    except Exception:
        return 0
    if not raw:
        return 0
    try:
        return int(raw)
    except Exception:
        return 0


def execute_computer_action(
    page: Page,
    action: str,
    action_input: Dict[str, Any],
    xform: CoordinateTransform,
    *,
    pre_click_sleep_s: float,
    pre_type_sleep_s: float,
    site_hints: Optional[Dict[str, Any]] = None,
    use_dom_heuristics: bool = True,
    learn_from_vision: bool = False,
) -> Optional[Dict[str, Any]]:
    action = action.lower().strip()
    explicit_dom_target = _has_explicit_dom_target(action_input)

    if action == "left_click":
        dom_result = _try_dom_click(page, action, action_input)
        if dom_result and (dom_result.get("ok") or dom_result.get("terminal")):
            return dom_result
        if site_hints and not explicit_dom_target:
            dom_result = _apply_site_hints(page, action, action_input, site_hints)
            if dom_result and dom_result.get("ok"):
                return dom_result
        if use_dom_heuristics and not explicit_dom_target:
            dom_result = _apply_dom_heuristics(page, action, action_input)
            if dom_result and dom_result.get("ok"):
                return dom_result
        pts = extract_action_points_for_marking(action, action_input, xform)
        if not pts:
            raise ValueError(f"left_click missing coordinate(s): {action_input}")
        ax, ay = pts[0]
        if learn_from_vision:
            dom_hint = infer_clickable_hint_from_point(page, ax, ay)
            if dom_hint:
                hint_input = _action_input_from_dom_hint(dom_hint)
                dom_result = _try_dom_click(page, action, hint_input)
                if dom_result and dom_result.get("ok"):
                    dom_result["dom_hint_source"] = "vision_point"
                    return dom_result
        settle_before_precise_action(page, pre_click_sleep_s)
        page.mouse.click(ax, ay, button="left")
        result = {
            "ok": True,
            "action": "left_click",
            "actual": [ax, ay],
            "mark_points": [[ax, ay]],
        }
        if learn_from_vision:
            dom_hint = infer_dom_hint_from_point(page, ax, ay)
            if dom_hint:
                result["dom_hint"] = dom_hint
                result["dom_hint_source"] = "vision"
        if dom_result and not dom_result.get("ok"):
            result["dom_fallback_error"] = dom_result.get("error", "dom_click_failed")
        return result

    if action == "double_click":
        dom_result = _try_dom_click(page, action, action_input)
        if dom_result and dom_result.get("ok"):
            return dom_result
        if site_hints and not explicit_dom_target:
            dom_result = _apply_site_hints(page, action, action_input, site_hints)
            if dom_result and dom_result.get("ok"):
                return dom_result
        if use_dom_heuristics and not explicit_dom_target:
            dom_result = _apply_dom_heuristics(page, action, action_input)
            if dom_result and dom_result.get("ok"):
                return dom_result
        pts = extract_action_points_for_marking(action, action_input, xform)
        if not pts:
            raise ValueError(f"double_click missing coordinate(s): {action_input}")
        ax, ay = pts[0]
        if learn_from_vision:
            dom_hint = infer_clickable_hint_from_point(page, ax, ay)
            if dom_hint:
                hint_input = _action_input_from_dom_hint(dom_hint)
                dom_result = _try_dom_click(page, action, hint_input)
                if dom_result and dom_result.get("ok"):
                    dom_result["dom_hint_source"] = "vision_point"
                    return dom_result
        settle_before_precise_action(page, pre_click_sleep_s)
        page.mouse.dblclick(ax, ay, button="left")
        result = {
            "ok": True,
            "action": "double_click",
            "actual": [ax, ay],
            "mark_points": [[ax, ay]],
        }
        if learn_from_vision:
            dom_hint = infer_dom_hint_from_point(page, ax, ay)
            if dom_hint:
                result["dom_hint"] = dom_hint
                result["dom_hint_source"] = "vision"
        if dom_result and not dom_result.get("ok"):
            result["dom_fallback_error"] = dom_result.get("error", "dom_click_failed")
        return result

    if action == "right_click":
        dom_result = _try_dom_click(page, action, action_input)
        if dom_result and dom_result.get("ok"):
            return dom_result
        if site_hints and not explicit_dom_target:
            dom_result = _apply_site_hints(page, action, action_input, site_hints)
            if dom_result and dom_result.get("ok"):
                return dom_result
        if use_dom_heuristics and not explicit_dom_target:
            dom_result = _apply_dom_heuristics(page, action, action_input)
            if dom_result and dom_result.get("ok"):
                return dom_result
        pts = extract_action_points_for_marking(action, action_input, xform)
        if not pts:
            raise ValueError(f"right_click missing coordinate(s): {action_input}")
        ax, ay = pts[0]
        if learn_from_vision:
            dom_hint = infer_clickable_hint_from_point(page, ax, ay)
            if dom_hint:
                hint_input = _action_input_from_dom_hint(dom_hint)
                dom_result = _try_dom_click(page, action, hint_input)
                if dom_result and dom_result.get("ok"):
                    dom_result["dom_hint_source"] = "vision_point"
                    return dom_result
        settle_before_precise_action(page, pre_click_sleep_s)
        page.mouse.click(ax, ay, button="right")
        result = {
            "ok": True,
            "action": "right_click",
            "actual": [ax, ay],
            "mark_points": [[ax, ay]],
        }
        if learn_from_vision:
            dom_hint = infer_dom_hint_from_point(page, ax, ay)
            if dom_hint:
                result["dom_hint"] = dom_hint
                result["dom_hint_source"] = "vision"
        if dom_result and not dom_result.get("ok"):
            result["dom_fallback_error"] = dom_result.get("error", "dom_click_failed")
        return result

    if action == "mouse_move":
        pts = extract_action_points_for_marking(action, action_input, xform)
        if not pts:
            raise ValueError(f"mouse_move missing coordinate(s): {action_input}")
        ax, ay = pts[0]
        page.mouse.move(ax, ay)
        return {"ok": True, "action": "mouse_move", "actual": [ax, ay]}

    if action == "left_click_drag":
        pts = extract_action_points_for_marking(action, action_input, xform)
        if len(pts) != 2:
            raise ValueError(f"left_click_drag missing start/end: {action_input}")
        (asx, asy), (aex, aey) = pts
        settle_before_precise_action(page, pre_click_sleep_s)
        page.mouse.move(asx, asy)
        page.mouse.down(button="left")
        page.mouse.move(aex, aey)
        page.mouse.up(button="left")
        return {
            "ok": True,
            "action": "left_click_drag",
            "actual_start": [asx, asy],
            "actual_end": [aex, aey],
            "mark_points": [[asx, asy], [aex, aey]],
        }

    if action == "type":
        text = str(action_input.get("text", ""))
        if pre_type_sleep_s:
            time.sleep(max(0.0, float(pre_type_sleep_s)))

        dom_result = _try_dom_type(page, action_input)
        if dom_result and dom_result.get("ok"):
            return dom_result
        hintable = any(
            action_input.get(k)
            for k in ("selector", "role", "name", "label", "target_text")
        )
        if not hintable and _active_element_is_editable(page):
            ok, observed = _type_and_verify_active_element(page, text)
            if ok:
                return {
                    "ok": True,
                    "action": "type",
                    "len": len(text),
                    "verified": True,
                    "mode": "active",
                }
        if site_hints and not explicit_dom_target:
            dom_result = _apply_site_hints(page, action, action_input, site_hints)
            if dom_result and dom_result.get("ok"):
                return dom_result
        if use_dom_heuristics and not explicit_dom_target:
            dom_result = _apply_dom_heuristics(page, action, action_input)
            if dom_result and dom_result.get("ok"):
                return dom_result

        ok, observed = _type_and_verify_active_element(page, text)
        if not ok:
            return {
                "ok": False,
                "action": "type",
                "error": "typed_value_mismatch_active",
                "observed": observed,
                "expected": text,
            }
        return {"ok": True, "action": "type", "len": len(text), "verified": True}

    if action == "key":
        key_raw = (
            action_input.get("key")
            or action_input.get("keys")
            or action_input.get("combo")
            or action_input.get("key_combo")
            or action_input.get("text")
            or ""
        )
        if not key_raw:
            raise ValueError(f"key missing: {action_input}")
        if isinstance(key_raw, (list, tuple)):
            key_raw = key_raw[0] if key_raw else ""
        if isinstance(key_raw, dict):
            key_raw = (
                key_raw.get("key")
                or key_raw.get("keys")
                or key_raw.get("combo")
                or key_raw.get("text")
                or ""
            )
        if not key_raw:
            raise ValueError(f"key missing: {action_input}")
        normalized = normalize_playwright_key_combo(str(key_raw))
        page.keyboard.press(normalized)
        return {"ok": True, "action": "key", "key": normalized}

    if action == "hold_key":
        key_raw = action_input.get("key") or action_input.get("text") or ""
        duration = float(action_input.get("duration", 0.25))
        if not key_raw:
            raise ValueError(f"hold_key missing: {action_input}")
        normalized = normalize_playwright_key_combo(str(key_raw))
        if "+" in normalized:
            page.keyboard.press(normalized)
        else:
            page.keyboard.down(normalized)
            time.sleep(max(0.0, duration))
            page.keyboard.up(normalized)
        return {
            "ok": True,
            "action": "hold_key",
            "key": normalized,
            "duration": duration,
        }

    if action == "scroll":
        direction = str(action_input.get("direction", "down")).lower()
        amount = float(action_input.get("amount", 400))
        amount = clamp(amount, 50, 2000)

        dx, dy = 0.0, 0.0
        if direction == "down":
            dy = amount
        elif direction == "up":
            dy = -amount
        elif direction == "right":
            dx = amount
        elif direction == "left":
            dx = -amount
        else:
            dy = amount

        page.mouse.wheel(dx, dy)
        return {"ok": True, "action": "scroll", "dx": dx, "dy": dy}

    if action == "wait":
        duration = float(action_input.get("duration", 0.5))
        time.sleep(clamp(duration, 0.05, 10.0))
        return {"ok": True, "action": "wait", "duration": duration}

    if action == "reload":
        page.reload(wait_until="domcontentloaded")
        return {"ok": True, "action": "reload"}

    if action == "screenshot":
        return {"ok": True, "action": "screenshot"}

    if action == "select_option":
        selector = str(action_input.get("selector", ""))
        label = (
            action_input.get("label")
            or action_input.get("text")
            or action_input.get("option")
        )
        value = action_input.get("value")
        try:
            loc = page.locator(selector)
            if loc.count() == 0:
                return {
                    "ok": False,
                    "action": "select_option",
                    "error": f"No element found for selector: {selector!r}",
                }
            kwargs: Dict[str, Any] = {}
            if label is not None:
                kwargs["label"] = str(label)
            elif value is not None:
                kwargs["value"] = str(value)
            loc.first.select_option(**kwargs, timeout=5000)
            return {
                "ok": True,
                "action": "select_option",
                "selector": selector,
                "label": label,
                "value": value,
            }
        except Exception as e:
            return {
                "ok": False,
                "action": "select_option",
                "error": str(e),
                "fallback": (
                    "Element is not a native <select> or option not found. "
                    "Fall back to: left_click the dropdown to open it, "
                    "then left_click the target option."
                ),
            }

    return None


def _execute_action_with_runtime_controls(
    page: Page,
    action: str,
    action_args: Dict[str, Any],
    xform: CoordinateTransform,
    *,
    pre_click_sleep_s: float,
    pre_type_sleep_s: float,
    post_type_sleep_s: float,
    post_action_sleep_s: float,
    site_hints_for_domain: Optional[Dict[str, Any]],
    learn_from_vision: bool,
) -> Tuple[Optional[Dict[str, Any]], float]:
    action_exec_t0 = time.perf_counter()
    _set_manual_click_ignore(page, True)
    try:
        result_dict = execute_computer_action(
            page,
            action,
            action_args,
            xform,
            pre_click_sleep_s=pre_click_sleep_s,
            pre_type_sleep_s=pre_type_sleep_s,
            site_hints=site_hints_for_domain,
            learn_from_vision=learn_from_vision,
        )
    finally:
        _set_manual_click_ignore(page, False)
    if action == "type" and post_type_sleep_s:
        time.sleep(max(0.0, float(post_type_sleep_s)))
    time.sleep(DEFAULT_ACTION_SLEEP_S)
    if post_action_sleep_s:
        time.sleep(max(0.0, float(post_action_sleep_s)))
    return result_dict, (time.perf_counter() - action_exec_t0)


def _extract_mark_points_from_result(
    result_dict: Optional[Dict[str, Any]],
) -> List[Tuple[float, float]]:
    marks_actual: List[Tuple[float, float]] = []
    if isinstance(result_dict, dict) and result_dict.get("mark_points"):
        try:
            for pt in result_dict["mark_points"]:
                marks_actual.append((float(pt[0]), float(pt[1])))
        except Exception:
            marks_actual = []
    return marks_actual


def _post_action_success_bookkeeping(
    *,
    context: BrowserContext,
    page: Page,
    action: str,
    result_dict: Optional[Dict[str, Any]],
    step: int,
    enable_agent_view: bool,
    agent_view_dir: str,
    x_size_px: int,
    x_thickness_px: int,
    last_mark_points_actual: List[Tuple[float, float]],
    fallback_mark_points: Optional[List[Tuple[float, float]]],
    result_prefix: str,
    add_history: Callable[[str], None],
    site_hints: Dict[str, Any],
    site_hints_path: str,
    verbose: bool,
) -> Tuple[Page, List[Tuple[float, float]], str]:
    page = maybe_switch_to_new_tab(context, page, verbose=verbose)
    marks2_actual = _extract_mark_points_from_result(result_dict)
    updated_last_mark_points = (
        marks2_actual[:] if marks2_actual else last_mark_points_actual
    )
    post_marks = marks2_actual if marks2_actual else fallback_mark_points
    _ = maybe_save_agent_view(
        enable_agent_view,
        page,
        agent_view_dir,
        step,
        f"pw_post_{action}",
        mark_points=post_marks if post_marks else None,
        x_size_px=x_size_px,
        thickness_px=x_thickness_px,
    )
    result_text = f"{result_prefix} {action}. Result: {result_dict}"
    add_history(f"{action}: {result_text}")
    if (
        isinstance(result_dict, dict)
        and result_dict.get("ok")
        and result_dict.get("dom_hint")
    ):
        domain = normalize_domain(page.url)
        if update_site_hints(site_hints, domain, result_dict["dom_hint"]):
            save_site_hints(site_hints_path, site_hints)
    return page, updated_last_mark_points, result_text


def _build_arm_preview_followup(
    *,
    page: Page,
    requested_point_actual: Tuple[float, float],
    viewport: Viewport,
    model_viewport: Viewport,
    xform: CoordinateTransform,
    x_size_px: int,
    x_thickness_px: int,
    notice_text: str,
) -> Tuple[str, str, List[Dict[str, Any]]]:
    preview_png = capture_model_screenshot_png(
        page,
        actual_w=viewport.width,
        actual_h=viewport.height,
        model_w=model_viewport.width,
        model_h=model_viewport.height,
    )
    mx, my = xform.to_model(requested_point_actual[0], requested_point_actual[1])
    preview_png = _draw_red_x_on_png_bytes(
        preview_png, [(mx, my)], x_size_px=x_size_px, thickness_px=x_thickness_px
    )
    armed_notice = notice_text
    last_result_text = "Preview shown; confirm or choose new coordinate."
    input_items = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": armed_notice},
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{b64_png(preview_png)}",
                },
            ],
        }
    ]
    return armed_notice, last_result_text, input_items


@dataclass
class ArmCommitGateState:
    page: Page
    armed: Optional["ArmedClick"]
    armed_notice: str
    last_result_text: str
    input_items: List[Dict[str, Any]]
    last_mark_points_actual: List[Tuple[float, float]]
    should_continue: bool


@dataclass
class StepExceptionResolution:
    page: Page
    last_result_text: str
    should_continue: bool
    outcome: Optional[RunOutcome] = None


@dataclass
class StepActionPrepResult:
    action: str
    action_args: Dict[str, Any]
    why: str
    last_result_text: str
    should_continue: bool


@dataclass
class VerifyGuardResolution:
    page: Page
    last_result_text: str
    should_continue: bool
    outcome: Optional[RunOutcome] = None


@dataclass
class StepResponseResolution:
    page: Page
    data: Optional[Dict[str, Any]]
    last_result_text: str
    should_continue: bool
    outcome: Optional[RunOutcome] = None


def _handle_arm_commit_gate(
    *,
    arm_commit: bool,
    action: str,
    marks_actual: List[Tuple[float, float]],
    armed: Optional["ArmedClick"],
    why: str,
    confirm_token: str,
    step: int,
    page: Page,
    context: BrowserContext,
    action_args: Dict[str, Any],
    xform: CoordinateTransform,
    viewport: Viewport,
    model_viewport: Viewport,
    pre_click_sleep_s: float,
    pre_type_sleep_s: float,
    learn_from_vision: bool,
    site_hints: Dict[str, Any],
    site_hints_path: str,
    enable_agent_view: bool,
    agent_view_dir: str,
    x_size_px: int,
    x_thickness_px: int,
    verbose: bool,
    input_items: List[Dict[str, Any]],
    last_mark_points_actual: List[Tuple[float, float]],
    add_history: Callable[[str], None],
    record_action: Callable[[str, Dict[str, Any], Optional[Dict[str, Any]]], None],
    armed_notice: str,
    last_result_text: str,
) -> ArmCommitGateState:
    if not (arm_commit and action in ARM_COMMIT_ELIGIBLE):
        return ArmCommitGateState(
            page=page,
            armed=armed,
            armed_notice=armed_notice,
            last_result_text=last_result_text,
            input_items=input_items,
            last_mark_points_actual=last_mark_points_actual,
            should_continue=False,
        )

    if not marks_actual:
        if any(
            _has_nonempty_arg(action_args, k)
            for k in ("selector", "role", "name", "label", "target_text")
        ):
            _log_info(
                f"[arm] Skipping arm/commit for DOM-targeted {action} without coordinates."
            )
        return ArmCommitGateState(
            page=page,
            armed=armed,
            armed_notice=armed_notice,
            last_result_text=last_result_text,
            input_items=input_items,
            last_mark_points_actual=last_mark_points_actual,
            should_continue=False,
        )

    requested_point_actual = (float(marks_actual[0][0]), float(marks_actual[0][1]))
    page.mouse.move(requested_point_actual[0], requested_point_actual[1])

    if (
        armed is not None
        and armed.action == action
        and points_close(armed.point_actual, requested_point_actual)
    ):
        if confirm_token.lower() in why.lower():
            if verbose:
                _log_info(
                    f"[arm] COMMIT {action} at {requested_point_actual} (token present)"
                )

            _ = maybe_save_agent_view(
                enable_agent_view,
                page,
                agent_view_dir,
                step,
                f"pw_preclick_{action}",
                mark_points=[requested_point_actual],
                x_size_px=x_size_px,
                thickness_px=x_thickness_px,
            )

            result_dict, action_elapsed_s = _execute_action_with_runtime_controls(
                page,
                action,
                action_args,
                xform,
                pre_click_sleep_s=pre_click_sleep_s,
                pre_type_sleep_s=pre_type_sleep_s,
                post_type_sleep_s=0.0,
                post_action_sleep_s=0.0,
                site_hints_for_domain=site_hints.get(normalize_domain(page.url), {}),
                learn_from_vision=learn_from_vision,
            )
            record_action(action, action_args, result_dict)
            _log_timing(
                f"llm.step_{step}.action_exec.{action}",
                action_elapsed_s,
                verbose=verbose,
                warn_threshold_s=DEFAULT_TIMING_WARN_S,
            )
            page, last_mark_points_actual, last_result_text = (
                _post_action_success_bookkeeping(
                    context=context,
                    page=page,
                    action=action,
                    result_dict=result_dict,
                    step=step,
                    enable_agent_view=enable_agent_view,
                    agent_view_dir=agent_view_dir,
                    x_size_px=x_size_px,
                    x_thickness_px=x_thickness_px,
                    last_mark_points_actual=last_mark_points_actual,
                    fallback_mark_points=[requested_point_actual],
                    result_prefix="COMMITTED",
                    add_history=add_history,
                    site_hints=site_hints,
                    site_hints_path=site_hints_path,
                    verbose=verbose,
                )
            )
            armed = None
            # Preserve existing behavior: committed action continues into non-gated path.
            return ArmCommitGateState(
                page=page,
                armed=armed,
                armed_notice=armed_notice,
                last_result_text=last_result_text,
                input_items=input_items,
                last_mark_points_actual=last_mark_points_actual,
                should_continue=False,
            )

        notice_text = (
            "CLICK PREVIEW (ARMED): Not clicking yet. "
            f"To COMMIT, repeat SAME coordinate next step AND include '{confirm_token}' in WHY. "
            "If X is wrong, choose a NEW coordinate."
        )
        armed_notice, last_result_text, input_items = _build_arm_preview_followup(
            page=page,
            requested_point_actual=requested_point_actual,
            viewport=viewport,
            model_viewport=model_viewport,
            xform=xform,
            x_size_px=x_size_px,
            x_thickness_px=x_thickness_px,
            notice_text=notice_text,
        )
        add_history(f"{action}: {last_result_text}")
        return ArmCommitGateState(
            page=page,
            armed=armed,
            armed_notice=armed_notice,
            last_result_text=last_result_text,
            input_items=input_items,
            last_mark_points_actual=last_mark_points_actual,
            should_continue=True,
        )

    notice_text = (
        "CLICK PREVIEW (ARMED): Not clicking yet. "
        f"If X is correct, repeat SAME coordinate next step AND include '{confirm_token}' in WHY to COMMIT. "
        "If X is wrong, choose a NEW coordinate."
    )
    armed = ArmedClick(
        action=action, point_actual=requested_point_actual, armed_step=step
    )
    armed_notice, last_result_text, input_items = _build_arm_preview_followup(
        page=page,
        requested_point_actual=requested_point_actual,
        viewport=viewport,
        model_viewport=model_viewport,
        xform=xform,
        x_size_px=x_size_px,
        x_thickness_px=x_thickness_px,
        notice_text=notice_text,
    )
    add_history(f"{action}: {last_result_text}")
    return ArmCommitGateState(
        page=page,
        armed=armed,
        armed_notice=armed_notice,
        last_result_text=last_result_text,
        input_items=input_items,
        last_mark_points_actual=last_mark_points_actual,
        should_continue=True,
    )


def _handle_step_action_exception(
    *,
    e: Exception,
    action: str,
    context: BrowserContext,
    page: Page,
    step: int,
    step_t0: float,
    verbose: bool,
    defer_final: bool,
    enable_agent_view: bool,
    agent_view_dir: str,
    success_path: str,
    failure_path: str,
    add_history: Callable[[str], None],
    action_records: List[Dict[str, Any]],
    final_state: FinalTokenState,
) -> StepExceptionResolution:
    err_text = str(e)
    recoverable_missing_coords = (
        action in ARM_COMMIT_ELIGIBLE and "missing coordinate(s)" in err_text.lower()
    )
    if recoverable_missing_coords:
        page = maybe_switch_to_new_tab(context, page, verbose=verbose)
        _ = maybe_save_agent_view(
            enable_agent_view, page, agent_view_dir, step, "pw_exception"
        )
        _log_info(f"[LLM] Recoverable action error: {err_text}")
        last_result_text = (
            "ERROR: Click action failed because coordinates were missing after DOM targeting. "
            "Respond with JSON only using either args.x,args.y (or args.coordinate) OR a valid DOM hint "
            "(role+name preferred, or selector/target_text without truncation like '...')."
        )
        add_history(last_result_text)
        _log_timing(
            f"llm.step_{step}.total",
            time.perf_counter() - step_t0,
            verbose=verbose,
            warn_threshold_s=DEFAULT_TIMING_WARN_S,
        )
        return StepExceptionResolution(
            page=page,
            last_result_text=last_result_text,
            should_continue=True,
            outcome=None,
        )

    page = maybe_switch_to_new_tab(context, page, verbose=verbose)
    png = page.screenshot(type="png", full_page=False, scale="css")
    shot = None
    if not defer_final:
        shot = write_final_screenshot(
            png,
            verdict="FAIL",
            success_path=success_path,
            failure_path=failure_path,
        )
    _ = maybe_save_agent_view(
        enable_agent_view, page, agent_view_dir, step, "pw_exception"
    )
    _log_info(f"\nFAILED executing action '{action}': {e}")
    if not defer_final:
        _log_final("FAIL", final_state)
    if shot:
        _log_info(f"Saved failure screenshot: {shot}")
    add_history(f"ERROR: {e}")
    return StepExceptionResolution(
        page=page,
        last_result_text=f"ERROR: {e}",
        should_continue=False,
        outcome=RunOutcome(verdict="FAIL", actions=action_records, error=str(e)),
    )


def _prepare_step_action(
    *,
    data: Dict[str, Any] | None,
    password: Optional[str],
    verbose: bool,
    step: int,
    add_history: Callable[[str], None],
    wait_for_step_training: Callable[[int, str], bool],
) -> StepActionPrepResult:
    data = data if isinstance(data, dict) else {}
    action = normalize_action_name(str(data.get("action") or ""))
    action_args = data.get("args") if isinstance(data.get("args"), dict) else {}
    why = str(data.get("why") or "")
    last_result_text = ""

    if not action:
        last_result_text = "ERROR: Missing action in JSON."
        add_history(last_result_text)
        return StepActionPrepResult(
            action="",
            action_args={},
            why=why,
            last_result_text=last_result_text,
            should_continue=True,
        )

    action_args, alias_notes = _normalize_action_args_for_schema(action, action_args)
    for note in alias_notes:
        _log_info(f"[LLM] Arg alias applied: {note}")
    schema_error = _schema_error_for_action(action, action_args)
    if schema_error:
        last_result_text = f"ERROR: {schema_error} Respond with JSON only."
        _log_info(f"[LLM] Schema repair requested: {schema_error}")
        add_history(last_result_text)
        return StepActionPrepResult(
            action=action,
            action_args=action_args,
            why=why,
            last_result_text=last_result_text,
            should_continue=True,
        )

    if verbose:
        redacted_args = _redact_step_for_log(action_args, password)
        _log_info(f"Model action: {action} args={redacted_args}")

    if not wait_for_step_training(step, action):
        return StepActionPrepResult(
            action=action,
            action_args=action_args,
            why=why,
            last_result_text=last_result_text,
            should_continue=True,
        )

    return StepActionPrepResult(
        action=action,
        action_args=action_args,
        why=why,
        last_result_text=last_result_text,
        should_continue=False,
    )


def _handle_verify_guard(
    *,
    data: Dict[str, Any] | None,
    client: OpenAIClient,
    model: str,
    context: BrowserContext,
    page: Page,
    step: int,
    step_t0: float,
    success_criteria: str,
    viewport: Viewport,
    model_viewport: Viewport,
    verify_wait_s: float,
    verbose: bool,
    enable_agent_view: bool,
    agent_view_dir: str,
    last_mark_points_actual: List[Tuple[float, float]],
    x_size_px: int,
    x_thickness_px: int,
    defer_final: bool,
    success_path: str,
    failure_path: str,
    action_records: List[Dict[str, Any]],
    add_history: Callable[[str], None],
    last_result_text: str,
    final_state: FinalTokenState,
    task_prompt: Optional[str] = None,
    verify_guard_min_confidence: float = 0.0,
) -> VerifyGuardResolution:
    data = data if isinstance(data, dict) else {}
    verify_raw = data.get("verify")
    verify: Dict[str, Any] = verify_raw if isinstance(verify_raw, dict) else {}
    step_ok = str(verify.get("step_ok") or "").upper()
    criteria_visible = str(verify.get("criteria_visible") or "").upper()
    verify_reason = str(verify.get("reason") or "").strip()
    if step_ok in ("YES", "NO") or criteria_visible in ("YES", "NO"):
        msg = f"VERIFY: step_ok={step_ok} criteria_visible={criteria_visible} - {verify_reason}".strip()
        _log_info(msg)
        add_history(msg)

    if criteria_visible != "YES":
        return VerifyGuardResolution(
            page=page,
            last_result_text=last_result_text,
            should_continue=False,
            outcome=None,
        )

    verify_t0 = time.perf_counter()
    try:
        history_str = _format_action_history_for_verify(action_records)
        verify_ok, verify_verdict, verify_why, verify_confidence, verify_png = (
            verify_success_with_llm(
                client,
                model,
                page,
                success_criteria,
                viewport=viewport,
                model_viewport=model_viewport,
                verify_wait_s=verify_wait_s,
                task_prompt=task_prompt,
                action_history=history_str if task_prompt else None,
            )
        )
    except Exception as e:
        verify_ok = False
        verify_verdict = "ERROR"
        verify_why = str(e)
        verify_confidence = None
        verify_png = b""
        _log_info(f"[LLM] Success criteria check failed: {verify_why}")
    _log_timing(
        f"llm.step_{step}.verify_guard",
        time.perf_counter() - verify_t0,
        verbose=verbose,
        warn_threshold_s=DEFAULT_TIMING_WARN_S,
    )
    if (
        verify_ok
        and verify_guard_min_confidence > 0.0
        and (
            verify_confidence is None or verify_confidence < verify_guard_min_confidence
        )
    ):
        conf_str = (
            f"{verify_confidence:.2f}" if verify_confidence is not None else "unknown"
        )
        _log_info(
            f"VERIFY GUARD: PASS rejected — confidence {conf_str} below threshold {verify_guard_min_confidence:.2f}"
        )
        verify_ok = False
    if verify_ok:
        page = maybe_switch_to_new_tab(context, page, verbose=verbose)
        _ = maybe_save_agent_view(
            enable_agent_view,
            page,
            agent_view_dir,
            step,
            "llm_final_pass",
            mark_points=last_mark_points_actual if last_mark_points_actual else None,
            x_size_px=x_size_px,
            thickness_px=x_thickness_px,
        )
        shot = None
        if not defer_final:
            shot = write_final_screenshot(
                verify_png,
                verdict="PASS",
                success_path=success_path,
                failure_path=failure_path,
            )
        conf_note = (
            f" (confidence={verify_confidence:.2f})"
            if verify_confidence is not None
            else ""
        )
        if not defer_final:
            _log_final("PASS", final_state)
        _log_info(f"[LLM] Success criteria confirmed: {verify_why}{conf_note}")
        if shot:
            _log_info(f"Saved success screenshot: {shot}")
        _log_timing(
            f"llm.step_{step}.total",
            time.perf_counter() - step_t0,
            verbose=verbose,
            warn_threshold_s=DEFAULT_TIMING_WARN_S,
        )
        return VerifyGuardResolution(
            page=page,
            last_result_text=last_result_text,
            should_continue=False,
            outcome=RunOutcome(verdict="PASS", actions=action_records),
        )

    conf_note = (
        f" (confidence={verify_confidence:.2f})"
        if verify_confidence is not None
        else ""
    )
    msg = f"VERIFY GUARD: criteria_visible=YES but verifier said {verify_verdict} - {verify_why}{conf_note}"
    _log_info(msg)
    add_history(msg)
    return VerifyGuardResolution(
        page=page,
        last_result_text=last_result_text,
        should_continue=False,
        outcome=None,
    )


def _handle_step_response_content(
    *,
    assistant_text: str,
    context: BrowserContext,
    page: Page,
    step: int,
    step_t0: float,
    verbose: bool,
    defer_final: bool,
    enable_agent_view: bool,
    agent_view_dir: str,
    last_mark_points_actual: List[Tuple[float, float]],
    x_size_px: int,
    x_thickness_px: int,
    success_path: str,
    failure_path: str,
    password: Optional[str],
    action_records: List[Dict[str, Any]],
    add_history: Callable[[str], None],
    last_result_text: str,
    final_state: FinalTokenState,
) -> StepResponseResolution:
    verdict = extract_final_verdict_from_text(assistant_text)
    if verdict is not None:
        page = maybe_switch_to_new_tab(context, page, verbose=verbose)
        final_label = "llm_final_pass" if verdict == "PASS" else "llm_final_fail"
        _ = maybe_save_agent_view(
            enable_agent_view,
            page,
            agent_view_dir,
            step,
            final_label,
            mark_points=last_mark_points_actual if last_mark_points_actual else None,
            x_size_px=x_size_px,
            thickness_px=x_thickness_px,
        )
        png = page.screenshot(type="png", full_page=False, scale="css")
        if last_mark_points_actual:
            png = _draw_red_x_on_png_bytes(
                png,
                last_mark_points_actual,
                x_size_px=x_size_px,
                thickness_px=x_thickness_px,
            )
        shot = None
        if not defer_final:
            shot = write_final_screenshot(
                png,
                verdict=verdict,
                success_path=success_path,
                failure_path=failure_path,
            )
            _log_final(verdict, final_state)
            _log_info(
                f"Saved {'success' if verdict == 'PASS' else 'failure'} screenshot: {shot}"
            )
        if assistant_text:
            _log_info(_redact_secret_text(assistant_text, password))
        _log_timing(
            f"llm.step_{step}.total",
            time.perf_counter() - step_t0,
            verbose=verbose,
            warn_threshold_s=DEFAULT_TIMING_WARN_S,
        )
        return StepResponseResolution(
            page=page,
            data=None,
            last_result_text=last_result_text,
            should_continue=False,
            outcome=RunOutcome(verdict=verdict, actions=action_records),
        )

    data = _extract_json_object(assistant_text or "")
    if not isinstance(data, dict):
        last_result_text = (
            "ERROR: Model response was not valid JSON. Respond with JSON only."
        )
        _log_info(last_result_text)
        if assistant_text:
            redacted = _redact_secret_text(assistant_text, password)
            max_len = 2000
            snippet = (
                redacted
                if len(redacted) <= max_len
                else f"{redacted[:max_len]}... [truncated]"
            )
            _log_info(f"RAW_MODEL_RESPONSE: {snippet}")
        add_history(last_result_text)
        return StepResponseResolution(
            page=page,
            data=None,
            last_result_text=last_result_text,
            should_continue=True,
            outcome=None,
        )

    return StepResponseResolution(
        page=page,
        data=data,
        last_result_text=last_result_text,
        should_continue=False,
        outcome=None,
    )


def _run_agent_step_loop(
    *,
    context: BrowserContext,
    state: "AgentLoopState",
    max_steps: int,
    verbose: bool,
    model: str,
    effective_max_tokens: int,
    model_viewport: Viewport,
    viewport: Viewport,
    enable_agent_view: bool,
    agent_view_dir: str,
    post_shot_sleep_s: float,
    call_openai: Callable[..., Any],
    password: Optional[str],
    add_history: Callable[[str], None],
    build_step_prompt: Callable[[int, str, str], str],
    final_state: FinalTokenState,
    defer_final: bool,
    x_size_px: int,
    x_thickness_px: int,
    success_path: str,
    failure_path: str,
    action_records: List[Dict[str, Any]],
    client: OpenAIClient,
    success_indicator: SuccessIndicatorConfig,
    verify_wait_s: float,
    wait_for_step_training: Callable[[int, str], bool],
    record_action: Callable[[str, Dict[str, Any], Optional[Dict[str, Any]]], None],
    xform: CoordinateTransform,
    arm_commit: bool,
    confirm_token: str,
    pre_click_sleep_s: float,
    pre_type_sleep_s: float,
    post_type_sleep_s: float,
    post_action_sleep_s: float,
    learn_from_vision: bool,
    site_hints: Dict[str, Any],
    site_hints_path: str,
    hover_required: bool,
    arm_timeout_steps: int,
    ensure_manual_capture: Callable[[Page], None],
    handle_manual_clicks: Callable[[int], bool],
    task_prompt: Optional[str] = None,
    verify_guard_min_confidence: float = 0.0,
) -> RunOutcome:
    try:
        for step in range(1, max_steps + 1):
            step_t0 = time.perf_counter()
            state.page = maybe_switch_to_new_tab(context, state.page, verbose=verbose)

            ensure_manual_capture(state.page)

            if state.armed is not None and (step - state.armed.armed_step) > int(
                arm_timeout_steps
            ):
                if verbose:
                    _log_info(
                        f"[arm] Expired armed click from step {state.armed.armed_step}"
                    )
                state.armed = None
                state.armed_notice = ""

            if handle_manual_clicks(step):
                pass

            pre_path = maybe_save_agent_view(
                enable_agent_view, state.page, agent_view_dir, step, "llm_pre"
            )
            if verbose:
                _log_info(f"\n=== STEP {step}/{max_steps} ===")
                if step == 1:
                    _log_info(f"Using model={model} max_tokens={effective_max_tokens}")
                    if (
                        model_viewport.width != viewport.width
                        or model_viewport.height != viewport.height
                    ):
                        _log_info(
                            f"[cost] model screenshots downscaled: actual={viewport.width}x{viewport.height} -> model={model_viewport.width}x{model_viewport.height}"
                        )
                _log_info(f"[agent_view] pre: {pre_path}")

            shot_t0 = time.perf_counter()
            png_bytes_model = capture_model_screenshot_png(
                state.page,
                actual_w=viewport.width,
                actual_h=viewport.height,
                model_w=model_viewport.width,
                model_h=model_viewport.height,
            )
            png_bytes_model = _overlay_grid_on_png_bytes(png_bytes_model, grid_px=80)
            if post_shot_sleep_s:
                time.sleep(max(0.0, float(post_shot_sleep_s)))
            _log_timing(
                f"llm.step_{step}.screenshot_prepare",
                time.perf_counter() - shot_t0,
                verbose=verbose,
                warn_threshold_s=DEFAULT_TIMING_WARN_S,
            )

            step_prompt = build_step_prompt(
                step, state.last_result_text, state.armed_notice
            )
            input_items = [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": step_prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/png;base64,{b64_png(png_bytes_model)}",
                        },
                    ],
                }
            ]

            resp = call_openai(input_items, None)
            if verbose:
                print_usage_tokens(resp)

            assistant_text = extract_openai_response_text(resp)
            if verbose and assistant_text:
                _log_info(_redact_secret_text(assistant_text, password))
            if assistant_text:
                add_history(f"LLM: {assistant_text.strip()[:200]}")
            else:
                output_types = extract_openai_output_types(resp)
                reasoning_only = bool(output_types) and all(
                    t == "reasoning" for t in output_types
                )
                if reasoning_only and str(model).lower().startswith("gpt-5"):
                    retry_tokens = min(
                        2048,
                        max(
                            int(effective_max_tokens) + 256,
                            int(effective_max_tokens) * 2,
                        ),
                    )
                    if verbose:
                        _log_info(
                            "WARN: GPT-5 returned reasoning-only output; retrying with higher max_output_tokens."
                        )
                    resp_retry = call_openai(
                        input_items,
                        None,
                        max_output_tokens_override=retry_tokens,
                        reasoning_effort_override="low",
                    )
                    if verbose:
                        print_usage_tokens(resp_retry)
                    assistant_text = extract_openai_response_text(resp_retry)
                    resp = resp_retry
                    if assistant_text:
                        add_history(f"LLM: {assistant_text.strip()[:200]}")
                    else:
                        state.last_result_text = "ERROR: Model returned no text output."
                        _log_info(state.last_result_text)
                        if verbose:
                            _log_info(debug_openai_response_summary(resp))
                        add_history(state.last_result_text)
                        continue
                else:
                    state.last_result_text = "ERROR: Model returned no text output."
                    _log_info(state.last_result_text)
                    if verbose:
                        _log_info(debug_openai_response_summary(resp))
                    add_history(state.last_result_text)
                    continue

            resp_state = _handle_step_response_content(
                assistant_text=assistant_text or "",
                context=context,
                page=state.page,
                step=step,
                step_t0=step_t0,
                verbose=verbose,
                defer_final=defer_final,
                enable_agent_view=enable_agent_view,
                agent_view_dir=agent_view_dir,
                last_mark_points_actual=state.last_mark_points_actual,
                x_size_px=x_size_px,
                x_thickness_px=x_thickness_px,
                success_path=success_path,
                failure_path=failure_path,
                password=password,
                action_records=action_records,
                add_history=add_history,
                last_result_text=state.last_result_text,
                final_state=final_state,
            )
            state.page = resp_state.page
            state.last_result_text = resp_state.last_result_text
            if resp_state.should_continue:
                continue
            if resp_state.outcome is not None:
                return resp_state.outcome
            data = resp_state.data

            if success_indicator.type == SuccessIndicatorType.VISUAL_LLM:
                verify_state = _handle_verify_guard(
                    data=data,
                    client=client,
                    model=model,
                    context=context,
                    page=state.page,
                    step=step,
                    step_t0=step_t0,
                    success_criteria=success_indicator.value,
                    viewport=viewport,
                    model_viewport=model_viewport,
                    verify_wait_s=verify_wait_s,
                    verbose=verbose,
                    enable_agent_view=enable_agent_view,
                    agent_view_dir=agent_view_dir,
                    last_mark_points_actual=state.last_mark_points_actual,
                    x_size_px=x_size_px,
                    x_thickness_px=x_thickness_px,
                    defer_final=defer_final,
                    success_path=success_path,
                    failure_path=failure_path,
                    action_records=action_records,
                    add_history=add_history,
                    last_result_text=state.last_result_text,
                    final_state=final_state,
                    task_prompt=task_prompt,
                    verify_guard_min_confidence=verify_guard_min_confidence,
                )
                state.page = verify_state.page
                state.last_result_text = verify_state.last_result_text
                if verify_state.should_continue:
                    continue
                if verify_state.outcome is not None:
                    return verify_state.outcome

            action = ""
            action_args: Dict[str, Any] = {}
            why = ""
            state.armed_notice = ""

            prep = _prepare_step_action(
                data=data,
                password=password,
                verbose=verbose,
                step=step,
                add_history=add_history,
                wait_for_step_training=wait_for_step_training,
            )
            action = prep.action
            action_args = prep.action_args
            why = prep.why
            if prep.last_result_text:
                state.last_result_text = prep.last_result_text
            if prep.should_continue:
                continue

            try:
                if action == "screenshot":
                    record_action(
                        "screenshot", action_args, {"ok": True, "action": "screenshot"}
                    )
                    state.last_result_text = "Screenshot captured."
                    add_history(f"{action}: {state.last_result_text}")
                    continue

                marks_actual = (
                    extract_action_points_for_marking(action, action_args, xform)
                    if action in CLICKLIKE_ACTIONS
                    else []
                )
                gate_state = _handle_arm_commit_gate(
                    arm_commit=arm_commit,
                    action=action,
                    marks_actual=marks_actual,
                    armed=state.armed,
                    why=why,
                    confirm_token=confirm_token,
                    step=step,
                    page=state.page,
                    context=context,
                    action_args=action_args,
                    xform=xform,
                    viewport=viewport,
                    model_viewport=model_viewport,
                    pre_click_sleep_s=pre_click_sleep_s,
                    pre_type_sleep_s=pre_type_sleep_s,
                    learn_from_vision=learn_from_vision,
                    site_hints=site_hints,
                    site_hints_path=site_hints_path,
                    enable_agent_view=enable_agent_view,
                    agent_view_dir=agent_view_dir,
                    x_size_px=x_size_px,
                    x_thickness_px=x_thickness_px,
                    verbose=verbose,
                    input_items=input_items,
                    last_mark_points_actual=state.last_mark_points_actual,
                    add_history=add_history,
                    record_action=record_action,
                    armed_notice=state.armed_notice,
                    last_result_text=state.last_result_text,
                )
                state.page = gate_state.page
                state.armed = gate_state.armed
                state.armed_notice = gate_state.armed_notice
                state.last_result_text = gate_state.last_result_text
                input_items = gate_state.input_items
                state.last_mark_points_actual = gate_state.last_mark_points_actual
                if gate_state.should_continue:
                    continue

                if marks_actual and action in CLICKLIKE_ACTIONS:
                    if hover_required:
                        try:
                            hx, hy = (
                                float(marks_actual[0][0]),
                                float(marks_actual[0][1]),
                            )
                            state.page.mouse.move(hx, hy)
                            record_action(
                                "mouse_move",
                                {"x": hx, "y": hy},
                                {"ok": True, "action": "mouse_move"},
                            )
                        except Exception:
                            pass
                    _ = maybe_save_agent_view(
                        enable_agent_view,
                        state.page,
                        agent_view_dir,
                        step,
                        f"pw_preclick_{action}",
                        mark_points=marks_actual,
                        x_size_px=x_size_px,
                        thickness_px=x_thickness_px,
                    )

                result_dict, action_elapsed_s = _execute_action_with_runtime_controls(
                    state.page,
                    action,
                    action_args,
                    xform,
                    pre_click_sleep_s=pre_click_sleep_s,
                    pre_type_sleep_s=pre_type_sleep_s,
                    post_type_sleep_s=post_type_sleep_s,
                    post_action_sleep_s=post_action_sleep_s,
                    site_hints_for_domain=site_hints.get(
                        normalize_domain(state.page.url), {}
                    ),
                    learn_from_vision=learn_from_vision,
                )
                record_action(action, action_args, result_dict)
                _log_timing(
                    f"llm.step_{step}.action_exec.{action}",
                    action_elapsed_s,
                    verbose=verbose,
                    warn_threshold_s=DEFAULT_TIMING_WARN_S,
                )
                state.page, state.last_mark_points_actual, state.last_result_text = (
                    _post_action_success_bookkeeping(
                        context=context,
                        page=state.page,
                        action=action,
                        result_dict=result_dict,
                        step=step,
                        enable_agent_view=enable_agent_view,
                        agent_view_dir=agent_view_dir,
                        x_size_px=x_size_px,
                        x_thickness_px=x_thickness_px,
                        last_mark_points_actual=state.last_mark_points_actual,
                        fallback_mark_points=None,
                        result_prefix="Executed",
                        add_history=add_history,
                        site_hints=site_hints,
                        site_hints_path=site_hints_path,
                        verbose=verbose,
                    )
                )
                if (
                    success_indicator.type != SuccessIndicatorType.VISUAL_LLM
                    and check_deterministic_success(state.page, success_indicator)
                ):
                    _log_info(
                        f"[deterministic] {success_indicator.type.value} matched: {success_indicator.value!r}"
                    )
                    det_png = state.page.screenshot(
                        type="png", full_page=False, scale="css"
                    )
                    if not defer_final:
                        write_final_screenshot(
                            det_png,
                            verdict="PASS",
                            success_path=success_path,
                            failure_path=failure_path,
                        )
                        _log_final("PASS", final_state)
                    return RunOutcome(
                        verdict="PASS", actions=action_records, error=None
                    )
                _log_timing(
                    f"llm.step_{step}.total",
                    time.perf_counter() - step_t0,
                    verbose=verbose,
                    warn_threshold_s=DEFAULT_TIMING_WARN_S,
                )

            except Exception as e:
                step_exc = _handle_step_action_exception(
                    e=e,
                    action=action,
                    context=context,
                    page=state.page,
                    step=step,
                    step_t0=step_t0,
                    verbose=verbose,
                    defer_final=defer_final,
                    enable_agent_view=enable_agent_view,
                    agent_view_dir=agent_view_dir,
                    success_path=success_path,
                    failure_path=failure_path,
                    add_history=add_history,
                    action_records=action_records,
                    final_state=final_state,
                )
                state.page = step_exc.page
                state.last_result_text = step_exc.last_result_text
                if step_exc.should_continue:
                    continue
                if step_exc.outcome is not None:
                    return step_exc.outcome
                return RunOutcome(verdict="FAIL", actions=action_records, error=str(e))

        return _finalize_timeout_failure(
            context=context,
            page=state.page,
            max_steps=max_steps,
            last_mark_points_actual=state.last_mark_points_actual,
            x_size_px=x_size_px,
            x_thickness_px=x_thickness_px,
            defer_final=defer_final,
            success_path=success_path,
            failure_path=failure_path,
            enable_agent_view=enable_agent_view,
            agent_view_dir=agent_view_dir,
            action_records=action_records,
            verbose=verbose,
            final_state=final_state,
        )
    except Exception as e:
        return _finalize_unhandled_failure(
            e=e,
            context=context,
            page=state.page,
            defer_final=defer_final,
            success_path=success_path,
            failure_path=failure_path,
            enable_agent_view=enable_agent_view,
            agent_view_dir=agent_view_dir,
            action_records=action_records,
            verbose=verbose,
            final_state=final_state,
        )


def _finalize_timeout_failure(
    *,
    context: BrowserContext,
    page: Page,
    max_steps: int,
    last_mark_points_actual: List[Tuple[float, float]],
    x_size_px: int,
    x_thickness_px: int,
    defer_final: bool,
    success_path: str,
    failure_path: str,
    enable_agent_view: bool,
    agent_view_dir: str,
    action_records: List[Dict[str, Any]],
    verbose: bool,
    final_state: FinalTokenState,
) -> RunOutcome:
    page = maybe_switch_to_new_tab(context, page, verbose=verbose)
    png = page.screenshot(type="png", full_page=False, scale="css")
    if last_mark_points_actual:
        png = _draw_red_x_on_png_bytes(
            png,
            last_mark_points_actual,
            x_size_px=x_size_px,
            thickness_px=x_thickness_px,
        )
    shot = None
    if not defer_final:
        shot = write_final_screenshot(
            png,
            verdict="FAIL",
            success_path=success_path,
            failure_path=failure_path,
        )
    _ = maybe_save_agent_view(
        enable_agent_view,
        page,
        agent_view_dir,
        max_steps,
        "llm_timeout",
        mark_points=last_mark_points_actual if last_mark_points_actual else None,
        x_size_px=x_size_px,
        thickness_px=x_thickness_px,
    )
    _log_info(f"\nFAILED: reached max_steps={max_steps} without a FINAL verdict.")
    if not defer_final:
        _log_final("FAIL", final_state)
    if shot:
        _log_info(f"Saved failure screenshot: {shot}")
    return RunOutcome(verdict="FAIL", actions=action_records, error="max_steps")


def _finalize_unhandled_failure(
    *,
    e: Exception,
    context: BrowserContext,
    page: Page,
    defer_final: bool,
    success_path: str,
    failure_path: str,
    enable_agent_view: bool,
    agent_view_dir: str,
    action_records: List[Dict[str, Any]],
    verbose: bool,
    final_state: FinalTokenState,
) -> RunOutcome:
    page = maybe_switch_to_new_tab(context, page, verbose=verbose)
    png = page.screenshot(type="png", full_page=False, scale="css")
    shot = None
    if not defer_final:
        shot = write_final_screenshot(
            png,
            verdict="FAIL",
            success_path=success_path,
            failure_path=failure_path,
        )
    _ = maybe_save_agent_view(enable_agent_view, page, agent_view_dir, 0, "unhandled")
    _log_info(f"\nUNHANDLED ERROR: {e}")
    if not defer_final:
        _log_final("FAIL", final_state)
    if shot:
        _log_info(f"Saved failure screenshot: {shot}")
    return RunOutcome(verdict="FAIL", actions=action_records, error=str(e))


class _TemplateVars(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _render_template(value: Any, variables: Dict[str, Any]) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return value.format_map(_TemplateVars(variables))
    except Exception:
        return value


def _redact_step_for_log(step: Dict[str, Any], secret: Optional[str]) -> Dict[str, Any]:
    if not secret:
        return step
    redacted: Dict[str, Any] = {}
    for k, v in step.items():
        if isinstance(v, str):
            redacted[k] = _redact_secret_text(v, secret)
        elif isinstance(v, list):
            redacted[k] = [
                _redact_secret_text(i, secret) if isinstance(i, str) else i for i in v
            ]
        else:
            redacted[k] = v
    return redacted


def _locator_from_step(page: Page, step: Dict[str, Any]):
    selector = step.get("selector")
    if selector:
        return page.locator(str(selector))
    role = step.get("role")
    name = step.get("name")
    if role:
        role_name = cast(Any, str(role))
        if name:
            return page.get_by_role(role_name, name=str(name))
        return page.get_by_role(role_name)
    target_text = step.get("target_text")
    if target_text:
        exact = bool(step.get("exact", False))
        return page.get_by_text(str(target_text), exact=exact)
    return None


def execute_model_function(
    page: Page,
    func: Dict[str, Any],
    variables: Dict[str, Any],
    *,
    verbose: bool,
    pre_type_sleep_s: float,
    post_type_sleep_s: float,
    post_action_sleep_s: float,
    enable_agent_view: bool,
    agent_view_dir: str,
    x_size_px: int,
    x_thickness_px: int,
) -> Tuple[bool, Optional[str], Page]:
    name = func.get("name", "<unnamed>")
    steps = func.get("steps", [])
    function_t0 = time.perf_counter()
    if verbose:
        _log_info(f"[playwright] Function: {name} ({len(steps)} steps)")
    if not isinstance(steps, list):
        _increment_function_count(func, "fail_count")
        return False, "steps_not_a_list", page
    for idx, raw_step in enumerate(steps, start=1):
        action_t0 = time.perf_counter()
        if not isinstance(raw_step, dict):
            _increment_function_count(func, "fail_count")
            return False, f"invalid_step_{idx}", page
        step = {k: _render_template(v, variables) for k, v in raw_step.items()}
        action = str(step.get("action", "")).lower().strip()
        if verbose:
            step_log = _redact_step_for_log(step, variables.get("password"))
            _log_info(f"[playwright] Action {idx}: action={action} data={step_log}")
        _ = maybe_save_agent_view(
            enable_agent_view,
            page,
            agent_view_dir,
            idx,
            f"pw_{name}_{idx:02d}_pre",
            x_size_px=x_size_px,
            thickness_px=x_thickness_px,
        )
        try:
            if action in ("click", "left_click"):
                coords = step.get("coordinates")
                if coords and isinstance(coords, list) and len(coords) == 2:
                    if verbose:
                        _log_info(f"[playwright] click coordinates={coords}")
                    page.mouse.click(float(coords[0]), float(coords[1]), button="left")
                else:
                    loc = _locator_from_step(page, step)
                    if loc is None:
                        raise ValueError("missing_locator")
                    if verbose:
                        _log_info("[playwright] click locator=first")
                    loc.first.click(timeout=10000)
            elif action == "right_click":
                coords = step.get("coordinates")
                if coords and isinstance(coords, list) and len(coords) == 2:
                    if verbose:
                        _log_info(f"[playwright] right_click coordinates={coords}")
                    page.mouse.click(float(coords[0]), float(coords[1]), button="right")
                else:
                    loc = _locator_from_step(page, step)
                    if loc is None:
                        raise ValueError("missing_locator")
                    if verbose:
                        _log_info("[playwright] right_click locator=first")
                    loc.first.click(timeout=10000, button="right")
            elif action == "double_click":
                loc = _locator_from_step(page, step)
                if loc is None:
                    raise ValueError("missing_locator")
                if verbose:
                    _log_info("[playwright] double_click locator=first")
                loc.first.dblclick(timeout=10000)
            elif action == "mouse_move":
                coords = step.get("coordinates")
                if coords and isinstance(coords, list) and len(coords) == 2:
                    if verbose:
                        _log_info(f"[playwright] mouse_move coordinates={coords}")
                    page.mouse.move(float(coords[0]), float(coords[1]))
                else:
                    loc = _locator_from_step(page, step)
                    if loc is None:
                        raise ValueError("missing_locator")
                    if verbose:
                        _log_info("[playwright] mouse_move locator=first")
                    loc.first.hover(timeout=10000)
            elif action == "left_click_drag":
                start = step.get("start_coordinate") or step.get("start")
                end = step.get("end_coordinate") or step.get("end")
                if (
                    not isinstance(start, list)
                    or not isinstance(end, list)
                    or len(start) != 2
                    or len(end) != 2
                ):
                    raise ValueError("missing_drag_coordinates")
                if verbose:
                    _log_info(f"[playwright] left_click_drag start={start} end={end}")
                page.mouse.move(float(start[0]), float(start[1]))
                page.mouse.down(button="left")
                page.mouse.move(float(end[0]), float(end[1]))
                page.mouse.up(button="left")
            elif action == "type":
                text = str(step.get("text", ""))
                if pre_type_sleep_s:
                    time.sleep(max(0.0, float(pre_type_sleep_s)))
                loc = _locator_from_step(page, step)
                if loc is None:
                    if verbose:
                        _log_info(f"[playwright] type keypress text_len={len(text)}")
                    ok = False
                    observed = ""
                    for attempt in range(2):
                        ok, observed = _type_and_verify_active_element(
                            page, text, retries=0
                        )
                        if ok:
                            break
                        if attempt == 0:
                            time.sleep(0.5)
                    if not ok:
                        raise ValueError(
                            f"typed_value_mismatch_active observed={observed!r} expected={text!r}"
                        )
                else:
                    if verbose:
                        _log_info(
                            f"[playwright] type verify text_len={len(text)} locator=first"
                        )
                    ok = False
                    observed = None
                    method = "fill"
                    for attempt in range(2):
                        ok, observed, method = _type_and_verify_locator(
                            loc.first, text, retries=0
                        )
                        if ok:
                            break
                        if attempt == 0:
                            time.sleep(0.5)
                    if not ok:
                        raise ValueError(
                            f"typed_value_mismatch (method={method}) observed={observed!r} expected={text!r}"
                        )
                if post_type_sleep_s:
                    time.sleep(max(0.0, float(post_type_sleep_s)))
            elif action in ("press", "key"):
                key = str(step.get("key", step.get("text", "")))
                if not key:
                    raise ValueError("missing_key")
                normalized = normalize_playwright_key_combo(key)
                if verbose:
                    _log_info(f"[playwright] press key={normalized}")
                page.keyboard.press(normalized)
            elif action == "wait":
                duration = float(step.get("duration", 0.5))
                if verbose:
                    _log_info(f"[playwright] wait duration={duration}")
                time.sleep(clamp(duration, 0.05, 10.0))
            elif action == "goto":
                url = str(step.get("url", ""))
                if not url:
                    raise ValueError("missing_url")
                if verbose:
                    _log_info(f"[playwright] goto url={url}")
                page.goto(url, wait_until="domcontentloaded")
            elif action == "reload":
                if verbose:
                    _log_info("[playwright] reload")
                page.reload(wait_until="domcontentloaded")
            elif action == "screenshot":
                if verbose:
                    _log_info("[playwright] screenshot (no-op in replay)")
            else:
                raise ValueError(f"unsupported_action:{action}")
            if action != "wait":
                time.sleep(max(0.0, float(post_action_sleep_s)))
            _ = maybe_save_agent_view(
                enable_agent_view,
                page,
                agent_view_dir,
                idx,
                f"pw_{name}_{idx:02d}_post",
                x_size_px=x_size_px,
                thickness_px=x_thickness_px,
            )
            page = maybe_switch_to_new_tab(page.context, page, verbose=verbose)
            _log_timing(
                f"playwright.action.{name}.step_{idx}.{action or 'unknown'}",
                time.perf_counter() - action_t0,
                verbose=verbose,
                warn_threshold_s=DEFAULT_TIMING_WARN_S,
            )
        except Exception as e:
            _log_timing(
                f"playwright.action.{name}.step_{idx}.{action or 'unknown'}_failed",
                time.perf_counter() - action_t0,
                verbose=True,
                warn_threshold_s=DEFAULT_TIMING_WARN_S,
                extra=f"error={type(e).__name__}",
            )
            _increment_function_count(func, "fail_count")
            return False, f"{name}:step_{idx}:{e}", page
    _increment_function_count(func, "success_count")
    _log_timing(
        f"playwright.function.{name}.total",
        time.perf_counter() - function_t0,
        verbose=verbose,
        warn_threshold_s=DEFAULT_TIMING_WARN_S,
        extra=f"steps={len(steps) if isinstance(steps, list) else 0}",
    )
    return True, None, page


def _dom_hint_to_step(action: str, dom_hint: Dict[str, Any]) -> Dict[str, Any]:
    step = {"action": action}
    hint_type = dom_hint.get("type")
    if hint_type == "selector":
        step["selector"] = str(dom_hint.get("value") or "")
    elif hint_type == "role_name":
        step["role"] = str(dom_hint.get("role") or "")
        step["name"] = str(dom_hint.get("name") or "")
    elif hint_type == "text":
        step["target_text"] = str(dom_hint.get("value") or "")
    return step


def _action_input_from_dom_hint(dom_hint: Dict[str, Any]) -> Dict[str, Any]:
    hint_type = dom_hint.get("type")
    if hint_type == "selector":
        return {"selector": str(dom_hint.get("value") or "")}
    if hint_type == "role_name":
        return {
            "role": str(dom_hint.get("role") or ""),
            "name": str(dom_hint.get("name") or ""),
        }
    if hint_type == "text":
        return {"target_text": str(dom_hint.get("value") or "")}
    return {}


def _clean_dom_text(value: str, limit: int = 80) -> str:
    text = (value or "").strip().replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text)
    if len(text) > limit:
        text = text[:limit].rstrip() + "..."
    return text


def _format_dom_candidate(item: Dict[str, Any]) -> str:
    parts: List[str] = []
    role = _clean_dom_text(str(item.get("role") or ""))
    tag = _clean_dom_text(str(item.get("tag") or ""))
    name = _clean_dom_text(str(item.get("name") or ""))
    placeholder = _clean_dom_text(str(item.get("placeholder") or ""))
    elem_id = _clean_dom_text(str(item.get("id") or ""))
    name_attr = _clean_dom_text(str(item.get("nameAttr") or ""))
    class_name = _clean_dom_text(str(item.get("className") or ""))
    title = _clean_dom_text(str(item.get("title") or ""))
    href = _clean_dom_text(str(item.get("href") or ""), limit=120)
    data_action = _clean_dom_text(str(item.get("dataAction") or ""))
    data_testid = _clean_dom_text(str(item.get("dataTestId") or ""))
    data_test = _clean_dom_text(str(item.get("dataTest") or ""))
    data_qa = _clean_dom_text(str(item.get("dataQa") or ""))

    selector = ""
    if data_testid:
        selector = f'[data-testid="{data_testid}"]'
    elif data_test:
        selector = f'[data-test="{data_test}"]'
    elif data_qa:
        selector = f'[data-qa="{data_qa}"]'
    elif data_action:
        selector = f'[data-action="{data_action}"]'
    elif elem_id:
        selector = f"#{elem_id}"
    elif name_attr:
        selector = f'[name="{name_attr}"]'
    elif placeholder:
        selector = f'[placeholder*="{placeholder[:32]}"]'
    elif href:
        selector = f'[href^="{href}"]'

    if role:
        parts.append(f"role={role}")
    if name:
        parts.append(f'name="{name}"')
    if selector:
        parts.append(f'selector="{selector}"')
    elif tag:
        parts.append(f"tag={tag}")
    if class_name:
        parts.append(f'class~="{class_name}"')
    if title:
        parts.append(f'title="{title}"')
    if href and "href" not in selector:
        parts.append(f'href="{href}"')

    return " ".join(parts).strip()


def _get_dom_candidates(page: Page, max_items: int = 20) -> List[str]:
    try:
        items = page.evaluate(
            """
            (maxItems) => {
              const isVisible = (el) => {
                const style = window.getComputedStyle(el);
                if (!style || style.visibility === 'hidden' || style.display === 'none' || style.opacity === '0') return false;
                const rect = el.getBoundingClientRect();
                if (rect.width < 4 || rect.height < 4) return false;
                if (rect.bottom < 0 || rect.top > window.innerHeight) return false;
                if (rect.right < 0 || rect.left > window.innerWidth) return false;
                return true;
              };
              const scanLimit = Math.max(400, maxItems * 20);
              const candidates = Array.from(document.querySelectorAll(
                "input, textarea, button, select, a, [role='button'], [role='link'], [role='textbox'], [role='searchbox'], [role='combobox'], [data-action], [data-id], .itemAction, [class*='search' i], [class*='icon' i]"
              ));
              const out = [];
              for (const el of candidates) {
                if (!isVisible(el)) continue;
                const attr = (n) => el.getAttribute(n) || "";
                const tag = (el.tagName || "").toLowerCase();
                const text = (el.innerText || el.textContent || "").trim();
                const labelFrom = (node) => {
                  if (!node) return "";
                  const aria = attr("aria-label");
                  if (aria) return aria;
                  const labelledby = attr("aria-labelledby");
                  if (labelledby) {
                    const ids = labelledby.split(/\\s+/).filter(Boolean);
                    const texts = ids.map((id) => {
                      const ref = document.getElementById(id);
                      return ref ? (ref.innerText || ref.textContent || "") : "";
                    }).filter(Boolean);
                    if (texts.length) return texts.join(" ").trim();
                  }
                  const title = attr("title");
                  if (title) return title;
                  const alt = attr("alt");
                  return alt || "";
                };
                const roleAttr = attr("role");
                const role = roleAttr || (tag === "a" ? "link" : (tag === "button" ? "button" : ""));
                const href = tag === "a" ? (el.getAttribute("href") || "") : "";
                let score = 0;
                if (role === "link") score += 4;
                else if (role === "button") score += 3;
                else if (tag === "input" || role === "textbox" || role === "searchbox" || role === "combobox") score += 2;
                if (href) score += 2;
                if (text.length >= 12) score += 1;
                out.push({
                  tag,
                  type: attr("type"),
                  role,
                  name: labelFrom(el) || text || "",
                  placeholder: attr("placeholder"),
                  nameAttr: attr("name"),
                  id: el.id || "",
                  className: el.className ? String(el.className) : "",
                  title: attr("title"),
                  alt: attr("alt"),
                  href,
                  dataAction: attr("data-action"),
                  dataTestId: attr("data-testid"),
                  dataTest: attr("data-test"),
                  dataQa: attr("data-qa"),
                  score,
                });
                if (out.length >= scanLimit) break;
              }
              out.sort((a, b) => (b.score || 0) - (a.score || 0));
              return out.slice(0, maxItems);
            }
            """,
            max_items,
        )
    except Exception:
        return []
    if not isinstance(items, list):
        return []
    lines: List[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        line = _format_dom_candidate(item)
        if line:
            lines.append(line)
    return lines


def _normalize_typed_text(
    value: str,
    username: Optional[str],
    password: Optional[str],
    rand_string: Optional[str] = None,
) -> str:
    if username and value == username:
        return "{username}"
    if password and value == password:
        return "{password}"
    if rand_string and rand_string in value:
        return value.replace(rand_string, "{rand_string}")
    return value


_HREF_ATTR_RE = re.compile(r"\[href=[^\]]+\]")


def _strip_href_from_selector(selector: str) -> str:
    """Remove [href=...] attribute components from a CSS selector.

    href values encode item-specific URLs (e.g. Jellyfin item IDs) that will
    never match a different item, making the saved action non-reusable.  Other
    attributes such as [data-action] and [title] are sufficient for targeting.
    Only strips when meaningful content remains after removal.
    """
    stripped = _HREF_ATTR_RE.sub("", selector).strip()
    return stripped if stripped else selector


def _replace_query_in_steps(steps: List[Any], query: Optional[str]) -> List[Any]:
    if not query:
        return steps
    out: List[Dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            out.append(step)
            continue
        new_step: Dict[str, Any] = {}
        action = str(step.get("action", "")).lower().strip()
        for k, v in step.items():
            if isinstance(v, str):
                # Strip item-specific href components from click selectors first
                if k == "selector" and action in _CLICK_ACTIONS:
                    v = _strip_href_from_selector(v)
                # Replace query value with {query} template (exact or substring)
                if v == query:
                    new_step[k] = "{query}"
                elif query in v:
                    new_step[k] = v.replace(query, "{query}")
                else:
                    new_step[k] = v
            else:
                new_step[k] = v
        out.append(new_step)
    return out


_CLICK_ACTIONS = frozenset(("click", "left_click", "double_click", "right_click"))


def _sanitize_model_steps(raw_steps: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_steps, list):
        return []
    out: List[Dict[str, Any]] = []
    for step in raw_steps:
        candidate = step
        if isinstance(step, str):
            text = step.strip()
            if text.startswith("{") and text.endswith("}"):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        candidate = parsed
                except Exception:
                    candidate = step
        if isinstance(candidate, dict):
            action_value = candidate.get("action")
            if isinstance(action_value, str) and action_value.strip():
                selector_val = candidate.get("selector")
                if selector_val is not None:
                    selector_str = str(selector_val)
                    if not _looks_like_css_selector(selector_str):
                        candidate = dict(candidate)
                        del candidate["selector"]
                        # Plain human text → promote to target_text for get_by_text replay.
                        # Template variables like {selector} are dropped entirely.
                        if selector_str and "{" not in selector_str:
                            candidate.setdefault("target_text", selector_str)
                        # If it's a click with no remaining target, skip the step.
                        if str(action_value).lower().strip() in _CLICK_ACTIONS:
                            has_target = any(
                                candidate.get(k)
                                for k in (
                                    "x",
                                    "y",
                                    "coordinates",
                                    "coordinate",
                                    "selector",
                                    "role",
                                    "name",
                                    "label",
                                    "target_text",
                                )
                            )
                            if not has_target:
                                continue
                # Drop type actions with no text — they can't replay correctly.
                # This lets the caller fall back to the actual recorded steps.
                if str(action_value).lower().strip() == "type":
                    if not str(candidate.get("text", "")).strip():
                        continue
                out.append(candidate)
    return out


def actions_to_model_steps(
    actions: List[Dict[str, Any]],
    *,
    username: Optional[str],
    password: Optional[str],
    prompt: Optional[str] = None,
    rand_string: Optional[str] = None,
) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []
    query = _extract_quoted_value(prompt or "")
    for item in actions:
        action = str(item.get("action", "")).lower().strip()
        result = item.get("result") or {}
        if not isinstance(result, dict) or not result.get("ok"):
            continue
        action_input = item.get("input") or {}

        if action in ("left_click", "double_click", "right_click", "manual_click"):
            dom_hint = result.get("dom_hint") or _extract_dom_hint(action_input)
            step = None
            if dom_hint:
                if action == "left_click":
                    step = _dom_hint_to_step("click", dom_hint)
                elif action == "double_click":
                    step = _dom_hint_to_step("double_click", dom_hint)
                else:
                    step = _dom_hint_to_step("right_click", dom_hint)
            elif (
                action == "manual_click" or not action_input.get("manual")
            ) and isinstance(result.get("actual"), list):
                step_action = (
                    "click"
                    if action == "left_click"
                    else ("double_click" if action == "double_click" else "right_click")
                )
                step = {"action": step_action, "coordinates": result.get("actual")}
            if step:
                steps.append(step)
        if action == "mouse_move":
            dom_hint = _extract_dom_hint(action_input)
            step = None
            if dom_hint:
                step = _dom_hint_to_step("mouse_move", dom_hint)
            elif isinstance(result.get("actual"), list):
                step = {"action": "mouse_move", "coordinates": result.get("actual")}
            if step:
                steps.append(step)
        if action == "left_click_drag":
            start = result.get("actual_start")
            end = result.get("actual_end")
            if (
                isinstance(start, list)
                and isinstance(end, list)
                and len(start) == 2
                and len(end) == 2
            ):
                steps.append({"action": "left_click_drag", "start": start, "end": end})
            continue

        if action == "type":
            dom_hint = result.get("dom_hint") or _extract_dom_hint(action_input)
            step = {"action": "type"}
            if dom_hint:
                step.update(_dom_hint_to_step("type", dom_hint))
            text = str(action_input.get("text", ""))
            step["text"] = _normalize_typed_text(text, username, password, rand_string)
            steps.append(step)
            continue

        if action == "key":
            key_val = (
                action_input.get("text") or action_input.get("key") or result.get("key")
            )
            if key_val:
                steps.append({"action": "press", "key": str(key_val)})
            continue

        if action == "wait":
            duration = action_input.get("duration", result.get("duration", 0.5))
            steps.append({"action": "wait", "duration": duration})
            continue

        if action == "reload":
            steps.append({"action": "reload"})
            continue

    return _replace_query_in_steps(steps, query)


def get_prompt_route(
    model: Dict[str, Any],
    prompt: str,
    functions_list: Optional[List[Dict[str, Any]]] = None,
) -> Optional[List[str]]:
    normalized = _replace_quoted_value(prompt or "", "{query}")
    if functions_list is not None:
        normalized = _normalize_prompt_for_routes(normalized, functions_list)
    routes = model.get("prompt_routes", [])
    if not isinstance(routes, list):
        return None
    for item in routes:
        if not isinstance(item, dict):
            continue
        item_prompt = str(item.get("prompt") or "")
        if item_prompt == prompt or item_prompt == normalized:
            seq = item.get("sequence")
            if isinstance(seq, list):
                return [str(s) for s in seq if s]
            continue
        if functions_list is not None and item_prompt:
            normalized_item = _normalize_prompt_for_routes(item_prompt, functions_list)
            if normalized_item == normalized:
                seq = item.get("sequence")
                if isinstance(seq, list):
                    return [str(s) for s in seq if s]
                continue
    return None


def set_prompt_route(
    model: Dict[str, Any],
    prompt: str,
    sequence: List[str],
    functions_list: Optional[List[Dict[str, Any]]] = None,
) -> None:
    routes = model.setdefault("prompt_routes", [])
    normalized = _replace_quoted_value(prompt or "", "{query}")
    if functions_list is not None:
        normalized = _normalize_prompt_for_routes(normalized, functions_list)
    for item in routes:
        if isinstance(item, dict) and item.get("prompt") in (prompt, normalized):
            item["sequence"] = sequence
            return
    routes.append({"prompt": normalized, "sequence": sequence})


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def pick_function_sequence(
    client: OpenAIClient,
    model_name: str,
    functions_list: List[Dict[str, Any]],
    prompt: str,
    *,
    max_tokens: int = 256,
    extra_note: str = "",
) -> Tuple[List[str], str]:
    if not functions_list:
        return [], "no_functions"

    lines = []
    for f in functions_list:
        name = str(f.get("name", "")).strip()
        desc = str(f.get("description", "")).strip()
        if not name:
            continue
        success_count = int(f.get("success_count", 0) or 0)
        fail_count = int(f.get("fail_count", 0) or 0)
        reliability = _function_reliability(success_count, fail_count)
        sigs = ", ".join(
            _summarize_steps(
                f.get("steps", []) if isinstance(f.get("steps"), list) else [], limit=5
            )
        )
        meta = _format_function_metadata_for_prompt(f)
        if desc:
            lines.append(
                f"- {name} (success={success_count}, fail={fail_count}, reliability={reliability:.2f}): {desc} | steps: {sigs}"
                + (f" | {meta}" if meta else "")
            )
        else:
            lines.append(
                f"- {name} (success={success_count}, fail={fail_count}, reliability={reliability:.2f}) | steps: {sigs}"
                + (f" | {meta}" if meta else "")
            )

    note = f"\nExtra context: {extra_note}\n" if extra_note else ""
    user_text = (
        "Pick the smallest ordered list of function names to accomplish the task.\n"
        'Return JSON: {"sequence": ["Func1", "Func2"], "reason": "..."}\n'
        "Prefer reusing existing functions even if they are not perfect matches, but avoid ones with high fail rates.\n"
        "When multiple functions could work, prefer higher reliability (higher success, lower fail).\n"
        "Prefer chaining atomic functions over choosing a single composite function.\n"
        "If a function has scope=composite and its deprioritize_when list is available, avoid the composite.\n"
        "Avoid validation-only functions (e.g., Check/Verify/Screenshot/Assert/WaitForText). Visual verification happens separately.\n"
        "Never choose functions whose purpose is to validate or confirm success.\n"
        f"Task: {prompt}\n"
        f"{note}"
        "Available functions:\n" + "\n".join(lines)
    )
    resp = client.responses.create(
        model=model_name,
        max_output_tokens=max_tokens,
        input=[
            {"role": "user", "content": [{"type": "input_text", "text": user_text}]}
        ],
    )
    print_usage_tokens(resp)
    text = extract_openai_response_text(resp)
    data = _extract_json_object(text) or {}
    seq = data.get("sequence")
    if isinstance(seq, list):
        clean = [str(s) for s in seq if s]
    else:
        clean = []
    allowed = {str(f.get("name")) for f in functions_list}
    clean = [s for s in clean if s in allowed]
    clean = _expand_composite_sequence(clean, functions_list)
    reason = str(data.get("reason", "")).strip()
    return clean, reason


def select_actions_to_rewrite_with_llm(
    client: OpenAIClient,
    model_name: str,
    manual_actions: List[str],
    functions_list: List[Dict[str, Any]],
    prompt: str,
    success_criteria: str,
    verify_reason: str,
    fallback_steps: List[Dict[str, Any]],
    *,
    max_tokens: int = 512,
    verbose: bool = False,
) -> Tuple[List[str], Optional[float], str]:
    if not manual_actions:
        return [], None, ""
    lines = []
    allowed_map = {_normalize_function_name(a): a for a in manual_actions}
    allowed = {a for a in manual_actions}
    for f in functions_list:
        name = str(f.get("name", "")).strip()
        if not name or name not in allowed:
            continue
        desc = str(f.get("description", "")).strip()
        sigs = ", ".join(
            _summarize_steps(
                f.get("steps", []) if isinstance(f.get("steps"), list) else [], limit=6
            )
        )
        lines.append(
            f"- {name}: {desc} | steps: {sigs}" if desc else f"- {name} | steps: {sigs}"
        )
    if not lines:
        return [], None, ""
    fallback_summary = ", ".join(_summarize_steps(fallback_steps, limit=10))
    user_text = (
        "We ran manual actions and they completed without error, but the final success criteria failed.\n"
        "Select which existing manual actions should be rewritten to align with the successful fallback behavior.\n"
        'Return JSON only: {"rewrite":["action1","action2"],"confidence":0.0,"reason":"..."}\n'
        "Only include actions from the manual list. If none should be rewritten, return an empty list.\n"
        f"Task: {prompt}\n"
        f"Success criteria: {success_criteria}\n"
        f"Failure reason: {verify_reason}\n"
        f"Fallback steps summary: {fallback_summary}\n"
        "Manual actions:\n" + "\n".join(lines)
    )
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "rewrite_actions",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "rewrite": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["rewrite", "confidence", "reason"],
            },
        },
    }
    req: Dict[str, Any] = dict(
        model=model_name,
        max_output_tokens=max_tokens,
        input=[
            {"role": "user", "content": [{"type": "input_text", "text": user_text}]}
        ],
        response_format=response_format,
    )
    effort = (
        normalize_reasoning_effort(model_name, "minimal")
        if str(model_name).lower().startswith("gpt-5")
        else None
    )
    if effort:
        req["reasoning"] = {"effort": effort}

    def _call_selector(req_payload: Dict[str, Any]) -> Any:
        attempts = 0
        while True:
            try:
                return client.responses.create(**req_payload)
            except TypeError as e:
                attempts += 1
                msg = str(e)
                changed = False
                if "response_format" in msg and "response_format" in req_payload:
                    req_payload.pop("response_format", None)
                    changed = True
                if "reasoning" in msg and "reasoning" in req_payload:
                    req_payload.pop("reasoning", None)
                    changed = True
                if not changed or attempts >= 3:
                    raise
            except Exception as e:
                msg = str(e)
                if "reasoning.effort" in msg and "reasoning" in req_payload:
                    req_payload["reasoning"] = {"effort": "low"}
                    continue
                raise

    resp = _call_selector(req)
    print_usage_tokens(resp)
    text = extract_openai_response_text(resp)
    if not text:
        output_types = extract_openai_output_types(resp)
        reasoning_only = bool(output_types) and all(
            t == "reasoning" for t in output_types
        )
        if reasoning_only:
            retry_req = dict(req)
            retry_req.pop("response_format", None)
            retry_req.pop("reasoning", None)
            retry_req["max_output_tokens"] = max(256, int(max_tokens))
            # Force a minimal JSON response when the model emits reasoning-only.
            retry_req["input"] = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_text
                            + '\nReturn JSON only: {"rewrite":[],"confidence":0.0,"reason":""}',
                        }
                    ],
                }
            ]
            resp_retry = _call_selector(retry_req)
            print_usage_tokens(resp_retry)
            text = extract_openai_response_text(resp_retry)
            resp = resp_retry
    if not text:
        # Fallback to a more JSON-reliable model if the current model returns reasoning-only.
        if (
            DEFAULT_MODEL
            and str(DEFAULT_MODEL).lower() != str(model_name).lower()
            and infer_model_provider(DEFAULT_MODEL) == infer_model_provider(model_name)
        ):
            fallback_req = {
                "model": DEFAULT_MODEL,
                "max_output_tokens": max(256, int(max_tokens)),
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": user_text
                                + '\nReturn JSON only: {"rewrite":[],"confidence":0.0,"reason":""}',
                            }
                        ],
                    }
                ],
            }
            resp_fallback = _call_selector(fallback_req)
            print_usage_tokens(resp_fallback)
            text = extract_openai_response_text(resp_fallback)
            resp = resp_fallback
            if verbose:
                _log_info(
                    f"[LLM] Rewrite selector fallback model used: {DEFAULT_MODEL}"
                )
    if not text:
        text = ""
    data = _extract_json_object(text) or {}
    if not data and text and text.strip().startswith("{"):
        try:
            data = json.loads(text)
        except Exception:
            data = {}
    if verbose:
        _log_info(f"[LLM] Rewrite selector raw: {text}")
        _log_info(f"[LLM] Rewrite selector parsed: {data}")
    raw = data.get("rewrite")
    if not isinstance(raw, list):
        raw = []
    rewrite = []
    for x in raw:
        key = _normalize_function_name(str(x))
        actual = allowed_map.get(key)
        if actual:
            rewrite.append(actual)
    conf_raw = data.get("confidence")
    confidence = None
    if isinstance(conf_raw, (int, float)):
        confidence = clamp(float(conf_raw), 0.0, 1.0)
    elif isinstance(conf_raw, str):
        try:
            confidence = clamp(float(conf_raw), 0.0, 1.0)
        except Exception:
            confidence = None
    reason = str(data.get("reason", "")).strip()
    return rewrite, confidence, reason


def _format_action_history_for_verify(
    action_records: List[Dict[str, Any]],
) -> str:
    """Convert action_records to a compact human-readable list for the verify prompt."""
    if not action_records:
        return "(none)"
    lines = []
    for i, rec in enumerate(action_records, 1):
        action = str(rec.get("action", "")).strip()
        inp = rec.get("input") or {}
        if action == "type":
            sel = inp.get("selector", "")
            text = inp.get("text", "")
            lines.append(f"{i}. type({sel!r}, {text!r})")
        elif action == "click":
            sel = inp.get("selector", "")
            lines.append(f"{i}. click({sel!r})")
        elif action in ("reload", "refresh"):
            lines.append(f"{i}. reload()")
        elif action == "navigate":
            url = inp.get("url", "")
            lines.append(f"{i}. navigate({url!r})")
        elif action:
            detail = ", ".join(f"{k}={v!r}" for k, v in inp.items() if v is not None)
            lines.append(f"{i}. {action}({detail})")
    return "\n".join(lines)


def verify_success_with_llm(
    client: OpenAIClient,
    model_name: str,
    page: Page,
    success_criteria: str,
    *,
    viewport: Viewport,
    model_viewport: Viewport,
    verify_wait_s: float,
    png_bytes: Optional[bytes] = None,
    task_prompt: Optional[str] = None,
    action_history: Optional[str] = None,
) -> Tuple[bool, str, str, Optional[float], bytes]:
    time.sleep(max(0.0, float(verify_wait_s)))
    if png_bytes is None:
        png_bytes = capture_model_screenshot_png(
            page,
            actual_w=viewport.width,
            actual_h=viewport.height,
            model_w=model_viewport.width,
            model_h=model_viewport.height,
        )
    if task_prompt and action_history is not None:
        prompt = (
            "Check if the success criteria is met in the screenshot.\n"
            'Reply with JSON: {"verdict":"PASS|FAIL","why":"short reason","confidence":0.0}\n'
            "confidence is 0.0 to 1.0.\n\n"
            f"Full task:\n{task_prompt}\n\n"
            "Actions executed so far (this is the complete and exhaustive list — "
            "do not assume any action occurred that is not listed here):\n"
            f"{action_history}\n\n"
            f"Criteria: {success_criteria}"
        )
    else:
        prompt = (
            "Check if the success criteria is met in the screenshot.\n"
            'Reply with JSON: {"verdict":"PASS|FAIL","why":"short reason","confidence":0.0}\n'
            "confidence is 0.0 to 1.0.\n"
            f"Criteria: {success_criteria}"
        )
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "verify_success",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
                    "why": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["verdict", "why", "confidence"],
            },
        },
    }

    base_tokens = 160 if str(model_name).lower().startswith("gpt-5") else 64

    def _call_verify(max_tokens: int) -> Any:
        req: Dict[str, Any] = dict(
            model=model_name,
            max_output_tokens=int(max_tokens),
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/png;base64,{b64_png(png_bytes)}",
                        },
                    ],
                }
            ],
            response_format=response_format,
        )
        effort = (
            normalize_reasoning_effort(model_name, "minimal")
            if str(model_name).lower().startswith("gpt-5")
            else None
        )
        if effort:
            req["reasoning"] = {"effort": effort}
        attempts = 0
        effort_retry_done = False
        while True:
            req_t0 = time.perf_counter()
            try:
                resp = client.responses.create(**req)
                _log_timing(
                    "llm.verify.responses.create",
                    time.perf_counter() - req_t0,
                    warn_threshold_s=DEFAULT_TIMING_WARN_S,
                    extra=f"attempt={attempts + 1} model={model_name} max_output_tokens={int(max_tokens)}",
                )
                return resp
            except TypeError as e:
                attempts += 1
                msg = str(e)
                changed = False
                if "response_format" in msg and "response_format" in req:
                    req.pop("response_format", None)
                    changed = True
                if "reasoning" in msg and "reasoning" in req:
                    req.pop("reasoning", None)
                    changed = True
                if not changed or attempts >= 3:
                    raise
            except Exception as e:
                msg = str(e)
                if (
                    not effort_retry_done
                    and "reasoning.effort" in msg
                    and "Unsupported value" in msg
                    and "reasoning" in req
                ):
                    req["reasoning"] = {"effort": "low"}
                    effort_retry_done = True
                    continue
                raise

    resp = _call_verify(base_tokens)
    print_usage_tokens(resp)
    text = extract_openai_response_text(resp)
    if not text:
        output_types = extract_openai_output_types(resp)
        reasoning_only = bool(output_types) and all(
            t == "reasoning" for t in output_types
        )
        if reasoning_only and str(model_name).lower().startswith("gpt-5"):
            resp_retry = _call_verify(min(512, base_tokens * 2))
            print_usage_tokens(resp_retry)
            text = extract_openai_response_text(resp_retry)
            resp = resp_retry
    data = _extract_json_object(text) or {}
    verdict = str(data.get("verdict", "")).upper()
    why = str(data.get("why", "")).strip()
    conf_raw = data.get("confidence")
    confidence = None
    if isinstance(conf_raw, (int, float)):
        confidence = float(conf_raw)
    elif isinstance(conf_raw, str):
        try:
            confidence = float(conf_raw)
        except Exception:
            confidence = None
    if verdict not in ("PASS", "FAIL"):
        m = re.search(r"\b(PASS|FAIL)\b", text, re.IGNORECASE)
        verdict = m.group(1).upper() if m else "UNKNOWN"
    if not why:
        why = "No reason provided."
    if confidence is not None:
        confidence = clamp(confidence, 0.0, 1.0)
    return verdict == "PASS", verdict, why, confidence, png_bytes


def write_final_screenshot(
    png_bytes: bytes,
    *,
    verdict: str,
    success_path: str,
    failure_path: str,
) -> str:
    target = success_path if verdict == "PASS" else failure_path
    shot = ensure_dir_for_file(os.path.abspath(target))
    with open(shot, "wb") as f:
        f.write(png_bytes)
    return shot


def split_steps_with_llm(
    client: OpenAIClient,
    model_name: str,
    steps: List[Dict[str, Any]],
    prompt: str,
    *,
    cap: int = MAX_SUBACTIONS_PER_FUNCTION,
    max_tokens: int = 512,
) -> Optional[Dict[str, Any]]:
    payload = json.dumps(steps, ensure_ascii=True)
    query = _extract_quoted_value(prompt or "")
    user_text = (
        "You are given a list of Playwright-style steps for a task.\n"
        "If it can be split into reusable functions (like Login), do so.\n"
        "Prefer creating small, atomic functions that can be chained together.\n"
        "Only create composite functions if the steps are inseparable.\n"
        f"Hard cap: at most {cap} actions per function (count click/type/key/press/wait/scroll; ignore screenshot).\n"
        "Return JSON only:\n"
        '{"functions": [{"name":"...","description":"...","steps": [...],'
        ' "preconditions":[...], "postconditions":[...], "scope":"atomic|composite",'
        ' "composes":[...], "avoid_with":[...]}],'
        ' "sequence": ["FuncA","FuncB"]}\n'
        "IMPORTANT: Do NOT add validation/check/screenshot/verify steps. Visual verification is handled separately at the end via LLM + screenshot.\n"
        "Do NOT create functions whose purpose is validation or confirmation (e.g., CheckImage, Verify, TakeScreenshot, CheckVisibility, Assert, WaitForText).\n"
        "Never include steps that replace or supplement the final image-based validation.\n"
        "If the prompt includes a specific entity in quotes, replace it with {query} in steps.\n"
        "Keep function names very short (1-3 words), lowercase, snake_case. Prefer generic verbs (e.g., login, search_media, open_details).\n"
        f"Original prompt: {prompt}\n"
        f"Steps: {payload}"
    )
    resp = client.responses.create(
        model=model_name,
        max_output_tokens=max_tokens,
        input=[
            {"role": "user", "content": [{"type": "input_text", "text": user_text}]}
        ],
    )
    print_usage_tokens(resp)
    text = extract_openai_response_text(resp)
    data = _extract_json_object(text)
    if not isinstance(data, dict):
        return None
    funcs = data.get("functions")
    seq = data.get("sequence")
    if not isinstance(funcs, list) or not isinstance(seq, list):
        return None
    for f in funcs:
        if not isinstance(f, dict):
            continue
        cleaned = _sanitize_model_steps(f.get("steps"))
        if query:
            cleaned = _replace_query_in_steps(cleaned, query)
        f["steps"] = cleaned
    return {"functions": funcs, "sequence": [str(s) for s in seq if s]}


def resummarize_steps_with_llm(
    client: OpenAIClient,
    model_name: str,
    steps: List[Dict[str, Any]],
    prompt: str,
    *,
    max_tokens: int = 384,
    verbose: bool = False,
) -> Optional[List[Dict[str, Any]]]:
    if not steps:
        return None
    payload = json.dumps(steps, ensure_ascii=True)
    user_text = (
        "You are given a list of Playwright-style steps that were actually executed.\n"
        "Produce a reduced list that keeps only the steps necessary to achieve the final successful outcome.\n"
        "Do NOT add new steps. Do NOT reorder steps. Only remove redundant or clearly ineffective steps.\n"
        "Use any Impact=HELPED|NO_EFFECT|REGRESSED tags found in WHY fields to guide pruning: remove NO_EFFECT/REGRESSED when safe.\n"
        "If unsure, return the original list unchanged.\n"
        'Return JSON only: {"steps": [...]}.\n'
        f"Original prompt: {prompt}\n"
        f"Steps: {payload}"
    )
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "resummarized_steps",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {"type": "object", "additionalProperties": True},
                    },
                },
                "required": ["steps"],
            },
        },
    }
    req = dict(
        model=model_name,
        max_output_tokens=max_tokens,
        input=[
            {"role": "user", "content": [{"type": "input_text", "text": user_text}]}
        ],
    )
    if response_format:
        req["response_format"] = response_format
    try:
        resp = client.responses.create(**cast(Any, req))
    except TypeError as e:
        msg = str(e)
        if "response_format" in msg and "response_format" in req:
            req.pop("response_format", None)
            resp = client.responses.create(**cast(Any, req))
        else:
            raise
    print_usage_tokens(resp)
    text = extract_openai_response_text(resp)
    data = _extract_json_object(text)
    if not isinstance(data, dict):
        if verbose:
            raw = text or ""
            snippet = raw if len(raw) <= 2000 else f"{raw[:2000]}... [truncated]"
            _log_info(f"[LLM] Resummarize raw response (invalid JSON): {snippet}")
        return None
    new_steps = data.get("steps")
    if not isinstance(new_steps, list):
        if verbose:
            raw = text or ""
            snippet = raw if len(raw) <= 2000 else f"{raw[:2000]}... [truncated]"
            _log_info(f"[LLM] Resummarize raw response (missing steps): {snippet}")
        return None
    cleaned: List[Dict[str, Any]] = []
    for step in new_steps:
        if isinstance(step, dict) and step.get("action"):
            cleaned.append(step)
    return cleaned or None


def split_steps_with_reuse_llm(
    client: OpenAIClient,
    model_name: str,
    steps: List[Dict[str, Any]],
    prompt: str,
    functions_list: List[Dict[str, Any]],
    *,
    cap: int = MAX_SUBACTIONS_PER_FUNCTION,
    max_tokens: int = 768,
) -> Optional[Dict[str, Any]]:
    if not functions_list:
        return None
    payload = json.dumps(steps, ensure_ascii=True)
    query = _extract_quoted_value(prompt or "")
    lines = []
    for f in functions_list:
        name = str(f.get("name", "")).strip()
        if not name:
            continue
        desc = str(f.get("description", "")).strip()
        success_count = int(f.get("success_count", 0) or 0)
        fail_count = int(f.get("fail_count", 0) or 0)
        reliability = _function_reliability(success_count, fail_count)
        sigs = ", ".join(
            _summarize_steps(
                f.get("steps", []) if isinstance(f.get("steps"), list) else [], limit=6
            )
        )
        meta = _format_function_metadata_for_prompt(f)
        if desc:
            lines.append(
                f"- {name} (success={success_count}, fail={fail_count}, reliability={reliability:.2f}): {desc} | steps: {sigs}"
                + (f" | {meta}" if meta else "")
            )
        else:
            lines.append(
                f"- {name} (success={success_count}, fail={fail_count}, reliability={reliability:.2f}) | steps: {sigs}"
                + (f" | {meta}" if meta else "")
            )

    user_text = (
        "You are given a list of Playwright-style steps for a task.\n"
        "Segment the steps into an ordered sequence of existing functions and any needed new functions.\n"
        "Prefer reusing existing functions even if they are not perfect matches, but avoid ones with high fail rates.\n"
        "When multiple functions could work, prefer higher reliability (higher success, lower fail).\n"
        "Prefer chaining atomic functions over choosing a single composite function.\n"
        f"Hard cap: at most {cap} actions per function (count click/type/key/press/wait/scroll; ignore screenshot).\n"
        "Segments must be contiguous and cover all steps in order.\n"
        "Return JSON only:\n"
        '{"sequence": [{"type":"existing|new","name":"..."}, ...],'
        ' "new_functions": [{"name":"...","description":"...","steps":[...],'
        ' "preconditions":[...], "postconditions":[...], "scope":"atomic|composite",'
        ' "composes":[...], "avoid_with":[...]}],'
        ' "reason":"..."}\n'
        "IMPORTANT: Do NOT add validation/check/screenshot/verify steps. Visual verification is handled separately at the end via LLM + screenshot.\n"
        "Do NOT create functions whose purpose is validation or confirmation (e.g., CheckImage, Verify, TakeScreenshot, CheckVisibility, Assert, WaitForText).\n"
        "Never include steps that replace or supplement the final image-based validation.\n"
        "Use exact existing function names when reusing.\n"
        "If the prompt includes a specific entity in quotes, replace it with {query} in steps.\n"
        "For any new function names, keep them very short (1-3 words), lowercase, snake_case. Prefer generic verbs (e.g., login, search_media, open_details).\n"
        f"Original prompt: {prompt}\n"
        "Available functions:\n" + "\n".join(lines) + f"\nSteps: {payload}"
    )
    resp = client.responses.create(
        model=model_name,
        max_output_tokens=max_tokens,
        input=[
            {"role": "user", "content": [{"type": "input_text", "text": user_text}]}
        ],
    )
    print_usage_tokens(resp)
    text = extract_openai_response_text(resp)
    data = _extract_json_object(text)
    if not isinstance(data, dict):
        return None
    seq = data.get("sequence")
    new_funcs = data.get("new_functions")
    if not isinstance(seq, list):
        return None
    if new_funcs is not None and not isinstance(new_funcs, list):
        return None
    if isinstance(new_funcs, list):
        for f in new_funcs:
            if not isinstance(f, dict):
                continue
            cleaned = _sanitize_model_steps(f.get("steps"))
            if query:
                cleaned = _replace_query_in_steps(cleaned, query)
            f["steps"] = cleaned
    return {"sequence": seq, "new_functions": new_funcs or []}


def execute_model_sequence(
    page: Page,
    model_data: Dict[str, Any],
    sequence: List[str],
    variables: Dict[str, Any],
    *,
    verbose: bool,
    pre_type_sleep_s: float,
    post_type_sleep_s: float,
    post_action_sleep_s: float,
    enable_agent_view: bool,
    agent_view_dir: str,
    x_size_px: int,
    x_thickness_px: int,
) -> Tuple[bool, Optional[str], Optional[str], Page]:
    funcs = {
        str(f.get("name")): f
        for f in model_data.get("functions", [])
        if isinstance(f, dict)
    }
    for name in sequence:
        func = funcs.get(name)
        if not func:
            return False, name, "missing_function", page
        ok, err, page = execute_model_function(
            page,
            func,
            variables,
            verbose=verbose,
            pre_type_sleep_s=pre_type_sleep_s,
            post_type_sleep_s=post_type_sleep_s,
            post_action_sleep_s=post_action_sleep_s,
            enable_agent_view=enable_agent_view,
            agent_view_dir=agent_view_dir,
            x_size_px=x_size_px,
            x_thickness_px=x_thickness_px,
        )
        if not ok:
            return False, name, err, page
    return True, None, None, page


def update_or_add_function(
    model_data: Dict[str, Any],
    name: str,
    *,
    description: str,
    steps: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    funcs = model_data.setdefault("functions", [])
    for item in funcs:
        if isinstance(item, dict) and item.get("name") == name:
            item["description"] = description
            item["steps"] = steps
            if metadata:
                for k, v in metadata.items():
                    if v:
                        item[k] = v
            _ensure_function_counts(item)
            return
    funcs.append(
        {
            "name": name,
            "description": description,
            "steps": steps,
            "success_count": 0,
            "fail_count": 0,
            **(metadata or {}),
        }
    )


def add_function_with_subaction_cap(
    model_data: Dict[str, Any],
    base_name: str,
    *,
    description: str,
    steps: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
    cap: int = MAX_SUBACTIONS_PER_FUNCTION,
    force_base_name: bool = False,
    allow_overwrite: bool = False,
    allow_split: bool = True,
) -> List[str]:
    chunks = _split_steps_by_action_cap(steps, cap)
    if not chunks:
        return []
    if len(chunks) > 1 and not allow_split:
        summaries = _summarize_steps(steps, limit=12)
        _log_info(
            f"[playwright] Function '{base_name}' exceeds max subactions ({cap}); "
            f"steps={len(steps)} summaries={summaries}"
        )
        return []
    if len(chunks) == 1:
        name = base_name
        if not force_base_name:
            name = _pick_unique_function_name(model_data, base_name)
        if allow_overwrite:
            name = base_name
        update_or_add_function(
            model_data,
            name,
            description=description,
            steps=chunks[0],
            metadata=metadata,
        )
        return [name]
    names: List[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        if idx == 1 and force_base_name:
            name = base_name
        else:
            suffix = idx if idx > 1 else 1
            candidate = f"{base_name}_{suffix}"
            name = _pick_unique_function_name(model_data, candidate)
        if allow_overwrite and idx == 1:
            name = base_name
        update_or_add_function(
            model_data,
            name,
            description=description,
            steps=chunk,
            metadata=metadata,
        )
        names.append(name)
    return names


def _ensure_function_counts(func: Dict[str, Any]) -> None:
    if not isinstance(func.get("success_count"), int):
        func["success_count"] = 0
    if not isinstance(func.get("fail_count"), int):
        func["fail_count"] = 0


def _increment_function_count(func: Dict[str, Any], key: str) -> None:
    _ensure_function_counts(func)
    func[key] = int(func.get(key, 0)) + 1


def _existing_function_desc(model_data: Dict[str, Any], name: str) -> Optional[str]:
    for item in model_data.get("functions", []):
        if isinstance(item, dict) and item.get("name") == name:
            return str(item.get("description") or "")
    return None


def _pick_unique_function_name(model_data: Dict[str, Any], desired: str) -> str:
    existing = {
        str(f.get("name"))
        for f in model_data.get("functions", [])
        if isinstance(f, dict)
    }
    if desired not in existing:
        return desired
    suffix = 2
    candidate = f"{desired}_{suffix}"
    while candidate in existing:
        suffix += 1
        candidate = f"{desired}_{suffix}"
    return candidate


# -----------------------------
# Arm/Commit state
# -----------------------------


@dataclass
class ArmedClick:
    action: str
    point_actual: Tuple[float, float]  # ACTUAL CSS px
    armed_step: int


@dataclass
class AgentRunContext:
    client: OpenAIClient
    site_hints: Dict[str, Any]
    xform: CoordinateTransform
    effective_max_tokens: int
    history_limit: int
    manual_enabled: bool
    step_training_enabled: bool
    step_training_token: int
    action_records: List[Dict[str, Any]] = field(default_factory=list)
    history_texts: List[str] = field(default_factory=list)


@dataclass
class AgentLoopState:
    page: Page
    last_mark_points_actual: List[Tuple[float, float]]
    armed: Optional["ArmedClick"]
    last_result_text: str
    armed_notice: str


def points_close(
    a: Tuple[float, float], b: Tuple[float, float], tol: float = 0.5
) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


# -----------------------------
# OpenAI loop
# -----------------------------


def build_initial_messages(
    task_prompt: str,
    success_criteria: str,
    confirm_token: str,
    username: Optional[str],
    password: Optional[str],
    *,
    preface_text: Optional[str] = None,
    preface_image_b64: Optional[str] = None,
) -> List[Dict[str, Any]]:
    cred_block = ""
    if username is not None and password is not None:
        cred_block = f"""
<robot_credentials>
username: {username}
password: {password}
</robot_credentials>
""".strip()

    user_text = f"""
You are controlling a real browser page via Playwright, driven by your vision-only instructions.
Do NOT use DOM selectors directly. Provide DOM hints in args when helpful. Do NOT assume success-verify via screenshots.

IMPORTANT LIMITATION:
- Screenshots show only the WEB PAGE viewport, not browser address bar/tabs.
- Do NOT click the address bar. Use in-page UI only.

DOM-FIRST (cost + reliability):
- Prefer DOM hints whenever possible.
- Include DOM hints in the action args:
  role+name or label/aria-label (preferred), then selector (CSS), then target_text.
- For typing into a specific field, include a DOM hint plus text to type.
- If a DOM hint is missing or fails, the system will fall back to vision clicks.
VISION CLICK SNAP:
- For long horizontal elements (search bars, URL fields), clicks may snap to the
  lower-center of the element's bounding box to avoid "too-high" clicks.

Task:
{task_prompt}

{cred_block}

Success criteria:
{success_criteria}

CRITICAL RELIABILITY RULES:
A) If any dropdown/overlay is open (suggestions, cookie prompt, etc), press Escape to close it before clicking elsewhere.
B) Before clicking a search result, hover it (mouse_move) then screenshot to confirm hover highlight, then click.
C) Arm/Commit: If you receive "CLICK PREVIEW (ARMED)" with a red X:
   - If X is correct: repeat SAME coordinate next step AND include token "{confirm_token}" in your WHY line to COMMIT.
   - If X is wrong: choose a NEW coordinate.
D) For any <select> / combobox element, you MUST use select_option — do NOT use left_click or scroll to interact with it.
   Example: {{"action":"select_option","args":{{"selector":"[data-testid=\\"country-select\\"]","label":"Canada"}},"why":"...","verify":{{...}}}}
   If select_option returns ok=false with a "fallback" field, follow that fallback instruction on the next step.

Rules each step:
1) Return JSON only, no markdown.
2) JSON format ONLY (no extra keys): {"action":"left_click|double_click|right_click|mouse_move|left_click_drag|type|key|scroll|wait|screenshot|select_option","args":{...},"why":"...","verify":{"step_ok":"YES|NO","criteria_visible":"YES|NO","reason":"..."}}
   - Use x,y in MODEL coordinates (screenshot size) for click/move actions.
   - For drag: provide start/end as [x,y] in MODEL coordinates (start_coordinate/end_coordinate or start/end).
   - For clicks: args must include x,y and may include role/name/selector/target_text.
   - For type: args must include text and may include x,y or DOM hints for the target field.
   - For key: args must include key (do NOT use press/pressed as an argument key).
   - For select_option: args must include selector (CSS for the <select> element) and label (visible option text) or value. Use for native <select> dropdowns instead of clicking and scrolling. If it returns ok=false with a "fallback" hint, follow that hint on the next step.
   - verify.step_ok indicates whether the previous step achieved its intended effect.
   - verify.criteria_visible MUST reflect whether the success criteria is visible in the current screenshot.
3) If you open a context menu via right_click, select the menu option with a left_click (the menu is part of the page UI).
4) Example:
   {"action":"left_click","args":{"x":404,"y":47},"why":"Focus the search bar.","verify":{"step_ok":"YES","criteria_visible":"NO","reason":"Success criteria not visible yet."}}
   {"action":"key","args":{"key":"Enter"},"why":"Submit the search.","verify":{"step_ok":"YES","criteria_visible":"NO","reason":"Results have not loaded yet."}}

FINAL PROTOCOL:
Finish with exactly one of:
  FINAL: PASS
  FINAL: FAIL
""".strip()

    if preface_text:
        user_text = f"{preface_text}\n\n{user_text}"

    content: List[Dict[str, Any]] = [{"type": "input_text", "text": user_text}]
    if preface_image_b64:
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{preface_image_b64}",
            }
        )

    return [{"role": "user", "content": content}]


def _next_action_response_format() -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "next_action",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "left_click",
                            "double_click",
                            "right_click",
                            "mouse_move",
                            "left_click_drag",
                            "type",
                            "key",
                            "scroll",
                            "wait",
                            "screenshot",
                        ],
                    },
                    "args": {"type": "object", "additionalProperties": True},
                    "why": {"type": "string"},
                    "verify": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "step_ok": {"type": "string", "enum": ["YES", "NO"]},
                            "criteria_visible": {
                                "type": "string",
                                "enum": ["YES", "NO"],
                            },
                            "reason": {"type": "string"},
                        },
                        "required": ["step_ok", "criteria_visible", "reason"],
                    },
                },
                "required": ["action", "args", "why", "verify"],
            },
        },
    }


def _request_next_action_response(
    *,
    client: OpenAIClient,
    model: str,
    next_inputs: List[Dict[str, Any]],
    effective_max_tokens: int,
    verbose: bool,
    previous_response_id: Optional[str] = None,
    max_output_tokens_override: Optional[int] = None,
    reasoning_effort_override: Optional[str] = None,
):
    req = dict(
        model=model,
        max_output_tokens=int(max_output_tokens_override or effective_max_tokens),
        input=next_inputs,
        response_format=_next_action_response_format(),
    )
    reasoning_effort = normalize_reasoning_effort(model, reasoning_effort_override)
    if reasoning_effort is None and str(model).lower().startswith("gpt-5"):
        reasoning_effort = normalize_reasoning_effort(model, "minimal")
    if reasoning_effort:
        req["reasoning"] = {"effort": reasoning_effort}
    if previous_response_id:
        req["previous_response_id"] = previous_response_id

    _TRANSIENT_RETRY_STATUSES = {429, 500, 502, 503, 504}
    _TRANSIENT_MAX_RETRIES = 3
    _TRANSIENT_BACKOFF_BASE_S = 5.0

    attempts = 0
    transient_retries = 0
    effort_retry_done = False
    while True:
        req_t0 = time.perf_counter()
        try:
            resp = client.responses.create(**cast(Any, req))
            _log_timing(
                "llm.responses.create",
                time.perf_counter() - req_t0,
                verbose=verbose,
                warn_threshold_s=DEFAULT_TIMING_WARN_S,
                extra=f"attempt={attempts + 1} model={model} max_output_tokens={req.get('max_output_tokens')}",
            )
            return resp
        except TypeError as e:
            attempts += 1
            msg = str(e)
            changed = False
            if "response_format" in msg and "response_format" in req:
                req.pop("response_format", None)
                changed = True
            if "reasoning" in msg and "reasoning" in req:
                req.pop("reasoning", None)
                changed = True
            if not changed or attempts >= 3:
                raise
        except Exception as e:
            msg = str(e)
            # Transient check: status_code attribute is present on both
            # openai.APIStatusError and anthropic.APIStatusError.
            status = getattr(e, "status_code", None)
            is_transient = status in _TRANSIENT_RETRY_STATUSES or isinstance(
                e, (openai.APIConnectionError, openai.APITimeoutError)
            )
            # Also cover Anthropic-SDK connection/timeout errors (no status_code).
            if not is_transient and anthropic_mod is not None:
                for _exc_name in ("APIConnectionError", "APITimeoutError"):
                    _exc_cls = getattr(anthropic_mod, _exc_name, None)
                    if _exc_cls is not None and isinstance(e, _exc_cls):
                        is_transient = True
                        break
            if is_transient and transient_retries < _TRANSIENT_MAX_RETRIES:
                transient_retries += 1
                attempts += 1
                delay = _TRANSIENT_BACKOFF_BASE_S * (2 ** (transient_retries - 1))
                _log_warn(
                    f"[llm] Transient API error (attempt {transient_retries}/{_TRANSIENT_MAX_RETRIES},"
                    f" status={status}): {e}. Retrying in {delay:.1f}s."
                )
                time.sleep(delay)
                continue
            if (
                not effort_retry_done
                and "reasoning.effort" in msg
                and "Unsupported value" in msg
                and "reasoning" in req
            ):
                req["reasoning"] = {"effort": "low"}
                effort_retry_done = True
                continue
            raise


def run_agent(
    context: BrowserContext,
    page: Page,
    task_prompt: str,
    success_indicator: SuccessIndicatorConfig,
    model: str,
    max_steps: int,
    viewport: Viewport,
    model_viewport: Viewport,
    username: Optional[str],
    password: Optional[str],
    max_tokens_user: int,
    max_tokens_margin: int,
    verbose: bool,
    screenshot_base_path: str,
    agent_view_dir: str,
    enable_agent_view: bool,
    final_in_agent_view_dir: bool,
    pre_click_sleep_s: float,
    pre_type_sleep_s: float,
    post_shot_sleep_s: float,
    verify_wait_s: float,
    post_action_sleep_s: float,
    post_type_sleep_s: float,
    x_size_px: int,
    x_thickness_px: int,
    arm_commit: bool,
    confirm_token: str,
    arm_timeout_steps: int,
    keep_last_turns: int,
    keep_last_images: int,
    learn_from_vision: bool,
    site_hints_path: str,
    allow_manual_interject: bool,
    step_training: bool,
    step_training_signal_path: Optional[str],
    defer_final: bool,
    final_state: FinalTokenState,
    preface_text: Optional[str] = None,
    preface_image_b64: Optional[str] = None,
    verify_guard_min_confidence: float = 0.0,
) -> RunOutcome:
    api_env_name = model_api_env_var(model)
    api_key = os.environ.get(api_env_name)
    if not api_key:
        raise SystemExit(f"Missing {api_env_name} env var.")

    if (
        model_viewport.width != viewport.width
        or model_viewport.height != viewport.height
    ) and not PIL_OK:
        raise SystemExit(
            "Pillow (PIL) is required for downscaling (--model-width/--model-height). Install pillow."
        )

    client = _new_model_client(model, api_key)

    site_hints = load_site_hints(site_hints_path)

    xform = CoordinateTransform(
        model_w=model_viewport.width,
        model_h=model_viewport.height,
        actual_w=viewport.width,
        actual_h=viewport.height,
    )

    effective_max_tokens = compute_effective_max_tokens(
        user_max_tokens=max_tokens_user,
        thinking_budget=None,
        margin=max_tokens_margin,
    )
    run_ctx = AgentRunContext(
        client=client,
        site_hints=site_hints,
        xform=xform,
        effective_max_tokens=effective_max_tokens,
        history_limit=max(0, int(keep_last_turns)),
        manual_enabled=bool(allow_manual_interject),
        step_training_enabled=bool(step_training) and bool(step_training_signal_path),
        step_training_token=0,
    )
    if run_ctx.step_training_enabled:
        run_ctx.step_training_token = _read_step_training_token(
            step_training_signal_path or ""
        )

    def call_openai(
        next_inputs: List[Dict[str, Any]],
        previous_response_id: Optional[str],
        *,
        max_output_tokens_override: Optional[int] = None,
        reasoning_effort_override: Optional[str] = None,
    ):
        return _request_next_action_response(
            client=run_ctx.client,
            model=model,
            next_inputs=next_inputs,
            effective_max_tokens=run_ctx.effective_max_tokens,
            verbose=verbose,
            previous_response_id=previous_response_id,
            max_output_tokens_override=max_output_tokens_override,
            reasoning_effort_override=reasoning_effort_override,
        )

    def build_step_prompt(step_idx: int, last_result: str, armed_notice: str) -> str:
        dom_candidates = _get_dom_candidates(page, max_items=60)
        parts = [
            f"Step {step_idx}: Choose the next single action.",
            "Return JSON only. If task is complete, reply with FINAL: PASS or FINAL: FAIL.",
            'Required schema: {"action":"...","args":{...},"why":"...","verify":{"step_ok":"YES|NO","criteria_visible":"YES|NO","reason":"..."}} with no extra keys.',
            "verify.step_ok indicates whether the previous step achieved its intended effect.",
            "verify.criteria_visible MUST indicate whether the success criteria is visible in the current screenshot.",
            "Use action values: left_click|double_click|right_click|mouse_move|left_click_drag|type|key|scroll|wait|screenshot.",
            "Prefer DOM hints for links and buttons (role/name/selector) instead of raw x,y when possible.",
            "If you open a context menu via right_click, select the menu option with a left_click.",
            "Use x,y in MODEL coordinates (screenshot size) for click/move actions.",
            "For left_click_drag: provide start/end coordinates as [x,y].",
            "In WHY, briefly summarize the top 2-3 DOM target options you considered and why you picked this one (keep concise).",
            "Also include an Impact tag in WHY: Impact=HELPED|NO_EFFECT|REGRESSED describing whether this step moved progress forward.",
            f"Task: {task_prompt}",
            f"Success criteria: {success_indicator.value}",
        ]
        if dom_candidates:
            parts.append("DOM candidates (use role/name or selector when possible):")
            parts.extend([f"- {line}" for line in dom_candidates])
        if preface_text:
            parts.append(f"Context: {preface_text}")
        if username is not None and password is not None:
            parts.append(f"Credentials: username={username} password={password}")
        if history_texts:
            parts.append("Recent history (text-only):")
            for h in history_texts:
                parts.append(f"- {h}")
        if armed_notice:
            parts.append(armed_notice)
        if last_result:
            parts.append(f"Last result: {last_result}")
        parts.append("Remember: use x,y in MODEL coordinates (screenshot size).")
        return "\n".join(parts)

    if enable_agent_view or final_in_agent_view_dir:
        agent_view_dir = ensure_dir(agent_view_dir)
        base_name = os.path.basename(screenshot_base_path)
        base_path = (
            os.path.join(agent_view_dir, base_name)
            if final_in_agent_view_dir
            else screenshot_base_path
        )
    else:
        base_path = screenshot_base_path
    success_path = final_stamp_path(base_path, "success")
    failure_path = final_stamp_path(base_path, "failure")

    last_mark_points_actual: List[Tuple[float, float]] = []
    armed: Optional[ArmedClick] = None
    action_records = run_ctx.action_records
    last_result_text = ""
    armed_notice = ""
    hover_required = "hover" in (task_prompt or "").lower()
    history_texts = run_ctx.history_texts
    history_limit = run_ctx.history_limit
    manual_enabled = run_ctx.manual_enabled
    manual_capture_page: Optional[Page] = None
    manual_last_ts = 0.0
    step_training_enabled = run_ctx.step_training_enabled
    step_training_token = run_ctx.step_training_token
    if step_training_enabled:
        _log_info(
            "[step-training] Enabled. Awaiting Continue before committing LLM actions."
        )
    elif verbose:
        _log_info("[step-training] Disabled. LLM actions will execute immediately.")

    def add_history(entry: str) -> None:
        if history_limit <= 0:
            return
        history_texts.append(entry)
        if len(history_texts) > history_limit:
            del history_texts[0 : len(history_texts) - history_limit]

    def record_action(
        action_name: str, action_input: Dict[str, Any], result: Optional[Dict[str, Any]]
    ) -> None:
        action_records.append(
            {
                "action": action_name,
                "input": dict(action_input) if isinstance(action_input, dict) else {},
                "result": result if isinstance(result, dict) else None,
            }
        )

    def _handle_manual_clicks(step_idx: int) -> bool:
        nonlocal manual_last_ts
        if not manual_enabled:
            return False
        manual_clicks, manual_last_ts = _poll_manual_clicks(
            loop_state.page, manual_last_ts
        )
        if not manual_clicks:
            return False
        last_click = manual_clicks[-1]
        ax = float(last_click.get("x") or 0.0)
        ay = float(last_click.get("y") or 0.0)
        dom_hint = None
        if isinstance(last_click, dict):
            dom_hint = (
                _build_dom_hint_from_element_info(last_click) if last_click else None
            )
        if not dom_hint:
            dom_hint = infer_clickable_hint_from_point(
                loop_state.page, ax, ay
            ) or infer_dom_hint_from_point(loop_state.page, ax, ay)
        mx, my = xform.to_model(ax, ay)
        manual_args: Dict[str, Any] = {"x": mx, "y": my, "manual": True}
        updated_hint = False
        if dom_hint:
            manual_args.update(_action_input_from_dom_hint(dom_hint))
            domain = normalize_domain(loop_state.page.url)
            updated_hint = update_site_hints(site_hints, domain, dom_hint)
            if updated_hint:
                save_site_hints(site_hints_path, site_hints)
        record_action(
            "manual_click",
            manual_args,
            {
                "ok": True,
                "action": "manual_click",
                "actual": [ax, ay],
                "dom_hint": dom_hint,
            },
        )
        loop_state.armed = None
        loop_state.armed_notice = ""
        loop_state.last_mark_points_actual = [(ax, ay)]
        _ = maybe_save_agent_view(
            enable_agent_view,
            loop_state.page,
            agent_view_dir,
            step_idx,
            "manual_click",
            mark_points=loop_state.last_mark_points_actual,
            x_size_px=x_size_px,
            thickness_px=x_thickness_px,
        )
        hint_desc = ""
        hint_source = ""
        if dom_hint:
            if dom_hint.get("type") == "role_name":
                hint_desc = f" role={dom_hint.get('role')} name={dom_hint.get('name')}"
            elif dom_hint.get("type") == "selector":
                hint_desc = f" selector={dom_hint.get('value')}"
            elif dom_hint.get("type") == "text":
                hint_desc = f" text={dom_hint.get('value')}"
            hint_source = "saved" if updated_hint else "seen"
        loop_state.last_result_text = f"Manual interject: user clicked at actual=({ax:.0f},{ay:.0f}) model=({mx:.0f},{my:.0f}).{hint_desc}"
        if dom_hint:
            hint_input = _action_input_from_dom_hint(dom_hint)
            hint_parts: List[str] = []
            if hint_input.get("selector"):
                hint_parts.append(f"selector={hint_input.get('selector')}")
            if hint_input.get("role") or hint_input.get("name"):
                hint_parts.append(
                    f"role={hint_input.get('role')} name={hint_input.get('name')}"
                )
            if hint_input.get("target_text"):
                hint_parts.append(f"text={hint_input.get('target_text')}")
            selector_info = "; ".join([p for p in hint_parts if p])
            loop_state.last_result_text += f" dom_hint={dom_hint} source={hint_source}"
            if selector_info:
                loop_state.last_result_text += f" selector_info=({selector_info})"
        _log_info(loop_state.last_result_text)
        add_history(loop_state.last_result_text)
        return True

    def _wait_for_step_training(step_idx: int, action_name: str) -> bool:
        nonlocal step_training_token
        if not step_training_enabled or action_name == "screenshot":
            return True
        _log_info(f"[step-training] Step {step_idx}: waiting to commit {action_name}.")
        while True:
            if _handle_manual_clicks(step_idx):
                _log_info(
                    f"[step-training] Manual click captured; skipping {action_name}."
                )
                return False
            token = _read_step_training_token(step_training_signal_path or "")
            if token != step_training_token:
                step_training_token = token
                run_ctx.step_training_token = token
                _log_info(
                    f"[step-training] Continue received; executing {action_name}."
                )
                return True
            time.sleep(0.1)

    def _ensure_manual_capture(current_page: Page) -> None:
        nonlocal manual_capture_page, manual_last_ts
        if manual_enabled and (
            manual_capture_page is None or manual_capture_page != current_page
        ):
            _init_manual_click_capture(current_page, enabled=True, verbose=verbose)
            manual_capture_page = current_page
            manual_last_ts = 0.0

    loop_state = AgentLoopState(
        page=page,
        last_mark_points_actual=last_mark_points_actual,
        armed=armed,
        last_result_text=last_result_text,
        armed_notice=armed_notice,
    )
    return _run_agent_step_loop(
        context=context,
        state=loop_state,
        max_steps=max_steps,
        verbose=verbose,
        model=model,
        effective_max_tokens=effective_max_tokens,
        model_viewport=model_viewport,
        viewport=viewport,
        enable_agent_view=enable_agent_view,
        agent_view_dir=agent_view_dir,
        post_shot_sleep_s=post_shot_sleep_s,
        call_openai=call_openai,
        final_state=final_state,
        password=password,
        add_history=add_history,
        build_step_prompt=build_step_prompt,
        defer_final=defer_final,
        x_size_px=x_size_px,
        x_thickness_px=x_thickness_px,
        success_path=success_path,
        failure_path=failure_path,
        action_records=action_records,
        client=client,
        success_indicator=success_indicator,
        verify_wait_s=verify_wait_s,
        wait_for_step_training=_wait_for_step_training,
        record_action=record_action,
        xform=xform,
        arm_commit=arm_commit,
        confirm_token=confirm_token,
        pre_click_sleep_s=pre_click_sleep_s,
        pre_type_sleep_s=pre_type_sleep_s,
        post_type_sleep_s=post_type_sleep_s,
        post_action_sleep_s=post_action_sleep_s,
        learn_from_vision=learn_from_vision,
        site_hints=site_hints,
        site_hints_path=site_hints_path,
        hover_required=hover_required,
        arm_timeout_steps=arm_timeout_steps,
        ensure_manual_capture=_ensure_manual_capture,
        handle_manual_clicks=_handle_manual_clicks,
        task_prompt=task_prompt,
        verify_guard_min_confidence=verify_guard_min_confidence,
    )


# -----------------------------
# Main
# -----------------------------


def main() -> None:
    args = parse_cli_args(logger=_log_info)
    run_cli_with_args(args)


def run_cli_with_args(args: Any) -> None:
    enable_agent_view = not args.no_agent_view
    final_in_agent_view_dir = not args.no_agent_view

    def _raise_if_both_final_shots(success_path: str, failure_path: str) -> None:
        if os.path.exists(success_path) and os.path.exists(failure_path):
            msg = f"Both success and failure screenshots exist: {success_path} | {failure_path}"
            _log_info(f"[error] {msg}")
            raise RuntimeError(msg)

    def _warn_if_both_final_shots() -> None:
        base = args.screenshot_base
        if final_in_agent_view_dir:
            base_name = os.path.basename(base)
            base = os.path.join(ensure_dir(args.agent_view_dir), base_name)
        base = _prefix_path_for_github_run(base)
        success_path = final_stamp_path(base, "success")
        failure_path = final_stamp_path(base, "failure")
        if os.path.exists(success_path) and os.path.exists(failure_path):
            _log_info(
                f"[warn] Both success and failure screenshots exist: {success_path} | {failure_path}"
            )

    atexit.register(_warn_if_both_final_shots)

    def maybe_save_final_shot(
        page: Page, verdict: str, png_bytes: Optional[bytes] = None
    ) -> None:
        base = args.screenshot_base
        if final_in_agent_view_dir:
            base_name = os.path.basename(base)
            base = os.path.join(ensure_dir(args.agent_view_dir), base_name)
        base = _prefix_path_for_github_run(base)
        success_path = final_stamp_path(base, "success")
        failure_path = final_stamp_path(base, "failure")
        _raise_if_both_final_shots(success_path, failure_path)
        if verdict == "PASS" and os.path.exists(failure_path):
            msg = f"Refusing to write success screenshot because failure already exists: {failure_path}"
            _log_info(f"[error] {msg}")
            raise RuntimeError(msg)
        if verdict != "PASS" and os.path.exists(success_path):
            msg = f"Refusing to write failure screenshot because success already exists: {success_path}"
            _log_info(f"[error] {msg}")
            raise RuntimeError(msg)
        png = (
            png_bytes
            if png_bytes is not None
            else page.screenshot(type="png", full_page=False, scale="css")
        )
        shot = write_final_screenshot(
            png,
            verdict=verdict,
            success_path=success_path,
            failure_path=failure_path,
        )
        _log_info(
            f"Saved {'success' if verdict == 'PASS' else 'failure'} screenshot: {shot}"
        )

    final_state = FinalTokenState()

    if args.log_file:
        try:
            _init_log_file(args.log_file)
        except Exception as exc:
            _log_info(f"[log] Failed to initialize log file '{args.log_file}': {exc}")
    _init_azure_logging(args.Azure_Logging)

    viewport = Viewport(args.width, args.height)
    mw = (
        args.model_width
        if args.model_width and args.model_width > 0
        else viewport.width
    )
    mh = (
        args.model_height
        if args.model_height and args.model_height > 0
        else viewport.height
    )
    model_viewport = Viewport(mw, mh)

    username = os.environ.get("AGENTICWEBQA_USERNAME")
    password = os.environ.get("AGENTICWEBQA_PASSWORD")

    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch(
            headless=args.headless, slow_mo=args.slowmo
        )
        context: BrowserContext = browser.new_context(
            viewport={"width": viewport.width, "height": viewport.height},
            device_scale_factor=1,
        )
        page: Page = context.new_page()

        page.goto(args.start_url, wait_until="domcontentloaded")

        api_env_name = model_api_env_var(args.model)
        api_key = os.environ.get(api_env_name)
        if not api_key:
            raise SystemExit(f"Missing {api_env_name} env var.")
        provider = infer_model_provider(args.model)
        _log_info(f"[LLM] Provider selected: {provider}")
        _log_info(f"[LLM] Model selected: {args.model}")
        models_dir = ensure_dir("Models")
        model_path = model_path_for_url(args.start_url, models_dir)
        page_model = load_page_model(model_path, args.start_url)

        manual_actions = _parse_actions_arg(args.actions)
        _now = datetime.datetime.now()
        variables = {
            "username": username or "",
            "password": password or "",
            "date": _now.strftime("%Y-%m-%d"),
            "epoch": str(int(_now.timestamp())),
            "rand_string": "".join(random.choices(string.ascii_lowercase, k=5)),
        }
        args.prompt = _render_template(args.prompt, variables)
        rendered_indicator_value = _render_template(
            args.success_indicator.value, variables
        )
        if rendered_indicator_value != args.success_indicator.value:
            args.success_indicator = SuccessIndicatorConfig(
                type=args.success_indicator.type,
                value=rendered_indicator_value,
            )
        # After rendering, extract username/password from the prompt as fallbacks
        # when they were not supplied via env vars (e.g. dynamic registration prompts).
        if not username:
            extracted = _extract_named_value_from_prompt(args.prompt, "username")
            if extracted:
                variables["username"] = extracted
        if not password:
            extracted = _extract_named_value_from_prompt(args.prompt, "password")
            if extracted:
                variables["password"] = extracted
        query = _extract_quoted_value(args.prompt)
        variables["prompt"] = args.prompt
        variables["success_criteria"] = args.success_indicator.value
        variables["query"] = query or ""

        _log_info("[LLM] Run context:")
        _secret = variables.get("password") or None
        _log_info(f"Prompt:\n{_redact_secret_text(args.prompt, _secret)}")
        _log_info(
            f"Success criteria:\n{_redact_secret_text(args.success_indicator.value, _secret)}"
        )

        client = _new_model_client(args.model, api_key)

        sequence: List[str] = []
        used_prompt_route = False
        existing_funcs = {
            str(f.get("name")): f
            for f in page_model.get("functions", [])
            if isinstance(f, dict)
        }
        if manual_actions:
            normalized_actions: List[str] = []
            for name in manual_actions:
                exact = next(
                    (n for n in existing_funcs.keys() if n.lower() == name.lower()),
                    name,
                )
                normalized_actions.append(exact)
            manual_actions = normalized_actions
            prefix: List[str] = []
            for name in manual_actions:
                if name in existing_funcs:
                    prefix.append(name)
                    continue
                break
            sequence = prefix
        else:
            sequence = (
                get_prompt_route(
                    page_model, args.prompt, page_model.get("functions", [])
                )
                or []
            )
            used_prompt_route = bool(sequence)
            if sequence:
                sequence = _expand_composite_sequence(
                    sequence, page_model.get("functions", [])
                )
            if not sequence and page_model.get("functions"):
                sequence, _ = pick_function_sequence(
                    client,
                    args.model,
                    page_model.get("functions", []),
                    args.prompt,
                )

        failed_func: Optional[str] = None
        completed_functions: List[str] = []
        last_sequence: List[str] = []
        last_sequence_error: Optional[str] = None
        remaining_actions: List[str] = []
        missing_actions: List[str] = []
        failed_manual_action: Optional[str] = None
        llm_repaired_action: Optional[str] = None
        manual_verify_failed = False
        manual_verify_why = ""
        manual_verify_confidence: Optional[float] = None
        if manual_actions:
            remaining_actions = manual_actions[len(sequence) :]
            missing_actions = [a for a in remaining_actions if a not in existing_funcs]

        def _final_shot_path(
            base: str, suffix: str, agent_dir: str, use_agent: bool
        ) -> str:
            if use_agent:
                base_name = os.path.basename(base)
                base = os.path.join(ensure_dir(agent_dir), base_name)
            return final_stamp_path(base, suffix)

        if sequence:
            last_sequence = sequence[:]
            if args.verbose:
                if manual_actions:
                    _log_info(f"[LLM] Manual actions requested: {manual_actions}")
                    _log_info(f"[LLM] Using existing actions in order: {sequence}")
                else:
                    _log_info(f"[LLM] Selected function sequence: {sequence}")
            if enable_agent_view or final_in_agent_view_dir:
                ensure_dir(args.agent_view_dir)
            ok, failed_func, err, page = execute_model_sequence(
                page,
                page_model,
                sequence,
                variables,
                verbose=args.verbose,
                pre_type_sleep_s=args.pre_type_sleep,
                post_type_sleep_s=args.post_type_sleep,
                post_action_sleep_s=args.post_action_sleep,
                enable_agent_view=enable_agent_view,
                agent_view_dir=args.agent_view_dir,
                x_size_px=args.x_size,
                x_thickness_px=args.x_thickness,
            )
            save_page_model(model_path, page_model)
            if ok:
                if manual_actions and remaining_actions:
                    if args.verbose:
                        _log_info(
                            f"[LLM] Completed requested prefix actions: {sequence}. Continuing to build missing actions: {remaining_actions}"
                        )
                else:
                    if args.success_indicator.type != SuccessIndicatorType.VISUAL_LLM:
                        if args.verify_wait and args.verify_wait > 0:
                            time.sleep(args.verify_wait)
                        det_ok = check_deterministic_success(
                            page, args.success_indicator, timeout_ms=10000
                        )
                        if det_ok:
                            _log_info(
                                f"[deterministic] {args.success_indicator.type.value} matched: {args.success_indicator.value!r}"
                            )
                            try:
                                maybe_save_final_shot(page, "PASS")
                            except Exception as e:
                                if args.verbose:
                                    _log_info(
                                        f"[playwright] Failed to save success screenshot: {e}"
                                    )
                            if not used_prompt_route and not manual_actions:
                                set_prompt_route(
                                    page_model,
                                    args.prompt,
                                    sequence,
                                    page_model.get("functions", []),
                                )
                                save_page_model(model_path, page_model)
                            _log_final("PASS", final_state)
                            context.close()
                            browser.close()
                            return
                        if args.verbose:
                            _log_info(
                                f"[deterministic] {args.success_indicator.type.value} not matched: {args.success_indicator.value!r}"
                            )
                    else:
                        verify_ok = False
                        verify_verdict = "FAIL"
                        verify_why = ""
                        verify_confidence = None
                        verify_png = None
                        try:
                            _seq_history = "\n".join(
                                f"{i + 1}. {name}" for i, name in enumerate(sequence)
                            )
                            (
                                verify_ok,
                                verify_verdict,
                                verify_why,
                                verify_confidence,
                                verify_png,
                            ) = verify_success_with_llm(
                                client,
                                args.model,
                                page,
                                args.success_indicator.value,
                                viewport=viewport,
                                model_viewport=model_viewport,
                                verify_wait_s=args.verify_wait,
                                task_prompt=args.prompt,
                                action_history=_seq_history,
                            )
                        except Exception as e:
                            verify_ok = False
                            verify_verdict = "ERROR"
                            verify_why = str(e)
                            verify_confidence = None
                            verify_png = None
                            _log_info(
                                f"[LLM] Success criteria check failed: {verify_why}"
                            )
                        if verify_ok:
                            try:
                                maybe_save_final_shot(
                                    page, "PASS", png_bytes=verify_png
                                )
                            except Exception as e:
                                if args.verbose:
                                    _log_info(
                                        f"[playwright] Failed to save success screenshot: {e}"
                                    )
                            if not used_prompt_route and not manual_actions:
                                set_prompt_route(
                                    page_model,
                                    args.prompt,
                                    sequence,
                                    page_model.get("functions", []),
                                )
                                save_page_model(model_path, page_model)
                            _log_final("PASS", final_state)
                            if args.verbose:
                                conf_note = (
                                    f" (confidence={verify_confidence:.2f})"
                                    if verify_confidence is not None
                                    else ""
                                )
                                _log_info(
                                    f"[LLM] Sequence completed and success criteria confirmed: {verify_why}{conf_note}"
                                )
                            context.close()
                            browser.close()
                            return
                        if args.verbose:
                            conf_note = (
                                f" (confidence={verify_confidence:.2f})"
                                if verify_confidence is not None
                                else ""
                            )
                            _log_info(
                                f"[LLM] Success criteria check: {verify_verdict} - {verify_why}{conf_note}"
                            )
                        if manual_actions:
                            manual_verify_failed = True
                            manual_verify_why = verify_why
                            manual_verify_confidence = verify_confidence

                        if args.verbose:
                            _log_info(f"[playwright] Sequence failed: {err}")
                        # If manual actions remain, continue to fallback regardless of verify result.
            if failed_func and failed_func in sequence:
                completed_functions = sequence[: sequence.index(failed_func)]
            else:
                completed_functions = sequence[:]
            last_sequence_error = err
            if manual_actions and failed_func and failed_func in manual_actions:
                failed_manual_action = failed_func
                if args.verbose:
                    _log_info(
                        f"[playwright] Manual action failed: {failed_manual_action}. Will attempt to repair it."
                    )

            if page_model.get("functions") and not manual_actions:
                alt_sequence, _ = pick_function_sequence(
                    client,
                    args.model,
                    page_model.get("functions", []),
                    args.prompt,
                    extra_note=f"Previous sequence failed: {sequence}. Error: {err}",
                )
                if alt_sequence and alt_sequence != sequence:
                    if args.verbose:
                        _log_info(
                            f"[LLM] Retrying with alternate sequence: {alt_sequence}"
                        )
                    if enable_agent_view or final_in_agent_view_dir:
                        ensure_dir(args.agent_view_dir)
                    ok, failed_func, err, page = execute_model_sequence(
                        page,
                        page_model,
                        alt_sequence,
                        variables,
                        verbose=args.verbose,
                        pre_type_sleep_s=args.pre_type_sleep,
                        post_type_sleep_s=args.post_type_sleep,
                        post_action_sleep_s=args.post_action_sleep,
                        enable_agent_view=enable_agent_view,
                        agent_view_dir=args.agent_view_dir,
                        x_size_px=args.x_size,
                        x_thickness_px=args.x_thickness,
                    )
                    if ok:
                        set_prompt_route(
                            page_model,
                            args.prompt,
                            alt_sequence,
                            page_model.get("functions", []),
                        )
                        save_page_model(model_path, page_model)
                        if args.verbose:
                            _log_info(
                                f"[playwright] Saved prompt route after alternate sequence success: {alt_sequence}"
                            )
                        context.close()
                        browser.close()
                        return
                    if args.verbose:
                        _log_info(f"[playwright] Alternate sequence failed: {err}")
                    sequence = alt_sequence
                    last_sequence = alt_sequence[:]
                    if failed_func and failed_func in alt_sequence:
                        completed_functions = alt_sequence[
                            : alt_sequence.index(failed_func)
                        ]
                    else:
                        completed_functions = alt_sequence[:]
                    last_sequence_error = err

        restart_for_llm = bool(last_sequence_error or failed_manual_action)
        replay_ok = True
        failed_target = failed_manual_action or failed_func
        if restart_for_llm and args.start_url:
            if args.verbose:
                _log_info("[playwright] Restarting from start_url before LLM fallback.")
            try:
                context.close()
            except Exception as e:
                if args.verbose:
                    _log_info(
                        f"[playwright] Failed to close context before restart: {e}"
                    )
            context = browser.new_context(
                viewport={"width": viewport.width, "height": viewport.height},
                device_scale_factor=1,
            )
            page = context.new_page()
            page.goto(args.start_url, wait_until="domcontentloaded")
            last_sequence = []
            if completed_functions:
                if args.verbose:
                    _log_info(
                        f"[playwright] Replaying completed actions: {completed_functions}"
                    )
                ok, _, replay_err, page = execute_model_sequence(
                    page,
                    page_model,
                    completed_functions,
                    variables,
                    verbose=args.verbose,
                    pre_type_sleep_s=args.pre_type_sleep,
                    post_type_sleep_s=args.post_type_sleep,
                    post_action_sleep_s=args.post_action_sleep,
                    enable_agent_view=enable_agent_view,
                    agent_view_dir=args.agent_view_dir,
                    x_size_px=args.x_size,
                    x_thickness_px=args.x_thickness,
                )
                if not ok:
                    replay_ok = False
                    if args.verbose:
                        _log_info(f"[playwright] Replay failed: {replay_err}")
            if manual_actions:
                if replay_ok and failed_target:
                    remaining_actions = [failed_target]
                else:
                    remaining_actions = manual_actions[:]
                missing_actions = [
                    a for a in remaining_actions if a not in existing_funcs
                ]

        if args.verbose:
            _log_info("[playwright] Falling back to LLM.")

        defer_final = bool(manual_actions)

        completed_text = (
            ", ".join(completed_functions) if completed_functions else "None"
        )
        current_url = page.url
        try:
            current_title = page.title()
        except Exception:
            current_title = ""
        if restart_for_llm:
            preface_lines = [
                "CONTEXT: You are starting from the beginning.",
                f"Start URL: {args.start_url}",
                f"Current URL: {current_url}",
            ]
            if completed_functions and replay_ok:
                preface_lines.append(
                    f"Completed via Playwright replay: {', '.join(completed_functions)}"
                )
            if not replay_ok:
                preface_lines.append(
                    "Playwright replay failed; complete the task from the beginning."
                )
        else:
            preface_lines = [
                "CONTEXT: You are NOT starting from the beginning.",
                f"Completed functions: {completed_text}",
                f"Current URL: {current_url}",
            ]
        if manual_actions:
            if remaining_actions:
                label = (
                    "Requested actions"
                    if restart_for_llm
                    else "Requested actions (remaining)"
                )
                preface_lines.append(f"{label}: {', '.join(remaining_actions)}")
            if missing_actions:
                preface_lines.append(
                    f"Missing actions to create: {', '.join(missing_actions)}"
                )
        if current_title:
            preface_lines.append(f"Page title: {current_title}")
        if failed_target:
            preface_lines.append(f"Failed action to take over: {failed_target}")
            if restart_for_llm and manual_actions:
                preface_lines.append(
                    "Only repair the failed action; remaining actions will be executed by Playwright."
                )
        if last_sequence_error:
            preface_lines.append(f"Last Playwright failure: {last_sequence_error}")
        if query:
            preface_lines.append(f"Search/query already in context: {query}")
        if not restart_for_llm:
            preface_lines.append(
                "Do NOT repeat completed functions unless absolutely required."
            )
        preface_text = "\n".join(preface_lines)

        preface_png = capture_model_screenshot_png(
            page,
            actual_w=viewport.width,
            actual_h=viewport.height,
            model_w=model_viewport.width,
            model_h=model_viewport.height,
        )

        outcome = run_agent(
            context=context,
            page=page,
            task_prompt=args.prompt,
            success_indicator=args.success_indicator,
            model=args.model,
            max_steps=args.max_steps,
            viewport=viewport,
            model_viewport=model_viewport,
            username=username,
            password=password,
            max_tokens_user=args.max_tokens,
            max_tokens_margin=args.max_tokens_margin,
            verbose=args.verbose,
            screenshot_base_path=args.screenshot_base,
            agent_view_dir=args.agent_view_dir,
            enable_agent_view=enable_agent_view,
            final_in_agent_view_dir=final_in_agent_view_dir,
            pre_click_sleep_s=args.pre_click_sleep,
            pre_type_sleep_s=args.pre_type_sleep,
            post_shot_sleep_s=args.post_shot_sleep,
            verify_wait_s=args.verify_wait,
            post_action_sleep_s=args.post_action_sleep,
            post_type_sleep_s=args.post_type_sleep,
            x_size_px=args.x_size,
            x_thickness_px=args.x_thickness,
            arm_commit=args.arm_commit,
            confirm_token=args.confirm_token,
            arm_timeout_steps=args.arm_timeout_steps,
            keep_last_turns=args.keep_last_turns,
            keep_last_images=args.keep_last_images,
            learn_from_vision=True,
            site_hints_path=args.site_hints_path,
            allow_manual_interject=not args.headless,
            step_training=args.step_training,
            step_training_signal_path=args.step_training_signal,
            defer_final=defer_final,
            final_state=final_state,
            preface_text=preface_text,
            preface_image_b64=b64_png(preface_png),
            verify_guard_min_confidence=args.verify_guard_min_confidence,
        )

        def _step_chunk_diagnostics(step_list: Any, cap_value: int) -> Dict[str, int]:
            steps_local = step_list if isinstance(step_list, list) else []
            raw_count = len(steps_local)
            dict_count = sum(1 for s in steps_local if isinstance(s, dict))
            capped_count = sum(
                1
                for s in steps_local
                if isinstance(s, dict) and _is_capped_interaction(s)
            )
            chunks_local = _split_steps_by_action_cap(steps_local, cap_value)
            chunk_count = len(chunks_local)
            final_len = sum(len(c) for c in chunks_local) if chunks_local else 0
            return {
                "raw_count": raw_count,
                "dict_count": dict_count,
                "capped_count": capped_count,
                "chunk_count": chunk_count,
                "final_len": final_len,
            }

        def _fail_due_to_action_cap(
            action_name: str,
            *,
            step_list: Optional[List[Dict[str, Any]]] = None,
            force_name: bool = True,
        ) -> None:
            cap_value = int(args.max_subactions_per_function)
            diag = _step_chunk_diagnostics(step_list, cap_value)
            if diag["raw_count"] > 0 and diag["dict_count"] == 0:
                msg = (
                    f"Manual action '{action_name}' could not be written: 0 valid step objects out of "
                    f"{diag['raw_count']} model steps (cap={cap_value})."
                )
            elif force_name and diag["chunk_count"] > 1:
                msg = (
                    f"Manual action '{action_name}' would require split into {diag['chunk_count']} chunks "
                    f"to satisfy max subactions ({cap_value}); split write failed."
                )
            elif diag["raw_count"] == 0:
                msg = f"Manual action '{action_name}' could not be written: no steps were produced."
            else:
                msg = (
                    f"Manual action '{action_name}' exceeds max subactions ({cap_value}); "
                    f"steps={diag['raw_count']} capped={diag['capped_count']} chunks={diag['chunk_count']}."
                )
            _log_info(f"[error] {msg}")
            if defer_final:
                try:
                    maybe_save_final_shot(page, "FAIL")
                except Exception:
                    pass
                _log_final("FAIL", final_state)
            raise RuntimeError(msg)

        if outcome.verdict == "PASS":
            if (
                manual_actions
                and failed_manual_action
                and restart_for_llm
                and replay_ok
                and failed_target
            ):
                llm_repaired_action = failed_target
            manual_rewrite_candidates: List[str] = []
            manual_rewrite_confidence: Optional[float] = None
            manual_rewrite_reason = ""
            if (
                manual_actions
                and not missing_actions
                and not failed_manual_action
                and manual_verify_failed
            ):
                (
                    manual_rewrite_candidates,
                    manual_rewrite_confidence,
                    manual_rewrite_reason,
                ) = select_actions_to_rewrite_with_llm(
                    client,
                    args.model,
                    manual_actions,
                    page_model.get("functions", []),
                    args.prompt,
                    args.success_indicator.value,
                    manual_verify_why,
                    outcome.actions,
                    verbose=args.verbose,
                )
                if (
                    manual_rewrite_confidence is None
                    or manual_rewrite_confidence < DEFAULT_REWRITE_CONFIDENCE
                ):
                    manual_rewrite_candidates = []
                if args.verbose:
                    conf_note = (
                        f" (confidence={manual_rewrite_confidence:.2f})"
                        if manual_rewrite_confidence is not None
                        else ""
                    )
                    _log_info(
                        f"[LLM] Manual rewrite candidates: {manual_rewrite_candidates} - {manual_rewrite_reason}{conf_note}"
                    )
            if (
                manual_actions
                and not missing_actions
                and not failed_manual_action
                and not manual_rewrite_candidates
            ):
                if args.verbose:
                    _log_info(
                        "[playwright] Manual actions complete; skipping auto-creation of new actions."
                    )
                if defer_final:
                    try:
                        maybe_save_final_shot(page, "PASS")
                    except Exception:
                        pass
                    _log_final("PASS", final_state)
                context.close()
                browser.close()
                return
            steps = actions_to_model_steps(
                outcome.actions,
                username=username,
                password=password,
                prompt=args.prompt,
                rand_string=variables.get("rand_string"),
            )
            if manual_actions and completed_functions:
                steps = _strip_known_prefix_steps(
                    steps, page_model, completed_functions
                )
            if steps:
                functions_before_model_update = copy.deepcopy(
                    page_model.get("functions", [])
                    if isinstance(page_model.get("functions", []), list)
                    else []
                )
                if manual_actions:
                    if failed_manual_action:
                        preferred_names = [failed_manual_action]
                        for name in missing_actions:
                            if name != failed_manual_action:
                                preferred_names.append(name)
                    elif missing_actions:
                        preferred_names = missing_actions[:]
                    else:
                        preferred_names = manual_rewrite_candidates[:]
                else:
                    preferred_names = []
                split = None
                if page_model.get("functions"):
                    # Exclude any function that is about to be rewritten (preferred_names)
                    # from existing-function matching so all its steps stay together
                    # as a contiguous new segment for the LLM to reassemble correctly.
                    preferred_name_set = {n.lower() for n in preferred_names}
                    functions_for_segment_match = [
                        f
                        for f in page_model.get("functions", [])
                        if not (
                            isinstance(f, dict)
                            and str(f.get("name", "")).strip().lower()
                            in preferred_name_set
                        )
                    ]
                    forced_segments = split_steps_with_existing_functions(
                        steps, functions_for_segment_match
                    )
                    if forced_segments and any(
                        seg.get("type") == "new" for seg in forced_segments
                    ):
                        forced_split: Dict[str, List[Any]] = {
                            "sequence": [],
                            "new_functions": [],
                        }
                        for seg in forced_segments:
                            if seg.get("type") == "existing":
                                forced_split["sequence"].append(
                                    {"type": "existing", "name": str(seg.get("name"))}
                                )
                                continue
                            segment_steps = seg.get("steps", [])
                            if not isinstance(segment_steps, list) or not segment_steps:
                                continue
                            seg_split = split_steps_with_llm(
                                client,
                                args.model,
                                segment_steps,
                                args.prompt,
                                cap=int(args.max_subactions_per_function),
                            )
                            if (
                                seg_split
                                and seg_split.get("functions")
                                and seg_split.get("sequence")
                            ):
                                for func in seg_split.get("functions", []):
                                    if isinstance(func, dict):
                                        forced_split["new_functions"].append(func)
                                for name in seg_split.get("sequence", []):
                                    forced_split["sequence"].append(
                                        {"type": "new", "name": str(name)}
                                    )
                            else:
                                fallback_name = _suggest_function_name(
                                    segment_steps, args.prompt, args.start_url
                                )
                                forced_split["sequence"].append(
                                    {"type": "new", "name": fallback_name}
                                )
                                forced_split["new_functions"].append(
                                    {
                                        "name": fallback_name,
                                        "description": f"Auto-learned segment from prompt: {_replace_quoted_value(args.prompt, '{query}')}",
                                        "steps": segment_steps,
                                    }
                                )
                        if forced_split.get("sequence"):
                            split = forced_split
                    if not split:
                        split = split_steps_with_reuse_llm(
                            client,
                            args.model,
                            steps,
                            args.prompt,
                            page_model.get("functions", []),
                            cap=int(args.max_subactions_per_function),
                        )
                if not split:
                    split = split_steps_with_llm(
                        client,
                        args.model,
                        steps,
                        args.prompt,
                        cap=int(args.max_subactions_per_function),
                    )
                if split and split.get("sequence"):
                    name_map: Dict[str, str] = {}
                    existing_names = {
                        str(f.get("name", "")).strip().lower(): str(
                            f.get("name", "")
                        ).strip()
                        for f in page_model.get("functions", [])
                        if isinstance(f, dict) and str(f.get("name", "")).strip()
                    }
                    allowed_existing = {
                        str(f.get("name", "")).strip()
                        for f in page_model.get("functions", [])
                        if isinstance(f, dict)
                    }
                    new_funcs: Dict[str, Dict[str, Any]] = {}
                    raw_new_funcs = None
                    if isinstance(split.get("new_functions"), list):
                        raw_new_funcs = split["new_functions"]
                    elif isinstance(split.get("functions"), list):
                        raw_new_funcs = split["functions"]
                    if isinstance(raw_new_funcs, list):
                        for func in raw_new_funcs:
                            if isinstance(func, dict):
                                fname = _normalize_function_name(
                                    str(func.get("name") or "").strip()
                                )
                                if _is_generic_function_name(fname):
                                    fn_steps = func.get("steps")
                                    if isinstance(fn_steps, list) and fn_steps:
                                        fname = _suggest_function_name(
                                            fn_steps, args.prompt, args.start_url
                                        )
                                if fname and fname not in new_funcs:
                                    func["name"] = fname
                                    new_funcs[fname] = func

                    sequence_items: List[str] = []
                    updated_functions: List[str] = []
                    for item in split["sequence"]:
                        if isinstance(item, str):
                            if item in allowed_existing:
                                if (
                                    manual_actions
                                    and preferred_names
                                    and item.lower() == preferred_names[0].lower()
                                ):
                                    desired = preferred_names.pop(0)
                                    resummarized_steps = resummarize_steps_with_llm(
                                        client,
                                        args.model,
                                        steps,
                                        args.prompt,
                                        verbose=args.verbose,
                                    )
                                    fn_steps_force = _sanitize_model_steps(
                                        resummarized_steps or steps
                                    )
                                    if (
                                        manual_verify_failed
                                        and not failed_manual_action
                                        and desired not in manual_rewrite_candidates
                                    ):
                                        fn_steps_force = (
                                            _merge_existing_action_with_fallback_steps(
                                                page_model, desired, fn_steps_force
                                            )
                                        )
                                    if not fn_steps_force:
                                        _fail_due_to_action_cap(
                                            desired, step_list=steps, force_name=True
                                        )
                                    inferred_meta = _infer_function_metadata(
                                        fn_steps_force, args.prompt, args.start_url
                                    )
                                    existing_desc = (
                                        _existing_function_desc(page_model, desired)
                                        or ""
                                    )
                                    forced_desc = existing_desc or (
                                        f"Auto-learned from prompt: {_replace_quoted_value(args.prompt, '{query}')}"
                                    )
                                    added = add_function_with_subaction_cap(
                                        page_model,
                                        desired,
                                        description=forced_desc,
                                        steps=fn_steps_force,
                                        metadata=inferred_meta,
                                        cap=int(args.max_subactions_per_function),
                                        force_base_name=True,
                                        allow_overwrite=True,
                                        allow_split=True,
                                    )
                                    if not added:
                                        _fail_due_to_action_cap(
                                            desired,
                                            step_list=fn_steps_force,
                                            force_name=True,
                                        )
                                    updated_functions.extend(added)
                                    name_map[item] = added[0]
                                    if args.verbose:
                                        _log_info(
                                            f"[playwright] Forced overwrite for existing action '{desired}' using executed fallback steps."
                                        )
                                if not manual_actions:
                                    sequence_items.append(item)
                                continue
                            norm_name = _normalize_function_name(item)
                            if norm_name in new_funcs:
                                raw_name = norm_name
                                func = new_funcs.get(raw_name, {})
                                desc = str(func.get("description") or "").strip()
                                if query:
                                    raw_name = raw_name.replace(query, "query")
                                    desc = (
                                        desc.replace(query, "{query}") if desc else desc
                                    )
                                desired = raw_name
                                if manual_actions and not preferred_names:
                                    continue
                                force_name = bool(preferred_names)
                                if force_name:
                                    desired = preferred_names[0]
                                fn_steps = _sanitize_model_steps(func.get("steps"))
                                if force_name:
                                    recorded_steps = _replace_query_in_steps(
                                        _sanitize_model_steps(steps),
                                        variables.get("query") or "",
                                    )
                                    _CLICK_LIKE = frozenset(
                                        (
                                            "click",
                                            "left_click",
                                            "triple_click",
                                            "double_click",
                                        )
                                    )

                                    def _has_click_before_type(sl):
                                        for _s in sl:
                                            if not isinstance(_s, dict):
                                                continue
                                            _a = str(_s.get("action", "")).lower()
                                            if _a == "type":
                                                return False
                                            if _a in _CLICK_LIKE:
                                                return True
                                        return False

                                    rec_has_type = any(
                                        str(s.get("action", "")).lower() == "type"
                                        for s in recorded_steps
                                        if isinstance(s, dict)
                                    )
                                    fn_has_type = any(
                                        str(s.get("action", "")).lower() == "type"
                                        for s in fn_steps
                                        if isinstance(s, dict)
                                    )
                                    rec_click_before_type = _has_click_before_type(
                                        recorded_steps
                                    )
                                    fn_click_before_type = _has_click_before_type(
                                        fn_steps
                                    )
                                    use_recorded = True
                                    fallback_reason = "Named action always uses recorded steps (Option B)"
                                    if use_recorded:
                                        fn_steps = recorded_steps
                                        if args.verbose:
                                            _log_warn(
                                                f"[playwright] {fallback_reason} for '{desired}'; using executed fallback steps."
                                            )
                                if not fn_steps:
                                    continue
                                if _is_generic_function_name(raw_name):
                                    raw_name = _suggest_function_name(
                                        fn_steps, args.prompt, args.start_url
                                    )
                                existing_name = existing_names.get(raw_name.lower())
                                if existing_name and not force_name:
                                    existing_desc = (
                                        _existing_function_desc(
                                            page_model, existing_name
                                        )
                                        or ""
                                    )
                                    if existing_desc and not existing_desc.startswith(
                                        "Auto-learned"
                                    ):
                                        name_map[raw_name] = existing_name
                                        sequence_items.append(existing_name)
                                        continue
                                if force_name:
                                    preferred_names.pop(0)
                                existing_desc = (
                                    _existing_function_desc(page_model, desired) or ""
                                )
                                if (
                                    existing_desc
                                    and not existing_desc.startswith("Auto-learned")
                                    and not force_name
                                ):
                                    desired = _pick_unique_function_name(
                                        page_model, desired
                                    )
                                inferred_meta = _infer_function_metadata(
                                    fn_steps, args.prompt, args.start_url
                                )
                                explicit_meta = _extract_function_metadata(func)
                                merged_meta = _merge_function_metadata(
                                    inferred_meta, explicit_meta
                                )
                                added = add_function_with_subaction_cap(
                                    page_model,
                                    desired,
                                    description=desc
                                    or f"Auto-learned from prompt: {_replace_quoted_value(args.prompt, '{query}')}",
                                    steps=fn_steps,
                                    metadata=merged_meta,
                                    cap=int(args.max_subactions_per_function),
                                    force_base_name=force_name,
                                    allow_overwrite=force_name,
                                    allow_split=(
                                        not force_name or bool(manual_actions)
                                    ),
                                )
                                if force_name and not added:
                                    _fail_due_to_action_cap(
                                        desired,
                                        step_list=fn_steps,
                                        force_name=force_name,
                                    )
                                if added:
                                    name_map[raw_name] = added[0]
                                    updated_functions.extend(added)
                                    sequence_items.extend(added)
                            continue
                        if not isinstance(item, dict):
                            continue
                        item_type = str(item.get("type") or "").strip().lower()
                        raw_name = _normalize_function_name(
                            str(item.get("name") or "").strip()
                        )
                        if not raw_name:
                            continue
                        if item_type == "existing":
                            if raw_name in allowed_existing:
                                if (
                                    manual_actions
                                    and preferred_names
                                    and raw_name.lower() == preferred_names[0].lower()
                                ):
                                    desired = preferred_names.pop(0)
                                    resummarized_steps = resummarize_steps_with_llm(
                                        client,
                                        args.model,
                                        steps,
                                        args.prompt,
                                        verbose=args.verbose,
                                    )
                                    fn_steps_force = _sanitize_model_steps(
                                        resummarized_steps or steps
                                    )
                                    if (
                                        manual_verify_failed
                                        and not failed_manual_action
                                        and desired not in manual_rewrite_candidates
                                    ):
                                        fn_steps_force = (
                                            _merge_existing_action_with_fallback_steps(
                                                page_model, desired, fn_steps_force
                                            )
                                        )
                                    if not fn_steps_force:
                                        _fail_due_to_action_cap(
                                            desired, step_list=steps, force_name=True
                                        )
                                    inferred_meta = _infer_function_metadata(
                                        fn_steps_force, args.prompt, args.start_url
                                    )
                                    existing_desc = (
                                        _existing_function_desc(page_model, desired)
                                        or ""
                                    )
                                    forced_desc = existing_desc or (
                                        f"Auto-learned from prompt: {_replace_quoted_value(args.prompt, '{query}')}"
                                    )
                                    added = add_function_with_subaction_cap(
                                        page_model,
                                        desired,
                                        description=forced_desc,
                                        steps=fn_steps_force,
                                        metadata=inferred_meta,
                                        cap=int(args.max_subactions_per_function),
                                        force_base_name=True,
                                        allow_overwrite=True,
                                        allow_split=True,
                                    )
                                    if not added:
                                        _fail_due_to_action_cap(
                                            desired,
                                            step_list=fn_steps_force,
                                            force_name=True,
                                        )
                                    updated_functions.extend(added)
                                    name_map[raw_name] = added[0]
                                    if args.verbose:
                                        _log_info(
                                            f"[playwright] Forced overwrite for existing action '{desired}' using executed fallback steps."
                                        )
                                sequence_items.append(raw_name)
                            continue
                        if item_type != "new":
                            continue
                        if raw_name in name_map:
                            sequence_items.append(name_map[raw_name])
                            continue
                        func = new_funcs.get(raw_name, {})
                        desc = str(func.get("description") or "").strip()
                        if query:
                            raw_name = raw_name.replace(query, "query")
                            desc = desc.replace(query, "{query}") if desc else desc
                        desired = raw_name
                        if manual_actions and not preferred_names:
                            continue
                        force_name = bool(preferred_names)
                        if force_name:
                            desired = preferred_names[0]
                        fn_steps = _sanitize_model_steps(func.get("steps"))
                        if force_name:
                            recorded_steps = _replace_query_in_steps(
                                _sanitize_model_steps(steps),
                                variables.get("query") or "",
                            )
                            _CLICK_LIKE2 = frozenset(
                                ("click", "left_click", "triple_click", "double_click")
                            )

                            def _has_click_before_type2(sl):
                                for _s in sl:
                                    if not isinstance(_s, dict):
                                        continue
                                    _a = str(_s.get("action", "")).lower()
                                    if _a == "type":
                                        return False
                                    if _a in _CLICK_LIKE2:
                                        return True
                                return False

                            rec_has_type2 = any(
                                str(s.get("action", "")).lower() == "type"
                                for s in recorded_steps
                                if isinstance(s, dict)
                            )
                            fn_has_type2 = any(
                                str(s.get("action", "")).lower() == "type"
                                for s in fn_steps
                                if isinstance(s, dict)
                            )
                            rec_click_before_type2 = _has_click_before_type2(
                                recorded_steps
                            )
                            fn_click_before_type2 = _has_click_before_type2(fn_steps)
                            use_recorded2 = True
                            fallback_reason2 = (
                                "Named action always uses recorded steps (Option B)"
                            )
                            if use_recorded2:
                                fn_steps = recorded_steps
                                if args.verbose:
                                    _log_warn(
                                        f"[playwright] {fallback_reason2} for '{desired}'; using executed fallback steps."
                                    )
                        if not fn_steps:
                            continue
                        if _is_generic_function_name(raw_name):
                            raw_name = _suggest_function_name(
                                fn_steps, args.prompt, args.start_url
                            )
                        existing_name = existing_names.get(raw_name.lower())
                        if existing_name and not force_name:
                            existing_desc = (
                                _existing_function_desc(page_model, existing_name) or ""
                            )
                            if existing_desc and not existing_desc.startswith(
                                "Auto-learned"
                            ):
                                name_map[raw_name] = existing_name
                                sequence_items.append(existing_name)
                                continue
                        if force_name:
                            preferred_names.pop(0)
                            pre_resummarize_len = len(fn_steps)
                        existing_desc = (
                            _existing_function_desc(page_model, desired) or ""
                        )
                        if (
                            existing_desc
                            and not existing_desc.startswith("Auto-learned")
                            and not force_name
                        ):
                            desired = _pick_unique_function_name(page_model, desired)
                        inferred_meta = _infer_function_metadata(
                            fn_steps, args.prompt, args.start_url
                        )
                        explicit_meta = _extract_function_metadata(func)
                        merged_meta = _merge_function_metadata(
                            inferred_meta, explicit_meta
                        )
                        added = add_function_with_subaction_cap(
                            page_model,
                            desired,
                            description=desc
                            or f"Auto-learned from prompt: {_replace_quoted_value(args.prompt, '{query}')}",
                            steps=fn_steps,
                            metadata=merged_meta,
                            cap=int(args.max_subactions_per_function),
                            force_base_name=force_name,
                            allow_overwrite=force_name,
                            allow_split=(not force_name or bool(manual_actions)),
                        )
                        if args.verbose and force_name:
                            diag = _step_chunk_diagnostics(
                                fn_steps, int(args.max_subactions_per_function)
                            )
                            _log_info(
                                f"[LLM] Final steps for '{desired}': raw={pre_resummarize_len} "
                                f"valid={diag['dict_count']} capped={diag['capped_count']} "
                                f"chunks={diag['chunk_count']} retained={diag['final_len']}"
                            )
                        if force_name and not added:
                            _fail_due_to_action_cap(
                                desired, step_list=fn_steps, force_name=force_name
                            )
                        if added:
                            name_map[raw_name] = added[0]
                            updated_functions.extend(added)
                            if not manual_actions:
                                sequence_items.extend(added)

                    # Fallback: if preferred_names still has unconsumed entries after
                    # the sequence loop (e.g. the LLM split mapped all steps to an
                    # existing function instead of creating a new one), force-create
                    # each remaining action from the raw steps.
                    if manual_actions and preferred_names and steps:
                        for leftover_name in list(preferred_names):
                            _log_warn(
                                f"[playwright] Preferred action '{leftover_name}' was not "
                                f"produced by split; force-creating from raw steps."
                            )
                            inferred_meta = _infer_function_metadata(
                                steps, args.prompt, args.start_url
                            )
                            existing_desc = (
                                _existing_function_desc(page_model, leftover_name) or ""
                            )
                            forced_desc = existing_desc or (
                                f"Auto-learned from prompt: {_replace_quoted_value(args.prompt, '{query}')}"
                            )
                            added = add_function_with_subaction_cap(
                                page_model,
                                leftover_name,
                                description=forced_desc,
                                steps=steps,
                                metadata=inferred_meta,
                                cap=int(args.max_subactions_per_function),
                                force_base_name=True,
                                allow_overwrite=True,
                                allow_split=True,
                            )
                            if added:
                                updated_functions.extend(added)
                        preferred_names.clear()

                    if sequence_items or (manual_actions and updated_functions):
                        current_functions = page_model.get("functions", [])
                        if (
                            isinstance(functions_before_model_update, list)
                            and functions_before_model_update
                            and (
                                not isinstance(current_functions, list)
                                or not current_functions
                            )
                        ):
                            _log_error(
                                "[playwright] Refusing to persist an empty 'functions' list; restoring previous model functions."
                            )
                            page_model["functions"] = functions_before_model_update
                        if sequence_items and not manual_actions:
                            set_prompt_route(
                                page_model,
                                args.prompt,
                                sequence_items,
                                page_model.get("functions", []),
                            )
                        save_page_model(model_path, page_model)
                        if manual_actions:
                            wrote_names = [n for n in updated_functions if n]
                            if not wrote_names:
                                fallback_names: List[str] = []
                                if manual_rewrite_candidates:
                                    fallback_names.extend(manual_rewrite_candidates)
                                if missing_actions:
                                    fallback_names.extend(missing_actions)
                                if failed_manual_action:
                                    fallback_names.append(failed_manual_action)
                                if llm_repaired_action:
                                    fallback_names.append(llm_repaired_action)
                                # Keep stable ordering while removing duplicates.
                                wrote_names = list(dict.fromkeys(fallback_names))
                                _log_warn(
                                    f"[playwright] No function definitions changed; preserving existing functions for {wrote_names}."
                                )
                            _log_info(
                                f"[playwright] Wrote model functions {wrote_names} in {model_path}"
                            )
                        else:
                            _log_info(
                                f"[playwright] Wrote model functions {sequence_items} in {model_path}"
                            )
                else:
                    generic_prompt = _replace_quoted_value(args.prompt, "query")
                    base_name = _normalize_function_name(
                        _prompt_to_func_name(generic_prompt)
                    )
                    if _is_generic_function_name(base_name):
                        base_name = _suggest_function_name(
                            steps, args.prompt, args.start_url
                        )
                    target_name = _pick_unique_function_name(page_model, base_name)
                    description = f"Auto-learned from AgenticWebQA `fallback for prompt: {_replace_quoted_value(args.prompt, '{query}')}"
                    if manual_actions and not preferred_names:
                        if args.verbose:
                            _log_info(
                                "[playwright] Manual actions complete; skipping auto-creation."
                            )
                        save_page_model(model_path, page_model)
                        context.close()
                        browser.close()
                        return
                    force_name = False
                    if preferred_names:
                        target_name = preferred_names.pop(0)
                        force_name = True
                    added = add_function_with_subaction_cap(
                        page_model,
                        target_name,
                        description=description,
                        steps=steps,
                        metadata=_infer_function_metadata(
                            steps, args.prompt, args.start_url
                        ),
                        cap=int(args.max_subactions_per_function),
                        force_base_name=force_name,
                        allow_overwrite=force_name,
                        allow_split=(not force_name or bool(manual_actions)),
                    )
                    if force_name and not added:
                        _fail_due_to_action_cap(
                            target_name, step_list=steps, force_name=force_name
                        )
                    if not added:
                        if not force_name:
                            added = [target_name]
                        else:
                            added = []
                    if added and not manual_actions:
                        set_prompt_route(
                            page_model,
                            args.prompt,
                            added,
                            page_model.get("functions", []),
                        )
                    save_page_model(model_path, page_model)
                    _log_info(
                        f"[playwright] Wrote model function '{target_name}' in {model_path}"
                    )

            # If manual actions were requested but some are still absent from the
            # model after the save logic above (e.g. the LLM succeeded via screenshot
            # only, recording no interactive steps), persist a no-op screenshot stub
            # so that run 2 can replay without falling back to LLM.
            if manual_actions:
                saved_names = {
                    str(f.get("name", "")).strip().lower()
                    for f in page_model.get("functions", [])
                    if isinstance(f, dict)
                }
                unsaved_stubs = [
                    a for a in manual_actions if a.strip().lower() not in saved_names
                ]
                if unsaved_stubs:
                    stub_step: Dict[str, Any] = {"action": "screenshot"}
                    for stub_name in unsaved_stubs:
                        add_function_with_subaction_cap(
                            page_model,
                            stub_name,
                            description=(
                                f"No-op stub: task already satisfied on page load. "
                                f"Prompt: {_replace_quoted_value(args.prompt, '{query}')}"
                            ),
                            steps=[stub_step],
                            metadata=_infer_function_metadata(
                                [stub_step], args.prompt, args.start_url
                            ),
                            cap=int(args.max_subactions_per_function),
                            force_base_name=True,
                            allow_overwrite=True,
                            allow_split=False,
                        )
                        _log_info(
                            f"[playwright] Saved no-op stub for '{stub_name}' "
                            f"(task already satisfied, no interactive steps recorded) in {model_path}"
                        )
                    save_page_model(model_path, page_model)

            if manual_actions and failed_manual_action:
                resume_from = len(completed_functions)
                resume_list = manual_actions[resume_from:]
                if (
                    llm_repaired_action
                    and resume_list
                    and resume_list[0] == llm_repaired_action
                ):
                    resume_list = resume_list[1:]
                if resume_list:
                    available = {
                        str(f.get("name"))
                        for f in page_model.get("functions", [])
                        if isinstance(f, dict)
                    }
                    missing_resume = [a for a in resume_list if a not in available]
                    if missing_resume:
                        raise RuntimeError(
                            f"Manual actions missing after repair: {missing_resume}"
                        )
                    if args.verbose:
                        _log_info(
                            f"[playwright] Resuming remaining manual actions: {resume_list}"
                        )
                    ok, failed_func, err, page = execute_model_sequence(
                        page,
                        page_model,
                        resume_list,
                        variables,
                        verbose=args.verbose,
                        pre_type_sleep_s=args.pre_type_sleep,
                        post_type_sleep_s=args.post_type_sleep,
                        post_action_sleep_s=args.post_action_sleep,
                        enable_agent_view=enable_agent_view,
                        agent_view_dir=args.agent_view_dir,
                        x_size_px=args.x_size,
                        x_thickness_px=args.x_thickness,
                    )
                    if not ok:
                        raise RuntimeError(
                            f"Manual action '{failed_func}' failed after repair: {err}"
                        )
                page = maybe_switch_to_new_tab(context, page, verbose=args.verbose)
                final_verify_png = capture_model_screenshot_png(
                    page,
                    actual_w=viewport.width,
                    actual_h=viewport.height,
                    model_w=model_viewport.width,
                    model_h=model_viewport.height,
                )
                _resume_history = "\n".join(
                    f"{i + 1}. {name}" for i, name in enumerate(manual_actions or [])
                )
                verify_ok, verify_verdict, verify_why, verify_confidence, verify_png = (
                    verify_success_with_llm(
                        client,
                        args.model,
                        page,
                        args.success_indicator.value,
                        viewport=viewport,
                        model_viewport=model_viewport,
                        verify_wait_s=args.verify_wait,
                        png_bytes=final_verify_png,
                        task_prompt=args.prompt,
                        action_history=_resume_history,
                    )
                )
                if not verify_ok:
                    try:
                        maybe_save_final_shot(page, "FAIL", png_bytes=verify_png)
                    except Exception:
                        pass
                    raise RuntimeError(
                        f"Success criteria failed after resuming actions: {verify_verdict} - {verify_why}"
                    )
                if args.verbose:
                    conf_note = (
                        f" (confidence={verify_confidence:.2f})"
                        if verify_confidence is not None
                        else ""
                    )
                    _log_info(
                        f"[LLM] Sequence completed and success criteria confirmed: {verify_why}{conf_note}"
                    )
                try:
                    maybe_save_final_shot(page, "PASS", png_bytes=verify_png)
                except Exception:
                    pass
                _log_final("PASS", final_state)
                context.close()
                browser.close()
                return

        if defer_final and outcome.verdict != "PASS":
            try:
                maybe_save_final_shot(page, "FAIL")
            except Exception:
                pass
            _log_final("FAIL", final_state)
        if defer_final and outcome.verdict == "PASS":
            try:
                maybe_save_final_shot(page, "PASS")
            except Exception:
                pass
            _log_final("PASS", final_state)
        context.close()
        browser.close()
        if outcome.verdict != "PASS":
            raise SystemExit(-1)


if __name__ == "__main__":
    main()
