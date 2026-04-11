from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

from .ui_state import ActionsLibState


def build_actions_library_tab(
    tab_actions_lib: ttk.Frame,
    *,
    root: ttk.Window,
    base_font_size: int,
    text_font_size: int,
) -> ActionsLibState:
    tab_actions_lib.columnconfigure(0, weight=0, minsize=240)
    tab_actions_lib.columnconfigure(1, weight=1)
    tab_actions_lib.rowconfigure(0, weight=1)

    actions_left = ttk.Frame(tab_actions_lib, width=240)
    actions_left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=6)
    actions_right = ttk.Frame(tab_actions_lib)
    actions_right.grid(row=0, column=1, sticky="nsew", pady=6)

    _add_section_title(actions_left, "Saved Actions By Site")
    _add_section_title(actions_right, "Actions File Contents")
    actions_text = tk.Text(
        actions_right, height=10, width=90, font=("Consolas", text_font_size)
    )
    actions_text.pack(fill="both", expand=True, pady=(2, 6))

    actions_buttons = ttk.Frame(actions_left)
    actions_buttons.pack(anchor="w", pady=(4, 6))

    actions_list_frame = ttk.Frame(actions_left)
    actions_list_frame.pack(side="top", fill="x")
    actions_list = tk.Listbox(
        actions_list_frame, width=24, height=9, font=("Segoe UI", base_font_size)
    )
    actions_list.pack(side="left", fill="y")
    actions_scroll = ttk.Scrollbar(
        actions_list_frame, orient="vertical", command=actions_list.yview
    )
    actions_scroll.pack(side="left", fill="y")
    actions_list.configure(yscrollcommand=actions_scroll.set)

    _add_section_title(actions_left, "Actions In File")
    actions_action_buttons = ttk.Frame(actions_left)
    actions_action_buttons.pack(anchor="w", pady=(0, 6), fill="x")

    actions_buttons_frame = ttk.Frame(actions_left, width=220)
    actions_buttons_frame.pack(side="top", fill="both", expand=True, pady=(4, 6))
    actions_buttons_frame.pack_propagate(False)
    actions_buttons_canvas = tk.Canvas(actions_buttons_frame, width=220)
    actions_buttons_canvas.pack(side="left", fill="both", expand=True)
    actions_buttons_scroll = ttk.Scrollbar(
        actions_buttons_frame, orient="vertical", command=actions_buttons_canvas.yview
    )
    actions_buttons_scroll.pack(side="right", fill="y")
    actions_buttons_canvas.configure(yscrollcommand=actions_buttons_scroll.set)
    actions_buttons_inner = ttk.Frame(actions_buttons_canvas)
    actions_buttons_canvas.create_window(
        (0, 0), window=actions_buttons_inner, anchor="nw"
    )

    actions_state = ActionsLibState(
        root=root,
        actions_list=actions_list,
        actions_text=actions_text,
        actions_buttons_inner=actions_buttons_inner,
        actions_buttons_canvas=actions_buttons_canvas,
    )

    ttk.Button(
        actions_action_buttons,
        text="Save Action",
        command=lambda: save_actions_file(actions_state),
    ).pack(side="left")
    ttk.Button(
        actions_buttons,
        text="Refresh",
        command=lambda: refresh_actions_list(actions_state),
    ).pack(side="left", padx=(0, 6))
    ttk.Button(
        actions_buttons, text="Save", command=lambda: save_actions_file(actions_state)
    ).pack(side="left")
    ttk.Button(
        actions_buttons,
        text="Delete",
        command=lambda: delete_actions_file(actions_state),
    ).pack(side="left", padx=(6, 0))

    actions_list.bind(
        "<<ListboxSelect>>", lambda event: load_selected_actions(actions_state, event)
    )
    actions_buttons_inner.bind(
        "<Configure>", lambda event: sync_actions_buttons_scroll(actions_state, event)
    )

    return actions_state


