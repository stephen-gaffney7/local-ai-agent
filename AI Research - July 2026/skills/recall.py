"""Skill: retrieve everything saved in long-term memory."""

from ._memory_store import load_memory

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "recall",
        "description": "Retrieve everything currently saved in long-term memory.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def run() -> str:
    memory = load_memory()
    if not memory:
        return "Long-term memory is empty."
    return "\n".join(f"[{i}] {item}" for i, item in enumerate(memory))
