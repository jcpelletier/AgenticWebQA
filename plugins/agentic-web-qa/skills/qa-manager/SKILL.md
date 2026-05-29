---
description: "QA orchestration: route QA work to specialist skills (web automation, API, traceability) and issue a single signed QA verdict. Use when planning, coordinating, or signing off on feature/bug QA."
---

# QA Manager Guide

## Purpose
Define a manager-subordinate QA workflow where `QAManager` routes work to skill agents and issues a final QA decision.

## Authority
- `the qa-manager skill` is the top QA authority document for this project.
- `the qa-web-automation skill`, `the qa-traceability skill`, and `the qa-api skill` are subordinate implementation guides.
- If any skill document conflicts with `the qa-manager skill`, follow `the qa-manager skill`.

## Scope
- Applies to QA planning, test design, and test execution review workflows.
- Complements `the planning skill` and the QA skill documents.

## Source Of Truth Documents
- Your project's architecture and coding guidelines docs (e.g. `AGENTS.md`, `docs/Code_Style.md`, `docs/Structure.md`, or equivalents).
- `the planning skill`
- `the qa-manager skill`
- `the qa-web-automation skill`
- `the qa-traceability skill`
- `the qa-api skill` (when API scope exists)

## Inputs
- Feature request or bug request text.
- Relevant feature TDD (e.g. `docs/features/tdd_<FeatureSlug>.md`) when present.
- Changed files list and test artifacts/logs.

## Testing Layers
- Unit tests: logic/validation behavior (e.g. under `tests/`).
- Integration smoke tests: end-to-end behavior via the AgenticWebQA engine against your app under test.
- Manual sanity checks: targeted browser verification for UI changes.

## Required Testing Outputs Per Feature
1. Test scenarios documented in the feature TDD.
2. Unit tests added/updated for new behavior.
3. Feature smoke test added to `tests_registry.json`.
4. Requirement-to-test traceability matrix documented in the feature TDD.
5. Run commands and pass/fail criteria documented.

## Sub-Agent Catalog
- `the qa-web-automation skill`: browser-automation and smoke-flow specialist.
- `the qa-api skill`: API-contract and service-behavior specialist.
- `the qa-traceability skill`: requirement-to-test mapping and evidence specialist.
- `the qa-ci-setup skill`: CI/CD pipeline configuration and model-drift workflow specialist.

## Orchestration Workflow
1. Intake and classify scope (UI flow, API behavior, mixed).
2. Select sub-agents using Routing Rules.
3. Send each selected sub-agent the same canonical request + constraints.
4. Collect outputs using the Required Output Contract.
5. Reconcile conflicts and gaps.
6. Publish one manager-signed QA report with final verdict.

## Routing Rules
- Invoke `QA_WebAutomation` when request affects:
  - Browser UI flows against your app under test.
  - Registered tests in `tests_registry.json`.
  - AgenticWebQA engine behavior (prompts, success criteria, action replay).
- Invoke `QA_API` when request affects:
  - API request/response contracts.
  - Endpoint validation/auth/error handling.
  - Integration boundaries with external/internal services.
- Invoke both for mixed features crossing UI and API boundaries.
- Invoke `QA_Traceability` by default for every feature QA run.
- `QA_Traceability` is mandatory when:
  - A feature TDD changed.
  - `REQ-*` or `TEST-*` IDs were added/edited.
  - Smoke tests in `tests_registry.json` or your release/precommit suite changed.
- Invoke `QA_CISetup` when:
  - The developer asks to configure CI, GitHub Actions, or automated test runs.
  - A new project has tests in `tests_registry.json` but no CI workflow yet.
  - Model-drift handling is needed (CI re-learned actions that should be committed back).
  - The developer asks why CI is re-learning tests or spending LLM tokens unexpectedly.

## Must-Have vs Optional Tests
Must-have:
- Unit tests for new/changed logic.
- A registered smoke test in `tests_registry.json` (run via `agenticwebqa:run_test` or `python -m agenticwebqa`).
- Smoke command documentation.
- Smoke command documentation uses portable Python path style and includes model override.
- Routine AI-driven QA runs your precommit suite (if one exists) by default and records outcome (or explicit skip reason) in the QA report.
- Your release suite updated to include any new unit/e2e smoke coverage introduced by the feature.

Optional (explicit decision required):
- Adding a new smoke test to your precommit suite (only by explicit developer request or manual developer edit).
- Extra long-running end-to-end variants.
- Running your full release suite during routine QA execution. This is manual-only and run only by explicit developer request or release sign-off.

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
- Log artifact path

## Pass/Fail Rules
- `pytest` passes for affected test modules.
- Smoke test exits with code 0 and emits `FINAL: PASS`.
- Smoke success criteria are satisfied via the AgenticWebQA engine.
- Smoke success criteria include a valid `VISUAL_UNIQUE:` terminal-only visible signal.
- Per-run token rule is satisfied for QA_WebAutomation runs: exactly one `FINAL: PASS` or `FINAL: FAIL`.
- Final report includes what was tested and what was skipped (`SKIP: <reason-code>` when used).
- Your full release suite is not required for routine QA pass/fail unless explicitly requested by a developer.

## Completion Gate
- Unit tests added/updated and passing.
- Feature smoke test exists in `tests_registry.json` and is runnable.
- Traceability matrix exists and covers all acceptance criteria (or documents `NOT TESTED` gaps).
- Any precommit inclusion decision is explicitly documented.
- Your precommit suite was run for routine QA, or the report includes an explicit skip reason.
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
