from __future__ import annotations

from config_shared import MODEL_OPTIONS, infer_model_provider, model_api_env_var
from vision_playwright_openai_vision_poc import _coerce_openai_input_to_anthropic


def test_model_options_include_multiple_claude_entries() -> None:
    claude_models = [m for m in MODEL_OPTIONS if m.startswith("claude-")]
    assert len(claude_models) >= 3


def test_provider_and_env_mapping_for_models() -> None:
    assert infer_model_provider("gpt-5.1") == "openai"
    assert model_api_env_var("gpt-5.1") == "OPENAI_API_KEY"
    assert infer_model_provider("claude-sonnet-4-5") == "anthropic"
    assert model_api_env_var("claude-sonnet-4-5") == "ANTHROPIC_API_KEY"


def test_openai_input_is_coerced_for_anthropic_messages() -> None:
    input_items = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "hello"},
                {"type": "input_image", "image_url": "data:image/png;base64,abcd"},
            ],
        }
    ]
    messages, system_text = _coerce_openai_input_to_anthropic(input_items)
    assert system_text is None
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"][0]["type"] == "text"
    assert messages[0]["content"][0]["text"] == "hello"
    assert messages[0]["content"][1]["type"] == "image"
