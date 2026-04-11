from __future__ import annotations

from pathlib import Path
from typing import Any, List, Tuple

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

from .ui_state import AIViewState

Image: Any
ImageTk: Any
try:
    from PIL import Image, ImageTk

    PIL_UI_OK = True
except Exception:
    Image = None
    ImageTk = None
    PIL_UI_OK = False


def build_ai_view_tab(
    tab_ai_view: ttk.Frame,
    *,
    root: ttk.Window,
    vars_map: dict[str, tk.Variable],
    base_font_size: int,
) -> AIViewState:
    ai_view_pane = tk.PanedWindow(
        tab_ai_view,
        orient="vertical",
        sashwidth=6,
        sashrelief="flat",
        bd=0,
        background="#aeb8c4",
        showhandle=False,
    )
    ai_view_pane.pack(fill="both", expand=True, padx=6, pady=6)
    ai_list_panel = ttk.Frame(ai_view_pane)
    ai_canvas_panel = ttk.Frame(ai_view_pane)
    ai_view_pane.add(ai_list_panel, minsize=180, stretch="always")
    ai_view_pane.add(ai_canvas_panel, minsize=180, stretch="always")

    def _set_ai_view_split(preferred_y: int | None = None) -> None:
        try:
            total_h = max(400, int(ai_view_pane.winfo_height()))
            default_y = int(total_h * 0.25)
            split_y = default_y if preferred_y is None else int(preferred_y)
            split_y = max(160, min(total_h - 160, split_y))
            ai_view_pane.sash_place(0, 0, split_y)
        except Exception:
            pass

    ai_view_pane.bind(
        "<Configure>", lambda _e: ai_view_pane.after_idle(_set_ai_view_split)
    )

    ttk.Label(ai_list_panel, text="agent_view images").pack(anchor="w")
    image_list = tk.Listbox(
        ai_list_panel, width=30, height=12, font=("Segoe UI", base_font_size)
    )
    image_list.pack(side="left", fill="both", expand=True)
    image_scroll = ttk.Scrollbar(
        ai_list_panel, orient="vertical", command=image_list.yview
    )
    image_scroll.pack(side="left", fill="y")
    image_list.configure(yscrollcommand=image_scroll.set)

    canvas = tk.Canvas(
        ai_canvas_panel, background="#0b0b0b", highlightthickness=0, bd=0
    )
    canvas.pack(side="left", fill="both", expand=True)
    canvas_scroll_y = ttk.Scrollbar(
        ai_canvas_panel, orient="vertical", command=canvas.yview
    )
    canvas_scroll_y.pack(side="right", fill="y")
    canvas_scroll_x = ttk.Scrollbar(
        ai_canvas_panel, orient="horizontal", command=canvas.xview
    )
    canvas_scroll_x.pack(side="bottom", fill="x")
    canvas.configure(
        yscrollcommand=canvas_scroll_y.set, xscrollcommand=canvas_scroll_x.set
    )

    ai_view = AIViewState(
        root=root,
        vars_map=vars_map,
        image_list=image_list,
        canvas=canvas,
    )

    image_list.bind(
        "<<ListboxSelect>>", lambda event: _show_selected_image(ai_view, event)
    )
    canvas.bind("<Configure>", lambda _e: _render_ai_image(ai_view))
    ai_view_buttons = ttk.Frame(ai_list_panel)
    ai_view_buttons.pack(anchor="w", pady=(4, 6), before=image_list)
    ttk.Button(
        ai_view_buttons,
        text="Refresh",
        command=lambda: refresh_ai_view(
            ai_view, list_ai_images(ai_view), select_latest=True
        ),
    ).pack(side="left")

    return ai_view


def _agent_view_dir(ai: AIViewState) -> Path:
    folder = (ai.vars_map.get("-AGENT-DIR-") or tk.StringVar()).get()
    base = Path(__file__).resolve().parent.parent
    if not folder:
        folder = "agent_view"
    return base / str(folder)


