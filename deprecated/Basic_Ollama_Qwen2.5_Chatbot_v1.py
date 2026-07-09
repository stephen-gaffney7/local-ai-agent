# -*- coding: utf-8 -*-
"""
Created on Tue Jul  7 09:32:35 2026

@author: stephen.gaffney
"""

## Exploration Document to Test Agents in Python

# Qwen Capabilities
# It supports long contexts of up to 128K tokens and can generate up to 8K tokens, and has 7.6B parameters with strong multilingual coverage across 29+ languages.
# It's solid at general chat, summarization, structured output (JSON, tables), basic coding help, and reasonably good math for its size — Qwen's team specifically improved coding/math over the prior generation.

# Imports
import ollama

# Basic Chat Loop to Practice and Get Started 
# No API Key, no subscriptions, no token count limits, etc. Just runs locally on the Ollama server
# Intentionally minimal: prompt + running message history + a loop
# Later tools, memory, planning steps, etc. can be added to this
 
MODEL = "qwen2.5"  # Lightweight model pulled so that it runs faster with my hardware restrictions
 
SYSTEM_PROMPT = (
    "You are a helpful, concise AI assistant to a data science consultant. "
    "Answer clearly and ask a clarifying question if the request is ambiguous."
)
 
 
def chat_loop():
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
 
    print(f"Chatting with '{MODEL}' via Ollama. Type 'exit', 'quit', or 'done' to stop.\n")
 
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit", "done"):
            print("Goodbye!")
            break
        if not user_input:
            continue
 
        messages.append({"role": "user", "content": user_input})
 
        # Stream the response so it feels responsive
        print("AI Assistant: ", end="", flush=True)
        full_reply = ""
        for chunk in ollama.chat(model=MODEL, messages=messages, stream=True):
            piece = chunk["message"]["content"]
            print(piece, end="", flush=True)
            full_reply += piece
        print("\n")
 
        messages.append({"role": "assistant", "content": full_reply})
 
 
if __name__ == "__main__":
    try:
        chat_loop()
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye!")
    except Exception as e:
        print(f"\nError: {e}")
        print(
            "Make sure Ollama is running (`ollama serve`) and the model is pulled "
            f"(`ollama pull {MODEL}`)."
        )
