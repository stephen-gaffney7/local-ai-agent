"""
Task-performing agent with drop-in skills, persistent memory, and a
sliding context window — built on a local Ollama model.

Folder layout expected next to this script:
    agent_with_tools.py
    skills/
        __init__.py          (empty, makes skills/ a package)
        _memory_store.py      (shared helper, not a tool)
        calculator.py
        current_time.py
        remember.py
        recall.py
        forget.py
        read_file.py

HOW SKILLS WORK:
    Each file in skills/ (except ones starting with "_") must define:
        TOOL_SCHEMA = {...}   # OpenAI-style function schema dict
        def run(**kwargs):    # the actual Python logic
            ...
    The loader below scans the folder and wires them up automatically.
    To add a new capability, just drop a new .py file in skills/ that
    follows this pattern -- no need to touch this main script at all.

WHAT'S NEW IN THIS VERSION:
    1. Skills auto-load from skills/ instead of being hardcoded here.
    2. New "forget" skill lets you remove/correct memory entries.
    3. Retry safeguard: if the model returns an empty reply with no
       tool call (the blank-response bug from earlier testing), the
       script automatically retries once before giving up, and tells
       you when that happens so it's not silently swallowed.
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
MEMORY_FILE = Path(__file__).parent / "memory.json"

# ---------------------------------------------------------------------
# SKILL AUTO-LOADER
# ---------------------------------------------------------------------


def load_skills():
    """Scan skills/ for modules exposing TOOL_SCHEMA + run(), and wire them up."""
    tool_schemas = []
    tool_functions = {}

    for _, module_name, _ in pkgutil.iter_modules(skills_package.__path__):
        if module_name.startswith("_"):
            continue  # skip shared helpers like _memory_store
        module = importlib.import_module(f"skills.{module_name}")
        if hasattr(module, "TOOL_SCHEMA") and hasattr(module, "run"):
            name = module.TOOL_SCHEMA["function"]["name"]
            tool_schemas.append(module.TOOL_SCHEMA)
            tool_functions[name] = module.run
        else:
            print(f"[skills] Skipping '{module_name}.py' -- missing TOOL_SCHEMA or run()")

    return tool_schemas, tool_functions


# ---------------------------------------------------------------------
# LONG-TERM MEMORY (for building the system prompt; skills handle read/write)
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
        "would give a more accurate answer than guessing (math, current time, "
        "saved notes, file contents). Use 'forget' if the user asks you to "
        "remove or correct a saved memory. Otherwise answer directly and "
        "concisely.\n\n"
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
# MAIN AGENT LOOP
# ---------------------------------------------------------------------


def get_model_reply(messages, tool_schemas, retries=1):
    """
    Call the model, and if it comes back with neither text nor a tool
    call (the blank-response bug), retry once before giving up.
    """
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

    # All retries exhausted -- return whatever we last got, plus a note
    reply["content"] = (
        reply.get("content") or
        "(No response generated -- you may want to rephrase the question.)"
    )
    return reply


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

        reply = get_model_reply(messages, tool_schemas)

        if reply.get("tool_calls"):
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

            follow_up = get_model_reply(messages, tool_schemas)
            final_text = follow_up.get("content", "")
            print(f"Assistant: {final_text}\n")
            messages.append({"role": "assistant", "content": final_text})

        else:
            final_text = reply.get("content", "")
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
