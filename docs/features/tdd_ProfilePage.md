# Profile Page (TDD)

## Feature Spec Header
- Feature Name: Profile Page
- Feature Slug: ProfilePage
- Owner: TBD
- User Story: As a user, I would like a profile page, so that I have somewhere to put profile info.
- In Scope:
  - Add a Profile navigation control on Home page.
  - Add a new Profile page reachable after login.
  - Add Profile page heading text only (no additional profile content yet).
  - Add a Home navigation control on Profile page.
- Out Of Scope:
  - Editing/saving profile fields.
  - Profile data persistence.
  - Backend/API integration.
  - Authorization roles beyond current local auth gate.
- Dependencies:
  - Existing local auth/session behavior in `test-site/app.js` via `auth_user`.
  - Existing login and logout flows in `test-site/index.html`, `test-site/home.html`, `test-site/app.js`.
  - Existing smoke framework (`run_testlogin_local.py` pattern).
- Rollout Risk: Low. Static page + simple navigation links on local test site.
- Test Requirements:
  - Unit tests for any new navigation guard logic in `test-site/app.js`.
  - New feature smoke script: `run_testprofilepage_local.py`.
  - Requirement-to-test traceability matrix included below.

## Summary
Add a minimal Profile page to the local test site so authenticated users can navigate from Home to Profile and back to Home, with Profile initially containing only a heading. This establishes a stable route and test IDs for future profile feature work.

## Goals
- Implement authenticated navigation from Home to Profile.
- Implement authenticated navigation from Profile back to Home.
- Render a visible Profile heading on Profile page.
- Preserve existing login/home/logout behavior.
- Add test coverage for the new navigation path.

## Non-Goals
- Profile fields, forms, or validation.
- Any profile CRUD behavior.
- Styling redesign beyond existing site patterns.
- Changes to AI model-learning behavior unrelated to this route.

## Assumptions
- ASSUMPTION: Profile page requires an authenticated user and redirects unauthenticated visitors to `index.html?redirect=profile`.
- ASSUMPTION: Home page Profile control is a link-style control (`<a>`) with stable `data-testid`.
- ASSUMPTION: Profile page Home control is a link-style control (`<a>`) with stable `data-testid`.
- ASSUMPTION: No precommit smoke inclusion update is required in this feature (manual decision per `docs/skills/QA_WebAutomation.MD`).

## Open Questions
- None.

## Linear Checklist
- [x] Define requirements and stable selectors for profile navigation and page heading (`REQ-1`, `REQ-2`, `REQ-3`).
- [x] Update `test-site/home.html` to add Profile navigation control with `data-testid="profile-link"` (`REQ-1`).
- [x] Add `test-site/profile.html` with heading `Profile`, `data-testid="profile-title"`, and Home navigation control `data-testid="profile-home-link"` (`REQ-2`, `REQ-3`).
- [x] Update `test-site/app.js` to enforce auth guard on Profile page similar to Home page guard (`REQ-2`).
- [x] Add/confirm event or redirect behavior needed for Profile/Home navigation while preserving logout behavior (`REQ-1`, `REQ-3`).
- [x] Add/update unit tests for profile page auth-gate and navigation-related logic (`TEST-UNIT-PROFILE-001`, `TEST-UNIT-PROFILE-002`).
- [x] Create `run_testprofilepage_local.py` smoke script with `--skip-install` and optional strict mode flag `--require-feature` (`TEST-SMOKE-PROFILE-001`).
- [x] Document smoke command and expected log artifact `profilepage_run.log` in this TDD (`TEST-SMOKE-PROFILE-001`).
- [x] Run targeted tests and smoke checks, capture command/exit code/result token in implementation PR notes (`TEST-UNIT-PROFILE-001`, `TEST-SMOKE-PROFILE-001`).
- [x] Update `docs/Structure.MD` if runtime flow/module boundaries change from adding the new page route.
- [x] Confirm all acceptance criteria map to `REQ-*` and `TEST-*` IDs and mark completion.

## UX Workflow
1. User logs in on `index.html` and lands on `home.html` (existing behavior).
2. User sees a `Profile` control on Home page.
3. User selects `Profile` and navigates to `profile.html`.
4. Profile page shows a visible heading: `Profile`.
5. User selects `Home` on Profile page and returns to `home.html`.
6. If user directly opens `profile.html` without auth, user is redirected to `index.html?redirect=profile`.

