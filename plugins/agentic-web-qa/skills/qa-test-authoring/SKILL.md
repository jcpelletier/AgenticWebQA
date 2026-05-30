---
description: "Author, run, and validate AgenticWebQA browser tests. Use when asked to write, create, generate, or debug a web automation/e2e test."
---

# QA Test Authoring — Skill Reference

## Purpose
This document tells Claude how to author, run, and validate new AgenticWebQA
tests. Read this before writing any test.

---

## When a developer asks for a test

1. Check `tests_registry.json` to see whether a test for this feature already exists.
2. If it exists, run it:
   - Via MCP tool: `agenticwebqa:run_test(name="<test_name>")`
   - Or CLI: `python -m agenticwebqa --start-url <url> --prompt "..." --visual-llm-success "..." --headless --verbose`
3. If it does not exist, follow the **authoring loop** below.

---

## Running tests

### Via the MCP tool (recommended for Claude)
```
agenticwebqa:run_test(name="<test_name>")
agenticwebqa:run_test(name="<test_name>", model="gpt-4o-mini")
agenticwebqa:run_test(name="<test_name>", headless=False)
```

For ad-hoc (not yet registered) tests:
```
agenticwebqa:run_test(
    prompt="...",
    start_url="https://your-app/",
    success_criteria="...",
    success_type="visual",
    model="gpt-4o-mini"
)
```

### Via CLI
```bash
python -m agenticwebqa \
    --start-url "https://your-app/" \
    --prompt "..." \
    --visual-llm-success "..." \
    --max-steps 20 \
    --headless \
    --verbose \
    --model gpt-4o-mini
```

Replace `--visual-llm-success` with `--text-present-success`, `--selector-present-success`,
or `--url-match-success` depending on the success type.

### Learn → reuse cycle
The engine learns Playwright actions on first run and replays them on subsequent
runs. To test this:
1. **Run 1 (learn)**: engine falls back to LLM, saves actions to the model file.
2. **Run 2 (verify no fallback)**: engine replays saved actions; fail if
   `[playwright] Falling back to LLM.` appears — that means the saved actions
   didn't replay cleanly.

Wipe learned artifacts before a fresh learn cycle:
```bash
python -m agenticwebqa --start-url <url> --wipe-models
```

---

## Authoring loop

### Step 1 — Design the spec

**Prompt** — imperative, numbered steps the agent will follow.
- Start from the beginning of the user journey (register or login if needed).
- One action per line. Be specific about UI labels.
- Use template variables (see below) wherever dynamic values are needed.

**Template variables** — substituted at runtime in both the prompt and success
criteria. Unknown `{keys}` are left as-is.

| Variable | What it resolves to |
|---|---|
| `{rand_string}` | 5 random lowercase letters, fixed for the run (e.g. `xkbqy`) |
| `{date}` | Today's date as `YYYY-MM-DD` (e.g. `2026-05-29`) |
| `{epoch}` | Unix timestamp in seconds (e.g. `1748518800`) |
| `{username}` | Auth username from `WEBQA_USERNAME` env var, or extracted from prompt |
| `{password}` | Auth password from `WEBQA_PASSWORD` env var (redacted in logs) |
| `{query}` | The first single-quoted value in the prompt (see below) |

**Single-quoted values in prompts** — write a specific value in single quotes
(e.g. `"Search for 'The Matrix'"`) to mark it as a *parameterised query*.
The engine extracts `The Matrix` as `{query}` and stores it as a placeholder in
learned Playwright actions. On subsequent runs the saved action substitutes in
whatever the current prompt's single-quoted value is, making the action reusable
across different searches or inputs.

**Single-quoted values in success criteria** — wrapping a variable in single
quotes (e.g. `"The page shows '{rand_string}' in the About me field"`) signals
to the visual verifier that the value was generated dynamically and is expected
to change between runs. The verifier matches the substituted value it actually
sees on screen against the current run's substituted value.

