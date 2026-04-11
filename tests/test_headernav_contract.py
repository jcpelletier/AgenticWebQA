from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_site_file(name: str) -> str:
    return (REPO_ROOT / "test-site" / name).read_text(encoding="utf-8", errors="ignore")


def test_home_header_navigation_contract() -> None:
    home_html = _read_site_file("home.html")
    assert 'data-testid="site-header"' in home_html
    assert 'data-testid="nav-home"' in home_html
    assert 'aria-current="page"' in home_html
    assert 'data-testid="nav-profile"' in home_html
    assert 'href="profile.html"' in home_html
    assert 'data-testid="profile-link"' not in home_html
    assert 'class="alt-action"' not in home_html


def test_profile_header_navigation_contract() -> None:
    profile_html = _read_site_file("profile.html")
    assert 'data-testid="site-header"' in profile_html
    assert 'data-testid="nav-home"' in profile_html
    assert 'href="home.html"' in profile_html
    assert 'data-testid="nav-profile"' in profile_html
    assert 'aria-current="page"' in profile_html


def test_header_styles_define_active_black_label() -> None:
    styles = _read_site_file("styles.css")
    assert ".site-header" in styles
    assert ".site-nav" in styles
    assert ".active-label" in styles
    assert "color: #000;" in styles
