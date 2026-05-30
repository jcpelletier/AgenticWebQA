---
description: "Set up CI/CD integration for AgenticWebQA tests. Use when asked to configure automated testing, set up GitHub Actions or other CI pipelines, wire up model persistence, or make tests run on every commit."
---

# QA CI Setup — Skill Reference

## Purpose
Configure a CI/CD pipeline that runs AgenticWebQA tests automatically on every
commit or pull request. This skill generates the appropriate workflow config for
the project's CI system, sets up model persistence, and explains the ongoing
model-drift workflow.

---

## When to invoke this skill

- "Set up CI for my tests"
- "Add this to my GitHub Actions / Jenkins / GitLab"
- "Make my tests run automatically"
- "How do I run these in CI?"
- After authoring tests, when the developer is ready to automate them

---

## Step 1 — Understand the project

Before generating anything, gather:

**CI system** — look for these files in the repo root:
- `.github/workflows/` → GitHub Actions
- `Jenkinsfile` → Jenkins
- `.gitlab-ci.yml` → GitLab CI
- `.circleci/config.yml` → CircleCI
- `azure-pipelines.yml` → Azure DevOps
- `bitbucket-pipelines.yml` → Bitbucket Pipelines

If none found, ask the user which system they use.

**Registered tests** — read `tests_registry.json` and collect all test names.
These become the individual test steps in the CI workflow.

If `tests_registry.json` does not exist yet, stop and tell the user to run
`agenticwebqa-init` (or use the `qa-test-authoring` skill to add a first test).
A CI workflow with no tests has nothing to run.

**App under test** — ask if not obvious:
- How is the app started? (`npm start`, `python manage.py runserver`, `./gradlew bootRun`, etc.)
- What port does it listen on?
- Does it need environment variables or a database to start?
- Is it already deployed somewhere, or must CI start it?

**API keys needed** — check which models are used across the registry. Determine
which secrets CI will need:
- OpenAI models → `OPENAI_API_KEY`
- Claude models → `ANTHROPIC_API_KEY`
- Gemini models → `GEMINI_API_KEY`

---

## Step 2 — Configure model tracking

Learned Playwright action models must be available to CI. They are not rebuilt
on every run — they replay deterministically and only re-learn when a UI change
breaks a selector.

**Check `.gitignore`** for a `Models/` exclusion and remove it:
```
# Before:
/Models/

# After: (remove the line entirely, or add a comment)
# Models/ is intentionally tracked — learned Playwright actions are source artifacts.
```

**Ensure `Models/` exists** in the repo (create it with a `.gitkeep` if empty).

**Check `docker-compose.yml`** if present — the `qa` service should mount
`./Models` as a bind mount, not a named volume:
```yaml
volumes:
  - ./Models:/workspace/Models    # bind-mounted so models are tracked in git
```

Tell the user:
> "After authoring and verifying your tests locally, commit both
> `tests_registry.json` and `Models/` to your repo. CI will replay the learned
> actions deterministically without making LLM calls."

---

## Step 3 — Generate the CI workflow

Use the appropriate template below. Fill in:
- `{TEST_LIST}` — one step per entry in `tests_registry.json`
- `{APP_START_COMMAND}` — how to start the app under test
- `{APP_PORT}` — the port the app listens on
- `{API_KEY_SECRETS}` — the env blocks for each required key
- `{PYTHON_VERSION}` — default `"3.11"`

### GitHub Actions

Create `.github/workflows/qa.yml`:

```yaml
name: QA Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

jobs:
  qa:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "{PYTHON_VERSION}"
          cache: pip

      - name: Install agenticwebqa
        run: pip install agenticwebqa

      - name: Install Playwright Chromium
        run: playwright install chromium --with-deps

      - name: Restore learned models
        uses: actions/cache@v4
        with:
          path: Models/
          key: agentqa-models-${{ hashFiles('tests_registry.json') }}
          restore-keys: agentqa-models-

      - name: Start app under test
        run: |
          {APP_START_COMMAND} &
          timeout 30 bash -c \
            'until curl -sf http://127.0.0.1:{APP_PORT}/ > /dev/null; do sleep 0.5; done'

      # Snapshot model state AFTER cache restore, BEFORE tests run.
      # We diff against this snapshot — not git HEAD — so a PR is only opened
      # when THIS run re-learned something.  Without the snapshot, cached models
      # that are newer than the repo would trigger a false PR every run.
      - name: Snapshot models before tests
        run: |
          if [ -d Models ]; then
            cp -r Models .models-snapshot
          else
            mkdir -p .models-snapshot
          fi

      {TEST_STEPS}

      # If this run changed any model file, open a draft PR so a developer
      # can review the selector diff and hit merge to accept the update.
      # Targets the current branch so the PR always flows back to wherever
      # the triggering code lives — a feature branch or main.
      - name: Propose model updates if actions changed
        if: always()
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          if ! diff -rq .models-snapshot Models/ > /dev/null 2>&1; then
            BRANCH="model-update/run-${{ github.run_number }}"
            git config user.name  "github-actions[bot]"
            git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
            git checkout -b "$BRANCH"
            git add Models/
            git commit -m "chore: update learned action models [skip ci]

            Playwright actions re-learned during CI run ${{ github.run_id }}.
            Tests passed — review the Models/ diff and merge to accept."
            git push origin "$BRANCH"
            gh pr create \
              --title "chore: update learned action models" \
              --body "## What happened

          One or more Playwright action models were re-learned during [run ${{ github.run_id }}](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}).

          The tests **passed** — the engine detected a broken selector, fell back to the LLM, rewrote the action steps, and the test succeeded with the new selectors.

          ## What to do

          Review the \`Models/\` diff in this PR. The changes are JSON selector sequences. Look for CSS selector or step-order changes that match your recent UI work. If they look correct, **merge this PR** to keep the updated actions in source control.

          If the changes look unexpected, investigate before merging — a selector change you didn't intend may indicate a regression." \
              --base "${{ github.ref_name }}" \
              --draft
          fi
```

