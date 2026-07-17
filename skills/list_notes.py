"""Skill: list all saved timestamped notes."""

from ._notes_store import load_notes

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_notes",
        "description": (
            "Retrieve saved notes/journal entries (each timestamped). Not "
            "for plain facts -- use recall for those."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}


def run() -> str:
    notes = load_notes()
    if not notes:
        return "No notes saved yet."
    ordered = list(reversed(notes))
    return "\n".join(f"[{n['timestamp']}] {n['note']}" for n in ordered)
