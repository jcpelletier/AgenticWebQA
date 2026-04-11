import argparse
import sys

import pytest

from cli_entry import build_parser, parse_cli_args, prepare_args
from config_shared import SuccessIndicatorType


def test_build_parser_accepts_visual_llm_success() -> None:
    parser = build_parser()
    ns = parser.parse_args(
        [
            "--prompt",
            "do thing",
            "--visual-llm-success",
            "done",
            "--start-url",
            "example.com",
        ]
    )
    assert ns.prompt == "do thing"
    assert ns.visual_llm_success == "done"
    assert ns.start_url == "example.com"


def test_build_parser_accepts_text_present_success() -> None:
    parser = build_parser()
    ns = parser.parse_args(
        [
            "--prompt",
            "do thing",
            "--text-present-success",
            "Welcome",
            "--start-url",
            "example.com",
        ]
    )
    assert ns.text_present_success == "Welcome"


def test_build_parser_accepts_selector_present_success() -> None:
    parser = build_parser()
    ns = parser.parse_args(
        [
            "--prompt",
            "do thing",
            "--selector-present-success",
            ".user-menu",
            "--start-url",
            "example.com",
        ]
    )
    assert ns.selector_present_success == ".user-menu"


def test_build_parser_accepts_url_match_success() -> None:
    parser = build_parser()
    ns = parser.parse_args(
        [
            "--prompt",
            "do thing",
            "--url-match-success",
            "/home.html",
            "--start-url",
            "example.com",
        ]
    )
    assert ns.url_match_success == "/home.html"


def test_prepare_args_sets_success_indicator_visual_llm() -> None:
    args = argparse.Namespace(
        visual_llm_success="done",
        text_present_success=None,
        selector_present_success=None,
        url_match_success=None,
        headless=True,
        step_training=False,
        step_training_signal="",
        start_url="https://example.com",
    )
    updated = prepare_args(args)
    assert updated.success_indicator.type == SuccessIndicatorType.VISUAL_LLM
    assert updated.success_indicator.value == "done"


def test_prepare_args_sets_success_indicator_text_present() -> None:
    args = argparse.Namespace(
        visual_llm_success=None,
        text_present_success="Welcome",
        selector_present_success=None,
        url_match_success=None,
        headless=False,
        step_training=False,
        step_training_signal="",
        start_url="https://example.com",
    )
    updated = prepare_args(args)
    assert updated.success_indicator.type == SuccessIndicatorType.TEXT_PRESENT
    assert updated.success_indicator.value == "Welcome"


def test_prepare_args_sets_success_indicator_selector_present() -> None:
    args = argparse.Namespace(
        visual_llm_success=None,
        text_present_success=None,
        selector_present_success=".user-menu",
        url_match_success=None,
        headless=False,
        step_training=False,
        step_training_signal="",
        start_url="https://example.com",
    )
    updated = prepare_args(args)
    assert updated.success_indicator.type == SuccessIndicatorType.SELECTOR_PRESENT
    assert updated.success_indicator.value == ".user-menu"


def test_prepare_args_sets_success_indicator_url_match() -> None:
    args = argparse.Namespace(
        visual_llm_success=None,
        text_present_success=None,
        selector_present_success=None,
        url_match_success="/home.html",
        headless=False,
        step_training=False,
        step_training_signal="",
        start_url="https://example.com",
    )
    updated = prepare_args(args)
    assert updated.success_indicator.type == SuccessIndicatorType.URL_MATCH
    assert updated.success_indicator.value == "/home.html"


def test_prepare_args_zero_indicators_exits(capsys) -> None:
    args = argparse.Namespace(
        visual_llm_success=None,
        text_present_success=None,
        selector_present_success=None,
        url_match_success=None,
        headless=False,
        step_training=False,
        step_training_signal="",
        start_url="https://example.com",
    )
    with pytest.raises(SystemExit) as exc_info:
        prepare_args(args)
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "success indicator is required" in captured.err


def test_prepare_args_two_indicators_exits(capsys) -> None:
    args = argparse.Namespace(
        visual_llm_success="done",
        text_present_success="Welcome",
        selector_present_success=None,
        url_match_success=None,
        headless=False,
        step_training=False,
        step_training_signal="",
        start_url="https://example.com",
    )
    with pytest.raises(SystemExit) as exc_info:
        prepare_args(args)
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "only one success indicator" in captured.err


def test_deprecated_flag_exits(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        parse_cli_args(
            [
                "--prompt",
                "run",
                "--success-criteria",
                "done",
                "--start-url",
                "example.com",
            ]
        )
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "--success-criteria has been removed" in captured.err
    assert "--visual-llm-success" in captured.err


def test_prepare_args_disables_step_training_in_headless_mode() -> None:
    args = argparse.Namespace(
        visual_llm_success="done",
        text_present_success=None,
        selector_present_success=None,
        url_match_success=None,
        headless=True,
        step_training=True,
        step_training_signal="",
        start_url="https://example.com",
    )
    updated = prepare_args(args)
    assert updated.step_training is False


def test_prepare_args_initializes_signal_file_when_step_training_enabled(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    args = argparse.Namespace(
        visual_llm_success="done",
        text_present_success=None,
        selector_present_success=None,
        url_match_success=None,
        headless=False,
        step_training=True,
        step_training_signal="",
        start_url="https://example.com",
    )
    updated = prepare_args(args)
    assert updated.step_training is True
    assert updated.step_training_signal
    signal_path = tmp_path / ".step_training_signal"
    assert signal_path.exists()
    assert signal_path.read_text(encoding="utf-8") == "0"


def test_prepare_args_adds_https_scheme_to_bare_start_url() -> None:
    args = argparse.Namespace(
        visual_llm_success="done",
        text_present_success=None,
        selector_present_success=None,
        url_match_success=None,
        headless=False,
        step_training=False,
        step_training_signal="",
        start_url="example.com",
    )
    updated = prepare_args(args)
    assert updated.start_url == "https://example.com"


def test_parse_cli_args_applies_prepare_logic(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    args = parse_cli_args(
        [
            "--prompt",
            "run",
            "--visual-llm-success",
            "done",
            "--start-url",
            "example.com",
            "--headless",
            "--step-training",
        ]
    )
    assert args.start_url == "https://example.com"
    assert args.step_training is False
    assert args.success_indicator.type == SuccessIndicatorType.VISUAL_LLM
    assert args.success_indicator.value == "done"
