---
description: "Requirement-to-test traceability auditing. Use when verifying REQ-* to TEST-* coverage, acceptance-criteria mapping, and execution evidence for a feature."
---

# QA Traceability Specialist

## Purpose
Validate requirement-to-test traceability and execution evidence completeness for each feature.

## Focus Areas
- `REQ-*` to `TEST-*` mapping completeness.
- Acceptance criteria mapping to both `REQ-*` and `TEST-*`.
- Command-level test executability and evidence quality.
- Coverage-gap handling with explicit `NOT TESTED` rationale.

## Required Test Matrix In Feature TDD
Each feature TDD should include at minimum:
- Happy path
- Validation errors
- Regression checks against existing behavior
- Smoke scope (what the smoke test verifies)
- Smoke prompt design notes showing how terminal-state validation is split across focused tests when needed.

Traceability requirements (mandatory):
- Define requirement IDs in planning (`REQ-1`, `REQ-2`, ...).
- Define test case IDs in testing (`TEST-UNIT-*`, `TEST-SMOKE-*`).
- Include a matrix mapping `Requirement ID -> Test ID -> Test Type -> Command`.
- Every acceptance criterion must map to at least one `REQ-*` and at least one `TEST-*`.
- Any uncovered requirement must be explicitly listed as `NOT TESTED` with a brief reason.

## Mandatory Checks
1. Every `REQ-*` maps to at least one `TEST-*` in the feature traceability matrix.
2. Every acceptance criterion maps to at least one `REQ-*` and at least one `TEST-*`.
3. Any uncovered requirement is explicitly marked `NOT TESTED` with reason.
4. Each mapped test includes a runnable command.
5. Executed tests include evidence: command, exit code, result token (when applicable), and artifact path.
6. Run-token evidence follows policy (`FINAL: PASS`/`FINAL: FAIL`, plus `SKIP: <reason-code>` when skipped).
7. TDD testing-plan IDs and actual test modules/registry entries are consistent.

## Inputs
- Feature TDD (e.g. `docs/features/tdd_<FeatureSlug>.md` or equivalent).
- Relevant test modules (e.g. under `tests/`).
- Relevant smoke tests registered in `tests_registry.json`.
- Run artifacts/log files referenced by the TDD.

## Output Contract
Return:
- `Scope Reviewed`
- `Findings` (ordered by severity)
- `Requirement Traceability` (REQ-* to TEST-* or NOT TESTED)
- `Commands Run`
- `Artifacts`
- `Risks/Unknowns`
- `Recommended Verdict` (PASS, FAIL, or PASS WITH RISKS)
- `Requirement Coverage Matrix Audit`
- `Acceptance Criteria Mapping Audit`
- `Execution Evidence Audit`
- `Uncovered/At-Risk Items`

## Handoff Prompt Template
```text
Follow the qa-manager skill and the qa-traceability skill.
Use the feature TDD as the traceability source of truth.
Audit REQ-* to TEST-* mappings and acceptance-criteria coverage.
Require explicit NOT TESTED entries for uncovered requirements.
Report exact run commands, exit codes, FINAL result tokens, and artifact paths for executed tests.
Return findings using the QA_Traceability output contract sections.
```

## Typical Commands
- Run all unit tests:
  - `python -m pytest -q tests/`
- Run feature unit tests:
  - `python -m pytest -q tests/test_<feature>*.py`
- Run a registered smoke test (MCP):
  - `agenticwebqa:run_test(name="<feature>")`
- Run a smoke test (CLI):
  - `python -m agenticwebqa --start-url <url> --prompt "..." --visual-llm-success "..." --headless --verbose --model gpt-4o-mini`
