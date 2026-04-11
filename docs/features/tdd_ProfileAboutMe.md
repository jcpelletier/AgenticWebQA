# Profile About Me (TDD)

## Feature Spec Header
- Feature Name: Profile About Me
- Feature Slug: ProfileAboutMe
- Owner: TBD
- User Story: As an authenticated user, I want to view my username on the Profile page and edit an `About me` section so I can save profile content.
- In Scope:
  - Display authenticated username near the top of `profile.html`.
  - Add an `About me` labeled textarea on `profile.html`.
  - Enforce `About me` max length of 1000 characters.
  - Add a `Save` action that persists about-me content.
  - Reload saved about-me content when the same authenticated user returns.
- Out Of Scope:
  - Rich text, markdown, links, or media uploads.
  - Backend/API services, cloud sync, or multi-device profile sync.
  - Profile editing on non-profile routes.
  - Changes to login/register/logout behavior other than compatibility.
- Dependencies:
  - Existing auth/session key `auth_user` in `test-site/app.js`.
  - Existing profile route and auth guard (`test-site/profile.html`, `test-site/app.js`).
  - Existing smoke harness in `run_testprofilepage_local.py`.
- Rollout Risk: Medium. Introduces user-scoped persisted state on an authenticated page.
- Test Requirements:
  - Unit tests for profile DOM contract and save/load/length behavior.
  - Updated smoke coverage in `run_testprofilepage_local.py` for save + reload.
  - Requirement-to-test traceability matrix included below.

## Summary
Extend the Profile page from heading-only content to a minimal editable profile surface by showing the signed-in username, adding an `About me` textarea with a 1000-character cap, and persisting content per authenticated user so it appears on later visits.

## Goals
- Show authenticated username on Profile page.
- Provide a labeled `About me` textarea.
- Enforce deterministic 1000-character cap.
- Persist about-me content through explicit `Save`.
- Rehydrate saved content for the same authenticated user.

## Non-Goals
- Server-side profile APIs.
- Changes to auth semantics.
- Moderation/admin workflows.
- New dependencies.

## Assumptions
- ASSUMPTION: "Simple on-disk-backed client storage" is satisfied by browser `localStorage`.
- ASSUMPTION: About-me data is keyed per canonical username to avoid cross-user overwrite.
- ASSUMPTION: Empty value is valid and represents clearing `About me`.
- ASSUMPTION: Native `maxlength="1000"` is present and save-path guard also enforces limit.
- ASSUMPTION: No `precommit_smoketest.ps1` change is required for this feature unless explicitly requested.

## Open Questions
- None.

## Linear Checklist
- [x] Define stable selectors and requirement IDs for username display, about-me input, save, and reload (`REQ-1`..`REQ-5`).
- [x] Update `test-site/profile.html` with username display element (`data-testid="profile-username"`) (`REQ-1`).
- [x] Update `test-site/profile.html` with `About me` label, textarea (`maxlength="1000"`), and Save button (`REQ-2`, `REQ-3`, `REQ-4`).
- [x] Update `test-site/app.js` profile-page logic to hydrate username from `auth_user` (`REQ-1`).
- [x] Add profile storage helpers in `test-site/app.js` using `profiles_v1` keyed by canonical username (`REQ-4`, `REQ-5`).
- [x] Hydrate textarea from saved state on Profile page load (`REQ-5`).
- [x] Persist textarea value on Save with deterministic 1000-char enforcement (`REQ-3`, `REQ-4`).
- [x] Add/update unit tests for profile contract/save/load/limit (`TEST-UNIT-PROFILEABOUT-001`..`003`).
- [x] Update `run_testprofilepage_local.py` smoke flow to verify username visibility, textarea save, and persisted reload (`TEST-SMOKE-PROFILEABOUT-001`).
- [x] Run targeted unit/smoke commands and record command, exit code, `FINAL` token, and artifact path under Test Execution Evidence.
- [x] Run regression login smoke (`TEST-REGRESSION-LOGIN-001`).
- [x] Update `docs/Structure.MD` if runtime flow/module boundaries change (not required for this feature; no boundary change).
- [x] Confirm acceptance criteria and REQ/TEST traceability are complete.

## UX Workflow
1. User logs in and reaches `home.html`.
2. User navigates to `profile.html`.
3. Profile page shows page title and authenticated username near top.
4. Page shows an `About me` label and textarea.
5. Existing saved content is preloaded for that user when present.
6. User edits text (up to 1000 chars) and clicks `Save`.
7. Content persists for that user.
8. On later profile visits, saved content is displayed again.
9. Existing unauthenticated redirect behavior for `profile.html` remains unchanged.

## Technical Design
- Files expected to change:
  - `test-site/profile.html`
  - `test-site/app.js`
  - `tests/test_profilepage_*.py` (or profile-about-specific module)
  - `run_testprofilepage_local.py`
  - `docs/features/tdd_ProfileAboutMe.md`
- Markup contract:
  - Username display: `data-testid="profile-username"`
  - About label: `data-testid="profile-about-label"`
  - About textarea: `data-testid="profile-about-input"` and `maxlength="1000"`
  - Save button: `data-testid="profile-save-button"`
- Data model (`localStorage`):
  - Key: `profiles_v1`
  - Shape: `{ "profiles": { "<canonical_username>": { "aboutMe": "..." } } }`
