#!/usr/bin/env python3
"""
Tkinter launcher for vision_playwright_openai_vision_poc.py.
Builds a full CLI argument list and spawns the main script.
"""

from __future__ import annotations

import os
import json
import sys
import subprocess
import queue
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import tkinter as tk
from config_shared import (
    DEFAULT_MODEL,
    build_shared_ui_defaults,
    build_shared_ui_cli_args,
    ui_spec_by_key,
)

try:
    import ttkbootstrap as ttk
except ModuleNotFoundError:
    # Attempt a best-effort install so first-run UX is smoother.
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "ttkbootstrap"])
        import ttkbootstrap as ttk
    except Exception as exc:
        raise ModuleNotFoundError(
            "ttkbootstrap is required for the UI. Install it with: python -m pip install ttkbootstrap"
        ) from exc
from tkinter import messagebox

from ui.ui_actions_library import build_actions_library_tab, refresh_actions_list
from ui.ui_app import build_root_layout
from ui.ui_ai_view import (
    build_ai_view_tab,
    clear_agent_view_images,
    list_ai_images,
    poll_ai_view,
    refresh_ai_view,
)
from ui.ui_prompt_tabs import (
    SUCCESS_LABEL_TO_ARG,
    SUCCESS_TYPE_DEFAULT,
    build_prompt_tabs_panel,
    clean_running_suffixes,
    create_prompt_tab,
    get_active_prompt_fields_from_state,
    get_prompt_tabs,
    get_prompt_state_snapshot,
    get_tab_display_name,
    set_prompt_running_visual,
)
from ui.ui_info_bar import build_info_bar_controller
from ui.ui_run_control import (
    build_credentials_tab,
    build_run_button_bar,
    build_run_log_panel,
)
from ui.ui_run_lifecycle import build_run_lifecycle
from ui.ui_restore_state import (
    RestoreContext,
    apply_initial_window_layout,
    restore_ui_state,
)
from ui.ui_settings_tabs import (
    build_action_settings_tab,
    build_browser_tab,
    build_output_tab,
    build_tokens_tab,
)
from ui.ui_state import AppState, PromptTabsState


REQUIRED_STATE_PATH = (
    Path(__file__).resolve().parent / "vision_playwright_openai_vision_ui.required.tmp"
)
LABEL_WIDTH = 18
RUNNING_TINT_BG = "#ffecec"
UI_SETTINGS_KEYS: Tuple[str, ...] = (
    "-WIDTH-",
    "-HEIGHT-",
    "-MODEL-W-",
    "-MODEL-H-",
    "-HEADLESS-",
    "-STEP-TRAIN-",
    "-SLOWMO-",
    "-MAX-STEPS-",
    "-MAX-TOKENS-",
    "-MAX-TOK-MARGIN-",
    "-VERIFY-WAIT-",
    "-VERIFY-GUARD-CONF-",
    "-PRECLICK-",
    "-PRETYPE-",
    "-POST-SHOT-",
    "-POST-ACTION-",
    "-POST-TYPE-",
    "-ARM-COMMIT-",
    "-CONFIRM-",
    "-MAX-SUBACTIONS-",
    "-ARM-TIMEOUT-",
    "-SCREENSHOT-",
    "-AGENT-DIR-",
    "-NO-AGENT-",
    "-LOG-FILE-",
    "-AZURE-",
    "-SITE-HINTS-",
    "-KEEP-TURNS-",
    "-KEEP-IMAGES-",
    "-VERBOSE-",
)
UI_KEYS_MANAGED_OUTSIDE_VARS_MAP: Tuple[str, ...] = (
    "-MODEL-",
    "-ACTIONS-",
)


def _append_log(app: AppState, text: str) -> None:
    auto_scroll = app.log_text.yview()[1] >= 0.99
    app.log_text.configure(state="normal")
    app.log_text.insert("end", text)
    if auto_scroll:
        app.log_text.see("end")
    app.log_text.configure(state="disabled")


def _set_continue_state(app: AppState) -> None:
    enabled = (
        app.running_state
        and bool(app.vars_map["-STEP-TRAIN-"].get())
        and not bool(app.vars_map["-HEADLESS-"].get())
    )
    app.continue_button.configure(state="normal" if enabled else "disabled")


