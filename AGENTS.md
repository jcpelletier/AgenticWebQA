# AGENTS.md

## Purpose
This file captures agent-specific collaboration rules and points to the correct source-of-truth documents.

## Scope
- Applies to all automated agents and assistants operating in this repository.
- If a rule conflicts with higher-priority system or developer instructions, those take precedence.

## Source Of Truth Documents
- `README.md`: product behavior, setup, run commands, and operator workflow.
- `docs/Code_Style.md`: coding standards, structure boundaries, testing expectations, and tooling policy.
- `docs/Structure.MD`: architecture map of key modules and runtime flow.
- `.claude/commands/qa-manager.md`: QA orchestration workflow, reporting contract, and completion gates.
- `.claude/commands/qa-web-automation.md`: web automation testing policy, smoke rules, and token policy.
- `.claude/commands/qa-traceability.md`: requirement-to-test traceability and evidence auditing rules.
- `.claude/commands/qa-api.md`: API-focused QA checks and contract validation policy.
- `.claude/commands/qa-test-authoring.md`: MCP-based test authoring workflow — how to author, run, retry, and escalate new tests using the agenticwebqa MCP server.

## Project Overview
- The goal of this project is to produce a new way of writing resilient web page automation using an LLM.
- Initially resolve test prompts using LLM actions and then save Playwright actions for future runs.
- Tests created using this tech will support CI/CD. They can be run using CLI or the GUI.
- Tests created using this tech will heal themselves when locators are updated, potentially resulting in no test failures after a locator change.
- Fall back on the LLM when tests fail and then have the LLM rewrite the actions if successful.
- Actions are written to be as atomic as possible while still being useful and reusable. Ideally a prompt to test a profile UI component would likely have actions like: `login`, `navigate_to_profile`, `confirm_profile_element`.

## Workflow
- Ignore vision_playwright_claude_cua_poc.py until further notice.
- Prefer small, reviewable changes.
- Keep prompts and actions atomic when possible.
- Update or create prompt routes for stable multi-step flows.
- Logging must emit exactly one `FINAL: PASS` or `FINAL: FAIL` per run; suppress any other occurrences of those tokens in log output so pass-counting is reliable.
- Run local quality checks with `python ./precommit_smoketest.py` from repo root (format, mypy, unit tests, integration smoke).
- Update `docs/Structure.MD` when architecture/module boundaries or runtime flow change.
- Update `README.md` when run commands, setup, or operator workflow changes.
- Update `docs/Code_Style.md` when style/tooling policy changes.

## Coding Conventions
- Follow `docs/Code_Style.md` for repo-specific style rules (applies to humans and agents).
- Treat `pyproject.toml` as the source of truth for Ruff and mypy configuration.
- Follow `.editorconfig` for line endings/indentation/editor defaults.
- Use UTF-8 (no BOM) for Markdown files.
- Use existing patterns and utilities in the repo.
- Avoid introducing new dependencies unless necessary.

## Contacts
- Add maintainers or owners here.
