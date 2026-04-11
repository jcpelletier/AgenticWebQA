from __future__ import annotations

import sys
from pathlib import Path

import vision_playwright_openai_vision_ui as ui


def test_build_command_and_launch(monkeypatch, tmp_path) -> None:
    values = {
        "-PROMPT-": "Do thing",
        "-SUCCESS-": "Done",
        "-STARTURL-": "example.com",
        "-STEP-TRAIN-": True,
    }
    step_signal = tmp_path / ".step_training_signal"
    cmd = ui._build_command(values, step_training_signal=step_signal)

    assert cmd[0] == sys.executable
    assert "--prompt" in cmd
    assert "--success-criteria" in cmd
    assert "--start-url" in cmd
    assert str(step_signal) in cmd

    launched = {}

    def _fake_popen(*args, **kwargs):
        launched["args"] = args
        launched["kwargs"] = kwargs

        class _Proc:
            stdout = []

        return _Proc()

    monkeypatch.setattr(ui.subprocess, "Popen", _fake_popen)

    env = {"OPENAI_API_KEY": "x"}
    proc = ui._launch_command(cmd, cwd=str(tmp_path), env=env)
    assert proc is not None
    assert launched["args"][0] == cmd
    assert launched["kwargs"]["cwd"] == str(tmp_path)
    assert launched["kwargs"]["env"] == env
