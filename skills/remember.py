"""Skill: save a fact to persistent long-term memory."""

from ._memory_store import load_memory, save_memory

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "remember",
        "description": (
            "Save a plain fact (no timestamp) -- name, preferences, personal "
            "details. Use add_note instead for timestamped journal entries."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "fact": {"type": "string", "description": "The fact or note to remember"}
            },
            "required": ["fact"],
        },
    },
}


def run(fact: str) -> str:
    memory = load_memory()
    memory.append(fact)
    save_memory(memory)
    return f"Saved to memory: {fact}"
