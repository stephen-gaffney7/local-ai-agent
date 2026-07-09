"""
Skill: remove an entry from long-term memory.

Accepts either:
  - the exact index shown by `recall` (e.g. "2"), or
  - a text snippet to match against saved facts (case-insensitive substring)

If a text snippet matches more than one saved fact, nothing is deleted and
the matches are listed instead, so the model/user can pick a specific index.
"""

from ._memory_store import load_memory, save_memory

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "forget",
        "description": (
            "Remove an entry from long-term memory. Pass either the index "
            "number shown by 'recall', or a snippet of the fact's text to match."
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
        return "Long-term memory is already empty."

    # Try exact index first
    target = target.strip()
    if target.isdigit():
        idx = int(target)
        if 0 <= idx < len(memory):
            removed = memory.pop(idx)
            save_memory(memory)
            return f"Removed: {removed}"
        return f"No memory entry at index {idx}."

    # Otherwise, match by substring
    matches = [i for i, item in enumerate(memory) if target.lower() in item.lower()]
    if not matches:
        return f"No memory entries matched '{target}'."
    if len(matches) > 1:
        listing = "\n".join(f"[{i}] {memory[i]}" for i in matches)
        return (
            f"Multiple entries matched '{target}'. Specify an index instead:\n{listing}"
        )

    removed = memory.pop(matches[0])
    save_memory(memory)
    return f"Removed: {removed}"
