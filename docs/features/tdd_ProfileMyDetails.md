# Profile My Details (TDD)

## Feature Spec Header

- **Feature Name:** Profile My Details
- **Feature Slug:** ProfileMyDetails
- **Owner:** TBD
- **User Story:**
  - **Original Request Wording:** "I would like to add a 'My Details' section to the profile that shows a list of form inputs of information about the user that they can enter and save. As a user, I would like to be able to fill out a comprehensive profile, so I can document a lot of information about myself. Acceptance Criteria: 1. Please include the following fields. Birthday, Hometown, Address, Timezone, Favorite Color, Occupation, Pronouns, Social Links (With icons for Linkedin, X, Twitter, instagram, etc), Favorite Quote. 2. Have a save button that will save any edits to fields. 3. Loading page shows existing saved values in each field."
  - **Clarified Story:** As an authenticated user, I want a "My Details" section on the profile page that contains comprehensive personal information fields (Birthday, Hometown, Address, Timezone, Favorite Color, Occupation, Pronouns, Social Links with platform icons, and Favorite Quote), so that I can document a rich set of information about myself, save it with a single Save button, and see those values pre-populated whenever I return to the page.
- **In Scope:**
  - Add a "My Details" collapsible/labeled section to `test-site/profile.html` containing all 9 field types.
  - Extend `test-site/app.js` `normalizeSavedProfile`, `getSavedProfile`, and `setSavedProfile` to include all new fields.
  - Social Links section with inline SVG icons (no CDN) for LinkedIn, X/Twitter, Instagram, Facebook, and GitHub.
  - Timezone `<select>` populated from a curated list of ~25 common IANA timezone strings.
  - Birthday `<input type="date">`, Hometown/Occupation/Pronouns/Favorite Color as `<input type="text">`, Address as `<textarea>`, Favorite Quote as `<textarea>`.
  - Save via the existing `profile-save-button`.
  - Backwards-compatible `profiles_v1` localStorage schema: missing new fields default to empty string.
  - Unit tests under `tests/test_profilemydetails_contract.py`.
  - Smoke script `webtests/run_testprofilemydetails_local.py`.
  - Update `release_test.py` with the new smoke step.
- **Out Of Scope:**
  - Server-side persistence (localStorage only).
  - Profile privacy or visibility settings.
  - Social link URL validation or linkability.
  - Full IANA timezone list (curated subset only).
  - Pronouns as a constrained dropdown (free-text input).
  - Profanity filtering or content moderation.
  - Field-level character limits beyond what the input type naturally provides (except Favorite Quote textarea, capped at 500 chars to match existing page aesthetics).
  - Adding `run_testprofilemydetails_local.py` to `precommit_smoketest.py` (default: do NOT add; requires explicit developer request).
- **Dependencies:**
  - Existing `profiles_v1` localStorage key and per-user profile object in `test-site/app.js`.
  - Existing `data-testid="profile-save-button"` on `profile.html`.
  - Existing `requireAuthenticatedUser` auth guard in `test-site/app.js`.
  - Existing `normalizeSavedProfile`, `getSavedProfile`, `setSavedProfile` functions in `test-site/app.js`.
- **Rollout Risk:** Low-Medium. Additive fields on an existing storage key; no breaking changes to existing profile fields. Risk is primarily `normalizeSavedProfile` backwards-compatibility if missing-field defaults are not handled correctly.
- **Test Requirements:**
  - Unit contract tests for DOM structure, new field save/load roundtrip, backwards-compatibility, and social link icon presence.
  - Smoke test covering register → open profile → fill My Details fields → save → reload → verify persistence.
  - Regression smoke for existing profile tests (about-me, location).
  - Requirement-to-test traceability matrix included below.

---

## Summary

Add a "My Details" section to the profile page containing 9 field types: Birthday, Hometown, Address, Timezone, Favorite Color, Occupation, Pronouns, Favorite Quote, and Social Links (LinkedIn, X/Twitter, Instagram, Facebook, GitHub) with inline SVG platform icons. All fields are optional, persist to the existing `profiles_v1` localStorage structure per authenticated user, and are pre-populated on return visits. The existing Save button submits all fields together.

---

## Goals

