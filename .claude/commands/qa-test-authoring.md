# QA Test Authoring — Skill Reference

## Purpose
This document tells Claude how to author, run, and validate new AgenticWebQA
tests. Read this before writing any test.

---

## When a developer asks for a test

1. Check `tests_registry.json` to see whether a test for this feature already exists.
2. If it exists, run it with `python webtests/run_test{name}_local.py --skip-install`.
3. If it does not exist, follow the **authoring loop** below.

---

## Script structure

All webtests scripts follow the same pattern. Use `webtests/run_testdisplayname_local.py`
as the canonical template. Key elements:

### Constants
```python
START_URL = "http://127.0.0.1:8000/index.html"
SITE_HINTS_KEY = "127.0.0.1"
SITE_MODEL_FILE = "http_127_0_0_1_8000_index_html.json"
LOG_NAME = "myfeature_run.log"
DEFAULT_MODEL = "claude-sonnet-4-6"
FALLBACK_PATTERN = "[playwright] Falling back to LLM."
```

For external sites (not localhost), set these to match the target URL.
`SITE_MODEL_FILE` is derived from the URL: scheme + host + path with
`/`, `.`, `:` replaced by `_`.

### TEST_CASES
A list of tuples: `(title, prompt, success_criteria, actions, model)`.
One entry per logical test flow.

### `wipe_site_artifacts(repo_root)`
Deletes the model file and removes the site's key from `site_hints.json`.
Always include this. Provide `--no-wipe` to skip it when debugging.

### `run_test(...)`
Calls `vision_playwright_openai_vision_poc.py` with the spec. Use:
- `--max-steps 25` for flows with 8–12 user steps
- `--max-subactions-per-function 5`
- `--headless --verbose`

### `main()` — wipe → learn → reuse loop
```
wipe_site_artifacts()          # clean slate
for each test case:
    run 1 (learn)              # LLM fallback allowed; actions saved to model
    run 2 (verify no fallback) # replay saved actions; fail if FALLBACK_PATTERN seen
```
Run 2 reads only its portion of the log (from the byte offset after run 1)
to check for fallback. See `tvjpelletier_smoketest.py` for the pattern.

---

## Authoring loop

### Step 1 — Design the spec

**Prompt** — imperative, numbered steps the agent will follow.
- Start from the beginning of the user journey (register or login if needed).
- One action per line. Be specific about UI labels.
- Use `{rand_string}` anywhere a unique value is needed.

**Success criteria** — one sentence describing what must be *visible* for the
test to pass. Written as an observation.
- Good: `"The home page shows 'Welcome, user_{rand_string}' as the fallback after display name was cleared."`
- Bad: `"The save worked."` / `"profile.name == rand_string"`

**Actions** — comma-separated snake_case names. Each name is an atomic reusable
unit. Reuse existing actions as prefixes rather than creating new ones
(e.g. `register_account,profile_open,my_new_action`, not `my_new_login`).

**Model** — `claude-sonnet-4-6` unless the task needs extra reasoning
(`claude-opus-4-6`) or is simple enough to be cheap (`claude-haiku-4-5`).

### Step 2 — Create the script

Copy `webtests/run_testdisplayname_local.py` and update:
- `START_URL`, `SITE_HINTS_KEY`, `SITE_MODEL_FILE`, `LOG_NAME`
- `TEST_CASES` entries
- Feature detection function (or remove it if not needed)

### Step 3 — Run and evaluate

Ensure the test server is running (for local tests):
```
python -m http.server 8000 --directory test-site
```

Run the script:
```
python webtests/run_test{name}_local.py --skip-install
```

Expected outcome on a healthy feature:
- Run 1: `PASS run 1: {title}` — actions learned
- Run 2: `PASS run 2 (no fallback): {title}` — actions replayed without LLM

#### Run 2 fallback policy

**Run 2 must not fall back.** A fallback in run 2 means the saved actions
did not replay correctly — this is a test-authoring defect, not a feature
defect.

If run 2 falls back:

1. **Check the log** — find the step that triggered the fallback. Look for
   the `FALLBACK_PATTERN` line and the step just before it.

2. **Try to resolve** — common causes and fixes:

   | Cause | Fix |
   |---|---|
   | Action split at a page-navigation boundary | Add a pre-login test case (separate `TEST_CASES` entry) so the target action starts on the correct page |
   | Action saved as a no-op (success criteria already satisfied on load) | Change success criteria to require visible evidence of the *new* action (not the page's default state) |
   | Action steps truncated (>5 steps saved per chunk) | Simplify the flow to ≤5 steps per action; split into multiple actions if needed |
   | Selector changed between runs | Add `--no-wipe` and re-inspect which selector the model saved |

3. **Iterate** — after each fix, re-run from scratch (without `--no-wipe`).
   Allow up to **3 attempts** to resolve a run-2 fallback.

4. **Escalate** — if run 2 still falls back after 3 fixes, stop and report
   to the user:

   > "Run 2 continues to fall back after 3 attempts. The last failure was at
   > [step description]. I've tried [fixes tried]. I need guidance on whether
   > to restructure the action boundaries, adjust the prompt, or accept this
   > as a known limitation."

Do not keep retrying the same approach — each attempt must change something
(prompt wording, action split, success criteria, or step count).

### Step 4 — Commit the spec

Add the spec to `tests_registry.json`. Update `CLAUDE.md` if the new test
should be part of the release test sequence.

---

## Retry guidance (when FAIL)

Read the log. Look for:
- `=== STEP N ===` — which step failed
- `criteria_visible: NO` — agent reached the step but the goal wasn't met
- `action` / `args` JSON — what the agent tried

Common failure causes and fixes:

| Symptom | Fix |
|---|---|
| Agent clicks wrong element | Be more specific about the UI label in the prompt |
| Criteria not met after all steps | Tighten success criteria or add a reload/wait step |
| Agent loops without progress | The feature may be broken — escalate |
| `Missing ANTHROPIC_API_KEY` | Set the env var |
| Page not reachable | Start the local test server |

**Maximum retries: 3.** After 3 consecutive FAIL results at the same step,
escalate to the user — do not keep retrying.

---

## Escalation

Stop retrying and report when:
- The test fails 3 times at the **same step** with the same failure mode.
- The agent reaches the step but the UI does not respond as expected.
- The log shows the agent uncertain whether the UI element exists.

> "I've attempted this test 3 times and it consistently fails at [step].
> The agent [description]. This may indicate [feature] is not working correctly.
> Do you want to investigate the feature, or should I try a different approach?"

---

## Action naming conventions

- snake_case, single responsibility: `login_demo`, `register_account`, `profile_open`
- Chained flows list prerequisites first: `register_account,profile_open,profile_aboutedit`
- Do not encode the site URL in the action name
- Do not create `login2`, `login_v2` — fix the existing action instead
