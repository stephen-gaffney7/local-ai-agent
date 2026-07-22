"""
Task-performing agent -- v3.3 (bug-fix pass on v3.2, no new functionality).
v3.2 testing found a few issues, addressed here:

    1. confirm_forget hallucination fix - saying "yes"/"no" when
       nothing was actually staged to be deleted caused the model to 
       fabricate an entirely fictional state, with no tool
       call. If there is nothing actually staged in _pending_deletion. 
       In that case a fixed, accurate message is shown directly and 
       the model is not consulted for that turn.
    2. forget tool call matching criteria increased. Previously, we saw
       a match fail due to not matching keywords. Now the criteria for
       finding the correct fact to forget is based on more of the initial
       memory prompt.
    3. recall and list_notes tool calls verification: "what's saved"
       questions weren't always backed by an actual tool call, and were
       sometimes confidently wrong as a result. Fixed at the code level
       if the user's message looks like a memory/notes query
       (via keyword matching), the script calls recall and/or
       list_notes itself and adds the real results into the
       conversation before the model responds so accurate data is
       available regardless of whether the model chooses to call the
       tool on its own.

Also strengthened as best-effort prompt-level mitigations (these are
model-behavior tendencies that can't be fully eliminated in code, only
made less likely):
    - Explicit instruction to always use convert_units for unit
      conversions rather than computing them manually via calculator.
    - Explicit instruction on recognizing a wider range of decline
      phrasing (not just a bare "no") when a forget match is ambiguous.

No functional/behavioral changes beyond these fixes -- same skills, same
two-step forget-confirmation flow, same iterative tool-call loop, same
memory files.

Folder layout expected next to this script:
    agent_with_tools_v3_3.py
    memory.json          (long-term facts -- auto-created)
    notes.json            (timestamped notes -- auto-created)
    skills/
        __init__.py
        _memory_store.py
        _notes_store.py
        _pending_deletion.py
        calculator.py
        current_time.py
        remember.py
        recall.py
        forget.py
        confirm_forget.py
        read_file.py
        convert_units.py
        add_note.py
        list_notes.py
"""

import ollama
import json
import importlib
import pkgutil
from pathlib import Path

import skills as skills_package
from skills._pending_deletion import get_pending
from skills.recall import run as recall_run
from skills.list_notes import run as list_notes_run

MODEL = "qwen2.5:3b"
MAX_HISTORY_MESSAGES = 12       # sliding window: keep last N messages
CONTEXT_TOKENS = 4096           # override Ollama's default 2048
MAX_TOOL_ROUNDS = 5             # cap on chained tool calls per turn
MEMORY_FILE = Path(__file__).parent / "memory.json"

# Bare confirmation-style replies that should be intercepted in code
# (not sent to the model) when nothing is actually staged for deletion
_CONFIRMATION_WORDS = {
    "yes", "y", "yeah", "yep", "sure", "confirm", "confirmed",
    "no", "n", "nope", "nah", "cancel",
}

# Keyword triggers for proactively grounding memory/notes queries with
# real tool output before the model responds (see inject_memory_grounding)
_FACT_QUERY_KEYWORDS = [
    "saved in memory", "in memory", "long-term memory", "long term memory",
    "what do you have saved", "what have i told you", "what facts",
]
_NOTE_QUERY_KEYWORDS = [
    "notes have i", "saved notes", "my notes", "list notes",
    "what notes", "journal",
]

# ---------------------------------------------------------------------
# SKILL AUTO-LOADER
# ---------------------------------------------------------------------


def load_skills():
    tool_schemas = []
    tool_functions = {}

    for _, module_name, _ in pkgutil.iter_modules(skills_package.__path__):
        if module_name.startswith("_"):
            continue
        module = importlib.import_module(f"skills.{module_name}")
        if hasattr(module, "TOOL_SCHEMA") and hasattr(module, "run"):
            name = module.TOOL_SCHEMA["function"]["name"]
            tool_schemas.append(module.TOOL_SCHEMA)
            tool_functions[name] = module.run
        else:
            print(f"[skills] Skipping '{module_name}.py' -- missing TOOL_SCHEMA or run()")

    return tool_schemas, tool_functions


# ---------------------------------------------------------------------
# LONG-TERM MEMORY (for building the system prompt)
# ---------------------------------------------------------------------


