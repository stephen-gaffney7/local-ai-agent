"""
Shared helpers for reading/writing timestamped notes -- a separate,
chronological log distinct from the fact-based long-term memory
(memory.json / remember / recall / forget).

Prefixed with an underscore so the skill auto-loader skips this file.
"""

import json
import os

NOTES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "notes.json")


def load_notes():
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_notes(notes):
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2)