def _add_section_title(parent: tk.Widget, text: str) -> None:
    ttk.Label(parent, text=text, style="SectionTitle.TLabel").pack(
        anchor="w", pady=(0, 6)
    )


def _models_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "Models"


def _truncate_action_name(name: str, max_len: int = 22) -> str:
    safe = (name or "").strip()
    if len(safe) <= max_len:
        return safe
    return safe[: max(0, max_len - 1)] + "..."


def refresh_actions_list(state: ActionsLibState) -> None:
    state.actions_list.delete(0, "end")
    models_dir = _models_dir()
    if not models_dir.exists():
        return
    files = sorted(
        [p for p in models_dir.iterdir() if p.suffix.lower() == ".json"],
        key=lambda p: p.name,
    )
    for p in files:
        state.actions_list.insert("end", p.name)


def _refresh_actions_buttons(
    state: ActionsLibState, data: Dict[str, Any] | None
) -> None:
    state.actions_buttons_map = {}
    for child in state.actions_buttons_inner.winfo_children():
        child.destroy()
    state.actions_buttons_canvas.update_idletasks()
    if not data:
        return
    funcs = data.get("functions") if isinstance(data, dict) else None
    if not isinstance(funcs, list):
        return
    for idx, func in enumerate(funcs):
        if not isinstance(func, dict):
            continue
        name = str(func.get("name") or "").strip()
        if not name:
            continue
        label = _truncate_action_name(name)

        def _handle_select(i: int = idx) -> None:
            _select_action_index(state, i)

        def _handle_menu(event: tk.Event, i: int = idx) -> None:
            _show_action_menu(state, event, i)

        btn = ttk.Button(
            state.actions_buttons_inner,
            text=label,
            bootstyle="secondary",
            command=_handle_select,
        )
        btn.pack(fill="x", padx=2, pady=2)
        btn.bind("<Button-3>", _handle_menu)
        btn.bind("<Button-2>", _handle_menu)
        btn.bind("<Control-Button-1>", _handle_menu)
        state.actions_buttons_map[idx] = btn


def _select_action_index(state: ActionsLibState, index: int | None) -> None:
    if index is None or state.current_actions_data is None:
        state.current_action_index = None
        state.actions_text.delete("1.0", "end")
        return
    funcs = state.current_actions_data.get("functions")
    if not isinstance(funcs, list) or not funcs:
        state.current_action_index = None
        state.actions_text.delete("1.0", "end")
        return
    idx = max(0, min(int(index), len(funcs) - 1))
    state.current_action_index = idx
    action_obj = funcs[idx] if isinstance(funcs[idx], dict) else {}
    state.actions_text.delete("1.0", "end")
    state.actions_text.insert("1.0", json.dumps(action_obj, indent=2))
    for key, btn in state.actions_buttons_map.items():
        try:
            btn.configure(bootstyle="primary" if key == idx else "secondary")
        except Exception:
            pass


def load_selected_actions(state: ActionsLibState, _: object = None) -> None:
    sel = state.actions_list.curselection()
    if not sel:
        return
    name = state.actions_list.get(sel[0])
    path = _models_dir() / name
    if not path.exists():
        return
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        messagebox.showerror("Load failed", str(exc))
        return
    state.current_actions_path = path
    try:
        parsed = json.loads(content)
    except Exception as exc:
        messagebox.showerror("Load failed", f"Invalid JSON: {exc}")
        return
    if not isinstance(parsed, dict):
        messagebox.showerror("Load failed", "Actions file must be a JSON object.")
        return
    state.current_actions_data = parsed
    _refresh_actions_buttons(state, parsed)
    _select_action_index(state, 0)


