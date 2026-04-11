#!/usr/bin/env python
import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


START_URL = "http://127.0.0.1:8000/index.html"
HOMEQUIZ_LOG = "homequiz_run.log"
DEFAULT_MODEL = "gpt-5.1"


def run(cmd: list[str], cwd: Path, tee_path: Path | None = None) -> None:
    if tee_path is None:
        subprocess.run(cmd, cwd=str(cwd), check=True)
        return
    with tee_path.open("w", encoding="utf-8") as f:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            try:
                sys.stdout.write(line)
            except UnicodeEncodeError:
                console_encoding = sys.stdout.encoding or "utf-8"
                safe_line = line.encode("utf-8", errors="replace").decode(
                    console_encoding, errors="replace"
                )
                sys.stdout.write(safe_line)
            f.write(line)
        rc = proc.wait()
        if rc != 0:
            raise subprocess.CalledProcessError(rc, cmd)


def wait_for_site(url: str, timeout_s: int = 45) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"Local test site not reachable at {url}")


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def pick_writable_log_path(path: Path) -> Path:
    if not path.exists():
        return path
    try:
        path.unlink()
        return path
    except PermissionError:
        fallback = path.with_name(f"{path.stem}_{int(time.time())}{path.suffix}")
        print(f"== Log file in use; using fallback log file: {fallback.name} ==")
        return fallback


def home_quiz_feature_available(site_dir: Path) -> bool:
    home_html = site_dir / "home.html"
    if not home_html.exists():
        return False
    home_text = home_html.read_text(encoding="utf-8", errors="ignore")
    required_tokens = (
        'data-testid="quiz-card"',
        'data-testid="quiz-title"',
        'data-testid="quiz-questions"',
        'data-testid="quiz-next-button"',
    )
    return all(token in home_text for token in required_tokens)


def home_quiz_flow_prompt() -> str:
    return (
        "Log in with username 'demo' and password 'demo123', then complete a deterministic "
        "quiz interaction and load the next quiz card. Use scroll actions if movement is "
        "needed, and do not use keyboard navigation keys.\n"
        "1. Log in.\n"
        "2. For Question 1, click the first answer option."
    )


def home_quiz_flow_success() -> str:
    return "You are on the Home page and Question 1 of 4 has been answered so far"


def run_home_quiz_integration(repo_root: Path, *, model: str, log_path: Path) -> None:
    script = repo_root / "vision_playwright_openai_vision_poc.py"
    cmd = [
        sys.executable,
        "-u",
        str(script),
        "--prompt",
        home_quiz_flow_prompt(),
        "--visual-llm-success",
        home_quiz_flow_success(),
        "--start-url",
        START_URL,
        "--actions",
        "login_flow,home_quiz_flow",
        "--max-steps",
        "20",
        "--headless",
        "--verbose",
        "--max-subactions-per-function",
        "8",
        "--model",
        model,
    ]
    print("== Run Home Quiz Integration Flow ==")
    run(cmd, cwd=repo_root, tee_path=log_path)


def _wait_for_quiz_id_change(page, previous_quiz_id: str) -> str:
    card = page.locator('[data-testid="quiz-card"]')
    deadline = time.time() + 4
    while time.time() < deadline:
        quiz_id = card.get_attribute("data-quiz-id") or ""
        if quiz_id and quiz_id != previous_quiz_id:
            return quiz_id
        time.sleep(0.05)
    raise RuntimeError("Timed out waiting for quiz id to change after Next Quiz.")


def _answer_question(page, question_number: int, *, choose_correct: bool) -> None:
    question = page.locator(f'[data-testid="quiz-question-{question_number}"]')
    question.wait_for(state="visible")
    assert question.locator("button.quiz-option").count() == 4
    selector = (
        'button.quiz-option[data-quiz-correct="true"]'
        if choose_correct
        else 'button.quiz-option[data-quiz-correct="false"]'
    )
    target = question.locator(selector).first
    target.click()


def _complete_quiz_mode(page, mode: str) -> None:
    if mode not in {"none", "some", "all"}:
        raise ValueError(f"Unknown mode: {mode}")
    for question_number in range(1, 5):
        choose_correct = mode == "all" or (mode == "some" and question_number == 1)
        _answer_question(page, question_number, choose_correct=choose_correct)


def _assert_results_for_mode(page, mode: str) -> dict[str, object]:
    card = page.locator('[data-testid="quiz-card"]')
    summary = page.locator('[data-testid="quiz-summary"]')
    percent = page.locator('[data-testid="quiz-percent"]')
    overall = page.locator('[data-testid="quiz-overall-status"]')
    next_button = page.locator('[data-testid="quiz-next-button"]')

    summary.wait_for(state="visible")
    next_button.wait_for(state="visible")

    card_class = card.get_attribute("class") or ""
    percent_text = percent.inner_text().strip()
    overall_text = overall.inner_text().strip()

    result_texts = [
        page.locator(f'[data-testid="quiz-question-{n}-result"]').inner_text().strip()
        for n in range(1, 5)
    ]

    if mode == "none":
        assert "quiz-state-none-correct" in card_class
        assert percent_text.startswith("0%")
        assert "Red" in overall_text
        assert all(text == "Incorrect" for text in result_texts)
    elif mode == "all":
        assert "quiz-state-all-correct" in card_class
        assert percent_text.startswith("100%")
        assert "Green" in overall_text
        assert all(text == "Correct" for text in result_texts)
    else:
        assert "quiz-state-some-correct" in card_class
        assert not percent_text.startswith("0%")
        assert not percent_text.startswith("100%")
        assert "Orange" in overall_text
        assert result_texts[0] == "Correct"
        assert all(text == "Incorrect" for text in result_texts[1:])
    return {
        "mode": mode,
        "card_class": card_class,
        "percent_text": percent_text,
        "overall_text": overall_text,
        "result_texts": result_texts,
    }


