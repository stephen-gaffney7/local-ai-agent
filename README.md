# Local Lightweight AI Agent (Ollama + qwen2.5) Use Case Development

A Python-based conversational agent that runs entirely on a local, free LLM via Ollama without the need for an API key, subscription, or token limits. Built incrementally as a demonstratable use-case project, starting from a basic chat loop and evolving into a tool-using agent with persistent memory and a modular skill system.

---

## Overview

**Model:** `qwen2.5:3b`, served locally through Ollama as other models were too computationally taxing
**Language:** Python 3.13.13
**IDE used:** Spyder

The agent can:
- Hold a conversation with sliding-window short-term memory
- Call real Python helper functions ("skills") when it decides they're needed: calculator (including sqrt/abs/round), clock, unit conversion, file reading, memory management, timestamped notes
- Save and retrieve facts in a persistent long-term memory file that survives restarts, plus a separate timestamped notes log
- Load new skills automatically by dropping a `.py` file into a `skills` folder: no code changes required
- Confirm with me before actually deleting anything from memory, rather than deleting on the first request

---

## Project Structure

```
AI Research - July 2026/
├── agent_with_tools_v3_2.py    # main script — current version
├── memory.json                  # persistent long-term facts (auto-created)
├── notes.json                   # persistent timestamped notes (auto-created)
├── test_notes.txt               # sample file used for read_file testing
├── agent_testing_results.xlsx   # test case log from V1-V3.2 testing sessions
└── skills/
    ├── __init__.py               # marks the folder as a Python package
    ├── _memory_store.py          # shared load/save helpers for facts (not a tool itself)
    ├── _notes_store.py           # shared load/save helpers for notes (not a tool itself)
    ├── _pending_deletion.py      # tracks a staged (unconfirmed) deletion in memory (not a tool itself)
    ├── calculator.py             # safe arithmetic evaluation, plus sqrt/abs/round/pow
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

Earlier, simpler versions (`basic_chat_agent.py`, `agent_with_tools.py`, `agent_with_tools_v2.py`, `agent_with_tools_v3.py`, `agent_with_tools_v3_1.py`) are kept in a `deprecated/` folder in the GitHub repo for reference but are superseded by `agent_with_tools_v3_2.py`.

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
   python agent_with_tools_v3_2.py
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
Deleting a fact is a two-step process as of v3: `forget` finds a match (by index or text snippet) and *stages* it without deleting anything, then I have to explicitly confirm before `confirm_forget` actually removes it. If a text snippet matches more than one saved fact, nothing is staged — it lists the matches and asks me to specify an index instead. NOTE: indexing is 0-based, so the first entry is `[0]`, the second is `[1]`, and so on. As of v3.2, matching also normalizes punctuation and whitespace before comparing, so a stray trailing period on the model's part won't cause a false "no match" — though matching is still substring-based, so a paraphrased search term that doesn't literally appear in the saved fact still won't match (see Known Bugs below).

### Short-term memory
Conversation history is trimmed to the last 12 messages, but this is customizable (`MAX_HISTORY_MESSAGES`) each turn, so response time doesn't keep degrading as a session gets longer. `CONTEXT_TOKENS` is also customizable, currently set to 4096 (up from Ollama's default of 2048) to give the model more room, balanced against local RAM concerns.

### Blank-response safeguard + iterative tool loop
Occasionally the model returns an empty reply with no tool call. `call_model()` detects this and automatically retries once, printing a `[warning]` when it happens. As of v3, I also found and fixed the actual root cause of most blank replies: the original loop only processed one round of tool calls per turn, so if the model wanted to chain a second tool call before answering, that request got silently dropped. The turn handler now loops through tool calls (capped at `MAX_TOOL_ROUNDS`) until it produces a real answer.

---

## v3.2 Bug-Fix Results

Full test logs for every version live in `agent_testing_results.xlsx` (one sheet per version). v3.2 targeted four bugs found in v3.1 testing. Here's how each one actually held up under a full retest:

**Confirmed fixed:**
- **Calculator sqrt/abs/round override** — fully fixed. The tool now actually supports these operations, so there's no error left for the model to override with a guess. Verified correct on every retest.
- **`add_note` argument corruption** — fully fixed. Both notes saved as clean plain strings this round, no malformed nested objects. The defensive coercion plus shortened tool descriptions both seem to have helped.

**Partially fixed / new failure modes surfaced:**
- **`forget` punctuation-sensitivity** — the specific bug (trailing punctuation causing a false "no match") is fixed and verified. But testing surfaced a related, different limitation: since matching is still substring-based, if I (or the model) describe a fact using a paraphrase instead of a literal snippet of the saved text, it still won't match. This isn't something v3.2 was designed to fix, but it's a real practical constraint worth addressing next.
- **Stuck-loop / false confirmation after a failed forget** — the original symptom (asking for yes/no confirmation right after correctly reporting no match) is fixed. But a **new and more concerning version showed up** in the previously-untested `confirm_forget` misuse case: saying "yes" when nothing was actually staged caused the assistant to fabricate an entirely fictional "staged for deletion" state, with no tool call behind it at all. That false belief even persisted into a following, unrelated request before finally being dropped. Ground truth was never at risk (no tool call means no data was touched), but this is a real regression I want to prioritize in v3.3.
- **Selective tool-dropping in multi-part requests** — improved but inconsistent. One multi-part prompt correctly chained both needed tools; another only called one of the two and then falsely claimed memory was empty when it wasn't, without ever calling `recall` to check.

**New issue found (not part of v3.2's original scope):**
- **`convert_units` going unused** — in this round's testing, the model never actually called the `convert_units` tool, instead manually computing conversions via `calculator` with hardcoded constants. Answers happened to be numerically correct, but this bypasses the tool's built-in mismatched-category safety check entirely (that specific test case got the right answer through the model's own reasoning, not the tool's error handling).

---

## Known Bugs I'm Currently Tracking (fixing in v3.3 before new functionality)

- **`confirm_forget` fabricating staged deletions:** saying "yes" or similar with nothing actually staged should either be ignored or clearly state nothing is pending — not invent a fictional staged entry. This is the top priority for v3.3.
- **Forget matching is paraphrase-fragile:** substring matching means the model has to reproduce a literal snippet of the saved fact, not a summary of it. Considering fuzzy/keyword-based matching as a next step.
- **`convert_units` bypass:** need to strengthen the tool description or system prompt so unit conversions reliably go through the dedicated tool rather than ad hoc arithmetic.
- **Inconsistent recall verification:** "what's saved in memory" answers aren't always backed by an actual `recall` call — sometimes accurate from context, sometimes confidently wrong (this round, a real regression: falsely claimed empty memory when facts existed).
- **Ambiguous-decline comprehension:** softer phrasing like "don't forget either" isn't always understood on the first try; only a blunter "Neither" reliably registers.

---

## Possible Next Steps (after v3.3 bug fixes)

- Expand skills (web search, web-scraping, unit conversion refinements)
   - Much further down the line, a Selenium integration would be deeply interesting.
- Try a larger model than `qwen2.5:3b` (e.g. `qwen2.5:7b`) if I get access to more RAM/compute, to compare reliability against the 3B version
- Consider fuzzy or keyword-based matching for `forget` instead of strict substring matching
