from typing import Any

from vision_playwright_openai_vision_poc import prune_messages_for_cost


def _tool_result_image(tool_use_id: str, image_id: str) -> dict:
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": [{"type": "image", "image": image_id}],
            }
        ],
    }


def test_prune_preserves_tool_use_before_tool_result() -> None:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "Instruction"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1"}]},
        _tool_result_image("t1", "img1"),
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t2"}]},
        _tool_result_image("t2", "img2"),
    ]

    pruned = prune_messages_for_cost(messages, keep_last_turns=1, keep_last_images=1)

    assert len(pruned) == 3
    assert pruned[0]["role"] == "system"
    assert pruned[1]["role"] == "assistant"
    assert pruned[2]["role"] == "user"


def test_prune_strips_older_tool_result_images() -> None:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "Instruction"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1"}]},
        _tool_result_image("t1", "img1"),
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t2"}]},
        _tool_result_image("t2", "img2"),
    ]

    pruned = prune_messages_for_cost(messages, keep_last_turns=4, keep_last_images=1)

    older_tool_result = pruned[2]["content"][0]["content"]
    assert all(item.get("type") != "image" for item in older_tool_result)
    assert any(
        item.get("type") == "text" and "omitted" in item.get("text", "")
        for item in older_tool_result
        if isinstance(item, dict)
    )