def load_memory_for_prompt():
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def build_system_prompt():
    long_term = load_memory_for_prompt()
    memory_block = (
        "\n".join(f"- {item}" for item in long_term)
        if long_term
        else "(nothing saved yet)"
    )
    return (
        "You are a helpful assistant with access to tools. Use them when they "
        "would give a more accurate answer than guessing (math, unit conversion, "
        "current time, saved notes/facts, file contents).\n\n"
        "IMPORTANT -- deleting memories is a two-step process:\n"
        "1. Call 'forget' to find and stage the entry (this does NOT delete it).\n"
        "2. Show the user exactly what would be deleted and ask them to confirm.\n"
        "3. Only after they explicitly say yes or no, call 'confirm_forget' with "
        "their answer. Never call confirm_forget without first asking the user.\n"
        "4. ALWAYS call 'forget' for any forget/remove/delete request, even if "
        "you think the fact doesn't exist -- the tool correctly reports back "
        "when nothing matches. Never answer a forget request conversationally "
        "without calling the tool first.\n"
        "5. If 'forget' reports no match or multiple matches, nothing was "
        "staged -- tell the user directly and do NOT ask for yes/no "
        "confirmation, since there is nothing to confirm.\n\n"
        "IMPORTANT -- there are two SEPARATE memory systems, don't mix them up:\n"
        "- FACTS (no timestamp): use 'remember' to save, 'recall' to retrieve. "
        "For things like name, preferences, personal details.\n"
        "- NOTES (timestamped): use 'add_note' to save, 'list_notes' to "
        "retrieve. For journal entries, logs, things that happened.\n"
        "If the user says 'notes' or 'log', use add_note/list_notes. If they "
        "say 'remember' or ask about facts/preferences, use remember/recall. "
        "Never call recall when asked about notes, and never call list_notes "
        "when asked about facts. Always call recall or list_notes fresh when "
        "asked what's saved, rather than answering from earlier conversation.\n\n"
        "IMPORTANT -- if a message asks multiple distinct things, call a tool "
        "for EACH part before answering -- don't skip any of them.\n\n"
        "IMPORTANT -- if a tool call returns an error, report that error to "
        "the user. Do not answer from your own knowledge as a substitute -- "
        "the tool's result is the ground truth, not a guess to override.\n\n"
        "IMPORTANT -- for ANY conversion between units of length, weight, or "
        "temperature, ALWAYS call convert_units. Do not compute conversions "
        "manually with calculator, even if you know the conversion factor -- "
        "convert_units also correctly catches mismatched unit categories.\n\n"
        "IMPORTANT -- if you've listed multiple matching entries for 'forget' "
        "and asked which one to remove, recognize a wide range of decline "
        "phrasing as 'don't delete anything' -- not just a bare 'no,' but "
        "also things like 'don't forget either,' 'neither,' 'cancel that,' "
        "'never mind,' etc. Any of these means: do not stage or delete "
        "anything, and do not keep re-asking the same question.\n\n"
        "After using any tool, always give a clear plain-language answer "
        "summarizing the result -- don't leave your reply empty.\n\n"
        f"Known long-term memory:\n{memory_block}"
    )


# ---------------------------------------------------------------------
# SHORT-TERM MEMORY (sliding window trim)
# ---------------------------------------------------------------------


def trim_history(messages):
    system_msgs = [m for m in messages if m["role"] == "system"]
    other_msgs = [m for m in messages if m["role"] != "system"]
    trimmed = other_msgs[-MAX_HISTORY_MESSAGES:]
    return system_msgs + trimmed


# ---------------------------------------------------------------------
# CONFIRM_FORGET FABRICATION FIX
# ---------------------------------------------------------------------


def is_bare_confirmation_with_nothing_staged(user_input: str) -> bool:
    """
    True if the user's message is just a bare yes/no/confirm-style word
    AND there is nothing actually staged in _pending_deletion. This is
    the exact situation where v3.2 testing found the model fabricating
    a fictional "staged for deletion" state -- so instead of trusting
    the model, we short-circuit deterministically in code.
    """
    cleaned = user_input.strip().lower().strip(".!?")
    if cleaned not in _CONFIRMATION_WORDS:
        return False
    idx, _ = get_pending()
    return idx is None


# ---------------------------------------------------------------------
# INCONSISTENT RECALL/LIST_NOTES VERIFICATION FIX
# ---------------------------------------------------------------------


def build_memory_grounding(user_input: str):
    """
    If the user's message looks like a memory/notes query, proactively
    call recall/list_notes ourselves and return a one-off grounding
    message with the real result -- or None if the query doesn't match.
    This is NOT added to persistent history (to avoid system messages
    accumulating unboundedly over a long session); it's meant to be
    appended only to the messages sent for this one model call.
    """
    lowered = user_input.lower()
    wants_facts = any(kw in lowered for kw in _FACT_QUERY_KEYWORDS)
    wants_notes = any(kw in lowered for kw in _NOTE_QUERY_KEYWORDS)

    if not wants_facts and not wants_notes:
        return None

    grounding_lines = []
    if wants_facts:
        grounding_lines.append(f"Actual current recall() result:\n{recall_run()}")
    if wants_notes:
        grounding_lines.append(f"Actual current list_notes() result:\n{list_notes_run()}")

    grounding_text = (
        "[System note -- ground truth, use this rather than guessing or "
        "relying on earlier conversation:]\n" + "\n\n".join(grounding_lines)
    )
    return {"role": "system", "content": grounding_text}


