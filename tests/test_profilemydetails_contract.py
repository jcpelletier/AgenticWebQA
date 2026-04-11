from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# TEST-UNIT-PROFILEMYDETAILS-001
# REQ-1: Profile page includes all 9 field types under a "My Details" heading.
# REQ-5: "My Details" section heading is visible within the profile card.
# ---------------------------------------------------------------------------


def test_profile_html_has_mydetails_section_heading() -> None:
    profile_html = (REPO_ROOT / "test-site" / "profile.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert 'data-testid="profile-mydetails-section"' in profile_html
    assert 'data-testid="profile-mydetails-heading"' in profile_html
    assert "My Details" in profile_html


def test_profile_html_has_all_nine_field_testids() -> None:
    profile_html = (REPO_ROOT / "test-site" / "profile.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    required = [
        'data-testid="profile-birthday-input"',
        'data-testid="profile-hometown-input"',
        'data-testid="profile-address-input"',
        'data-testid="profile-timezone-select"',
        'data-testid="profile-favoritecolor-input"',
        'data-testid="profile-occupation-input"',
        'data-testid="profile-pronouns-input"',
        'data-testid="profile-favoritequote-input"',
        'data-testid="profile-sociallinks-section"',
        'data-testid="profile-social-linkedin-input"',
        'data-testid="profile-social-xtwitter-input"',
        'data-testid="profile-social-instagram-input"',
        'data-testid="profile-social-facebook-input"',
        'data-testid="profile-social-github-input"',
    ]
    for token in required:
        assert token in profile_html, f"Missing: {token}"


def test_profile_html_has_save_button() -> None:
    profile_html = (REPO_ROOT / "test-site" / "profile.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert 'data-testid="profile-save-button"' in profile_html


def test_profile_html_favoritequote_has_maxlength() -> None:
    profile_html = (REPO_ROOT / "test-site" / "profile.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert 'maxlength="500"' in profile_html


# ---------------------------------------------------------------------------
# TEST-UNIT-PROFILEMYDETAILS-002
# REQ-2: Save button persists all My Details fields to localStorage.
# REQ-3: Profile page load pre-populates fields from localStorage.
# ---------------------------------------------------------------------------


def test_app_js_has_mydetails_constants() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert "const FAVORITE_QUOTE_MAX_LEN = 500" in app_js
    assert "const TIMEZONE_OPTIONS = [" in app_js
    assert "const TIMEZONE_SET = new Set(TIMEZONE_OPTIONS)" in app_js


def test_app_js_has_mydetails_normalize_functions() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert "function normalizeTimezone(" in app_js
    assert "TIMEZONE_SET.has(candidate)" in app_js
    assert "function truncateFavoriteQuote(" in app_js
    assert "FAVORITE_QUOTE_MAX_LEN" in app_js
    assert "function normalizeSocialLinks(" in app_js


def test_app_js_normalizeSavedProfile_includes_mydetails_fields() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    required_fields = [
        "entry?.birthday",
        "entry?.hometown",
        "entry?.address",
        "normalizeTimezone(entry?.timezone",
        "entry?.favoriteColor",
        "entry?.occupation",
        "entry?.pronouns",
        "truncateFavoriteQuote(entry?.favoriteQuote",
        "normalizeSocialLinks(entry?.socialLinks)",
    ]
    for field in required_fields:
        assert field in app_js, f"Missing in normalizeSavedProfile: {field}"


def test_app_js_profile_page_loads_mydetails_fields() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    # Each field element is retrieved
    assert 'document.getElementById("profile-birthday-input")' in app_js
    assert 'document.getElementById("profile-hometown-input")' in app_js
    assert 'document.getElementById("profile-timezone-select")' in app_js
    assert 'document.getElementById("profile-favoritequote-input")' in app_js
    assert 'document.getElementById("profile-social-linkedin-input")' in app_js
    # Loaded from savedProfile on page init
    assert "birthdayInput.value = savedProfile.birthday" in app_js
    assert "hometownInput.value = savedProfile.hometown" in app_js
    assert "favoriteQuoteInput.value = savedProfile.favoriteQuote" in app_js
    assert "socialLinkedinInput.value = savedProfile.socialLinks.linkedin" in app_js


def test_app_js_save_handler_includes_mydetails_fields() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    # All new fields written to setSavedProfile call
    assert "birthday," in app_js
    assert "hometown," in app_js
    assert "address," in app_js
    assert "timezone," in app_js
    assert "favoriteColor," in app_js
    assert "occupation," in app_js
    assert "pronouns," in app_js
    assert "favoriteQuote," in app_js
    assert "socialLinks," in app_js


def test_app_js_getSavedProfile_uses_normalizeSavedProfile_for_default() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    # Default return must go through normalizeSavedProfile, not hardcoded partial object
    assert "return normalizeSavedProfile({});" in app_js


# ---------------------------------------------------------------------------
# TEST-UNIT-PROFILEMYDETAILS-003
# REQ-4: Social Links inputs display inline SVG platform icons.
# ---------------------------------------------------------------------------


def test_profile_html_has_social_icon_testids() -> None:
    profile_html = (REPO_ROOT / "test-site" / "profile.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    icon_testids = [
        'data-testid="social-icon-linkedin"',
        'data-testid="social-icon-xtwitter"',
        'data-testid="social-icon-instagram"',
        'data-testid="social-icon-facebook"',
        'data-testid="social-icon-github"',
    ]
    for testid in icon_testids:
        assert testid in profile_html, f"Missing SVG icon: {testid}"


def test_profile_html_social_icons_have_aria_labels() -> None:
    profile_html = (REPO_ROOT / "test-site" / "profile.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert 'aria-label="LinkedIn"' in profile_html
    assert 'aria-label="X (Twitter)"' in profile_html
    assert 'aria-label="Instagram"' in profile_html
    assert 'aria-label="Facebook"' in profile_html
    assert 'aria-label="GitHub"' in profile_html


def test_profile_html_social_icons_are_inline_svg() -> None:
    profile_html = (REPO_ROOT / "test-site" / "profile.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    # Inline SVG must be present (not <img> or external references)
    assert "<svg" in profile_html
    assert "</svg>" in profile_html
    # Must not reference external icon files
    assert "social-icon" not in profile_html.replace('data-testid="social-icon', "x")


# ---------------------------------------------------------------------------
# TEST-UNIT-PROFILEMYDETAILS-004
# REQ-1: Timezone select is populated from a curated IANA timezone constant.
# ---------------------------------------------------------------------------


def test_app_js_timezone_list_has_required_entries() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    required_zones = [
        '"America/New_York"',
        '"Europe/London"',
        '"Asia/Tokyo"',
    ]
    for zone in required_zones:
        assert zone in app_js, f"Missing required timezone: {zone}"


def test_app_js_timezone_select_populated_in_profile_block() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert 'document.getElementById("profile-timezone-select")' in app_js
    assert "setSelectOptions(timezoneSelect, TIMEZONE_OPTIONS)" in app_js
    assert "timezoneSelect.value = savedProfile.timezone" in app_js
