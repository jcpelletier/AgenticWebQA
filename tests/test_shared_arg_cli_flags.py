import argparse

from config_shared import SHARED_ARG_SPECS, add_shared_cli_arguments


def test_cli_parser_flags_match_shared_arg_specs() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    add_shared_cli_arguments(parser)

    parser_flags = set()
    for action in parser._actions:
        for option in action.option_strings:
            if option.startswith("--"):
                parser_flags.add(option)

    spec_flags = {spec.flag for spec in SHARED_ARG_SPECS}

    missing_in_parser = sorted(spec_flags - parser_flags)
    extra_in_parser = sorted(parser_flags - spec_flags)

    assert not missing_in_parser, (
        f"Parser missing flags from SHARED_ARG_SPECS: {missing_in_parser}"
    )
    assert not extra_in_parser, (
        f"Parser has flags not present in SHARED_ARG_SPECS: {extra_in_parser}"
    )
