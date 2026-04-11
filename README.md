# Vision + DOM Hybrid Browser Agent
![demo](https://github.com/user-attachments/assets/ca860220-c45e-47ff-83c0-444983349c5b)


This project is a proof-of-concept browser automation agent that combines:
- DOM-first interactions (Playwright locators) when targets can be identified, and
- Vision-based fallback using OpenAI vision models when DOM hints are missing or fail.

The main script is `vision_playwright_openai_vision_poc.py`.
The optional GUI launcher is `vision_playwright_openai_vision_ui.py`.

## Docs Index

- `AGENTS.md`: agent collaboration and repository rules.
- `docs/Code_Style.md`: coding standards and tooling policy.
- `docs/Structure.MD`: architecture map and runtime flow.
- `docs/REPO_REVIEW.md`: repository review notes and commands.
- `docs/Planning.MD`: workflow for turning product requirements into feature TDD docs.
- `docs/QAManager.MD`: QA orchestration workflow, report contract, and completion gates.
- `docs/skills/QA_WebAutomation.MD`: web automation testing policy and smoke rules.
- `docs/skills/QA_Traceability.MD`: requirement-to-test traceability and evidence auditing.
- `docs/skills/QA_API.MD`: API-focused QA policy and checks.
- `docs/features/tdd_RegisterAccount.md`: TDD and implementation plan for Register Account.
- `docs/features/tdd_ProfilePage.md`: TDD and implementation plan for Profile Page.
- `docs/features/tdd_ProfileLocationDropdown.md`: TDD and implementation plan for Profile Country/State dropdown behavior.
- `docs/features/tdd_HomeQuiz.md`: TDD and implementation plan for Home quiz card behavior.

## Adding A New Feature

Use this process for all new product features:

1. Create a feature TDD file at `docs/features/tdd_<FeatureName>.md`.
2. Use `docs/Planning.MD` to guide requirements intake and build the TDD structure/checklist.
3. Implement the feature by working through the TDD checklist in order.
4. Use `docs/QAManager.MD` plus `docs/skills/QA_WebAutomation.MD` and `docs/skills/QA_Traceability.MD` to define and add required tests (unit/integration/smoke).
5. Update docs and smoke orchestration as needed, then run `python ./precommit_smoketest.py`.

## Install

```powershell
# If pip is missing for your Python install
python -m ensurepip --upgrade

# Install Python dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Install Playwright browser binaries
python -m playwright install chromium
```

## Formatting

We use `ruff format` as the single source of truth for Python formatting (humans and robots). Before committing, run:
For repo-specific coding conventions (for humans and agents), follow `docs/Code_Style.md`.
Tooling configuration is centralized in `pyproject.toml` (`[tool.ruff]`, `[tool.ruff.format]`, `[tool.mypy]`), and editor defaults are in `.editorconfig`.

```powershell
python -m ruff format .
```

## Build GUI Binary (Optional)

The GUI launcher can be packaged with PyInstaller:

```powershell
python -m PyInstaller VisionLauncher.spec
```

Output goes to `dist/VisionLauncher/` (build artifacts in `build/`).

## Recommended Workflow

The intended workflow is two-phase:

1. LLM training runs (headed, best model).
   - Run prompts in primarily LLM mode to explore the site and learn reliable DOM hints.
   - This builds the site actions library automatically (`site_hints.json` and `Models/*.json`).
   - Use the best available model here. Recommendation: `gpt-5.1`.
2. Test execution runs (Playwright-first).
   - Re-run prompts and tests with the learned library in place.
   - Playwright handles stable steps, while the LLM can adapt to small UI changes without failing the current run.

## High-Level Flow

1) Parse CLI arguments.
2) Validate environment (OpenAI API key, optional Pillow for downscaling).
3) Launch Playwright (Chromium) and create a page.
4) Build the initial prompt for the OpenAI vision model.
5) Loop until a final verdict or max steps:
   - Take a screenshot for the model (CSS-scaled).
   - Send messages to the model.
   - Parse the response for a tool action or FINAL verdict.
   - Execute the action using DOM-first logic (site hints + heuristics), fall back to vision actions.
   - Log results and continue.
6) Save a success/failure screenshot and exit.

## Detailed Logic Walkthrough

### 1) Configuration and Defaults

The top of the script defines defaults used across the agent:
- Model selection (`DEFAULT_MODEL`).
- Viewport sizing and cost controls (max tokens, pruning window).
- Action safety settings (click settle timing, arm/commit gating).
- Screenshot annotation settings (red X size/thickness).

