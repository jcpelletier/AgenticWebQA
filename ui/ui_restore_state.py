from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Protocol, TYPE_CHECKING

import tkinter as tk
import tkinter.font as tkfont

from config_shared import DEFAULT_MODEL
from .ui_prompt_tabs import SUCCESS_TYPE_DEFAULT
from .ui_state import PromptTabsState

if TYPE_CHECKING:
    import ttkbootstrap as ttk


class CreatePromptTab(Protocol):
    def __call__(
        self, state: PromptTabsState, *, name: str, text_font_size: int
    ) -> tk.Widget: ...


@dataclass
class RestoreContext:
    root: tk.Tk | tk.Toplevel
    notebook: "ttk.Notebook"
    button_frame: tk.Widget
    log_container: tk.Widget
    log_text: tk.Text
    win_w: int
    win_h: int
    x: int
    y: int
    logical_top: int
    logical_bottom: int


def apply_initial_window_layout(ctx: RestoreContext) -> None:
    ctx.root.update_idletasks()
    line_height = tkfont.Font(font=ctx.log_text.cget("font")).metrics("linespace")
    min_log_px = (line_height * 2) + 10
    try:
        ctx.log_container.configure({"height": min_log_px})
        ctx.log_container.pack_propagate(False)
    except Exception:
        pass
    min_h = (
        ctx.notebook.winfo_reqheight()
        + ctx.button_frame.winfo_reqheight()
        + min_log_px
        + 30
    )
    default_h = int((ctx.logical_bottom - ctx.logical_top) * 0.80)
    win_h = max(min_h, min(default_h, ctx.win_h))
    ctx.root.minsize(ctx.win_w, min_h)
    ctx.root.geometry(f"{ctx.win_w}x{win_h}+{ctx.x}+{ctx.y}")
    try:
        ctx.root.state("zoomed")
    except Exception:
        try:
            ctx.root.attributes("-zoomed", True)
        except Exception:
            pass


def restore_ui_state(
    *,
    root: tk.Tk | tk.Toplevel,
    prompt_state: PromptTabsState,
    prompt_tabs: "ttk.Notebook",
    vars_map: Dict[str, tk.Variable],
    load_required_state: Callable[[], Dict[str, object]],
    apply_persistable_settings: Callable[
        [Dict[str, tk.Variable], Dict[str, object]], None
    ],
    set_default_split: Callable[[int | None, float | None], None],
    get_prompt_tabs: Callable[[PromptTabsState], list[str]],
    create_prompt_tab: CreatePromptTab,
    get_active_prompt_fields: Callable[
        [],
        tuple[tk.Text, tk.Text, tk.StringVar, tk.StringVar, tk.StringVar, tk.StringVar],
    ],
    text_font_size: int,
) -> None:
    cached = load_required_state()
    cached_settings = cached.get("settings")
    if isinstance(cached_settings, dict):
        apply_persistable_settings(vars_map, cached_settings)

    def _apply_default_split() -> None:
        set_default_split(None, 0.50)

    root.after(300, _apply_default_split)
    prompts = cached.get("prompts")
    if isinstance(prompts, list) and prompts:
        for tab_id in get_prompt_tabs(prompt_state):
            prompt_tabs.forget(tab_id)
            cf = prompt_state.content_frames.pop(tab_id, None)
            if cf is not None:
                cf.destroy()
        prompt_state.tab_counter = 0
        for item in prompts:
            if not isinstance(item, dict):
                continue
            title = (
                str(item.get("title") or "").strip()
                or f"prompt{prompt_state.tab_counter + 1}"
            )
            prompt_state.tab_counter += 1
            tab = create_prompt_tab(
                prompt_state, name=title, text_font_size=text_font_size
            )
            prompt_widget = getattr(tab, "_prompt_text")
            success_widget = getattr(tab, "_success_text")
            success_type_var = getattr(tab, "_success_type_var")
            start_url_var = getattr(tab, "_start_url_var")
            model_var = getattr(tab, "_model_var")
            actions_var = getattr(tab, "_actions_var")
            prompt_widget.insert("1.0", str(item.get("prompt") or ""))
            success_widget.insert("1.0", str(item.get("success_criteria") or ""))
            success_type_var.set(str(item.get("success_type") or SUCCESS_TYPE_DEFAULT))
            start_url_var.set(str(item.get("start_url") or ""))
            model_var.set(str(item.get("model") or DEFAULT_MODEL))
            actions_var.set(str(item.get("actions") or ""))
        active_index = cached.get("active_prompt_index", 0)
        if isinstance(active_index, int):
            tabs = get_prompt_tabs(prompt_state)
            if tabs:
                prompt_tabs.select(tabs[min(active_index, len(tabs) - 1)])
    else:
        (
            prompt_widget,
            success_widget,
            success_type_var,
            start_url_var,
            model_var,
            actions_var,
        ) = get_active_prompt_fields()
        if cached.get("prompt"):
            prompt_widget.insert("1.0", str(cached.get("prompt") or ""))
        if cached.get("success_criteria"):
            success_widget.insert("1.0", str(cached.get("success_criteria") or ""))
        success_type_var.set(str(cached.get("success_type") or SUCCESS_TYPE_DEFAULT))
        if cached.get("start_url"):
            start_url_var.set(str(cached.get("start_url") or ""))
        if cached.get("model"):
            model_var.set(str(cached.get("model") or DEFAULT_MODEL))
        if cached.get("actions"):
            actions_var.set(str(cached.get("actions") or ""))
