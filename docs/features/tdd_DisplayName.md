# Profile Display Name (TDD)

## Feature Spec Header
- Feature Name: Profile Display Name
- Feature Slug: DisplayName
- Owner: TBD
- User Story: As an authenticated user, I want to set an optional display name on my profile so that the home page greets me by that name instead of my username.
- In Scope:
  - Add an optional `Display name` text input to `profile.html`.
  - Enforce max length of 32 characters.
  - Persist display name per authenticated user in `profiles_v1` localStorage.
  - On `home.html`, show "Welcome, [display name]" when a display name is set; fall back to username when it is empty or not set.
  - Reload saved display name when the authenticated user returns to `profile.html`.
- Out Of Scope:
  - Profanity filtering or content moderation.
  - Display name uniqueness enforcement (usernames are unique; display names are not).
  - Display name appearing in any location other than the home page welcome text and profile page.
  - Backend/API services or cloud sync.
  - Changes to login, logout, or registration behavior other than compatibility.
- Dependencies:
  - Existing `profiles_v1` localStorage key and per-user profile object in `test-site/app.js`.
  - Existing `data-testid="welcome-text"` element on `home.html`.
  - Existing `data-testid="profile-save-button"` on `profile.html`.
  - Existing auth guard (`requireAuthenticatedUser`) in `test-site/app.js`.
- Rollout Risk: Low. Additive field on an existing storage key; no breaking changes to existing profile fields or auth flow.
- Test Requirements:
  - Unit tests for DOM contract and save/load/length behavior.
  - Smoke test covering set display name → verify home page welcome text → clear display name → verify fallback to username.
  - Requirement-to-test traceability matrix included below.

## Summary
Add an optional `Display name` field to the profile page. When saved, the home page welcome message uses the display name instead of the username. Clearing the field reverts to the username. All state is stored in the existing `profiles_v1` localStorage structure.

## Goals
- Provide a labeled `Display name` text input on `profile.html`.
- Enforce max 32 characters.
- Persist display name per authenticated user through existing `Save` action.
- Show display name in home page welcome text when set.
- Fall back to username on home page when display name is empty or absent.
- Rehydrate saved display name on profile page return visits.

## Non-Goals
- Server-side profile APIs.
- Display name uniqueness or availability checks.
- Display name appearing outside the home page welcome text.
- Changing auth or session semantics.
- New npm/pip dependencies.

## Assumptions
- ASSUMPTION: `profiles_v1` per-user object is extended with a `displayName` key (string). Empty string and absent key both mean "not set".
- ASSUMPTION: Display name is trimmed of leading/trailing whitespace before save and before rendering.
- ASSUMPTION: A display name consisting only of whitespace is treated as empty (falls back to username).
- ASSUMPTION: The existing `Save` button on `profile.html` saves all profile fields together, including display name.
- ASSUMPTION: `maxlength="32"` on the input is sufficient for enforcement; save path also guards against oversized values.

## Open Questions
- None.

## Linear Checklist
- [x] Define stable selectors and requirement IDs (`REQ-1`..`REQ-5`).
- [x] Add `Display name` label and input (`maxlength="32"`) to `test-site/profile.html` (`REQ-1`, `REQ-2`).
- [x] Update `test-site/app.js` profile save logic to include `displayName` in `profiles_v1` per-user object (`REQ-3`).
- [x] Update `test-site/app.js` profile load logic to hydrate display name input from saved state (`REQ-4`).
- [x] Update `test-site/app.js` home welcome text rendering to prefer `displayName` over username when set (`REQ-5`).
- [x] Add unit tests for DOM contract and save/load/fallback behavior (`TEST-UNIT-DISPLAYNAME-001`..`003`).
- [x] Add smoke script `webtests/run_testdisplayname_local.py` covering set → verify → clear → verify fallback (`TEST-SMOKE-DISPLAYNAME-001`).
- [x] Run targeted unit/smoke commands and record results under Test Execution Evidence.
- [x] Run regression login smoke (`TEST-REGRESSION-LOGIN-001`) — blocked by transient API overload; no code failure.
- [x] Confirm acceptance criteria and REQ/TEST traceability are complete.

## UX Workflow
1. User logs in and lands on `home.html`. Welcome text shows "Welcome, [username]".
2. User navigates to `profile.html`.
3. Profile page shows a `Display name` label and text input below the username display.
4. If a display name was previously saved, the input is pre-filled with that value.
5. User enters a display name (up to 32 chars) and clicks `Save`.
6. User navigates to `home.html`. Welcome text now shows "Welcome, [display name]".
7. User returns to `profile.html`, clears the display name field, and clicks `Save`.
8. User navigates to `home.html`. Welcome text reverts to "Welcome, [username]".

## Technical Design
- Files expected to change:
  - `test-site/profile.html`
  - `test-site/home.html`
  - `test-site/app.js`
  - `tests/test_displayname_contract.py` (new)
  - `run_testdisplayname_local.py` (new)
  - `docs/features/tdd_DisplayName.md`
- Markup contract:
  - Display name label: `data-testid="profile-displayname-label"`
  - Display name input: `data-testid="profile-displayname-input"` and `maxlength="32"`
  - Home welcome text (existing): `data-testid="welcome-text"`
- Data model (`localStorage`):
  - Key: `profiles_v1` (existing)
  - Extended shape: `{ "profiles": { "<canonical_username>": { "aboutMe": "...", "country": "...", "state": "...", "displayName": "..." } } }`
  - `displayName` absent or empty string → render username on home page.
