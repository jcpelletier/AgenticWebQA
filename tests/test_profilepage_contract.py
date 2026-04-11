from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_profile_page_has_required_heading_and_home_link() -> None:
    profile_html = (REPO_ROOT / "test-site" / "profile.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert 'data-testid="profile-title"' in profile_html
    assert ">Profile<" in profile_html
    assert 'data-testid="nav-home"' in profile_html
    assert 'href="home.html"' in profile_html
    assert 'data-testid="site-header"' in profile_html
    assert 'data-testid="nav-profile"' in profile_html
    assert 'data-testid="profile-username"' in profile_html
    assert 'data-testid="profile-about-label"' in profile_html
    assert 'data-testid="profile-about-input"' in profile_html
    assert 'data-testid="profile-country-label"' in profile_html
    assert 'data-testid="profile-country-select"' in profile_html
    assert 'data-testid="profile-state-container"' in profile_html
    assert 'data-testid="profile-state-label"' in profile_html
    assert 'data-testid="profile-state-select"' in profile_html
    assert "hidden" in profile_html
    assert 'maxlength="1000"' in profile_html
    assert 'data-testid="profile-save-button"' in profile_html


def test_home_page_has_profile_link() -> None:
    home_html = (REPO_ROOT / "test-site" / "home.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert 'data-testid="site-header"' in home_html
    assert 'data-testid="nav-home"' in home_html
    assert 'data-testid="nav-profile"' in home_html
    assert 'href="profile.html"' in home_html


def test_profile_auth_guard_redirect_exists() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert 'document.getElementById("profile-root")' in app_js
    assert 'requireAuthenticatedUser("profile")' in app_js
    assert "index.html?redirect=${redirectTarget}" in app_js


def test_profile_about_persistence_helpers_exist() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert 'const PROFILES_KEY = "profiles_v1"' in app_js
    assert "function loadProfiles()" in app_js
    assert "function saveProfiles(store)" in app_js
    assert "function getSavedAboutMe(username)" in app_js
    assert "function setSavedAboutMe(username, aboutMe)" in app_js
    assert "function getSavedProfile(username)" in app_js
    assert "function setSavedProfile(username, entry)" in app_js
    assert "const COUNTRY_OPTIONS = [" in app_js
    assert "const US_STATE_OPTIONS = [" in app_js
    assert 'const USA_COUNTRY = "United States of America"' in app_js
    assert (
        "function applyStateVisibility(countrySelect, stateContainer, stateSelect)"
        in app_js
    )


def test_profile_about_length_guard_exists() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert "const ABOUT_ME_MAX_LEN = 1000" in app_js
    assert "function truncateAboutMe(value)" in app_js
    assert ".slice(0, ABOUT_ME_MAX_LEN)" in app_js
    assert "aboutInput.maxLength = ABOUT_ME_MAX_LEN" in app_js
