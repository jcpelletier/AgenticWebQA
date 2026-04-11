# Gemini Provider Support (TDD)

## Feature Spec Header

- **Feature Name:** Gemini Provider Support
- **Feature Slug:** GeminiProviderSupport
- **Owner:** TBD
- **User Story:**
  - **Original Request Wording:** "Lets use Planning.md to add support for Gemini. I would the following. 1 Add api key UX support similar to anthropic and openai in the gui and cli 2. make sure responses from Gemini will respect our formats 3. make sure we support sending to the gemini api and respect their syntax."
  - **Clarified Story:** As a developer, I want Gemini API support in the existing CLI/UI workflow so I can select Gemini models in the GUI model dropdown, supply a `GEMINI_API_KEY`, and execute the same end-to-end agent flow — with Gemini API calls using the OpenAI-compatible endpoint — without breaking existing OpenAI or Anthropic behavior.
- **In Scope:**
  - Add `GEMINI_MODEL_OPTIONS` constant to `config_shared.py` and merge into `MODEL_OPTIONS`.
  - Update `infer_model_provider()` to detect `gemini-*` model names and return `"gemini"`.
  - Update `model_api_env_var()` to return `"GEMINI_API_KEY"` for Gemini models.
  - Add Gemini API Key field (masked, OK/MISSING status) to GUI credentials panel in `ui/ui_run_control.py`.
  - Add `gemini_key_var: tk.StringVar` field to `AppState` in `ui/ui_state.py`.
  - Update `build_run_lifecycle()` in `ui/ui_run_lifecycle.py` to validate and inject `GEMINI_API_KEY` for Gemini models.
  - Add `"gemini"` provider branch to `_new_model_client()` in `vision_playwright_openai_vision_poc.py` using the OpenAI client pointed at the Gemini OpenAI-compatible base URL.
  - Ensure response parsing/adapting routes `"gemini"` provider the same as `"openai"` (OpenAI-compatible response shape).
  - Unit tests for provider routing, env-var mapping, model list, and client adapter.
  - Integration smoke test for a Gemini-powered run against the local test site.
- **Out Of Scope:**
  - Native Gemini SDK (`google-genai` / `google-generativeai`); use the OpenAI-compatible endpoint only.
  - Streaming responses.
  - Gemini-specific multimodal tool schemas beyond what the OpenAI-compatible endpoint supports.
  - Replacing OpenAI or Anthropic as default/existing providers.
  - Adding `run_testgemini_local.py` to `precommit_smoketest.py` unless explicitly requested by a developer.
- **Dependencies:**
  - `config_shared.py`: shared model constants, provider routing.
  - `vision_playwright_openai_vision_poc.py`: `_new_model_client()`, `_ModelClientAdapter`, response parsing.
  - `ui/ui_run_control.py`, `ui/ui_state.py`, `ui/ui_run_lifecycle.py`: credentials UX and lifecycle.
  - `vision_playwright_openai_vision_ui.py`: `AppState` instantiation (must wire `gemini_key_var`).
  - Existing `openai` Python SDK (already in `requirements.txt`) — reused for Gemini via base URL override.
- **Rollout Risk:** Medium. Changing `infer_model_provider()` return type and `model_api_env_var()` dispatch is a cross-cutting modification with mypy type implications. UI credentials changes affect all callers that unpack the return of `build_credentials_tab()`.
- **Test Requirements:**
  - Unit tests: provider detection, env-var routing, model list, client factory, AppState field, lifecycle key validation.
  - Integration/smoke test: Gemini-powered e2e run against the local test site.
  - Requirement-to-test traceability matrix mapping every `REQ-*` to `TEST-*`.

---

## Summary

Add Gemini as a third LLM provider by wiring `GEMINI_API_KEY` into the GUI credentials panel and CLI env-var path, extending provider detection in shared config, and routing `gemini-*` model calls through the OpenAI-compatible Gemini endpoint. The design reuses the existing `openai` SDK with a Gemini-specific base URL so no new SDK dependency is required. The same learn/reuse/auto-heal/success-verification/final-token-policy workflow must function with a Gemini model selected.

