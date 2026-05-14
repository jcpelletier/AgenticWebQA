from __future__ import annotations

import os
from typing import Callable, Tuple

import tkinter as tk

import ttkbootstrap as ttk


def build_credentials_tab(
    tab_creds: ttk.Frame,
    *,
    root: ttk.Window,
    vars_map: dict[str, tk.Variable],
    add_section_title: Callable[[tk.Widget, str], None],
    add_field_help: Callable[[tk.Widget, str, int], None],
    add_labeled_entry: Callable[[tk.Widget, str, tk.Variable, int, str], None],
    add_labeled_password: Callable[[tk.Widget, str, tk.Variable, int, str], None],
) -> Tuple[tk.StringVar, tk.StringVar, tk.StringVar, Callable[[], None]]:
    openai_key_var = tk.StringVar(
        value=(os.environ.get("OPENAI_API_KEY") or "").strip()
    )
    anthropic_key_var = tk.StringVar(
        value=(os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    )
    gemini_key_var = tk.StringVar(
        value=(os.environ.get("GEMINI_API_KEY") or "").strip()
    )

    def _set_api_status() -> None:
        openai_current = (openai_key_var.get() or "").strip()
        anthropic_current = (anthropic_key_var.get() or "").strip()
        gemini_current = (gemini_key_var.get() or "").strip()
        openai_status_label.configure(
            text=("OK" if openai_current else "MISSING"),
            foreground=("green" if openai_current else "red"),
        )
        anthropic_status_label.configure(
            text=("OK" if anthropic_current else "MISSING"),
            foreground=("green" if anthropic_current else "red"),
        )
        gemini_status_label.configure(
            text=("OK" if gemini_current else "MISSING"),
            foreground=("green" if gemini_current else "red"),
        )

    def _apply_api_key() -> None:
        openai_raw = (openai_key_var.get() or "").strip()
        if openai_raw:
            os.environ["OPENAI_API_KEY"] = openai_raw
        else:
            os.environ.pop("OPENAI_API_KEY", None)
        anthropic_raw = (anthropic_key_var.get() or "").strip()
        if anthropic_raw:
            os.environ["ANTHROPIC_API_KEY"] = anthropic_raw
        else:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        gemini_raw = (gemini_key_var.get() or "").strip()
        if gemini_raw:
            os.environ["GEMINI_API_KEY"] = gemini_raw
        else:
            os.environ.pop("GEMINI_API_KEY", None)
        _set_api_status()

    creds_api_card = ttk.Frame(
        tab_creds, style="Card.TFrame", bootstyle="secondary", padding=12
    )
    creds_api_card.pack(fill="x", padx=10, pady=(8, 4))
    add_section_title(creds_api_card, "API Credentials")
    add_field_help(
        creds_api_card,
        "Credentials are environment-variable only. This UI does not save API keys, usernames, or passwords to its session state file.",
        0,
    )
    add_field_help(
        creds_api_card,
        "API key fields map to environment variables: OPENAI_API_KEY, ANTHROPIC_API_KEY, and GEMINI_API_KEY",
        0,
    )
    creds_key_row = ttk.Frame(creds_api_card)
    ttk.Label(creds_key_row, text="OpenAI API Key", width=18, anchor="w").pack(
        side="left", padx=(0, 8)
    )
    openai_entry = ttk.Entry(
        creds_key_row, width=30, show="*", textvariable=openai_key_var
    )
    openai_entry.pack(side="left")
    openai_status_label = ttk.Label(creds_key_row, text="")
    openai_status_label.pack(side="left", padx=(8, 0))
    creds_key_row.pack(anchor="w", pady=2, fill="x")

    anthropic_key_row = ttk.Frame(creds_api_card)
    ttk.Label(anthropic_key_row, text="Claude API Key", width=18, anchor="w").pack(
        side="left", padx=(0, 8)
    )
    anthropic_entry = ttk.Entry(
        anthropic_key_row, width=30, show="*", textvariable=anthropic_key_var
    )
    anthropic_entry.pack(side="left")
    anthropic_status_label = ttk.Label(anthropic_key_row, text="")
    anthropic_status_label.pack(side="left", padx=(8, 0))
    anthropic_key_row.pack(anchor="w", pady=2, fill="x")

    gemini_key_row = ttk.Frame(creds_api_card)
    ttk.Label(gemini_key_row, text="Gemini API Key", width=18, anchor="w").pack(
        side="left", padx=(0, 8)
    )
    gemini_entry = ttk.Entry(
        gemini_key_row, width=30, show="*", textvariable=gemini_key_var
    )
    gemini_entry.pack(side="left")
    gemini_status_label = ttk.Label(gemini_key_row, text="")
    gemini_status_label.pack(side="left", padx=(8, 0))
    gemini_key_row.pack(anchor="w", pady=2, fill="x")

    ttk.Button(creds_api_card, text="Apply", command=_apply_api_key).pack(
        anchor="w", pady=(6, 0)
    )
    _set_api_status()

    def _api_key_changed(_: object = None) -> None:
        _apply_api_key()

    openai_entry.bind("<KeyRelease>", _api_key_changed)
    openai_entry.bind("<<Paste>>", _api_key_changed)
    openai_entry.bind("<FocusOut>", _api_key_changed)
    anthropic_entry.bind("<KeyRelease>", _api_key_changed)
    anthropic_entry.bind("<<Paste>>", _api_key_changed)
    anthropic_entry.bind("<FocusOut>", _api_key_changed)
    gemini_entry.bind("<KeyRelease>", _api_key_changed)
    gemini_entry.bind("<<Paste>>", _api_key_changed)
    gemini_entry.bind("<FocusOut>", _api_key_changed)

    vars_map["-USERNAME-"].set((os.environ.get("AGENTICWEBQA_USERNAME") or "").strip())
    vars_map["-PASSWORD-"].set(os.environ.get("AGENTICWEBQA_PASSWORD") or "")

    def _apply_creds() -> None:
        username = (vars_map["-USERNAME-"].get() or "").strip()
        password = vars_map["-PASSWORD-"].get() or ""
        if username:
            os.environ["AGENTICWEBQA_USERNAME"] = username
        else:
            os.environ.pop("AGENTICWEBQA_USERNAME", None)
        if password:
            os.environ["AGENTICWEBQA_PASSWORD"] = password
        else:
            os.environ.pop("AGENTICWEBQA_PASSWORD", None)

    creds_login_card = ttk.Frame(
        tab_creds, style="Card.TFrame", bootstyle="secondary", padding=12
    )
    creds_login_card.pack(fill="x", padx=10, pady=(4, 8))
    add_section_title(creds_login_card, "Site Credentials")
    add_field_help(
        creds_login_card,
        "Username maps to AGENTICWEBQA_USERNAME. Password maps to AGENTICWEBQA_PASSWORD.",
        0,
    )
    add_labeled_entry(
        creds_login_card,
        "Username",
        vars_map["-USERNAME-"],
        30,
        "Optional username passed to the run.",
    )
    add_labeled_password(
        creds_login_card,
        "Password",
        vars_map["-PASSWORD-"],
        30,
        "Optional password passed to the run.",
    )

    username_entry = None
    password_entry = None
    try:
        username_row = creds_login_card.winfo_children()[1]
        password_row = creds_login_card.winfo_children()[2]
        username_entry = username_row.winfo_children()[1]
        password_entry = password_row.winfo_children()[1]
    except Exception:
        username_entry = None
        password_entry = None

    def _creds_changed(_: object = None) -> None:
        _apply_creds()

    if username_entry is not None:
        username_entry.bind("<KeyRelease>", _creds_changed)
        username_entry.bind("<<Paste>>", _creds_changed)
        username_entry.bind("<FocusOut>", _creds_changed)
    if password_entry is not None:
        password_entry.bind("<KeyRelease>", _creds_changed)
        password_entry.bind("<<Paste>>", _creds_changed)
        password_entry.bind("<FocusOut>", _creds_changed)

    return openai_key_var, anthropic_key_var, gemini_key_var, _apply_api_key


def build_run_log_panel(
    right_panel: ttk.Frame,
    *,
    text_font_size: int,
) -> Tuple[tk.Text, ttk.Button, ttk.Frame]:
    log_container = ttk.Frame(right_panel)
    log_container.pack(fill="both", expand=True, padx=6, pady=6)

    log_card = ttk.Frame(
        log_container, style="Card.TFrame", bootstyle="secondary", padding=12
    )
    log_card.pack(fill="both", expand=True, padx=10, pady=6)
    log_header = ttk.Frame(log_card)
    ttk.Label(log_header, text="Run Log", style="SectionTitle.TLabel").pack(
        side="left", padx=(0, 6)
    )
    continue_button = ttk.Button(log_header, text="Continue", bootstyle="success")
    continue_button.pack(side="right")
    log_header.pack(fill="x", pady=(0, 6))
    log_frame = ttk.Frame(log_card)
    log_frame.pack(fill="both", expand=True, pady=(2, 6))
    log_scroll = ttk.Scrollbar(log_frame, orient="vertical")
    log_scroll.pack(side="right", fill="y")
    log_text = tk.Text(
        log_card,
        height=6,
        width=90,
        state="disabled",
        yscrollcommand=log_scroll.set,
        font=("Consolas", text_font_size),
    )
    log_text.pack(in_=log_frame, side="left", fill="both", expand=True)
    log_scroll.config(command=log_text.yview)
    return log_text, continue_button, log_container


def build_run_button_bar(
    left_panel: ttk.Frame,
    *,
    run_callback: Callable[[], None],
) -> Tuple[ttk.Button, ttk.Frame, ttk.Label, ttk.Frame]:
    button_frame = ttk.Frame(left_panel)
    button_frame.pack(fill="x", padx=6, pady=6)
    run_button = ttk.Button(
        button_frame, text="Run", command=run_callback, bootstyle="success"
    )
    run_button.pack(side="left", padx=8)

    info_bar = ttk.Frame(button_frame)
    info_label = ttk.Label(info_bar, text="", anchor="w")
    info_label.pack(side="left", padx=(12, 0), pady=4)
    return run_button, info_bar, info_label, button_frame
