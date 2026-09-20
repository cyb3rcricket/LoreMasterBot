# Main bot runtime: client setup, tool schema, chat loop, and tool-call orchestration.
#
# Data flow for a lore question:
#   user types a question
#   → first model call (may request tools)
#   → this file runs each tool handler
#   → handlers call the Blizzard API
#   → tool results are added to conversation history
#   → second model call writes the spoken reply
#
# A "tool" is a function the language model is allowed to request. The model
# does not call Blizzard itself. It names a tool and arguments; Python runs it.
from openai import OpenAI
import json
import re
import time
import threading
import itertools
import sys
import uuid
from types import SimpleNamespace

from src.config import (
    SYSTEM_PROMPT,
    MODEL_NAME,
    CLIENT_ID,
    CLIENT_SECRET,
    print_missing_credentials_warning,
)
from src.api import blizzard as blizzard_api
from src.api.blizzard import ensure_valid_token, get_access_token
from src.tools.handlers import TOOL_HANDLERS
from src.tools.schemas import TOOL_SCHEMAS

# Exact-match greetings and filler. These skip Blizzard lookups. Short WoW
# names such as "Invincible" are intentionally NOT in this list. An older bug
# treated those names as chit-chat, so the model answered from memory.
CONVERSATIONAL_PHRASES = (
    "thanks", "thank you", "ok", "okay", "cool", "got it",
    "nice", "great", "awesome", "lol", "haha", "bye", "goodbye",
    "hello", "hi", "hey", "yes", "no", "sure", "sounds good",
    "that's helpful", "interesting", "wow"
)

# The openai library speaks the OpenAI Chat Completions format. Ollama is a
# program that runs models on this computer and exposes the same format at
# localhost:11434. We are not calling OpenAI's paid cloud API. The api_key
# value is a required dummy; Ollama ignores it.
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

# Conversation history is a list of message dictionaries sent back to the
# model on later turns. Each item has a role such as "user", "assistant", or
# "tool". Tool turns also store IDs that link a request to its result.
# This list is process-wide so tests can inspect it after run() returns.
history = []


class ToolCall:
    """A tool request that looks like the official API object.

    Fallback parsing builds these by hand. The chat loop then reads
    `.id` and `.function.name` / `.function.arguments` the same way it
    would read a real model tool call.

    id: unique string that later tool-result messages must repeat.
    name: which handler to run, such as "lookup_item".
    arguments: a dict or JSON string of parameters.
    """
    def __init__(self, id=None, name=None, arguments=None):
        self.id = id
        # Using SimpleNamespace for a simple object with dynamic attributes
        self.function = SimpleNamespace(name=name, arguments=arguments)


class Spinner:
    """
    A simple threaded spinner for showing loading progress.
    Displays a message with a spinning animation using standard library only.

    A thread is a second line of work that can run while the main program
    waits on the network. start() launches that work; stop() asks it to
    finish and waits so the spinning characters do not overwrite the reply.
    """
    def __init__(self, message="Loading..."):
        self.message = message
        self.spinner = itertools.cycle(['-', '/', '|', '\\'])
        self.running = False
        self.thread = None

    def spin(self):
        while self.running:
            sys.stdout.write(f'\r{self.message} {next(self.spinner)}')
            sys.stdout.flush()
            time.sleep(0.1)
        # Clear the line when stopped
        sys.stdout.write('\r' + ' ' * (len(self.message) + 2) + '\r')
        sys.stdout.flush()

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.spin, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()


def parse_tool_calls(response_message):
    """
    Collect tool requests from a model message.

    Standard path: the API fills `response_message.tool_calls`. That is the
    official list and must win if it is present.

    Fallback path: some local models write a JSON array into `content`
    instead of filling tool_calls. This function scrapes those arrays and
    builds ToolCall objects. Each fallback call gets a generated
    `call_<32 hex digits>` id because later history messages must link a
    result to a request. Without an id, the next model call can fail.

    Returns a list of ToolCall-like objects.
    Modifies response_message.content in place if tool calls are parsed from content.
    """
    tool_calls = response_message.tool_calls or []
    if not tool_calls and response_message.content:
        # Fallback: parse tool calls from message content (for models that output tools in text)
        json_matches = re.findall(r"\[.*?\]", response_message.content)
        for match in json_matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, list) and parsed:
                    for item in parsed:
                        if isinstance(item, dict) and "name" in item and "arguments" in item:
                            tool_calls.append(ToolCall(id=f"call_{uuid.uuid4().hex}", name=item["name"], arguments=json.dumps(item["arguments"])))
            except Exception:
                continue
        # Remove the tool call JSON from the content
        if tool_calls:
            response_message.content = re.sub(r"\[.*?\]$", "", response_message.content).strip()
    return tool_calls