def _send_step_training_continue(app: AppState) -> None:
    if app.step_training_signal_path is None:
        return
    app.step_training_token += 1
    try:
        app.step_training_signal_path.write_text(
            str(app.step_training_token), encoding="utf-8"
        )
    except Exception as exc:
        messagebox.showerror("Step Training", f"Failed to write continue signal: {exc}")
        return
    _append_log(app, "[UI] Continue requested.\n")


def _poll_log(
    app: AppState,
    *,
    set_run_state: "Callable[[bool], None]",
    set_prompt_running_visual: "Callable[[str | None, bool], None]",
) -> None:
    try:
        while True:
            line = app.log_queue.get_nowait()
            _append_log(app, line)
    except queue.Empty:
        pass
    if app.process is not None:
        if app.process.poll() is not None:
            _append_log(app, "\n[UI] Process finished.\n")
            set_run_state(False)
            set_prompt_running_visual(None, False)
            app.running_prompt_tab_id = None
            app.process = None
            app.step_training_signal_path = None
            app.step_training_token = 0
        else:
            app.root.after(
                200,
                lambda: _poll_log(
                    app,
                    set_run_state=set_run_state,
                    set_prompt_running_visual=set_prompt_running_visual,
                ),
            )


def _get_api_key_status() -> Tuple[str, str]:
    api_key = os.environ.get("OPENAI_API_KEY") or ""
    if api_key.strip():
        return "OK", "green"
    return "MISSING", "red"


def _script_path() -> Path:
    return Path(__file__).resolve().parent / "vision_playwright_openai_vision_poc.py"


def _load_required_state() -> Dict[str, object]:
    try:
        if REQUIRED_STATE_PATH.exists():
            raw = REQUIRED_STATE_PATH.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_required_state(state: Dict[str, object]) -> None:
    try:
        REQUIRED_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


def _build_command(
    values: Dict[str, Any], step_training_signal: Path | None = None
) -> List[str]:
    prompt = (values.get("-PROMPT-") or "").strip()
    success = (values.get("-SUCCESS-") or "").strip()
    start_url = (values.get("-STARTURL-") or "").strip()
    success_type_label = str(
        values.get("-SUCCESS-TYPE-") or SUCCESS_TYPE_DEFAULT
    ).strip()
    success_flag = SUCCESS_LABEL_TO_ARG.get(success_type_label, "--visual-llm-success")
    if not prompt or not success or not start_url:
        raise ValueError("Prompt, success criteria, and start URL are required.")

    args: List[str] = [
        sys.executable,
        "-u",
        str(_script_path()),
        "--prompt",
        prompt,
        success_flag,
        success,
        "--start-url",
        start_url,
    ]
    args.extend(build_shared_ui_cli_args(values))

    if values.get("-STEP-TRAIN-"):
        if step_training_signal is not None:
            args.extend(["--step-training-signal", str(step_training_signal)])

    return args


def _launch_command(
    cmd: List[str], *, cwd: str, env: Dict[str, str]
) -> subprocess.Popen:
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def _build_vars_map() -> Dict[str, tk.Variable]:
    defaults = build_shared_ui_defaults(UI_SETTINGS_KEYS, overrides={"-VERBOSE-": True})
    vars_map: Dict[str, tk.Variable] = {}
    for key in UI_SETTINGS_KEYS:
        try:
            spec = ui_spec_by_key(key)
            default = defaults.get(key, spec.default)
        except KeyError:
            spec = None
            default = defaults.get(key, "")
        if spec is not None and spec.kind == "bool":
            vars_map[key] = tk.BooleanVar(value=bool(default))
        else:
            vars_map[key] = tk.StringVar(value="" if default is None else str(default))
    vars_map["-USERNAME-"] = tk.StringVar()
    vars_map["-PASSWORD-"] = tk.StringVar()
    return vars_map


def _collect_values(
    vars_map: Dict[str, tk.Variable],
    prompt_text: tk.Text,
    success_text: tk.Text,
    success_type_var: tk.StringVar,
    start_url_var: tk.StringVar,
    model_var: tk.StringVar,
    actions_var: tk.StringVar,
) -> Dict[str, object]:
    values: Dict[str, object] = {}
    for key, var in vars_map.items():
        if isinstance(var, tk.BooleanVar):
            values[key] = bool(var.get())
        else:
            values[key] = str(var.get())
    values["-PROMPT-"] = prompt_text.get("1.0", "end").strip()
    values["-SUCCESS-"] = success_text.get("1.0", "end").strip()
    values["-SUCCESS-TYPE-"] = (success_type_var.get() or SUCCESS_TYPE_DEFAULT).strip()
    values["-STARTURL-"] = (start_url_var.get() or "").strip()
    values["-MODEL-"] = (model_var.get() or "").strip()
    values["-ACTIONS-"] = (actions_var.get() or "").strip()
    return values