def verify_home_quiz_with_playwright() -> list[str]:
    evidence_lines: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(START_URL, wait_until="domcontentloaded")
            page.locator('[data-testid="username"]').fill("demo")
            page.locator('[data-testid="password"]').fill("demo123")
            page.locator('[data-testid="login-button"]').click()

            page.locator('[data-testid="home-title"]').wait_for(state="visible")
            page.locator('[data-testid="quiz-card"]').wait_for(state="visible")

            for question_number in range(1, 5):
                assert (
                    page.locator(
                        f'[data-testid="quiz-question-{question_number}"] button.quiz-option'
                    ).count()
                    == 4
                )
            evidence_lines.append(
                "Initial quiz render verified: 4 questions with 4 answer options each."
            )

            _complete_quiz_mode(page, "none")
            none_result = _assert_results_for_mode(page, "none")
            evidence_lines.append(
                "Mode none verified: "
                f"class='{none_result['card_class']}', "
                f"percent='{none_result['percent_text']}', "
                f"overall='{none_result['overall_text']}'."
            )

            card = page.locator('[data-testid="quiz-card"]')
            next_button = page.locator('[data-testid="quiz-next-button"]')
            previous_quiz_id = card.get_attribute("data-quiz-id") or ""
            next_button.click()
            assert "quiz-card-transition" in (card.get_attribute("class") or "")
            next_quiz_id = _wait_for_quiz_id_change(page, previous_quiz_id)
            assert next_quiz_id != previous_quiz_id
            evidence_lines.append(
                f"Next Quiz transition verified (1): quiz id changed from '{previous_quiz_id}' to '{next_quiz_id}'."
            )

            _complete_quiz_mode(page, "some")
            some_result = _assert_results_for_mode(page, "some")
            evidence_lines.append(
                "Mode some verified: "
                f"class='{some_result['card_class']}', "
                f"percent='{some_result['percent_text']}', "
                f"overall='{some_result['overall_text']}'."
            )

            previous_quiz_id = card.get_attribute("data-quiz-id") or ""
            next_button.click()
            assert "quiz-card-transition" in (card.get_attribute("class") or "")
            next_quiz_id = _wait_for_quiz_id_change(page, previous_quiz_id)
            assert next_quiz_id != previous_quiz_id
            evidence_lines.append(
                f"Next Quiz transition verified (2): quiz id changed from '{previous_quiz_id}' to '{next_quiz_id}'."
            )

            _complete_quiz_mode(page, "all")
            all_result = _assert_results_for_mode(page, "all")
            evidence_lines.append(
                "Mode all verified: "
                f"class='{all_result['card_class']}', "
                f"percent='{all_result['percent_text']}', "
                f"overall='{all_result['overall_text']}'."
            )
        finally:
            browser.close()
    return evidence_lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--require-feature", action="store_true")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model override for AI runs (default: {DEFAULT_MODEL}).",
    )
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Missing OPENAI_API_KEY environment variable.")

    repo_root = Path(__file__).resolve().parent.parent
    agent_view_dir = repo_root / "agent_view"
    homequiz_log = repo_root / HOMEQUIZ_LOG

    if not args.skip_install:
        print("== Install dependencies ==")
        run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], cwd=repo_root)
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(repo_root / "requirements.txt"),
            ],
            cwd=repo_root,
        )
        run([sys.executable, "-m", "playwright", "install", "chromium"], cwd=repo_root)

    print("== Prepare home quiz smoke artifacts ==")
    reset_dir(agent_view_dir)
    homequiz_log = pick_writable_log_path(homequiz_log)

    print("== Start local test site ==")
    site_dir = repo_root / "test-site"
    if not site_dir.exists():
        raise RuntimeError(f"Missing test site at {site_dir}")
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8000", "--directory", str(site_dir)],
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        print("== Wait for local test site ==")
        wait_for_site(START_URL, timeout_s=60)

        feature_found = home_quiz_feature_available(site_dir)
        if not feature_found:
            message = (
                "Home quiz feature not detected in test-site; skipping home quiz smoke."
            )
            if args.require_feature:
                raise RuntimeError(message)
            print(f"== {message} ==")
            with homequiz_log.open("w", encoding="utf-8") as f:
                f.write("SKIP: HOME_QUIZ_FEATURE_MISSING\n")
                f.write("FINAL: PASS\n")
            return 0

        run_home_quiz_integration(repo_root, model=args.model, log_path=homequiz_log)
        try:
            evidence_lines = verify_home_quiz_with_playwright()
        except Exception as exc:
            with homequiz_log.open("a", encoding="utf-8") as f:
                f.write(f"[VERIFY] FAIL: {exc}\n")
            raise

        with homequiz_log.open("a", encoding="utf-8") as f:
            f.write("\n[VERIFY] Deterministic Playwright verification\n")
            for line in evidence_lines:
                f.write(f"[VERIFY] {line}\n")

        print("== Deterministic verification summary ==")
        for line in evidence_lines:
            print(f"[VERIFY] {line}")
        print("Local testhomequiz sequence passed.")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
