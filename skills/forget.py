"""
Skill: STAGE removal of a memory entry (does not delete yet).

This is step 1 of a two-step confirm flow. It finds the matching entry
and reports exactly what it would delete, but makes no changes to
memory.json. Use the "confirm_forget" skill to actually finalize
(or cancel) the deletion after the user confirms.
"""

from ._memory_store import load_memory
from ._pending_deletion import set_pending, clear_pending

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "forget",
        "description": (
            "Stage removal of a memory entry for confirmation (does NOT delete "
            "yet). Pass either the index number shown by 'recall', or a text "
            "snippet to match. After this, ask the user to confirm, then call "
            "confirm_forget with their answer."
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

    matches = [i for i, item in enumerate(memory) if target.lower() in item.lower()]

    if not matches:
        clear_pending()
        return f"No memory entries matched '{target}'. Nothing staged."

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
