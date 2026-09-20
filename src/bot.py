# Main bot runtime: client setup, tool schema, chat loop, and tool-call orchestration.
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

CONVERSATIONAL_PHRASES = (
    "thanks", "thank you", "ok", "okay", "cool", "got it",
    "nice", "great", "awesome", "lol", "haha", "bye", "goodbye",
    "hello", "hi", "hey", "yes", "no", "sure", "sounds good",
    "that's helpful", "interesting", "wow"
)

# --- Ollama Client Setup ---
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

# Simple conversation memory - keeps the last 7 turns so the bot remembers context
history = []


class ToolCall:
    """Represents a tool call with id, function name, and arguments."""
    def __init__(self, id=None, name=None, arguments=None):
        self.id = id
        # Using SimpleNamespace for a simple object with dynamic attributes
        self.function = SimpleNamespace(name=name, arguments=arguments)


class Spinner:
    """
    A simple threaded spinner for showing loading progress.
    Displays a message with a spinning animation using standard library only.
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
    Parses tool calls from the response message.
    Handles both standard tool_calls from the API and fallback parsing from message content.
    Returns a list of ToolCall objects.
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
    Trims the conversation history to keep roughly the last max_turns full conversational turns.
    A turn is defined as: user message + any tool calls/results + final assistant response.
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
    """Detect purely conversational messages that don't need a tool lookup."""
    user_text = user_prompt.strip().lower().rstrip("!.,?")
    return user_text in CONVERSATIONAL_PHRASES


def _normalize_tool_arguments(raw_arguments):
    """
    Normalize tool-call arguments for execution and history storage.
    Returns (function_args_or_None, stored_arguments_string).
    History storage is always a JSON/text string.
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
    print("Authenticating with Blizzard...")
    token, expires_in = get_access_token()
    if token:
        blizzard_api.blizzard_token = token
        blizzard_api.token_expiry = time.time() + expires_in
        print("Authentication successful!")
    else:
        print("Could not authenticate with Blizzard. API lookups will be unavailable.")


def run():
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

        # --- NEW TOOL-AWARE LLM CALL ---
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

                # Final LLM call with tool results
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

        # Prevent model reasoning leakage (local Ollama models often think out loud)
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
