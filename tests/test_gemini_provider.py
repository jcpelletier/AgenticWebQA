from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from config_shared import (
    GEMINI_BASE_URL,
    GEMINI_MODEL_OPTIONS,
    MODEL_OPTIONS,
    infer_model_provider,
    model_api_env_var,
)
import vision_playwright_openai_vision_poc as poc


# ---------------------------------------------------------------------------
# TEST-UNIT-GEMINI-001  (REQ-1, REQ-2)
# ---------------------------------------------------------------------------


def test_infer_model_provider_returns_gemini_for_gemini_models() -> None:
    for model in GEMINI_MODEL_OPTIONS:
        assert infer_model_provider(model) == "gemini", (
            f"Expected 'gemini' for model '{model}'"
        )


def test_infer_model_provider_gemini_prefix_variants() -> None:
    assert infer_model_provider("gemini-2.0-flash") == "gemini"
    assert infer_model_provider("gemini-1.5-pro") == "gemini"
    assert infer_model_provider("GEMINI-2.0-flash") == "gemini"


def test_infer_model_provider_non_gemini_unchanged() -> None:
    assert infer_model_provider("gpt-5.1") == "openai"
    assert infer_model_provider("claude-sonnet-4-6") == "anthropic"


def test_model_api_env_var_returns_gemini_key_for_gemini() -> None:
    assert model_api_env_var("gemini-2.0-flash") == "GEMINI_API_KEY"
    assert model_api_env_var("gemini-1.5-pro") == "GEMINI_API_KEY"


def test_model_api_env_var_non_gemini_unchanged() -> None:
    assert model_api_env_var("gpt-5.1") == "OPENAI_API_KEY"
    assert model_api_env_var("claude-sonnet-4-6") == "ANTHROPIC_API_KEY"


# ---------------------------------------------------------------------------
# TEST-UNIT-GEMINI-002  (REQ-3)
# ---------------------------------------------------------------------------


def test_gemini_model_options_is_nonempty() -> None:
    assert len(GEMINI_MODEL_OPTIONS) >= 1


def test_gemini_model_options_all_start_with_gemini() -> None:
    for m in GEMINI_MODEL_OPTIONS:
        assert m.startswith("gemini"), f"Expected 'gemini' prefix, got '{m}'"


def test_gemini_model_options_present_in_model_options() -> None:
    for m in GEMINI_MODEL_OPTIONS:
        assert m in MODEL_OPTIONS, f"'{m}' missing from MODEL_OPTIONS"


def test_model_options_preserves_openai_and_claude_entries() -> None:
    openai_models = [m for m in MODEL_OPTIONS if m.startswith("gpt-")]
    claude_models = [m for m in MODEL_OPTIONS if m.startswith("claude-")]
    assert len(openai_models) >= 1, "OpenAI models missing from MODEL_OPTIONS"
    assert len(claude_models) >= 3, "Claude models missing from MODEL_OPTIONS"


# ---------------------------------------------------------------------------
# TEST-UNIT-GEMINI-003  (REQ-7)
# ---------------------------------------------------------------------------


def test_new_model_client_returns_gemini_provider() -> None:
    fake_client = MagicMock()
    with patch.object(poc, "_new_gemini_client", return_value=fake_client):
        adapter = poc._new_model_client("gemini-2.0-flash", "fake-key")
    assert adapter.provider == "gemini"


def test_new_model_client_gemini_uses_gemini_client_factory() -> None:
    captured: list[str] = []

    def _fake_gemini_client(api_key: str) -> MagicMock:
        captured.append(api_key)
        return MagicMock()

    with patch.object(poc, "_new_gemini_client", side_effect=_fake_gemini_client):
        poc._new_model_client("gemini-2.0-flash", "my-gemini-key")

    assert captured == ["my-gemini-key"]


def test_new_gemini_client_uses_correct_base_url() -> None:
    """_new_gemini_client must pass GEMINI_BASE_URL to the OpenAI constructor."""
    calls: list[dict] = []

    class _FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            calls.append(dict(kwargs))

    with patch.object(poc, "OpenAI", _FakeOpenAI):
        poc._new_gemini_client("test-key")

    assert len(calls) == 1
    assert calls[0]["api_key"] == "test-key"
    assert calls[0]["base_url"] == GEMINI_BASE_URL


