# LoreMasterBot Build Log

## 2026-09-22 — Day 1

### Baseline

Command:

`python -m pytest -q`

Result:

- 182 passed
- 0 failed
- 1 warning
- Runtime: 4.62s

### Environment note

Running `pytest -q` directly caused `ModuleNotFoundError: No module named 'src'`.

Running pytest through the active project Python environment with:

`python -m pytest -q`

worked correctly.

There is also a non-blocking urllib3 / LibreSSL warning from the current Python 3.9 environment. I am not changing the environment today because it does not affect the passing test baseline.

### Goal for today

I am adding behavioral evaluation without changing agent behavior first because I need a trustworthy before-state.

I want to measure what LoreMasterBot currently does before changing prompts, tool schemas, handlers, or model behavior.

### AI assistance

ChatGPT helped me identify the correct way to run the existing test suite from the project virtual environment.

No production behavior has been changed.

## Request Flow

1. `run()` reads the user's prompt.
2. The prompt is classified as conversational or tool-requiring.
3. The user message is appended to `history`.
4. The first model call receives:
   - `SYSTEM_PROMPT`
   - conversation history
   - `TOOL_SCHEMAS`
5. Non-conversational prompts use `tool_choice="required"`.
6. `parse_tool_calls()` extracts any structured tool calls from the model response.
7. For each tool call:
   - arguments are normalized
   - the tool name is matched against `TOOL_HANDLERS`
   - a Blizzard access token is obtained
   - the matching handler executes
   - the result is stored with its `tool_call_id`
8. One assistant history entry containing all tool calls is appended.
9. Each tool result is appended to history.
10. A second model call receives the system prompt plus that updated history.
11. The model writes the final user-facing answer using the retrieved tool data.
12. The final response is cleaned defensively, added to history, and printed.

### What I understand now

LoreMasterBot is a two-stage tool-calling loop:

`user → model chooses tool → handler gets Blizzard data → model writes final answer`

The tool result becomes part of the conversation history before the second model call, which lets the final response be grounded in the retrieved API data instead of relying only on model memory.