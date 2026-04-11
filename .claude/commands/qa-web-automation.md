# QA WebAutomation Specialist

## Purpose
Define QA policy for AgenticWebQA web automation, where e2e behavior is produced by the agent system (`vision_playwright_openai_vision_poc.py`) and not by direct Playwright-only scripts.

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
This document is a web-automation specialization guide under `.claude/commands/qa-manager.md`.
If this document conflicts with `.claude/commands/qa-manager.md`, follow `.claude/commands/qa-manager.md`.

## Scope
- `webtests/run_test*_local.py` smoke workflows.
- Prompt and success-criteria authoring for agent runs.
- Final token policy and run artifact quality.
- Release/precommit orchestration decisions for smoke coverage.

## Mandatory E2E Policy
- All automated e2e/smoke coverage MUST run through `vision_playwright_openai_vision_poc.py`.
- Direct Playwright-only e2e validation inside feature smoke scripts is NOT allowed as the authoritative pass/fail signal.
- Playwright may be used for support checks (unit/contract/integration helpers) when not acting as the authoritative e2e verdict.

## Naming Conventions (Required)
- Unit tests: `tests/test_<feature>_<behavior>.py`
- Feature smoke script: `webtests/run_test<feature>_local.py`
- Feature smoke log artifact: `<feature>_run.log`

## Smoke Test Structure Standard
- Baseline flow:
  - `webtests/run_testlogin_local.py`
- Feature flow:
  - `webtests/run_test<feature>_local.py`
- Precommit orchestration:
  - `precommit_smoketest.py` is curated manually.
  - Default rule: do not auto-add new feature smoke scripts.
  - Add only when a developer explicitly requests or manually performs the change.
- Release orchestration:
  - `release_test.py` runs full release validation.
  - Default rule: add new automated unit/e2e coverage to `release_test.py`.
  - Execution rule: do not run `release_test.py` in routine QA flows; run only when explicitly requested by a developer or for manual release sign-off.

## Feature Smoke Script Requirements
- Must validate the feature's primary user flow end-to-end.
- Must include deterministic terminal-state success criteria.
- Must emit a dedicated log artifact.
- Must support `--skip-install`.
- Must support `--model` override for the AI model used by the run (default may be script-defined).
- May auto-skip when feature is not yet present.
- Should expose strict mode where relevant (for example `--require-feature`).
- Must run agent invocations with `--max-steps 20` unless explicitly overridden by a developer.
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
  - `precommit_smoketest.py` may run multiple child runs.
  - Exactly-one token rule is per child run, not global per precommit session.

## QA Review Checklist (WebAutomation)
1. Smoke script follows naming and `--skip-install`/strict-mode conventions.
2. Agent run uses `vision_playwright_openai_vision_poc.py` as authoritative e2e path.
3. `--max-steps 20` is used unless explicitly overridden.
4. Prompt is selector-free and verification-free.
5. Success criteria checks terminal visible state only and includes a valid `VISUAL_UNIQUE:` terminal marker.
6. Token policy is satisfied, including skip behavior.
7. `release_test.py` updated when new automated smoke/unit coverage is introduced.
8. `release_test.py` execution is skipped in routine QA unless explicitly requested.
9. `python ./precommit_smoketest.py` is run in routine AI-driven QA and outcome (or explicit skip reason) is captured in the report.
10. `precommit_smoketest.py` modified only by explicit developer request.

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
Follow .claude/commands/qa-manager.md and .claude/commands/qa-web-automation.md.

Task:
Review web automation quality for feature <FeatureSlug>.

Inputs:
- Feature TDD: docs/features/tdd_<FeatureSlug>.md
- Changed files: <list>
- Relevant smoke scripts: webtests/run_test<feature>_local.py (and related)
- Relevant logs/artifacts: <list>

Required checks:
1) Confirm authoritative e2e path uses vision_playwright_openai_vision_poc.py.
2) Validate prompt authoring rules (no selectors, no inline verify/check, action-oriented steps).
3) Validate success criteria rules (terminal visible end-state only, deterministic, and include `VISUAL_UNIQUE:` terminal-only marker).
4) Validate smoke-script requirements (--skip-install, required `--model` override support, optional --require-feature, max-steps 20 unless explicitly overridden).
5) Validate run token policy (exactly one FINAL token per run, SKIP format when applicable).
6) Validate orchestration policy (release_test.py updated for new coverage and treated as manual-only execution; precommit_smoketest.py is run routinely for AI-driven QA; script edits only when explicitly requested).

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
- `python -m pytest -q tests`
- `python ./webtests/run_test<feature>_local.py --skip-install --model gpt-5.1`
- `python ./webtests/run_test<feature>_local.py --skip-install --require-feature --model gpt-5.1`

## Command Reference
- Run release test suite:
  - `python ./release_test.py`
  - Manual-only: do not run during routine QA unless explicitly requested by a developer.
- Run all checks:
  - `python ./precommit_smoketest.py`
- Run login smoke:
  - `python ./webtests/run_testlogin_local.py --skip-install --model gpt-5.1`
- Run feature smoke:
  - `python ./webtests/run_testregister_local.py --skip-install --model gpt-5.1`
- Run feature smoke strict mode:
  - `python ./webtests/run_testregister_local.py --skip-install --require-feature --model gpt-5.1`
- Run local test site:
  - `python -m http.server 8000 --directory test-site`
