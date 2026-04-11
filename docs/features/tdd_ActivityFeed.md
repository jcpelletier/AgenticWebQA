# Activity Feed (TDD)

## Feature Spec Header
- Feature Name: Activity Feed
- Feature Slug: ActivityFeed
- Owner: TBD
- User Story: As an authenticated user, I want to post short messages to a feed on the home page so that I can leave notes visible to myself, and delete my own posts when I no longer need them.
- In Scope:
  - Add a text input and Post button to `home.html` for submitting messages (≤140 characters).
  - Render posts in a feed below the input, newest first, each showing the message text, the author's username, and a relative or absolute timestamp.
  - Show a Delete button on each post, visible only to the post's author.
  - Persist posts in `posts_v1` localStorage key, shared across all users of the same browser.
  - Enforce the 140-character limit: disable or ignore Post when input exceeds the limit.
  - Clear the input field after a successful post.
- Out Of Scope:
  - Editing existing posts.
  - Liking, replying to, or threading posts.
  - Pagination or infinite scroll (all posts rendered; no limit enforced on total count).
  - Posts appearing on any page other than `home.html`.
  - Backend/API services or cloud sync.
  - Real-time updates when another user posts in the same browser tab.
  - Profanity filtering or content moderation.
- Dependencies:
  - Existing auth session (`currentUser` in `sessionStorage`) in `test-site/app.js`.
  - Existing auth guard (`requireAuthenticatedUser`) in `test-site/app.js`.
  - `home.html` as the target page for the feed UI.
- Rollout Risk: Medium. Introduces a new `posts_v1` localStorage key and new DOM on `home.html`. No changes to existing auth, profile, or registration flows.
- Test Requirements:
  - Unit tests for DOM contract, post/delete/persistence behavior, and 140-char enforcement.
  - Smoke test covering: post a message → verify it appears in the feed → delete it → verify it is gone.
  - Requirement-to-test traceability matrix included below.

## Summary
Add a simple activity feed to `home.html`. Authenticated users can type a message (up to 140 characters) and click Post. The message appears in the feed with the author's username and timestamp. The author sees a Delete button on their own posts; other users do not. All posts are stored in `posts_v1` localStorage.

## Goals
- Provide a labeled message input (`maxlength="140"`) and a Post button on `home.html`.
- On submit, prepend the new post to the feed (newest first) and clear the input.
- Each post displays: message text, author username, timestamp, and a Delete button (author only).
- Delete removes the post from the feed and from `posts_v1` storage immediately.
- Posts persist across page reloads for any user sharing the same browser storage.
- Posts authored by another user do not show a Delete button for the current user.

## Non-Goals
- Server-side storage or multi-device sync.
- Post editing.
- Feed pagination or post count limits.
- Posts appearing outside `home.html`.
- Changing auth or session semantics.
- New npm/pip dependencies.

## Assumptions
- ASSUMPTION: `posts_v1` is a JSON array in localStorage, each element shaped as `{ id, author, text, timestamp }`. `id` is a unique string (e.g. `Date.now().toString()`).
- ASSUMPTION: Posts are rendered in reverse insertion order (newest first) on every page load and after every post/delete.
- ASSUMPTION: Author identity is determined by `currentUser` in `sessionStorage`. If the session is missing, the page redirects via the existing auth guard before the feed is rendered.
- ASSUMPTION: The Delete button is rendered conditionally: present in the DOM only for posts where `post.author === currentUser`.
- ASSUMPTION: An empty or whitespace-only input is rejected silently (Post button disabled or click ignored).
- ASSUMPTION: A post whose text exceeds 140 characters after trim is rejected; the `maxlength` attribute on the input is the primary enforcement mechanism.
- ASSUMPTION: Timestamps are stored as ISO strings and displayed as-is (no relative formatting required).

## Open Questions
- None.