---

## Goals

- Support Gemini model execution through the existing agent runtime flow without breaking OpenAI or Anthropic behavior.
- Expose Gemini model options in the GUI Model dropdown and CLI model argument.
- Provide a Gemini API Key credential field in the GUI credentials panel (consistent with existing OpenAI/Anthropic key fields).
- Keep `GEMINI_API_KEY` environment-variable only; do not persist in UI session state.
- Add measurable test coverage for provider routing, client creation, and end-to-end execution.

---

## Non-Goals

- Building a generalized multi-provider plugin abstraction beyond the three providers.
- Migrating existing saved actions/model files to provider-specific formats.
- Changing final-token policy semantics or step-learning semantics.
- Expanding test-site product behavior for this feature.

---

## Assumptions

- ASSUMPTION: All Gemini model names start with the prefix `gemini-`; prefix-based detection is sufficient.
- ASSUMPTION: The Gemini OpenAI-compatible endpoint (`https://generativelanguage.googleapis.com/v1beta/openai/`) returns standard OpenAI response shapes that are parseable by the existing `extract_openai_response_text()` / `extract_openai_output_types()` path.
- ASSUMPTION: Gemini `usage` field names match OpenAI conventions closely enough for `_get_usage_value()` / `print_usage_tokens()` to work without modification; a smoke run will validate this.
- ASSUMPTION: The Gemini OpenAI-compatible endpoint is accessed using `api_key` as the bearer token (no OAuth or service-account credentials needed beyond the API key).
- ASSUMPTION: `GEMINI_BASE_URL` constant is added to `config_shared.py` as a named constant so the URL is not hardcoded inline.
- ASSUMPTION: Default policy applies: do not add `run_testgemini_local.py` to `precommit_smoketest.py` unless explicitly requested by a developer.
- ASSUMPTION: The `build_credentials_tab()` return signature will be extended to include `gemini_key_var`; all callers in `vision_playwright_openai_vision_ui.py` must be updated.

---

## Open Questions

- Which Gemini models should be in the initial `GEMINI_MODEL_OPTIONS` list? (Suggested: `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-1.5-pro`, `gemini-1.5-flash`.)
- Should the existing `model_options` in the UI prompt tab dropdown be updated automatically from `MODEL_OPTIONS`, or is there a separate hardcoded list to update?
- If the Gemini OpenAI-compatible endpoint `usage` field differs from OpenAI, is a minor normalization shim acceptable within `_get_usage_value()`, or should it emit a warning and continue?
- Should `run_testgemini_local.py` skip gracefully with `SKIP: GEMINI_API_KEY_NOT_SET` when the key is absent, or hard-fail?

---

## Sub-Agent Orchestration

| Role | Guide | Output Captured |
|---|---|---|
| `PlanningOrchestrator` | `.claude/commands/planning.md` | This TDD |
| `QAManager` | `.claude/commands/qa-manager.md` | See Sub-Agent Output Verification section |
| `RequirementsTraceabilityReviewer` | `.claude/commands/qa-traceability.md` | See Sub-Agent Output Verification section |

`QAManager` routed to `QA_WebAutomation` (smoke script scope) and `QA_API` (model client routing scope).

---

## Linear Checklist

