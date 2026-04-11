from __future__ import annotations

import tkinter as tk
import ttkbootstrap as ttk


def build_browser_tab(tab_browser: ttk.Frame, vars_map: dict[str, tk.Variable]) -> None:
    browser_card = ttk.Frame(
        tab_browser, style="Card.TFrame", bootstyle="secondary", padding=12
    )
    browser_card.pack(fill="x", padx=10, pady=8)
    _add_section_title(browser_card, "Browser Settings")
    _add_labeled_entry(
        browser_card,
        "Viewport width",
        vars_map["-WIDTH-"],
        width=10,
        desc="Browser viewport width in CSS pixels for the live page.",
    )
    _add_labeled_entry(
        browser_card,
        "Viewport height",
        vars_map["-HEIGHT-"],
        width=10,
        desc="Browser viewport height in CSS pixels for the live page.",
    )
    _add_labeled_entry(
        browser_card,
        "Model width",
        vars_map["-MODEL-W-"],
        width=10,
        desc="Screenshot width sent to the model (0 uses viewport width).",
    )
    _add_labeled_entry(
        browser_card,
        "Model height",
        vars_map["-MODEL-H-"],
        width=10,
        desc="Screenshot height sent to the model (0 uses viewport height).",
    )
    _add_checkbox(
        browser_card,
        "Headless",
        vars_map["-HEADLESS-"],
        desc="Run without a visible browser window for automation.",
    )
    step_train_row = ttk.Frame(browser_card)
    step_train_button = ttk.Checkbutton(
        step_train_row,
        text="Step Training",
        variable=vars_map["-STEP-TRAIN-"],
        style="FieldCheck.TCheckbutton",
    )
    step_train_button.pack(side="left")
    _add_field_help(
        step_train_row,
        "Pause LLM actions so a manual tester can approve or manually interject before committing.",
        indent=24,
    )
    step_train_row.pack(anchor="w", pady=3, fill="x")

    def _sync_step_training_state(*_: object) -> None:
        headless = bool(vars_map["-HEADLESS-"].get())
        if headless:
            if bool(vars_map["-STEP-TRAIN-"].get()):
                vars_map["-STEP-TRAIN-"].set(False)
            step_train_button.state(["disabled"])
        else:
            step_train_button.state(["!disabled"])

    vars_map["-HEADLESS-"].trace_add("write", _sync_step_training_state)
    _sync_step_training_state()
    _add_labeled_entry(
        browser_card,
        "Slowmo (ms)",
        vars_map["-SLOWMO-"],
        width=10,
        desc="Delay between Playwright actions to slow things down.",
    )
    _add_labeled_entry(
        browser_card,
        "Max steps",
        vars_map["-MAX-STEPS-"],
        width=10,
        desc="Maximum agent steps before the run is marked failed.",
    )


def build_tokens_tab(tab_tokens: ttk.Frame, vars_map: dict[str, tk.Variable]) -> None:
    tokens_card = ttk.Frame(
        tab_tokens, style="Card.TFrame", bootstyle="secondary", padding=12
    )
    tokens_card.pack(fill="x", padx=10, pady=8)
    _add_section_title(tokens_card, "Token Settings")
    _add_labeled_entry(
        tokens_card,
        "Max tokens",
        vars_map["-MAX-TOKENS-"],
        width=10,
        desc="Maximum output tokens requested from the model per step.",
    )
    _add_labeled_entry(
        tokens_card,
        "Max tokens margin",
        vars_map["-MAX-TOK-MARGIN-"],
        width=10,
        desc="Extra buffer added when thinking budgets are used.",
    )
    _add_labeled_entry(
        tokens_card,
        "Verify wait (s)",
        vars_map["-VERIFY-WAIT-"],
        width=10,
        desc="Seconds to wait before final success verification.",
    )
    _add_labeled_entry(
        tokens_card,
        "Verify guard min confidence",
        vars_map["-VERIFY-GUARD-CONF-"],
        width=10,
        desc="Min confidence (0-1) for in-step verify to accept PASS. Blocks low-confidence early termination.",
    )