## Linear Checklist
- [ ] Define stable selectors and requirement IDs (`REQ-1`..`REQ-7`).
- [ ] Add message input, character counter, and Post button to `test-site/home.html` (`REQ-1`, `REQ-2`).
- [ ] Add feed container to `test-site/home.html` (`REQ-3`).
- [ ] Implement post submission logic in `test-site/app.js`: validate, write to `posts_v1`, prepend to feed, clear input (`REQ-2`, `REQ-3`, `REQ-5`).
- [ ] Implement feed render logic in `test-site/app.js`: load `posts_v1`, render newest-first, include Delete button for author only (`REQ-3`, `REQ-4`, `REQ-6`).
- [ ] Implement delete logic in `test-site/app.js`: remove post from `posts_v1`, remove element from DOM (`REQ-6`).
- [ ] Add unit tests for DOM contract, post/delete/persistence, and 140-char enforcement (`TEST-UNIT-FEED-001`..`004`).
- [ ] Add smoke script `webtests/run_testactivityfeed_local.py` (`TEST-SMOKE-FEED-001`).
- [ ] Run unit tests and record results under Test Execution Evidence.
- [ ] Run smoke test and record results under Test Execution Evidence.
- [ ] Confirm acceptance criteria and REQ/TEST traceability are complete.

## UX Workflow
1. Authenticated user lands on `home.html`. The feed area is visible below the welcome text.
2. If posts exist in storage, they are rendered newest-first on page load.
3. User types a message in the input (up to 140 characters) and clicks Post.
4. The new post appears at the top of the feed with the user's username and the current timestamp.
5. The input is cleared.
6. The user sees a Delete button next to their own posts. Clicking Delete removes the post immediately.
7. If another user logs in on the same browser, they see all posts but no Delete button on posts they did not author.

## Technical Design
- Files expected to change:
  - `test-site/home.html`
  - `test-site/app.js`
  - `tests/test_activityfeed_contract.py` (new)
  - `webtests/run_testactivityfeed_local.py` (new)
  - `docs/features/tdd_ActivityFeed.md`