- [ ] Define Gemini provider requirements and IDs (`REQ-1` through `REQ-9`). *(REQ-1–REQ-9)*
- [ ] Add `GEMINI_MODEL_OPTIONS` list and `GEMINI_BASE_URL` constant to `config_shared.py`; merge into `MODEL_OPTIONS`. *(REQ-3)*
- [ ] Update `infer_model_provider()` return type to `Literal["openai", "anthropic", "gemini"]` and add `gemini-` prefix detection. *(REQ-1)*
- [ ] Update `model_api_env_var()` to return `"GEMINI_API_KEY"` for the `"gemini"` provider. *(REQ-2)*
- [ ] Run `python -m mypy .` and fix any type errors introduced by the `Literal` change.
- [ ] Add `gemini_key_var: tk.StringVar` field to `AppState` in `ui/ui_state.py`. *(REQ-5)*
- [ ] Add Gemini API Key entry row (masked, OK/MISSING status label, event bindings) to `build_credentials_tab()` in `ui/ui_run_control.py`; update help text and return signature. *(REQ-4)*
- [ ] Update all callers of `build_credentials_tab()` in `vision_playwright_openai_vision_ui.py` to accept the extended return value and wire `gemini_key_var` into `AppState`. *(REQ-4, REQ-5)*
- [ ] Update `build_run_lifecycle()` in `ui/ui_run_lifecycle.py` to read `gemini_key_var`, validate it when a Gemini model is selected, and inject `GEMINI_API_KEY` into the subprocess env. *(REQ-6)*
- [ ] Add `"gemini"` provider branch to `_new_model_client()` in `vision_playwright_openai_vision_poc.py` using `OpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)` and returning `_ModelClientAdapter("gemini", client)`. *(REQ-7)*
- [ ] Ensure `_ResponsesAdapter.create()` routes `"gemini"` provider through the OpenAI-compatible call path. *(REQ-8)*
- [ ] Verify `extract_openai_response_text()`, `extract_openai_output_types()`, and `_get_usage_value()` handle Gemini responses without errors. *(REQ-8)*
- [ ] Add unit tests to `tests/test_gemini_provider.py` covering `TEST-UNIT-GEMINI-001` through `TEST-UNIT-GEMINI-004`. *(REQ-1–REQ-7)*
- [ ] Invoke `QAManager` subagent with canonical request packet and capture returned test strategy, commands, and risks. *(done — see Sub-Agent Output Verification)*
- [ ] Invoke `RequirementsTraceabilityReviewer` subagent and capture REQ/TEST/AC mapping audit output. *(done — see Sub-Agent Output Verification)*
- [ ] Run `python -m pytest -q tests/` and confirm no regressions in the existing 105-test baseline.
- [ ] Run feature unit tests: `python -m pytest -q tests/test_gemini_provider.py` and record exit code and pass evidence in Testing Plan.
- [ ] Add `webtests/run_testgemini_local.py` smoke script following the `run_testlogin_local.py` pattern; add `SKIP: GEMINI_API_KEY_NOT_SET` graceful exit when key is absent. *(TEST-SMOKE-GEMINI-001)*
- [ ] Run `python ./precommit_smoketest.py` and record exit code and pass evidence in Testing Plan.
- [ ] Run feature smoke test: `python ./webtests/run_testgemini_local.py --skip-install --model gemini-2.0-flash` and record exit code, `FINAL:` token, and artifact path in Testing Plan.
- [ ] Update `release_test.py` to include `TEST-UNIT-GEMINI-001` through `TEST-UNIT-GEMINI-004` unit coverage and `TEST-SMOKE-GEMINI-001` smoke entry.
- [ ] Update `README.md` with `GEMINI_API_KEY` setup instructions and CLI usage example for Gemini models.
- [ ] Update `docs/Structure.MD` Provider Routing section to reference the `"gemini"` provider case.
- [ ] Confirm all acceptance criteria `AC-1` through `AC-6` are satisfied and each maps to `REQ-*` and `TEST-*` IDs.

---

## UX Workflow

**Happy Path — GUI:**
1. Developer opens the UI launcher and navigates to the **Credentials** tab.
2. A new **Gemini API Key** row is visible (masked entry, OK/MISSING status) alongside the existing OpenAI and Anthropic key rows.
3. Developer pastes the `GEMINI_API_KEY` value; the status label changes to **OK**.
4. Developer selects a `gemini-*` model from the Model dropdown on any prompt tab.
5. Developer clicks **Run**; the run lifecycle validates that a Gemini key is present, injects `GEMINI_API_KEY` into the subprocess env, and launches the agent.
6. Agent executes the prompt using the Gemini API via the OpenAI-compatible endpoint and emits `FINAL: PASS` or `FINAL: FAIL`.

