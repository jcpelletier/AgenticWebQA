---
description: "Web automation QA policy: prompt and success-criteria authoring rules, smoke-script standards, and run-token policy. Use when reviewing or designing agent-driven browser e2e tests."
---

# QA WebAutomation Specialist

## Purpose
Define QA policy for AgenticWebQA web automation, where e2e behavior is produced by the
AgenticWebQA engine (`python -m agenticwebqa`) and not by direct Playwright-only scripts.

## System Model (Authoritative)
AgenticWebQA is a hybrid automation system:
- LLM plans and selects actions from prompt + screenshots + tool history.
- Playwright executes browser actions (DOM-first when possible).
- Vision fallback is used when DOM targeting fails or is unavailable.
- Learned actions/hints are persisted and reused across runs.

Practical implication:
- Playwright is an execution substrate inside the system.
- QA policy evaluates system-level resilience and end-state correctness, not brittle locator scripting.

## Policy Authority
This document is a web-automation specialization guide under `the qa-manager skill`.
If this document conflicts with `the qa-manager skill`, follow `the qa-manager skill`.

## Scope
- Registered smoke tests in `tests_registry.json` and custom smoke scripts.
- Prompt and success-criteria authoring for agent runs.
- Final token policy and run artifact quality.
- Release/precommit orchestration decisions for smoke coverage.

## Mandatory E2E Policy
- All automated e2e/smoke coverage MUST run through the AgenticWebQA engine
  (`python -m agenticwebqa` or the `agenticwebqa:run_test` MCP tool).
- Direct Playwright-only e2e validation is NOT allowed as the authoritative pass/fail signal.
- Playwright may be used for support checks (unit/contract/integration helpers) when not
  acting as the authoritative e2e verdict.

## Naming Conventions (Recommended)
- Unit tests: `tests/test_<feature>_<behavior>.py`
- Feature smoke log artifact: `<feature>_run.log`
- Tests registered in `tests_registry.json` under a descriptive snake_case key.

## Smoke Test Structure Standard
- Run smoke tests via `agenticwebqa:run_test(name="<name>")` (MCP) or the CLI.
- Precommit orchestration: curated manually — do not auto-add new feature smoke tests.
  Add only when a developer explicitly requests or manually performs the change.
- Release orchestration: add new automated unit/e2e coverage to your release suite.
  Do not run the release suite in routine QA flows; run only when explicitly requested.

## Feature Smoke Test Requirements
- Must validate the feature's primary user flow end-to-end.
- Must include deterministic terminal-state success criteria.
- Must emit a dedicated log artifact (`log_path` from `agenticwebqa:run_test`).
- Must support a `model` override (pass `model=` to MCP tool or `--model` to CLI).
- May auto-skip when the feature is not yet present.
- Must run agent invocations with `max_steps=20` (or `--max-steps 20`) unless explicitly overridden.
- Must preserve per-run final-token policy (`FINAL: PASS`/`FINAL: FAIL` exactly once).

## Prompt Authoring Rules (Required)
- Prompts must describe user intent and user actions only.
- Prompts must not include selector strings (`data-testid`, CSS, XPath).
- Prompts must not include inline verification instructions (`verify`, `assert`, `confirm`, `check`).
- Prompts should be short and procedural when sequencing matters.
- Use action language aligned to supported tool schema:
  - Prefer `click`, `type`, `send key`, `scroll`, `wait`, `hover`, `drag`.
  - Avoid ambiguous phrasing that implies unsupported argument keys.

## Success Criteria Rules (Required)
- Must evaluate final visible end state only.
- Must not evaluate intermediate steps or historical transitions.
- Must not embed persistence-history assertions that are not visible in terminal state.
- Should be deterministic and unambiguous for one-pass verdicting.
- Must include an explicit `VISUAL_UNIQUE:` line in the success criteria text.
- `VISUAL_UNIQUE:` must describe a terminal-only visible signal that is not visible before the final required action.
- If no terminal-only visual signal exists, mark the scenario as `BLOCKED` and request a UI-observable terminal marker before finalizing smoke criteria.

## Test Design Strategy
- Prefer a small set of focused prompts over one mega-prompt.
- Do not force one prompt per acceptance criterion.
- Split by terminal-state intent when multiple validations are required.
- Keep prompts/actions atomic and reusable where possible.

## Disallowed Patterns
- Playwright-only scripted e2e replacing agent-based smoke.
- Selector-heavy prompt authoring.
- Prompt steps that mix action + assertion in one instruction.
- Non-deterministic success criteria.
- Multiple incidental `FINAL:*` token occurrences in logs.

