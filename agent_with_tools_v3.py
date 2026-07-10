"""
Task-performing agent -- v3.

New in this version:
    1. FORGET CONFIRMATION: deleting a memory now requires two steps.
       'forget' finds and STAGES a match without deleting it, then the
       model must call 'confirm_forget' with the user's yes/no answer
       before anything is actually removed.
    2. ITERATIVE TOOL LOOP (blank-response fix): earlier versions only
       handled ONE round of tool calls per turn. If the model wanted to
       chain a second tool call before answering, that request was
       silently dropped, which is what caused several of the blank
       responses seen in testing. This version loops through tool calls
       until the model produces a real text answer (capped at
       MAX_TOOL_ROUNDS to avoid infinite loops).
    3. NEW SKILLS: convert_units (length/weight/temperature) and
       add_note / list_notes (timestamped journal entries, separate
       from the fact-based long-term memory).

Folder layout expected next to this script:
    agent_with_tools_v3.py
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

MODEL = "qwen2.5:3b"
MAX_HISTORY_MESSAGES = 12       # sliding window: keep last N messages
CONTEXT_TOKENS = 4096           # override Ollama's default 2048
MAX_TOOL_ROUNDS = 5             # cap on chained tool calls per turn
MEMORY_FILE = Path(__file__).parent / "memory.json"

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
        "their answer. Never call confirm_forget without first asking the user.\n\n"
        "Use 'add_note' for timestamped journal-style entries, and 'remember' for "
        "plain facts with no timestamp. After using any tool, always give a clear "
        "plain-language answer summarizing the result -- don't leave your reply empty.\n\n"
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

        messages.append({"role": "user", "content": user_input})
        messages = trim_history(messages)

        final_text = run_turn(messages, tool_schemas, tool_functions)
        print(f"Assistant: {final_text}\n")
        messages.append({"role": "assistant", "content": final_text})


if __name__ == "__main__":
    try:
        run_agent()
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye!")
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure Ollama is running and the model is pulled.")