**Failure — Missing Gemini Key:**
- If a `gemini-*` model is selected and the Gemini key field is empty, the run lifecycle shows an error dialog: `"GEMINI_API_KEY is missing for selected model '<model>'."` — identical behavior to the existing OpenAI/Anthropic missing-key guard.

**Happy Path — CLI:**
1. Developer sets `GEMINI_API_KEY=<key>` in the environment.
2. Developer runs: `python vision_playwright_openai_vision_poc.py --model gemini-2.0-flash --start-url <url> --prompt "..." --success "..."`
3. The runtime detects provider `"gemini"`, reads `GEMINI_API_KEY`, creates the OpenAI-compatible client, and executes the agent flow as normal.

---

## Technical Design

### Requirement IDs

- **REQ-1:** `infer_model_provider()` in `config_shared.py` detects `gemini-*` model names and returns `"gemini"`.
- **REQ-2:** `model_api_env_var()` in `config_shared.py` returns `"GEMINI_API_KEY"` for the `"gemini"` provider.
- **REQ-3:** `GEMINI_MODEL_OPTIONS` list and `GEMINI_BASE_URL` constant are added to `config_shared.py` and `GEMINI_MODEL_OPTIONS` is merged into `MODEL_OPTIONS`.
- **REQ-4:** GUI credentials panel (`ui/ui_run_control.py`) adds a Gemini API Key field (masked entry, OK/MISSING status label, auto-apply event bindings on KeyRelease/Paste/FocusOut) and updates help text to reference `GEMINI_API_KEY`.
- **REQ-5:** `AppState` in `ui/ui_state.py` gains a `gemini_key_var: tk.StringVar` field; all `AppState` instantiation sites are updated.
- **REQ-6:** `build_run_lifecycle()` in `ui/ui_run_lifecycle.py` reads `gemini_key_var`, validates the Gemini key when a Gemini model is selected (same missing-key error dialog pattern), and injects `GEMINI_API_KEY` into the subprocess env.
- **REQ-7:** `_new_model_client()` in `vision_playwright_openai_vision_poc.py` supports a `"gemini"` provider branch — creates an OpenAI client with `base_url=GEMINI_BASE_URL` (imported from `config_shared`) and returns `_ModelClientAdapter("gemini", client)`.
- **REQ-8:** Response parsing routes `"gemini"` provider through the existing OpenAI-compatible call and parse path; `_ResponsesAdapter.create()` handles `"gemini"` the same as `"openai"`.
- **REQ-9:** CLI reads `GEMINI_API_KEY` from the environment for Gemini models. (This is automatic once REQ-1 and REQ-2 are implemented — `model_api_env_var()` returns `"GEMINI_API_KEY"` and the existing env-read pattern at `run_agent()` entry works unchanged.)

### Key File Changes

| File | Change Description |
|---|---|
| `config_shared.py` | Add `GEMINI_MODEL_OPTIONS`, `GEMINI_BASE_URL`; update `infer_model_provider()` type and logic; update `model_api_env_var()`; merge into `MODEL_OPTIONS`. |
| `ui/ui_state.py` | Add `gemini_key_var: tk.StringVar` to `AppState`. |
| `ui/ui_run_control.py` | Add Gemini key row in `build_credentials_tab()`; extend return tuple; update help text. |
| `vision_playwright_openai_vision_ui.py` | Update callers of `build_credentials_tab()` to unpack `gemini_key_var`; pass to `AppState` constructor. |
| `ui/ui_run_lifecycle.py` | Add Gemini key validation and env injection in `build_run_lifecycle()`. |
| `vision_playwright_openai_vision_poc.py` | Add `"gemini"` branch to `_new_model_client()`; ensure `_ResponsesAdapter.create()` routes `"gemini"` via OpenAI path. |
| `tests/test_gemini_provider.py` | New file: unit tests for REQ-1 through REQ-7 (see Testing Plan). |
| `webtests/run_testgemini_local.py` | New file: smoke script for end-to-end Gemini run (see Testing Plan). |
| `release_test.py` | Add unit + smoke coverage entries for Gemini tests. |
| `README.md` | Add `GEMINI_API_KEY` setup instructions and CLI usage example. |
| `docs/Structure.MD` | Update Provider Routing section to reference `"gemini"`. |

