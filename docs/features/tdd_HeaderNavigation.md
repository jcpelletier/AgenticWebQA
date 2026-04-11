# Header Navigation (TDD)

## Feature Spec Header
- Feature Name: Header Navigation
- Feature Slug: HeaderNavigation
- Owner: TBD
- User Story: As a user, I would like a header bar, so that we have a consistent spot for site navigation between Home and Profile.
- In Scope:
  - Add a visually distinct header area at the top of main authenticated pages.
  - Place `Home` and `Profile` navigation options in the header.
  - Show the current page label in black and render non-current page options as clickable navigation controls.
  - Remove the centered Profile button from Home page content and relocate Profile navigation to the header.
  - Establish reusable header markup/style pattern so future main pages can adopt the same navigation structure.
- Out Of Scope:
  - New page creation beyond existing Home and Profile routes.
  - Major site-wide visual redesign outside header/navigation elements.
  - Backend/API/session model changes.
  - Role-based or permission-based navigation variants.
- Dependencies:
  - Existing authenticated routes and auth gate behavior in `test-site/app.js`.
  - Existing Home/Profile pages (`test-site/home.html`, `test-site/profile.html`).
  - Existing UI regression smoke baseline (`run_testlogin_local.py`) and profile smoke flow (`run_testprofilepage_local.py`).
- Rollout Risk: Low to Medium. Shared navigation markup touches multiple pages and can introduce route/selector regressions if contracts drift.
- Test Requirements:
  - Add/extend unit tests validating header nav selector contract and active-state semantics.
  - Add/extend feature smoke coverage for Home <-> Profile navigation via header controls.
  - Maintain requirement-to-test traceability for all `REQ-*` IDs.

## Summary
Introduce a shared header navigation bar for main authenticated pages so Home and Profile routing is consistent and future pages can plug into the same top-of-page navigation pattern. The header must indicate the active page label in black, keep other page labels clickable, and remove the old centered Profile button from Home content.

## Goals
- Create a consistent top header navigation pattern for current and future main pages.
- Make `Home` and `Profile` navigable from header UI on both pages.
- Render active page label in black to indicate current location.
- Preserve existing auth-gated behavior and route stability.
- Remove duplicate/legacy centered Profile button from Home content area.

## Non-Goals
- Introducing additional nav destinations (for example Settings/About) in this feature.
- Building a dynamic router framework.
- Changing login screen structure.
- Adding animation-heavy or theme overhaul behavior.

## Assumptions
- ASSUMPTION: "Current page label in header shows as black" means computed text color is black (`rgb(0, 0, 0)` or `#000`) for the active nav item.
- ASSUMPTION: Non-current nav options use anchor elements and are keyboard-focusable/clickable.
- ASSUMPTION: Header is required on authenticated main pages currently in scope (`home.html`, `profile.html`), but not required on `index.html` login page.
- ASSUMPTION: Existing auth guard behavior remains unchanged; this feature only changes navigation placement/presentation.
- ASSUMPTION: Default policy applies: do not modify `precommit_smoketest.ps1` unless explicitly requested by a developer.

## Open Questions
- Should the active page label be non-clickable plain text, or a disabled-style link that is still focusable? (Current plan assumes non-clickable label.)
- Should header container/test IDs be standardized now (for example `site-header`, `nav-home`, `nav-profile`, `nav-current`) for future pages? (Current plan assumes yes.)