These defaults reduce spend by limiting tokens and trimming historical images,
while maintaining enough context for reliable action selection.

### 2) Startup and Environment Checks

`main()` parses CLI arguments and constructs viewports:
- `--width/--height` are the actual browser viewport size.
- `--model-width/--model-height` optionally downscale screenshots sent to the model.

`run_agent()` validates:
- `OPENAI_API_KEY` is set.
- Pillow is available when downscaling is requested.

### 3) Initial Prompt Construction

`build_initial_messages()` creates the initial user message with:
- The task prompt and success criteria.
- DOM-first instructions (use selectors/role/text when possible).
- Vision-only constraints (no address bar).
- Final verdict protocol (`FINAL: PASS` or `FINAL: FAIL`).
- Optional credentials from environment variables.

This gives the model stable rules for tools, safety, and success.

## Prompt Variables and Reusable Actions

### Template Variables (`{...}`)

Prompts and success criteria support `{variable}` substitution. Before the agent runs, the following variables are resolved:

| Variable | Source | Example value |
|---|---|---|
| `{username}` | `WEBQA_USERNAME` env var, or extracted from prompt | `Automation` |
| `{password}` | `WEBQA_PASSWORD` env var, or extracted from prompt | `hunter2` |
| `{date}` | Current date | `2026-03-17` |
| `{epoch}` | Current Unix timestamp (integer string) | `1742173200` |
| `{rand_string}` | 5-char random lowercase string, generated once per run | `xkqmv` |
| `{query}` | First quoted value found in the prompt | see below |
| `{prompt}` | Full rendered prompt text | — |
| `{success_criteria}` | Full rendered success criteria text | — |

Example prompt using variables:

```
1. Enter username {username}
2. Enter password {password}
3. Click Sign In
```

At runtime, `{username}` and `{password}` are replaced before the agent runs and before the prompt is passed to the LLM.

### How Quoting Makes Actions Reusable

When you write a literal value in your prompt — for example:

```
Input username 'Automation'
```

— the agent extracts `Automation` as the username fallback (used when `WEBQA_USERNAME` is not set in the environment). More importantly, when a saved action step types a value that matches the current username, password, or rand_string, **the literal value is automatically replaced with its template placeholder** (`{username}`, `{password}`, `{rand_string}`) in the stored action JSON.

This means:
- A saved `login` action stores `{username}` and `{password}` — not hardcoded credentials.
- The same saved action works for any user simply by changing the env var or prompt.
- Actions shared across a team or CI environment stay credential-free in source control.

The same logic applies to `{rand_string}`: if your registration prompt uses a unique value (e.g., a timestamp-based username), the saved action stores `{rand_string}` so each replay generates a fresh unique value automatically.

### How `{query}` Works

`{query}` captures the **first single- or double-quoted string** in the prompt. It is useful for search or lookup actions where the target term is defined inline:

```
Search for 'quarterly report' and open the first result.
```

Here `{query}` resolves to `quarterly report`. A reusable `search` action can store `{query}` as its typed text, so changing the quoted term in the prompt changes what is searched — without editing the saved action.

#### Don't repeat the quoted value in follow-up steps

`{query}` normalization applies to **typed text only** — it does not apply to click selectors. If the quoted value appears again in a later step, the LLM uses it as an anchor when constructing the click selector, baking the literal value into the saved action and making it brittle.

**Problematic — repeats `'Chicago'` in the click step:**
```
1. Search for 'Chicago'
2. Open the Movie Details screen for the 'Chicago'
```
The LLM sees "Chicago" in step 2 and saves a selector like `[title="Chicago"]`. That action fails for any other movie.

**Better — name the item once, then use a positional instruction:**
```
1. Search for 'Chicago'
2. Open the Movie Details screen for the first result
```
Step 1 guarantees the search is for Chicago. Step 2 has nothing to anchor on, so the LLM picks a generic structural selector that works for any search term.

### Adding a New Variable

1. Add an entry to the `variables` dict near line 7050 in `vision_playwright_openai_vision_poc.py`:

    ```python
    variables = {
        "username": username or "",
        "password": password or "",
        "date": _now.strftime("%Y-%m-%d"),
        "epoch": str(int(_now.timestamp())),
        "rand_string": "".join(random.choices(string.ascii_lowercase, k=5)),
        "my_var": some_value,   # ← add your variable here
    }
    ```