### Design Notes

- **Base URL constant:** `GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"` lives in `config_shared.py` as a named constant so it is easy to update and importable by both the runtime and tests.
- **Type annotation:** `infer_model_provider()` return type changes from `Literal["openai", "anthropic"]` to `Literal["openai", "anthropic", "gemini"]`. All consuming call sites must be verified with `python -m mypy .`.
- **Response adapter:** The `"gemini"` provider string flows through `_ModelClientAdapter` and `_ResponsesAdapter`. The adapter must branch on `"gemini"` the same as `"openai"` (not the Anthropic normalization path), since Gemini uses the OpenAI-compatible response envelope.
- **No new SDK dependency:** The existing `openai` package in `requirements.txt` supports `base_url` override; no new package is required.

---

## Testing Plan

### Test Cases

| Test ID | Type | File | Description | REQ Coverage |
|---|---|---|---|---|
| TEST-UNIT-GEMINI-001 | Unit | `tests/test_gemini_provider.py` | `infer_model_provider()` returns `"gemini"` for all `gemini-*` inputs; `model_api_env_var("gemini-2.0-flash")` returns `"GEMINI_API_KEY"`. | REQ-1, REQ-2 |
| TEST-UNIT-GEMINI-002 | Unit | `tests/test_gemini_provider.py` | `GEMINI_MODEL_OPTIONS` contains at least one entry; all entries appear in `MODEL_OPTIONS`; no existing OpenAI or Claude entries are removed. | REQ-3 |
| TEST-UNIT-GEMINI-003 | Unit | `tests/test_gemini_provider.py` | `_new_model_client("gemini-2.0-flash", "fake_key")` returns a `_ModelClientAdapter` with `provider == "gemini"` and the underlying client configured with `GEMINI_BASE_URL`. | REQ-7 |
| TEST-UNIT-GEMINI-004 | Unit | `tests/test_gemini_provider.py` | `AppState` dataclass has `gemini_key_var` attribute; `build_run_lifecycle()` raises/shows error and does NOT launch subprocess when Gemini model is selected and `gemini_key_var` is empty. | REQ-5, REQ-6 |
| TEST-SMOKE-GEMINI-001 | Smoke | `webtests/run_testgemini_local.py` | Full e2e login run against the local test site using `--model gemini-2.0-flash`; emits exactly one `FINAL: PASS` or `FINAL: FAIL`; no API or parsing errors in log. Success criterion: `VISUAL_UNIQUE: GEMINI_PROVIDER_SMOKE_COMPLETE` — terminal log line visible only at run completion, not in intermediate agent steps. | REQ-7, REQ-8, REQ-9 |

### Smoke Test Success Criteria (TEST-SMOKE-GEMINI-001)

- Exit code 0.
- Log contains exactly one `FINAL: PASS` token (per final-token policy).
- No lines matching `Error` or `Exception` from the Gemini client call path.
- `VISUAL_UNIQUE: GEMINI_PROVIDER_SMOKE_COMPLETE` appears in terminal output as the last status line — this token is injected by the smoke script only after all assertions pass and must not be present in earlier agent step logs.

### Commands

```bash
# Unit tests
python -m pytest -q tests/test_gemini_provider.py

# Full regression suite (must keep 105-test baseline passing)
python -m pytest -q tests/

# Precommit suite
python ./precommit_smoketest.py

# Feature smoke test (requires GEMINI_API_KEY in env)
python ./webtests/run_testgemini_local.py --skip-install --model gemini-2.0-flash
```