def _collect_persistable_settings(
    vars_map: Dict[str, tk.Variable],
) -> Dict[str, object]:
    out: Dict[str, object] = {}
    for key, var in vars_map.items():
        if key in ("-USERNAME-", "-PASSWORD-"):
            continue
        try:
            if isinstance(var, tk.BooleanVar):
                out[key] = bool(var.get())
            else:
                out[key] = str(var.get())
        except Exception:
            continue
    return out


def _apply_persistable_settings(
    vars_map: Dict[str, tk.Variable], settings: Dict[str, object]
) -> None:
    for key, value in settings.items():
        if key in ("-USERNAME-", "-PASSWORD-"):
            continue
        var = vars_map.get(key)
        if var is None:
            continue
        try:
            if isinstance(var, tk.BooleanVar):
                if isinstance(value, bool):
                    var.set(value)
                elif isinstance(value, str):
                    var.set(value.strip().lower() in ("1", "true", "yes", "on"))
            else:
                var.set("" if value is None else str(value))
        except Exception:
            continue


def _add_labeled_entry(
    parent: tk.Widget,
    label: str,
    var: tk.Variable,
    width: int = 12,
    desc: str = "",
) -> None:
    row = ttk.Frame(parent)
    top = ttk.Frame(row)
    ttk.Label(
        top, text=label, width=LABEL_WIDTH, anchor="e", style="FieldLabel.TLabel"
    ).pack(side="left", padx=(0, 8))
    ttk.Entry(top, textvariable=var, width=width).pack(
        side="left", fill="x", expand=True
    )
    top.pack(fill="x")
    if desc:
        _add_field_help(row, desc, indent=(LABEL_WIDTH + 8))
    row.pack(anchor="w", pady=3, fill="x")


def _add_labeled_password(
    parent: tk.Widget,
    label: str,
    var: tk.Variable,
    width: int = 12,
    desc: str = "",
) -> None:
    row = ttk.Frame(parent)
    top = ttk.Frame(row)
    ttk.Label(
        top, text=label, width=LABEL_WIDTH, anchor="e", style="FieldLabel.TLabel"
    ).pack(side="left", padx=(0, 8))
    ttk.Entry(top, textvariable=var, width=width, show="*").pack(
        side="left", fill="x", expand=True
    )
    top.pack(fill="x")
    if desc:
        _add_field_help(row, desc, indent=(LABEL_WIDTH + 8))
    row.pack(anchor="w", pady=3, fill="x")


def _add_section_title(parent: tk.Widget, text: str) -> None:
    ttk.Label(parent, text=text, style="SectionTitle.TLabel").pack(
        anchor="w", pady=(0, 6)
    )


def _add_field_help(parent: tk.Widget, text: str, indent: int) -> None:
    help_row = ttk.Frame(parent, style="FieldHelpRow.TFrame", padding=(0, 0))
    help_row.pack(fill="x", padx=(indent, 0), pady=(2, 0))
    ttk.Label(
        help_row,
        text=text,
        style="FieldHelp.TLabel",
        wraplength=900,
        justify="left",
    ).pack(anchor="w", padx=(8, 8), pady=(4, 4))


