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
├── agent_with_tools_v3_3.py    # main script — current version
├── memory.json                  # persistent long-term facts (auto-created)
├── notes.json                   # persistent timestamped notes (auto-created)
├── test_notes.txt               # sample file used for read_file testing
├── agent_testing_results.xlsx   # test case log from V1-V3.3 testing sessions
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
    ├── forget.py                   # stage removal of a fact by index, text snippet, or paraphrase
    ├── confirm_forget.py           # finalize or cancel a staged deletion
    ├── add_note.py                 # save a timestamped note
    ├── list_notes.py               # retrieve all saved notes
    └── read_file.py                # read a local text file's contents
```

Earlier, simpler versions (`basic_chat_agent.py`, `agent_with_tools.py`, `agent_with_tools_v2.py`, `agent_with_tools_v3.py`, `agent_with_tools_v3_1.py`, `agent_with_tools_v3_2.py`) are kept in a `deprecated/` folder in the GitHub repo for reference but are superseded by `agent_with_tools_v3_3.py`.

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
   python agent_with_tools_v3_3.py
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
Deleting a fact is a two-step process as of v3: `forget` finds a match (by index, text snippet, or now paraphrase — see below) and *stages* it without deleting anything, then I have to explicitly confirm before `confirm_forget` actually removes it. If a text snippet matches more than one saved fact, nothing is staged — it lists the matches and asks me to specify an index instead. NOTE: indexing is 0-based, so the first entry is `[0]`, the second is `[1]`, and so on. As of v3.2, matching normalizes punctuation and whitespace before comparing. As of v3.3, matching also tolerates paraphrasing: if the meaningful words in a search target all appear somewhere in a saved fact (regardless of exact wording or order), that counts as a match too, not just literal substrings.

### Deterministic safeguards (code-level, not just prompting)
Two things are handled directly in Python rather than relying on the model to behave correctly:
- **Bare yes/no interception:** if I reply with just "yes," "no," or similar, and nothing is actually staged for deletion, the script answers directly without even consulting the model — eliminating any chance of a fabricated "staged for deletion" claim for that specific case.
- **Memory-query grounding:** if my message looks like a question about what's saved, the script silently calls `recall`/`list_notes` itself and injects the real result into context before the model responds, regardless of whether the model chooses to call the tool on its own.

### Short-term memory
Conversation history is trimmed to the last 12 messages, but this is customizable (`MAX_HISTORY_MESSAGES`) each turn, so response time doesn't keep degrading as a session gets longer. `CONTEXT_TOKENS` is also customizable, currently set to 4096 (up from Ollama's default of 2048) to give the model more room, balanced against local RAM concerns.

### Blank-response safeguard + iterative tool loop
Occasionally the model returns an empty reply with no tool call. `call_model()` detects this and automatically retries once, printing a `[warning]` when it happens. As of v3, I also found and fixed the actual root cause of most blank replies: the original loop only processed one round of tool calls per turn, so if the model wanted to chain a second tool call before answering, that request got silently dropped. The turn handler now loops through tool calls (capped at `MAX_TOOL_ROUNDS`) until it produces a real answer.

---

## v3.3 Bug-Fix Results

Full test logs for every version live in `agent_testing_results.xlsx` (one sheet per version). v3.3 targeted the top issues from v3.2 testing. Here's how it actually held up:

**Confirmed fixed:**
- **Forget paraphrase-fragile matching** — fully fixed and verified. The exact case that failed in v3.2 (a compressed search term like "prefer_metric" against the saved fact "I prefer imperial units over metric") now matches correctly via a new word-subset matching tier, with no regression to normal substring matching.
- **`convert_units` bypass** — fixed for the three valid-conversion test cases this round; the tool was actually called instead of the model computing conversions manually via `calculator`. The mismatched-category case still didn't invoke the tool itself, though the model reasoned through it correctly on its own.
- **Selective tool-dropping in multi-part requests** — both multi-part test prompts correctly chained both needed tools this round, a clean improvement over earlier versions.
- **Ambiguous-decline comprehension** — "Don't forget either" was correctly recognized as a decline on the first attempt this round, an improvement over v3.2 needing two tries.

**Worked as designed, but exposed a real regression:**
- **`confirm_forget` fabrication fix** — the code-level intercept works exactly as intended for its target case (a bare "yes" with nothing staged, tested in isolation, correctly got the deterministic "nothing pending" response with zero model involvement). **However**, this same mechanism is scoped too broadly: it caught ordinary, unrelated "yes" replies too — specifically, when the model added its own unprompted "Is this correct?" after a `remember` call, replying "yes" to that got the canned forget-related deflection instead of just... being acknowledged normally. This is a genuine new bug to fix in v3.4, not just a lingering model-behavior quirk — it's a scoping problem in the fix itself.

**Still an open problem, and possibly a deeper one than expected:**
- **Inconsistent recall verification** — the proactive grounding injection (silently calling `recall`/`list_notes` and putting the real result in context) does work mechanically — verified the correct data was actually injected. But in one case, the model was handed the accurate answer directly in context and **still answered incorrectly**, confidently claiming no facts were saved when 2 real facts existed. This suggests guaranteeing correct data in context isn't sufficient on its own; the model can still choose to ignore it. Also saw a new disambiguation regression in the opposite direction from before: a facts question ("what's saved in memory") triggered a `list_notes` tool call instead of `recall` on two occasions.

---

## Known Bugs I'm Currently Tracking (fixing in v3.4 before new functionality)

- **Bare yes/no intercept over-triggering (new, top priority):** needs to only intercept when the model's own preceding message was actually a forget-confirmation question, not any arbitrary yes/no exchange. Likely fix: track whether the last assistant message was itself a staged-deletion confirmation prompt, rather than intercepting based on user input alone.
- **Grounded data being ignored:** even with accurate `recall`/`list_notes` output silently injected into context, the model gave a confidently false answer once. Need to investigate whether this is a phrasing/prominence issue with how the grounding note is presented, or a deeper limitation.
- **recall vs list_notes disambiguation regression:** a plain "what's saved in memory" question triggered `list_notes` instead of `recall` twice this round — the opposite confusion from earlier versions, suggesting this disambiguation is still fragile rather than solved.
- **File content bleeding into the forget/memory system:** after reading a file, the assistant unprompted referred to its contents as "a timestamped note from your log" and offered to remove it — a minor but real confabulation blending unrelated systems.
- **`convert_units` still not invoked for the mismatched-category case:** works fine for valid conversions now, but the specific safety-check path (incompatible units) still bypasses the tool, even though the conversational answer happens to be correct.

---

## Possible Next Steps (after v3.4 bug fixes)

- Expand skills (web search, web-scraping, unit conversion refinements)
   - Much further down the line, a Selenium integration would be deeply interesting.
- Try a larger model than `qwen2.5:3b` (e.g. `qwen2.5:7b`) if I get access to more RAM/compute, to compare reliability against the 3B version
- Consider whether some of these remaining issues are inherent limits of a 3B model rather than fixable via better prompting/code scaffolding alone