- Provide a labeled "My Details" section in the profile card with all 9 field types.
- Persist all new fields via the existing Save button to `profiles_v1` localStorage.
- Pre-populate all new fields from localStorage on profile page load.
- Display inline SVG icons next to each Social Links input.
- Extend `normalizeSavedProfile` with backwards-compatible defaults for all new fields.
- Provide unit contract tests and a dedicated smoke script.

---

## Non-Goals

- Server-side profile storage or API endpoints.
- Social link URL validation, hyperlinking, or preview.
- Display of My Details fields on any page other than profile.
- Full IANA timezone list or timezone detection.
- Profanity filtering.
- Pronouns constrained to a preset list.
- Adding the new smoke script to `precommit_smoketest.py` automatically.

---

## Assumptions

- ASSUMPTION: `profiles_v1` per-user object is extended with the following keys: `birthday` (string), `hometown` (string), `address` (string), `timezone` (string), `favoriteColor` (string), `occupation` (string), `pronouns` (string), `favoriteQuote` (string), `socialLinks` (object with keys: `linkedin`, `xTwitter`, `instagram`, `facebook`, `github`, each a string URL or handle). Absent or empty string means "not set".
- ASSUMPTION: All new fields are optional; empty string is a valid and meaningful saved value.
- ASSUMPTION: The existing Save button on `profile.html` saves all profile fields together, including all new My Details fields.
- ASSUMPTION: Timezone select will contain a curated list of approximately 25 common IANA timezone strings (e.g., `America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles`, `Europe/London`, `Europe/Paris`, `Asia/Tokyo`, etc.). The full list must be enumerated in the Technical Design and unit contract.
- ASSUMPTION: Social link inputs accept free-text (no URL format enforcement). Each input is labeled with the platform name and paired with an inline SVG icon identified via `data-testid="social-icon-<platform>"`.
- ASSUMPTION: Favorite Quote textarea is capped at `maxlength="500"`.
- ASSUMPTION: `normalizeSavedProfile` must gracefully handle both legacy profiles (missing new fields) and profiles with partial new fields by defaulting all new fields to empty string without corrupting existing fields.

---

## Open Questions

- **OQ-1:** Should "My Details" be a collapsible/expandable section (e.g., using `<details>`/`<summary>`) or always visible? **Default assumption: always visible.** Developer must confirm before implementation if collapsible behavior is preferred.
- **OQ-2:** Should Favorite Color use `<input type="color">` (native browser color picker) or `<input type="text">`? `type="color"` provides a richer UX but may complicate smoke test assertions. **Default assumption: `<input type="text">` for testability.** Developer must confirm if a color picker is preferred.
- **OQ-3:** Should the Social Links section accept full URLs (e.g., `https://linkedin.com/in/username`) or short handles (e.g., `username`)? **Default assumption: free-text, no validation.** Developer must confirm if URL format is required.
- **OQ-4:** Exact curated timezone list contents (beyond the ~25 suggested in Assumptions) — should it mirror browser `Intl.supportedValuesOf('timeZone')` output or a manually maintained list? **Default assumption: manually maintained list enumerated in app.js constant.**

---

## Sub-Agent Orchestration

| Role | Guide | Status |
|------|-------|--------|
| PlanningOrchestrator | `.claude/commands/planning.md` | Complete — this document |
| QAManager | `.claude/commands/qa-manager.md` | Invoked — output captured in Sub-Agent Output Verification |
| RequirementsTraceabilityReviewer | `.claude/commands/qa-traceability.md` | Invoked — output captured in Sub-Agent Output Verification |

Subagent routing decision: `QA_WebAutomation` was invoked via QAManager (feature affects `test-site/` UI and `webtests/` smoke scripts). `QA_API` was not invoked (no API scope). `QA_Traceability` was invoked by default (REQ-* and TEST-* IDs are being defined).

---

## Linear Checklist

