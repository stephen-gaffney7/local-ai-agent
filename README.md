# Local Lightweight AI Agent (Ollama + qwen2.5) Use Case Development

A Python-based conversational agent that runs entirely on a local, free LLM via Ollama without the need for an API key, subscription, or token limits. Built incrementally as a demonstratable use-case project, starting from a basic chat loop and evolving into a tool-using agent with persistent memory and a modular skill system.

---

## Overview

**Model:** `qwen2.5:3b`, served locally through Ollama as other models were too computationally taxing
**Language:** Python 3.13.13
**IDE used:** Spyder

The agent can:
- Hold a conversation with sliding-window short-term memory
- Call real Python helper functions ("skills") when it decides they're needed: calculator, clock, unit conversion, file reading, memory management, timestamped notes
- Save and retrieve facts in a persistent long-term memory file that survives restarts, plus a separate timestamped notes log
- Load new skills automatically by dropping a `.py` file into a `skills` folder: no code changes required
- Confirm with me before actually deleting anything from memory, rather than deleting on the first request

---

## Project Structure

```
AI Research - July 2026/
├── agent_with_tools_v3_1.py    # main script — current version
├── memory.json                  # persistent long-term facts (auto-created)
├── notes.json                   # persistent timestamped notes (auto-created)
├── test_notes.txt               # sample file used for read_file testing
├── agent_testing_results.xlsx   # test case log from V1-V3.1 testing sessions
└── skills/
    ├── __init__.py               # marks the folder as a Python package
    ├── _memory_store.py          # shared load/save helpers for facts (not a tool itself)
    ├── _notes_store.py           # shared load/save helpers for notes (not a tool itself)
    ├── _pending_deletion.py      # tracks a staged (unconfirmed) deletion in memory (not a tool itself)
    ├── calculator.py             # safe arithmetic evaluation
    ├── current_time.py           # current date/time
    ├── convert_units.py          # length/weight/temperature conversion
    ├── remember.py                # save a fact to long-term memory
    ├── recall.py                  # retrieve all saved facts
    ├── forget.py                   # stage removal of a fact by index or text match
    ├── confirm_forget.py           # finalize or cancel a staged deletion
    ├── add_note.py                 # save a timestamped note
    ├── list_notes.py               # retrieve all saved notes
    └── read_file.py                # read a local text file's contents
```

Earlier, simpler versions (`basic_chat_agent.py`, `agent_with_tools.py`, `agent_with_tools_v2.py`, `agent_with_tools_v3.py`) are kept in a `deprecated/` folder in the GitHub repo for reference but are superseded by `agent_with_tools_v3_1.py`.

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
5. **Set your working directory** (in Spyder: Tools → Preferences → Current working directory) to this project folder, so relative paths (`test_notes.txt`, etc.) resolve correctly.
6. **Run the agent:**
   ```bash
   python agent_with_tools_v3_1.py
   ```
   On startup you should see:
   ```
   Loaded skills: add_note, calculator, confirm_forget, convert_units, get_current_time, forget, list_notes, read_file, recall, remember
   ```

---

## How It Works

### Skills (tools)
Each file in `skills` defines a `TOOL_SCHEMA` (a JSON description of the tool) and a `run()` function (the actual logic). At startup, the main script scans the folder and wires everything up automatically. The model reads the schemas and decides on its own when a tool call is warranted versus answering directly.

**To add a new skill:** create a new `.py` file in the `skills` folder following the same pattern — no changes to the main script needed.

### Two separate memory systems
I split memory into two distinct stores, since I found the model needs a clear distinction between them:
- **Facts** (`memory.json`, no timestamp): saved via `remember`, retrieved via `recall`. For things like my dog's name or unit preferences.
- **Notes** (`notes.json`, timestamped): saved via `add_note`, retrieved via `list_notes`. For journal-style, logged-in-time entries.

