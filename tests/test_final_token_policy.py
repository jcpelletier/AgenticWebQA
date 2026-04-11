from __future__ import annotations

import logging

import vision_playwright_openai_vision_poc as vp


def _reset_logger() -> None:
    if getattr(vp, "LOGGER", None):
        for handler in list(vp.LOGGER.handlers):
            vp.LOGGER.removeHandler(handler)
        vp.LOGGER.setLevel(logging.NOTSET)
    if hasattr(vp.LOGGER, "_configured"):
        delattr(vp.LOGGER, "_configured")


def test_log_final_emits_once_on_success(capsys) -> None:
    _reset_logger()
    state = vp.FinalTokenState()
    vp._log_final("PASS", state)
    vp._log_final("PASS", state)
    out = capsys.readouterr().out
    assert out.count("FINAL: PASS") == 1


def test_log_final_emits_once_on_failure(capsys) -> None:
    _reset_logger()
    state = vp.FinalTokenState()
    vp._log_final("FAIL", state)
    vp._log_final("FAIL", state)
    out = capsys.readouterr().out
    assert out.count("FINAL: FAIL") == 1


def test_log_info_squelches_final_tokens(capsys) -> None:
    _reset_logger()
    vp._log_info("Noise before FINAL: PASS should be removed.")
    out = capsys.readouterr().out
    assert "FINAL: PASS" not in out
