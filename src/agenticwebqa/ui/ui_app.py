from __future__ import annotations

import ctypes
import ctypes.wintypes
from dataclasses import dataclass
from typing import Callable

import tkinter as tk
import tkinter.font as tkfont
import ttkbootstrap as ttk


@dataclass
class RootLayout:
    root: ttk.Window
    left_panel: ttk.Frame
    right_panel: ttk.Frame
    set_default_split: Callable[[int | None, float | None], None]
    get_split_sash_x: Callable[[], int | None]
    base_font_size: int
    text_font_size: int
    tab_font_size: int
    button_font_size: int
    root_bg: str
    card_bg: str
    win_w: int
    win_h: int
    x: int
    y: int
    logical_left: int
    logical_top: int
    logical_right: int
    logical_bottom: int


def build_root_layout(*, running_tint_bg: str) -> RootLayout:
    root = ttk.Window(themename="flatly")
    root.withdraw()
    style = ttk.Style()
    root_bg = "#eef2f6"
    root.configure(background=root_bg)
    base_font_size = 12
    text_font_size = 13
    tab_font_size = 12
    button_font_size = 12
    for font_name in (
        "TkDefaultFont",
        "TkTextFont",
        "TkHeadingFont",
        "TkMenuFont",
        "TkCaptionFont",
        "TkSmallCaptionFont",
        "TkFixedFont",
    ):
        try:
            f = tkfont.nametofont(font_name)
            f.configure(
                size=base_font_size if font_name != "TkTextFont" else text_font_size
            )
        except Exception:
            pass
    style.configure(
        "TNotebook.Tab",
        padding=(12, 8),
        background="#e6e6e6",
        font=("Segoe UI", tab_font_size),
    )
    style.configure("TButton", font=("Segoe UI", button_font_size), padding=(10, 6))
    style.configure("TLabel", font=("Segoe UI", base_font_size))
    style.configure("TEntry", font=("Segoe UI", base_font_size))
    style.configure("TCombobox", font=("Segoe UI", base_font_size))
    style.configure("TCheckbutton", font=("Segoe UI", base_font_size))
    style.configure("TRadiobutton", font=("Segoe UI", base_font_size))
    style.configure("TFrame", background=root_bg)
    style.configure("TNotebook", background=root_bg)
    card_bg = "#f3f5f7"
    style.configure("Card.TFrame", background=card_bg, borderwidth=1, relief="solid")
    style.configure(
        "SectionTitle.TLabel",
        font=("Segoe UI", base_font_size + 3, "bold"),
        foreground="#223142",
    )
    style.configure(
        "FieldLabel.TLabel",
        font=("Segoe UI", base_font_size + 1, "bold"),
        foreground="#1b314a",
        background=card_bg,
    )
    style.configure(
        "FieldCheck.TCheckbutton",
        font=("Segoe UI", base_font_size + 1),
        foreground="#1b314a",
    )
    style.configure("FieldHelpRow.TFrame", background="#dfe7f1")
    style.configure(
        "FieldHelp.TLabel",
        font=("Segoe UI", max(10, base_font_size - 1)),
        foreground="#2e4762",
        background="#dfe7f1",
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", "#ffffff")],
        foreground=[("selected", "#000000")],
    )
    style.configure("RunningPrompt.TFrame", background=running_tint_bg)
    style.configure("RunningPrompt.TLabel", background=running_tint_bg)
    style.configure("RunningPrompt.TEntry", fieldbackground=running_tint_bg)
    style.configure("RunningPrompt.TCombobox", fieldbackground=running_tint_bg)
    base_title = "OpenAI Vision Launcher"
    root.title(base_title)
    root.update_idletasks()
    win_w = int(820 * 1.6)
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    work_left = 0
    work_top = 0
    work_right = screen_w
    work_bottom = screen_h
    try:
        spi_get_work_area = 0x0030
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(
            spi_get_work_area, 0, ctypes.byref(rect), 0
        )
        work_left, work_top, work_right, work_bottom = (
            rect.left,
            rect.top,
            rect.right,
            rect.bottom,
        )
    except Exception:
        pass
    try:
        scale = float(root.winfo_fpixels("1i")) / 96.0
        if scale <= 0:
            scale = 1.0
    except Exception:
        scale = 1.0
    logical_left = int(work_left / scale)
    logical_top = int(work_top / scale)
    logical_right = int(work_right / scale)
    logical_bottom = int(work_bottom / scale)
    available_h = max(200, logical_bottom - logical_top)
    win_h = max(200, int(available_h * 0.9))
    x = max(logical_left, logical_right - win_w)
    y = logical_top
    root.geometry(f"{win_w}x{win_h}+{x}+{y}")

    bg_gradient = tk.Canvas(root, highlightthickness=0, bd=0, background=root_bg)
    bg_gradient.place(x=0, y=0, relwidth=1, relheight=1)
    root.tk.call("lower", str(bg_gradient))
    gradient_last_size: list[int] = [0, 0]
    gradient_after_id: list[str | None] = [None]

    def _refresh_root_gradient(_: object = None) -> None:
        w = max(1, int(bg_gradient.winfo_width()))
        h = max(1, int(bg_gradient.winfo_height()))
        if gradient_last_size[0] == w and gradient_last_size[1] == h:
            return
        gradient_last_size[0] = w
        gradient_last_size[1] = h
        _draw_vertical_gradient(bg_gradient, "#b8d1eb", "#e4ebf4")
        root.tk.call("lower", str(bg_gradient))

    def _schedule_root_gradient(_: object = None) -> None:
        if gradient_after_id[0]:
            try:
                root.after_cancel(gradient_after_id[0])
            except Exception:
                pass
        gradient_after_id[0] = root.after(40, _refresh_root_gradient)

    root.bind("<Configure>", _schedule_root_gradient)
    _schedule_root_gradient()

    split_pane = tk.PanedWindow(
        root,
        orient="horizontal",
        sashwidth=6,
        sashrelief="flat",
        bd=0,
        background="#aeb8c4",
        showhandle=False,
    )
    split_pane.pack(fill="both", expand=True, padx=8, pady=8)
    left_panel = ttk.Frame(split_pane)
    right_panel = ttk.Frame(split_pane)
    split_pane.add(left_panel, minsize=500, stretch="always")
    split_pane.add(right_panel, minsize=420, stretch="always")

    def _set_default_split(
        preferred_x: int | None = None, preferred_ratio: float | None = None
    ) -> None:
        try:
            total_w = max(1000, int(split_pane.winfo_width()))
            min_left = 420
            min_right = 360
            default_x = int(total_w * 0.50)
            split_x = default_x
            if preferred_ratio is not None:
                if 0.20 <= preferred_ratio <= 0.80:
                    split_x = int(total_w * preferred_ratio)
            elif preferred_x is not None:
                preferred_ratio = preferred_x / float(total_w)
                if 0.40 <= preferred_ratio <= 0.60:
                    split_x = int(preferred_x)
            split_x = max(min_left, min(total_w - min_right, split_x))
            split_pane.sash_place(0, split_x, 0)
        except Exception:
            pass

    def _get_split_sash_x() -> int | None:
        try:
            split_x, _ = split_pane.sash_coord(0)
            return int(split_x)
        except Exception:
            return None

    return RootLayout(
        root=root,
        left_panel=left_panel,
        right_panel=right_panel,
        set_default_split=_set_default_split,
        get_split_sash_x=_get_split_sash_x,
        base_font_size=base_font_size,
        text_font_size=text_font_size,
        tab_font_size=tab_font_size,
        button_font_size=button_font_size,
        root_bg=root_bg,
        card_bg=card_bg,
        win_w=win_w,
        win_h=win_h,
        x=x,
        y=y,
        logical_left=logical_left,
        logical_top=logical_top,
        logical_right=logical_right,
        logical_bottom=logical_bottom,
    )


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) != 6:
        return (0, 0, 0)
    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    )


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return (
        f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"
    )


def _draw_vertical_gradient(
    canvas: tk.Canvas, top_color: str, bottom_color: str
) -> None:
    canvas.update_idletasks()
    w = max(1, int(canvas.winfo_width()))
    h = max(1, int(canvas.winfo_height()))
    canvas.delete("grad")
    c1 = _hex_to_rgb(top_color)
    c2 = _hex_to_rgb(bottom_color)
    for y in range(h):
        t = y / max(1, h - 1)
        rgb = (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        )
        color = _rgb_to_hex(rgb)
        canvas.create_line(0, y, w, y, fill=color, tags="grad")