- [x] Invoke QAManager subagent and capture returned test strategy, commands, and risks. (`REQ-1`..`REQ-5`)
- [x] Invoke RequirementsTraceabilityReviewer subagent and capture REQ/TEST/AC mapping audit. (`REQ-1`..`REQ-5`)
- [x] Confirm Open Questions (OQ-1 through OQ-4) with developer or lock in default assumptions. (`REQ-1`) — all locked as ASSUMPTION defaults
- [x] Enumerate the exact curated IANA timezone list (~25 entries) in `test-site/app.js` as a named constant. (`REQ-1`)
- [x] Add "My Details" section HTML to `test-site/profile.html` with all 9 field types, correct `data-testid` attributes, and inline SVG icons for all 5 social platforms. (`REQ-1`, `REQ-4`, `REQ-5`)
- [x] Extend `normalizeSavedProfile()` in `test-site/app.js` to include all new My Details fields with empty-string defaults. (`REQ-2`, `REQ-3`)
- [x] Update profile save logic in `test-site/app.js` to persist all new My Details fields to `profiles_v1`. (`REQ-2`)
- [x] Update profile load logic in `test-site/app.js` to pre-populate all new My Details fields from `profiles_v1` on page load. (`REQ-3`)
- [x] Create `tests/test_profilemydetails_contract.py` with `TEST-UNIT-PROFILEMYDETAILS-001` through `-004`. (`REQ-1`..`REQ-5`)
- [x] Create `webtests/run_testprofilemydetails_local.py` covering `TEST-SMOKE-PROFILEMYDETAILS-001`, `-002`, `-003` with `--skip-install`, `--require-feature`, `--model`, and `--max-steps 20`. (`REQ-1`..`REQ-5`)
- [x] Update `release_test.py` to include the new ProfileMyDetails e2e smoke step. (`REQ-1`..`REQ-5`)
- [x] Run `python -m pytest -q tests/test_profilemydetails_contract.py` and record result in Test Execution Evidence. (`TEST-UNIT-PROFILEMYDETAILS-001`..`-004`) — **15 passed**
- [x] Run `python ./precommit_smoketest.py` and record result in Test Execution Evidence. — **PASS (78 unit tests + login smoke)**
- [ ] Run `python ./webtests/run_testprofilemydetails_local.py --skip-install --require-feature --model claude-sonnet-4-6` and record result in Test Execution Evidence. (`TEST-SMOKE-PROFILEMYDETAILS-001`..`-003`)
- [ ] Run regression smokes (`run_testprofilepage_local.py`, `run_testprofilelocation_local.py`) and record results in Test Execution Evidence. (`TEST-REGRESSION-PROFILEPAGE-001`, `TEST-REGRESSION-PROFILELOC-001`)
- [x] Record all test commands and pass outcomes in Test Execution Evidence section of this TDD.
- [x] Confirm `Sub-Agent Output Verification` section is complete with all required fields for each subagent.

---

## UX Workflow

1. Authenticated user navigates to `profile.html`.
2. Profile page loads. Existing fields (About me, Country/State, Display name) are visible.
3. Below or alongside existing fields, a "My Details" section heading is visible.
4. The "My Details" section contains:
   - Birthday: date input pre-filled if previously saved.
   - Hometown: text input pre-filled if previously saved.
   - Address: textarea pre-filled if previously saved.
   - Timezone: select dropdown showing saved timezone (or blank/default if not set).
   - Favorite Color: text input pre-filled if previously saved.
   - Occupation: text input pre-filled if previously saved.
   - Pronouns: text input pre-filled if previously saved.
   - Favorite Quote: textarea (max 500 chars) pre-filled if previously saved.
   - Social Links: five labeled text inputs (LinkedIn, X/Twitter, Instagram, Facebook, GitHub), each preceded by an inline SVG icon, pre-filled if previously saved.
5. User edits one or more fields and clicks the existing **Save** button.
6. All profile fields (existing + new My Details) are persisted to `profiles_v1` localStorage.
7. User navigates away (e.g., to Home) and returns to the profile page.
8. All previously saved values are pre-populated in their respective fields.

**Failure behavior:**
- If localStorage is unavailable or corrupted, `normalizeSavedProfile` returns empty defaults; no error is thrown; the page still renders with empty fields.
- Missing new fields in an existing profile object default to empty string silently.

---

## Technical Design

### Files to Change