def save_actions_file(state: ActionsLibState) -> None:
    if state.current_actions_path is None:
        messagebox.showinfo("No file selected", "Select an actions file to save.")
        return
    if state.current_actions_data is None:
        messagebox.showinfo("No actions loaded", "Select an actions file to save.")
        return
    if state.current_action_index is None:
        messagebox.showinfo(
            "No action selected", "Select an action button to save changes."
        )
        return
    try:
        edited = state.actions_text.get("1.0", "end").strip()
        updated_action = json.loads(edited) if edited else None
    except Exception as exc:
        messagebox.showerror("Save failed", f"Invalid action JSON: {exc}")
        return
    if not isinstance(updated_action, dict):
        messagebox.showerror("Save failed", "Action JSON must be an object.")
        return
    funcs = state.current_actions_data.get("functions")
    if not isinstance(funcs, list) or state.current_action_index >= len(funcs):
        messagebox.showerror("Save failed", "Actions list is invalid.")
        return
    funcs[state.current_action_index] = updated_action
    try:
        content = json.dumps(state.current_actions_data, indent=2)
        state.current_actions_path.write_text(content, encoding="utf-8")
    except Exception as exc:
        messagebox.showerror("Save failed", str(exc))
        return
    messagebox.showinfo("Saved", f"Saved {state.current_actions_path.name}")
    _refresh_actions_buttons(state, state.current_actions_data)
    _select_action_index(state, state.current_action_index)


def _delete_action_by_index(state: ActionsLibState, index: int) -> None:
    if state.current_actions_path is None or state.current_actions_data is None:
        messagebox.showinfo("No file selected", "Select an actions file first.")
        return
    funcs = state.current_actions_data.get("functions")
    if not isinstance(funcs, list) or not funcs:
        messagebox.showinfo("No actions", "No actions to delete.")
        return
    if index < 0 or index >= len(funcs):
        messagebox.showerror("Delete failed", "Selected action index is out of range.")
        return
    action_name = str(funcs[index].get("name") or "selected action")
    confirm = messagebox.askyesno(
        "Delete action",
        f"Delete action '{action_name}' from this file? This cannot be undone.",
        parent=state.root,
    )
    if not confirm:
        return
    del funcs[index]
    try:
        content = json.dumps(state.current_actions_data, indent=2)
        state.current_actions_path.write_text(content, encoding="utf-8")
    except Exception as exc:
        messagebox.showerror("Delete failed", str(exc))
        return
    funcs = state.current_actions_data.get("functions")
    if not isinstance(funcs, list):
        messagebox.showerror("Delete failed", "Actions list is missing after delete.")
        return
    if not funcs:
        state.current_action_index = None
        state.actions_text.delete("1.0", "end")
        _refresh_actions_buttons(state, state.current_actions_data)
        return
    state.current_action_index = min(index, len(funcs) - 1)
    _refresh_actions_buttons(state, state.current_actions_data)
    _select_action_index(state, state.current_action_index)


def _show_action_menu(state: ActionsLibState, event: tk.Event, index: int) -> None:
    menu = tk.Menu(state.root, tearoff=0)
    try:

        def _handle_delete() -> None:
            _delete_action_by_index(state, index)

        menu.add_command(label="Delete", command=_handle_delete)
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def delete_actions_file(state: ActionsLibState) -> None:
    if state.current_actions_path is None:
        messagebox.showinfo("No file selected", "Select an actions file to delete.")
        return
    name = state.current_actions_path.name
    confirm = messagebox.askyesno(
        "Delete actions file",
        f"Delete {name}? This cannot be undone.",
    )
    if not confirm:
        return
    try:
        state.current_actions_path.unlink()
    except Exception as exc:
        messagebox.showerror("Delete failed", str(exc))
        return
    state.current_actions_path = None
    state.current_actions_data = None
    state.current_action_index = None
    state.actions_text.delete("1.0", "end")
    _refresh_actions_buttons(state, None)
    refresh_actions_list(state)
    messagebox.showinfo("Deleted", f"Deleted {name}")


def sync_actions_buttons_scroll(state: ActionsLibState, _: object = None) -> None:
    state.actions_buttons_canvas.configure(
        scrollregion=state.actions_buttons_canvas.bbox("all")
    )