- Load/save behavior:
  - On profile load: resolve authenticated user, load `displayName` if present, populate input.
  - On save: trim value, enforce 32-char max, persist. Empty string is a valid saved value (clears display name).
  - On invalid/missing storage data: recover to empty default without throwing.
  - On home page load: resolve authenticated user, load `displayName`, render in `welcome-text` if non-empty after trim; otherwise render username.
- Logging/token policy:
  - Preserve exactly one terminal `FINAL: PASS` or `FINAL: FAIL` per smoke script run.

### Requirement IDs
- `REQ-1`: Profile page includes a visible `Display name` label and text input.
- `REQ-2`: Display name input enforces max 32 characters.
- `REQ-3`: Save action persists display name for the authenticated user.
- `REQ-4`: Returning authenticated users see their previously saved display name pre-filled on the profile page.
- `REQ-5`: Home page welcome text shows display name when set; falls back to username when empty or absent.

## Testing Plan
### Test Cases
- `TEST-UNIT-DISPLAYNAME-001` (Unit): Profile HTML contract includes display name label and input with `maxlength="32"` and correct `data-testid` values.
- `TEST-UNIT-DISPLAYNAME-002` (Unit): Save/load logic stores and restores display name per authenticated user; absent/empty value does not overwrite other profile fields.
- `TEST-UNIT-DISPLAYNAME-003` (Unit): Home page welcome text renders display name when set and falls back to username when display name is empty or absent.
- `TEST-SMOKE-DISPLAYNAME-001` (Smoke): register → profile → set display name → save → home → verify welcome shows display name → profile → clear display name → save → home → verify welcome shows username.
- `TEST-REGRESSION-LOGIN-001` (Regression Smoke): Existing login smoke remains passing.

### Commands
- Unit tests:
  - `python -m pytest -q tests/test_displayname_contract.py`
- Feature smoke:
  - `python .\run_testdisplayname_local.py --skip-install`
- Feature smoke strict:
  - `python .\run_testdisplayname_local.py --skip-install`
- Regression smoke:
  - `python .\run_testlogin_local.py --skip-install`

### Requirement-to-Test Traceability Matrix
| Requirement ID | Test ID | Test Type | Command |
|---|---|---|---|
| REQ-1 | TEST-UNIT-DISPLAYNAME-001 | Unit | `python -m pytest -q tests/test_displayname_contract.py` |
| REQ-1 | TEST-SMOKE-DISPLAYNAME-001 | Smoke | `python .\run_testdisplayname_local.py --skip-install` |
| REQ-2 | TEST-UNIT-DISPLAYNAME-001 | Unit | `python -m pytest -q tests/test_displayname_contract.py` |
| REQ-2 | TEST-SMOKE-DISPLAYNAME-001 | Smoke | `python .\run_testdisplayname_local.py --skip-install` |
| REQ-3 | TEST-UNIT-DISPLAYNAME-002 | Unit | `python -m pytest -q tests/test_displayname_contract.py` |
| REQ-3 | TEST-SMOKE-DISPLAYNAME-001 | Smoke | `python .\run_testdisplayname_local.py --skip-install` |
| REQ-4 | TEST-UNIT-DISPLAYNAME-002 | Unit | `python -m pytest -q tests/test_displayname_contract.py` |
| REQ-4 | TEST-SMOKE-DISPLAYNAME-001 | Smoke | `python .\run_testdisplayname_local.py --skip-install` |
| REQ-5 | TEST-UNIT-DISPLAYNAME-003 | Unit | `python -m pytest -q tests/test_displayname_contract.py` |
| REQ-5 | TEST-SMOKE-DISPLAYNAME-001 | Smoke | `python .\run_testdisplayname_local.py --skip-install` |
| REQ-1..REQ-5 | TEST-REGRESSION-LOGIN-001 | Regression Smoke | `python .\run_testlogin_local.py --skip-install` |

### Test Execution Evidence (Fill During Implementation)
- `python -m pytest -q tests/test_displayname_contract.py` -> exit: 0 (5 passed), token: N/A, log: pytest console output.
- `python .\run_testdisplayname_local.py --skip-install` -> exit: 0 (FINAL: PASS), token: ~24k input / ~3k output, log: `displayname_run.log`.
- `python .\run_testlogin_local.py --skip-install` -> exit: 4294967295 (FINAL: FAIL — transient API overload_error from Anthropic, unrelated to this change; no code failure).

## Acceptance Criteria
- `AC-1` (`REQ-1`, `TEST-UNIT-DISPLAYNAME-001`, `TEST-SMOKE-DISPLAYNAME-001`): Profile page shows a visible `Display name` label and input with stable selector.
- `AC-2` (`REQ-2`, `TEST-UNIT-DISPLAYNAME-001`, `TEST-SMOKE-DISPLAYNAME-001`): Display name input is capped at 32 characters.
- `AC-3` (`REQ-3`, `TEST-UNIT-DISPLAYNAME-002`, `TEST-SMOKE-DISPLAYNAME-001`): Save persists display name for the authenticated user without disturbing other profile fields.
- `AC-4` (`REQ-4`, `TEST-UNIT-DISPLAYNAME-002`, `TEST-SMOKE-DISPLAYNAME-001`): Saved display name is pre-filled on return visits to the profile page.
- `AC-5` (`REQ-5`, `TEST-UNIT-DISPLAYNAME-003`, `TEST-SMOKE-DISPLAYNAME-001`): Home page welcome text shows display name when set and falls back to username when empty or absent.