| File | Change |
|------|--------|
| `test-site/profile.html` | Add "My Details" section with all 9 field types and inline SVG social icons |
| `test-site/app.js` | Extend `normalizeSavedProfile`, profile save/load logic, and curated IANA timezone constant |
| `tests/test_profilemydetails_contract.py` | New file — unit contract tests |
| `webtests/run_testprofilemydetails_local.py` | New file — smoke script |
| `release_test.py` | Add ProfileMyDetails e2e smoke step |
| `docs/features/tdd_ProfileMyDetails.md` | This document |

### `data-testid` Attribute Contract

| Element | `data-testid` |
|---------|--------------|
| My Details section container | `profile-mydetails-section` |
| My Details section heading | `profile-mydetails-heading` |
| Birthday input | `profile-birthday-input` |
| Hometown input | `profile-hometown-input` |
| Address textarea | `profile-address-input` |
| Timezone select | `profile-timezone-select` |
| Favorite Color input | `profile-favoritecolor-input` |
| Occupation input | `profile-occupation-input` |
| Pronouns input | `profile-pronouns-input` |
| Favorite Quote textarea | `profile-favoritequote-input` |
| Social Links container | `profile-sociallinks-section` |
| LinkedIn input | `profile-social-linkedin-input` |
| X/Twitter input | `profile-social-xtwitter-input` |
| Instagram input | `profile-social-instagram-input` |
| Facebook input | `profile-social-facebook-input` |
| GitHub input | `profile-social-github-input` |
| LinkedIn icon SVG | `social-icon-linkedin` |
| X/Twitter icon SVG | `social-icon-xtwitter` |
| Instagram icon SVG | `social-icon-instagram` |
| Facebook icon SVG | `social-icon-facebook` |
| GitHub icon SVG | `social-icon-github` |

### Data Model (`localStorage`)

Key: `profiles_v1` (existing)

Extended per-user shape:
```json
{
  "profiles": {
    "<canonical_username>": {
      "aboutMe": "...",
      "country": "...",
      "state": "...",
      "displayName": "...",
      "birthday": "...",
      "hometown": "...",
      "address": "...",
      "timezone": "...",
      "favoriteColor": "...",
      "occupation": "...",
      "pronouns": "...",
      "favoriteQuote": "...",
      "socialLinks": {
        "linkedin": "...",
        "xTwitter": "...",
        "instagram": "...",
        "facebook": "...",
        "github": "..."
      }
    }
  }
}
```

All new keys absent from a legacy profile object → default to `""` (empty string) via `normalizeSavedProfile`. `socialLinks` absent → default to `{ linkedin: "", xTwitter: "", instagram: "", facebook: "", github: "" }`.

### Curated IANA Timezone List (to be defined in `app.js`)

Minimum required entries (exact string values):

```
America/New_York, America/Chicago, America/Denver, America/Phoenix,
America/Los_Angeles, America/Anchorage, America/Honolulu,
America/Toronto, America/Vancouver, America/Mexico_City,
America/Sao_Paulo, America/Buenos_Aires,
Europe/London, Europe/Paris, Europe/Berlin, Europe/Moscow,
Africa/Johannesburg, Africa/Cairo,
Asia/Dubai, Asia/Kolkata, Asia/Bangkok, Asia/Shanghai,
Asia/Tokyo, Asia/Seoul,
Australia/Sydney, Pacific/Auckland
```

The unit contract test must assert that at least `America/New_York`, `Europe/London`, and `Asia/Tokyo` are present in the select options.

### Save/Load Logic

- **On profile save:** Read all My Details input values, trim strings, enforce Favorite Quote `maxlength="500"` at the JS layer as well, write the full extended profile object to `profiles_v1`.
- **On profile load:** Call `normalizeSavedProfile(entry)` which fills missing new keys with empty defaults, then populate each input element from the normalized object.
- **Backward-compatibility contract:** `normalizeSavedProfile({})` must return an object where all new keys are present as `""` (or `{}` for `socialLinks`). `normalizeSavedProfile({ aboutMe: "x" })` must return `{ aboutMe: "x", country: "", state: "", displayName: "", birthday: "", ... }` without throwing.

### Social Link Icon Implementation

Inline SVG elements rendered directly in `profile.html` source. Each icon:
- Has `aria-label="<PlatformName>"` for accessibility.
- Has `data-testid="social-icon-<platform>"` for test assertions.
- No external CDN or image requests.
- Unit contract test asserts on `data-testid` presence, not raw SVG path data.