## Linear Checklist
- [x] Define header navigation requirement contracts and stable selectors for shared usage (`REQ-1`, `REQ-2`, `REQ-3`, `REQ-4`, `REQ-5`).
- [x] Update `test-site/home.html` to add top header container with Home/Profile nav controls and active-state semantics (`REQ-1`, `REQ-2`, `REQ-3`).
- [x] Update `test-site/profile.html` to add matching top header container with Home/Profile nav controls and active-state semantics (`REQ-1`, `REQ-2`, `REQ-3`).
- [x] Remove legacy centered Profile button/control from Home content section (`REQ-5`).
- [x] Update shared styles in `test-site/styles.css` to make header visually distinct and enforce active label black styling (`REQ-1`, `REQ-3`).
- [x] Update `test-site/app.js` only as needed to preserve route/auth behavior while supporting shared header nav contracts (`REQ-2`, `REQ-4`). (No change required.)
- [x] Add/update unit tests for header selector contract and active-state semantics (`TEST-UNIT-HEADERNAV-001`, `TEST-UNIT-HEADERNAV-002`).
- [x] Add/update smoke coverage for Home/Profile navigation through header only (`TEST-SMOKE-HEADERNAV-001`).
- [x] Run `.\precommit_smoketest.ps1` and capture result evidence in this TDD (`TEST-REGRESSION-HEADERNAV-001`).
- [x] Run feature unit tests and capture command + pass evidence in this TDD (`TEST-UNIT-HEADERNAV-001`, `TEST-UNIT-HEADERNAV-002`).
- [x] Run feature integration/smoke tests and capture command + pass evidence in this TDD (`TEST-SMOKE-HEADERNAV-001`).
- [x] Record all executed test commands, exit codes, and pass outcomes in the Testing Plan evidence section.
- [x] Update `docs/Structure.MD` if runtime flow/module boundaries change due to shared header composition.
- [x] Confirm all acceptance criteria are satisfied and mapped to `REQ-*` and `TEST-*` IDs.

## UX Workflow
1. Authenticated user lands on `home.html` and sees a visually distinct header at the top of the page.
2. Header contains `Home` and `Profile` labels.
3. On Home page, `Home` appears as the active label in black; `Profile` appears clickable.
4. User clicks `Profile` in header and navigates to `profile.html`.
5. On Profile page, `Profile` appears as the active label in black; `Home` appears clickable.
6. User clicks `Home` in header and returns to `home.html`.
7. Home page body no longer contains the previous centered Profile button.

## Technical Design
- Files expected to change:
  - `test-site/home.html`
  - `test-site/profile.html`
  - `test-site/styles.css`
  - `test-site/app.js` (only if needed for nav/auth consistency)
  - `tests/test_headernav_*.py` (new/updated)
  - `run_testprofilepage_local.py` or `run_testheadernavigation_local.py` (implementation decision)
- Shared header markup contract (proposed):
  - Header container test id: `data-testid="site-header"`
  - Home nav item test id: `data-testid="nav-home"`
  - Profile nav item test id: `data-testid="nav-profile"`
  - Active nav item state marker: `aria-current="page"` plus active class (for style assertion)
- Active/inactive behavior:
  - Active item on current page is rendered non-clickable and styled black.
  - Inactive item remains clickable and routes to its target page.
- Styling:
  - Header has clear visual separation from body (for example border/background/padding differences).
  - Active item text color forced to black.
- Routing/auth behavior:
  - Keep existing auth checks for Home/Profile intact.
  - No login page header requirement in this feature.

### Requirement IDs
- `REQ-1`: A visually distinct header area appears at the top of Home and Profile pages.
- `REQ-2`: Header includes `Home` and `Profile` navigation options on both pages.
- `REQ-3`: The current page label in header is styled black.
- `REQ-4`: Non-current page option is clickable and navigates correctly.
- `REQ-5`: Centered Profile button is removed from Home page body.

## Testing Plan
### Test Cases
- `TEST-UNIT-HEADERNAV-001` (Unit): Verify Home page markup includes header container and both nav IDs with correct active-state attributes.
- `TEST-UNIT-HEADERNAV-002` (Unit): Verify Profile page markup includes header container and both nav IDs with correct active-state attributes.
- `TEST-SMOKE-HEADERNAV-001` (Smoke): End-to-end flow login -> Home header visible -> click Profile in header -> verify Profile active label black -> click Home in header -> verify Home active label black and no centered Profile button.
- `TEST-REGRESSION-HEADERNAV-001` (Regression): Existing login smoke continues passing.

### Commands
- Precommit regression suite:
  - `.\precommit_smoketest.ps1`