## Technical Design
- Files expected to change:
  - `test-site/home.html`
  - `test-site/profile.html` (new)
  - `test-site/app.js`
  - `run_testprofilepage_local.py` (new, implementation phase)
  - `tests/test_profilepage_*.py` (new/updated, implementation phase)
- Markup contract:
  - Home page adds: `data-testid="profile-link"`.
  - Profile page adds:
    - `data-testid="profile-title"`
    - `data-testid="profile-home-link"`
- Auth behavior:
  - Reuse `AUTH_USER_KEY` check from current Home guard.
  - On missing user in Profile context, redirect to `index.html?redirect=profile`.
- Navigation behavior:
  - Home -> Profile via static route `profile.html`.
  - Profile -> Home via static route `home.html`.
- Logging/token policy for smoke:
  - Script must preserve exactly one terminal `FINAL: PASS` or `FINAL: FAIL` per run entrypoint.

### Requirement IDs
- `REQ-1`: Home page provides a Profile navigation control for authenticated users.
- `REQ-2`: Profile page exists, requires auth, and displays heading text `Profile`.
- `REQ-3`: Profile page provides UI navigation back to Home.

## Testing Plan
### Test Cases
- `TEST-UNIT-PROFILE-001` (Unit): Profile auth guard redirects unauthenticated access to `index.html?redirect=profile`.
- `TEST-UNIT-PROFILE-002` (Unit): Profile page contract selectors/heading string are present in rendered static page fixture or parser check.
- `TEST-SMOKE-PROFILE-001` (Smoke): End-to-end flow: login -> Home -> Profile -> verify heading -> back to Home.
- `TEST-REGRESSION-LOGIN-001` (Regression Smoke): Existing login smoke (`run_testlogin_local.py`) remains passing with no behavior regression.

### Commands
- Unit tests:
  - `python -m pytest -q tests/test_profilepage_*.py`
- Profile smoke:
  - `python .\run_testprofilepage_local.py --skip-install`
- Profile smoke strict:
  - `python .\run_testprofilepage_local.py --skip-install --require-feature`
- Regression smoke:
  - `python .\run_testlogin_local.py --skip-install`

### Requirement-to-Test Traceability Matrix
| Requirement ID | Test ID | Test Type | Command |
|---|---|---|---|
| REQ-1 | TEST-SMOKE-PROFILE-001 | Smoke | `python .\run_testprofilepage_local.py --skip-install` |
| REQ-2 | TEST-UNIT-PROFILE-001 | Unit | `python -m pytest -q tests/test_profilepage_*.py` |
| REQ-2 | TEST-UNIT-PROFILE-002 | Unit | `python -m pytest -q tests/test_profilepage_*.py` |
| REQ-2 | TEST-SMOKE-PROFILE-001 | Smoke | `python .\run_testprofilepage_local.py --skip-install --require-feature` |
| REQ-3 | TEST-SMOKE-PROFILE-001 | Smoke | `python .\run_testprofilepage_local.py --skip-install` |
| REQ-1, REQ-2, REQ-3 | TEST-REGRESSION-LOGIN-001 | Regression Smoke | `python .\run_testlogin_local.py --skip-install` |

## Acceptance Criteria
- `AC-1` (`REQ-1`, `TEST-SMOKE-PROFILE-001`): Home page includes a visible Profile control (`data-testid="profile-link"`) that navigates to `profile.html`.
- `AC-2` (`REQ-2`, `TEST-UNIT-PROFILE-001`, `TEST-SMOKE-PROFILE-001`): Profile route exists and unauthenticated visits to `profile.html` redirect to `index.html?redirect=profile`.
- `AC-3` (`REQ-2`, `TEST-UNIT-PROFILE-002`, `TEST-SMOKE-PROFILE-001`): Profile page displays heading text exactly `Profile` (`data-testid="profile-title"`).
- `AC-4` (`REQ-3`, `TEST-SMOKE-PROFILE-001`): Profile page includes a Home UI control (`data-testid="profile-home-link"`) that returns the user to `home.html`.
- `AC-5` (`REQ-1`, `REQ-2`, `REQ-3`, `TEST-REGRESSION-LOGIN-001`): Existing login flow continues to pass without regression.


