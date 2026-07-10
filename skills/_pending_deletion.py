"""
Tracks a single staged memory deletion, awaiting user confirmation.

This is intentionally in-memory only (not saved to disk) -- a pending
deletion shouldn't survive a script restart; if the session ends before
confirming, nothing was ever deleted, which is the safe default.

Prefixed with an underscore so the skill auto-loader skips this file --
it's shared state, not a tool itself.
"""

_pending = {"index": None, "text": None}


def set_pending(index: int, text: str):
    _pending["index"] = index
    _pending["text"] = text


def get_pending():
    return _pending["index"], _pending["text"]


def clear_pending():
    _pending["index"] = None
    _pending["text"] = None