Each test becomes a step:
```yaml
      - name: Test — {test_name}
        env:
          {API_KEY_SECRETS}
        run: agenticwebqa-run-test {test_name}
```

**Note on test ordering:** if any test uses a pre-warmed model from an earlier
test (e.g. `profile_all_fields` depends on `login_demo` having run first), list
the prerequisite test first. Check `tests_registry.json` — a test whose
`actions` field begins with another test's action name is a dependant.

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
qa:
  image: python:3.11-slim
  stage: test
  variables:
    TEST_SITE_URL: http://127.0.0.1:{APP_PORT}
  cache:
    key:
      files: [tests_registry.json]
    paths: [Models/]
  before_script:
    - pip install agenticwebqa
    - playwright install chromium --with-deps
    - {APP_START_COMMAND} &
    - sleep 5
  script:
    {TEST_SCRIPT_LINES}
  artifacts:
    paths: [Models/]
    when: always
```

### Jenkins (declarative pipeline)

```groovy
pipeline {
  agent { label 'ubuntu' }
  stages {
    stage('Setup') {
      steps {
        sh 'pip install agenticwebqa'
        sh 'playwright install chromium --with-deps'
      }
    }
    stage('Start app') {
      steps {
        sh '{APP_START_COMMAND} &'
        sh 'sleep 10'
      }
    }
    stage('QA Tests') {
      environment {
        OPENAI_API_KEY  = credentials('openai-api-key')
        // add other keys as needed
      }
      steps {
        {TEST_STEPS_GROOVY}
      }
    }
  }
  post {
    always {
      archiveArtifacts artifacts: 'Models/**', allowEmptyArchive: true
    }
  }
}
```

### CircleCI

```yaml
version: 2.1
jobs:
  qa:
    docker:
      - image: python:3.11-slim
    steps:
      - checkout
      - restore_cache:
          keys: [agentqa-models-{{ checksum "tests_registry.json" }}]
      - run:
          name: Install
          command: |
            pip install agenticwebqa
            playwright install chromium --with-deps
      - run:
          name: Start app
          command: {APP_START_COMMAND}
          background: true
      {TEST_STEPS_CIRCLE}
      - save_cache:
          key: agentqa-models-{{ checksum "tests_registry.json" }}
          paths: [Models/]
      - store_artifacts:
          path: Models/
workflows:
  qa:
    jobs: [qa]
```

---

## Step 4 — Secrets setup

After generating the config, tell the user exactly which secrets to add:

### GitHub Actions
> Go to **Settings → Secrets and variables → Actions → New repository secret**:
> - `OPENAI_API_KEY` (if using any OpenAI model)
> - `ANTHROPIC_API_KEY` (if using any Claude model)
> - `GEMINI_API_KEY` (if using any Gemini model)
>
> `GITHUB_TOKEN` is provided automatically — no setup needed.

### GitLab
> Go to **Settings → CI/CD → Variables**. Mark each as Protected + Masked.

### Jenkins
> Add credentials of type "Secret text" in **Manage Jenkins → Credentials**.
> Reference them via `credentials('credential-id')` in the pipeline.

---

## Step 5 — Model drift workflow

Explain this to the user once setup is complete:

**Normal CI run (no UI changes):**
- Models exist in repo → Playwright replays them deterministically → no LLM calls → fast and cheap.

**After a UI change that breaks a selector:**
- Playwright step fails → engine falls back to LLM → re-learns the action → test PASSES → model file updated.
- On GitHub Actions: a draft PR is automatically opened with the `Models/` diff.
- On other systems: updated models are in the CI artifact — download and commit them.

**Developer action when a model-update PR appears:**
1. Review the `Models/` diff — it shows changed CSS selectors or step sequences.
2. If the changes match the intended UI update, merge the PR.
3. If unexpected, investigate whether the UI change was intentional.

**Re-learning everything from scratch** (e.g. after a major UI redesign):
```bash
rm -rf Models/
# Re-run each registered test to re-learn its actions:
agenticwebqa-run-test <test-name>
# Then commit the regenerated Models/
git add Models/ && git commit -m "chore: regen action models after redesign"
```

---

## Step 6 — Validate

Before closing:

1. Confirm `Models/` is no longer in `.gitignore`.
2. Confirm at least one `Models/*.json` file exists (learned during local authoring).
3. Confirm the API key secret name in the workflow matches what the user will
   add to their CI system.
4. Offer to do a dry-run: `agenticwebqa-run-test <first_test>` locally
   to verify the test still works before the first CI push.

---

## Checklist

- [ ] CI system detected / confirmed
- [ ] Workflow file created with all registered tests as steps
- [ ] `Models/` removed from `.gitignore`
- [ ] `Models/` directory exists and has content (committed)
- [ ] User knows which API key secrets to add
- [ ] Model-drift handling explained (auto-PR or manual artifact sync)
- [ ] User knows the difference between a test failure and a model-update event
