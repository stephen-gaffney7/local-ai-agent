"""Skill: return the current date and time."""

from datetime import datetime

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "Get the current date and time.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def run() -> str:
    return datetime.now().strftime("%A, %B %d %Y, %I:%M %p")
