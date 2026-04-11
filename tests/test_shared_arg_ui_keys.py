import ast
from pathlib import Path

from config_shared import SHARED_ARG_SPECS


def _extract_ui_settings_keys_from_ui_file() -> set[str]:
    ui_path = (
        Path(__file__).resolve().parents[1] / "vision_playwright_openai_vision_ui.py"
    )
    source = ui_path.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(ui_path))

    for node in module.body:
        value = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "UI_SETTINGS_KEYS":
                    value = node.value
                    break
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id == "UI_SETTINGS_KEYS"
            ):
                value = node.value

        if value is None:
            continue
        if not isinstance(value, ast.Tuple):
            raise AssertionError("UI_SETTINGS_KEYS must be a tuple literal.")
        keys: set[str] = set()
        for elt in value.elts:
            if not isinstance(elt, ast.Constant) or not isinstance(elt.value, str):
                raise AssertionError(
                    "UI_SETTINGS_KEYS entries must be string literals."
                )
            keys.add(elt.value)
        return keys

    raise AssertionError(
        "UI_SETTINGS_KEYS constant not found in vision_playwright_openai_vision_ui.py."
    )


def _extract_outside_vars_map_keys_from_ui_file() -> set[str]:
    ui_path = (
        Path(__file__).resolve().parents[1] / "vision_playwright_openai_vision_ui.py"
    )
    source = ui_path.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(ui_path))

    for node in module.body:
        value = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "UI_KEYS_MANAGED_OUTSIDE_VARS_MAP"
                ):
                    value = node.value
                    break
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id == "UI_KEYS_MANAGED_OUTSIDE_VARS_MAP"
            ):
                value = node.value

        if value is None:
            continue
        if not isinstance(value, ast.Tuple):
            raise AssertionError(
                "UI_KEYS_MANAGED_OUTSIDE_VARS_MAP must be a tuple literal."
            )
        keys: set[str] = set()
        for elt in value.elts:
            if not isinstance(elt, ast.Constant) or not isinstance(elt.value, str):
                raise AssertionError(
                    "UI_KEYS_MANAGED_OUTSIDE_VARS_MAP entries must be string literals."
                )
            keys.add(elt.value)
        return keys

    return set()


def test_ui_settings_keys_match_shared_arg_specs() -> None:
    spec_ui_keys = {spec.ui_key for spec in SHARED_ARG_SPECS if spec.ui_key}
    ui_settings_keys = _extract_ui_settings_keys_from_ui_file()
    excluded_keys = _extract_outside_vars_map_keys_from_ui_file()
    expected_ui_settings_keys = spec_ui_keys - excluded_keys

    missing_in_ui = sorted(expected_ui_settings_keys - ui_settings_keys)
    missing_in_specs = sorted(ui_settings_keys - expected_ui_settings_keys)

    assert not missing_in_ui, (
        f"UI_SETTINGS_KEYS missing keys from expected shared UI keys: {missing_in_ui}"
    )
    assert not missing_in_specs, (
        f"UI_SETTINGS_KEYS has keys not present in expected shared UI keys: {missing_in_specs}"
    )
