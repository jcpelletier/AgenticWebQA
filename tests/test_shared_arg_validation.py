import argparse

import pytest

from config_shared import add_shared_cli_arguments, parse_ui_value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    add_shared_cli_arguments(parser)
    return parser


def test_parse_ui_value_accepts_valid_edge_values() -> None:
    assert parse_ui_value("0", flag="--max-tokens") == 0
    assert parse_ui_value("0", flag="--model-width") == 0
    assert parse_ui_value("1", flag="--max-steps") == 1
    assert parse_ui_value("0", flag="--pre-click-sleep") == 0.0


def test_parse_ui_value_rejects_out_of_range_values() -> None:
    with pytest.raises(ValueError, match=r"Max steps must be >= 1"):
        parse_ui_value("0", flag="--max-steps")
    with pytest.raises(ValueError, match=r"Width must be >= 1"):
        parse_ui_value("0", flag="--width")
    with pytest.raises(ValueError, match=r"Pre-click sleep must be >= 0"):
        parse_ui_value("-0.1", flag="--pre-click-sleep")


def test_cli_parser_rejects_out_of_range_values() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--max-steps", "0"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--width", "0"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--pre-click-sleep", "-0.1"])


def test_cli_parser_accepts_valid_edge_values() -> None:
    parser = _build_parser()
    ns = parser.parse_args(
        ["--max-steps", "1", "--width", "1", "--pre-click-sleep", "0"]
    )
    assert ns.max_steps == 1
    assert ns.width == 1
    assert ns.pre_click_sleep == 0.0