### Logging/Token Policy

- Smoke script must emit exactly one `FINAL: PASS` or `FINAL: FAIL` per run.
- If `--require-feature` is passed and the My Details section is not detected, emit `SKIP: PROFILE_MY_DETAILS_FEATURE_MISSING` followed by `FINAL: PASS`.

---

## Requirement IDs

- **REQ-1:** Profile page includes a "My Details" section with all 9 field types: Birthday (`<input type="date">`), Hometown (text), Address (textarea), Timezone (select from curated IANA list), Favorite Color (text), Occupation (text), Pronouns (text), Favorite Quote (textarea, max 500), and Social Links (LinkedIn, X/Twitter, Instagram, Facebook, GitHub text inputs with inline SVG icons).
- **REQ-2:** The existing Save button persists all "My Details" fields to `profiles_v1` localStorage under the authenticated user's profile key.
- **REQ-3:** Profile page load pre-populates all "My Details" fields with previously saved values from `profiles_v1` localStorage.
- **REQ-4:** Social Links inputs each display a recognizable inline SVG platform icon identified by `data-testid="social-icon-<platform>"` for LinkedIn, X/Twitter, Instagram, Facebook, and GitHub.
- **REQ-5:** A "My Details" section heading (`data-testid="profile-mydetails-heading"`) is visible within the profile card layout.

---

## Testing Plan

### Test Cases

| Test ID | Type | File / Script | Scenario | REQ |
|---------|------|---------------|---------|-----|
| TEST-UNIT-PROFILEMYDETAILS-001 | Unit | `tests/test_profilemydetails_contract.py` | `profile.html` contains My Details section heading, all 9 field `data-testid` attributes, and Save button | REQ-1, REQ-5 |
| TEST-UNIT-PROFILEMYDETAILS-002 | Unit | `tests/test_profilemydetails_contract.py` | `normalizeSavedProfile()` extends legacy profiles with all new fields as empty-string defaults; save/load roundtrip for new fields does not corrupt existing fields | REQ-2, REQ-3 |
| TEST-UNIT-PROFILEMYDETAILS-003 | Unit | `tests/test_profilemydetails_contract.py` | `profile.html` contains inline SVG elements with correct `data-testid="social-icon-<platform>"` for all 5 platforms | REQ-4 |
| TEST-UNIT-PROFILEMYDETAILS-004 | Unit | `tests/test_profilemydetails_contract.py` | Timezone select is populated from a constant containing at least `America/New_York`, `Europe/London`, and `Asia/Tokyo` | REQ-1 |
| TEST-SMOKE-PROFILEMYDETAILS-001 | Smoke | `webtests/run_testprofilemydetails_local.py` | Register → open Profile → verify "My Details" section heading and all field types are visible | REQ-1, REQ-5 |
| TEST-SMOKE-PROFILEMYDETAILS-002 | Smoke | `webtests/run_testprofilemydetails_local.py` | Register → open Profile → fill Hometown with `{rand_string}` → Save → reload page → verify Hometown field contains `{rand_string}` | REQ-2, REQ-3 |
| TEST-SMOKE-PROFILEMYDETAILS-003 | Smoke | `webtests/run_testprofilemydetails_local.py` | Register → open Profile → scroll to Social Links area → verify platform icons are visible | REQ-4 |
| TEST-INTEG-PROFILEMYDETAILS-001 | Integration (in smoke) | `webtests/run_testprofilemydetails_local.py` | Playwright-level: inspect localStorage `profiles_v1` after save to confirm new fields are present alongside legacy fields without corruption | REQ-2, REQ-3 |
| TEST-REGRESSION-PROFILEPAGE-001 | Regression Smoke | `webtests/run_testprofilepage_local.py` | Existing About Me save/load flow still passes after My Details changes | REQ-1..REQ-5 |
| TEST-REGRESSION-PROFILELOC-001 | Regression Smoke | `webtests/run_testprofilelocation_local.py` | Existing Country/State flow still passes after My Details changes | REQ-1..REQ-5 |

### Smoke Prompt and Success Criteria Design

