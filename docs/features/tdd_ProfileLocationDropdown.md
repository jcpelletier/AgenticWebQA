# Profile Location Dropdown (TDD)

## Feature Spec Header
- Feature Name: Profile Location Dropdown
- Feature Slug: ProfileLocationDropdown
- Owner: TBD
- User Story: As a user, I would like a Location dropdown on the Profile page, so that I can list where I am in the world.
- In Scope:
  - Add Country dropdown under About Me on `profile.html`.
  - Populate Country with a long country list where first country is `United States of America` and remaining countries are alphabetical.
  - Conditionally show State dropdown only when Country is `United States of America`.
  - Persist `country` and conditional `state` with existing profile data persistence.
  - Wipe saved `state` when selected country is changed to non-USA.
- Out Of Scope:
  - Geolocation APIs or auto-detection.
  - International sub-region dropdowns for non-USA countries.
  - Backend/database profile APIs.
  - UI redesign outside Profile page form controls.
- Dependencies:
  - Existing Profile page markup and auth gate in `test-site/profile.html` and `test-site/app.js`.
  - Existing local storage profile key `profiles_v1`.
  - Existing Profile smoke pattern in `run_testprofilepage_local.py`.
- Rollout Risk: Medium-low. Touches profile storage shape and profile form behavior.
- Test Requirements:
  - Contract/unit tests for new profile location controls and persistence helpers.
  - New feature smoke script `run_testprofilelocation_local.py`.
  - Requirement-to-test traceability matrix included below.

## Summary
Add a Country dropdown to the Profile page, add a conditional State dropdown that appears only for USA, and persist both values with existing About Me profile data. State data must be cleared whenever the selected country is not USA.

## Goals
- Add stable, testable Country and State profile controls.
- Keep Country options deterministic with `United States of America` first and all following country options alphabetically ordered.
- Show State dropdown only for USA selection.
- Persist Country and State with existing profile persistence behavior.
- Ensure saved State is removed when a non-USA country is selected.

## Non-Goals
- No mandatory country selection requirement.
- No non-USA region/state handling.
- No API or server persistence.
- No changes to login/home/register behavior.

## Assumptions
- ASSUMPTION: Country is optional and can remain unselected.
- ASSUMPTION: State is optional even when Country is USA.
- ASSUMPTION: Existing `profiles_v1` records without `country`/`state` remain valid and default to empty values.
- ASSUMPTION: `precommit_smoketest.ps1` remains unchanged unless explicitly requested.

## Open Questions
- None.

## Linear Checklist
- [x] Define location requirements with `REQ-*` coverage for country ordering, conditional state visibility, and persistence semantics (`REQ-1`, `REQ-2`, `REQ-3`, `REQ-4`, `REQ-5`).
- [x] Add Country UI on `test-site/profile.html` under About Me with stable test IDs (`REQ-1`, `REQ-2`).
- [x] Add hidden State UI on `test-site/profile.html` with stable test IDs (`REQ-3`).
- [x] Add style support for select elements and conditional field block in `test-site/styles.css` (`REQ-1`, `REQ-3`).
- [x] Extend `test-site/app.js` profile storage model to persist `aboutMe`, `country`, and conditional `state` (`REQ-4`).
- [x] Implement Country list initialization where USA is first and remainder alphabetical (`REQ-2`).
- [x] Implement conditional State show/hide logic and clear State when country is non-USA (`REQ-3`, `REQ-5`).
- [x] Add/update contract tests in `tests/test_profilepage_contract.py` for location controls and helper functions (`TEST-UNIT-PROFILELOC-001`, `TEST-UNIT-PROFILELOC-002`).
- [x] Add unit contract test module `tests/test_profilelocation_contract.py` to validate option ordering lists and USA/state wipe guard semantics in script contracts (`TEST-UNIT-PROFILELOC-003`).
- [x] Add feature smoke script `run_testprofilelocation_local.py` with `--skip-install` and `--require-feature` (`TEST-SMOKE-PROFILELOC-001`).
- [x] Add smoke log artifact ignore entry for `profilelocation_run.log` (`TEST-SMOKE-PROFILELOC-001`).
- [x] Update `README.md` and `docs/Structure.MD` for new profile-location behavior and command references.
- [x] Run `python -m pytest -q tests/test_profilepage_*.py`.
- [x] Run `python -m pytest -q tests/test_profilelocation_*.py`.
- [x] Run `python .\run_testprofilelocation_local.py --skip-install --require-feature`.
- [x] Run `.\precommit_smoketest.ps1`.
- [x] Record test execution evidence (commands + outcomes) in this TDD.
- [x] Confirm all acceptance criteria are satisfied and mapped to `REQ-*` and `TEST-*`.

## UX Workflow
1. Authenticated user opens Profile page.
2. User sees About Me textarea, Country dropdown, and Save button.
3. User selects a country.
4. If selected country is `United States of America`, State dropdown appears.
5. If selected country is not USA, State dropdown is hidden and any previous State selection is cleared.
6. User clicks Save to persist About Me, Country, and conditional State.
7. On returning to Profile later, saved values are restored from local storage.

## Technical Design
### Requirement IDs
- `REQ-1`: Profile page includes Country dropdown under About Me with stable selectors.
- `REQ-2`: Country dropdown contains a long country list where first country is `United States of America` and all following countries are alphabetical.
- `REQ-3`: State dropdown is hidden by default and only shown when Country is `United States of America`.
- `REQ-4`: Country and State persist with profile data similar to About Me save behavior.
- `REQ-5`: Saved State is wiped whenever Country is changed/saved to any non-USA value.

