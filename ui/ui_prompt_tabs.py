from __future__ import annotations

from typing import Callable, Dict, List, Tuple, cast

import tkinter as tk
from tkinter import messagebox, simpledialog

import ttkbootstrap as ttk

from config_shared import DEFAULT_MODEL, MODEL_OPTIONS
from .ui_state import PromptTabsState

LABEL_WIDTH = 18
RUNNING_TAB_SUFFIX = ""
RUNNING_TAB_LEGACY_SUFFIX = " (RUNNING)"
RUNNING_TAB_PREFIX = "â— "


def build_prompt_tabs_panel(
    tab_prompts: ttk.Frame,
    *,
    root: ttk.Window,
    text_font_size: int,
    update_info_bar_text: Callable[[str | None], None],
    save_ui_state_snapshot: Callable[[], None],
) -> PromptTabsState:
    # ── Scrollable tab strip ────────────────────────────────────────────────────
    tab_strip_outer = ttk.Frame(tab_prompts)
    tab_strip_outer.pack(fill="x")

    tab_strip_canvas = tk.Canvas(tab_strip_outer, highlightthickness=0, bd=0)
    h_scrollbar = ttk.Scrollbar(
        tab_strip_outer, orient="horizontal", command=tab_strip_canvas.xview
    )
    tab_strip_canvas.configure(xscrollcommand=h_scrollbar.set)
    tab_strip_canvas.pack(fill="x", side="top")
    h_scrollbar.pack(fill="x", side="top", pady=(0, 4))

    tab_strip_inner = ttk.Frame(tab_strip_canvas)
    tab_strip_canvas.create_window((0, 0), window=tab_strip_inner, anchor="nw")

    def _sync_canvas_size(event: object = None) -> None:
        req_w = tab_strip_inner.winfo_reqwidth()
        req_h = tab_strip_inner.winfo_reqheight()
        tab_strip_canvas.configure(
            height=req_h,
            scrollregion=(0, 0, req_w, req_h),
        )

    tab_strip_inner.bind("<Configure>", _sync_canvas_size)

    # ── Notebook (tab strip only — height=1 hides content area) ────────────────
    prompt_tabs = ttk.Notebook(tab_strip_inner, height=1)
    prompt_tabs.pack(side="left", fill="y")
    plus_tab = ttk.Frame(prompt_tabs)
    prompt_tabs.add(plus_tab, text="+")

    # ── Full-width content area below the scrollable strip ─────────────────────
    tab_content_area = ttk.Frame(tab_prompts)
    tab_content_area.pack(fill="both", expand=True)

    prompt_state = PromptTabsState(
        root=root,
        prompt_tabs=prompt_tabs,
        plus_tab=plus_tab,
        tab_content_area=tab_content_area,
    )

    def _add_prompt_tab_local() -> None:
        add_prompt_tab_to_state(
            prompt_state,
            text_font_size=text_font_size,
            update_info_bar_text=update_info_bar_text,
        )

    def _on_prompt_tab_changed(_: object = None) -> None:
        current = prompt_tabs.select()
        if current == str(plus_tab):
            _add_prompt_tab_local()
            current = prompt_tabs.select()
        for tab_id, cf in prompt_state.content_frames.items():
            if tab_id == current:
                cf.pack(fill="both", expand=True)
            else:
                cf.pack_forget()
        update_info_bar_text(current)

    def _rename_prompt_tab_handler(event: tk.Event) -> None:
        rename_prompt_tab(prompt_state, event)

    def _on_tab_strip_wheel(event: tk.Event) -> None:
        tab_strip_canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")

    prompt_tabs.bind("<<NotebookTabChanged>>", _on_prompt_tab_changed)
    prompt_tabs.bind("<Double-1>", _rename_prompt_tab_handler)
    tab_strip_canvas.bind("<MouseWheel>", _on_tab_strip_wheel)
    prompt_tabs.bind("<MouseWheel>", _on_tab_strip_wheel)

    _add_prompt_tab_local()

    _drag: Dict[str, object] = {"source_idx": None}

    def _on_drag_start(event: tk.Event) -> None:
        if prompt_tabs.identify(event.x, event.y) != "label":
            _drag["source_idx"] = None
            return
        try:
            idx = prompt_tabs.index(f"@{event.x},{event.y}")
        except Exception:
            _drag["source_idx"] = None
            return
        if prompt_tabs.tabs()[idx] == str(plus_tab):
            _drag["source_idx"] = None
            return
        _drag["source_idx"] = idx

    def _on_drag_motion(event: tk.Event) -> None:
        if _drag["source_idx"] is None:
            return
        if prompt_tabs.identify(event.x, event.y) == "label":
            try:
                idx = prompt_tabs.index(f"@{event.x},{event.y}")
                if prompt_tabs.tabs()[idx] != str(plus_tab):
                    prompt_tabs.configure(cursor="exchange")
                    return
            except Exception:
                pass
        prompt_tabs.configure(cursor="")

    def _on_drag_release(event: tk.Event) -> None:
        source_idx = _drag["source_idx"]
        _drag["source_idx"] = None
        prompt_tabs.configure(cursor="")
        if source_idx is None:
            return
        if prompt_tabs.identify(event.x, event.y) != "label":
            return
        try:
            target_idx = prompt_tabs.index(f"@{event.x},{event.y}")
        except Exception:
            return
        tabs = prompt_tabs.tabs()
        if target_idx >= len(tabs) or tabs[target_idx] == str(plus_tab):
            target_idx = len(tabs) - 2  # last real tab position
        if source_idx == target_idx:
            return
        source_tab_id = tabs[source_idx]
        prompt_tabs.insert(target_idx, source_tab_id)
        prompt_tabs.select(source_tab_id)

    prompt_tabs.bind("<ButtonPress-1>", _on_drag_start)
    prompt_tabs.bind("<B1-Motion>", _on_drag_motion)
    prompt_tabs.bind("<ButtonRelease-1>", _on_drag_release)

    def _delete_current_prompt_tab(tab_id: str) -> None:
        delete_prompt_tab_from_state(
            prompt_state,
            tab_id,
            save_ui_state_snapshot=save_ui_state_snapshot,
            add_prompt_tab=_add_prompt_tab_local,
        )

    def _show_prompt_tab_menu_handler(event: tk.Event) -> None:
        show_prompt_tab_menu(
            prompt_state,
            event,
            delete_prompt_tab=_delete_current_prompt_tab,
        )

    prompt_tabs.bind("<Button-3>", _show_prompt_tab_menu_handler)
    prompt_tabs.bind("<Button-2>", _show_prompt_tab_menu_handler)
    prompt_tabs.bind("<Control-Button-1>", _show_prompt_tab_menu_handler)

    return prompt_state


