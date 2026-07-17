"""
Skill: STAGE removal of a memory entry (does not delete yet).

This is step 1 of a two-step confirm flow. It finds the matching entry
and reports exactly what it would delete, but makes no changes to
memory.json. Use the "confirm_forget" skill to actually finalize
(or cancel) the deletion after the user confirms.
"""

import re

from ._memory_store import load_memory
from ._pending_deletion import set_pending, clear_pending

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "forget",
        "description": (
            "Stage removal of a memory entry for confirmation (does NOT delete "
            "yet). ALWAYS call this tool whenever the user asks to forget, "
            "remove, delete, or erase something from memory -- even if you "
            "are not sure the fact exists. This tool will correctly report "
            "back if no match is found, so never answer a forget request "
            "conversationally without calling it first. Pass either the "
            "index number shown by 'recall', or a text snippet to match. "
            "After this, ask the user to confirm, then call confirm_forget "
            "with their answer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Index number (e.g. '2') or text snippet to match",
                }
            },
            "required": ["target"],
        },
    },
}


def _normalize(text: str) -> str:
    """
    Strip punctuation and collapse whitespace so matching isn't thrown
    off by things like a trailing period the model added on its own
    that isn't present in the originally saved fact.
    """
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)  # remove punctuation
    text = re.sub(r"\s+", " ", text).strip()  # collapse whitespace
    return text


def run(target: str) -> str:
    memory = load_memory()
    if not memory:
        clear_pending()
        return "Long-term memory is already empty. Nothing to forget."

    target = target.strip()

    if target.isdigit():
        idx = int(target)
        if 0 <= idx < len(memory):
            set_pending(idx, memory[idx])
            return (
                f"Ready to delete entry [{idx}]: \"{memory[idx]}\". "
                f"Ask the user to confirm before calling confirm_forget."
            )
        clear_pending()
        return f"No memory entry at index {idx}. Nothing staged."

    normalized_target = _normalize(target)
    matches = [
        i for i, item in enumerate(memory)
        if normalized_target in _normalize(item)
    ]

    if not matches:
        clear_pending()
        return (
            f"No memory entries matched '{target}'. Nothing staged -- tell "
            f"the user directly that nothing matched. Do NOT ask for yes/no "
            f"confirmation, since there is nothing staged to confirm."
        )

    if len(matches) > 1:
        clear_pending()
        listing = "\n".join(f"[{i}] {memory[i]}" for i in matches)
        return (
            f"Multiple entries matched '{target}'. Nothing staged yet -- "
            f"ask the user which index they mean:\n{listing}"
        )

    idx = matches[0]
    set_pending(idx, memory[idx])
    return (
        f"Ready to delete entry [{idx}]: \"{memory[idx]}\". "
        f"Ask the user to confirm before calling confirm_forget."
    )
