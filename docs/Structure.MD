# Structure

This document outlines the major classes, functions, and control flow in `vision_playwright_openai_vision_poc.py` to help new engineers orient quickly.

**High-Level Flow**
1. `main()` parses CLI args, configures logging, builds Playwright context, and dispatches to `run_agent()`.
2. `run_agent()` orchestrates:
   - LLM interaction and step generation
   - DOM heuristics and action execution
   - Success verification
   - Optional action learning/splitting into reusable functions
3. Results are logged with strict `FINAL: PASS|FAIL` handling.

**Key Data Classes**
- `Viewport`: Simple width/height container.
- `CoordinateTransform`: Converts between model (LLM image) coordinates and actual viewport coordinates.
  - `to_actual()`, `to_model()`
- `RunOutcome`: Holds verdict, actions list, and error message.
- `_TemplateVars`: `dict` subclass for safe string formatting with default values.
- `ArmedClick`: Tracks â€œarm/commitâ€ click gating state (confirmable clicks).
- `_TeeStream`: Mirrors stdout/stderr to a log file.

**Logging + Telemetry**
- `_init_logger()`, `_refresh_logger_stream()`: Configure stdout logging.
- `_squelch_final_tokens()`: Prevent duplicate `FINAL:` tokens in non-final logs.
- `_log_info()`, `_log_warn()`, `_log_error()`, `_log_final()`: Logging helpers; `_log_final()` enforces single verdict.
- `_init_log_file()`: Tee stdout/stderr to file.
- `_init_azure_logging()`: Optional Azure Monitor wiring.

**Config + Constants**
- Shared defaults live in `config_shared.py` (model/provider/timing/viewport/safety defaults used by both CLI and UI).
- Shared CLI argument metadata and UI value validation helpers also live in `config_shared.py`.
- Runtime-specific constants remain in `vision_playwright_openai_vision_poc.py` (token policy, regex, retry tuning, etc.).
- Regex: `FINAL_RE` for verdict extraction.

**Filesystem + JSON Helpers**
- `ensure_dir()`, `ensure_dir_for_file()`: Directory creation.
- `stamp_path()`, `final_stamp_path()`: Screenshot naming.
- `_safe_json_load()`, `_safe_json_write()`: Robust JSON IO.
- `load_site_hints()`, `save_site_hints()`: Persist domain-specific hints.

**Prompt/Function Naming + Metadata**
- `_sanitize_filename()`, `_prompt_to_func_name()`, `_normalize_function_name()`, `_is_generic_function_name()`.
- `_suggest_function_name()`: Picks function name based on inferred tags.
- `_extract_quoted_value()`, `_replace_quoted_value()`.
- `_infer_function_metadata()`: Infer tags, inputs, selectors, pre/post conditions from steps.
- `_extract_function_metadata()`, `_merge_function_metadata()`: Combine explicit and inferred metadata.
- `_format_function_metadata_for_prompt()`: Format metadata into model prompt text.

**Step Signatures + Splitting**
- `_step_signature()`, `_summarize_steps()`.
- `_strip_known_prefix_steps()`: Remove steps already covered by known functions.
- `_is_capped_interaction()`, `_split_steps_by_action_cap()`: Enforce sub-action caps.
- `split_steps_with_existing_functions()`: Match steps to existing functions first.
- `split_steps_with_llm()`: Ask LLM to segment steps into functions.
- `split_steps_with_reuse_llm()`: LLM-guided reuse of existing functions.

**Model File Management**
- `model_path_for_url()`: Map domain ? model json path.
- `load_page_model()`, `save_page_model()`.
- `get_prompt_route()`, `set_prompt_route()`: Persist prompt ? function sequence routing.

**LLM Response Parsing**
- `extract_openai_response_text()`, `extract_openai_output_types()`.
- `extract_openai_tool_calls()`, `build_openai_tool_output_inputs()`.
- `extract_final_verdict()`, `extract_final_verdict_from_text()`.
- `extract_assistant_text_blocks()`, `_extract_json_object()`.
- `debug_openai_response_summary()`: Structured debug logging.

**Provider Routing**
- Runtime infers provider from selected model (`gpt-*` => OpenAI, `claude-*` => Anthropic).
- Provider-specific API key requirements are enforced via `model_api_env_var()` from shared config.
- `_new_model_client()` returns a normalized client adapter so call sites continue using `client.responses.create(...)`.

**Usage + Tokens**
- `_get_usage_value()`, `print_usage_tokens()`.

**Input Normalization**
- `normalize_openai_action_input()`: Normalize tool payloads.
- `normalize_action_name()`, `_map_openai_action()`.
- `normalize_playwright_key_combo()`: Standardize key sequences.
- `_normalize_action_args_for_schema()`: Normalize LLM arg aliases to canonical keys.
- `_schema_error_for_action()`: Validate action args; trigger schema repair loop.
- `_has_nonempty_arg()`: Helper for arg presence checks.

**Screenshot + Visualization**
- `b64_png()`: Base64 encoding.
- `capture_model_screenshot_png()`: CSS-scaled screenshot capture.
- `_capture_screenshot_png_with_retry()`: Retry wrapper.
- `_draw_red_x_on_png_bytes()`: Click annotation.
- `_resize_png_bytes()`, `_overlay_grid_on_png_bytes()`.
- `save_agent_view()`, `maybe_save_agent_view()`.
- `write_final_screenshot()`, `maybe_save_final_shot()`.

