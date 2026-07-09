"""Skill: read the text contents of a local file by path."""

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the text contents of a local file by path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"}
            },
            "required": ["path"],
        },
    },
}


def run(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(2000)
        return content if content else "(file is empty)"
    except Exception as e:
        return f"Error reading file: {e}"
