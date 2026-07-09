# Local Lightweight AI Agent (Ollama + qwen2.5) Use Case Development

A Python-based conversational agent that runs entirely on a local, free LLM via Ollama without the need for an API key, subscription, or token limits. Built incrementally as a demonstratable use-case project, starting from a basic chat loop and evolving into a tool-using agent with persistent memory and a modular skill system.

---

## Overview

**Model:** `qwen2.5:3b`, served locally through Ollama as other models were too computationally taxing
**Language:** Python 3.13.13
**IDE used:** Spyder

The agent can:
- Hold a conversation with sliding-window short-term memory
- Call real Python helper functions ("skills") when it decides they're needed: calculator, clock, file reading, memory management
- Save and retrieve facts in a persistent long-term memory file that survives restarts
- Load new skills automatically by dropping a `.py` file into a `skills` folder: no code changes required

---

## Project Structure

```
AI Research - July 2026/
├── agent_with_tools_v2.py     # main script — current version
├── memory.json                 # persistent long-term memory (auto-created)
├── test_notes.txt              # sample file used for read_file testing
├── agent_testing_results.xlsx  # test case log from V1/V2 testing sessions
└── skills/
    ├── __init__.py              # marks the folder as a Python package
    ├── _memory_store.py         # shared load/save helpers (not a tool itself)
    ├── calculator.py            # safe arithmetic evaluation
    ├── current_time.py          # current date/time
    ├── remember.py               # save a fact to long-term memory
    ├── recall.py                 # retrieve all saved facts
    ├── forget.py                  # remove a fact by index or text match
    └── read_file.py              # read a local text file's contents
```

Earlier, simpler versions (`basic_chat_agent.py`, `agent_with_tools.py`) were kept for reference but are superseded by `agent_with_tools_v2.py`.

---

## Setup

1. **Install Ollama** [ollama.com/download](https://ollama.com/download)
2. **Pull the model in your terminal:**
   ```bash
   ollama pull qwen2.5:3b
   ```
3. **Install the Python client:**
   ```bash
   pip install ollama
   ```
4. **Confirm Ollama is running:**
   ```bash
   curl http://localhost:11434
   ```
   Should return `Ollama is running`. If not, start it manually with `ollama serve`.
5. **Set your working directory** (in Spyder: Tools → Preferences → Current working directory) to this project folder, so relative paths (`memory.json`, `test_notes.txt`) resolve correctly.
6. **Run the agent:**
   ```bash
   python agent_with_tools_v2.py
   ```
   On startup you should see:
   ```
   Loaded skills: calculator, get_current_time, forget, read_file, recall, remember
   ```

---

## How It Works

### Skills (tools)
Each file in `skills` defines a `TOOL_SCHEMA` (a JSON description of the tool) and a `run()` function (the actual logic). At startup, the main script scans the folder and wires everything up automatically. The model reads the schemas and decides on its own when a tool call is warranted versus answering directly.

**To add a new skill:** create a new `.py` file in `skills` folder following the same pattern — no changes to the main script needed.

### Long-term memory
Saved via the `remember` skill to `memory.json`, located next to the script (using `Path(__file__).parent` so it's independent of whatever working directory Python happens to be using). This file is loaded into the system prompt every time the script starts, so facts persist across sessions. `recall` reads it back; `forget` removes entries by index (e.g., `"2"`) or by a text snippet — if a snippet matches multiple entries, nothing is deleted and the matches are listed so you can specify an index instead. NOTE: Index is 0 based so the first entry will be 0, the second entry will be 1, and so on.

### Short-term memory
Conversation history is trimmed to the last 12 messages, but this is customizable (`MAX_HISTORY_MESSAGES`) each turn, so response time doesn't keep degrading as a session gets longer. `CONTEXT_TOKENS` is also customizable, currently set to 4096 (up from Ollama's default of 2048) to give the model more room, balanced for local RAM concerns.

### Blank-response safeguard
Occasionally the model returns an empty reply with no tool call. `get_model_reply()` detects this and automatically retries once, printing a `[warning]` message so the retry is visible rather than silent. NOTE: This has not been working in some of my recent tests. I am looking into this currently.

---

## Known Issues from Testing

Testing (v1 and v2 logged in `agent_testing_results.xlsx`) showed the tools themselves are reliable: calculator, remember, recall, forget, and read_file consistently returned correct results. Most observed failures were the **model's narration diverging from what its own tools actually did or reported**, for example:

- Overriding a tool's error with a guessed answer, stated with the same confidence as verified results
- Claiming a `forget` action succeeded when the tool had actually refused (ambiguous match) or when no tool call fired at all
- Off-by-one mistakes when deleting memory "by entry number". The model did not know it used index based counting and counted naturally.
- Occasional blank responses after a tool call (the safeguard above mitigates but doesn't fully eliminate this)

---

## Possible Next Steps

- Add a confirmation step before `forget` executes, echoing back what will be deleted
- Expand skills (web search, web-scraping, note-taking with timestamps, unit conversion)
   - Much further down the line, a selenium integration would be deeply interesting.
- Investigate the remaining blank-response cases more deeply and try to find a solution
- Try a larger model than `qwen2.5:7b` if RAM allows or if I get access to more computation/memory, to compare reliability against the 3B version