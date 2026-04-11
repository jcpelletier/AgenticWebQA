# Feature Spec Header

**Feature Name:** Alternative Success Indicators
**Feature Slug:** `SuccessIndicators`
**Owner:** Joel Pelletier
**User Story:**
- **Original Request Wording:** "Currently the tests only pass via a visual llm success indicator. I'd like to add some alternative indictators. I'd like to be able to assert the present of certain text or certain selecters exist."
- **Clarified Story:** Replace the single `--success-criteria` CLI argument with four mutually exclusive success indicator types (`--visual-llm-success`, `--text-present-success`, `--selector-present-success`, `--url-match-success`). Deterministic indicators (text, selector, URL) run via Playwright on every step without an LLM call. The CLI enforces that exactly one indicator is provided. The GUI offers a dropdown to select the type. All existing scripts are migrated from `--success-criteria` to `--visual-llm-success`.

**In Scope:**
- Rename `--success-criteria` → `--visual-llm-success` (identical behavior)
- New `--text-present-success` (visible text contains / `regex:` prefix)
- New `--selector-present-success` (CSS selector exists in DOM)
- New `--url-match-success` (current URL contains / `regex:` prefix)
- CLI mutual exclusivity enforcement (exactly one required; hard error for `--success-criteria`)
- Playwright-based deterministic check loop (runs every step for non-LLM indicators)
- GUI dropdown for success type selection; switching clears the value field
- `.tmp` schema gains `success_type` per tab
- Migration of all `webtests/run_test*_local.py` scripts
- Unit tests for new CLI parsing and deterministic check helpers
- Update `release_test.py` with migrated arg

**Out Of Scope:**
- Combining multiple indicator types (AND logic)
- `--text-absent-success`, `--selector-absent-success`
- Cookie / localStorage / HTTP-response indicators
- Per-step timeout tuning for deterministic checks

**Dependencies:**
- Playwright `page.locator()`, `page.url`, `page.inner_text("body")`
- `config_shared.py` SharedArgSpec pattern (shared CLI/UI arg definitions)
- Existing `_handle_verify_guard()` and `verify_success_with_llm()` in `vision_playwright_openai_vision_poc.py`

**Rollout Risk:** Medium — touches CLI contract, all webtests scripts, GUI state, and `.tmp` schema. Existing users who pass `--success-criteria` get a hard error on first run after upgrade.

**Test Requirements:** See Testing Plan below.

---

# Summary

All AgenticWebQA tests currently determine success via one mechanism: the LLM examines a screenshot and evaluates free-form success criteria text. This requires an LLM call and is non-deterministic. This feature adds three deterministic Playwright-backed alternatives — text presence, selector existence, and URL matching — and enforces that exactly one success indicator type is chosen per test run. The old `--success-criteria` flag is hard-removed with a clear deprecation error.

---

# Goals

- Give test authors a choice of four success indicator types, each suitable for different assertion needs.
- Make deterministic checks (text, selector, URL) run without any additional LLM call.
- Enforce a clean, unambiguous CLI contract: exactly one indicator type per run.
- Preserve full backwards compatibility for the visual LLM path under the new flag name.
- Keep the GUI ergonomic: one dropdown, one value field, no confusion.

---

# Non-Goals

- Combining multiple indicator types in a single run (AND/OR logic).
- Negative assertions (`--text-absent`, `--selector-absent`).
- Cookie, localStorage, network-request, or API-response checks.
- Any changes to how the LLM generates actions or navigates pages.

---

# Assumptions