2. If typed text containing this value should be normalized to `{my_var}` in saved actions, add a corresponding check in `_normalize_typed_text` (around line 5232):

    ```python
    if my_var and value == my_var:
        return "{my_var}"
    ```

3. Use `{my_var}` in any prompt or success criteria string — it will be substituted before the agent starts.

---

### Prompt Reliability Tips

Use language that matches the schema actions to reduce ambiguity:
- For buttons and links, use terms like `click`, `left click`, or `double click`.
- For typing, use `type` or `enter text`.
- For key presses, use `send key Enter` or `hit Enter key` (avoid the word `press`).
- For scrolling, use `scroll`.
- For mouse movement or hover, use `mouse move` or `hover`.
- For dragging, use `drag`.
- For timing gaps, use `wait`.
- For captures, use `screenshot`.

Avoid prompt wording that suggests unsupported argument keys. For example, avoid saying "press" if you want a key action; prefer "send key" or "hit key" instead.

### 4) The Agent Loop

`run_agent()` executes a step loop (default 40 steps):

#### a) Screenshot and Context
- The agent optionally saves a pre-step screenshot to `agent_view/step_XXX.pre.png`
  (disabled with `--no-agent-view`).
- For model context, the last N turns are kept; all but the most recent
  screenshot image payloads are stripped to reduce cost.

#### b) Model Call
The model responds with either:
- A tool action (`tool_use`), or
- A `FINAL: PASS/FAIL` verdict.

#### c) Final Verdict Handling
If `FINAL: PASS/FAIL` is detected:
- A final screenshot is saved.
- The script exits.

#### d) Tool Action Handling
If a tool action is requested, the script:
- Validates there's exactly one tool_use call.
- Previews click-like actions with optional arm/commit gating.
- Executes the action (DOM-first or vision fallback).

### 5) DOM-First Actions with Vision Fallback

For `left_click` and `double_click`:
- The script tries DOM hints first using Playwright locators:
  - `role` + `name` / label / aria-label (preferred), then
  - `selector` (CSS), then
  - `target_text`
- If DOM selection fails or errors, the action falls back to
  the vision-based coordinate action.

For `type`, the script always uses `page.keyboard.type(...)` to avoid
changing focus by selecting the wrong field.

This improves reliability and reduces the need for large screenshot history.

### 7) Site Hints Map (Auto-Learned)

The agent maintains a per-site hints file (JSON) keyed by domain:
- Default path: `site_hints.json` (configurable via `--site-hints-path`).
- If the file does not exist, it is created automatically.
- When a DOM hint succeeds, it is appended to that site's hints entry.
- You can edit the file manually to refine or add new selectors.

Example structure:

```json
{
  "yahoo.com": {
    "selectors": ["input[name='p']"],
    "role_name": [{"role": "searchbox", "name": "Search"}],
    "text": ["Search"]
  }
}
```

### 8) DOM Heuristics Before Vision

If no explicit hint is supplied or in the site map, the agent tries common selectors
for inputs before resorting to vision (e.g., `input[type=search]`, `input[name=q]`,
`[role=searchbox]`, `input[placeholder*="search" i]`).

### 9) Tool Results and Screenshots

After executing an action:
- Post-action screenshots are saved in `agent_view/` when enabled.
- If an error occurs, a failure screenshot is saved to
  `<screenshot-base>.failure.png`.

### 10) Cost Controls

Cost savings are implemented via:
- Aggressive pruning of older messages.
- Stripping image payloads from all but the most recent screenshot tool_result (capped at 1).
- Low default `max_tokens`.
- Optional downscaling of screenshots sent to the model.

These are designed to keep the tool responsive and affordable while still
providing enough visual context to make accurate decisions.

Recommended cost flags for most runs:
- `--max-tokens 192 --max-steps 20 --keep-last-turns 3 --keep-last-images 0`

Current estimate: roughly $0.01 per step when using the flags above (varies by
page complexity, screenshot frequency, and model output length).

## DOM vs. Vision Behavior

The agent attempts DOM-first actions for clicks, then falls back to vision
when DOM targets are unavailable or unreliable. Typing always targets the
currently focused element.

Common reasons DOM fails and vision is used:
- The page uses dynamic IDs/classes without stable roles or labels.
- Elements are rendered inside a canvas, image, or custom widget.
- The model did not include DOM hints in its tool input.
- The element exists but is offscreen or hidden at the moment of action.

