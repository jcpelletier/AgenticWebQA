from __future__ import annotations

from types import SimpleNamespace

from cli_entry import parse_cli_args
import vision_playwright_openai_vision_poc as poc


class _DummyPage:
    def __init__(self) -> None:
        self.url = "about:blank"

    def goto(self, url: str, wait_until: str | None = None) -> None:
        self.url = url

    def title(self) -> str:
        return "Example"

    def screenshot(self, **_kwargs: object) -> bytes:
        return b"png"


class _DummyContext:
    def __init__(self) -> None:
        self._page = _DummyPage()

    def new_page(self) -> _DummyPage:
        return self._page

    def close(self) -> None:
        pass


class _DummyBrowser:
    def new_context(self, **_kwargs: object) -> _DummyContext:
        return _DummyContext()

    def close(self) -> None:
        pass


class _DummyChromium:
    def launch(self, **_kwargs: object) -> _DummyBrowser:
        return _DummyBrowser()


class _DummyPlaywright:
    chromium = _DummyChromium()

    def __enter__(self) -> "_DummyPlaywright":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        return None


def _dummy_sync_playwright() -> _DummyPlaywright:
    return _DummyPlaywright()


class _DummyOpenAI:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key


class _DummyClientAdapter:
    def __init__(self, provider: str, api_key: str) -> None:
        self.provider = provider
        self.api_key = api_key
        self.responses = SimpleNamespace(create=lambda **_kwargs: None)


def test_run_cli_with_args_smoke(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(poc, "sync_playwright", _dummy_sync_playwright)
    monkeypatch.setattr(
        poc,
        "_new_model_client",
        lambda model_name, api_key: _DummyClientAdapter(
            poc.infer_model_provider(model_name), api_key
        ),
    )
    monkeypatch.setattr(poc, "ensure_dir", lambda path: str(tmp_path / path))
    monkeypatch.setattr(
        poc,
        "load_page_model",
        lambda path, start_url: {
            "start_url": start_url,
            "functions": [],
            "prompt_routes": [],
        },
    )
    monkeypatch.setattr(poc, "save_page_model", lambda path, data: None)
    monkeypatch.setattr(poc, "_init_azure_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        poc, "capture_model_screenshot_png", lambda *_args, **_kwargs: b"png"
    )

    called = SimpleNamespace(count=0, args=None, kwargs=None)

    def _fake_run_agent(*args, **kwargs):
        called.count += 1
        called.args = args
        called.kwargs = kwargs
        return poc.RunOutcome(verdict="PASS", actions=[])

    monkeypatch.setattr(poc, "run_agent", _fake_run_agent)

    args = parse_cli_args(
        [
            "--prompt",
            "Open example.com",
            "--visual-llm-success",
            "Example",
            "--start-url",
            "example.com",
            "--no-agent-view",
        ]
    )

    poc.run_cli_with_args(args)

    assert called.count == 1
    assert called.kwargs is not None
    assert called.kwargs.get("task_prompt") == "Open example.com"
    indicator = called.kwargs.get("success_indicator")
    assert indicator is not None
    assert indicator.type == poc.SuccessIndicatorType.VISUAL_LLM
    assert indicator.value == "Example"
