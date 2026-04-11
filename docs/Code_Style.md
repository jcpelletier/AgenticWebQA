# AgenticWebQA Repository Code Style Guide

## Table of Contents
- [1. Scope and Principles](#1-scope-and-principles)
- [2. Indentation and Whitespace](#2-indentation-and-whitespace)
- [3. Line Endings and Editor Expectations](#3-line-endings-and-editor-expectations)
- [4. Naming Conventions](#4-naming-conventions)
- [5. Complexity and Readability](#5-complexity-and-readability)
- [6. Imports Organization](#6-imports-organization)
- [7. Error Handling and Reliability](#7-error-handling-and-reliability)
- [8. Logging and Observability](#8-logging-and-observability)
- [9. Type Hints and Contracts](#9-type-hints-and-contracts)
- [10. Project Structure and Boundaries](#10-project-structure-and-boundaries)
- [11. Tests and Maintainability](#11-tests-and-maintainability)
- [12. Security and Secrets](#12-security-and-secrets)
- [13. PR and Change Expectations](#13-pr-and-change-expectations)
- [14. Tooling (Enforced by Tooling)](#14-tooling-enforced-by-tooling)
- [15. Recommended Repo Additions](#15-recommended-repo-additions)

## 1. Scope and Principles
This guide defines repo-specific standards for humans and coding agents.

Rules in this document use:
- MUST: required for new or changed code.
- SHOULD: expected unless there is a justified reason.
- MAY: optional.

Observed in this repo:
- `AGENTS.md`: requires small, reviewable changes and atomic prompt/action flows.
- `AGENTS.md`: requires exactly one `FINAL: PASS` or `FINAL: FAIL` per run.
- `README.md`: declares `ruff format` as source of truth for formatting.
- `pyproject.toml`: centralizes Ruff and mypy tool configuration.

## 2. Indentation and Whitespace
- Python code MUST use 4 spaces per indentation level.
- Tabs MUST NOT be used for indentation.
- Continuation lines SHOULD be wrapped in a way `ruff format` keeps stable.
- Trailing whitespace SHOULD be avoided.

Observed in this repo:
- `cli_entry.py`: 4-space indentation and wrapped argument blocks.
- `config_shared.py`: consistent 4-space indentation in dataclass/spec definitions.
- `ui/ui_settings_tabs.py`: multi-line UI builder calls follow 4-space indentation.
- `vision_playwright_openai_vision_poc.py`: deep but space-indented blocks throughout.

## 3. Line Endings and Editor Expectations
- Source files SHOULD be committed with LF line endings to keep diffs stable across OSes.
- Developers on Windows MAY keep CRLF in working tree, but repository normalization SHOULD remain LF.
- Editors SHOULD save UTF-8; Markdown MUST be UTF-8 (no BOM).

Observed in this repo:
- `git ls-files --eol` output: index uses `i/lf` for tracked files.
- `git ls-files --eol` output: working tree varies (`w/crlf`, `w/lf`, `w/mixed`).
- `AGENTS.md`: explicitly requires UTF-8 (no BOM) for Markdown.
- `.editorconfig`: defines LF endings and indentation defaults by file type.

Inconsistency noticed:
- `README.md`: reported as `w/mixed` in working tree.
- `precommit_smoketest.py`: `w/lf`, while many `.py` files are `w/crlf`.

Chosen standard: Commit LF-normalized text files; allow platform-local working-tree endings.
Rationale: This matches current Git normalization while reducing noisy cross-platform diffs.

## 4. Naming Conventions
- Files/modules MUST use `snake_case.py`.
- Classes MUST use `PascalCase`.
- Functions/variables MUST use `snake_case`.
- Constants MUST use `UPPER_SNAKE_CASE`.
- Boolean names SHOULD start with `is_`, `has_`, or `can_` where practical.
- Collections SHOULD use plural nouns (`items`, `messages`, `functions_list`).
- Abbreviations SHOULD be minimized and kept readable (`url`, `api`, `ui` are acceptable; avoid cryptic short forms).

Observed in this repo:
- `ui/ui_run_lifecycle.py`: classes `RunLifecycle`, `LaunchCommand`; functions in `snake_case`.
- `ui/ui_state.py`: dataclasses in `PascalCase`, fields in `snake_case`.
- `config_shared.py`: constants like `DEFAULT_MODEL`, `DEFAULT_MAX_STEPS`.
- `vision_playwright_openai_vision_poc.py`: boolean variables like `has_login`, `has_search`; plural collections like `actions`, `messages`.
- `tests/test_cli_entry.py`: test names use `test_<behavior>` style.

Inconsistency noticed:
- `config_shared.py`: CLI flag `--Azure-Logging` uses mixed-case and hyphenated capitalization.
- `ui/ui_prompt_tabs.py`: `RUNNING_TAB_PREFIX` contains a mojibake-looking marker string.

Chosen standard: New flags and identifiers MUST be lowercase, predictable, and ASCII-safe unless external compatibility requires otherwise.
Rationale: Predictable naming is easier for both agents and humans to generate and maintain.

## 5. Complexity and Readability
Definition of depth:
- "Depth" means count of nested control blocks (`if/for/while/try/with`) inside a function.

Rules:
- Functions SHOULD target depth <= 3 for new code.
- Functions SHOULD use guard clauses and early returns to flatten branching.
- Functions SHOULD stay focused (rough guidance: <= 60 lines for new functions, excluding docstring/comments).
- Refactor trigger: when a function handles multiple responsibilities (I/O, parsing, business decisions, logging), extract helpers.
- Large legacy functions MAY remain, but touched areas SHOULD be incrementally decomposed.

Observed in this repo:
- `vision_playwright_openai_vision_poc.py`: many helper extractions exist, but also very large orchestration paths.
- `ui/ui_run_lifecycle.py`: `run_script` uses guard clauses for missing process/API key/script path.
- `config_shared.py`: validation logic split into `_validate_numeric_bounds`, `_coerce_cli_numeric`, `parse_ui_value`.

Inconsistency noticed:
- `vision_playwright_openai_vision_poc.py`: monolithic runtime logic spans many responsibilities.
- `ui/*` modules: comparatively small, focused helpers.

Chosen standard: All new code MUST follow small-function, helper-extraction style used in `ui/*` and `config_shared.py`; monolithic additions are not allowed.
Rationale: Focused functions reduce breakage risk in automation-heavy code.

## 6. Imports Organization
- Imports MUST be grouped in this order: standard library, third-party, local modules.
- Each group MUST be separated by one blank line.
- `from __future__ import annotations` SHOULD be first when used.
- Wildcard imports MUST NOT be used.

Observed in this repo:
- `cli_entry.py`: stdlib imports, then local `config_shared` import.
- `ui/ui_run_lifecycle.py`: stdlib, Tkinter, then local `.ui_state` import.
- `vision_playwright_openai_vision_ui.py`: stdlib, third-party (`ttkbootstrap`), then local modules.
- `vision_playwright_openai_vision_poc.py`: stdlib, third-party (`openai`, `playwright`), then local modules.

Inconsistency noticed:
- `tests/test_cli_smoke.py`: local imports appear before a direct import of another local module alias; grouping remains readable but not strictly segmented.
- `run_testlogin_local.py`: stdlib-only file with no group separation needed.

Chosen standard: Keep strict three-group ordering whenever more than one category exists.
Rationale: Consistent import layout improves automated edits and conflict resolution.

## 7. Error Handling and Reliability
- Code MUST raise exceptions for invalid state/inputs at module boundaries.
- Code SHOULD return structured results for expected runtime outcomes where practical.
- Exceptions MUST NOT be silently swallowed unless there is a clear best-effort reason.
- When catching broad exceptions, code SHOULD add context (message/log/exception chaining).
- I/O and browser/network operations MUST define timeouts.
- Retries MAY be used for transient failures; retry loops SHOULD log attempt context.

Observed in this repo:
- `config_shared.py`: parsing errors are converted to clear `ArgumentTypeError`/`ValueError` messages.
- `run_testlogin_local.py`: network readiness uses `urlopen(..., timeout=3)` with deadline loop and explicit failure.
- `vision_playwright_openai_vision_poc.py`: screenshot capture has retry helper `_capture_screenshot_png_with_retry`.
- `vision_playwright_openai_vision_poc.py`: many browser actions set explicit Playwright timeouts (for example `timeout=10000`).

Inconsistency noticed:
- `vision_playwright_openai_vision_poc.py`: some `except Exception:` branches intentionally ignore errors in best-effort flows.
- `ui/ui_run_lifecycle.py`: some cleanup paths use broad `except Exception: pass`.

Chosen standard: Broad catches are allowed only in cleanup/best-effort paths and SHOULD include a debug log when failure could affect behavior.
Rationale: Preserve resilience without hiding actionable failures.

## 8. Logging and Observability
- Runtime logs MUST preserve the single final verdict token rule (`FINAL: PASS` or `FINAL: FAIL` exactly once).
- Log levels SHOULD follow: `INFO` for normal run events, `WARNING` for degraded behavior, `ERROR` for failures.
- Logs SHOULD remain plain text unless a structured sink requires otherwise.
- Sensitive values (passwords, secrets, tokens) MUST be redacted or excluded.
- Correlation fields MAY be added later if multi-run aggregation needs grow.

Observed in this repo:
- `vision_playwright_openai_vision_poc.py`: central logger `LOGGER` with `_log_info/_log_warn/_log_error` helpers.
- `vision_playwright_openai_vision_poc.py`: `_squelch_final_tokens` and `_log_final` enforce final token policy.
- `tests/test_final_token_policy.py`: verifies final token emits once and noisy occurrences are removed.
- `AGENTS.md`: mandates exactly one final token per run.

## 9. Type Hints and Contracts
- Public module boundaries MUST be type-annotated (function args and returns).
- Internal helpers SHOULD be type-annotated unless truly dynamic.
- `Any` SHOULD be minimized; when used, keep it near external payload boundaries (API responses, untyped JSON).
- `Optional[T]` and `T | None` are both present; new code SHOULD prefer `T | None` (Python 3.12 target).
- Dataclasses SHOULD be used for simple state containers.
- TypedDict/Pydantic: Not enough evidence found in repo.
- If structured dict payloads expand, `TypedDict` SHOULD be introduced at key boundaries.

Observed in this repo:
- `ui/ui_state.py`: dataclasses define UI state contracts.
- `config_shared.py`: typed `SharedArgSpec` dataclass and typed helper APIs.
- `vision_playwright_openai_vision_poc.py`: heavy use of typed signatures, but also many `Any` payloads around model/tool data.
- `pyproject.toml`: Python 3.12 target and mypy settings are centralized under `[tool.mypy]`.

Inconsistency noticed:
- `cli_entry.py` and `config_shared.py`: use `Optional[...]` style.
- `ui/ui_state.py` and many UI modules: use `| None` unions.

Chosen standard: New code SHOULD use `| None`; existing `Optional[...]` MAY remain until touched.
Rationale: Union syntax is the modern standard in the configured Python version.

## 10. Project Structure and Boundaries
- UI composition MUST stay in `ui/*.py` modules.
- Shared argument/config logic MUST stay in `config_shared.py` and be reused by CLI and UI.
- CLI parsing/composition MUST stay in `cli_entry.py`.
- Core agent/runtime behavior MUST stay in `vision_playwright_openai_vision_poc.py` (or extracted runtime modules if refactored).
- Tests MUST live under `tests/` and target behavior through public functions where possible.
- Cross-layer imports SHOULD point inward: entrypoints -> shared config/runtime helpers, not the reverse.

Observed in this repo:
- `vision_playwright_openai_vision_ui.py`: orchestrates UI modules rather than embedding all logic inline.
- `cli_entry.py`: parser builder and normalization logic are isolated.
- `config_shared.py`: single source for shared CLI/UI argument specs.
- `tests/test_shared_arg_ui_keys.py`: validates alignment between UI constants and shared specs.

Inconsistency noticed:
- `vision_playwright_openai_vision_poc.py`: very broad scope (logging, OpenAI interaction, Playwright actions, model persistence) in one file.
- `ui/*` modules: already split by concern.

Chosen standard: Any new substantial runtime feature SHOULD be added via extracted helper modules rather than enlarging the monolith.
Rationale: Preserves maintainability as agent behavior grows.

## 11. Tests and Maintainability
- Test files MUST be named `tests/test_<feature>.py`.
- Test names MUST describe behavior (`test_<unit>_<expected_behavior>`).
- Behavior changes MUST include test updates in the same PR.
- Mocks SHOULD be applied at external boundaries (OpenAI client, Playwright, subprocess), not internal pure logic.
- Over-mocking SHOULD be avoided for pure helpers; use direct input/output assertions.

Observed in this repo:
- `tests/test_cli_smoke.py`: mocks Playwright/OpenAI boundaries via `monkeypatch`.
- `tests/test_ui_launch_smoke.py`: patches `subprocess.Popen` at launch boundary.
- `tests/test_shared_arg_validation.py`: direct validation tests for parser and value coercion.
- `tests/test_message_pruning.py`: pure function behavior checks with plain dict fixtures.

## 12. Security and Secrets
- Secrets MUST come from environment variables; do not hardcode credentials or API keys.
- Logs MUST NOT expose secrets; redact when values may appear in model/tool output.
- Test/demo credentials MAY be used only for local deterministic test fixtures and never for real systems.

Observed in this repo:
- `vision_playwright_openai_vision_poc.py`: requires `OPENAI_API_KEY` and exits if missing.
- `ui/ui_run_lifecycle.py`: injects `OPENAI_API_KEY`, `AGENTICWEBQA_USERNAME`, and `AGENTICWEBQA_PASSWORD` into subprocess env.
- `vision_playwright_openai_vision_poc.py`: `_redact_secret_text` is used to avoid leaking password-like values.
- `run_testlogin_local.py`: uses fixed demo credentials for local test-site flow.

## 13. PR and Change Expectations
- Changes MUST be small and reviewable.
- Prompt/action updates SHOULD remain atomic and reusable.
- Documentation SHOULD be updated when behavior or workflow changes.
- Formatting and tests MUST pass before merge.

Observed in this repo:
- `AGENTS.md`: explicitly requires small, reviewable changes and atomic actions.
- `AGENTS.md`: routes local quality checks through `precommit_smoketest.py`.
- `README.md`: documents formatting and local verification workflows.

Local commands (repo-root, current tooling):
- `python -m ruff format .`
- `python -m pytest`
- `python -m mypy .`
- `python ./precommit_smoketest.py`

## 14. Tooling (Enforced by Tooling)
Keep this short: tooling enforces format/basic static checks; this guide defines higher-level style and maintainability rules.

Observed in this repo:
- `requirements.txt`: includes `ruff`, `pytest`, `mypy`.
- `pyproject.toml`: contains active Ruff and mypy settings (`[tool.ruff]`, `[tool.ruff.format]`, `[tool.mypy]`).
- `.editorconfig`: defines editor-level defaults for line endings, charset, and indentation.
- `precommit_smoketest.py`: runs `ruff format`, `mypy`, `pytest`, and the integration smoke script.
- `README.md`: names `ruff format` as formatting source of truth.

Not enough evidence found in repo.
- No `setup.cfg` was found in this checkout.
Chosen standard: `pyproject.toml` is the config source of truth, with operational workflow details in `README.md`, `AGENTS.md`, `precommit_smoketest.py`, and `.github/workflows/agenticwebqa-testlogin.yml`.
Rationale: This matches current executable project behavior.

## 15. Recommended Repo Additions
- Keep CI expectations aligned with `.github/workflows/agenticwebqa-testlogin.yml`.
- If AgenticWebQA-specific CI diverges from the monorepo workflow, document the reason in `README.md` and `AGENTS.md`.

Observed in this repo:
- `.github/workflows/agenticwebqa-testlogin.yml` exists in this repo and governs workflow execution.