## Run Result Token Policy
- Scope: policy applies per automated run entrypoint.
- Each automated run must emit exactly one terminal token:
  - `FINAL: PASS`
  - `FINAL: FAIL`
- Skip behavior:
  - Skipped runs still emit exactly one terminal token.
  - Use `FINAL: PASS` with `SKIP: <reason-code>` in logs.
- Token safety:
  - Suppress incidental `FINAL: PASS`/`FINAL: FAIL` text in non-terminal logging.
- Precommit clarification:
  - A precommit suite may run multiple child runs.
  - Exactly-one token rule is per child run, not global per precommit session.

## QA Review Checklist (WebAutomation)
1. Test is registered in `tests_registry.json` or driven via the AgenticWebQA CLI.
2. Agent run uses the AgenticWebQA engine as the authoritative e2e path.
3. `max_steps=20` (or `--max-steps 20`) is used unless explicitly overridden.
4. Prompt is selector-free and verification-free.
5. Success criteria checks terminal visible state only and includes a valid `VISUAL_UNIQUE:` terminal marker.
6. Token policy is satisfied, including skip behavior.
7. Release suite updated when new automated smoke/unit coverage is introduced.
8. Release suite execution is skipped in routine QA unless explicitly requested.
9. Precommit suite is run in routine AI-driven QA and outcome (or explicit skip reason) is captured in the report.
10. Precommit suite modified only by explicit developer request.

## Output Contract
Return:
- `Scope Reviewed`
- `Findings` (ordered by severity)
- `Requirement Traceability` (REQ-* to TEST-* or NOT TESTED)
- `Commands Run`
- `Artifacts`
- `Risks/Unknowns`
- `Recommended Verdict` (PASS, FAIL, or PASS WITH RISKS)
- `Prompt/Success Criteria Review`
- `Token Policy Review`
- `Smoke Coverage Review`

## Handoff Prompt Template
```text
Follow the qa-manager skill and the qa-web-automation skill.

Task:
Review web automation quality for feature <FeatureSlug>.

Inputs:
- Feature TDD: docs/features/tdd_<FeatureSlug>.md (or equivalent)
- Changed files: <list>
- Relevant smoke tests: tests_registry.json entries for <feature> (and related)
- Relevant logs/artifacts: <list>

Required checks:
1) Confirm authoritative e2e path uses the AgenticWebQA engine.
2) Validate prompt authoring rules (no selectors, no inline verify/check, action-oriented steps).
3) Validate success criteria rules (terminal visible end-state only, deterministic, include `VISUAL_UNIQUE:` terminal-only marker).
4) Validate smoke-test requirements (model override support, max_steps=20 unless explicitly overridden).
5) Validate run token policy (exactly one FINAL token per run, SKIP format when applicable).
6) Validate orchestration policy (release suite updated for new coverage and treated as manual-only execution;
   precommit suite is run routinely for AI-driven QA; edits only when explicitly requested).

Execution:
- Run relevant unit/smoke commands as needed.
- Capture command, exit code, FINAL token (if applicable), and artifact path.

Output format (exact sections):
- Scope Reviewed
- Findings (ordered by severity)
- Requirement Traceability (REQ-* to TEST-* or NOT TESTED)
- Commands Run
- Artifacts
- Risks/Unknowns
- Recommended Verdict (PASS | FAIL | PASS WITH RISKS)
- Prompt/Success Criteria Review
- Token Policy Review
- Smoke Coverage Review

Constraints:
- Treat this as AgenticWebQA system QA (LLM+DOM+Playwright hybrid), not direct Playwright-only e2e design.
- Do not propose selector-heavy prompt rewrites.
```

## Typical Commands

Via MCP tool:
```
agenticwebqa:list_tests()
agenticwebqa:run_test(name="<feature>")
agenticwebqa:run_test(name="<feature>", model="gpt-4o-mini")
agenticwebqa:run_test(name="<feature>", headless=False)
```

Via CLI:
```bash
python -m pytest -q tests/
python -m agenticwebqa --start-url <url> --prompt "..." --visual-llm-success "..." --max-steps 20 --headless --verbose --model gpt-4o-mini
```

## Command Reference
- List registered tests:
  - `agenticwebqa:list_tests()`
- Run a registered test:
  - `agenticwebqa:run_test(name="<feature>")`
- Run an ad-hoc test:
  - `agenticwebqa:run_test(prompt="...", start_url="...", success_criteria="...", success_type="visual")`
- Run via CLI:
  - `python -m agenticwebqa --start-url <url> --prompt "..." --visual-llm-success "..." --headless --verbose`
- Run unit tests:
  - `python -m pytest -q tests/`
