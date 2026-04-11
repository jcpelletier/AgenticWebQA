# Home Quiz (TDD)

## Feature Spec Header
- Feature Name: Home Quiz
- Feature Slug: HomeQuiz
- Owner: TBD
- User Story:
  - Original Request Wording: "As a user, I would like a Quiz feature on the home page, so that there is an activity on the home page to do . We want to add a basic quiz that appears on the home page. It consists of a list of 5 questions that are multiple choice with 4 possible answers each."
  - Clarified Story: As an authenticated user on Home, I can interact with a large quiz card that presents 4 multiple-choice questions, provides per-question correctness feedback, computes a final score, colors overall outcomes, and allows loading a new random quiz card from a 20-quiz bank with a small transition animation.
- In Scope:
  - Add a large quiz card to `test-site/home.html`.
  - Add a quiz bank of 20 quizzes in `test-site/app.js`.
  - Each quiz includes exactly 4 questions and each question has exactly 4 answer options.
  - Show per-question success/failure state after each answer.
  - Show final percentage after all questions are answered.
  - Show overall green/orange/red final status based on all/some/none correct.
  - Show `Next Quiz` button after completion and load a different random quiz card.
  - Apply small card-change animation for quiz replacement.
  - Add contract tests and feature smoke coverage.
- Out Of Scope:
  - Backend persistence of quiz attempts.
  - Timers, leaderboards, or scoring history.
  - Adaptive difficulty and user-specific quiz personalization.
  - Changes to login/register/profile flows.
- Dependencies:
  - Existing Home auth gate in `test-site/app.js`.
  - Existing home page shell (`test-site/home.html`) and styles (`test-site/styles.css`).
  - Existing smoke orchestration conventions in `webtests/` and `release_test.py`.
- Rollout Risk: Medium. The feature adds significant new interactive JS and Home UI state transitions.
- Test Requirements:
  - Add contract tests for Home quiz markup and quiz-bank/rules contract.
  - Add a dedicated feature smoke script `webtests/run_testhomequiz_local.py` with `--skip-install` and `--require-feature`.
  - Update release coverage with new smoke command.

## Summary
Add an interactive Home-page quiz experience that renders as a large card, uses a random quiz from a 20-quiz bank, provides immediate per-question correctness feedback, computes final percentage and color-coded overall status, and allows switching to a new randomized quiz card via a small animation.

## Goals
- Provide a visible, interactive quiz activity on Home.
- Keep quiz structure deterministic: 4 questions, 4 options each.
- Provide clear feedback at question and overall levels.
- Support repeated play via `Next Quiz` card replacement.
- Maintain compatibility with existing auth and navigation behavior.

## Non-Goals
- Storing quiz progress across sessions.
- Server/API-driven quiz data.
- Accessibility redesign beyond existing local test-site conventions.
- New cross-page navigation routes for quiz mode.

## Assumptions
- ASSUMPTION: Acceptance Criteria takes precedence over story prose conflict, so each quiz has 4 questions (not 5).
- ASSUMPTION: "Large card" means a clearly wider/taller card than existing small Home content card.
- ASSUMPTION: "Randomly each time" means initial load and each `Next Quiz` request select randomly from 20 quizzes, avoiding immediate repeat where possible.
- ASSUMPTION: Default policy applies: do not add this new smoke script to `precommit_smoketest.py` unless explicitly requested by a developer.

## Open Questions
- None.

## Sub-Agent Orchestration
- `PlanningOrchestrator`:
  - Scope: Convert request into REQ/AC/TEST design and implementation checklist.
  - Status: Complete.
- `QAManager`:
  - Scope Reviewed: Home quiz UI behavior, smoke path requirements, release coverage impact.
  - Findings (ordered by severity):
    - Must include dedicated smoke script with strict feature-detection behavior and one log artifact.
    - Must include deterministic checks for all three overall states (all/some/none correct).
    - Must preserve existing login/profile coverage without regressions.
  - Requirement Traceability: Planned REQ-to-TEST matrix provided below.
  - Commands Run: `python -m pytest -q tests/test_homequiz_contract.py`, `python ./webtests/run_testhomequiz_local.py --skip-install --require-feature`, `python ./precommit_smoketest.py`, `python ./release_test.py`.
  - Artifacts: `homequiz_run.log`, console outputs from unit/regression commands.
  - Risks/Unknowns: Release suite still has unrelated existing failures in register/profile-location smoke runs.
  - Recommended Verdict: PASS WITH RISKS.
- `RequirementsTraceabilityReviewer` (default `docs/skills/QA_Traceability.MD`):
  - Scope Reviewed: REQ completeness, AC mapping, command-level executability.
  - Findings (ordered by severity):
    - Every AC must map to both REQ and TEST IDs.
    - Coverage must include explicit verification for green/orange/red aggregate states and Next Quiz replacement behavior.
  - Requirement Traceability: Planned complete mapping present.
  - Commands Run: Reviewed command/evidence set from `Test Execution Evidence`.
  - Artifacts: Traceability matrix and execution artifacts listed below.
  - Risks/Unknowns: No traceability gaps; one regression command remains blocked by unrelated existing failures.
  - Recommended Verdict: PASS WITH RISKS.

## Linear Checklist
- [x] Define Home quiz requirement contracts and stable selectors (`REQ-1` to `REQ-10`).
- [x] Update `test-site/home.html` to include large quiz card container and required child slots (`REQ-1`, `REQ-8`).
- [x] Update `test-site/styles.css` with quiz card layout, per-question state styling, aggregate state colors, and card-transition animation (`REQ-1`, `REQ-3`, `REQ-5`, `REQ-6`, `REQ-7`, `REQ-9`).
- [x] Extend `test-site/app.js` with quiz bank and validation contracts (20 quizzes, 4 questions, 4 options) (`REQ-2`, `REQ-10`).
- [x] Implement Home quiz runtime behavior (answering, per-question feedback, final percentage, aggregate color state, next-quiz replacement) (`REQ-3`, `REQ-4`, `REQ-5`, `REQ-6`, `REQ-7`, `REQ-8`, `REQ-9`).
- [x] Add unit/contract test module for Home quiz (`TEST-UNIT-HOMEQUIZ-001`, `TEST-UNIT-HOMEQUIZ-002`, `TEST-UNIT-HOMEQUIZ-003`).
- [x] Add feature smoke script `webtests/run_testhomequiz_local.py` with `--skip-install`, `--require-feature`, and `homequiz_run.log` artifact (`TEST-SMOKE-HOMEQUIZ-001`).
- [x] Update `.gitignore` for `homequiz_run.log` (`TEST-SMOKE-HOMEQUIZ-001`).
- [x] Update `release_test.py` to include Home quiz smoke coverage (`TEST-REGRESSION-HOMEQUIZ-001`).
- [x] Update `README.md` and `docs/Structure.MD` for new feature and command references (`REQ-1` to `REQ-10`).
- [x] Invoke `QAManager` and capture returned test requirements in this TDD.
- [x] Invoke traceability reviewer and capture mapping audit in this TDD.
- [x] Run `python ./precommit_smoketest.py` and capture results (`TEST-REGRESSION-HOMEQUIZ-002`).
- [x] Run feature unit tests and capture results (`TEST-UNIT-HOMEQUIZ-001`, `TEST-UNIT-HOMEQUIZ-002`, `TEST-UNIT-HOMEQUIZ-003`).
- [x] Run feature integration/smoke tests and capture results (`TEST-SMOKE-HOMEQUIZ-001`).
- [x] Update `release_test.py` coverage evidence and command outcomes in this TDD.

## UX Workflow
1. Authenticated user lands on Home page and sees a large quiz card.
2. User sees 4 multiple-choice questions with 4 answer buttons each.
3. User answers each question once.
4. Each answered question immediately displays `Correct` or `Incorrect` state.
5. After all 4 answers are provided, quiz displays final percent correct.
6. Overall quiz card state becomes:
   - green when all answers are correct,
   - orange when some are correct,
   - red when none are correct.
7. `Next Quiz` button appears on completion.
8. User clicks `Next Quiz`; card animates and is replaced with a different random quiz from the bank.

## Technical Design
### Requirement IDs
- `REQ-1`: Home page renders a large quiz card UI.
- `REQ-2`: Each quiz rendered on Home has exactly 4 questions and each question has exactly 4 answer options.
- `REQ-3`: Quiz displays success/failure state per question after answer selection.
- `REQ-4`: Quiz displays percentage correct after all questions are answered.
- `REQ-5`: Overall quiz UI is green when all answers are correct.
- `REQ-6`: Overall quiz UI is orange when some answers are correct.
- `REQ-7`: Overall quiz UI is red when no answers are correct.
- `REQ-8`: `Next Quiz` appears only after completion and replaces current card content.
- `REQ-9`: Card replacement applies a small transition animation.
- `REQ-10`: System maintains a 20-quiz bank and selects quiz content randomly per load/next cycle.

