"""
Shared helpers for reading/writing persistent long-term memory.

Prefixed with an underscore so the skill auto-loader (which only loads
files exposing TOOL_SCHEMA + run) skips this one — it's a shared utility,
not a tool itself.
"""

import json
import os

MEMORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory.json")


def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)