How to push more DOM usage:
- Add or edit entries in `site_hints.json` for known targets.
- Use `--site-hints-path` to point at a shared hints file across runs.

How to diagnose which path ran:
- DOM actions return `dom: true` and include `dom_hint` in tool results.
- Vision fallback results include coordinates.

## UI Model Selection (Dropdown)

In the UI (`vision_playwright_openai_vision_ui.py`), the Model dropdown currently includes:
- `gpt-5`
- `gpt-5.1`
- `gpt-5.2`
- `gpt-5-mini`
- `gpt-5-nano`

Recommendation:
- Use `gpt-5.1` for LLM training runs and difficult sites.
- Use the smaller models for cheaper exploratory runs when needed.

The dropdown value maps directly to the CLI `--model` flag.

## Manual Click Interjection (Headed Mode)

When running headed (not `--headless`), you can interject during a stuck step:
- Click the correct element yourself in the live browser.
- The agent will record a `manual interject` step.
- It will extract DOM hints from your click, update `site_hints.json`, and feed that hint into the next model step.

This is especially useful during LLM training runs when a control is hidden, covered, or requires human-like reveal behavior.

## CLI Flags

Required:
- `--prompt`: Task instruction for the agent.
- `--success-criteria`: Text describing what must be visible for `FINAL: PASS`.
- `--start-url`: Page to open before the agent starts.

Optional:
- `--actions`: Comma-separated list of action functions to allow (recommended allowlist).
- `ANTHROPIC_API_KEY`: Anthropic API key (environment variable).
- `WEBQA_USERNAME`: Username for login tasks — maps to `{username}` in prompts (environment variable).
- `WEBQA_PASSWORD`: Password for login tasks — maps to `{password}` in prompts (environment variable).
- `--model`: OpenAI model name.
- `--width`: Browser viewport width (actual).
- `--height`: Browser viewport height (actual).
- `--model-width`: Model screenshot width (0 uses `--width`).
- `--model-height`: Model screenshot height (0 uses `--height`).
- `--headless`: Run Chromium headless.
- `--slowmo`: Playwright slowmo in ms.
- `--max-steps`: Maximum agent loop iterations.
- `--max-tokens`: Max tokens per model response (0 uses low default).
- `--max-tokens-margin`: Additional margin for thinking.
- `--pre-click-sleep`: Sleep before click-like actions (seconds).
- `--pre-type-sleep`: Sleep before Playwright type actions (seconds).
- `--post-shot-sleep`: Sleep after each model screenshot (seconds).
- `--post-action-sleep`: Sleep after each Playwright action (seconds).
- `--post-type-sleep`: Sleep after Playwright type actions (seconds).
- `--arm-commit`: Enable arm/commit gating for clicks. Increases token cost.
- `--confirm-token`: Token required to commit armed click.
- `--arm-timeout-steps`: Expire armed click after N steps.
- `--keep-last-turns`: Keep last N messages in history.
- `--keep-last-images`: Keep last N screenshot tool_results (0 strips all images).
- `--x-size`: Red X half-size in pixels for annotations.
- `--x-thickness`: Red X thickness in pixels for annotations.
- `--verbose`: Enable verbose logging.
- `--screenshot-base`: Base screenshot path (writes `.success.png`/`.failure.png`).
- `--agent-view-dir`: Directory for per-step `agent_view` screenshots.
- `--no-agent-view`: Disable extra `agent_view` debug captures.
- `--max-subactions-per-function`: Hard cap on actions per learned function (default: 3).
- `--site-hints-path`: Path to JSON file for per-site DOM hints.

## Credentials

You can set credentials as environment variables so secrets never appear in plain text on the command line:

- `ANTHROPIC_API_KEY`: Anthropic API key used for model calls.
- `WEBQA_USERNAME`: Username used for login flows (maps to `{username}` in prompts).
- `WEBQA_PASSWORD`: Password used for login flows (maps to `{password}` in prompts).

Set them permanently in PowerShell:

```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-your-key", "User")
[System.Environment]::SetEnvironmentVariable("WEBQA_USERNAME", "demo.user@example.com", "User")
[System.Environment]::SetEnvironmentVariable("WEBQA_PASSWORD", "P@ssw0rd123!", "User")
```

Or for the current session only:

```powershell
$env:ANTHROPIC_API_KEY="sk-your-api-key-here"
$env:WEBQA_USERNAME="demo.user@example.com"
$env:WEBQA_PASSWORD="P@ssw0rd123!"
```
## How to Run