**Success criteria** — one sentence describing what must be *visible* for the
test to pass. Written as an observation.
- Good: `"The Profile page shows '{rand_string}' in the About me field."`
- Good: `"The home page shows 'Welcome, user_{rand_string}' as the fallback after display name was cleared."`
- Bad: `"The save worked."` / `"profile.name == rand_string"`

**Success criteria design rules:**
1. The criteria must be FALSE at the start of the test (otherwise it fires
   immediately and the action is never learned). Watch out for two common traps:
   - `text` success type on a `<textarea>` fires as soon as the agent *types*
     the value — before Save or any persistence check runs.
   - `text` or `visual` criteria that describe a default page state (e.g.
     "No posts yet." on an empty feed) fire right after login, before the test
     actions run.
   Fix: anchor the criteria to a state that can only exist *after the last
   meaningful action* — for example, check a home-page welcome text that
   reflects a saved display name, rather than a form field value in-progress.
2. The criteria should be checkable from the *current viewport* without extra
   scrolling — prefer verifying elements near the top of the page, or switch
   to `success_type: "text"` for content in `<p>` / `<div>` / `<span>` elements.
3. Avoid verifying values stored only in `<input>` or `<select>` elements with
   `text` success type — `page.innerText` does not include form field values.
   Use `visual` instead, or navigate to a page that displays them as readable
   text (e.g. a profile display name showing on the home page).
4. Prefer **navigate-away-and-back** over page reload (F5/Ctrl+R) for
   persistence checks — navigation resets scroll to the top of the page, while
   reload may preserve a deep scroll position inside a long form.

**Actions** — comma-separated snake_case names. Each name is an atomic reusable
unit. Reuse existing actions as prefixes rather than creating new ones
(e.g. `login,profile_open,my_new_action`, not `my_new_login`).

**Model recommendations:**

| Use case | Recommended model |
|---|---|
| General use | `gpt-5.4-mini` or `claude-sonnet-4-6` |
| Complex multi-step / long forms | `gpt-5.4` or `claude-opus-4-6` |
| Heavy reasoning / highest quality | `gpt-5.5` or `claude-opus-4-7` |
| Cheap baseline / smoke tests | `gpt-5.4-nano` (current gen) or `gpt-4o-mini` (legacy, cheapest) |

### Step 2 — Add to `tests_registry.json`

Add the spec directly to `tests_registry.json`:
```json
{
  "my_feature": {
    "prompt": "1. Navigate to ...\n2. Click ...",
    "success_criteria": "The page shows the expected result.",
    "start_url": "https://your-app/",
    "actions": "login_demo,my_feature",
    "model": "gpt-5.4-mini",
    "success_type": "visual"
  }
}
```

Optional fields:

| Field | Default | Purpose |
|---|---|---|
| `success_type` | `"visual"` | `"visual"` \| `"text"` \| `"selector"` \| `"url"` |
| `max_subactions` | `5` | Max steps per learned action chunk. Raise to `8`–`10` for complex flows with many form fields or navigation steps. If you see `action_name_2`, `action_name_3` duplicates in the model file, the default cap is too low. |

### Step 3 — Run and evaluate

Ensure your app under test is reachable, then run the test:
```
agenticwebqa:run_test(name="my_feature")
```

Expected outcome on a healthy feature:
- `FINAL: PASS` — success criteria confirmed by the LLM.
- Learned actions saved for replay on subsequent runs.

To verify the replay (run 2 must not fall back):
```
agenticwebqa:run_test(name="my_feature")   # second call replays saved actions
```

If `[playwright] Falling back to LLM.` appears in the second run's log, see
**Run 2 fallback policy** below.

#### Run 2 fallback policy

**Run 2 must not fall back.** A fallback in run 2 means the saved actions
did not replay correctly — this is a test-authoring defect, not a feature
defect.

If run 2 falls back:

1. **Check the log** — find the step that triggered the fallback. Look for
   `[playwright] Falling back to LLM.` and the step just before it.