**TEST-SMOKE-PROFILEMYDETAILS-001 — Section Visibility**
- Prompt: `"1. Register a new account.\n2. Open the Profile page from the navigation header."`
- Success criteria: `"The profile page is visible and shows a 'My Details' section heading. VISUAL_UNIQUE: The text 'My Details' is visible as a distinct section heading within the profile card, and this heading was not present on any earlier page in this flow."`
- Actions: `register_account,profile_open,profile_mydetails_view`

**TEST-SMOKE-PROFILEMYDETAILS-002 — Save and Reload Persistence**
- Prompt: `"1. Register a new account.\n2. Open the Profile page from the navigation header.\n3. Find the Hometown field under My Details and enter {rand_string}.\n4. Click the Save button.\n5. Reload the page."`
- Success criteria: `"The profile page is visible after reload with the Hometown field containing {rand_string}. VISUAL_UNIQUE: The value {rand_string} is visible inside the Hometown input field after the page was reloaded, which confirms persistence; this value was not present in the Hometown field before the save action."`
- Actions: `register_account,profile_open,profile_mydetails_save`

**TEST-SMOKE-PROFILEMYDETAILS-003 — Social Link Icons**
- Prompt: `"1. Register a new account.\n2. Open the Profile page from the navigation header.\n3. Scroll to the Social Links section under My Details."`
- Success criteria: `"The profile page shows the Social Links area with visible platform icons next to the input fields. VISUAL_UNIQUE: Platform icons (such as the LinkedIn or GitHub logo) are visible as graphical elements adjacent to social link text inputs, which were not present anywhere before this section was scrolled into view."`
- Actions: `register_account,profile_open,profile_mydetails_view`

### Commands

```sh
# Unit tests (run after implementation)
python -m pytest -q tests/test_profilemydetails_contract.py

# Full unit suite (regression baseline)
python -m pytest -q tests/

# Feature smoke (run after implementation)
python ./webtests/run_testprofilemydetails_local.py --skip-install --require-feature --model claude-sonnet-4-6

# Regression smokes
python ./webtests/run_testprofilepage_local.py --skip-install --require-feature --model claude-sonnet-4-6
python ./webtests/run_testprofilelocation_local.py --skip-install --require-feature --model claude-sonnet-4-6

# Pre-commit (run after all implementation)
python ./precommit_smoketest.py
```

> **Precommit inclusion decision:** Do NOT add `run_testprofilemydetails_local.py` to `precommit_smoketest.py`. This is the default QAManager policy. A developer must explicitly request this before it is added.

### Requirement-to-Test Traceability Matrix

| Requirement ID | Test ID | Test Type | Command |
|----------------|---------|-----------|---------|
| REQ-1 | TEST-UNIT-PROFILEMYDETAILS-001 | Unit | `python -m pytest -q tests/test_profilemydetails_contract.py` |
| REQ-1 | TEST-UNIT-PROFILEMYDETAILS-004 | Unit | `python -m pytest -q tests/test_profilemydetails_contract.py` |
| REQ-1 | TEST-SMOKE-PROFILEMYDETAILS-001 | Smoke | `python ./webtests/run_testprofilemydetails_local.py --skip-install --require-feature --model claude-sonnet-4-6` |
| REQ-2 | TEST-UNIT-PROFILEMYDETAILS-002 | Unit | `python -m pytest -q tests/test_profilemydetails_contract.py` |
| REQ-2 | TEST-SMOKE-PROFILEMYDETAILS-002 | Smoke | `python ./webtests/run_testprofilemydetails_local.py --skip-install --require-feature --model claude-sonnet-4-6` |
| REQ-2 | TEST-INTEG-PROFILEMYDETAILS-001 | Integration | `python ./webtests/run_testprofilemydetails_local.py --skip-install --require-feature --model claude-sonnet-4-6` |
| REQ-3 | TEST-UNIT-PROFILEMYDETAILS-002 | Unit | `python -m pytest -q tests/test_profilemydetails_contract.py` |
| REQ-3 | TEST-SMOKE-PROFILEMYDETAILS-002 | Smoke | `python ./webtests/run_testprofilemydetails_local.py --skip-install --require-feature --model claude-sonnet-4-6` |
| REQ-4 | TEST-UNIT-PROFILEMYDETAILS-003 | Unit | `python -m pytest -q tests/test_profilemydetails_contract.py` |
| REQ-4 | TEST-SMOKE-PROFILEMYDETAILS-003 | Smoke | `python ./webtests/run_testprofilemydetails_local.py --skip-install --require-feature --model claude-sonnet-4-6` |
| REQ-5 | TEST-UNIT-PROFILEMYDETAILS-001 | Unit | `python -m pytest -q tests/test_profilemydetails_contract.py` |
| REQ-5 | TEST-SMOKE-PROFILEMYDETAILS-001 | Smoke | `python ./webtests/run_testprofilemydetails_local.py --skip-install --require-feature --model claude-sonnet-4-6` |
| REQ-1..REQ-5 | TEST-REGRESSION-PROFILEPAGE-001 | Regression Smoke | `python ./webtests/run_testprofilepage_local.py --skip-install --require-feature --model claude-sonnet-4-6` |
| REQ-1..REQ-5 | TEST-REGRESSION-PROFILELOC-001 | Regression Smoke | `python ./webtests/run_testprofilelocation_local.py --skip-install --require-feature --model claude-sonnet-4-6` |

