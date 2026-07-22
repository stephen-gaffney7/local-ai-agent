"""
Skill: STAGE removal of a memory entry (does not delete yet).

This is step 1 of a two-step confirm flow. It finds the matching entry
and reports exactly what it would delete, but makes no changes to
memory.json. Use the "confirm_forget" skill to actually finalize
(or cancel) the deletion after the user confirms.
"""

import re

from ._memory_store import load_memory
from ._pending_deletion import set_pending, clear_pending

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "forget",
        "description": (
            "Stage removal of a memory entry for confirmation (does NOT delete "
            "yet). ALWAYS call this tool whenever the user asks to forget, "
            "remove, delete, or erase something from memory -- even if you "
            "are not sure the fact exists. This tool will correctly report "
            "back if no match is found, so never answer a forget request "
            "conversationally without calling it first. Pass either the "
            "index number shown by 'recall', or a text snippet or paraphrase "
            "to match -- matching tolerates different wording, not just exact "
            "substrings. After this, ask the user to confirm, then call "
            "confirm_forget with their answer."
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


_STOPWORDS = {
    "i", "a", "an", "the", "is", "are", "was", "were", "am", "to", "of",
    "in", "on", "at", "that", "this", "my", "me", "and", "or", "it",
}


def _normalize(text: str) -> str:
    """
    Strip punctuation and collapse whitespace so matching isn't thrown
    off by things like a trailing period the model added on its own
    that isn't present in the originally saved fact.
    """
    text = text.lower()
    text = text.replace("_", " ")  # so 'prefer_metric' splits into separate words
    text = re.sub(r"[^\w\s]", "", text)  # remove punctuation
    text = re.sub(r"\s+", " ", text).strip()  # collapse whitespace
    return text


def _meaningful_words(text: str) -> set:
    return {w for w in text.split() if w not in _STOPWORDS}


def _is_match(target: str, item: str) -> bool:
    """
    Two-tier matching:
    1. Substring match (handles exact/near-exact snippets, case- and
       punctuation-insensitive).
    2. Word-subset match (handles paraphrases, e.g. a compressed search
       term like "prefer_metric" -- once normalized to "prefer metric"
       -- against a saved fact like "I prefer imperial units over
       metric"). Requires at least one meaningful (non-stopword) word,
       so short/common-word targets don't match everything.
    """
    if target in item:
        return True

    target_words = _meaningful_words(target)
    item_words = _meaningful_words(item)
    if target_words and target_words.issubset(item_words):
        return True

    return False


def run(target: str) -> str:
    memory = load_memory()
    if not memory:
        clear_pending()
        return "Long-term memory is already empty. Nothing to forget."

    target = target.strip()

    if target.isdigit():
        idx = int(target)
        if 0 <= idx < len(memory):
            set_pending(idx, memory[idx])
            return (
                f"Ready to delete entry [{idx}]: \"{memory[idx]}\". "
                f"Ask the user to confirm before calling confirm_forget."
            )
        clear_pending()
        return f"No memory entry at index {idx}. Nothing staged."

    normalized_target = _normalize(target)
    matches = [
        i for i, item in enumerate(memory)
        if _is_match(normalized_target, _normalize(item))
    ]

    if not matches:
        clear_pending()
        return (
            f"No memory entries matched '{target}'. Nothing staged -- tell "
            f"the user directly that nothing matched. Do NOT ask for yes/no "
            f"confirmation, since there is nothing staged to confirm."
        )

    if len(matches) > 1:
        clear_pending()
        listing = "\n".join(f"[{i}] {memory[i]}" for i in matches)
        return (
            f"Multiple entries matched '{target}'. Nothing staged yet -- "
            f"ask the user which index they mean:\n{listing}"
        )

    idx = matches[0]
    set_pending(idx, memory[idx])
    return (
        f"Ready to delete entry [{idx}]: \"{memory[idx]}\". "
        f"Ask the user to confirm before calling confirm_forget."
    )