2. **Try to resolve** — common causes and fixes:

   | Cause | Fix |
   |---|---|
   | Action split at a page-navigation boundary | Add a pre-navigation test case so the target action starts on the correct page |
   | Action saved as a no-op (`task already satisfied, no interactive steps recorded`) | Criteria fires before the action runs — redesign so criteria is FALSE until the very last step (see design rules above) |
   | Duplicate function names in model (`action_2`, `action_3`) | The `max_subactions` cap is too low for the flow length. Add `"max_subactions": 8` (or higher) to the registry entry |
   | First step of a replayed action is the wrong page action (e.g. clicks register-link from inside a profile flow) | Multiple new actions were learned in a single LLM session and their steps were mis-distributed. Fix: ensure prerequisite actions (e.g. `login_demo`) already exist in the model before the learn run so only one new action is learned per session |
   | Selector changed between runs | Re-run the learn cycle; inspect which selector the model saved |

3. **Iterate** — after each fix, wipe and re-run from scratch.
   Allow up to **3 attempts** to resolve a run-2 fallback.

4. **Escalate** — if run 2 still falls back after 3 fixes, stop and report
   to the user:

   > "Run 2 continues to fall back after 3 attempts. The last failure was at
   > [step description]. I've tried [fixes tried]. I need guidance on whether
   > to restructure the action boundaries, adjust the prompt, or accept this
   > as a known limitation."

Do not keep retrying the same approach — each attempt must change something
(prompt wording, action split, success criteria, or step count).

#### Accepting LLM-always behaviour

Some tests are inherently LLM-driven on every run and that is **acceptable**.
Do not spend time trying to force deterministic replay for:

- **Randomly-generated UI content** (e.g. a quiz that picks from 20 random
  variants per page load) — saved click positions will never match the next
  variant.
- **Tests where the success criteria references dynamic content** (e.g.
  `{rand_string}` in the About me field) — the engine re-substitutes the
  variable on replay, but saved typed text may diverge across runs until the
  model stabilises over 2–3 runs.
- **Flows that are too long to fit in a single action chunk** even with a high
  `max_subactions` — these stabilise gradually as each replay run overwrites
  no-op stubs with real steps.

The distinction that matters is not *deterministic vs LLM* but
*reliably passes vs flaky*. A test that uses LLM on every replay but passes
100% of the time is production-ready. A test that sometimes replays
deterministically but fails 30% of the time is not.

### Step 4 — Commit the spec and models

Commit both files together — they are a matched pair:
```bash
git add tests_registry.json Models/
git commit -m "test: add <feature> smoke test"
```

The `Models/*.json` files are the learned Playwright action sequences. CI will
replay them deterministically without making LLM calls. If `Models/` is in
`.gitignore`, remove that exclusion — these are source artifacts, not build
outputs.

Update any release or precommit suite your project uses if this test should be
part of those runs.

### Step 5 — Wire up CI (if not already done)

If the project does not yet have a CI workflow that runs AgenticWebQA tests,
invoke `the qa-ci-setup skill`. It will:
- Detect your CI system (GitHub Actions, GitLab, Jenkins, etc.)
- Generate the appropriate workflow config with all registered tests as steps
- Configure model caching so CI replays deterministically
- Set up the model-drift PR bot so updated selectors flow back to source control

---

## Retry guidance (when FAIL)

Read the log tail returned by `agenticwebqa:run_test` (field: `log_tail`), or
the full log at the path in `log_path`. Look for:
- `=== STEP N ===` — which step failed
- `criteria_visible: NO` — agent reached the step but the goal wasn't met
- `action` / `args` JSON — what the agent tried

Common failure causes and fixes:

| Symptom | Fix |
|---|---|
| Agent clicks wrong element | Be more specific about the UI label in the prompt |
| Criteria not met after all steps | Tighten success criteria or add a reload/wait step |
| Agent loops without progress | The feature may be broken — escalate |
| `Missing ANTHROPIC_API_KEY` / `Missing OPENAI_API_KEY` | Set the env var |
| Page not reachable | Start your app under test |

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

- snake_case, single responsibility: `login`, `register_account`, `profile_open`
- Chained flows list prerequisites first: `register_account,profile_open,profile_aboutedit`
- Do not encode the site URL in the action name
- Do not create `login2`, `login_v2` — fix the existing action instead
