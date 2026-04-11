# Claude Support (TDD)

## Feature Spec Header
- Feature Name: Claude Support
- Feature Slug: ClaudeSupport
- Owner: TBD
- User Story:
  - Original Request Wording: "lets writeup a new feature doc based on planning.md The new feature will be \n\"Claude Support\"\nAs a developer I would like to be able to use Claude APIs, so that I can choose that as an option.\n\nAcceptance Criteria:\n- A variety of Claude API model options are available in the Model dropdown.\n- The existing workflow works using claude api models"
  - Clarified Story: As a developer, I want Anthropic Claude API support in the existing CLI/UI workflow so I can select Claude models in the Model dropdown and execute the same end-to-end agent flow without breaking current OpenAI behavior.
- In Scope:
  - Add Anthropic Claude as a supported provider option for model calls in the core runtime.
  - Expose multiple Claude model options in UI Model dropdown and CLI model selection path.
  - Add provider/API-key configuration contracts for Claude in UI launch flow and subprocess environment wiring.
  - Keep existing run flow semantics (learn, reuse, auto-heal, success verification, final token policy) working when Claude is selected.
  - Add tests and smoke validation for provider selection and Claude execution path.
- Out Of Scope:
  - Replacing OpenAI as default provider.
  - New UI redesign beyond required provider/model selection controls.
  - Non-Claude providers beyond currently supported OpenAI + new Claude provider.
  - Cost/performance optimization tuning for every Claude model variant.
- Dependencies:
  - `config_shared.py` for shared model defaults/options and argument metadata.
  - `vision_playwright_openai_vision_poc.py` runtime model call + response parsing paths.
  - `vision_playwright_openai_vision_ui.py` and `ui/` modules for credentials/model dropdown/run environment wiring.
  - `requirements.txt` dependency declaration for Claude client package.
  - Existing smoke entrypoints in `webtests/` and orchestration scripts (`precommit_smoketest.ps1`, `release_test.ps1`) per policy.
- Rollout Risk: Medium. Provider abstraction and response-shape differences can regress action parsing, final verdict detection, or UI launch contracts if not guarded by tests.
- Test Requirements:
  - Unit tests for provider selection/config validation and Claude response normalization contracts.
  - UI contract tests for Model dropdown including multiple Claude entries.
  - Integration/smoke test execution proving existing workflow passes with a Claude model.
  - Requirement-to-test traceability matrix mapping every `REQ-*` to `TEST-*`.

## Summary
Introduce Claude API support as an additional selectable model provider so developers can run the same AgenticWebQA workflow with Claude models. The feature must add multiple Claude choices in the UI Model dropdown, preserve current workflow behavior, and maintain existing OpenAI compatibility.

## Goals
- Support Claude model execution through existing agent runtime flow.
- Expose multiple Claude model options in the UI model selection path.
- Preserve existing workflow behavior (learn/reuse/auto-heal/final verification) under Claude selection.
- Keep OpenAI workflow backward-compatible.
- Add measurable test coverage for provider selection and execution behavior.

## Non-Goals
- Building a generalized multi-provider plugin framework beyond immediate Claude support.
- Migrating existing saved actions/model files to provider-specific formats.
- Changing final-token policy semantics.
- Expanding test-site product behavior for this feature.

## Assumptions
- ASSUMPTION: The UI will continue using a single Model dropdown; provider is inferred from selected model name unless explicit provider control is introduced during implementation.
- ASSUMPTION: Claude API key is supplied through environment variable `ANTHROPIC_API_KEY` and kept separate from `OPENAI_API_KEY`.
- ASSUMPTION: Existing OpenAI model options remain available and functional.
- ASSUMPTION: Default policy applies: do not add new feature smoke scripts to `precommit_smoketest.ps1` unless explicitly requested.

## Open Questions
- Should provider be explicitly selectable in UI/CLI (for example `--provider anthropic|openai`) instead of inferring provider from model name?
- Which Claude model versions are required for MVP availability in dropdown (for example `claude-sonnet-4-5`, `claude-opus-4-1`, `claude-haiku-4-5`), and should this list be centrally version-pinned?
- Should Claude-specific run telemetry (token usage/cost fields) be normalized to match existing OpenAI logging output format?