Both use `Path(__file__).parent` so they're found reliably regardless of whatever working directory Python happens to be using, and both are loaded fresh every time the script starts, so everything persists across restarts.

### Two-step forget confirmation
Deleting a fact is a two-step process as of v3: `forget` finds a match (by index or text snippet) and *stages* it without deleting anything, then I have to explicitly confirm before `confirm_forget` actually removes it. If a text snippet matches more than one saved fact, nothing is staged — it lists the matches and asks me to specify an index instead. NOTE: indexing is 0-based, so the first entry is `[0]`, the second is `[1]`, and so on.

### Short-term memory
Conversation history is trimmed to the last 12 messages, but this is customizable (`MAX_HISTORY_MESSAGES`) each turn, so response time doesn't keep degrading as a session gets longer. `CONTEXT_TOKENS` is also customizable, currently set to 4096 (up from Ollama's default of 2048) to give the model more room, balanced against local RAM concerns.

### Blank-response safeguard + iterative tool loop
Occasionally the model returns an empty reply with no tool call. `call_model()` detects this and automatically retries once, printing a `[warning]` when it happens. As of v3, I also found and fixed the actual root cause of most blank replies: the original loop only processed one round of tool calls per turn, so if the model wanted to chain a second tool call before answering, that request got silently dropped. The turn handler now loops through tool calls (capped at `MAX_TOOL_ROUNDS`) until it produces a real answer.

---

## Known Bugs I'm Currently Tracking

Full test logs for every version live in `agent_testing_results.xlsx` (one sheet per version). As of v3.1, I've found a few real bugs I plan to fix in **v3.2 before adding any new functionality**:

- **`add_note` argument corruption:** in v3.1 testing, the model sometimes passed a malformed nested object (echoing the tool's own JSON-schema keys) instead of a plain string, which corrupted the saved note content. Suspect this is related to the longer, more detailed tool descriptions I added in v3.1 for disambiguation purposes — worth testing whether shortening them fixes this without reintroducing the recall/list_notes confusion it was meant to solve.
- **`forget` punctuation-sensitivity:** since matching is done via substring, a search target with extra punctuation (e.g. a trailing period the model added on its own) can fail to match a saved fact that doesn't have it, producing a false "no match" on something that actually exists. I plan to normalize/strip punctuation before comparing.
- **Stuck-loop after a failed forget:** related to the bug above — after a false "no match," the assistant asked for yes/no confirmation on nothing actually staged, then repeated the identical response verbatim across multiple turns instead of progressing. Needs investigation into why no tool call was being made during the repeats.
- **Selective tool-dropping in multi-part requests:** occasionally, when asked two things in one message (e.g. "what's today's date, and what notes have I saved"), only one of the two needed tools gets called, and the model sometimes falsely claims the missing capability "isn't provided" rather than just not having called it. Inconsistent — other multi-part requests in the same session chained both tools correctly.
- **Tool-verified answers ignored:** on the `sqrt(16)` test case, `calculator` correctly returns an "unsupported expression" error, but the model answers "4" anyway from its own knowledge, with the same confident tone as tool-verified results. This one's been present since v1 testing and isn't specific to any single skill — worth deciding whether to expand `calculator`'s supported operations or add stronger prompting around respecting tool errors.
- **Narration not always backed by a tool call:** several "what's saved in memory" answers were accurate but weren't actually verified via a fresh `recall`/`list_notes` call — the model answered from short-term chat context instead. Correct so far, but not a habit I want to rely on.

---

## Possible Next Steps (after v3.2 bug fixes)

- Expand skills (web search, web-scraping, unit conversion refinements)
   - Much further down the line, a Selenium integration would be deeply interesting.
- Try a larger model than `qwen2.5:3b` (e.g. `qwen2.5:7b`) if I get access to more RAM/compute, to compare reliability against the 3B version
- Revisit whether tool descriptions can be both explicit enough to disambiguate similar tools and short enough to avoid destabilizing argument-filling