def main() -> None:
    layout = build_root_layout(running_tint_bg=RUNNING_TINT_BG)
    root = layout.root
    left_panel = layout.left_panel
    right_panel = layout.right_panel
    base_font_size = layout.base_font_size
    text_font_size = layout.text_font_size
    win_w = layout.win_w
    win_h = layout.win_h
    x = layout.x
    y = layout.y
    logical_top = layout.logical_top
    logical_bottom = layout.logical_bottom

    def _set_default_split(
        preferred_x: int | None = None, preferred_ratio: float | None = None
    ) -> None:
        layout.set_default_split(preferred_x, preferred_ratio)

    def _get_split_sash_x() -> int | None:
        return layout.get_split_sash_x()

    vars_map: Dict[str, tk.Variable] = _build_vars_map()

    notebook = ttk.Notebook(left_panel)
    notebook.pack(fill="both", expand=True, padx=6, pady=6)

    tab_prompts = ttk.Frame(notebook)
    tab_browser = ttk.Frame(notebook)
    tab_tokens = ttk.Frame(notebook)
    tab_actions = ttk.Frame(notebook)
    tab_output = ttk.Frame(notebook)
    tab_creds = ttk.Frame(notebook)
    tab_ai_view = ttk.Frame(notebook)
    tab_actions_lib = ttk.Frame(notebook)

    notebook.add(tab_prompts, text="Tests")
    notebook.add(tab_ai_view, text="AI View")
    notebook.add(tab_creds, text="Credentials")
    notebook.add(tab_actions_lib, text="Actions")
    notebook.add(tab_actions, text="Action Settings")
    notebook.add(tab_browser, text="Browser")
    notebook.add(tab_tokens, text="Tokens")
    notebook.add(tab_output, text="Output")

    prompt_state = build_prompt_tabs_panel(
        tab_prompts,
        root=root,
        text_font_size=text_font_size,
        update_info_bar_text=lambda _tab_id: None,
        save_ui_state_snapshot=lambda: _save_ui_state_snapshot(),
    )
    prompt_tabs = prompt_state.prompt_tabs
    plus_tab = prompt_state.plus_tab

    def _get_active_prompt_fields() -> Tuple[
        tk.Text, tk.Text, tk.StringVar, tk.StringVar, tk.StringVar, tk.StringVar
    ]:
        return get_active_prompt_fields_from_state(prompt_state)

    def _save_ui_state_snapshot() -> None:
        try:
            (
                prompt_widget,
                success_widget,
                success_type_var,
                start_url_var,
                model_var,
                actions_var,
            ) = _get_active_prompt_fields()
            values = _collect_values(
                vars_map,
                prompt_widget,
                success_widget,
                success_type_var,
                start_url_var,
                model_var,
                actions_var,
            )
        except Exception:
            values = {}
        prompt_state_snapshot = get_prompt_state_snapshot(prompt_state)
        state: Dict[str, object] = {
            "prompt": values.get("-PROMPT-", ""),
            "success_criteria": values.get("-SUCCESS-", ""),
            "success_type": values.get("-SUCCESS-TYPE-", SUCCESS_TYPE_DEFAULT),
            "start_url": values.get("-STARTURL-", ""),
            "model": values.get("-MODEL-", DEFAULT_MODEL),
            "actions": values.get("-ACTIONS-", ""),
            "prompts": prompt_state_snapshot.get("prompts", []),
            "active_prompt_index": prompt_state_snapshot.get("active_index", 0),
            "settings": _collect_persistable_settings(vars_map),
        }
        split_x = _get_split_sash_x()
        if split_x is not None:
            state["split_sash_x"] = split_x
            try:
                total_w = max(1, int(root.winfo_width()))
                state["split_sash_ratio"] = round(split_x / float(total_w), 3)
            except Exception:
                pass
        _save_required_state(state)

    build_browser_tab(tab_browser, vars_map)
    build_tokens_tab(tab_tokens, vars_map)
    build_action_settings_tab(tab_actions, vars_map)
    build_output_tab(tab_output, vars_map)

    openai_key_var, anthropic_key_var, _apply_api_key = build_credentials_tab(
        tab_creds,
        root=root,
        vars_map=vars_map,
        add_section_title=_add_section_title,
        add_field_help=_add_field_help,
        add_labeled_entry=_add_labeled_entry,
        add_labeled_password=_add_labeled_password,
    )

    log_text, continue_button, log_container = build_run_log_panel(
        right_panel,
        text_font_size=text_font_size,
    )

    ai_view = build_ai_view_tab(
        tab_ai_view,
        root=root,
        vars_map=vars_map,
        base_font_size=base_font_size,
    )

    actions_state = build_actions_library_tab(
        tab_actions_lib,
        root=root,
        base_font_size=base_font_size,
        text_font_size=text_font_size,
    )

    def _on_any_tab_changed(event: object) -> None:
        _ = event
        current_main = notebook.select()
        if current_main == str(tab_ai_view):
            files = list_ai_images(ai_view)
            ai_view.last_ai_files = files
            refresh_ai_view(ai_view, files, select_latest=True)
        if current_main == str(tab_actions_lib):
            refresh_actions_list(actions_state)

    notebook.bind("<<NotebookTabChanged>>", _on_any_tab_changed)

    log_queue: "queue.Queue[str]" = queue.Queue()
    app = AppState(
        root=root,
        vars_map=vars_map,
        prompt_tabs=prompt_tabs,
        plus_tab=plus_tab,
        log_text=log_text,
        log_queue=log_queue,
        continue_button=continue_button,
        openai_key_var=openai_key_var,
        anthropic_key_var=anthropic_key_var,
    )

    app.continue_button.configure(command=lambda: _send_step_training_continue(app))
    _set_continue_state(app)
    app.vars_map["-STEP-TRAIN-"].trace_add("write", lambda *_: _set_continue_state(app))
    app.vars_map["-HEADLESS-"].trace_add("write", lambda *_: _set_continue_state(app))

    def _set_run_state(running: bool) -> None:
        app.running_state = running
        if app.run_button is not None:
            if running:
                app.run_button.configure(text="Stop", bootstyle="danger")
            else:
                app.run_button.configure(text="Run", bootstyle="success")
        info_bar_controller.set_info_bar(running)
        _set_continue_state(app)

    run_button, info_bar, info_label, button_frame = build_run_button_bar(
        left_panel,
        run_callback=lambda: None,
    )
    app.run_button = run_button
    app.info_bar = info_bar
    app.info_label = info_label

    info_bar_controller = build_info_bar_controller(
        app=app,
        prompt_tabs=prompt_tabs,
        get_tab_display_name=get_tab_display_name,
        prompt_state=prompt_state,
    )
    run_lifecycle = build_run_lifecycle(
        app=app,
        root=root,
        prompt_tabs=prompt_tabs,
        prompt_state=prompt_state,
        vars_map=vars_map,
        apply_api_key=_apply_api_key,
        get_active_prompt_fields=_get_active_prompt_fields,
        collect_values=_collect_values,
        build_command=_build_command,
        script_path=_script_path,
        launch_command=_launch_command,
        poll_log=_poll_log,
        set_run_state=_set_run_state,
        append_log=_append_log,
        save_ui_state_snapshot=_save_ui_state_snapshot,
        update_info_bar_text=info_bar_controller.update_info_bar_text,
        clear_agent_view_images=clear_agent_view_images,
        ai_view=ai_view,
        set_prompt_running_visual=set_prompt_running_visual,
        clean_running_suffixes=clean_running_suffixes,
    )
    run_button.configure(command=run_lifecycle.toggle_run)

    prompt_tabs.bind(
        "<<NotebookTabChanged>>",
        lambda _e: info_bar_controller.update_info_bar_text(prompt_tabs.select()),
        add="+",
    )
    info_bar_controller.set_info_bar(False)
    info_bar_controller.update_info_bar_text(prompt_tabs.select())

    root.protocol("WM_DELETE_WINDOW", run_lifecycle.on_close)
    apply_initial_window_layout(
        RestoreContext(
            root=root,
            notebook=notebook,
            button_frame=button_frame,
            log_container=log_container,
            log_text=log_text,
            win_w=win_w,
            win_h=win_h,
            x=x,
            y=y,
            logical_top=logical_top,
            logical_bottom=logical_bottom,
        )
    )

    def _restore_create_prompt_tab(
        state: PromptTabsState, *, name: str, text_font_size: int
    ) -> tk.Widget:
        return create_prompt_tab(state, name=name, text_font_size=text_font_size)

    restore_ui_state(
        root=root,
        prompt_state=prompt_state,
        prompt_tabs=prompt_tabs,
        vars_map=vars_map,
        load_required_state=_load_required_state,
        apply_persistable_settings=_apply_persistable_settings,
        set_default_split=_set_default_split,
        get_prompt_tabs=get_prompt_tabs,
        create_prompt_tab=_restore_create_prompt_tab,
        get_active_prompt_fields=_get_active_prompt_fields,
        text_font_size=text_font_size,
    )

    clean_running_suffixes(prompt_state)
    set_prompt_running_visual(prompt_state, None, running=False)
    root.after(500, lambda: poll_ai_view(ai_view))
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()
