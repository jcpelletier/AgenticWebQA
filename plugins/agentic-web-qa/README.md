# agentic-web-qa

Self-healing, LLM-driven web QA for Claude Code. An LLM explores a site and
learns reliable Playwright actions on the first run, then replays those actions
without the model on later runs — and falls back to the LLM (re-learning the
action) when a selector changes. This makes browser tests resilient to UI churn.

## What's in this plugin

- **Skills** — QA workflow guides Claude uses automatically:
  - `qa-manager` — orchestrates QA work and issues a single signed verdict
  - `qa-test-authoring` — authors, runs, and validates new web tests
  - `qa-web-automation` — prompt/success-criteria and smoke-script policy
  - `qa-traceability` — requirement-to-test coverage auditing
  - `qa-api` — API/service contract QA
  - `qa-ci-setup` — generates a CI workflow (GitHub Actions, GitLab, Jenkins,
    CircleCI) that runs the registered tests and proposes model updates when
    selectors drift
  - `planning` — turns product requirements into a feature TDD
- **MCP server** (`agenticwebqa`) — exposes the AgenticWebQA engine to Claude
  (`list_tests`, `run_test`, and authoring helpers).
- **CLI entry points** installed with the package:
  - `agenticwebqa-init` — bootstrap `tests_registry.json` + `Models/` in a project
  - `agenticwebqa-run-test <name>` — run a registered test (the command CI uses)
  - `agenticwebqa-mcp` — MCP server
  - `agenticwebqa-gui` — desktop authoring UI

Skills are namespaced under the plugin, e.g. `/agentic-web-qa:qa-test-authoring`.

## Prerequisites

The MCP server drives a Python engine that runs a real browser, so it must be
installed on your machine (it is not bundled in the plugin):

```bash
pip install "agenticwebqa[mcp]"   # provides the `agenticwebqa-mcp` command
python -m playwright install chromium
```

Provide the API key(s) for the model provider(s) you use. The plugin passes
these through to the MCP server from your environment:

- `OPENAI_API_KEY` (for `gpt-*` models)
- `ANTHROPIC_API_KEY` (for `claude-*` models)
- `GEMINI_API_KEY` (for `gemini-*` models)
- `WEBQA_USERNAME` / `WEBQA_PASSWORD` (optional, for login flows)

## Install

```shell
/plugin marketplace add jcpelletier/AgenticWebQA
/plugin install agentic-web-qa@agenticwebqa
```

For local development of the plugin itself:

```shell
/plugin marketplace add ./
/plugin install agentic-web-qa@agenticwebqa
```

## Status

`v0.2.0` — pre-release. The engine is not yet on PyPI, so installs come from
source until publication:

```bash
pip install "agenticwebqa[mcp] @ git+https://github.com/jcpelletier/AgenticWebQA"
```

Once published, this becomes `pip install "agenticwebqa[mcp]"`.
