from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# TEST-UNIT-FEED-001  (REQ-1)
# Home HTML contract: feed input, Post button, feed container with correct
# data-testid values and maxlength="140".
# ---------------------------------------------------------------------------


def test_home_html_feed_input_and_button() -> None:
    home_html = (REPO_ROOT / "test-site" / "home.html").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert 'data-testid="feed-post-input"' in home_html
    assert 'maxlength="140"' in home_html
    assert 'data-testid="feed-post-button"' in home_html
    assert 'data-testid="feed-container"' in home_html


# ---------------------------------------------------------------------------
# TEST-UNIT-FEED-002  (REQ-2, REQ-3, REQ-4, REQ-6)
# Post logic: app.js stores posts in posts_v1 with correct shape, renders
# newest-first, and supports delete.
# ---------------------------------------------------------------------------


def test_app_js_posts_key_and_max_len() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert 'const POSTS_KEY = "posts_v1"' in app_js
    assert "const POST_MAX_LEN = 140" in app_js


def test_app_js_load_and_save_posts() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert "function loadPosts(" in app_js
    assert "function savePosts(" in app_js
    assert "localStorage.getItem(POSTS_KEY)" in app_js
    assert "localStorage.setItem(POSTS_KEY" in app_js


def test_app_js_render_feed_newest_first() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert "function renderFeed(" in app_js
    # Sorts descending by timestamp
    assert "a.timestamp > b.timestamp" in app_js
    assert 'data-testid", "feed-post"' in app_js
    assert 'data-testid", "feed-post-text"' in app_js
    assert 'data-testid", "feed-post-author"' in app_js
    assert 'data-testid", "feed-post-timestamp"' in app_js


def test_app_js_post_object_shape() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    # Post object must include id, author, text, timestamp
    assert "id: Date.now().toString()" in app_js
    assert "author: currentUser" in app_js
    assert "text," in app_js
    assert "timestamp: new Date().toISOString()" in app_js


def test_app_js_delete_removes_from_storage_and_rerenders() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    # Delete filters out the post by id and saves, then re-renders feed
    assert "stored.filter((p) => p.id !== post.id)" in app_js
    assert "renderFeed(feedContainer, currentUser)" in app_js


def test_app_js_feed_initialized_for_home_page() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    assert "initializeFeed(username)" in app_js


# ---------------------------------------------------------------------------
# TEST-UNIT-FEED-003  (REQ-5)
# Empty and whitespace-only input is rejected; oversized input (>140) rejected.
# ---------------------------------------------------------------------------


def test_app_js_post_rejects_empty_and_oversized() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    # Trim then check empty
    assert "postInput.value.trim()" in app_js
    # Reject if empty or exceeds max
    assert "!text || text.length > POST_MAX_LEN" in app_js


# ---------------------------------------------------------------------------
# TEST-UNIT-FEED-004  (REQ-7)
# Delete button is present for author's posts and absent for others.
# ---------------------------------------------------------------------------


def test_app_js_delete_button_author_only() -> None:
    app_js = (REPO_ROOT / "test-site" / "app.js").read_text(
        encoding="utf-8", errors="ignore"
    )
    # Delete button rendered conditionally for author
    assert "post.author === currentUser" in app_js
    assert 'data-testid", "feed-post-delete"' in app_js