- Feature unit tests:
  - `python -m pytest -q tests/test_headernav_contract.py`
- Feature smoke tests (recommended existing profile smoke path):
  - `python .\run_testprofilepage_local.py --skip-install --require-feature`
- Regression smoke:
  - `python .\run_testlogin_local.py --skip-install`

### Requirement-to-Test Traceability Matrix
| Requirement ID | Test ID | Test Type | Command |
|---|---|---|---|
| REQ-1 | TEST-UNIT-HEADERNAV-001 | Unit | `python -m pytest -q tests/test_headernav_contract.py` |
| REQ-1 | TEST-UNIT-HEADERNAV-002 | Unit | `python -m pytest -q tests/test_headernav_contract.py` |
| REQ-1 | TEST-SMOKE-HEADERNAV-001 | Smoke | `python .\run_testprofilepage_local.py --skip-install --require-feature` |
| REQ-2 | TEST-UNIT-HEADERNAV-001 | Unit | `python -m pytest -q tests/test_headernav_contract.py` |
| REQ-2 | TEST-UNIT-HEADERNAV-002 | Unit | `python -m pytest -q tests/test_headernav_contract.py` |
| REQ-2 | TEST-SMOKE-HEADERNAV-001 | Smoke | `python .\run_testprofilepage_local.py --skip-install --require-feature` |
| REQ-3 | TEST-UNIT-HEADERNAV-001 | Unit | `python -m pytest -q tests/test_headernav_contract.py` |
| REQ-3 | TEST-UNIT-HEADERNAV-002 | Unit | `python -m pytest -q tests/test_headernav_contract.py` |
| REQ-3 | TEST-SMOKE-HEADERNAV-001 | Smoke | `python .\run_testprofilepage_local.py --skip-install --require-feature` |
| REQ-4 | TEST-SMOKE-HEADERNAV-001 | Smoke | `python .\run_testprofilepage_local.py --skip-install --require-feature` |
| REQ-5 | TEST-SMOKE-HEADERNAV-001 | Smoke | `python .\run_testprofilepage_local.py --skip-install --require-feature` |
| REQ-1, REQ-2, REQ-3, REQ-4, REQ-5 | TEST-REGRESSION-HEADERNAV-001 | Regression | `.\precommit_smoketest.ps1` |

### Test Execution Evidence
- Command: `python -m pytest -q tests/test_headernav_contract.py`
  - Exit code: `0`
  - Result token: N/A (pytest unit run)
  - Log artifact: Console output only
- Command: `python .\run_testprofilepage_local.py --skip-install --require-feature`
  - Exit code: `0`
  - Result token: `FINAL: PASS`
  - Log artifact: `profilepage_run_1771622123.log` (fallback path used due locked default log file)
- Command: `.\precommit_smoketest.ps1`
  - Exit code: `0`
  - Result token: Login smoke emitted `FINAL: PASS` for auto-heal and reuse runs within precommit flow
  - Log artifact: Console output only

## Acceptance Criteria
- `AC-1` (`REQ-1`, `TEST-UNIT-HEADERNAV-001`, `TEST-UNIT-HEADERNAV-002`, `TEST-SMOKE-HEADERNAV-001`): Home and Profile each render a visually distinct header area at top-of-page.
- `AC-2` (`REQ-2`, `TEST-UNIT-HEADERNAV-001`, `TEST-UNIT-HEADERNAV-002`, `TEST-SMOKE-HEADERNAV-001`): Header on both pages includes `Home` and `Profile` labels.
- `AC-3` (`REQ-3`, `TEST-UNIT-HEADERNAV-001`, `TEST-UNIT-HEADERNAV-002`, `TEST-SMOKE-HEADERNAV-001`): Active page label is rendered in black on Home and Profile respectively.
- `AC-4` (`REQ-4`, `TEST-SMOKE-HEADERNAV-001`): Non-active label is clickable and navigates to the other page.
- `AC-5` (`REQ-5`, `TEST-SMOKE-HEADERNAV-001`): Home page no longer shows a centered Profile button in page body.


