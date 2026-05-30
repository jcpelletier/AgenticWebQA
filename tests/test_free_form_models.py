from agenticwebqa.config import infer_model_provider, model_api_env_var


def test_free_form_model_inference():
    # Test arbitrary names
    assert infer_model_provider("my-custom-gpt-model") == "openai"
    assert model_api_env_var("my-custom-gpt-model") == "OPENAI_API_KEY"

    assert infer_model_provider("claude-4.8-super-opus") == "anthropic"
    assert model_api_env_var("claude-4.8-super-opus") == "ANTHROPIC_API_KEY"

    assert infer_model_provider("gemini-4.0-ultra") == "gemini"
    assert model_api_env_var("gemini-4.0-ultra") == "GEMINI_API_KEY"


def test_new_anthropic_keyword_inference():
    # Test that the new keywords also trigger anthropic provider
    assert infer_model_provider("claude-opus-4-8") == "anthropic"
    assert infer_model_provider("claude-sonnet-4-7") == "anthropic"
    assert infer_model_provider("claude-haiku-4-6") == "anthropic"

    assert model_api_env_var("claude-opus-4-8") == "ANTHROPIC_API_KEY"
    assert model_api_env_var("claude-sonnet-4-7") == "ANTHROPIC_API_KEY"
    assert model_api_env_var("claude-haiku-4-6") == "ANTHROPIC_API_KEY"