### Gaps and NOT TESTED Items

| Item | Status | Reason |
|------|--------|--------|
| Input boundary/validation errors (oversized text, invalid date) | NOT TESTED | Out of scope for initial delivery; field-level validation is minimal by design (HTML maxlength + type constraints). Recommended for a follow-up TDD if validation behavior is added. |
| Favorite Quote 500-char enforcement via JS (beyond HTML maxlength) | NOT TESTED | JS-layer enforcement is covered implicitly by the save/load unit test; a dedicated boundary test is recommended but deferred. |

### Test Execution Evidence (Fill During Implementation)

| Command | Exit Code | Token | Artifact |
|---------|-----------|-------|---------|
| `python -m pytest -q tests/test_profilemydetails_contract.py` | 0 | N/A | 15 passed in 0.06s |
| `python -m pytest -q tests/` | 0 | N/A | 78 passed in 1.43s (no regressions) |
| `python ./precommit_smoketest.py` | 0 | N/A | ruff format + mypy + 78 pytest passed + login smoke FINAL: PASS |
| `python ./webtests/run_testprofilemydetails_local.py --skip-install --require-feature --model claude-sonnet-4-6` | ___ | ___ | `profilemydetails_run.log` (pending e2e run) |
| `python ./webtests/run_testprofilepage_local.py --skip-install --require-feature --model claude-sonnet-4-6` | ___ | ___ | `profilepage_run.log` (pending regression run) |
| `python ./webtests/run_testprofilelocation_local.py --skip-install --require-feature --model claude-sonnet-4-6` | ___ | ___ | `profilelocation_run.log` (pending regression run) |

---

## Acceptance Criteria

- **AC-1** (`REQ-1`, `TEST-UNIT-PROFILEMYDETAILS-001`, `TEST-UNIT-PROFILEMYDETAILS-004`, `TEST-SMOKE-PROFILEMYDETAILS-001`): All 9 field types (Birthday, Hometown, Address, Timezone, Favorite Color, Occupation, Pronouns, Favorite Quote, Social Links) are visible on the profile page under a "My Details" section heading. Timezone select contains at least `America/New_York`, `Europe/London`, and `Asia/Tokyo`.
- **AC-2** (`REQ-2`, `TEST-UNIT-PROFILEMYDETAILS-002`, `TEST-SMOKE-PROFILEMYDETAILS-002`, `TEST-INTEG-PROFILEMYDETAILS-001`): Filling one or more My Details fields and clicking Save persists values to `profiles_v1` localStorage; navigating away and returning to the profile page shows the saved values in the correct fields without corrupting existing profile fields (About Me, Country, State, Display Name).
- **AC-3** (`REQ-3`, `TEST-UNIT-PROFILEMYDETAILS-002`, `TEST-SMOKE-PROFILEMYDETAILS-002`): On profile page load, all My Details fields are pre-populated with any previously saved values. Fields with no saved value are blank.
- **AC-4** (`REQ-4`, `TEST-UNIT-PROFILEMYDETAILS-003`, `TEST-SMOKE-PROFILEMYDETAILS-003`): Each Social Links input is visually paired with an inline SVG platform icon. Icons are present for LinkedIn, X/Twitter, Instagram, Facebook, and GitHub. Each icon has a `data-testid="social-icon-<platform>"` attribute.
- **AC-5** (`REQ-5`, `TEST-UNIT-PROFILEMYDETAILS-001`, `TEST-SMOKE-PROFILEMYDETAILS-001`): A "My Details" section heading with `data-testid="profile-mydetails-heading"` is visible within the profile card on the profile page.