## Linear Checklist
- [ ] Define Claude support requirements and IDs (`REQ-1`, `REQ-2`, `REQ-3`, `REQ-4`, `REQ-5`, `REQ-6`).
- [ ] Update `config_shared.py` model/provider constants so Claude model options are available for CLI/UI selection (`REQ-1`, `REQ-2`).
- [ ] Add runtime provider selection + client initialization in `vision_playwright_openai_vision_poc.py` for OpenAI and Claude (`REQ-3`).
- [ ] Add Claude response parsing/normalization path that maps Claude output to existing internal action/verdict contracts (`REQ-3`, `REQ-4`).
- [ ] Update UI credentials/settings flow to accept Claude API key and pass it to run subprocess environment (`REQ-5`).
- [ ] Update UI Model dropdown population to include multiple Claude models while preserving existing OpenAI models (`REQ-1`, `REQ-2`).
- [ ] Add/update unit tests for provider routing, response normalization, and config validation (`TEST-UNIT-CLAUDE-001`, `TEST-UNIT-CLAUDE-002`, `TEST-UNIT-CLAUDE-003`).
- [ ] Add/update UI contract tests for dropdown options and credential propagation (`TEST-UNIT-CLAUDE-004`).
- [ ] Add/update smoke coverage to execute existing workflow with selected Claude model (`TEST-SMOKE-CLAUDE-001`).
- [ ] Run `.\precommit_smoketest.ps1` and capture results in this TDD (`TEST-REGRESSION-CLAUDE-001`).
- [ ] Run feature unit tests and capture command + pass evidence in this TDD (`TEST-UNIT-CLAUDE-001`, `TEST-UNIT-CLAUDE-002`, `TEST-UNIT-CLAUDE-003`, `TEST-UNIT-CLAUDE-004`).
- [ ] Run feature integration/smoke tests and capture command + pass evidence in this TDD (`TEST-SMOKE-CLAUDE-001`).
- [ ] Record all executed test commands, exit codes, and pass outcomes in the Testing Plan evidence section.
- [ ] Update `README.md` for Claude setup/usage commands and `docs/Structure.MD` if module/runtime flow boundaries change.
- [ ] Confirm all acceptance criteria are satisfied and mapped to `REQ-*` and `TEST-*` IDs.

## UX Workflow
1. Developer opens the UI launcher and navigates to model/settings controls.
2. Model dropdown displays existing OpenAI models plus multiple Claude model options.
3. Developer enters required API key for selected provider and starts run.
4. Run executes the existing workflow (prompt route selection, action execution, verification, and final verdict emission).
5. Developer can switch between OpenAI and Claude models without changing prompt/test intent.

## Technical Design
### Requirement IDs
- `REQ-1`: The UI Model dropdown includes multiple Claude model options.
- `REQ-2`: Claude model options are selectable through shared model config used by both CLI and UI paths.
- `REQ-3`: Runtime can initialize and call Claude APIs while retaining OpenAI path behavior.
- `REQ-4`: Claude responses are normalized to existing internal action/verdict contracts so existing workflow behavior is preserved.
- `REQ-5`: Claude API key configuration is supported in UI-run subprocess environment wiring.
- `REQ-6`: Existing workflow (learn/reuse/auto-heal/success verification/final token emission) executes successfully with at least one Claude model.

### File Changes
- `config_shared.py`
  - Add/update model option constants to include supported Claude models.
  - Add any provider/model validation helpers required by CLI/UI shared config.
- `vision_playwright_openai_vision_poc.py`
  - Add provider routing and Claude client call path.
  - Add Claude response parsing/normalization into existing action/verdict abstraction.
- `vision_playwright_openai_vision_ui.py`
  - Extend credential handling and settings wiring for Claude API key.
  - Ensure Model dropdown includes Claude options from shared config.
- `ui/ui_settings_tabs.py`, `ui/ui_run_control.py`, `ui/ui_run_lifecycle.py` (as needed)
  - Surface Claude credential input and propagate provider-specific env vars to subprocess runs.
- `requirements.txt`
  - Add Anthropic SDK dependency if not already present.
- `tests/test_*claude*.py` (new/updated)
  - Provider routing, normalization contracts, and UI model option assertions.
- `webtests/run_test*_local.py` (existing script update or new feature smoke script)
  - Add Claude-mode smoke execution path honoring existing smoke policies.
- `README.md`
  - Add Claude environment setup and execution examples.

## Testing Plan
### Test Cases
- `TEST-UNIT-CLAUDE-001` (Unit): Shared config exposes multiple Claude model options and validates model selection contracts.
- `TEST-UNIT-CLAUDE-002` (Unit): Runtime provider routing selects Claude/OpenAI client paths correctly based on selected model/provider.
- `TEST-UNIT-CLAUDE-003` (Unit): Claude response normalization returns expected internal action/verdict structures.
- `TEST-UNIT-CLAUDE-004` (Unit/UI Contract): UI Model dropdown includes Claude options and run lifecycle passes `ANTHROPIC_API_KEY` when needed.
- `TEST-SMOKE-CLAUDE-001` (Smoke): Existing workflow run (login or profile flow) executes end-to-end with a Claude model and emits exactly one final token.
- `TEST-REGRESSION-CLAUDE-001` (Regression): Existing precommit regression suite continues passing for non-Claude baseline behavior.