# ---------------------------------------------------------------------
# MODEL CALL WITH RETRY (blank-response safeguard)
# ---------------------------------------------------------------------


def call_model(messages, tool_schemas, retries=1):
    for attempt in range(retries + 1):
        response = ollama.chat(
            model=MODEL,
            messages=messages,
            tools=tool_schemas,
            options={"num_ctx": CONTEXT_TOKENS},
        )
        reply = response["message"]
        has_content = bool(reply.get("content", "").strip())
        has_tool_call = bool(reply.get("tool_calls"))

        if has_content or has_tool_call:
            return reply

        if attempt < retries:
            print("[warning] Model returned an empty reply -- retrying...")

    reply["content"] = (
        reply.get("content")
        or "(No response generated -- you may want to rephrase the question.)"
    )
    return reply


# ---------------------------------------------------------------------
# MAIN TURN HANDLER -- iterative tool-calling loop
# ---------------------------------------------------------------------


def run_turn(messages, tool_schemas, tool_functions):
    """
    Handles one full user turn, looping through as many rounds of tool
    calls as the model needs (up to MAX_TOOL_ROUNDS) before returning
    a final plain-text answer. This is what fixes the old blank-response
    bug -- previously only one round of tool calls was ever processed.
    """
    for round_num in range(MAX_TOOL_ROUNDS):
        reply = call_model(messages, tool_schemas)

        if not reply.get("tool_calls"):
            # Model gave a real answer -- we're done
            return reply.get("content", "")

        messages.append(reply)

        for call in reply["tool_calls"]:
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            func = tool_functions.get(name)

            if func:
                if isinstance(args, str):
                    args = json.loads(args)
                result = func(**args) if args else func()
            else:
                result = f"Unknown tool: {name}"

            print(f"[tool call] {name}({args}) -> {result}")
            messages.append({"role": "tool", "content": str(result)})

    # Hit the round cap without a final answer -- ask directly, no tools,
    # forcing the model to summarize rather than chain further
    print("[warning] Hit max tool-call rounds -- forcing a final answer.")
    final = ollama.chat(
        model=MODEL,
        messages=messages,
        options={"num_ctx": CONTEXT_TOKENS},
    )
    return final["message"].get("content", "(No response generated.)")


def run_agent():
    tool_schemas, tool_functions = load_skills()
    print(f"Loaded skills: {', '.join(tool_functions.keys())}")

    messages = [{"role": "system", "content": build_system_prompt()}]
    print(f"Agent ready ({MODEL}). Type 'exit' or 'quit' to stop.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break
        if not user_input:
            continue

        # Fix: intercept bare yes/no when nothing is staged, BEFORE the
        # model ever sees it -- eliminates the fabrication failure mode
        # found in v3.2 testing entirely, since the model isn't consulted.
        if is_bare_confirmation_with_nothing_staged(user_input):
            reply_text = (
                "There's nothing pending to confirm right now. If you'd "
                "like to forget something, just tell me what to remove."
            )
            print(f"Assistant: {reply_text}\n")
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": reply_text})
            messages = trim_history(messages)
            continue

        messages.append({"role": "user", "content": user_input})
        messages = trim_history(messages)

        # Fix: proactively ground memory/notes queries with real tool
        # output before the model responds, regardless of whether it
        # chooses to call recall/list_notes itself. This is appended
        # only to the messages sent for THIS call, not saved to
        # persistent history, so it doesn't accumulate over a session.
        grounding = build_memory_grounding(user_input)
        call_messages = messages + [grounding] if grounding else messages

        final_text = run_turn(call_messages, tool_schemas, tool_functions)
        print(f"Assistant: {final_text}\n")

        # run_turn mutates call_messages in place (appending any tool-call
        # turns) -- sync that back to persistent history, but strip out
        # the ephemeral grounding note itself so it doesn't get saved.
        if grounding:
            call_messages.remove(grounding)
        messages = call_messages
        messages.append({"role": "assistant", "content": final_text})


if __name__ == "__main__":
    try:
        run_agent()
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye!")
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure Ollama is running and the model is pulled.")
