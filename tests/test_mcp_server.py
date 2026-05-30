import json

import agenticwebqa.mcp_server as m


def _write_registry(tmp_path, data):
    path = tmp_path / "tests_registry.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_list_tests_reads_registry(tmp_path):
    reg = _write_registry(
        tmp_path,
        {
            "a": {
                "prompt": "p",
                "success_criteria": "s",
                "start_url": "u",
                "actions": "x",
                "model": "Sonnet 4.6",
            }
        },
    )
    out = m._list_tests(registry_path=str(reg))
    assert out["count"] == 1
    assert "a" in out["tests"]
    assert out["registry"] == str(reg)


def test_list_tests_missing_registry_is_empty(tmp_path):
    out = m._list_tests(registry_path=str(tmp_path / "nope.json"))
    assert out["count"] == 0
    assert out["tests"] == {}


def test_run_test_requires_fields():
    out = m._run_test()
    assert out["ok"] is False
    assert "required" in out["error"]


def test_run_test_unknown_name(tmp_path):
    reg = _write_registry(tmp_path, {})
    out = m._run_test(name="nope", registry_path=str(reg))
    assert out["ok"] is False
    assert "not found" in out["error"]
    assert out["available"] == []


def test_run_test_invalid_success_type():
    out = m._run_test(
        prompt="p", start_url="u", success_criteria="s", success_type="bogus"
    )
    assert out["ok"] is False
    assert "visual" in out["valid_success_types"]


class _FakeProc:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_run_test_named_pass_builds_command(tmp_path, monkeypatch):
    reg = _write_registry(
        tmp_path,
        {
            "login": {
                "prompt": "do login",
                "success_criteria": "welcome",
                "start_url": "http://x/",
                "actions": "login",
                "model": "Haiku 4.5",
            }
        },
    )
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _FakeProc(stdout="step 1\nFINAL: PASS\n", returncode=0)

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    out = m._run_test(name="login", registry_path=str(reg), cwd=str(tmp_path))

    assert out["verdict"] == "PASS"
    assert out["ok"] is True
    cmd = captured["cmd"]
    assert "-m" in cmd and "agenticwebqa" in cmd
    assert "--visual-llm-success" in cmd and "welcome" in cmd
    assert "do login" in cmd and "http://x/" in cmd
    assert "--actions" in cmd and "login" in cmd
    assert "--model" in cmd and "Haiku 4.5" in cmd
    assert "--headless" in cmd
    assert captured["kwargs"]["cwd"] == str(tmp_path)
    assert (tmp_path / "mcp_run_login.log").is_file()


def test_run_test_adhoc_fail_text_success(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProc(stderr="boom\nFINAL: FAIL\n", returncode=1)

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    out = m._run_test(
        prompt="p",
        start_url="u",
        success_criteria="s",
        success_type="text",
        headless=False,
        cwd=str(tmp_path),
    )
    assert out["verdict"] == "FAIL"
    assert out["ok"] is False
    assert "--text-present-success" in captured["cmd"]
    assert "--headless" not in captured["cmd"]


def test_run_test_timeout(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise m.subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 1))

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    out = m._run_test(
        prompt="p", start_url="u", success_criteria="s", cwd=str(tmp_path)
    )
    assert out["ok"] is False
    assert out["verdict"] == "TIMEOUT"
