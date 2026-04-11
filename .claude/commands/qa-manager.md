# QA Manager Guide

## Purpose
Define a manager-subordinate QA workflow where `QAManager` routes work to skill agents and issues a final QA decision.

## Authority
- `.claude/commands/qa-manager.md` is the top QA authority document in this repository.
- `.claude/commands/qa-web-automation.md`, `.claude/commands/qa-traceability.md`, and `.claude/commands/qa-api.md` are subordinate implementation guides.
- If any skill document conflicts with `.claude/commands/qa-manager.md`, follow `.claude/commands/qa-manager.md`.

## Scope
- Applies to QA planning, test design, and test execution review workflows.
- Complements existing repo rules in `AGENTS.md`, `.claude/commands/planning.md`, and the QA skill documents under `.claude/commands/`.

## Source Of Truth Documents
- `AGENTS.md`
- `docs/Code_Style.md`
- `docs/Structure.MD`
- `.claude/commands/planning.md`
- `.claude/commands/qa-manager.md`
- `.claude/commands/qa-web-automation.md`
- `.claude/commands/qa-traceability.md`
- `.claude/commands/qa-api.md` (when API scope exists)

## Inputs
- Feature request or bug request text.
- Relevant feature TDD (`docs/features/tdd_<FeatureSlug>.md`) when present.
- Changed files list and test artifacts/logs.

## Testing Layers
- Unit tests: logic/validation behavior under `tests/`.
- Integration smoke tests: end-to-end behavior via local test site and smoke scripts.
- Manual sanity checks: targeted browser verification for UI changes.

## Required Testing Outputs Per Feature
1. Test scenarios documented in feature TDD (`docs/features/tdd_<FeatureSlug>.md`).
2. Unit tests added/updated for new behavior.
3. Feature smoke script added as a dedicated Python file.
4. Requirement-to-test traceability matrix documented in the feature TDD.
5. Run commands and pass/fail criteria documented.

## Sub-Agent Catalog
- `.claude/commands/qa-web-automation.md`: browser-automation and smoke-flow specialist.
- `.claude/commands/qa-api.md`: API-contract and service-behavior specialist.
- `.claude/commands/qa-traceability.md`: requirement-to-test mapping and evidence specialist.

## Orchestration Workflow
1. Intake and classify scope (UI flow, API behavior, mixed).
2. Select sub-agents using Routing Rules.
3. Send each selected sub-agent the same canonical request + constraints.
4. Collect outputs using the Required Output Contract.
5. Reconcile conflicts and gaps.
6. Publish one manager-signed QA report with final verdict.

## Routing Rules
- Invoke `QA_WebAutomation` when request affects:
  - `webtests/` smoke scripts
  - UI routes/flows in `test-site/`
  - `vision_playwright_openai_vision_poc.py` e2e behavior
- Invoke `QA_API` when request affects:
  - API request/response contracts
  - endpoint validation/auth/error handling
  - integration boundaries with external/internal services
- Invoke both for mixed features crossing UI and API boundaries.
- Invoke `QA_Traceability` by default for every feature QA run.
- `QA_Traceability` is mandatory when:
  - A feature TDD changed.
  - `REQ-*` or `TEST-*` IDs were added/edited.
  - Smoke scripts or `release_test.py`/`precommit_smoketest.py` coverage changed.

## Must-Have vs Optional Tests
Must-have:
- Unit tests for new/changed logic.
- `webtests/run_test<feature>_local.py` script.
- Smoke command documentation.
- Smoke command documentation uses portable Python path style and includes model override (`python ./webtests/run_test<feature>_local.py ... --model <ai-model>`).
- Routine AI-driven QA runs `python ./precommit_smoketest.py` by default and records outcome (or explicit skip reason) in the QA report.
- `release_test.py` updated to include any new unit/e2e smoke coverage introduced by the feature.

Optional (explicit decision required):
- Adding feature smoke script to `precommit_smoketest.py` (only by explicit developer request or manual developer edit).
- Extra long-running end-to-end variants.
- Running `python ./release_test.py` during routine QA execution. This is manual-only and run only by explicit developer request or release sign-off.

## Required Output Contract (Sub-Agents)
Each sub-agent must return:
- Scope Reviewed
- Findings (ordered by severity)
- Requirement Traceability (REQ-* to TEST-* or NOT TESTED)
- Commands Run
- Artifacts (log/test output paths)
- Risks/Unknowns
- Recommended Verdict (PASS, FAIL, or PASS WITH RISKS)
- Prompt/Success Criteria Review (for `QA_WebAutomation`, must explicitly validate `VISUAL_UNIQUE:` terminal marker quality)

## Conflict Resolution
- Prefer evidence-backed findings (repro command + artifact) over opinion.
- If sub-agents disagree, mark as BLOCKED until tie-break checks run.
- Tie-break checks must be explicitly listed in manager report.

## Final Manager Gate
`QAManager` must verify before final sign-off:
- Exactly one final verdict token per QA_WebAutomation run entrypoint policy is preserved.
- Traceability matrix exists and maps all acceptance criteria.
- Required unit + smoke coverage exists or is explicitly marked NOT TESTED.
- Required docs were updated when workflow/structure changed.
- `QA_Traceability` report is present and all uncovered requirements are explicitly justified.
- Every QA_WebAutomation success criterion contains a `VISUAL_UNIQUE:` terminal-only visual marker that is not visible in earlier steps.

## Test Report Contract
For each run, report:
- Command executed
- Exit code
- Result token (`FINAL: PASS` or `FINAL: FAIL`) for QA_WebAutomation runs; otherwise `N/A`
- Whether skipped (`SKIP: <reason-code>` when applicable to QA_WebAutomation runs)
- Log artifact path (for example `<feature>_run.log`)

## Pass/Fail Rules
- `pytest` passes for affected test modules.
- Smoke script exits with code 0.
- Smoke success criteria are satisfied via the `vision_playwright_openai_vision_poc.py`-driven run.
- Smoke success criteria include a valid `VISUAL_UNIQUE:` terminal-only visible signal.
- Per-run token rule is satisfied for QA_WebAutomation runs: exactly one `FINAL: PASS` or `FINAL: FAIL`.
- Final report includes what was tested and what was skipped (`SKIP: <reason-code>` when used).
- `release_test.py` is not required for routine QA pass/fail unless explicitly requested by a developer.

## Completion Gate
- Unit tests added/updated and passing.
- Feature smoke script exists and is runnable.
- Traceability matrix exists and covers all acceptance criteria (or documents `NOT TESTED` gaps).
- Any precommit inclusion decision is explicitly documented.
- `python ./precommit_smoketest.py` was run for routine QA, or the report includes an explicit skip reason.
- `README.md` command examples updated if run workflow changed.
- Feature TDD checklist test items updated.

## Final Report Template
- Request Summary:
- Sub-Agents Invoked:
- Consolidated Findings:
- Coverage and Traceability Status:
- Commands and Artifacts:
- Open Risks:
- Final Verdict:
