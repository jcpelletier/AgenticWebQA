# Planning Guide

## Purpose
Define a repeatable planning-orchestrator workflow for turning product requirements into an actionable feature TDD document through named subagents.

## When To Use
Use this guide whenever product introduces a new feature or meaningful behavior change.

## Legacy TDD Compatibility
- Existing feature TDDs authored under older planning rules are grandfathered.
- This guide is mandatory for new feature TDDs and major rewrites of existing TDDs.

## Planning Authority
- `.claude/commands/planning.md` is the top authority for planning-phase orchestration.
- Planning is the manager role. It owns requirement intake, subagent delegation, and final TDD authorship.
- Planning must call `.claude/commands/qa-manager.md` as a subagent for test strategy and required test commands.
- Planning must call a traceability/requirements-validation subagent (default: `.claude/commands/qa-traceability.md`) for REQ/AC mapping completeness.
- Planning does not directly orchestrate `QA_WebAutomation` or `QA_API`; those are routed by `QAManager` as needed.

## Source Of Truth Documents
- `AGENTS.md`: workflow rules, guardrails, and required doc updates.
- `docs/Structure.MD`: architecture/module/runtime flow boundaries.
- `docs/Code_Style.md`: coding conventions, structure boundaries, and tooling policy.
- `.claude/commands/planning.md`: planning-phase orchestration rules and output contract.
- `.claude/commands/qa-manager.md`: QA orchestration workflow, report contract, and completion gates.
- `.claude/commands/qa-traceability.md`: requirement-to-test traceability and evidence policy.
- `.claude/commands/qa-web-automation.md`: subordinate QA specialization (invoked by `QAManager` when applicable).
- `.claude/commands/qa-api.md`: subordinate QA specialization (invoked by `QAManager` when API scope exists).

## Inputs Required
- Product requirement text (problem, scope, constraints).
- Relevant existing feature docs under `docs/features/`.
- Any known operational constraints (environments, auth, external services).
- If available, changed-file candidates and known risk areas.

## Feature Spec Header (Required)
Every feature TDD must include:
- `Feature Name`
- `Feature Slug` (PascalCase; used for file naming: `docs/features/tdd_<FeatureSlug>.md`)
- `Owner`
- `User Story` (must include both: `Original Request Wording` quoted exactly from product input, and `Clarified Story` used for planning)
- `In Scope`
- `Out Of Scope`
- `Dependencies`
- `Rollout Risk`
- `Test Requirements`

## Output Contract (Strict)
Planner output must:
- Create exactly one file at `docs/features/tdd_<FeatureSlug>.md`.
- Use required sections and exact heading names in the exact order below.
- Include a linear checkbox checklist (`- [ ]`) in executable order.
- Preserve the exact original story request text verbatim in `Feature Spec Header > User Story` under `Original Request Wording`.
- Include measurable acceptance criteria.
- Include requirement IDs (`REQ-1`, `REQ-2`, ...) and reference those IDs in testing and acceptance criteria.
- Include test IDs (`TEST-UNIT-*`, `TEST-SMOKE-*`, `TEST-INTEG-*`, `TEST-REGRESSION-*`) and map acceptance criteria to both `REQ-*` and `TEST-*`.
- Require the `Testing Plan` content to be derived from `QAManager` subagent output.
- Require each visual smoke success criterion in `Testing Plan` to include `VISUAL_UNIQUE:` terminal marker text that is not visible in earlier prompt steps.
- Require explicit test execution evidence in the TDD showing which unit and integration/smoke commands were run and passed.
- Require all newly introduced unit/integration tests to be explicitly documented in the TDD Testing Plan (test IDs, scenario intent, and run command).
- Use portable Python command paths in testing instructions (for example `python ./webtests/run_test<feature>_local.py --skip-install --model gpt-5.1`).
- Avoid implementation code in planning output.

Example:
- `docs/features/tdd_RegisterAccount.md`

## Required Sections In Every Feature TDD (Exact Order, Exact Headings)
- `Feature Spec Header`
- `Summary`
- `Goals`
- `Non-Goals`
- `Assumptions`
- `Open Questions`
- `Sub-Agent Orchestration`
- `Linear Checklist`
- `UX Workflow`
- `Technical Design`
- `Testing Plan`
- `Acceptance Criteria`
- `Sub-Agent Output Verification`

