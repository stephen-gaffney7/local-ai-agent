"""
Task-performing agent with tools, persistent memory, and a sliding
context window — built on a local Ollama model (qwen2.5:3b by default - 
a downgrade from the previous model version to account for increased complexity).

WHAT THIS ADDS over the basic chat loop:
    1. TOOLS / SKILLS  - the model can call real Python functions
                         (calculator, save/recall notes, read a file,
                         get the current time) when it decides they're
                         needed, instead of just guessing answers.
    2. LONG-TERM MEMORY - facts you ask it to "remember" are saved to
                         memory.json and persist across script restarts.
    3. SHORT-TERM MEMORY - conversation history is kept, but trimmed
                         to the last N exchanges so responses don't
                         keep getting slower as the chat grows.
"""

import ollama
import json
import os
import ast
import operator
from datetime import datetime

MODEL = "qwen2.5:3b"
MEMORY_FILE = "memory.json"          # persistent long-term notes
MAX_HISTORY_MESSAGES = 12            # sliding window: keep last N messages
CONTEXT_TOKENS = 4096                # override Ollama's default 2048

# ---------------------------------------------------------------------
# 1. TOOLS / SKILLS
#    Each tool is a plain Python function + a JSON schema describing it.
#    The model reads the schemas and decides if/when to call one.
# ---------------------------------------------------------------------

SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.USub: operator.neg,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPS:
        return SAFE_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPS:
        return SAFE_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Unsupported expression")


def calculator(expression: str) -> str:
    """Safely evaluate a basic arithmetic expression (+, -, *, /, **)."""
    try:
        result = _safe_eval(ast.parse(expression, mode="eval").body)
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"


def get_current_time() -> str:
    """Return the current date and time."""
    return datetime.now().strftime("%A, %B %d %Y, %I:%M %p")


def remember(fact: str) -> str:
    """Save a fact to persistent long-term memory (survives restarts)."""
    memory = _load_memory()
    memory.append(fact)
    _save_memory(memory)
    return f"Saved to memory: {fact}"


def recall(_: str = "") -> str:
    """Return everything currently stored in long-term memory."""
    memory = _load_memory()
    if not memory:
        return "Long-term memory is empty."
    return "\n".join(f"- {item}" for item in memory)


def read_file(path: str) -> str:
    """Read and return the text contents of a local file (first 2000 chars)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(2000)
        return content if content else "(file is empty)"
    except Exception as e:
        return f"Error reading file: {e}"


# Map tool name -> actual Python function
TOOL_FUNCTIONS = {
    "calculator": calculator,
    "get_current_time": get_current_time,
    "remember": remember,
    "recall": recall,
    "read_file": read_file,
}

# JSON schemas describing each tool to the model (OpenAI-style tool spec,
# which Ollama's tool-calling models understand)
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a basic arithmetic expression.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "e.g. '12 * (3 + 4)'"}
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save a fact or note to permanent long-term memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The fact or note to remember"}
                },
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Retrieve everything currently saved in long-term memory.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
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
    },
]

# ---------------------------------------------------------------------
# 2. PERSISTENT LONG-TERM MEMORY (JSON file on disk)
# ---------------------------------------------------------------------


def _load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)


# ---------------------------------------------------------------------
# 3. SHORT-TERM MEMORY (sliding window trim)
# ---------------------------------------------------------------------


def trim_history(messages):
    """Keep the system prompt plus only the most recent N messages."""
    system_msgs = [m for m in messages if m["role"] == "system"]
    other_msgs = [m for m in messages if m["role"] != "system"]
    trimmed = other_msgs[-MAX_HISTORY_MESSAGES:]
    return system_msgs + trimmed


# ---------------------------------------------------------------------
# MAIN AGENT LOOP
# ---------------------------------------------------------------------


def build_system_prompt():
    long_term = _load_memory()
    memory_block = (
        "\n".join(f"- {item}" for item in long_term)
        if long_term
        else "(nothing saved yet)"
    )
    return (
        "You are a helpful assistant with access to tools. Use them when they "
        "would give a more accurate answer than guessing (math, current time, "
        "saved notes, file contents). Otherwise answer directly and concisely.\n\n"
        f"Known long-term memory:\n{memory_block}"
    )


def run_agent():
    messages = [{"role": "system", "content": build_system_prompt()}]
    print(f"Agent ready ({MODEL}). Tools: calculator, time, remember, recall, read_file.")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        messages = trim_history(messages)

        response = ollama.chat(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            options={"num_ctx": CONTEXT_TOKENS},
        )

        reply = response["message"]

        # If the model wants to call one or more tools, execute them
        if reply.get("tool_calls"):
            messages.append(reply)  # keep the assistant's tool-call turn

            for call in reply["tool_calls"]:
                name = call["function"]["name"]
                args = call["function"]["arguments"]
                func = TOOL_FUNCTIONS.get(name)

                if func:
                    if isinstance(args, str):
                        args = json.loads(args)
                    result = func(**args) if args else func()
                else:
                    result = f"Unknown tool: {name}"

                print(f"[tool call] {name}({args}) -> {result}")
                messages.append({"role": "tool", "content": str(result)})

            # Ask the model to produce a final natural-language answer
            # now that it has the tool results
            follow_up = ollama.chat(
                model=MODEL,
                messages=messages,
                options={"num_ctx": CONTEXT_TOKENS},
            )
            final_text = follow_up["message"]["content"]
            print(f"Assistant: {final_text}\n")
            messages.append({"role": "assistant", "content": final_text})

        else:
            final_text = reply["content"]
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