### Commands
- `python -m pytest -q tests/test_claude_*.py`
- `python -m pytest -q tests/test_ui_*claude*.py`
- `python .\webtests\run_testlogin_local.py --skip-install --model <claude-model>`
- `python .\webtests\run_testprofilepage_local.py --skip-install --model <claude-model>`
- `.\precommit_smoketest.ps1`

### Requirement-to-Test Traceability Matrix
| Requirement ID | Test ID | Test Type | Command |
|---|---|---|---|
| REQ-1 | TEST-UNIT-CLAUDE-001 | Unit | `python -m pytest -q tests/test_claude_*.py` |
| REQ-1 | TEST-UNIT-CLAUDE-004 | Unit/UI Contract | `python -m pytest -q tests/test_ui_*claude*.py` |
| REQ-2 | TEST-UNIT-CLAUDE-001 | Unit | `python -m pytest -q tests/test_claude_*.py` |
| REQ-2 | TEST-UNIT-CLAUDE-002 | Unit | `python -m pytest -q tests/test_claude_*.py` |
| REQ-3 | TEST-UNIT-CLAUDE-002 | Unit | `python -m pytest -q tests/test_claude_*.py` |
| REQ-3 | TEST-SMOKE-CLAUDE-001 | Smoke | `python .\webtests\run_testlogin_local.py --skip-install --model <claude-model>` |
| REQ-4 | TEST-UNIT-CLAUDE-003 | Unit | `python -m pytest -q tests/test_claude_*.py` |
| REQ-4 | TEST-SMOKE-CLAUDE-001 | Smoke | `python .\webtests\run_testprofilepage_local.py --skip-install --model <claude-model>` |
| REQ-5 | TEST-UNIT-CLAUDE-004 | Unit/UI Contract | `python -m pytest -q tests/test_ui_*claude*.py` |
| REQ-6 | TEST-SMOKE-CLAUDE-001 | Smoke | `python .\webtests\run_testlogin_local.py --skip-install --model <claude-model>` |
| REQ-1, REQ-2, REQ-3, REQ-4, REQ-5, REQ-6 | TEST-REGRESSION-CLAUDE-001 | Regression | `.\precommit_smoketest.ps1` |

### Test Execution Evidence
- Command: `python -m pytest -q tests/test_claude_*.py`
  - Exit code: `TBD`
  - Result token: N/A (unit run)
  - Log artifact: `TBD`
- Command: `python -m pytest -q tests/test_ui_*claude*.py`
  - Exit code: `TBD`
  - Result token: N/A (unit/UI contract run)
  - Log artifact: `TBD`
- Command: `python .\webtests\run_testlogin_local.py --skip-install --model <claude-model>`
  - Exit code: `TBD`
  - Result token: `TBD` (`FINAL: PASS` or `FINAL: FAIL`)
  - Log artifact: `TBD`
- Command: `python .\webtests\run_testprofilepage_local.py --skip-install --model <claude-model>`
  - Exit code: `TBD`
  - Result token: `TBD` (`FINAL: PASS` or `FINAL: FAIL`)
  - Log artifact: `TBD`
- Command: `.\precommit_smoketest.ps1`
  - Exit code: `TBD`
  - Result token: `TBD` (per-run policy)
  - Log artifact: `TBD`

## Acceptance Criteria
- `AC-1` (`REQ-1`, `TEST-UNIT-CLAUDE-001`, `TEST-UNIT-CLAUDE-004`): UI Model dropdown lists a variety of Claude API model options.
- `AC-2` (`REQ-2`, `TEST-UNIT-CLAUDE-001`, `TEST-UNIT-CLAUDE-002`): Claude model options are available through shared CLI/UI model configuration.
- `AC-3` (`REQ-3`, `TEST-UNIT-CLAUDE-002`, `TEST-SMOKE-CLAUDE-001`): Runtime can execute model calls through Claude APIs without breaking OpenAI path selection.
- `AC-4` (`REQ-4`, `TEST-UNIT-CLAUDE-003`, `TEST-SMOKE-CLAUDE-001`): Existing workflow logic continues to function with Claude responses through normalized action/verdict contracts.
- `AC-5` (`REQ-5`, `TEST-UNIT-CLAUDE-004`): UI launch flow supports Claude API key configuration for subprocess execution.
- `AC-6` (`REQ-6`, `TEST-SMOKE-CLAUDE-001`, `TEST-REGRESSION-CLAUDE-001`): Existing workflow completes successfully using Claude model selection and keeps baseline regressions passing.
