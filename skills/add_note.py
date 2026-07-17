"""Skill: add a timestamped note (separate from long-term facts)."""

from datetime import datetime
from ._notes_store import load_notes, save_notes

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "add_note",
        "description": (
            "Save a timestamped note or journal entry. Different from "
            "'remember', which saves plain facts with no timestamp."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "note": {"type": "string", "description": "The note text, as a plain string"}
            },
            "required": ["note"],
        },
    },
}


def _coerce_to_string(note) -> str:
    """
    Defensive fallback: if the model passes something other than a plain
    string (e.g. a dict echoing the schema's own keys, seen in v3.1
    testing), try to pull out something usable rather than saving a
    corrupted structure to disk.
    """
    if isinstance(note, str):
        return note
    if isinstance(note, dict):
        for key in ("description", "note", "value", "content", "text"):
            if key in note and isinstance(note[key], str):
                return note[key]
        return str(note)
    return str(note)


def run(note) -> str:
    note = _coerce_to_string(note)
    notes = load_notes()
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": note,
    }
    notes.append(entry)
    save_notes(notes)
    return f"Note saved at {entry['timestamp']}: {note}"
