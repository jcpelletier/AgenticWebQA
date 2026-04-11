from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Protocol, Tuple, TYPE_CHECKING

import tkinter as tk
from tkinter import messagebox

from config_shared import infer_model_provider, model_api_env_var

from .ui_state import AppState, AIViewState, PromptTabsState

if TYPE_CHECKING:
    import subprocess
    import ttkbootstrap as ttk


@dataclass
class RunLifecycle:
    run_script: Callable[[], None]
    stop_script: Callable[[], None]
    toggle_run: Callable[[], None]
    on_close: Callable[[], None]


class LaunchCommand(Protocol):
    def __call__(
        self, cmd: list[str], *, cwd: str, env: Dict[str, str]
    ) -> "subprocess.Popen": ...


def build_run_lifecycle(
    *,
    app: AppState,
    root: tk.Tk | tk.Toplevel,
    prompt_tabs: "ttk.Notebook",
    prompt_state: PromptTabsState,
    vars_map: Dict[str, tk.Variable],
    apply_api_key: Callable[[], None],
    get_active_prompt_fields: Callable[
        [],
        Tuple[tk.Text, tk.Text, tk.StringVar, tk.StringVar, tk.StringVar, tk.StringVar],
    ],
    collect_values: Callable[
        [
            Dict[str, tk.Variable],
            tk.Text,
            tk.Text,
            tk.StringVar,
            tk.StringVar,
            tk.StringVar,
            tk.StringVar,
        ],
        Dict[str, object],
    ],
    build_command: Callable[[Dict[str, object], Path | None], list[str]],
    script_path: Callable[[], Path],
    launch_command: LaunchCommand,
    poll_log: Callable[..., None],
    set_run_state: Callable[[bool], None],
    append_log: Callable[[AppState, str], None],
    save_ui_state_snapshot: Callable[[], None],
    update_info_bar_text: Callable[[str | None], None],
    clear_agent_view_images: Callable[[AIViewState], None],
    ai_view: AIViewState,
    set_prompt_running_visual: Callable[[PromptTabsState, str | None, bool], None],
    clean_running_suffixes: Callable[[PromptTabsState], None],
) -> RunLifecycle:
    def _default_step_training_signal_path() -> Path:
        return Path(__file__).resolve().parent.parent / ".step_training_signal"

    def run_script() -> None:
        if app.process is not None:
            return
        apply_api_key()
        target_script = script_path()
        if not target_script.exists():
            messagebox.showerror("Missing script", f"Script not found: {target_script}")
            return
        (
            prompt_widget,
            success_widget,
            success_type_var,
            start_url_var,
            model_var,
            actions_var,
        ) = get_active_prompt_fields()
        values = collect_values(
            vars_map,
            prompt_widget,
            success_widget,
            success_type_var,
            start_url_var,
            model_var,
            actions_var,
        )
        selected_model = str(values.get("-MODEL-") or "").strip()
        required_env = model_api_env_var(selected_model)
        provider = infer_model_provider(selected_model)
        openai_key = (app.openai_key_var.get() or "").strip()
        anthropic_key = (app.anthropic_key_var.get() or "").strip()
        gemini_key = (app.gemini_key_var.get() or "").strip()
        if provider == "anthropic":
            required_key = anthropic_key
        elif provider == "gemini":
            required_key = gemini_key
        else:
            required_key = openai_key
        if not required_key:
            messagebox.showerror(
                "Missing API key",
                f"{required_env} is missing for selected model '{selected_model}'.",
            )
            return
        step_training_signal = None
        if values.get("-STEP-TRAIN-"):
            step_training_signal = _default_step_training_signal_path()
            try:
                step_training_signal.write_text("0", encoding="utf-8")
            except Exception as exc:
                messagebox.showerror(
                    "Step Training", f"Failed to initialize step training signal: {exc}"
                )
                return
        try:
            cmd = build_command(values, step_training_signal)
        except Exception as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        set_prompt_running_visual(prompt_state, app.running_prompt_tab_id, False)
        clean_running_suffixes(prompt_state)
        app.running_prompt_tab_id = prompt_tabs.select()
        set_prompt_running_visual(prompt_state, app.running_prompt_tab_id, True)
        update_info_bar_text(app.running_prompt_tab_id)
        save_ui_state_snapshot()
        clear_agent_view_images(ai_view)
        env = os.environ.copy()
        if openai_key:
            env["OPENAI_API_KEY"] = openai_key
        if anthropic_key:
            env["ANTHROPIC_API_KEY"] = anthropic_key
        if gemini_key:
            env["GEMINI_API_KEY"] = gemini_key
        username = str(values.get("-USERNAME-") or "").strip()
        password = str(values.get("-PASSWORD-") or "")
        if username:
            env["AGENTICWEBQA_USERNAME"] = username
        if password:
            env["AGENTICWEBQA_PASSWORD"] = password
        try:
            app.log_text.configure(state="normal")
            app.log_text.delete("1.0", "end")
            app.log_text.configure(state="disabled")
            app.step_training_signal_path = step_training_signal
            app.step_training_token = 0
            app.process = launch_command(cmd, cwd=str(target_script.parent), env=env)
            set_run_state(True)
            threading.Thread(
                target=_reader_thread, args=(app, app.process), daemon=True
            ).start()
            root.after(
                200,
                lambda: poll_log(
                    app,
                    set_run_state=set_run_state,
                    set_prompt_running_visual=lambda tab_id, running: (
                        set_prompt_running_visual(prompt_state, tab_id, running)
                    ),
                ),
            )
        except Exception as exc:
            messagebox.showerror("Launch failed", str(exc))
            set_prompt_running_visual(prompt_state, None, False)
            app.running_prompt_tab_id = None
            app.process = None
            set_run_state(False)

    def stop_script() -> None:
        if app.process is None:
            return
        try:
            app.process.terminate()
            append_log(app, "\n[UI] Stop requested.\n")
        except Exception as exc:
            messagebox.showerror("Stop failed", str(exc))
        set_prompt_running_visual(prompt_state, None, False)
        app.running_prompt_tab_id = None

    def toggle_run() -> None:
        if app.process is None:
            run_script()
        else:
            stop_script()

    def on_close() -> None:
        save_ui_state_snapshot()
        if app.process is not None:
            try:
                app.process.terminate()
            except Exception:
                pass
        root.destroy()

    return RunLifecycle(
        run_script=run_script,
        stop_script=stop_script,
        toggle_run=toggle_run,
        on_close=on_close,
    )


def _reader_thread(app: AppState, proc: "subprocess.Popen") -> None:
    stdout = getattr(proc, "stdout", None)
    if stdout is None:
        return
    for line in stdout:
        app.log_queue.put(line)
    try:
        stdout.close()
    except Exception:
        pass
