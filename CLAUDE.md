# AgenticWebQA — Claude Notes

## UI State / Test Configuration File

The GUI (vision_playwright_openai_vision_ui.py) persists all test tab configs to:

```
vision_playwright_openai_vision_ui.required.tmp
```

This file is the source of truth for prompts, success criteria, models, and actions for each named test. When syncing release_test.py or the webtests/ scripts, compare against this file.

### Current test tabs (as of last sync)

| Tab title        | Script                              | Model              | Actions                                                                  |
|------------------|-------------------------------------|--------------------|--------------------------------------------------------------------------|
| Login_demo       | run_testlogin_local.py              | claude-opus-4-6    | login_demo                                                               |
| Logout           | run_testlogout_local.py             | claude-haiku-4-5   | login_demo,logout                                                        |
| Register         | run_testregister_local.py           | claude-sonnet-4-6  | register_account                                                         |
| ProfileOpen      | run_testprofileopen_local.py        | claude-sonnet-4-6  | register_account,profile_open                                            |
| ProfileAboutEdit | run_testprofilepage_local.py        | claude-sonnet-4-6  | register_account,profile_open,profile_aboutedit                          |
| ProfileLocationCanada      | run_testprofilelocation_local.py    | claude-sonnet-4-6  | register_account,profile_open,profile_location_canada        |
| ProfileLocationUSCalifornia | run_testprofilelocationus_local.py  | claude-sonnet-4-6  | register_account,profile_open,profile_location_uscalifornia  |

### rand_string substitution

The GUI replaces `{rand_string}` at runtime. In standalone scripts this is generated as `str(int(time.time()))`. Affects:
- Register: username = `user_{rand_str}`, password = `pass1_{rand_str}`
- ProfileAboutEdit: about me text = `{rand_str}`

## release_test.py

Runs: unit tests → Login_demo → Logout → Register → ProfileOpen → ProfileAboutEdit → ProfileLocationCanada → ProfileLocationUSCalifornia

- Login_demo includes a learn → break-selectors → auto-heal → reuse cycle (selector relearn test)
- All other e2e tests are single-run flows
- Profile tests use `--require-feature` (skip gracefully if test-site lacks the feature)

## tvjpelletier_smoketest.py

Runs: Login → SearchForMovie → OpenMovieDetails → CheckForSubs against `https://tv.jpelletier.com/`

- All tests use `claude-sonnet-4-6` by default (overrides the opus-4-6 values in the .tmp file)
- Login is a learn → reuse cycle (run 1 builds the action, run 2 verifies no fallback)
- SearchForMovie, OpenMovieDetails, and CheckForSubs build on learned actions in sequence
- Credentials come from `WEBQA_USERNAME` / `WEBQA_PASSWORD` env vars

| Tab title        | Model             | Actions                              |
|------------------|-------------------|--------------------------------------|
| Login            | claude-sonnet-4-6 | login                                |
| SearchForMovie   | claude-sonnet-4-6 | login, search_movie                  |
| OpenMovieDetails | claude-sonnet-4-6 | login, search_movie, open_moviedetails |
| CheckForSubs     | claude-sonnet-4-6 | login, search_movie, open_moviedetails |

## Writing Tests

When asked to write, author, or generate a new test:
1. Read `.claude/commands/qa-test-authoring.md` before starting.
2. Run and verify tests by invoking the webtests script directly via the Bash tool.

## Test site

Static vanilla HTML/JS/CSS app in `test-site/`. No framework, no build step.
Serve with: `python -m http.server 8000 --directory test-site`
Credentials: `demo` / `demo123`