def get_prompt_tabs(state: PromptTabsState) -> List[str]:
    return [
        tab_id for tab_id in state.prompt_tabs.tabs() if tab_id != str(state.plus_tab)
    ]


def create_prompt_tab(
    state: PromptTabsState, *, name: str, text_font_size: int
) -> ttk.Frame:
    # Minimal placeholder inside the notebook — just holds the tab label.
    placeholder = ttk.Frame(state.prompt_tabs, height=1)
    insert_at = max(0, state.prompt_tabs.index("end") - 1)
    state.prompt_tabs.insert(insert_at, placeholder, text=name)

    # Actual content lives outside the scrollable strip, in the full-width area.
    content_frame = ttk.Frame(state.tab_content_area)
    state.content_frames[str(placeholder)] = content_frame

    prompt_card = ttk.Frame(
        content_frame, style="Card.TFrame", bootstyle="secondary", padding=12
    )
    prompt_card.pack(fill="x", pady=(0, 8))
    _add_section_title(prompt_card, "Prompt")
    prompt_frame = ttk.Frame(prompt_card)
    prompt_frame.pack(fill="x", pady=(0, 6))
    prompt_scroll = ttk.Scrollbar(prompt_frame, orient="vertical")
    prompt_scroll.pack(side="right", fill="y")
    prompt_text = tk.Text(
        prompt_frame,
        height=8,
        width=90,
        yscrollcommand=prompt_scroll.set,
        font=("Segoe UI", text_font_size),
    )
    prompt_text.pack(side="left", fill="x", expand=True)
    prompt_scroll.config(command=prompt_text.yview)

    success_card = ttk.Frame(
        content_frame, style="Card.TFrame", bootstyle="secondary", padding=12
    )
    success_card.pack(fill="x", pady=(0, 8))
    _add_section_title(success_card, "Success Criteria")
    success_text = tk.Text(
        success_card, height=3, width=90, font=("Segoe UI", text_font_size)
    )
    success_text.pack(fill="x", pady=(0, 2))

    run_card = ttk.Frame(
        content_frame, style="Card.TFrame", bootstyle="secondary", padding=12
    )
    run_card.pack(fill="x", pady=(0, 8))
    _add_section_title(run_card, "Run Configuration")
    start_url_var = tk.StringVar()
    model_var = tk.StringVar(value=DEFAULT_MODEL)
    actions_var = tk.StringVar()
    _add_labeled_entry(
        run_card,
        "Start URL",
        start_url_var,
        width=60,
        desc="Starting page the browser opens before any actions run.",
    )
    model_row = ttk.Frame(run_card)
    ttk.Label(
        model_row,
        text="Model",
        width=LABEL_WIDTH,
        anchor="e",
        style="FieldLabel.TLabel",
    ).pack(
        side="left",
        padx=(0, 8),
    )
    model_combo = ttk.Combobox(
        model_row,
        textvariable=model_var,
        values=MODEL_OPTIONS,
        width=27,
        state="readonly",
    )
    model_combo.pack(side="left")
    model_row.pack(anchor="w", pady=(3, 0), fill="x")
    _add_field_help(
        run_card,
        "Select the vision model used for screenshot reasoning.",
        indent=(LABEL_WIDTH + 8),
    )
    _add_labeled_entry(
        run_card,
        "Actions",
        actions_var,
        width=40,
        desc="Comma-separated action names (e.g., login, search, click_movie).",
    )
    # Attributes on placeholder for backward-compatible access via nametowidget.
    setattr(placeholder, "_prompt_text", prompt_text)
    setattr(placeholder, "_success_text", success_text)
    setattr(placeholder, "_start_url_var", start_url_var)
    setattr(placeholder, "_model_var", model_var)
    setattr(placeholder, "_actions_var", actions_var)
    return placeholder


