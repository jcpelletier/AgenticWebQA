from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

import tkinter as tk

from .ui_state import AppState
from .ui_state import PromptTabsState

if TYPE_CHECKING:
    import ttkbootstrap as ttk


@dataclass
class InfoBarController:
    update_info_bar_text: Callable[[str | None], None]
    set_info_bar: Callable[[bool], None]


def build_info_bar_controller(
    *,
    app: AppState,
    prompt_tabs: "ttk.Notebook",
    get_tab_display_name: Callable[[PromptTabsState, str | None], str],
    prompt_state: PromptTabsState,
) -> InfoBarController:
    def _update_info_bar_text(tab_id: str | None) -> None:
        name = get_tab_display_name(prompt_state, tab_id)
        status = "Running" if app.running_state else "Stopped"
        if name:
            label = f"{name} - {status}"
        else:
            label = status
        if app.info_label is not None:
            app.info_label.configure(text=label)
        app.root.title(label)

    def _set_info_bar(_: bool) -> None:
        if app.info_bar is not None and not app.info_bar.winfo_ismapped():
            app.info_bar.pack(side="left", padx=8)
        _update_info_bar_text(prompt_tabs.select())

    return InfoBarController(
        update_info_bar_text=_update_info_bar_text,
        set_info_bar=_set_info_bar,
    )