### File Changes
- `test-site/home.html`
  - Add quiz card container/slots with stable `data-testid` selectors.
- `test-site/styles.css`
  - Add large-card styles, question/result styles, aggregate status color classes, and page-turn-like transition keyframes.
- `test-site/app.js`
  - Add quiz bank, bank validation, random selection, render/answer logic, aggregate scoring logic, and next-quiz transition behavior.
- `tests/test_homequiz_contract.py` (new)
  - Contract tests for Home markup and quiz bank/state/animation contracts.
- `webtests/run_testhomequiz_local.py` (new)
  - Agent-driven smoke plus deterministic support checks for required quiz states.
- `release_test.py`
  - Add Home quiz smoke step.
- `.gitignore`
  - Add `homequiz_run.log`.
- `README.md`, `docs/Structure.MD`
  - Document feature and smoke command.

## Testing Plan
### Test Cases
- `TEST-UNIT-HOMEQUIZ-001` (Unit/Contract): Home page includes large quiz-card selectors and required structural slots.
- `TEST-UNIT-HOMEQUIZ-002` (Unit/Contract): Quiz bank contract exists with 20 quiz IDs, each containing 4 questions and 4 answer options.
- `TEST-UNIT-HOMEQUIZ-003` (Unit/Contract): App/style contracts include per-question result states, aggregate color states, Next Quiz behavior, and card transition animation hooks.
- `TEST-SMOKE-HOMEQUIZ-001` (Smoke): End-to-end flow verifies quiz completion behavior, percentage display, red/orange/green aggregate states, Next Quiz replacement, and transition trigger.
- `TEST-REGRESSION-HOMEQUIZ-001` (Regression): `release_test.py` includes and executes Home quiz smoke in full suite.
- `TEST-REGRESSION-HOMEQUIZ-002` (Regression): `python ./precommit_smoketest.py` remains passing for existing baseline checks.

### Commands
- `python -m pytest -q tests/test_homequiz_contract.py`
- `python ./webtests/run_testhomequiz_local.py --skip-install`
- `python ./webtests/run_testhomequiz_local.py --skip-install --require-feature`
- `python ./release_test.py`
- `python ./precommit_smoketest.py`

### Requirement-to-Test Traceability Matrix
| Requirement ID | Test ID | Test Type | Command |
|---|---|---|---|
| REQ-1 | TEST-UNIT-HOMEQUIZ-001 | Unit/Contract | `python -m pytest -q tests/test_homequiz_contract.py` |
| REQ-2 | TEST-UNIT-HOMEQUIZ-002 | Unit/Contract | `python -m pytest -q tests/test_homequiz_contract.py` |
| REQ-3 | TEST-UNIT-HOMEQUIZ-003 | Unit/Contract | `python -m pytest -q tests/test_homequiz_contract.py` |
| REQ-3 | TEST-SMOKE-HOMEQUIZ-001 | Smoke | `python ./webtests/run_testhomequiz_local.py --skip-install --require-feature` |
| REQ-4 | TEST-SMOKE-HOMEQUIZ-001 | Smoke | `python ./webtests/run_testhomequiz_local.py --skip-install --require-feature` |
| REQ-5 | TEST-SMOKE-HOMEQUIZ-001 | Smoke | `python ./webtests/run_testhomequiz_local.py --skip-install --require-feature` |
| REQ-6 | TEST-SMOKE-HOMEQUIZ-001 | Smoke | `python ./webtests/run_testhomequiz_local.py --skip-install --require-feature` |
| REQ-7 | TEST-SMOKE-HOMEQUIZ-001 | Smoke | `python ./webtests/run_testhomequiz_local.py --skip-install --require-feature` |
| REQ-8 | TEST-SMOKE-HOMEQUIZ-001 | Smoke | `python ./webtests/run_testhomequiz_local.py --skip-install --require-feature` |
| REQ-9 | TEST-UNIT-HOMEQUIZ-003 | Unit/Contract | `python -m pytest -q tests/test_homequiz_contract.py` |
| REQ-9 | TEST-SMOKE-HOMEQUIZ-001 | Smoke | `python ./webtests/run_testhomequiz_local.py --skip-install --require-feature` |
| REQ-10 | TEST-UNIT-HOMEQUIZ-002 | Unit/Contract | `python -m pytest -q tests/test_homequiz_contract.py` |
| REQ-1..REQ-10 | TEST-REGRESSION-HOMEQUIZ-001 | Regression | `python ./release_test.py` |
| REQ-1..REQ-10 | TEST-REGRESSION-HOMEQUIZ-002 | Regression | `python ./precommit_smoketest.py` |

