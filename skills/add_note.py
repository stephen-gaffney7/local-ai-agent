"""Skill: add a timestamped note (separate from long-term facts)."""

from datetime import datetime
from ._notes_store import load_notes, save_notes

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "add_note",
        "description": (
            "Save a timestamped note or journal entry. Use this for things "
            "the user wants logged with a date/time attached, as opposed to "
            "'remember' which is for plain facts with no timestamp."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "note": {"type": "string", "description": "The note content"}
            },
            "required": ["note"],
        },
    },
}


def run(note: str) -> str:
    notes = load_notes()
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": note,
    }
    notes.append(entry)
    save_notes(notes)
    return f"Note saved at {entry['timestamp']}: {note}"
