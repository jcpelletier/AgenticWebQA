from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_site_file(name: str) -> str:
    return (REPO_ROOT / "test-site" / name).read_text(encoding="utf-8", errors="ignore")


def test_home_quiz_markup_contract() -> None:
    home_html = _read_site_file("home.html")
    assert 'class="card home-card"' in home_html
    assert 'data-testid="quiz-card"' in home_html
    assert 'data-testid="quiz-title"' in home_html
    assert 'data-testid="quiz-progress"' in home_html
    assert 'data-testid="quiz-questions"' in home_html
    assert 'data-testid="quiz-summary"' in home_html
    assert 'data-testid="quiz-percent"' in home_html
    assert 'data-testid="quiz-overall-status"' in home_html
    assert 'data-testid="quiz-next-button"' in home_html
    assert "Next Quiz" in home_html


def test_quiz_bank_contract_enforces_20_quizzes_with_4x4_shape() -> None:
    app_js = _read_site_file("app.js")
    assert "const QUIZ_BANK_SIZE = 20;" in app_js
    assert "const QUIZ_QUESTION_COUNT = 4;" in app_js
    assert "const QUIZ_OPTIONS_COUNT = 4;" in app_js
    assert "function buildGeneratedQuiz(quizNumber)" in app_js
    assert "const QUIZ_BANK = Array.from({ length: QUIZ_BANK_SIZE }" in app_js
    assert "function validateQuizBank(quizBank)" in app_js
    assert "quiz.questions.length !== QUIZ_QUESTION_COUNT" in app_js
    assert "question.answers.length !== QUIZ_OPTIONS_COUNT" in app_js
    assert "question.correctIndex >= QUIZ_OPTIONS_COUNT" in app_js
    assert "validateQuizBank(QUIZ_BANK);" in app_js


def test_home_quiz_state_and_animation_contracts() -> None:
    app_js = _read_site_file("app.js")
    styles = _read_site_file("styles.css")
    assert "data-quiz-correct" in app_js
    assert 'questionResult.textContent = isCorrect ? "Correct" : "Incorrect";' in app_js
    assert "quiz-state-all-correct" in app_js
    assert "quiz-state-some-correct" in app_js
    assert "quiz-state-none-correct" in app_js
    assert "quiz-card-transition" in app_js
    assert "const QUIZ_TRANSITION_MS = 320;" in app_js
    assert ".quiz-state-all-correct" in styles
    assert ".quiz-state-some-correct" in styles
    assert ".quiz-state-none-correct" in styles
    assert ".quiz-card-transition" in styles
    assert "@keyframes quiz-page-turn" in styles