## Sub-Agent Orchestration Contract
Planner must orchestrate the following named roles per feature:

- `PlanningOrchestrator` (manager role, this guide):
  - Owns final TDD output.
  - Resolves missing inputs and open questions.
- `QAManager` (required):
  - Returns test strategy, test IDs, required commands, and QA risks using `.claude/commands/qa-manager.md` output contract.
  - Routes subordinate QA specialists (`QA_WebAutomation`, `QA_API`) when feature scope requires it.
- `RequirementsTraceabilityReviewer` (required):
  - Default implementation: `.claude/commands/qa-traceability.md`.
  - Validates REQ/AC/TEST coverage and identifies `NOT TESTED` gaps.
  - Can be replaced by an equivalent traceability role if explicitly stated in the TDD.

Planner-to-subagent request packet (minimum):
- Feature slug and clarified story.
- Draft `REQ-*` list and acceptance criteria draft.
- In-scope/out-of-scope boundaries.
- Known assumptions/open questions.
- Candidate commands/artifact expectations.

## Planner Workflow
1. Restate feature goal in one short paragraph.
   - Include both the exact original request wording and a clarified story statement when needed.
2. Extract explicit product requirements.
3. Run Clarifications Gate and ask missing questions.
4. Define scope and non-goals.
5. Draft UX flow (happy path + failure behavior).
6. Draft technical design (files touched, data model, validation, edge handling).
7. Draft initial requirement IDs (`REQ-*`).
8. Invoke `QAManager` subagent with canonical request packet and capture returned test strategy, commands, and risks.
9. Invoke `RequirementsTraceabilityReviewer` subagent and capture coverage findings, mapping gaps, and `NOT TESTED` recommendations.
10. Reconcile subagent outputs; write `Testing Plan` and traceability matrix based on those outputs, enforcing `VISUAL_UNIQUE:` terminal markers for visual smoke success criteria.
11. Create a linear checklist with implementation + validation + docs steps. Default precommit policy: do not add new feature smoke scripts to `precommit_smoketest.py` unless explicitly requested by a developer.
12. Add three separate checklist items for test execution:
   - run `python ./precommit_smoketest.py`
   - run new feature unit tests
   - run new feature integration/smoke tests
   and capture pass evidence in the TDD.
13. If new automated unit/e2e coverage is introduced, add a checklist step to update `release_test.py` coverage.
14. Write measurable acceptance criteria mapped to both `REQ-*` and `TEST-*`.
15. Complete `Sub-Agent Output Verification` and ensure required report fields are present for each subagent.
16. Confirm source-of-truth constraints are respected.

## Clarifications Gate
Planner must ask follow-up questions when any of these are unclear:
- required fields/inputs
- validation rules
- success destination/state
- failure UX behavior
- storage/data lifecycle
- integration with existing flows
- out-of-scope boundaries
- required test scenarios
- QA and traceability ownership expectations

Defaulting policy:
- Low-risk copy/style defaults are allowed.
- Functional/behavioral defaults must be explicitly listed as assumptions in TDD.
- If clarification answers are unavailable, continue in fallback mode and mark each functional default as `ASSUMPTION:` in `Assumptions`.
- Any blocker that could change shipped behavior must be listed in `Open Questions`.
- If a required subagent is unavailable, continue in fallback mode and record an `Open Questions` blocker plus a temporary `ASSUMPTION:`.

## Checklist Quality Rules
- Must be linear and executable top-to-bottom.
- Must include implementation and validation tasks.
- Must include doc update steps when architecture/workflow changes.
- Must avoid vague items (for example, "finish feature").
- Each line must be independently checkable.
- Each checklist line should reference relevant `REQ-*` IDs when applicable.
- Checklist/test-plan language must default to NO automatic `precommit_smoketest.py` edits unless explicitly requested by a developer.
- Must include explicit, separate checklist steps to:
  - invoke `QAManager` and capture returned test requirements
  - invoke traceability reviewer and capture mapping audit
  - run `python ./precommit_smoketest.py`
  - run feature unit tests
  - run feature integration/smoke tests
