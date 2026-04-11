import argparse

from cli_entry import build_parser, parse_cli_args, prepare_args


def test_build_parser_requires_core_arguments() -> None:
    parser = build_parser()
    ns = parser.parse_args(
        [
            "--prompt",
            "do thing",
            "--success-criteria",
            "done",
            "--start-url",
            "example.com",
        ]
    )
    assert ns.prompt == "do thing"
    assert ns.success_criteria == "done"
    assert ns.start_url == "example.com"


def test_prepare_args_disables_step_training_in_headless_mode() -> None:
    args = argparse.Namespace(
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
            "--success-criteria",
            "done",
            "--start-url",
            "example.com",
            "--headless",
            "--step-training",
        ]
    )
    assert args.start_url == "https://example.com"
    assert args.step_training is False
