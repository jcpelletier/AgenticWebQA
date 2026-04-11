# Register Account (TDD)

## Summary
Add a simple, non-production account registration capability to the local `test-site` so AgenticWebQA can test:
- account creation
- logout
- login with the newly registered account

This feature is intentionally lightweight and local-only (no backend, no captcha, no email verification, no security hardening).

## Goals
- Allow a user to register with `username` + `password`.
- Block duplicate usernames.
- Auto-login the user after successful registration and land on the existing Home screen.
- Keep existing demo account (`demo` / `demo123`) available by default.
- Ensure newly registered accounts work with normal login flow.
- Keep logout available and verified in tests.

## Non-Goals
- Production-grade auth/security.
- Password hashing/encryption.
- Backend API/database integration.
- MFA, email verification, captcha, recovery flows.

## Linear Checklist
- [x] Add "Create account" navigation on `test-site/index.html` (`data-testid="register-link"`) that opens `register.html`.
- [x] Add `test-site/register.html` with required `username` and `password` fields, Register submit, Back to login control, and `register-error` banner (`role="alert"`).
- [x] Add/confirm stable register test IDs in markup: `register-form`, `register-username`, `register-password`, `register-button`, `register-error`, `back-to-login`.
- [x] Add account store helpers in `test-site/app.js` for `localStorage` key `accounts_v1` (load/init/save/find).
- [x] Seed store with checked-in default account (`demo` / `demo123`) when `accounts_v1` is absent.
- [x] Refactor login in `test-site/app.js` to authenticate against stored accounts (case-insensitive username, exact password match).
- [x] Implement registration validation in `test-site/app.js`:
: username required, trimmed, length `3-24`, chars `[A-Za-z0-9_-]`; password required, min `8`, includes letter+number.
- [x] Implement duplicate username prevention (case-insensitive) and show explicit duplicate error message.
- [x] On successful registration, persist account, set `auth_user`, and redirect to `home.html`.
- [x] Confirm existing Home/logout behavior still works: `Welcome, <username>`, logout clears `auth_user`, redirect to `index.html`.
- [x] Add `run_testregister_local.py` for integration scenario: register -> logout -> re-login.
- [x] Add register feature detection in `run_testregister_local.py` so the script auto-skips when Register UI is not yet present.
- [x] Keep feature smoke entrypoint Python-only via `run_testregister_local.py` and support `--skip-install` / `--require-feature`.
- [x] Keep login smoke in `run_testlogin_local.py` unchanged for learn -> auto-heal -> reuse.
- [x] Update `precommit_smoketest.ps1` to execute both smoke scripts (`run_testlogin_local.py`, `run_testregister_local.py`).
- [x] Add generated register smoke artifact to ignore rules (`register_run.log` in `.gitignore`).
- [ ] Run register smoke with `--require-feature` after implementation and confirm PASS for:
: registration happy path, logout, and login with newly registered account.
- [ ] Run full smoke validation (login smoke + register smoke) and verify no regressions.
- [x] Update docs that changed (`README.md`, this TDD file, and `docs/Structure.MD` if runtime/test flow changed).
- [ ] Confirm all Acceptance Criteria below are satisfied and check off completion.

## UX Workflow

### Entry Point
- On `index.html` (login page), add a clear "Create account" control that opens `register.html`.

### Registration Page
- Fields:
  - `username` (required)
  - `password` (required)
- Primary action:
  - `Register`
- Secondary action:
  - `Back to login`

### Validation (chosen defaults)
- Username:
  - required
  - trimmed
  - length `3-24`
  - characters: letters, numbers, `_`, `-`
- Password:
  - required
  - minimum length `8`
  - at least one letter and one number
- Duplicate usernames:
  - not allowed
  - duplicate check is case-insensitive

### Error UX
- Show an inline form-level error banner (role `alert`) for failures.
- Keep message brief and explicit, for example:
  - `Username already exists.`
  - `Username must be 3-24 characters and contain only letters, numbers, _ or -.`
  - `Password must be at least 8 characters and include a letter and a number.`

### Success UX
- On successful registration:
  - create account
  - set `auth_user`
  - redirect to `home.html`
- Home page must show the same post-login UX as normal login (`Welcome, <username>`).

### Logout
- Keep existing logout behavior on Home:
  - clear `auth_user`
  - redirect to `index.html`

## Technical Design

## Storage Model (Local)
- Use `localStorage` key: `accounts_v1`.
- Keep `auth_user` for session identity (already used).
- Seed account list with checked-in default account:
  - username: `demo`
  - password: `demo123`

Proposed shape:

```json
{
  "accounts": [
    { "username": "demo", "password": "demo123" },
    { "username": "regdemo_123", "password": "regdemo123" }
  ]
}
```

Notes:
- On load, if `accounts_v1` does not exist, initialize with seeded account.
- Keep username lookup case-insensitive for duplicate checking and login matching.

## Site File Changes
- `test-site/index.html`
  - add register entry control (link/button) with stable test id.
- `test-site/register.html` (new)
  - registration form and error container.
- `test-site/app.js`
  - centralize account store load/save helpers
  - login against local account store (not just hardcoded constants)
  - registration handler with validation and duplicate checks
  - keep/extend logout behavior
- `test-site/styles.css`
  - reuse existing card/form styles for register screen and error banner.

## Suggested Test IDs
- Login page:
  - `register-link`
- Register page:
  - `register-form`
  - `register-username`
  - `register-password`
  - `register-button`
  - `register-error`
  - `back-to-login`
- Existing home/logout test ids remain:
  - `home-title`
  - `welcome-text`
  - `logout-button`

## Testing Plan (AgenticWebQA-Driven)

## Existing Smoke Coverage (keep)
- Login learn/auto-heal/reuse flow with demo account.

## New Integration Scenarios
- Registration happy path:
  - Register new username/password.
  - Confirm Home and welcome text for new username.
- Logout:
  - Click logout from Home.
  - Confirm return to login page.
- Login with newly registered account:
  - Login using same just-registered credentials.
  - Confirm Home and same welcome text.

## Smoke Script Changes
- Keep existing login smoke flow unchanged in `run_testlogin_local.py`.
- Add new register smoke flow in `run_testregister_local.py`:
  - register -> logout -> re-login
- Add feature detection so register integration tests auto-skip until Register UI exists.
- Keep smoke scripts Python-only (no `.ps1` wrappers).
- Update `precommit_smoketest.ps1` to call both Python smoke scripts.

## Suggested Agent Prompt (for integration scenario)
`Register a new account, verify Home, log out, then log in with the same account and verify Home again.`

## Acceptance Criteria
- Register flow creates account and blocks duplicates.
- Successful register lands on Home as authenticated user.
- Logout returns to login page and clears authenticated state.
- Newly registered user can log in again via standard login flow.
- Agentic smoke script includes register/logout/re-login integration coverage.