- Must include a checklist step to update `release_test.py` when new automated unit/e2e coverage is introduced.
- Must include a step to record test commands and pass outcomes in the feature TDD.
- Must include checklist/test-plan coverage to document any new tests added for the feature (unit/integration), including test file/module names.
- Smoke command references should use portable path style: `python ./webtests/run_test<feature>_local.py ... --model <ai-model>`.
- For visual smoke tests, success criteria text must include `VISUAL_UNIQUE:` and describe a terminal-only visual signal absent from previous steps.

## Sub-Agent Output Verification Contract
`Sub-Agent Output Verification` section in each TDD must include one entry per required subagent and verify presence of these fields:
- `Scope Reviewed`
- `Findings (ordered by severity)`
- `Requirement Traceability (REQ-* to TEST-* or NOT TESTED)`
- `Commands Run`
- `Artifacts`
- `Risks/Unknowns`
- `Recommended Verdict (PASS | FAIL | PASS WITH RISKS)`

Verification rules:
- If any required field is missing, mark the subagent output as `INCOMPLETE` and list follow-up action in checklist.
- If subagents disagree, defer to `QAManager` tie-break policy or log blocker in `Open Questions`.
- Planning cannot mark planning phase done while required subagent outputs are `INCOMPLETE`.

## Handoff Prompt Template (Planner)
```text
Follow .claude/commands/planning.md.
Create docs/features/tdd_<FeatureSlug>.md using the required section order.
Use AGENTS.md, docs/Structure.MD, and docs/Code_Style.md as constraints.
In `Feature Spec Header > User Story`, always include `Original Request Wording` verbatim and a `Clarified Story` line.
If functional details are missing, ask clarifying questions before finalizing.
Include a linear checklist with implementation, validation, and doc update steps.

Sub-agent orchestration requirements:
1) Invoke QAManager (.claude/commands/qa-manager.md) as a subagent and capture its returned test strategy, commands, risks, and verdict.
2) Invoke a traceability reviewer subagent (default .claude/commands/qa-traceability.md) and capture REQ/TEST/AC mapping audit output.
3) Do not directly orchestrate QA_WebAutomation or QA_API from Planning; those route through QAManager.
4) Reconcile subagent outputs into `Testing Plan` and `Sub-Agent Output Verification`.

Use requirement IDs (REQ-1, REQ-2, ...) and map Acceptance Criteria + Testing Plan to both REQ-* and TEST-*.
For visual smoke tests, require `VISUAL_UNIQUE:` in success criteria and ensure that marker is terminal-only (not visible in prior steps).
If answers are unavailable, continue with explicit ASSUMPTION markers and capture blockers in Open Questions.
Default to no `precommit_smoketest.py` changes unless explicitly requested by a developer.
Require checklist items to separately run `python ./precommit_smoketest.py`, feature unit tests, and feature integration/smoke tests, and to record which test commands passed in the TDD.
Require generated feature integration/smoke command examples to include `--model <ai-model>` (default `gpt-5.1`) unless a different model is explicitly requested.
Require a checklist step to update `release_test.py` whenever new automated unit/e2e coverage is introduced.
Require the Testing Plan to list any new unit/integration tests added for the feature with test IDs, intent, and command.
Require Sub-Agent Output Verification to confirm required QAManager-style fields for each subagent response.
```

## Definition Of Done (Planning Phase)
- Feature TDD exists in `docs/features/`.
- Open questions are resolved or explicitly captured as assumptions.
- Checklist is implementation-ready.
- Acceptance criteria are measurable.
- Required section order is satisfied.
- `User Story` includes both exact `Original Request Wording` and `Clarified Story`.
- Requirement IDs and test IDs exist and are mapped through testing + acceptance criteria.
- TDD includes explicit, separate validation tasks to execute `python ./precommit_smoketest.py`, feature unit tests, and feature integration/smoke tests.
- TDD includes a step to update `release_test.py` when feature scope introduces new automated unit/e2e coverage.
- TDD includes a place to record test execution evidence (commands run and pass status) during implementation.
- TDD Testing Plan explicitly documents all newly added unit/integration tests for the feature.
- `QAManager` and traceability subagent outputs are captured and verified as complete in `Sub-Agent Output Verification`.