---

## Sub-Agent Output Verification

### QAManager

| Field | Value |
|-------|-------|
| Scope Reviewed | ProfileMyDetails — `test-site/profile.html`, `test-site/app.js`, `webtests/`, `tests/`, `release_test.py` |
| Findings (ordered by severity) | (1) BLOCKING: smoke script missing; (2) BLOCKING: feature not implemented; (3) BLOCKING: app.js not extended; (4) MEDIUM: VISUAL_UNIQUE markers must be defined; (5) MEDIUM: release_test.py not yet updated; (6) LOW: precommit inclusion not documented |
| Requirement Traceability | REQ-1..REQ-5: all NOT TESTED (pre-implementation, justified) — matrix above reflects full mapping |
| Commands Run | `python -m pytest -q tests/` → exit 0, 63 passed (baseline); feature-specific files not yet created |
| Artifacts | pytest console baseline; no feature-specific artifacts yet |
| Risks/Unknowns | (HIGH) normalizeSavedProfile backward-compat break; (MEDIUM) timezone curated list unspecified; (MEDIUM) color input type rendering variability; (LOW) SVG icon test stability; (LOW) smoke step count vs. --max-steps 20 |
| Recommended Verdict | FAIL (pre-implementation — expected and correct; baseline of 63 unit tests continues to pass without regression) |
| Status | COMPLETE |

### RequirementsTraceabilityReviewer

| Field | Value |
|-------|-------|
| Scope Reviewed | TDD (not yet created at audit time), `tests/test_profile_mydetails.py` (missing), `webtests/run_testprofilemydetails_local.py` (missing), `test-site/app.js` normalizeSavedProfile, `test-site/profile.html` |
| Findings (ordered by severity) | (F-1 CRITICAL) Feature not in test-site; (F-2 CRITICAL) TDD absent; (F-3 CRITICAL) unit test module absent; (F-4 CRITICAL) smoke script absent; (F-5 HIGH) pytest command non-runnable (file missing); (F-6 HIGH) `--model gpt-5.1` is an invalid model identifier — corrected to `claude-sonnet-4-6` in this TDD; (F-7 HIGH) precommit_smoketest.py has no My Details coverage; (F-8 HIGH) TEST-REGRESSION-PROFILE-01 under-specified — addressed with explicit commands above; (F-9 MEDIUM) backward-compat test unrunnable until feature is implemented; (F-10 MEDIUM) AC-4 icon coverage has no unit-level fallback — addressed with TEST-UNIT-PROFILEMYDETAILS-003; (F-11 LOW) no validation-error test cases — noted as NOT TESTED gap above |
| Requirement Traceability | REQ-1..REQ-5: all NOT TESTED (pre-implementation) — full matrix above |
| Commands Run | All feature-specific commands non-runnable (artifacts missing); `python ./precommit_smoketest.py` exists but contains no My Details coverage |
| Artifacts | None for this feature; baseline 63 pytest passes |
| Risks/Unknowns | R-1: Pre-implementation traceability package (expected); R-2: gpt-5.1 typo corrected to claude-sonnet-4-6; R-3: precommit false-signal risk noted; R-4: IANA list source unspecified — addressed in Technical Design; R-5: --require-feature skip semantics documented in smoke design |
| Recommended Verdict | FAIL (pre-implementation — expected; zero runnable test artifacts at audit time) |
| Status | COMPLETE |

**Reconciliation note:** The traceability reviewer flagged `--model gpt-5.1` as an invalid model identifier. All smoke commands in this TDD have been corrected to use `--model claude-sonnet-4-6`, consistent with existing profile test scripts per `CLAUDE.md`.