### Test Execution Evidence
- Command: `python -m pytest -q tests/test_homequiz_contract.py`
  - Exit code: `0`
  - Result token: N/A (pytest unit run)
  - Outcome: `3 passed`
  - Artifacts: Console output only
- Command: `python ./webtests/run_testhomequiz_local.py --skip-install --require-feature`
  - Exit code: `0`
  - Result token: `FINAL: PASS`
  - Artifacts: `homequiz_run.log` (contains `FINAL: PASS`)
- Command: `python ./precommit_smoketest.py`
  - Exit code: `0`
  - Result token: Login smoke emitted terminal `FINAL: PASS` token(s) per run
  - Outcome: `ruff format` passed, `mypy` passed, `pytest` passed (`42 passed`), login integration smoke passed
- Command: `python ./release_test.py`
  - Exit code: `1`
  - Result token: Mixed child-run results
  - Outcome: Home quiz smoke step passed; release suite failed due existing unrelated register/profile-location smoke failures
  - Summary: `4 passed, 2 failed, 6 total`

## Acceptance Criteria
- `AC-1` (`REQ-1`, `TEST-UNIT-HOMEQUIZ-001`, `TEST-SMOKE-HOMEQUIZ-001`): Quiz appears as a large card on Home page.
- `AC-2` (`REQ-2`, `TEST-UNIT-HOMEQUIZ-002`, `TEST-SMOKE-HOMEQUIZ-001`): Quiz has 4 questions, each with 4 answers.
- `AC-3` (`REQ-3`, `TEST-UNIT-HOMEQUIZ-003`, `TEST-SMOKE-HOMEQUIZ-001`): Each question shows success/failure state after answer.
- `AC-4` (`REQ-4`, `TEST-SMOKE-HOMEQUIZ-001`): Quiz shows percentage correct when all questions are answered.
- `AC-5` (`REQ-5`, `TEST-SMOKE-HOMEQUIZ-001`): Overall quiz UI shows green success state when all questions are correct.
- `AC-6` (`REQ-6`, `TEST-SMOKE-HOMEQUIZ-001`): Overall quiz UI shows orange success state when some questions are correct.
- `AC-7` (`REQ-7`, `TEST-SMOKE-HOMEQUIZ-001`): Overall quiz UI shows red success state when no questions are correct.
- `AC-8` (`REQ-8`, `TEST-SMOKE-HOMEQUIZ-001`): `Next Quiz` appears after completion and replaces the current quiz card with a new one.
- `AC-9` (`REQ-9`, `TEST-UNIT-HOMEQUIZ-003`, `TEST-SMOKE-HOMEQUIZ-001`): Card replacement includes a small animation (page-turn or similar).
- `AC-10` (`REQ-10`, `TEST-UNIT-HOMEQUIZ-002`, `TEST-SMOKE-HOMEQUIZ-001`): Site uses a bank of 20 quizzes and pulls randomly per run.

## Sub-Agent Output Verification
### QAManager
- Scope Reviewed: Home quiz feature plan, smoke/release coverage strategy.
- Findings (ordered by severity): Present.
- Requirement Traceability (REQ-* to TEST-* or NOT TESTED): Present.
- Commands Run: `python -m pytest -q tests/test_homequiz_contract.py`, `python ./webtests/run_testhomequiz_local.py --skip-install --require-feature`, `python ./precommit_smoketest.py`, `python ./release_test.py`.
- Artifacts: `homequiz_run.log`, console outputs for pytest/precommit/release.
- Risks/Unknowns: Release suite still has unrelated flaky failures in existing register/profile-location smoke.
- Recommended Verdict (PASS | FAIL | PASS WITH RISKS): PASS WITH RISKS.
- Verification Status: COMPLETE.

### RequirementsTraceabilityReviewer
- Scope Reviewed: REQ/TEST/AC mapping completeness.
- Findings (ordered by severity): Present.
- Requirement Traceability (REQ-* to TEST-* or NOT TESTED): Present.
- Commands Run: Evidence commands reviewed in `Test Execution Evidence`.
- Artifacts: Traceability matrix above and run artifacts/logs.
- Risks/Unknowns: `TEST-REGRESSION-HOMEQUIZ-001` currently blocked by unrelated pre-existing release-suite failures.
- Recommended Verdict (PASS | FAIL | PASS WITH RISKS): PASS WITH RISKS.
- Verification Status: COMPLETE.
