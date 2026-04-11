"""
Unit tests for deterministic success-check helpers in
vision_playwright_openai_vision_poc.py.

Tests cover _check_text_present, _check_selector_present, _check_url_match,
and check_deterministic_success dispatch via mocked Playwright Page objects.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import vision_playwright_openai_vision_poc as poc
from config_shared import SuccessIndicatorConfig, SuccessIndicatorType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_page(
    *, body_text: str = "", url: str = "http://example.com/", locator_count: int = 0
) -> MagicMock:
    page = MagicMock()
    page.inner_text.return_value = body_text
    page.url = url
    loc = MagicMock()
    loc.count.return_value = locator_count
    page.locator.return_value = loc
    return page


def _cfg(type_: SuccessIndicatorType, value: str) -> SuccessIndicatorConfig:
    return SuccessIndicatorConfig(type=type_, value=value)


# ---------------------------------------------------------------------------
# _check_text_present
# ---------------------------------------------------------------------------


class TestCheckTextPresent:
    def test_plain_string_found(self) -> None:
        page = _make_page(body_text="Welcome, demo user!")
        cfg = _cfg(SuccessIndicatorType.TEXT_PRESENT, "Welcome, demo")
        assert poc._check_text_present(page, cfg) is True

    def test_plain_string_not_found(self) -> None:
        page = _make_page(body_text="Login failed.")
        cfg = _cfg(SuccessIndicatorType.TEXT_PRESENT, "Welcome, demo")
        assert poc._check_text_present(page, cfg) is False

    def test_regex_match(self) -> None:
        page = _make_page(body_text="Welcome, user_1234 to the site.")
        cfg = _cfg(SuccessIndicatorType.TEXT_PRESENT, r"regex:Welcome, user_\d+")
        assert poc._check_text_present(page, cfg) is True

    def test_regex_no_match(self) -> None:
        page = _make_page(body_text="Error: invalid credentials.")
        cfg = _cfg(SuccessIndicatorType.TEXT_PRESENT, r"regex:Welcome, user_\d+")
        assert poc._check_text_present(page, cfg) is False

    def test_inner_text_exception_returns_false(self) -> None:
        page = MagicMock()
        page.inner_text.side_effect = Exception("timeout")
        cfg = _cfg(SuccessIndicatorType.TEXT_PRESENT, "anything")
        assert poc._check_text_present(page, cfg) is False

    def test_empty_value_matches_any_body(self) -> None:
        """Empty string is always contained in any string."""
        page = _make_page(body_text="Some text")
        cfg = _cfg(SuccessIndicatorType.TEXT_PRESENT, "")
        assert poc._check_text_present(page, cfg) is True


# ---------------------------------------------------------------------------
# _check_selector_present
# ---------------------------------------------------------------------------


class TestCheckSelectorPresent:
    def test_selector_found(self) -> None:
        page = _make_page(locator_count=2)
        cfg = _cfg(
            SuccessIndicatorType.SELECTOR_PRESENT, "[data-testid='home-welcome']"
        )
        assert poc._check_selector_present(page, cfg) is True

    def test_selector_not_found(self) -> None:
        page = _make_page(locator_count=0)
        cfg = _cfg(SuccessIndicatorType.SELECTOR_PRESENT, ".does-not-exist")
        assert poc._check_selector_present(page, cfg) is False

    def test_locator_exception_returns_false(self) -> None:
        page = MagicMock()
        page.locator.side_effect = Exception("invalid selector")
        cfg = _cfg(SuccessIndicatorType.SELECTOR_PRESENT, "!!!bad!!!")
        assert poc._check_selector_present(page, cfg) is False


# ---------------------------------------------------------------------------
# _check_url_match
# ---------------------------------------------------------------------------


class TestCheckUrlMatch:
    def test_plain_contains(self) -> None:
        page = _make_page(url="http://127.0.0.1:8000/home.html")
        cfg = _cfg(SuccessIndicatorType.URL_MATCH, "home.html")
        assert poc._check_url_match(page, cfg) is True

    def test_plain_not_contains(self) -> None:
        page = _make_page(url="http://127.0.0.1:8000/index.html")
        cfg = _cfg(SuccessIndicatorType.URL_MATCH, "home.html")
        assert poc._check_url_match(page, cfg) is False

    def test_regex_match(self) -> None:
        page = _make_page(url="http://127.0.0.1:8000/home.html")
        cfg = _cfg(SuccessIndicatorType.URL_MATCH, r"regex:.*home\.html$")
        assert poc._check_url_match(page, cfg) is True

    def test_regex_no_match(self) -> None:
        page = _make_page(url="http://127.0.0.1:8000/index.html")
        cfg = _cfg(SuccessIndicatorType.URL_MATCH, r"regex:.*home\.html$")
        assert poc._check_url_match(page, cfg) is False


# ---------------------------------------------------------------------------
# check_deterministic_success dispatch
# ---------------------------------------------------------------------------


class TestCheckDeterministicSuccess:
    def test_dispatches_text_present(self) -> None:
        page = _make_page(body_text="Welcome, demo")
        cfg = _cfg(SuccessIndicatorType.TEXT_PRESENT, "Welcome, demo")
        assert poc.check_deterministic_success(page, cfg) is True

    def test_dispatches_selector_present(self) -> None:
        page = _make_page(locator_count=1)
        cfg = _cfg(SuccessIndicatorType.SELECTOR_PRESENT, ".my-class")
        assert poc.check_deterministic_success(page, cfg) is True

    def test_dispatches_url_match(self) -> None:
        page = _make_page(url="http://example.com/dashboard")
        cfg = _cfg(SuccessIndicatorType.URL_MATCH, "dashboard")
        assert poc.check_deterministic_success(page, cfg) is True

    def test_visual_llm_returns_false(self) -> None:
        """VISUAL_LLM is handled by the LLM verify guard, not deterministic checks."""
        page = _make_page(body_text="anything")
        cfg = _cfg(SuccessIndicatorType.VISUAL_LLM, "The user is logged in.")
        assert poc.check_deterministic_success(page, cfg) is False