def add_prompt_tab_to_state(
    state: PromptTabsState,
    *,
    text_font_size: int,
    update_info_bar_text: Callable[[str | None], None] | None = None,
) -> None:
    state.tab_counter += 1
    tab = create_prompt_tab(
        state, name=f"prompt{state.tab_counter}", text_font_size=text_font_size
    )
    state.prompt_tabs.select(tab)
    if update_info_bar_text is not None:
        update_info_bar_text(state.prompt_tabs.select())


def get_active_prompt_fields_from_state(
    state: PromptTabsState,
) -> Tuple[tk.Text, tk.Text, tk.StringVar, tk.StringVar, tk.StringVar]:
    current = state.prompt_tabs.select()
    tab = state.prompt_tabs.nametowidget(current)
    prompt_widget = getattr(tab, "_prompt_text")
    success_widget = getattr(tab, "_success_text")
    start_url_var = getattr(tab, "_start_url_var")
    model_var = getattr(tab, "_model_var")
    actions_var = getattr(tab, "_actions_var")
    return prompt_widget, success_widget, start_url_var, model_var, actions_var


def get_prompt_state_snapshot(state: PromptTabsState) -> Dict[str, object]:
    items: List[Dict[str, str]] = []
    active_index = 0
    active_tab = state.prompt_tabs.select()
    tabs = get_prompt_tabs(state)
    for idx, tab_id in enumerate(tabs):
        tab = state.prompt_tabs.nametowidget(tab_id)
        title = str(state.prompt_tabs.tab(tab_id, "text"))
        prompt_widget = getattr(tab, "_prompt_text")
        success_widget = getattr(tab, "_success_text")
        start_url_var = getattr(tab, "_start_url_var")
        model_var = getattr(tab, "_model_var")
        actions_var = getattr(tab, "_actions_var")
        items.append(
            {
                "title": title,
                "prompt": prompt_widget.get("1.0", "end").strip(),
                "success_criteria": success_widget.get("1.0", "end").strip(),
                "start_url": (start_url_var.get() or "").strip(),
                "model": (model_var.get() or "").strip(),
                "actions": (actions_var.get() or "").strip(),
            }
        )
        if tab_id == active_tab:
            active_index = idx
    return {"prompts": items, "active_index": active_index}