def list_ai_images(ai: AIViewState) -> List[str]:
    folder = _agent_view_dir(ai)
    if not folder.exists():
        return []
    items: List[Tuple[float, str]] = []
    for p in folder.iterdir():
        if p.suffix.lower() != ".png":
            continue
        try:
            ts = p.stat().st_mtime
        except Exception:
            ts = 0.0
        items.append((ts, p.name))
    # Show newest captures first using file modified time.
    items.sort(key=lambda item: (-item[0], item[1].lower()))
    return [name for _, name in items]


def refresh_ai_view(
    ai: AIViewState, files: List[str], *, select_latest: bool = False
) -> None:
    ai.image_list.delete(0, "end")
    for name in files:
        ai.image_list.insert("end", name)
    if files and select_latest:
        ai.image_list.selection_clear(0, "end")
        ai.image_list.selection_set(0)
        ai.image_list.event_generate("<<ListboxSelect>>")


def _render_ai_image(ai: AIViewState) -> None:
    if ai.current_ai_image_path is None:
        return
    if not ai.current_ai_image_path.exists():
        ai.current_ai_image_path = None
        ai.canvas.delete("all")
        ai.root.after(
            0, lambda: refresh_ai_view(ai, list_ai_images(ai), select_latest=True)
        )
        return
    ai.canvas.update_idletasks()
    canvas_w = max(1, ai.canvas.winfo_width())
    canvas_h = max(1, ai.canvas.winfo_height())
    try:
        if PIL_UI_OK and Image is not None and ImageTk is not None:
            img = Image.open(ai.current_ai_image_path)
            src_w, src_h = img.size
            scale = min(canvas_w / max(1, src_w), canvas_h / max(1, src_h))
            target_w = max(1, int(src_w * scale))
            target_h = max(1, int(src_h * scale))
            resampling = getattr(Image, "Resampling", None)
            if resampling is not None:
                resample_filter = resampling.LANCZOS
            else:
                resample_filter = getattr(Image, "LANCZOS", Image.BICUBIC)
            resized = img.resize((target_w, target_h), resample_filter)
            ai.canvas_image_ref = ImageTk.PhotoImage(resized)
        else:
            base_img = tk.PhotoImage(file=str(ai.current_ai_image_path))
            scale_w = max(1, (base_img.width() + canvas_w - 1) // canvas_w)
            scale_h = max(1, (base_img.height() + canvas_h - 1) // canvas_h)
            scale = max(scale_w, scale_h)
            ai.canvas_image_ref = base_img.subsample(scale, scale)
    except Exception as exc:
        if not ai.current_ai_image_path or not ai.current_ai_image_path.exists():
            ai.current_ai_image_path = None
            ai.canvas.delete("all")
            ai.root.after(
                0, lambda: refresh_ai_view(ai, list_ai_images(ai), select_latest=True)
            )
            return
        messagebox.showerror("Image load failed", str(exc))
        return
    ai.canvas.delete("all")
    ai.canvas_image_id = ai.canvas.create_image(
        canvas_w // 2,
        canvas_h // 2,
        anchor="center",
        image=ai.canvas_image_ref,
    )
    ai.canvas.configure(scrollregion=(0, 0, canvas_w, canvas_h))


def _show_selected_image(ai: AIViewState, _: object = None) -> None:
    sel = ai.image_list.curselection()
    if not sel:
        return
    name = ai.image_list.get(sel[0])
    img_path = _agent_view_dir(ai) / name
    if not img_path.exists():
        ai.current_ai_image_path = None
        ai.root.after(
            0, lambda: refresh_ai_view(ai, list_ai_images(ai), select_latest=True)
        )
        return
    ai.current_ai_image_path = img_path
    ai.root.after(0, lambda: _render_ai_image(ai))


def poll_ai_view(ai: AIViewState) -> None:
    files = list_ai_images(ai)
    if files != ai.last_ai_files:
        ai.last_ai_files = files
        refresh_ai_view(ai, files, select_latest=True)
    ai.root.after(500, lambda: poll_ai_view(ai))


def clear_agent_view_images(ai: AIViewState) -> None:
    folder = _agent_view_dir(ai)
    if not folder.exists():
        return
    for p in folder.iterdir():
        if p.suffix.lower() == ".png":
            try:
                p.unlink()
            except Exception:
                pass
    ai.last_ai_files = []
    refresh_ai_view(ai, [], select_latest=False)