def build_action_settings_tab(
    tab_actions: ttk.Frame, vars_map: dict[str, tk.Variable]
) -> None:
    actions_card = ttk.Frame(
        tab_actions, style="Card.TFrame", bootstyle="secondary", padding=12
    )
    actions_card.pack(fill="x", padx=10, pady=8)
    _add_section_title(actions_card, "Action Timing And Guardrails")
    _add_labeled_entry(
        actions_card,
        "Pre-click sleep (s)",
        vars_map["-PRECLICK-"],
        width=10,
        desc="Pause before click-like actions to allow the UI to settle.",
    )
    _add_labeled_entry(
        actions_card,
        "Pre-type sleep (s)",
        vars_map["-PRETYPE-"],
        width=10,
        desc="Pause before typing to ensure the input has focus.",
    )
    _add_labeled_entry(
        actions_card,
        "Post-shot sleep (s)",
        vars_map["-POST-SHOT-"],
        width=10,
        desc="Pause after each model screenshot to avoid layout shifts.",
    )
    _add_labeled_entry(
        actions_card,
        "Post-action sleep (s)",
        vars_map["-POST-ACTION-"],
        width=10,
        desc="Pause after each Playwright action to slow the sequence.",
    )
    _add_labeled_entry(
        actions_card,
        "Post-type sleep (s)",
        vars_map["-POST-TYPE-"],
        width=10,
        desc="Pause after typing to let the page react to input.",
    )
    _add_checkbox(
        actions_card,
        "Arm commit gating",
        vars_map["-ARM-COMMIT-"],
        desc="Preview clicks first and require confirmation to commit.",
    )
    _add_labeled_entry(
        actions_card,
        "Confirm token",
        vars_map["-CONFIRM-"],
        width=12,
        desc="Word the model must include to commit a gated click.",
    )
    _add_labeled_entry(
        actions_card,
        "Max subactions",
        vars_map["-MAX-SUBACTIONS-"],
        width=10,
        desc="Hard cap on actions per learned function.",
    )
    _add_labeled_entry(
        actions_card,
        "Arm timeout steps",
        vars_map["-ARM-TIMEOUT-"],
        width=10,
        desc="Number of steps before an armed click expires.",
    )


def build_output_tab(tab_output: ttk.Frame, vars_map: dict[str, tk.Variable]) -> None:
    output_card = ttk.Frame(
        tab_output, style="Card.TFrame", bootstyle="secondary", padding=12
    )
    output_card.pack(fill="x", padx=10, pady=8)
    _add_section_title(output_card, "Output And Logging")
    _add_labeled_entry(
        output_card,
        "Screenshot base",
        vars_map["-SCREENSHOT-"],
        width=30,
        desc="Base filename used for success/failure screenshots.",
    )
    _add_labeled_entry(
        output_card,
        "Agent view dir",
        vars_map["-AGENT-DIR-"],
        width=30,
        desc="Folder where per-step agent screenshots are written.",
    )
    _add_checkbox(
        output_card,
        "Disable agent view",
        vars_map["-NO-AGENT-"],
        desc="Disable per-step screenshots to reduce disk usage.",
    )
    _add_labeled_entry(
        output_card,
        "Log file",
        vars_map["-LOG-FILE-"],
        width=30,
        desc="Optional log file path (duplicates stdout/stderr).",
    )
    _add_checkbox(
        output_card,
        "Azure logging",
        vars_map["-AZURE-"],
        desc="Enable Azure Application Insights logging (best-effort).",
    )
    _add_labeled_entry(
        output_card,
        "Site hints path",
        vars_map["-SITE-HINTS-"],
        width=30,
        desc="JSON file storing learned DOM hints per site.",
    )
    _add_labeled_entry(
        output_card,
        "Keep last turns",
        vars_map["-KEEP-TURNS-"],
        width=10,
        desc="How many recent text turns are kept in the prompt.",
    )
    _add_labeled_entry(
        output_card,
        "Keep last images",
        vars_map["-KEEP-IMAGES-"],
        width=10,
        desc="How many recent images are kept in the prompt.",
    )
    _add_checkbox(
        output_card,
        "Verbose logging",
        vars_map["-VERBOSE-"],
        desc="Enable verbose logging to the Run Log.",
    )


def _add_labeled_entry(
    parent: tk.Widget,
    label: str,
    var: tk.Variable,
    width: int = 12,
    desc: str = "",
) -> None:
    row = ttk.Frame(parent)
    top = ttk.Frame(row)
    ttk.Label(top, text=label, width=18, anchor="e", style="FieldLabel.TLabel").pack(
        side="left", padx=(0, 8)
    )
    ttk.Entry(top, textvariable=var, width=width).pack(
        side="left", fill="x", expand=True
    )
    top.pack(fill="x")
    if desc:
        _add_field_help(row, desc, indent=(18 + 8))
    row.pack(anchor="w", pady=3, fill="x")


def _add_checkbox(
    parent: tk.Widget, label: str, var: tk.Variable, desc: str = ""
) -> None:
    row = ttk.Frame(parent)
    ttk.Checkbutton(
        row, text=label, variable=var, style="FieldCheck.TCheckbutton"
    ).pack(side="left")
    if desc:
        _add_field_help(row, desc, indent=24)
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