def delete_prompt_tab_from_state(
    state: PromptTabsState,
    tab_id: str,
    *,
    save_ui_state_snapshot: Callable[[], None],
    add_prompt_tab: Callable[[], None],
) -> None:
    tabs = get_prompt_tabs(state)
    if tab_id not in tabs:
        return
    tab_name = get_tab_display_name(state, tab_id)
    confirm = messagebox.askyesno(
        "Delete test",
        f"Delete test '{tab_name or 'this test'}'? This cannot be undone.",
        parent=state.root,
    )
    if not confirm:
        return
    try:
        state.prompt_tabs.forget(tab_id)
    except Exception:
        return
    cf = state.content_frames.pop(tab_id, None)
    if cf is not None:
        cf.destroy()
    save_ui_state_snapshot()
    tabs = get_prompt_tabs(state)
    if not tabs:
        state.tab_counter = 0
        add_prompt_tab()
        save_ui_state_snapshot()
        return
    try:
        state.prompt_tabs.select(tabs[min(0, len(tabs) - 1)])
    except Exception:
        pass


def rename_prompt_tab(state: PromptTabsState, event: tk.Event) -> None:
    if state.prompt_tabs.identify(event.x, event.y) != "label":
        return
    try:
        idx = state.prompt_tabs.index(f"@{event.x},{event.y}")
    except Exception:
        return
    if state.prompt_tabs.tabs()[idx] == str(state.plus_tab):
        return
    current_name = str(state.prompt_tabs.tab(idx, "text"))
    new_name = simpledialog.askstring(
        "Rename prompt",
        "New name:",
        initialvalue=current_name,
        parent=state.root,
    )
    if new_name is None:
        return
    new_name = new_name.strip()
    if not new_name:
        return
    state.prompt_tabs.tab(idx, text=new_name)


def show_prompt_tab_menu(
    state: PromptTabsState,
    event: tk.Event,
    *,
    delete_prompt_tab: Callable[[str], None],
) -> None:
    try:
        if state.prompt_tabs.identify(event.x, event.y) != "label":
            return
        idx = state.prompt_tabs.index(f"@{event.x},{event.y}")
    except Exception:
        return
    tab_id = state.prompt_tabs.tabs()[idx]
    if tab_id == str(state.plus_tab):
        return
    menu = tk.Menu(state.root, tearoff=0)
    try:

        def _handle_delete() -> None:
            delete_prompt_tab(tab_id)

        menu.add_command(label="Delete", command=_handle_delete)
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def clean_running_suffixes(state: PromptTabsState) -> None:
    for tab_id in get_prompt_tabs(state):
        try:
            tab = state.prompt_tabs.nametowidget(tab_id)
            text = str(state.prompt_tabs.tab(tab_id, "text") or "")
            cleaned = text.replace(RUNNING_TAB_LEGACY_SUFFIX, "").replace(
                RUNNING_TAB_SUFFIX, ""
            )
            if cleaned.startswith(RUNNING_TAB_PREFIX):
                cleaned = cleaned[len(RUNNING_TAB_PREFIX) :]
            state.prompt_tabs.tab(tab_id, text=cleaned)
            if hasattr(tab, "_orig_tab_text"):
                base = str(getattr(tab, "_orig_tab_text"))
                base = base.replace(RUNNING_TAB_LEGACY_SUFFIX, "").replace(
                    RUNNING_TAB_SUFFIX, ""
                )
                if base.startswith(RUNNING_TAB_PREFIX):
                    base = base[len(RUNNING_TAB_PREFIX) :]
                setattr(tab, "_orig_tab_text", base)
        except Exception:
            continue


