# Flow Completion and Premature Success (Design Notes)

## Problem Statement

A common test pattern is:

> **Set State A → Set State B → Set State A → Verify State A**

The intent is to verify that State A *persists* through an intermediate state change. However, the agent currently terminates as soon as the success criteria is first satisfied — which happens immediately after the first "Set State A", before the intermediate steps ever run.

The same pattern breaks stored action learning: the LLM fallback executes just enough to pass the verify check, then stops. Whatever truncated steps ran get saved as the learned action, and all subsequent replays are equally truncated.

### Concrete examples from this project

| Intended flow | What actually executes | Why it passes early |
|---|---|---|
| Open Profile → Type About Me → **Save → Reload** → Verify text persists | Open Profile → Type text | The About Me field shows the typed text immediately; verify passes before save/reload |
| Type username → **Type password → Click login** | Type username | Username field contains the value; verify passes before password or submit |
| Register → **Logout → Login** → Verify home page | Register form filled | Registration fields contain values; verify sees partial success |

---

## Root Cause

The verify check runs **after each action batch** (stored action execution or LLM step). If the success criteria is evaluable at any point during the flow, the loop terminates there. There is no concept of "all steps must complete before checking".

This means:
1. **Stored actions are learned only up to the first passing verify** — subsequent steps are never executed and never stored.
2. **On replay, the same truncation applies** — the stored action runs, verify passes, done.
3. **The full flow never runs at all** — not even during initial learning.

---

## Mitigation Patterns

### Pattern 1: Natural Intermediate State Invalidation (best)

Design the flow so that **State B genuinely removes or hides State A**. The final verify can only pass after State A is re-established.

**Example:** For a persistence test:
- If the app clears the About Me field on page load and only fills it from storage, then after a reload the field will be empty unless the save actually worked.
- Success criteria: "The About Me field is visible and contains the saved value" — this fails after typing (before save) because reload clears the unsaved input.

**This is the most reliable pattern.** It requires no framework changes and cannot false-positive.

---

### Pattern 2: Navigation-Gated Criteria

Include navigation away and back as **a prerequisite for the success state being observable**. The criteria must reference something only visible on the correct page after the full round-trip.

**Example:**
```
Success criteria: You are on the Profile page (navigated back from Home),
and the About Me field shows the saved value.
```

This works if the verb "navigated back" causes the verify LLM to look for evidence of a round-trip. It is weaker than Pattern 1 because the verify LLM may still accept the early state if it looks similar enough.

---

### Pattern 3: Anchoring Criteria to a Post-Action Element

Include a UI element in the success criteria that **only appears after a specific action completes** — a save confirmation, a toast, a page-title change, a timestamp, or a different URL.

**Example:**
```
Success criteria: A save confirmation or the profile page shows
the About Me value after the page was reloaded (address bar unchanged,
content rehydrated from storage).
```

The verify LLM must see the confirmation element, not just the input value.

---

### Pattern 4: Ordered Step Numbering as Gating Signal (current partial mitigation)

The agent prompt already includes numbered steps. The LLM in-step verifier checks `criteria_visible: YES/NO` at each step and adds reasoning. If the prompt steps are numbered and explicit, the in-step reasoning often notes "step N is not yet complete" and continues.

This is **unreliable** as a hard gate — the final verify check at the end of the action batch is separate from the in-step verifier and will still pass early if criteria is visually satisfied.

---

### Pattern 5: Intermediate State Assertion in Prompt Steps (partial)

Add an explicit step in the prompt that **asserts the intermediate state** must be true before proceeding:

```
4. Enter About me text: {rand_string}
5. Confirm About me field is NOT yet saved (no confirmation shown).
6. Click Save.
7. Reload the page.
8. Confirm About me field still shows {rand_string}.
```

This gives the LLM stronger signal to not terminate early, but the final verify check still overrides once criteria passes.

---

## Recommended Framework Solution: Step-Aware Verify

### What the verify LLM currently receives

`verify_success_with_llm` ([vision_playwright_openai_vision_poc.py:5558](../../vision_playwright_openai_vision_poc.py#L5558)) sends exactly two things to the LLM:

1. A screenshot
2. The success criteria string

No prompt, no action history, no step context. The LLM cannot know whether step 6 (Reload) ran or not — it can only see the current visual state.

### The fix: pass prompt + completed steps into the verify call

Extend the verify prompt to include:

```
Full task: <original prompt with numbered steps>
Steps executed so far: <action names and/or step log>
Criteria: <success_criteria>

All numbered steps in the task must have been executed AND the criteria must be
visually met in the screenshot. If any required step from the task is missing
from the executed steps, output FAIL.
```

This makes flow completion a first-class part of the verify decision. The LLM is already capable of this reasoning — it just isn't given the information to do it.

**Key properties:**
- Low-risk change: only affects the verify prompt, not execution logic
- Requires passing `prompt` and `completed_steps` down to `verify_success_with_llm`
- Works for both the stored-action verify (after replay) and the LLM-fallback verify (after each step)
- Also fixes the action learning problem: the LLM fallback will not stop at step 2 if the verify correctly fails because steps 5–6 haven't run

---

## Other Potential Framework Solutions (Future Work)

### Option A: Deferred Verify Mode

A flag (e.g., `--defer-verify`) that suppresses the success criteria check until **all manually-specified actions in `--actions` complete**. The verify only runs after the last action in the sequence finishes.

- Pros: Guarantees full flow execution before termination.
- Cons: If an intermediate action genuinely completes the task, the system will not stop early and will continue running unnecessary steps.

### Option B: Minimum Steps Gate

A parameter (e.g., `--min-steps N`) that prevents success criteria from triggering until at least N LLM steps have been executed.

- Pros: Simple to implement.
- Cons: Fragile — the right N varies by flow and would need to be tuned per test.

### Option C: Negative Intermediate Criteria

Support a `--intermediate-must-fail` criteria string. The system would verify this criteria **must be false** at some point mid-flow before the final success check is allowed to pass.

- Example: `--intermediate-must-fail "About me field shows {rand_string}"` (must be false after reload, before the field rehydrates from storage).
- Pros: Formally encodes the Set A → Set B → Set A pattern.
- Cons: Adds authoring complexity.

### Option D: Postcondition Chaining

Each stored action declares a `postconditions` list. The framework could enforce that a stored action's postconditions are **verifiably false before that action runs** (i.e., the action is only meaningful if the state is not already satisfied). This would prevent re-running a "type username" action from passing if the username field is already filled.

---

## Recommended Approach Per Test Type

| Test type | Recommended pattern |
|---|---|
| Persistence (save → reload → verify) | Pattern 1: ensure reload clears unsaved state |
| Navigation round-trip (go away → come back → verify) | Pattern 1 + Pattern 3: verify something only visible after return |
| Multi-field form (fill several fields → submit) | Pattern 3: verify a post-submit element (confirmation, redirect) |
| Register → logout → login | Pattern 3: verify the home page Welcome message (only appears post-login) |
| Any "Set A → Set B → Set A" | Pattern 1 if possible; Pattern 3 otherwise |

---

## Summary

The core constraint is: **success criteria is a visual snapshot check, not a flow-completion check**. Any criteria that can be visually satisfied mid-flow will terminate the loop at that point. The most reliable mitigation is to design the app's UI so that intermediate steps genuinely invalidate the success state — making it impossible for the check to pass until the full flow has run.