def trim_history(history, max_turns=7):
    """
    Drop old conversation turns so the prompt stays a manageable size.

    A turn is: user message + any tool requests/results + the final assistant
    reply (the assistant message that has spoken `content`).

    History must not be sliced by raw message count. A naive slice can cut
    through the middle of a tool-call group and leave an orphan tool result.
    The next model request would then see a broken protocol.

    Always preserves the most recent turn completely, including all tool-related messages.
    """
    turns = []
    i = 0
    while i < len(history):
        if history[i]['role'] == 'user':
            turn_start = i
            # Find the next assistant message with content (final response)
            j = i + 1
            while j < len(history):
                if history[j]['role'] == 'assistant' and history[j].get('content'):
                    turn_end = j
                    turns.append((turn_start, turn_end))
                    i = j
                    break
                j += 1
            else:
                # No complete turn found, stop
                break
        i += 1
    
    if len(turns) <= max_turns:
        return history
    
    # Keep from the start of the (max_turns)th turn from the end
    keep_from = turns[-max_turns][0]
    return history[keep_from:]


def is_conversational_prompt(user_prompt):
    """Return True only for known casual phrases that should not force a tool.

    Matching is exact after trim, lowercase, and stripping simple punctuation.
    Anything else, including a one-word mount name, is treated as a lore query.
    """
    user_text = user_prompt.strip().lower().rstrip("!.,?")
    return user_text in CONVERSATIONAL_PHRASES


def _normalize_tool_arguments(raw_arguments):
    """
    Turn whatever the model stored as arguments into two values.

    Returns (function_args_or_None, stored_arguments_string).

    Why two values exist:
    - function_args is a dict the handler can read, or None if execution
      must be skipped.
    - stored_arguments is always a string written into history.

    History arguments must stay strings. A past bug stored a dict or a
    ToolCall object. json.dumps(history) then failed, and the next model
    request crashed. The cases below are locked by regression tests:

    - dict → use it, store json.dumps(dict)
    - JSON object string → parse it, store the original string
    - malformed string → do not run the handler, store the raw text
    - None / list / number / other → do not run the handler, store JSON text
    """
    if isinstance(raw_arguments, dict):
        return raw_arguments, json.dumps(raw_arguments)
    if isinstance(raw_arguments, str):
        stored_arguments = raw_arguments
        try:
            function_args = json.loads(raw_arguments)
            if not isinstance(function_args, dict):
                return None, stored_arguments
            return function_args, stored_arguments
        except (json.JSONDecodeError, TypeError):
            return None, stored_arguments
    try:
        stored_arguments = json.dumps(raw_arguments)
    except (TypeError, ValueError):
        stored_arguments = "null"
    return None, stored_arguments


def _authenticate_blizzard():
    """Ask Blizzard for an access token when the chat loop actually starts.

    An access token is a short-lived password for API calls. This is not run
    at import time, so `import src.bot` does not hit the network.
    """
    print("Authenticating with Blizzard...")
    token, expires_in = get_access_token()
    if token:
        blizzard_api.blizzard_token = token
        blizzard_api.token_expiry = time.time() + expires_in
        print("Authentication successful!")
    else:
        print("Could not authenticate with Blizzard. API lookups will be unavailable.")


