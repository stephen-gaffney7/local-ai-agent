"""
Skill: step 2 of the forget flow. Finalizes or cancels a deletion that
was previously staged by the 'forget' skill, based on the user's answer.
"""

from ._memory_store import load_memory, save_memory
from ._pending_deletion import get_pending, clear_pending

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "confirm_forget",
        "description": (
            "Finalize or cancel a deletion previously staged by 'forget', "
            "based on whether the user said yes or no. Only call this after "
            "'forget' has staged something and the user has responded."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "confirm": {
                    "type": "boolean",
                    "description": "true if the user confirmed the deletion, false if they declined",
                }
            },
            "required": ["confirm"],
        },
    },
}


def run(confirm: bool) -> str:
    idx, text = get_pending()

    if idx is None:
        return "There's no pending deletion to confirm. Use 'forget' first."

    if not confirm:
        clear_pending()
        return "Deletion cancelled. Nothing was removed."

    # Re-check memory hasn't changed since staging, for safety
    memory = load_memory()
    if idx >= len(memory) or memory[idx] != text:
        clear_pending()
        return (
            "Memory changed since this deletion was staged, so it was cancelled "
            "for safety. Please try 'forget' again."
        )

    removed = memory.pop(idx)
    save_memory(memory)
    clear_pending()
    return f"Deleted: {removed}"