def test_new_model_client_non_gemini_unchanged() -> None:
    fake_openai = MagicMock()
    fake_anthropic = MagicMock()
    with (
        patch.object(poc, "_new_openai_client", return_value=fake_openai),
        patch.object(poc, "_new_anthropic_client", return_value=fake_anthropic),
    ):
        openai_adapter = poc._new_model_client("gpt-5.1", "key")
        anthropic_adapter = poc._new_model_client("claude-sonnet-4-6", "key")

    assert openai_adapter.provider == "openai"
    assert anthropic_adapter.provider == "anthropic"


# ---------------------------------------------------------------------------
# TEST-UNIT-GEMINI-004  (REQ-5, REQ-6)
# ---------------------------------------------------------------------------


def test_appstate_has_gemini_key_var_field() -> None:
    import dataclasses
    from ui.ui_state import AppState

    field_names = {f.name for f in dataclasses.fields(AppState)}
    assert "gemini_key_var" in field_names, "AppState is missing 'gemini_key_var' field"


def test_run_lifecycle_rejects_missing_gemini_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_run_lifecycle must not launch when Gemini model selected and key is empty."""
    import tkinter as tk
    from unittest.mock import MagicMock
    from ui.ui_run_lifecycle import build_run_lifecycle
    from ui.ui_state import AppState

    # A real Tk root is required before creating tk.StringVar instances.
    tk_root = tk.Tk()
    tk_root.withdraw()
    try:
        root = MagicMock()
        log_text = MagicMock()
        log_text.yview.return_value = (0.0, 1.0)

        vars_map: dict[str, tk.Variable] = {}
        app = AppState(
            root=root,
            vars_map=vars_map,
            prompt_tabs=MagicMock(),
            plus_tab=MagicMock(),
            log_text=log_text,
            log_queue=MagicMock(),
            continue_button=MagicMock(),
            openai_key_var=tk.StringVar(value=""),
            anthropic_key_var=tk.StringVar(value=""),
            gemini_key_var=tk.StringVar(value=""),
        )

        error_shown: list[str] = []

        import ui.ui_run_lifecycle as lifecycle_mod

        monkeypatch.setattr(
            lifecycle_mod.messagebox,
            "showerror",
            lambda title, msg: error_shown.append(msg),
        )

        launched: list[bool] = []

        def _fake_launch(cmd: list, *, cwd: str, env: dict) -> MagicMock:
            launched.append(True)
            return MagicMock()

        def _fake_get_fields() -> tuple:
            model_var = tk.StringVar(value="gemini-2.0-flash")
            return (
                MagicMock(),
                MagicMock(),
                tk.StringVar(),
                tk.StringVar(),
                model_var,
                tk.StringVar(),
            )

        def _fake_collect(
            vm: object,
            pw: object,
            sw: object,
            stv: object,
            suv: object,
            mv: tk.StringVar,
            av: object,
        ) -> dict:
            return {"-MODEL-": mv.get()}

        def _fake_build_cmd(values: dict, signal: object) -> list:
            return ["python", "script.py"]

        lifecycle = build_run_lifecycle(
            app=app,
            root=root,
            prompt_tabs=MagicMock(),
            prompt_state=MagicMock(),
            vars_map=vars_map,
            apply_api_key=lambda: None,
            get_active_prompt_fields=_fake_get_fields,
            collect_values=_fake_collect,
            build_command=_fake_build_cmd,
            script_path=lambda: MagicMock(__class__=MagicMock, exists=lambda: True),
            launch_command=_fake_launch,
            poll_log=lambda *a, **kw: None,
            set_run_state=lambda r: None,
            append_log=lambda a, t: None,
            save_ui_state_snapshot=lambda: None,
            update_info_bar_text=lambda t: None,
            clear_agent_view_images=lambda v: None,
            ai_view=MagicMock(),
            set_prompt_running_visual=lambda s, t, r: None,
            clean_running_suffixes=lambda s: None,
        )
        lifecycle.run_script()
    finally:
        tk_root.destroy()

    assert not launched, "Subprocess should NOT have launched without Gemini key"
    assert any("GEMINI_API_KEY" in msg for msg in error_shown), (
        f"Expected missing-key error for GEMINI_API_KEY, got: {error_shown}"
    )