def run():
    """Start the interactive chat loop.

    1. Refuse to start without Blizzard credentials (exit code 1, no traceback).
    2. Authenticate with Blizzard.
    3. Read user lines until they type quit.
    4. For each line, call the model, run any tools, then print a reply.
    """
    global history

    if not CLIENT_ID or not CLIENT_SECRET:
        print_missing_credentials_warning()
        sys.exit(1)

    _authenticate_blizzard()

    # --- Updated Welcome Message ---
    print("\n🤖 Hello! I'm your Loremaster's Companion. (Type 'quit' to exit)")
    print("You can now ask me about anything in Azeroth naturally!")
    print("Examples:")
    print("   • Tell me about the mount Invincible")
    print("   • What is the achievement Ahead of the Curve?")
    print("   • How do I get the toy Mr. Pinchy?")
    print("   • Tell me the story of the raid Karazhan")
    print("   • What does the spell Fireball do?")
    print("-" * 30)

    # --- Main Chat Loop ---
    while True:
        user_prompt = input("You: ")

        # Detect purely conversational messages that don't need a tool lookup
        is_conversational = is_conversational_prompt(user_prompt)

        # Check for quit before adding to history
        if user_prompt.lower() == "quit":
            print("Goodbye! 👋")
            break

        history.append({"role": "user", "content": user_prompt})
        history = trim_history(history)

        # First model call. tool_choice="none" forbids tools on greetings.
        # tool_choice="required" forces a tool on everything else so a small
        # local model cannot answer a named entity from training memory.
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ] + history

        chat_completion = client.chat.completions.create(
            messages=messages,
            model=MODEL_NAME,
            tools=TOOL_SCHEMAS,
            tool_choice="none" if is_conversational else "required"
        )

        response_message = chat_completion.choices[0].message

        tool_calls = parse_tool_calls(response_message)

        # If the model wants to call a tool
        #
        # Multi-tool protocol shape (must stay in this order):
        #   user message
        #   → one assistant message listing tool A and tool B
        #   → tool result A (tool_call_id matches A)
        #   → tool result B (tool_call_id matches B)
        #   → assistant final spoken response
        #
        # Older code appended one assistant message per tool. That broke the
        # Chat Completions tool protocol and is covered by P1 tests.
        if tool_calls:
            spinner = Spinner("Fetching lore from Azeroth...")
            spinner.start()
            try:
                assistant_tool_calls = []
                tool_results = []

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args, stored_arguments = _normalize_tool_arguments(tool_call.function.arguments)

                    call_id = tool_call.id if getattr(tool_call, "id", None) else f"call_{uuid.uuid4().hex}"
                    assistant_tool_calls.append({
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": function_name,
                            "arguments": stored_arguments
                        }
                    })

                    if function_args is None or not isinstance(function_args, dict):
                        tool_result = "Error parsing tool arguments."
                    else:
                        access_token = ensure_valid_token()
                        if function_name in TOOL_HANDLERS:
                            # Isolate handler crashes so one bad tool does not
                            # abort the rest of the turn.
                            try:
                                tool_result = TOOL_HANDLERS[function_name](function_args, access_token)
                            except Exception as e:
                                print(f"Error executing tool {function_name}: {e}")
                                tool_result = f"Error executing tool: {function_name}"
                        else:
                            tool_result = f"Unknown tool: {function_name}"

                    tool_results.append({
                        "role": "tool",
                        "content": tool_result,
                        "tool_call_id": call_id
                    })

                # Append one assistant history entry containing all tool calls
                history.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": assistant_tool_calls
                })
                # Append one tool-result entry per call
                for result_entry in tool_results:
                    history.append(result_entry)

                # Second model call: the model now sees official tool data and
                # must write the in-character answer from that data only.
                final_completion = client.chat.completions.create(
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
                    model=MODEL_NAME
                )
                response = final_completion.choices[0].message.content
            finally:
                spinner.stop()
        else:
            response = response_message.content

        # defensive guard in case final response is None/empty
        if not response:
            response = "(no response)"

        # Local models sometimes "think out loud" before the real answer
        # ("let me look that up..."). Those prefixes are replaced with a
        # canned in-character line so the user does not see the scratch work.
        REASONING_PREFIXES = (
            "let me", "first,", "i got", "i need to", "i should", "i'll try",
            "i will", "i'm going to", "to answer", "since the", "it seems i",
            "i got sidetracked"
        )
        if response and any(response.lower().startswith(prefix) for prefix in REASONING_PREFIXES):
            response = "I'm afraid the ancient scrolls are silent on that specific detail, friend. What other tale from Azeroth would you like to hear?"

        history.append({"role": "assistant", "content": response})
        history = trim_history(history)

        print(f"Loremaster: {response}")
        print("-" * 30)
