from types import SimpleNamespace

from vision_playwright_openai_vision_poc import (
    extract_final_verdict,
    extract_final_verdict_from_text,
)


def test_extract_final_verdict_from_blocks() -> None:
    blocks = [SimpleNamespace(type="text", text="Done.\nFINAL: pass")]
    assert extract_final_verdict(blocks) == "PASS"


def test_extract_final_verdict_from_text() -> None:
    assert extract_final_verdict_from_text("All good.\nFINAL: FAIL") == "FAIL"
    assert extract_final_verdict_from_text("") is None
