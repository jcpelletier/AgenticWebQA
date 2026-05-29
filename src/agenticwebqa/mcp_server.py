"""MCP server exposing the AgenticWebQA engine.

Tools:
- ``list_tests``: enumerate tests defined in a ``tests_registry.json``.
- ``run_test``: run a registered test (by name) or an ad-hoc spec, headless,
  and return its ``FINAL: PASS`` / ``FINAL: FAIL`` verdict.

The engine itself is invoked as ``python -m agenticwebqa``. Provider API keys
(``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY`` / ``GEMINI_API_KEY``) and optional
``WEBQA_USERNAME`` / ``WEBQA_PASSWORD`` are read from the environment, which the
plugin's ``.mcp.json`` passes through.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("agenticwebqa")

SUCCESS_FLAGS: dict[str, str] = {
    "visual": "--visual-llm-success",
    "text": "--text-present-success",
    "selector": "--selector-present-success",
    "url": "--url-match-success",
}


def _registry_path(registry_path: Optional[str]) -> Path:
    if registry_path:
        return Path(registry_path).expanduser()
    env = os.environ.get("AGENTICWEBQA_REGISTRY")
    if env:
        return Path(env).expanduser()
    return Path.cwd() / "tests_registry.json"


def _load_registry(registry_path: Optional[str]) -> dict[str, Any]:
    path = _registry_path(registry_path)
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _list_tests(registry_path: Optional[str] = None) -> dict[str, Any]:
    registry = _load_registry(registry_path)
    return {
        "registry": str(_registry_path(registry_path)),
        "count": len(registry),
        "tests": registry,
    }


def _run_test(
    name: Optional[str] = None,
    prompt: Optional[str] = None,
    start_url: Optional[str] = None,
    success_criteria: Optional[str] = None,
    success_type: str = "visual",
    actions: Optional[str] = None,
    model: Optional[str] = None,
    max_steps: int = 20,
    headless: bool = True,
    max_subactions_per_function: int = 5,
    timeout_seconds: int = 600,
    registry_path: Optional[str] = None,
    cwd: Optional[str] = None,
) -> dict[str, Any]:
    if name:
        registry = _load_registry(registry_path)
        spec = registry.get(name)
        if spec is None:
            return {
                "ok": False,
                "error": f"test '{name}' not found in registry",
                "available": sorted(registry),
            }
        prompt = prompt or spec.get("prompt")
        start_url = start_url or spec.get("start_url")
        success_criteria = success_criteria or spec.get("success_criteria")
        actions = actions or spec.get("actions")
        model = model or spec.get("model")
        success_type = spec.get("success_type", success_type)

    if not prompt or not start_url or not success_criteria:
        return {
            "ok": False,
            "error": (
                "prompt, start_url, and success_criteria are required "
                "(supply them directly or via a registered test name)"
            ),
        }

    success_flag = SUCCESS_FLAGS.get(success_type)
    if success_flag is None:
        return {
            "ok": False,
            "error": f"invalid success_type '{success_type}'",
            "valid_success_types": sorted(SUCCESS_FLAGS),
        }

    cmd = [
        sys.executable,
        "-u",
        "-m",
        "agenticwebqa",
        "--prompt",
        prompt,
        success_flag,
        success_criteria,
        "--start-url",
        start_url,
        "--max-steps",
        str(max_steps),
        "--max-subactions-per-function",
        str(max_subactions_per_function),
        "--verbose",
    ]
    if headless:
        cmd.append("--headless")
    if actions:
        cmd.extend(["--actions", actions])
    if model:
        cmd.extend(["--model", model])

    run_cwd = cwd or os.getcwd()
    try:
        proc = subprocess.run(
            cmd,
            cwd=run_cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "verdict": "TIMEOUT",
            "error": f"run exceeded {timeout_seconds}s",
            "command": cmd,
        }

    output = (proc.stdout or "") + (proc.stderr or "")
    if "FINAL: PASS" in output:
        verdict = "PASS"
    elif "FINAL: FAIL" in output:
        verdict = "FAIL"
    else:
        verdict = "UNKNOWN"

    log_path: Optional[Path] = Path(run_cwd) / f"mcp_run_{name or 'adhoc'}.log"
    try:
        log_path.write_text(output, encoding="utf-8")  # type: ignore[union-attr]
    except OSError:
        log_path = None

    tail = "\n".join(output.splitlines()[-40:])
    return {
        "ok": proc.returncode == 0 and verdict == "PASS",
        "verdict": verdict,
        "returncode": proc.returncode,
        "log_path": str(log_path) if log_path else None,
        "log_tail": tail,
        "command": cmd,
    }


@mcp.tool()
def list_tests(registry_path: Optional[str] = None) -> dict[str, Any]:
    """List AgenticWebQA tests defined in a tests_registry.json file.

    Each entry maps a test name to its spec: prompt, success_criteria,
    start_url, actions, and model. By default reads ``tests_registry.json`` in
    the current working directory; override with ``registry_path`` or the
    ``AGENTICWEBQA_REGISTRY`` environment variable.
    """
    return _list_tests(registry_path)


@mcp.tool()
def run_test(
    name: Optional[str] = None,
    prompt: Optional[str] = None,
    start_url: Optional[str] = None,
    success_criteria: Optional[str] = None,
    success_type: str = "visual",
    actions: Optional[str] = None,
    model: Optional[str] = None,
    max_steps: int = 20,
    headless: bool = True,
    max_subactions_per_function: int = 5,
    timeout_seconds: int = 600,
    registry_path: Optional[str] = None,
    cwd: Optional[str] = None,
) -> dict[str, Any]:
    """Run an AgenticWebQA test headless and return its PASS/FAIL verdict.

    Provide ``name`` to run a registered test, or supply ``prompt``,
    ``start_url`` and ``success_criteria`` for an ad-hoc run. ``success_type``
    is one of: visual, text, selector, url. Returns the verdict, exit code, a
    log tail, and the path to the full captured log.
    """
    return _run_test(
        name=name,
        prompt=prompt,
        start_url=start_url,
        success_criteria=success_criteria,
        success_type=success_type,
        actions=actions,
        model=model,
        max_steps=max_steps,
        headless=headless,
        max_subactions_per_function=max_subactions_per_function,
        timeout_seconds=timeout_seconds,
        registry_path=registry_path,
        cwd=cwd,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