**Message + Cost Control**
- `_message_has_tool_result()`, `_message_has_tool_result_image()`.
- `_strip_images_inside_tool_results()`.
- `prune_messages_for_cost()`: Keep last N turns/images.

**Page/Tab Handling**
- `pick_active_page()`: Choose best page from context.
- `maybe_switch_to_new_tab()`.

**DOM + Locator Heuristics**
- `_dom_locator_from_action_input()`.
- `_extract_dom_hint()`, `_hint_list()`.
- `_apply_site_hints()`, `_apply_dom_heuristics()`.
- `update_site_hints()`: Persist newly discovered hints.
- `infer_dom_hint_from_point()`, `infer_clickable_hint_from_point()`.
- `_build_dom_hint_from_element_info()`, `_css_attr_selector()`, `_infer_role_from_tag()`.
- `_get_dom_candidates()`, `_format_dom_candidate()`.
- `_clean_dom_text()`.

**Direct DOM Interaction**
- `_try_dom_click()`, `_try_dom_type()`.
- `_read_locator_value()`, `_type_and_verify_locator()`.
- `_read_active_element_value()`, `_active_element_is_editable()`, `_type_and_verify_active_element()`.

**Manual Click Capture**
- `_init_manual_click_capture()`, `_set_manual_click_ignore()`, `_poll_manual_clicks()`.
- Step Training (UI-driven): optional pause before committing LLM actions; waits for Continue signal or manual click.

**Action Execution**
- `execute_computer_action()`: Core dispatcher for click/type/press/screenshot/wait.
- `execute_model_function()`: Runs a stored function (steps list) against Playwright.
- `execute_model_sequence()`: Executes a sequence of functions and returns success/failure.
- `_locator_from_step()`: Step ? Playwright locator.
- `_render_template()`: Template expansion for variables.
- `_redact_step_for_log()`: Remove secrets for logging.
- `_dom_hint_to_step()`, `_action_input_from_dom_hint()`.
- `_normalize_typed_text()`, `_replace_query_in_steps()`.
- `actions_to_model_steps()`: Convert recorded actions to model steps.

**LLM Planning + Verification**
- `build_initial_messages()`: Assemble system + user + context messages.
- `pick_function_sequence()`: Decide which functions to run for a prompt.
- `select_actions_to_rewrite_with_llm()`: Identify actions to repair via LLM.
- `resummarize_steps_with_llm()`: Prune redundant executed steps before saving new actions.
- `verify_success_with_llm()`: Screenshot-based success criteria check.

**Learning + Model Update**
- `update_or_add_function()`: Insert/replace model function.
- `add_function_with_subaction_cap()`: Split long steps into capped functions.
- `_ensure_function_counts()`, `_increment_function_count()`: Track reliability.
- `_existing_function_desc()`, `_pick_unique_function_name()`.

**Core Orchestration**
- `run_agent()`: Main execution loop; handles actions, verification, repair, and model updates.
- `main()`: CLI entrypoint.

**Notable Behaviors**
- Strict `FINAL: PASS|FAIL` token policy; `_log_final()` enforces single verdict.
- Arm/commit gating for click-like actions using `ArmedClick` and confirm token logic.
- Screenshot scaling uses CSS pixels to match coordinate space.
- Cost controls via message pruning and image downscaling.
- Step Training can pause LLM actions until a UI Continue signal or a manual click is captured.

**Local Test Site**
- `test-site/`: Static auth flow pages used by CI and local runs (`index.html` login, `register.html` registration, `home.html` post-login with quiz card activity, `profile.html` profile route), including shared header navigation between Home/Profile.
- `test-site/app.js`: Local storage-backed auth logic for seeded demo account, register validation/duplicate checks, login, logout, profile persistence (`aboutMe`, `country`, conditional `state` for USA), and Home quiz runtime orchestration (20-quiz bank generation, 4-question rendering, per-question correctness, aggregate score state coloring, and Next Quiz transition behavior).

**UI Launcher**
- `vision_playwright_openai_vision_ui.py`: Tkinter entrypoint for configuring runs and launching the CLI.
- `ui/ui_state.py`: Shared UI state dataclasses for prompts, AI view, actions library, and run status.
- `ui/ui_ai_view.py`: AI screenshot list + canvas rendering panel.
- `ui/ui_actions_library.py`: Actions JSON browser/editor panel for saved model files.
- `ui/ui_prompt_tabs.py`: Prompt tab creation, persistence snapshotting, and running-state visuals.
- `ui/ui_run_control.py`: Credentials panel and run/log control widgets.
- `ui/ui_settings_tabs.py`: Browser/tokens/action/output settings tabs.
- `ui/ui_app.py`: Root window creation, styling, and layout panes.
- `ui/ui_run_lifecycle.py`: Run/stop lifecycle handlers for launching subprocesses and updating run state.
- `ui/ui_restore_state.py`: UI layout sizing and persisted state restore.
- `ui/ui_info_bar.py`: Info bar text/update wiring for the selected prompt and run status.