def set_prompt_running_visual(
    state: PromptTabsState, tab_id: str | None, running: bool
) -> None:
    def _strip_markers(text: str) -> str:
        out = (
            (text or "")
            .replace(RUNNING_TAB_LEGACY_SUFFIX, "")
            .replace(RUNNING_TAB_SUFFIX, "")
        )
        if out.startswith(RUNNING_TAB_PREFIX):
            out = out[len(RUNNING_TAB_PREFIX) :]
        return out.strip()

    tabs = get_prompt_tabs(state)
    if not tabs:
        return

    if not running or not tab_id:
        for tid in tabs:
            try:
                tab = cast(tk.Widget, state.prompt_tabs.nametowidget(tid))
                base = _strip_markers(str(state.prompt_tabs.tab(tid, "text") or ""))
                state.prompt_tabs.tab(tid, text=base, foreground="")
                if hasattr(tab, "_orig_tab_text"):
                    setattr(
                        tab,
                        "_orig_tab_text",
                        _strip_markers(str(getattr(tab, "_orig_tab_text"))),
                    )
                _tint_prompt_widget_tree(tab, running=False)
            except Exception:
                continue
        return

    for tid in tabs:
        try:
            tab = cast(tk.Widget, state.prompt_tabs.nametowidget(tid))
            base = _strip_markers(str(state.prompt_tabs.tab(tid, "text") or ""))
            state.prompt_tabs.tab(tid, text=base, foreground="")
            if hasattr(tab, "_orig_tab_text"):
                setattr(
                    tab,
                    "_orig_tab_text",
                    _strip_markers(str(getattr(tab, "_orig_tab_text"))),
                )
        except Exception:
            continue

    try:
        tab = cast(tk.Widget, state.prompt_tabs.nametowidget(tab_id))
    except Exception:
        return
    try:
        current_text = str(state.prompt_tabs.tab(tab_id, "text") or "")
        base_text = _strip_markers(current_text)
        if (
            not hasattr(tab, "_orig_tab_text")
            or not str(getattr(tab, "_orig_tab_text") or "").strip()
        ):
            setattr(tab, "_orig_tab_text", base_text)
        base_text = _strip_markers(str(getattr(tab, "_orig_tab_text") or base_text))
        state.prompt_tabs.tab(
            tab_id, text=RUNNING_TAB_PREFIX + base_text, foreground=""
        )
    except Exception:
        pass
    _tint_prompt_widget_tree(tab, running=True)


def _tint_prompt_widget_tree(widget: tk.Misc, running: bool) -> None:
    _ = running
    for child in widget.winfo_children():
        _tint_prompt_widget_tree(child, running)


def get_tab_display_name(state: PromptTabsState, tab_id: str | None) -> str:
    if not tab_id:
        return ""
    try:
        text = str(state.prompt_tabs.tab(tab_id, "text") or "")
    except Exception:
        return ""
    cleaned = text.replace(RUNNING_TAB_LEGACY_SUFFIX, "").replace(
        RUNNING_TAB_SUFFIX, ""
    )
    if cleaned.startswith(RUNNING_TAB_PREFIX):
        cleaned = cleaned[len(RUNNING_TAB_PREFIX) :]
    return cleaned.strip()


def _add_labeled_entry(
    parent: tk.Widget,
    label: str,
    var: tk.StringVar,
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
