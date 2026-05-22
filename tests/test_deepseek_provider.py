from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from config_shared import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL_OPTIONS,
    MODEL_OPTIONS,
    infer_model_provider,
    model_api_env_var,
)
import vision_playwright_openai_vision_poc as poc


# ---------------------------------------------------------------------------
# TEST-UNIT-DEEPSEEK-001
# ---------------------------------------------------------------------------


def test_infer_model_provider_returns_deepseek_for_deepseek_models() -> None:
    for model in DEEPSEEK_MODEL_OPTIONS:
        assert infer_model_provider(model) == "deepseek", (
            f"Expected 'deepseek' for model '{model}'"
        )


def test_infer_model_provider_deepseek_prefix_variants() -> None:
    assert infer_model_provider("deepseek-v4-flash") == "deepseek"
    assert infer_model_provider("deepseek-v4-pro") == "deepseek"
    assert infer_model_provider("DEEPSEEK-V4-FLASH") == "deepseek"


def test_model_api_env_var_returns_deepseek_key_for_deepseek() -> None:
    assert model_api_env_var("deepseek-v4-flash") == "DEEPSEEK_API_KEY"
    assert model_api_env_var("deepseek-v4-pro") == "DEEPSEEK_API_KEY"


# ---------------------------------------------------------------------------
# TEST-UNIT-DEEPSEEK-002
# ---------------------------------------------------------------------------


def test_deepseek_model_options_is_nonempty() -> None:
    assert len(DEEPSEEK_MODEL_OPTIONS) >= 2


def test_deepseek_model_options_all_start_with_deepseek() -> None:
    for m in DEEPSEEK_MODEL_OPTIONS:
        assert m.startswith("deepseek"), f"Expected 'deepseek' prefix, got '{m}'"


def test_deepseek_model_options_present_in_model_options() -> None:
    for m in DEEPSEEK_MODEL_OPTIONS:
        assert m in MODEL_OPTIONS, f"'{m}' missing from MODEL_OPTIONS"


# ---------------------------------------------------------------------------
# TEST-UNIT-DEEPSEEK-003
# ---------------------------------------------------------------------------


def test_new_model_client_returns_deepseek_provider() -> None:
    fake_client = MagicMock()
    with patch.object(poc, "_new_deepseek_client", return_value=fake_client):
        adapter = poc._new_model_client("deepseek-v4-flash", "fake-key")
    assert adapter.provider == "deepseek"


def test_new_model_client_deepseek_uses_deepseek_client_factory() -> None:
    captured: list[str] = []

    def _fake_deepseek_client(api_key: str) -> MagicMock:
        captured.append(api_key)
        return MagicMock()

    with patch.object(poc, "_new_deepseek_client", side_effect=_fake_deepseek_client):
        poc._new_model_client("deepseek-v4-flash", "my-deepseek-key")

    assert captured == ["my-deepseek-key"]


def test_new_deepseek_client_uses_correct_base_url() -> None:
    """_new_deepseek_client must pass DEEPSEEK_BASE_URL to the OpenAI constructor."""
    calls: list[dict] = []

    class _FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            calls.append(dict(kwargs))

    with patch.object(poc, "OpenAI", _FakeOpenAI):
        poc._new_deepseek_client("test-key")

    assert len(calls) == 1
    assert calls[0]["api_key"] == "test-key"
    assert calls[0]["base_url"] == DEEPSEEK_BASE_URL


# ---------------------------------------------------------------------------
# TEST-UNIT-DEEPSEEK-004
# ---------------------------------------------------------------------------


def test_appstate_has_deepseek_key_var_field() -> None:
    import dataclasses
    from ui.ui_state import AppState

    field_names = {f.name for f in dataclasses.fields(AppState)}
    assert "deepseek_key_var" in field_names, (
        "AppState is missing 'deepseek_key_var' field"
    )


def test_run_lifecycle_rejects_missing_deepseek_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_run_lifecycle must not launch when DeepSeek model selected and key is empty."""
    import tkinter as tk
    from unittest.mock import MagicMock
    from ui.ui_run_lifecycle import build_run_lifecycle
    from ui.ui_state import AppState

    # A real Tk root is required before creating tk.StringVar instances.
    try:
        tk_root = tk.Tk()
    except tk.TclError:
        pytest.skip("No $DISPLAY available for Tkinter tests")
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
            deepseek_key_var=tk.StringVar(value=""),
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
            model_var = tk.StringVar(value="deepseek-v4-flash")
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

    assert not launched, "Subprocess should NOT have launched without DeepSeek key"
    assert any("DEEPSEEK_API_KEY" in msg for msg in error_shown), (
        f"Expected missing-key error for DEEPSEEK_API_KEY, got: {error_shown}"
    )
