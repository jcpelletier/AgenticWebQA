from vision_playwright_openai_vision_poc import (
    _merge_existing_action_with_fallback_steps,
    _normalize_action_args_for_schema,
    normalize_openai_action_input,
    normalize_playwright_key_combo,
)


def test_normalize_openai_action_input_expands_action_dict() -> None:
    tool_input = {"action": {"type": "click", "x": 10, "y": 20}, "selector": ".btn"}
    action, args = normalize_openai_action_input(tool_input)
    assert action == "left_click"
    assert args["x"] == 10
    assert args["y"] == 20
    assert args["selector"] == ".btn"
    assert "action" not in args


def test_normalize_openai_action_input_from_type_field() -> None:
    tool_input = {"type": "keypress", "key": "Enter"}
    action, args = normalize_openai_action_input(tool_input)
    assert action == "key"
    assert args["key"] == "Enter"


def test_normalize_action_args_for_schema_aliases() -> None:
    args, notes = _normalize_action_args_for_schema("key", {"key_press": "Enter"})
    assert args["key"] == "Enter"
    assert "key_press -> key" in notes

    args, notes = _normalize_action_args_for_schema("left_click", {"position": [5, 6]})
    assert args["x"] == 5
    assert args["y"] == 6
    assert "position -> x,y" in notes

    args, _ = _normalize_action_args_for_schema("type", {"value": "hello"})
    assert args["text"] == "hello"


def test_merge_existing_action_with_fallback_steps_appends_completion() -> None:
    model_data = {
        "functions": [
            {
                "name": "login",
                "steps": [
                    {"action": "click", "selector": "#txtManualName"},
                    {"action": "type", "text": "Automation"},
                    {"action": "click", "selector": "#txtManualPassword"},
                ],
            }
        ]
    }
    fallback_steps = [
        {"action": "type", "selector": "#txtManualPassword", "text": "{password}"},
        {"action": "click", "role": "button", "name": "Sign In"},
    ]
    merged = _merge_existing_action_with_fallback_steps(
        model_data, "login", fallback_steps
    )
    assert merged == [
        {"action": "click", "selector": "#txtManualName"},
        {"action": "type", "text": "Automation"},
        {"action": "click", "selector": "#txtManualPassword"},
        {"action": "type", "selector": "#txtManualPassword", "text": "{password}"},
        {"action": "click", "role": "button", "name": "Sign In"},
    ]


def test_merge_existing_action_with_fallback_steps_removes_overlap() -> None:
    model_data = {
        "functions": [
            {
                "name": "login",
                "steps": [
                    {"action": "click", "selector": "#txtManualName"},
                    {"action": "type", "text": "Automation"},
                ],
            }
        ]
    }
    fallback_steps = [
        {"action": "type", "text": "Automation"},
        {"action": "click", "role": "button", "name": "Sign In"},
    ]
    merged = _merge_existing_action_with_fallback_steps(
        model_data, "login", fallback_steps
    )
    assert merged == [
        {"action": "click", "selector": "#txtManualName"},
        {"action": "type", "text": "Automation"},
        {"action": "click", "role": "button", "name": "Sign In"},
    ]


def test_normalize_playwright_key_combo_uppercase_navigation_keys() -> None:
    assert normalize_playwright_key_combo("HOME") == "Home"
    assert normalize_playwright_key_combo("END") == "End"
    assert normalize_playwright_key_combo("PAGEUP") == "PageUp"
    assert normalize_playwright_key_combo("PAGEDOWN") == "PageDown"


def test_normalize_playwright_key_combo_navigation_with_modifiers() -> None:
    assert normalize_playwright_key_combo("CTRL+HOME") == "Control+Home"
    assert normalize_playwright_key_combo("Shift + PageDown") == "Shift+PageDown"