Set username and password environment variables if needed so you don't need to enter secrets in plain text.
Set the API key and run the script.

```powershell
$env:OPENAI_API_KEY="sk-..."
python .\vision_playwright_openai_vision_poc.py `
  --prompt "Log in with username 'demo' and password 'demo123'.`n1. Fill in the username field`n2. Fill in the password field`n3. Click Log in" `
  --success-criteria "You are on the Home page and see 'Welcome, demo'." `
  --start-url "http://127.0.0.1:8000/index.html" `
  --actions "login_flow" `
  --max-tokens 192 --max-steps 20 --keep-last-turns 3 --keep-last-images 0 `
  --site-hints-path "site_hints.json" `
  --verbose
```

### Run Local Test Site

From the repo root, start the local static site used by smoke tests:

```powershell
python -m http.server 8000 --directory test-site
```

Then open:
- `http://127.0.0.1:8000/index.html` (login page)
- `http://127.0.0.1:8000/home.html` (home page)
- `http://127.0.0.1:8000/profile.html` (profile page, when present)
- `http://127.0.0.1:8000/register.html` (register page, when present)

Stop the server with `Ctrl+C` in the same terminal.

### Developer Local Validation

Before pushing, developers can run both a manual pre-commit check and the local smoke sequence used by CI.

Cross-platform quality suites:

```powershell
python ./precommit_smoketest.py
python ./release_test.py
# Repeat any target command/script N times and report pass/fail consistency.
python ./tools/consistency.py ./precommit_smoketest.py 10
```

Manual pre-commit hook (from repo root):

```powershell
git config core.hooksPath .githooks
if (Test-Path .\.githooks\pre-commit) { bash .\.githooks\pre-commit } else { Write-Host "No .githooks/pre-commit found." }
```

Optional: run the GitHub-Action-equivalent login smoke sequence during pre-commit (requires `OPENAI_API_KEY`):

```powershell
$env:AGENTICWEBQA_PRECOMMIT_GHA_SMOKE="1"
```

One-command local login smoke sequence (learn -> auto-heal -> reuse):

```powershell
$env:OPENAI_API_KEY="sk-..."; python ./webtests/run_testlogin_local.py --skip-install
```

One-command local register integration smoke sequence (register -> logout -> re-login):

```powershell
$env:OPENAI_API_KEY="sk-..."; python ./webtests/run_testregister_local.py --skip-install
```

Register smoke auto-skips when the Register feature is not yet present in `test-site`. To require the feature and fail if missing, pass `--require-feature`.

One-command local profile navigation smoke sequence (login -> profile -> home):

```powershell
$env:OPENAI_API_KEY="sk-..."; python ./webtests/run_testprofilepage_local.py --skip-install
```

Profile smoke auto-skips when the Profile feature is not yet present in `test-site`. To require the feature and fail if missing, pass `--require-feature`.

One-command local profile location smoke sequence (country/state visibility + persistence + state wipe):

```powershell
$env:OPENAI_API_KEY="sk-..."; python ./webtests/run_testprofilelocation_local.py --skip-install
```

Profile location smoke auto-skips when the location controls are not yet present in `test-site`. To require the feature and fail if missing, pass `--require-feature`.

One-command local home quiz smoke sequence (quiz completion + score states + next-quiz animation/replacement):

```powershell
$env:OPENAI_API_KEY="sk-..."; python ./webtests/run_testhomequiz_local.py --skip-install
```

Home quiz smoke auto-skips when quiz controls are not yet present in `test-site`. To require the feature and fail if missing, pass `--require-feature`.

Artifacts from local smoke runs are written under repo-root paths (`Models`, `agent_view`, `reuse_run.log`, `auto_heal_run.log`, `register_run.log`, `profilepage_run.log`, `profilelocation_run.log`, `homequiz_run.log`, and `site_hints.json`).

### UI Launcher (Recommended)

You can also run the Tkinter launcher:

```powershell
python .\vision_playwright_openai_vision_ui.py
```

In the UI:
- Choose your model from the dropdown (see "UI Model Selection (Dropdown)").
- Prefer `gpt-5.1` for training/learning runs.
- Run headed when you want to use manual click interjection.

## Key Files

- `vision_playwright_openai_vision_poc.py`: main agent implementation
- `vision_playwright_openai_vision_ui.py`: Tkinter GUI launcher
- `agent_view/`: per-step screenshots (pre/post/action previews)
- `site_hints.json`: per-site DOM hint map (auto-created)
