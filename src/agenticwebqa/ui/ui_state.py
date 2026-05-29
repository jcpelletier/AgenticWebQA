from __future__ import annotations

import queue
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, TYPE_CHECKING

import tkinter as tk

if TYPE_CHECKING:
    import ttkbootstrap as ttk
    from PIL import ImageTk


@dataclass
class AppState:
    root: "ttk.Window"
    vars_map: Dict[str, tk.Variable]
    prompt_tabs: "ttk.Notebook"
    plus_tab: "ttk.Frame"
    log_text: tk.Text
    log_queue: "queue.Queue[str]"
    continue_button: "ttk.Button"
    openai_key_var: tk.StringVar
    anthropic_key_var: tk.StringVar
    gemini_key_var: tk.StringVar
    process: subprocess.Popen | None = None
    running_state: bool = False
    running_prompt_tab_id: str | None = None
    step_training_signal_path: Path | None = None
    step_training_token: int = 0
    run_button: "ttk.Button" | None = None
    info_bar: "ttk.Frame" | None = None
    info_label: "ttk.Label" | None = None


@dataclass
class AIViewState:
    root: "ttk.Window"
    vars_map: Dict[str, tk.Variable]
    image_list: tk.Listbox
    canvas: tk.Canvas
    canvas_image_id: int | None = None
    canvas_image_ref: "ImageTk.PhotoImage | tk.PhotoImage | None" = None
    current_ai_image_path: Path | None = None
    last_ai_files: List[str] = field(default_factory=list)


@dataclass
class PromptTabsState:
    root: "ttk.Window"
    prompt_tabs: "ttk.Notebook"
    plus_tab: "ttk.Frame"
    tab_content_area: "ttk.Frame"
    tab_counter: int = 0
    content_frames: Dict[str, "ttk.Frame"] = field(default_factory=dict)


@dataclass
class ActionsLibState:
    root: "ttk.Window"
    actions_list: tk.Listbox
    actions_text: tk.Text
    actions_buttons_inner: "ttk.Frame"
    actions_buttons_canvas: tk.Canvas
    actions_buttons_map: Dict[int, "ttk.Button"] = field(default_factory=dict)
    current_actions_path: Path | None = None
    current_actions_data: Dict[str, Any] | None = None
    current_action_index: int | None = None