- Markup contract:
  - Post input: `data-testid="feed-post-input"` and `maxlength="140"`
  - Post button: `data-testid="feed-post-button"`
  - Feed container: `data-testid="feed-container"`
  - Individual post: `data-testid="feed-post"` (one per post)
  - Post text: `data-testid="feed-post-text"`
  - Post author: `data-testid="feed-post-author"`
  - Post timestamp: `data-testid="feed-post-timestamp"`
  - Delete button: `data-testid="feed-post-delete"` (author's posts only)
- Data model (`localStorage`):
  - Key: `posts_v1`
  - Shape: `[{ "id": "1700000000000", "author": "user_abc", "text": "Hello", "timestamp": "2026-03-19T12:00:00.000Z" }, ...]`
  - Newest post is at index 0 after render; storage order may be append or prepend — render always sorts by timestamp descending.
- Post logic:
  - On Post click: trim input, reject if empty or >140 chars, create post object, prepend to `posts_v1`, re-render feed, clear input.
  - On Delete click: remove post by `id` from `posts_v1`, remove DOM element.
  - On page load: load `posts_v1`, render all posts newest-first.

### Requirement IDs
- `REQ-1`: Home page includes a visible message input with `maxlength="140"` and a Post button.
- `REQ-2`: Submitting a non-empty message (≤140 chars) adds it to the feed and clears the input.
- `REQ-3`: Posts are displayed in the feed newest-first, each showing message text, author, and timestamp.
- `REQ-4`: Posts persist across page reloads.
- `REQ-5`: Empty or whitespace-only input is rejected; the Post button has no effect.
- `REQ-6`: The author sees a Delete button on their own posts; clicking it removes the post from the feed and storage.
- `REQ-7`: Users do not see a Delete button on posts authored by others.

## Testing Plan
### Test Cases
- `TEST-UNIT-FEED-001` (Unit): Home HTML contract includes feed input, Post button, and feed container with correct `data-testid` values and `maxlength="140"`.
- `TEST-UNIT-FEED-002` (Unit): Post logic stores post in `posts_v1` with correct shape; re-render shows it newest-first; Delete removes it from storage and DOM.
- `TEST-UNIT-FEED-003` (Unit): Empty and whitespace-only input is rejected; oversized input (>140 chars) is rejected.
- `TEST-UNIT-FEED-004` (Unit): Delete button is present for author's posts and absent for posts authored by a different user.
- `TEST-SMOKE-FEED-001` (Smoke): register → post a message → verify it appears in the feed → delete it → verify it is gone from the feed.

### Commands
- Unit tests:
  - `python -m pytest -q tests/test_activityfeed_contract.py`
- Smoke test:
  - `python webtests/run_testactivityfeed_local.py --skip-install`

### Requirement-to-Test Traceability Matrix
| Requirement ID | Test ID | Test Type | Command |
|---|---|---|---|
| REQ-1 | TEST-UNIT-FEED-001 | Unit | `python -m pytest -q tests/test_activityfeed_contract.py` |
| REQ-1 | TEST-SMOKE-FEED-001 | Smoke | `python webtests/run_testactivityfeed_local.py --skip-install` |
| REQ-2 | TEST-UNIT-FEED-002 | Unit | `python -m pytest -q tests/test_activityfeed_contract.py` |
| REQ-2 | TEST-SMOKE-FEED-001 | Smoke | `python webtests/run_testactivityfeed_local.py --skip-install` |
| REQ-3 | TEST-UNIT-FEED-002 | Unit | `python -m pytest -q tests/test_activityfeed_contract.py` |
| REQ-3 | TEST-SMOKE-FEED-001 | Smoke | `python webtests/run_testactivityfeed_local.py --skip-install` |
| REQ-4 | TEST-UNIT-FEED-002 | Unit | `python -m pytest -q tests/test_activityfeed_contract.py` |
| REQ-5 | TEST-UNIT-FEED-003 | Unit | `python -m pytest -q tests/test_activityfeed_contract.py` |
| REQ-6 | TEST-UNIT-FEED-002 | Unit | `python -m pytest -q tests/test_activityfeed_contract.py` |
| REQ-6 | TEST-SMOKE-FEED-001 | Smoke | `python webtests/run_testactivityfeed_local.py --skip-install` |
| REQ-7 | TEST-UNIT-FEED-004 | Unit | `python -m pytest -q tests/test_activityfeed_contract.py` |

## Test Execution Evidence (Fill During Implementation)
- `python -m pytest -q tests/test_activityfeed_contract.py` -> 9 passed
- `python webtests/run_testactivityfeed_local.py --skip-install` -> All 2 activity feed smoke test(s) passed (both runs): PASS run 1: ActivityFeed_Login, PASS run 2 (no fallback): ActivityFeed_Login, PASS run 1: ActivityFeed_Post, PASS run 2 (no fallback): ActivityFeed_Post

## Acceptance Criteria
- `AC-1` (`REQ-1`, `TEST-UNIT-FEED-001`, `TEST-SMOKE-FEED-001`): Home page shows a visible message input capped at 140 characters and a Post button with stable selectors.
- `AC-2` (`REQ-2`, `TEST-UNIT-FEED-002`, `TEST-SMOKE-FEED-001`): Posting a valid message adds it to the feed and clears the input.
- `AC-3` (`REQ-3`, `TEST-UNIT-FEED-002`, `TEST-SMOKE-FEED-001`): Feed renders posts newest-first with text, author, and timestamp visible.
- `AC-4` (`REQ-4`, `TEST-UNIT-FEED-002`): Posts survive a page reload.
- `AC-5` (`REQ-5`, `TEST-UNIT-FEED-003`): Empty and oversized input is silently rejected.
- `AC-6` (`REQ-6`, `TEST-UNIT-FEED-002`, `TEST-SMOKE-FEED-001`): Author can delete their own post; it is removed from the feed and storage immediately.
- `AC-7` (`REQ-7`, `TEST-UNIT-FEED-004`): No Delete button is shown to users who did not author the post.