### Requirement-to-Test Traceability Matrix

| Requirement ID | Test ID | Test Type | Command |
|---|---|---|---|
| REQ-1 | TEST-UNIT-GEMINI-001 | Unit | `python -m pytest -q tests/test_gemini_provider.py` |
| REQ-2 | TEST-UNIT-GEMINI-001 | Unit | `python -m pytest -q tests/test_gemini_provider.py` |
| REQ-3 | TEST-UNIT-GEMINI-002 | Unit | `python -m pytest -q tests/test_gemini_provider.py` |
| REQ-4 | TEST-UNIT-GEMINI-004 | Unit | `python -m pytest -q tests/test_gemini_provider.py` |
| REQ-5 | TEST-UNIT-GEMINI-004 | Unit | `python -m pytest -q tests/test_gemini_provider.py` |
| REQ-6 | TEST-UNIT-GEMINI-004 | Unit | `python -m pytest -q tests/test_gemini_provider.py` |
| REQ-7 | TEST-UNIT-GEMINI-003 | Unit | `python -m pytest -q tests/test_gemini_provider.py` |
| REQ-7 | TEST-SMOKE-GEMINI-001 | Smoke | `python ./webtests/run_testgemini_local.py --skip-install --model gemini-2.0-flash` |
| REQ-8 | TEST-SMOKE-GEMINI-001 | Smoke | `python ./webtests/run_testgemini_local.py --skip-install --model gemini-2.0-flash` |
| REQ-9 | TEST-SMOKE-GEMINI-001 | Smoke | `python ./webtests/run_testgemini_local.py --skip-install --model gemini-2.0-flash` |

### Test Execution Evidence

*(To be filled during implementation)*

- Command: `python -m pytest -q tests/test_gemini_provider.py`
  - Exit code: `TBD`
  - Result token: N/A (unit run)
  - Log artifact: `TBD`

- Command: `python -m pytest -q tests/`
  - Exit code: `TBD`
  - Result token: N/A (unit run)
  - Log artifact: `TBD`

- Command: `python ./precommit_smoketest.py`
  - Exit code: `TBD`
  - Result token: `TBD` (per-run policy)
  - Log artifact: `TBD`

- Command: `python ./webtests/run_testgemini_local.py --skip-install --model gemini-2.0-flash`
  - Exit code: `TBD`
  - Result token: `TBD` (`FINAL: PASS` or `FINAL: FAIL`)
  - Log artifact: `TBD`

---

## Acceptance Criteria

- **AC-1** (`REQ-1`, `REQ-2`, `TEST-UNIT-GEMINI-001`): `infer_model_provider("gemini-2.0-flash")` returns `"gemini"` and `model_api_env_var("gemini-2.0-flash")` returns `"GEMINI_API_KEY"`.
- **AC-2** (`REQ-3`, `TEST-UNIT-GEMINI-002`): `GEMINI_MODEL_OPTIONS` includes at least one entry and every entry appears in `MODEL_OPTIONS`; existing OpenAI and Claude entries are not removed.
- **AC-3** (`REQ-4`, `REQ-5`, `REQ-6`, `TEST-UNIT-GEMINI-004`): GUI credentials panel displays a Gemini API Key field; selecting a `gemini-*` model and attempting a run without a key triggers the missing-key error dialog and does not launch the subprocess.
- **AC-4** (`REQ-7`, `TEST-UNIT-GEMINI-003`): `_new_model_client("gemini-2.0-flash", key)` returns a `_ModelClientAdapter` with `provider == "gemini"` using the correct Gemini OpenAI-compatible base URL.
- **AC-5** (`REQ-8`, `TEST-SMOKE-GEMINI-001`): A Gemini-powered smoke run against the local test site completes with exactly one `FINAL: PASS` and no response-parsing errors; terminal output includes `VISUAL_UNIQUE: GEMINI_PROVIDER_SMOKE_COMPLETE`.
- **AC-6** (`REQ-9`, `TEST-SMOKE-GEMINI-001`): The CLI correctly reads `GEMINI_API_KEY` from the environment for a `gemini-*` model and completes the run without a missing-key error.

