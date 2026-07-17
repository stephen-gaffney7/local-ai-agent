"""Skill: retrieve everything saved in long-term memory."""

from ._memory_store import load_memory

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "recall",
        "description": (
            "Retrieve saved facts (no timestamp) -- name, preferences, "
            "personal details. Not for notes/journal entries -- use "
            "list_notes for those."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}


def run() -> str:
    memory = load_memory()
    if not memory:
        return "Long-term memory is empty."
    return "\n".join(f"[{i}] {item}" for i, item in enumerate(memory))
