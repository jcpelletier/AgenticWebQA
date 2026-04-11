from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_app_js() -> str:
    return (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )


def test_country_dropdown_contract_has_usa_first_then_alpha_examples() -> None:
    app_js = _read_app_js()
    assert 'const USA_COUNTRY = "United States of America"' in app_js
    assert 'USA_COUNTRY,\n    "Afghanistan",' in app_js
    assert '"United Kingdom",' in app_js
    assert '"Uruguay",' in app_js
    assert '"Zimbabwe",' in app_js


def test_state_visibility_and_wipe_contract_exists() -> None:
    app_js = _read_app_js()
    assert "const showState = countrySelect.value === USA_COUNTRY;" in app_js
    assert "if (!showState) {" in app_js
    assert 'stateSelect.value = "";' in app_js
    assert (
        'const state = country === USA_COUNTRY ? normalizeState(entry?.state || "") : "";'
        in app_js
    )