---

## Sub-Agent Output Verification

### QAManager

| Field | Status | Notes |
|---|---|---|
| Scope Reviewed | COMPLETE | Reviewed all 6 affected files; scope matches REQ-1–REQ-9 |
| Findings (ordered by severity) | COMPLETE | 9 critical gaps identified (all requirements unimplemented); type annotation risk flagged |
| Requirement Traceability (REQ-* to TEST-*) | COMPLETE | All 9 REQs mapped to TEST-* IDs or explicitly NOT TESTED with justification |
| Commands Run | COMPLETE | Unit and smoke commands documented with portable path style |
| Artifacts | COMPLETE | Proposed: `tests/test_gemini_provider.py`, `webtests/run_testgemini_local.py` |
| Risks/Unknowns | COMPLETE | 6 risks documented: type annotation breaking change, Gemini endpoint behavior, base URL config, GUI testing limits, missing feature TDD (resolved), API key CI availability |
| Recommended Verdict | COMPLETE | FAIL — feature not yet implemented; prerequisite list provided |

**QAManager sub-agents invoked:** QA_WebAutomation (smoke script scope), QA_API (model client routing, env-var contract).

**QAManager VISUAL_UNIQUE validation:** Confirmed — `TEST-SMOKE-GEMINI-001` success criterion includes `VISUAL_UNIQUE: GEMINI_PROVIDER_SMOKE_COMPLETE` as a terminal-only marker injected by the smoke script only after all assertions pass.

**QAManager verdict:** FAIL — not yet implemented. See prerequisite checklist in this TDD.

---

### RequirementsTraceabilityReviewer

| Field | Status | Notes |
|---|---|---|
| Scope Reviewed | COMPLETE | Reviewed `config_shared.py`, `vision_playwright_openai_vision_poc.py`, `ui/ui_run_lifecycle.py`, `ui/ui_run_control.py`, `ui/ui_state.py`, `cli_entry.py`, `tests/test_claude_support_contract.py`, `tests/test_cli_smoke.py`, `webtests/run_testlogin_local.py` |
| Findings (ordered by severity) | COMPLETE | 17 findings: 9 CRITICAL (requirements not implemented), 8 MEDIUM (tests not written) |
| Requirement Traceability (REQ-* to TEST-* or NOT TESTED) | COMPLETE | 0/9 REQs implemented; all 8 TEST-* IDs marked NOT IMPLEMENTED with explicit reason |
| Commands Run | COMPLETE | Baseline: 105 tests pass; no Gemini tests found |
| Artifacts | COMPLETE | Source files inspected; no GeminiProviderSupport test files or TDD found |
| Risks/Unknowns | COMPLETE | 8 risks documented: Gemini OpenAI compat details, key naming conflict risk, `Literal` type change, `build_credentials_tab()` signature change, model list maintenance, smoke test env key availability, regression impact, UI state management |
| Recommended Verdict | COMPLETE | FAIL — 100% of requirements unmapped to implemented code; 0% test coverage |
| Requirement Coverage Matrix Audit | COMPLETE | All 9 REQs identified with file, line, and missing implementation detail |
| Acceptance Criteria Mapping Audit | COMPLETE | 6/6 ACs unmapped to passing tests; all marked NOT TESTED |
| Execution Evidence Audit | COMPLETE | No execution evidence exists for any GeminiProviderSupport test |
| Uncovered/At-Risk Items | COMPLETE | 9 explicit NOT TESTED entries; 5 at-risk integrations listed |

**Traceability reviewer verdict:** FAIL — resubmit after implementation and test authoring complete.

---

*Both subagent reports are COMPLETE. Planning phase may proceed to implementation. Implementation is blocked pending development work per the Linear Checklist above.*