### File Changes
- `test-site/profile.html`
  - Add Country label/select test IDs.
  - Add State container/label/select test IDs.
- `test-site/styles.css`
  - Apply input styling parity to `select`.
  - Add spacing rules for conditional state block.
- `test-site/app.js`
  - Add country/state constants and option lists.
  - Extend profile load/save normalization for `country` and conditional `state`.
  - Populate dropdown options at runtime.
  - Implement conditional State visibility and wipe behavior.
- `tests/test_profilepage_contract.py`
  - Add markup and JS contract assertions for location controls and persistence helpers.
- `tests/test_profilelocation_contract.py` (new)
  - Validate country ordering contract and USA/state wipe semantics string contracts.
- `run_testprofilelocation_local.py` (new)
  - End-to-end smoke: country/state select, persistence, and state wipe check.
- `.gitignore`
  - Add `profilelocation_run.log`.

## Testing Plan
### Test Cases
- `TEST-UNIT-PROFILELOC-001` (Unit/Contract): Profile HTML exposes Country and State controls with stable `data-testid`s.
- `TEST-UNIT-PROFILELOC-002` (Unit/Contract): `app.js` defines country/state option constants and profile save/load helpers for `country` and `state`.
- `TEST-UNIT-PROFILELOC-003` (Unit/Contract): `app.js` contract includes USA-first ordering and explicit state wipe branch on non-USA country.
- `TEST-SMOKE-PROFILELOC-001` (Smoke): Login -> Profile -> save non-USA country -> verify no State -> save USA+State -> persist -> switch back to non-USA -> verify State wiped.
- `TEST-REGRESSION-PROFILE-001` (Regression Smoke): Existing profile page smoke still passes.
- `TEST-REGRESSION-LOGIN-001` (Regression Smoke): Existing login smoke still passes through precommit.

### Commands
- `python -m pytest -q tests/test_profilepage_*.py`
- `python -m pytest -q tests/test_profilelocation_*.py`
- `python .\run_testprofilelocation_local.py --skip-install`
- `python .\run_testprofilelocation_local.py --skip-install --require-feature`
- `python .\run_testprofilepage_local.py --skip-install`
- `.\precommit_smoketest.ps1`

### Requirement-to-Test Traceability Matrix
| Requirement ID | Test ID | Test Type | Command |
|---|---|---|---|
| REQ-1 | TEST-UNIT-PROFILELOC-001 | Unit/Contract | `python -m pytest -q tests/test_profilepage_*.py` |
| REQ-2 | TEST-UNIT-PROFILELOC-002 | Unit/Contract | `python -m pytest -q tests/test_profilelocation_*.py` |
| REQ-2 | TEST-UNIT-PROFILELOC-003 | Unit/Contract | `python -m pytest -q tests/test_profilelocation_*.py` |
| REQ-3 | TEST-UNIT-PROFILELOC-001 | Unit/Contract | `python -m pytest -q tests/test_profilepage_*.py` |
| REQ-3 | TEST-SMOKE-PROFILELOC-001 | Smoke | `python .\run_testprofilelocation_local.py --skip-install --require-feature` |
| REQ-4 | TEST-SMOKE-PROFILELOC-001 | Smoke | `python .\run_testprofilelocation_local.py --skip-install --require-feature` |
| REQ-5 | TEST-UNIT-PROFILELOC-003 | Unit/Contract | `python -m pytest -q tests/test_profilelocation_*.py` |
| REQ-5 | TEST-SMOKE-PROFILELOC-001 | Smoke | `python .\run_testprofilelocation_local.py --skip-install --require-feature` |
| REQ-1, REQ-2, REQ-3, REQ-4, REQ-5 | TEST-REGRESSION-PROFILE-001 | Regression Smoke | `python .\run_testprofilepage_local.py --skip-install` |
| REQ-1, REQ-2, REQ-3, REQ-4, REQ-5 | TEST-REGRESSION-LOGIN-001 | Regression Smoke | `.\precommit_smoketest.ps1` |

### Test Execution Evidence
- `python -m pytest -q tests/test_profilepage_contract.py tests/test_profilelocation_contract.py`
  - Exit code: `0`
  - Result: `7 passed`
- `python .\run_testprofilelocation_local.py --skip-install --require-feature`
  - Exit code: `0`
  - Result token artifact: `profilelocation_run.log` with `FINAL: PASS`
- `.\precommit_smoketest.ps1`
  - Exit code: `0`
  - Result: `ruff format` completed, `mypy` passed, `pytest` passed (`33 passed`), login integration smoke completed with `FINAL: PASS`

## Acceptance Criteria
- `AC-1` (`REQ-1`, `TEST-UNIT-PROFILELOC-001`): Profile page has a Country dropdown under About Me with stable selectors.
- `AC-2` (`REQ-2`, `TEST-UNIT-PROFILELOC-002`, `TEST-UNIT-PROFILELOC-003`): Country list is long; `United States of America` is first country; all following countries are alphabetical.
- `AC-3` (`REQ-3`, `TEST-UNIT-PROFILELOC-001`, `TEST-SMOKE-PROFILELOC-001`): State dropdown appears only when Country equals `United States of America` and is hidden otherwise.
- `AC-4` (`REQ-4`, `TEST-SMOKE-PROFILELOC-001`): Country and State values persist when saved, similar to About Me behavior.
- `AC-5` (`REQ-5`, `TEST-UNIT-PROFILELOC-003`, `TEST-SMOKE-PROFILELOC-001`): Saved State is cleared when a non-USA country is selected and saved.