- ASSUMPTION: `regex:` is a sufficient prefix to distinguish regex from plain-string matching; no additional quoting or escaping rules are introduced.
- ASSUMPTION: Visible text check uses `page.inner_text("body")` (Playwright's DOM text extraction, strips hidden elements); this is "visible text only" per product decision.
- ASSUMPTION: Selector check uses `page.locator(selector).count() > 0`; no timeout wait is added (the check is snapshot-at-step, not a wait).
- ASSUMPTION: URL check uses `page.url` (current page URL after action completes).
- ASSUMPTION: `success_type` in the `.tmp` file defaults to `"visual_llm"` for tabs that were saved before this feature (backwards-compatible load).
- ASSUMPTION: The GUI dropdown label strings map to CLI arg names: `"Visual (LLM)"` → `visual_llm`, `"Text Present"` → `text_present`, `"Selector Present"` → `selector_present`, `"URL Match"` → `url_match`.
- ASSUMPTION: `tvjpelletier_smoketest.py` and `release_test.py` are updated as part of this feature (they hardcode `--success-criteria` equivalent values via shared helpers).

---

# Open Questions

- None remaining. All design decisions resolved in pre-planning conversation.

---

# Sub-Agent Orchestration

| Role | Status | Notes |
|---|---|---|
| PlanningOrchestrator | Complete | This document |
| QAManager | Fallback inline | Agent type unavailable; QA strategy produced inline below |
| RequirementsTraceabilityReviewer | Fallback inline | Agent type unavailable; traceability matrix produced inline below |

ASSUMPTION: QAManager and RequirementsTraceabilityReviewer subagent types were not available in this environment. Their outputs have been produced inline by the PlanningOrchestrator following the same output contract. Sub-Agent Output Verification section reflects this.

---

# Linear Checklist

## Phase 1 — Core Runtime

- [x] (REQ-1, REQ-6) Add `success_indicator` module or section in `vision_playwright_openai_vision_poc.py`: define `SuccessIndicatorType` enum (`VISUAL_LLM`, `TEXT_PRESENT`, `SELECTOR_PRESENT`, `URL_MATCH`) and `SuccessIndicatorConfig` dataclass (`type: SuccessIndicatorType`, `value: str`). — Types moved to `config_shared.py` to avoid circular import.
- [x] (REQ-2, REQ-3, REQ-4, REQ-7) Implement `check_deterministic_success(page, config: SuccessIndicatorConfig) -> bool` in `vision_playwright_openai_vision_poc.py`: dispatch to `_check_text_present()`, `_check_selector_present()`, `_check_url_match()` helpers; support `regex:` prefix in text and URL helpers.
- [x] (REQ-7, REQ-8) Modify `_run_agent_step_loop()`: after each action, if `indicator_type != VISUAL_LLM`, call `check_deterministic_success()`; on `True`, emit `FINAL: PASS` and terminate. Leave the existing `_handle_verify_guard()` path active only for `VISUAL_LLM`.
- [x] (REQ-8) Confirm `verify_success_with_llm()` and `_handle_verify_guard()` are guarded by `indicator_type == VISUAL_LLM`; no behavior change for that path.

## Phase 2 — CLI

- [x] (REQ-1, REQ-2, REQ-3, REQ-4) In `cli_entry.py`, replace `--success-criteria` with four new arguments: `--visual-llm-success`, `--text-present-success`, `--selector-present-success`, `--url-match-success`. All optional at parse time (mutual exclusivity validated in `prepare_args()`).
- [x] (REQ-5) In `prepare_args()`, validate exactly one indicator arg is provided; raise `SystemExit` with a clear message listing the four valid flags if zero or more than one are given.
- [x] (REQ-6) Before `build_parser()`, check `sys.argv` for `--success-criteria`; if found, print a hard deprecation error (`"--success-criteria is removed. Use --visual-llm-success instead."`) and call `sys.exit(1)`.
- [x] (REQ-1) Pass the resolved `SuccessIndicatorConfig` from parsed args into `run_agent()` / `run_cli_with_args()` in place of the old `success_criteria` string.

## Phase 3 — Unit Tests

- [x] (TEST-UNIT-1) Add `tests/test_success_indicators.py`: test `check_deterministic_success()` text-present path — plain string match, regex match, no-match cases.
- [x] (TEST-UNIT-2) Add to `tests/test_success_indicators.py`: selector-present path — found, not-found cases using mocked Playwright `Page`.
- [x] (TEST-UNIT-3) Add to `tests/test_success_indicators.py`: URL-match path — plain contains, regex match, no-match cases.
- [x] (TEST-UNIT-4) Add to `tests/test_cli_entry.py`: verify `--visual-llm-success` parses correctly; verify passing two indicator args raises SystemExit; verify passing zero indicator args raises SystemExit; verify `--success-criteria` raises SystemExit with deprecation message.
- [x] (TEST-UNIT-5) Update existing `test_build_parser_requires_core_arguments` in `tests/test_cli_entry.py` to use `--visual-llm-success` instead of `--success-criteria`.
- [x] (TEST-UNIT-6) Update `test_parse_cli_args_applies_prepare_logic` in `tests/test_cli_entry.py` to use `--visual-llm-success`.

## Phase 4 — Config / Shared Arg Alignment

- [x] (REQ-1) Confirm `config_shared.py` `SHARED_ARG_SPECS` does not need changes (since `--success-criteria` was defined in `cli_entry.py` directly, not in shared specs). `SuccessIndicatorType` and `SuccessIndicatorConfig` added to `config_shared.py` to avoid circular import; no shared arg spec changes required.
- [x] (REQ-10) `-SUCCESS-TYPE-` UI key is managed in `ui_prompt_tabs.py` via `_success_type_var` on each tab; no `SHARED_ARG_SPECS` entry needed.

## Phase 5 — GUI

- [x] (REQ-9) In `ui/ui_prompt_tabs.py`: replaced the success criteria `Text` widget label with a two-widget group: `ttk.Combobox` for success type (values: `Visual (LLM)`, `Text Present`, `Selector Present`, `URL Match`) + existing `Text` widget for value. Bound `<<ComboboxSelected>>` to clear the value field.
- [x] (REQ-9) Updated `get_active_prompt_fields_from_state()` and `get_prompt_state_snapshot()` to include `success_type`.
- [x] (REQ-10) In `vision_playwright_openai_vision_ui.py`, updated `_save_ui_state_snapshot()` to write `success_type` per tab; restores from saved state (defaults to `"Visual (LLM)"` if absent).
- [x] (REQ-9, REQ-10) Updated `_build_command()` in `vision_playwright_openai_vision_ui.py` to emit the correct CLI arg (`--visual-llm-success`, `--text-present-success`, etc.) based on stored `success_type`.

## Phase 6 — Script Migration

- [x] (REQ-11) Updated all 13 `webtests/run_test*_local.py` scripts plus `lifelink_calculator.py` and `run_nsa_calculator.py`: replaced `"--success-criteria"` with `"--visual-llm-success"` in cmd list construction.
- [x] (REQ-11) `release_test.py`: no direct `--success-criteria` reference found; delegates to webtests scripts (already migrated).
- [x] (REQ-11) `tvjpelletier_smoketest.py`: migrated.
- [x] (REQ-11) `precommit_smoketest.py`: no `--success-criteria` reference found; no change needed.

## Phase 7 — Validation

- [x] Run `python -m pytest` — **105 passed** (REQ-5, REQ-6, TEST-UNIT-*)
- [x] Run `python -m mypy .` — **Success: no issues found in 53 source files**
- [x] Run `python -m ruff format .` — **format passes**
- [x] Run new feature unit tests: `python -m pytest tests/test_success_indicators.py -v` — **17 passed**
- [x] Run integration smoke (login, migrated script): `python ./webtests/run_testlogin_local.py --skip-install --model claude-sonnet-4-6` — PASS (REQ-11, TEST-SMOKE-1). Also ran TEST-SMOKE-2/3/4 directly via CLI — all PASS with deterministic log confirmation.
- [x] Run `python ./precommit_smoketest.py` — **PASS** (TEST-REGRESSION-1). All checks passed in 120s.
- [x] Update `release_test.py` coverage: no changes required. `release_test.py` already runs `pytest -q tests` as its first step, which picks up `tests/test_success_indicators.py` automatically. No new standalone webtest scripts were added for this feature.

## Phase 8 — Docs

- [x] Update `docs/Structure.MD` to document `SuccessIndicatorType`, `SuccessIndicatorConfig`, and `check_deterministic_success()` under Key Data Classes and LLM Planning + Verification.
- [x] Update `CLAUDE.md` to document `success_type` field in the `.tmp` schema description and default behavior.
- [x] Update `README.md`: replace `--success-criteria` with the four new indicator flags in the CLI Flags section; update the example command to use `--visual-llm-success`; add deprecation note.
- [x] Record test execution evidence (commands run and outcomes) in the Testing Plan section below.

---

# UX Workflow

## CLI Happy Path (text present example)
```
python vision_playwright_openai_vision_poc.py \
  --prompt "Log in with username demo and password demo123" \
  --text-present-success "Welcome, demo" \
  --start-url http://127.0.0.1:8000/index.html \
  --model claude-sonnet-4-6
```
After each Playwright action, the agent checks whether "Welcome, demo" appears in the visible page text. On first step where it does, emits `FINAL: PASS` and exits.

## CLI Happy Path (selector present)
```
python vision_playwright_openai_vision_poc.py \
  --prompt "Log in" \
  --selector-present-success "[data-testid='home-welcome']" \
  --start-url http://127.0.0.1:8000/index.html \
  --model claude-sonnet-4-6
```

## CLI Happy Path (URL match)
```
python vision_playwright_openai_vision_poc.py \
  --prompt "Log in" \
  --url-match-success "/home.html" \
  --start-url http://127.0.0.1:8000/index.html \
  --model claude-sonnet-4-6
```

## CLI Happy Path (regex URL)
```
  --url-match-success "regex:.*home\\.html$"
```

## CLI Error — Two indicators
```
$ python vision_playwright_openai_vision_poc.py --visual-llm-success "..." --text-present-success "foo" ...
Error: exactly one success indicator is required. Provide one of:
  --visual-llm-success
  --text-present-success
  --selector-present-success
  --url-match-success
```

## CLI Error — Deprecated flag
```
$ python vision_playwright_openai_vision_poc.py --success-criteria "..." ...
Error: --success-criteria has been removed. Use --visual-llm-success instead.
```

## GUI Workflow
1. User opens a test tab.
2. In the success section, a **"Success Type"** dropdown shows: `Visual (LLM)` (default), `Text Present`, `Selector Present`, `URL Match`.
3. User selects a type. The **value field clears**.
4. User enters the success value (LLM criteria text, text to find, CSS selector, or URL fragment).
5. On save/run, the GUI emits the correct CLI arg.
6. The `.tmp` file persists `success_type` alongside the value.

---

# Technical Design

## New Types (vision_playwright_openai_vision_poc.py)

```python
from enum import Enum
from dataclasses import dataclass

class SuccessIndicatorType(Enum):
    VISUAL_LLM = "visual_llm"
    TEXT_PRESENT = "text_present"
    SELECTOR_PRESENT = "selector_present"
    URL_MATCH = "url_match"

@dataclass
class SuccessIndicatorConfig:
    type: SuccessIndicatorType
    value: str
```

## New Helper Functions (vision_playwright_openai_vision_poc.py)

```python
def _is_regex_value(value: str) -> tuple[bool, str]:
    """Returns (is_regex, pattern). Strips 'regex:' prefix if present."""

def _check_text_present(page: Page, value: str) -> bool:
    """True if value (or regex pattern) found in page.inner_text('body')."""

def _check_selector_present(page: Page, value: str) -> bool:
    """True if page.locator(value).count() > 0."""

def _check_url_match(page: Page, value: str) -> bool:
    """True if value (or regex pattern) found in page.url."""

def check_deterministic_success(page: Page, config: SuccessIndicatorConfig) -> bool:
    """Dispatch to the correct helper based on config.type. Returns True on match."""
```

## Modified Step Loop (vision_playwright_openai_vision_poc.py)

In `_run_agent_step_loop()`, after each action execution:
```python
if indicator_config.type != SuccessIndicatorType.VISUAL_LLM:
    if check_deterministic_success(page, indicator_config):
        _log_final("FINAL: PASS")
        return RunOutcome(verdict="PASS", ...)
```

The existing `_handle_verify_guard()` call is guarded:
```python
if indicator_config.type == SuccessIndicatorType.VISUAL_LLM:
    _handle_verify_guard(...)
```

## CLI Changes (cli_entry.py)

- Remove `--success-criteria` argument definition.
- Add four new optional args: `--visual-llm-success`, `--text-present-success`, `--selector-present-success`, `--url-match-success`.
- Add deprecation sentinel check at module top (before `build_parser()`):
  ```python
  if "--success-criteria" in sys.argv:
      print("Error: --success-criteria has been removed. Use --visual-llm-success instead.", file=sys.stderr)
      sys.exit(1)
  ```
- In `prepare_args()`, validate mutual exclusivity and construct `SuccessIndicatorConfig`.

## GUI Changes (ui/ui_prompt_tabs.py)

- Add `_success_type_var: StringVar` to tab state, default `"visual_llm"`.
- Add `ttk.Combobox` above the existing success `Text` widget; bind `<<ComboboxSelected>>` to clear the `Text` widget.
- Include `success_type` in `get_prompt_state_snapshot()` return dict.

## .tmp Schema Change (vision_playwright_openai_vision_ui.py)

Per-tab entry gains:
```json
{
  "title": "...",
  "prompt": "...",
  "success_criteria": "...",
  "success_type": "visual_llm",
  ...
}
```
Load defaults `success_type` to `"visual_llm"` when absent.

## Files Touched

| File | Change |
|---|---|
| `vision_playwright_openai_vision_poc.py` | Add enum/dataclass, deterministic helpers, modify step loop and verify guard dispatch |
| `cli_entry.py` | Replace `--success-criteria`, add four args, add deprecation sentinel, mutual exclusivity validation |
| `ui/ui_prompt_tabs.py` | Add success type dropdown, bind clear on change, include in snapshot |
| `vision_playwright_openai_vision_ui.py` | Add `success_type` to `.tmp` save/load, update `_build_command()` |
| `config_shared.py` | Add `-SUCCESS-TYPE-` UI key if success criteria UI key was previously in shared specs |
| `tests/test_cli_entry.py` | Update to use `--visual-llm-success`; add mutual exclusivity tests |
| `tests/test_success_indicators.py` | New file: unit tests for deterministic check helpers |
| `webtests/run_test*_local.py` (all 11) | Migrate `--success-criteria` → `--visual-llm-success` |
| `release_test.py` | Migrate arg |
| `tvjpelletier_smoketest.py` | Migrate arg |
| `precommit_smoketest.py` | Migrate arg if referenced |
| `docs/Structure.MD` | Document new types and functions |
| `CLAUDE.md` | Update `.tmp` schema description |

---

# Testing Plan

_Derived from inline QAManager analysis (fallback mode — see Sub-Agent Output Verification)._

## Unit Tests

| Test ID | File | Scenario | Run Command |
|---|---|---|---|
| TEST-UNIT-1 | `tests/test_success_indicators.py` | `_check_text_present()` — plain string found in body text | `python -m pytest tests/test_success_indicators.py -v` |
| TEST-UNIT-2 | `tests/test_success_indicators.py` | `_check_text_present()` — plain string not found | same |
| TEST-UNIT-3 | `tests/test_success_indicators.py` | `_check_text_present()` — `regex:` prefix, match | same |
| TEST-UNIT-4 | `tests/test_success_indicators.py` | `_check_text_present()` — `regex:` prefix, no match | same |
| TEST-UNIT-5 | `tests/test_success_indicators.py` | `_check_selector_present()` — locator count > 0 | same |
| TEST-UNIT-6 | `tests/test_success_indicators.py` | `_check_selector_present()` — locator count == 0 | same |
| TEST-UNIT-7 | `tests/test_success_indicators.py` | `_check_url_match()` — plain URL contains | same |
| TEST-UNIT-8 | `tests/test_success_indicators.py` | `_check_url_match()` — `regex:` URL match | same |
| TEST-UNIT-9 | `tests/test_success_indicators.py` | `_check_url_match()` — no match | same |
| TEST-UNIT-10 | `tests/test_cli_entry.py` | `--visual-llm-success` parses correctly, `success_type == VISUAL_LLM` | `python -m pytest tests/test_cli_entry.py -v` |
| TEST-UNIT-11 | `tests/test_cli_entry.py` | Two indicator args → `SystemExit` with clear message | same |
| TEST-UNIT-12 | `tests/test_cli_entry.py` | Zero indicator args → `SystemExit` with clear message | same |
| TEST-UNIT-13 | `tests/test_cli_entry.py` | `--success-criteria` → `SystemExit` with deprecation message | same |

## Integration / Smoke Tests

| Test ID | Scenario | Run Command | Success Criteria |
|---|---|---|---|
| TEST-SMOKE-1 | Login with `--visual-llm-success` (migrated script) | `python ./webtests/run_testlogin_local.py --skip-install --model claude-sonnet-4-6` | `VISUAL_UNIQUE: FINAL: PASS` appears in terminal output; no fallback to vision |
| TEST-SMOKE-2 | Login with `--text-present-success "Welcome, demo"` | `python vision_playwright_openai_vision_poc.py --prompt "Log in with demo/demo123" --text-present-success "Welcome, demo" --start-url http://127.0.0.1:8000/index.html --model claude-sonnet-4-6 --headless` | `VISUAL_UNIQUE: FINAL: PASS` in terminal; no LLM verify call in log |
| TEST-SMOKE-3 | Login with `--selector-present-success "[data-testid='home-welcome']"` | `python vision_playwright_openai_vision_poc.py --prompt "Log in with demo/demo123" --selector-present-success "[data-testid='home-welcome']" --start-url http://127.0.0.1:8000/index.html --model claude-sonnet-4-6 --headless` | `VISUAL_UNIQUE: FINAL: PASS` in terminal |
| TEST-SMOKE-4 | Login with `--url-match-success "home.html"` | `python vision_playwright_openai_vision_poc.py --prompt "Log in with demo/demo123" --url-match-success "home.html" --start-url http://127.0.0.1:8000/index.html --model claude-sonnet-4-6 --headless` | `VISUAL_UNIQUE: FINAL: PASS` in terminal |
| TEST-REGRESSION-1 | Full existing webtest suite | `python ./precommit_smoketest.py` | All previously passing tests continue to pass |

## Test Execution Evidence (to be filled in during implementation)

| Test ID | Command Run | Outcome | Date |
|---|---|---|---|
| TEST-UNIT-* (17 tests) | `python -m pytest tests/test_success_indicators.py tests/test_cli_entry.py -v` | PASS (32 passed) | 2026-04-10 |
| Full suite (105 tests) | `python -m pytest tests/ -q` | PASS (105 passed) | 2026-04-10 |
| mypy | `python -m mypy .` | PASS (no issues in 53 files) | 2026-04-10 |
| TEST-SMOKE-1 | `python ./webtests/run_testlogin_local.py --skip-install --model claude-sonnet-4-6` | PASS | 2026-04-11 |
| TEST-SMOKE-2 | `python vision_playwright_openai_vision_poc.py ... --text-present-success "Welcome, demo" --actions login_demo ...` | PASS (`[deterministic] text_present matched`) | 2026-04-11 |
| TEST-SMOKE-3 | `python vision_playwright_openai_vision_poc.py ... --selector-present-success "[data-testid='home-welcome']" ...` | PASS | 2026-04-11 |
| TEST-SMOKE-4 | `python vision_playwright_openai_vision_poc.py ... --url-match-success "home.html" ...` | PASS (`[deterministic] url_match matched`) | 2026-04-11 |
| TEST-REGRESSION-1 | `python ./precommit_smoketest.py` | PASS (120s — ruff, mypy, 105 unit tests, login learn/heal/reuse cycle) | 2026-04-11 |

---

# Acceptance Criteria

| AC | Requirement(s) | Test(s) | Criterion |
|---|---|---|---|
| AC-1 | REQ-1, REQ-8 | TEST-UNIT-10, TEST-SMOKE-1 | `--visual-llm-success "..."` produces identical run behavior to old `--success-criteria "..."` |
| AC-2 | REQ-2 | TEST-UNIT-1, TEST-SMOKE-2 | `--text-present-success "Welcome, demo"` passes when that string is in visible page text |
| AC-3 | REQ-2 | TEST-UNIT-3 | `--text-present-success "regex:^Welcome.*demo$"` passes when visible text matches the pattern |
| AC-4 | REQ-3 | TEST-UNIT-5, TEST-SMOKE-3 | `--selector-present-success ".selector"` passes when the selector resolves to ≥1 element |
| AC-5 | REQ-4 | TEST-UNIT-7, TEST-SMOKE-4 | `--url-match-success "/home.html"` passes when current URL contains that string |
| AC-6 | REQ-4 | TEST-UNIT-8 | `--url-match-success "regex:.*home\\.html$"` passes when URL matches the pattern |
| AC-7 | REQ-5 | TEST-UNIT-11 | Passing two indicator args exits with a message naming all four valid flags |
| AC-8 | REQ-5 | TEST-UNIT-12 | Passing zero indicator args exits with same guidance message |
| AC-9 | REQ-6 | TEST-UNIT-13 | Passing `--success-criteria` exits with deprecation error naming `--visual-llm-success` |
| AC-10 | REQ-7 | TEST-SMOKE-2, TEST-SMOKE-3, TEST-SMOKE-4 | Deterministic checks resolve without any LLM verify call in the log |
| AC-11 | REQ-9 | Manual GUI verification | GUI dropdown shows four options; switching type clears value field |
| AC-12 | REQ-10 | Manual GUI verification | Saving and reloading the `.tmp` file restores `success_type` per tab |
| AC-13 | REQ-11 | TEST-REGRESSION-1 | All `webtests/run_test*_local.py` scripts run without argument errors after migration |

---

# Sub-Agent Output Verification

## QAManager (Inline Fallback)

| Field | Status | Notes |
|---|---|---|
| Scope Reviewed | PRESENT | CLI, runtime, GUI, `.tmp` schema, script migration, unit tests |
| Findings (ordered by severity) | PRESENT | High: all 11 webtests scripts + release_test + smoketest must be migrated atomically or existing CI breaks. Medium: deterministic check runs every step — regex compilation should be cached to avoid per-step overhead. Low: GUI dropdown state not validated against CLI arg in build_command(). |
| Requirement Traceability | PRESENT | See matrix below |
| Commands Run | PRESENT | Documented in Testing Plan |
| Artifacts | PRESENT | `tests/test_success_indicators.py` (new), updated `tests/test_cli_entry.py` |
| Risks/Unknowns | PRESENT | See Risks below |
| Recommended Verdict | PASS WITH RISKS | Feature is well-scoped; migration risk is manageable with atomic script updates |

**Requirement Traceability Matrix:**

| REQ | Description | Test(s) |
|---|---|---|
| REQ-1 | `--visual-llm-success` CLI arg | TEST-UNIT-10, TEST-SMOKE-1 |
| REQ-2 | `--text-present-success` with contains/regex | TEST-UNIT-1..4, TEST-SMOKE-2 |
| REQ-3 | `--selector-present-success` | TEST-UNIT-5..6, TEST-SMOKE-3 |
| REQ-4 | `--url-match-success` with contains/regex | TEST-UNIT-7..9, TEST-SMOKE-4 |
| REQ-5 | Mutual exclusivity enforcement | TEST-UNIT-11, TEST-UNIT-12 |
| REQ-6 | `--success-criteria` hard deprecation | TEST-UNIT-13 |
| REQ-7 | Deterministic checks run every step | TEST-SMOKE-2..4 (log inspection) |
| REQ-8 | Visual LLM path unchanged | TEST-UNIT-10, TEST-SMOKE-1 |
| REQ-9 | GUI dropdown + clear on switch | NOT TESTED (manual AC-11 only) |
| REQ-10 | `.tmp` schema `success_type` field | NOT TESTED (manual AC-12 only) |
| REQ-11 | Script migration | TEST-REGRESSION-1 |
| REQ-12 | `config_shared.py`/`cli_entry.py`/poc updated | TEST-UNIT-10, precommit (mypy/ruff) |

**Risks:**
1. Script migration is all-or-nothing: any missed `--success-criteria` reference breaks CI immediately after the flag is removed. Mitigation: grep all files before shipping.
2. Regex compilation per step is wasteful if indicator runs on every step. Mitigation: compile regex once at startup, store in `SuccessIndicatorConfig`.
3. REQ-9 and REQ-10 have no automated coverage — GUI is Tkinter and hard to automate. Mitigation: manual checklist items, accepted as-is per project conventions.

## RequirementsTraceabilityReviewer (Inline Fallback)

| Field | Status | Notes |
|---|---|---|
| Scope Reviewed | PRESENT | All 12 REQs, all 13 ACs, all test IDs |
| Findings (ordered by severity) | PRESENT | See below |
| Requirement Traceability | PRESENT | Matrix above |
| Commands Run | PRESENT | See Testing Plan |
| Artifacts | PRESENT | This TDD |
| Risks/Unknowns | PRESENT | See below |
| Recommended Verdict | PASS WITH RISKS | Two NOT TESTED gaps (GUI/tmp) are accepted per project GUI testing conventions |

**Traceability Findings:**
- HIGH: REQ-9 (GUI dropdown) and REQ-10 (`.tmp` schema) are NOT TESTED by automated tests. This is a known gap; Tkinter GUI is not covered by the automated suite in this project. Manual verification via AC-11 and AC-12 is the accepted approach.
- MEDIUM: REQ-7 (deterministic check runs every step, not LLM-gated) is verified by log inspection in smoke tests, not a formal assertion. A unit test mocking the step loop would give stronger coverage — listed as a future enhancement.
- LOW: `test_shared_arg_cli_flags.py` implicitly validates the CLI flag set matches `SHARED_ARG_SPECS`. If `--success-criteria` was not in shared specs (confirmed: it was in `cli_entry.py` directly), this test does not cover its removal. Implementer must verify no residual spec reference exists.
