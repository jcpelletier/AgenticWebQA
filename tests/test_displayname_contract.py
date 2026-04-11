from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# TEST-UNIT-DISPLAYNAME-001
# REQ-1: Profile page includes a visible Display name label and text input.
# REQ-2: Display name input enforces max 32 characters.
# ---------------------------------------------------------------------------


def test_profile_html_has_displayname_label_and_input() -> None:
    profile_html = (REPO_ROOT / "test-site" / "profile.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert 'data-testid="profile-displayname-label"' in profile_html
    assert 'data-testid="profile-displayname-input"' in profile_html
    assert 'maxlength="32"' in profile_html
    assert "Display name" in profile_html
    assert 'for="profile-displayname-input"' in profile_html


# ---------------------------------------------------------------------------
# TEST-UNIT-DISPLAYNAME-002
# REQ-3: Save action persists display name for the authenticated user.
# REQ-4: Returning authenticated users see their previously saved display name.
# ---------------------------------------------------------------------------


def test_app_js_has_display_name_constant_and_normalize() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert "const DISPLAY_NAME_MAX_LEN = 32" in app_js
    assert "function normalizeDisplayName(" in app_js
    assert ".trim().slice(0, DISPLAY_NAME_MAX_LEN)" in app_js


def test_app_js_normalizeSavedProfile_includes_displayName() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    # normalizeSavedProfile must call normalizeDisplayName and return displayName
    assert "normalizeDisplayName(entry?.displayName" in app_js
    assert "displayName" in app_js


def test_app_js_profile_page_loads_and_saves_displayName() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    # Input element is retrieved
    assert 'document.getElementById("profile-displayname-input")' in app_js
    # Loaded on page init
    assert "displayNameInput.value = savedProfile.displayName" in app_js
    # Saved on button click
    assert "displayName," in app_js
    assert "normalizeDisplayName(displayNameInput.value)" in app_js


# ---------------------------------------------------------------------------
# TEST-UNIT-DISPLAYNAME-003
# REQ-5: Home page welcome text shows display name when set;
#        falls back to username when empty or absent.
# ---------------------------------------------------------------------------


def test_app_js_home_welcome_uses_displayName_with_fallback() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    # The home page block must call getSavedProfile for the logged-in user
    assert "getSavedProfile(username)" in app_js
    # Must use displayName with username fallback
    assert "homeProfile.displayName || username" in app_js
