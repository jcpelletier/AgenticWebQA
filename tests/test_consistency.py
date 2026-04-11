from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from tools import consistency


def test_resolve_command_python_script_uses_repo_relative_path(tmp_path: Path) -> None:
    script_path = tmp_path / "tmp_consistency_target.py"
    script_path.write_text("print('ok')\n", encoding="utf-8")

    command = consistency.resolve_command("tmp_consistency_target.py", [], tmp_path)

    assert command == [sys.executable, str(script_path.resolve())]


def test_resolve_command_strips_separator_for_forwarded_args(tmp_path: Path) -> None:
    command = consistency.resolve_command("pytest", ["--", "-q", "tests"], tmp_path)
    assert command == ["pytest", "-q", "tests"]


def test_parse_args_rejects_non_positive_runs() -> None:
    with pytest.raises(SystemExit):
        consistency.parse_args(["precommit_smoketest.py", "0"])


def test_main_reports_pass_fail_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        consistency,
        "resolve_command",
        lambda *_args, **_kwargs: ["fake-test-command"],
    )

    return_codes = iter([0, 1, 0])

    def _fake_run(_command, cwd, check):  # noqa: ARG001
        return SimpleNamespace(returncode=next(return_codes))

    monkeypatch.setattr(consistency.subprocess, "run", _fake_run)

    monotonic_values = iter(float(i) for i in range(8))
    monkeypatch.setattr(consistency.time, "monotonic", lambda: next(monotonic_values))

    exit_code = consistency.main(["precommit_smoketest.py", "3"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "[consistency]   Passed: 2/3 (66.7%)" in captured.out
    assert "[consistency]   Failed: 1/3 (33.3%)" in captured.out


def test_main_returns_error_when_python_target_is_missing(
    tmp_path: Path, capsys
) -> None:
    missing_script = tmp_path / "missing_target.py"
    exit_code = consistency.main([str(missing_script), "2"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Target script not found" in captured.err


def test_main_runs_target_from_repo_root(monkeypatch) -> None:
    monkeypatch.setattr(
        consistency,
        "resolve_command",
        lambda *_args, **_kwargs: ["fake-test-command"],
    )

    observed: dict[str, Path] = {}

    def _fake_run(_command, cwd, check):  # noqa: ARG001
        observed["cwd"] = Path(cwd)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(consistency.subprocess, "run", _fake_run)

    monotonic_values = iter(float(i) for i in range(4))
    monkeypatch.setattr(consistency.time, "monotonic", lambda: next(monotonic_values))

    exit_code = consistency.main(["precommit_smoketest.py", "1"])

    assert exit_code == 0
    assert observed["cwd"] == Path(consistency.__file__).resolve().parent.parent