- Load/save behavior:
  - On profile load: resolve authenticated user, canonicalize, load value if present.
  - On save: truncate to 1000 if needed, persist by canonical username.
  - On invalid/missing storage data: recover to empty default state without throwing.
- Logging/token policy:
  - Preserve exactly one terminal `FINAL: PASS` or `FINAL: FAIL` per smoke script run.

### Requirement IDs
- `REQ-1`: Profile page displays authenticated username near the top.
- `REQ-2`: Profile page includes visible `About me` label and textarea.
- `REQ-3`: `About me` input enforces max 1000 characters.
- `REQ-4`: Save action persists current about-me text for authenticated user.
- `REQ-5`: Returning authenticated users see previously saved about-me text.

## Testing Plan
### Test Cases
- `TEST-UNIT-PROFILEABOUT-001` (Unit): Profile HTML contract includes username display, label, textarea, save button, and `maxlength="1000"`.
- `TEST-UNIT-PROFILEABOUT-002` (Unit): Save/load logic stores and restores about-me text per authenticated username.
- `TEST-UNIT-PROFILEABOUT-003` (Unit): Save/input path enforces deterministic 1000-char cap.
- `TEST-SMOKE-PROFILEABOUT-001` (Smoke): login -> profile -> verify username -> enter about me -> save -> leave/revisit -> verify persisted content.
- `TEST-REGRESSION-LOGIN-001` (Regression Smoke): Existing login smoke remains passing.

### Commands
- Unit tests:
  - `python -m pytest -q tests/test_profilepage_*.py`
- Feature smoke:
  - `python .\run_testprofilepage_local.py --skip-install`
- Feature smoke strict:
  - `python .\run_testprofilepage_local.py --skip-install --require-feature`
- Regression smoke:
  - `python .\run_testlogin_local.py --skip-install`

### Requirement-to-Test Traceability Matrix
| Requirement ID | Test ID | Test Type | Command |
|---|---|---|---|
| REQ-1 | TEST-UNIT-PROFILEABOUT-001 | Unit | `python -m pytest -q tests/test_profilepage_*.py` |
| REQ-1 | TEST-SMOKE-PROFILEABOUT-001 | Smoke | `python .\run_testprofilepage_local.py --skip-install --require-feature` |
| REQ-2 | TEST-UNIT-PROFILEABOUT-001 | Unit | `python -m pytest -q tests/test_profilepage_*.py` |
| REQ-2 | TEST-SMOKE-PROFILEABOUT-001 | Smoke | `python .\run_testprofilepage_local.py --skip-install --require-feature` |
| REQ-3 | TEST-UNIT-PROFILEABOUT-003 | Unit | `python -m pytest -q tests/test_profilepage_*.py` |
| REQ-3 | TEST-SMOKE-PROFILEABOUT-001 | Smoke | `python .\run_testprofilepage_local.py --skip-install --require-feature` |
| REQ-4 | TEST-UNIT-PROFILEABOUT-002 | Unit | `python -m pytest -q tests/test_profilepage_*.py` |
| REQ-4 | TEST-SMOKE-PROFILEABOUT-001 | Smoke | `python .\run_testprofilepage_local.py --skip-install --require-feature` |
| REQ-5 | TEST-UNIT-PROFILEABOUT-002 | Unit | `python -m pytest -q tests/test_profilepage_*.py` |
| REQ-5 | TEST-SMOKE-PROFILEABOUT-001 | Smoke | `python .\run_testprofilepage_local.py --skip-install --require-feature` |
| REQ-1, REQ-2, REQ-3, REQ-4, REQ-5 | TEST-REGRESSION-LOGIN-001 | Regression Smoke | `python .\run_testlogin_local.py --skip-install` |

### Test Execution Evidence (Fill During Implementation)
- `python -m pytest -q tests\test_profilepage_contract.py` -> exit: `0`, token: N/A (unit test run), log: pytest console output.
- `python .\run_testprofilepage_local.py --skip-install --require-feature` -> exit: `0`, token: `FINAL: PASS`, log: `profilepage_run.log`.
- `python .\run_testlogin_local.py --skip-install` -> exit: `0`, token: `FINAL: PASS`, log: `reuse_run.log` (plus script default artifacts).

## Acceptance Criteria
- `AC-1` (`REQ-1`, `TEST-UNIT-PROFILEABOUT-001`, `TEST-SMOKE-PROFILEABOUT-001`): Profile page shows authenticated username in visible element with stable selector.
- `AC-2` (`REQ-2`, `TEST-UNIT-PROFILEABOUT-001`, `TEST-SMOKE-PROFILEABOUT-001`): Profile page includes visible `About me` label and textarea.
- `AC-3` (`REQ-3`, `TEST-UNIT-PROFILEABOUT-003`, `TEST-SMOKE-PROFILEABOUT-001`): About-me input is capped at 1000 chars deterministically.
- `AC-4` (`REQ-4`, `TEST-UNIT-PROFILEABOUT-002`, `TEST-SMOKE-PROFILEABOUT-001`): Save persists about-me value for authenticated user.
- `AC-5` (`REQ-5`, `TEST-UNIT-PROFILEABOUT-002`, `TEST-SMOKE-PROFILEABOUT-001`): Saved about-me content reloads on later authenticated profile visits.
