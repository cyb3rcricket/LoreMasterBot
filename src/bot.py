# Main bot runtime: client setup, tool schema, chat loop, and tool-call orchestration.
from openai import OpenAI
import json
import re
import time
import threading
import itertools
import sys
from types import SimpleNamespace

from src.api import blizzard as blizzard_api
from src.api.blizzard import ensure_valid_token, get_access_token
from src.config import MissingCredentialsError
from src.tools.handlers import TOOL_HANDLERS
from src.tools.schemas import TOOL_SCHEMAS

try:
    from src.config import SYSTEM_PROMPT, MODEL_NAME
except MissingCredentialsError:
    import sys
    sys.exit(1)


# --- Get Blizzard access token once when the script starts ---
print("Authenticating with Blizzard...")
token, expires_in = get_access_token()
if token:
    blizzard_api.blizzard_token = token
    blizzard_api.token_expiry = time.time() + expires_in
    print("Authentication successful!")
else:
    print("Could not authenticate with Blizzard. API lookups will be unavailable.")

# --- Ollama Client Setup ---
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

# Simple conversation memory - keeps the last 8 turns so the bot remembers context
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
                            tool_calls.append(ToolCall(name=item["name"], arguments=json.dumps(item["arguments"])))
                            break  # Stop after finding the first valid tool call in this match
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


def run():
    global history

    # --- Updated Welcome Message ---
    print("\n🤖 Hello! I'm your Loremaster's Companion. (Type 'quit' to exit)")
    print("You can now ask me about anything in Azeroth naturally!")
    print("Examples:")
    print("   • Tell me about the mount Invincible")
    print("   • What is the achievement Ahead of the Curve?")
    print("   • How do I get the toy Mr. Pinchy?")
    print("   • Tell me the story of the raid Karazhan")
    print("   • What does the spell Thunderfury do?")
    print("-" * 30)

    # --- Main Chat Loop ---
    while True:
        user_prompt = input("You: ")

        # Detect purely conversational messages that don't need a tool lookup
        user_text = user_prompt.strip().lower().rstrip("!.,?")
        is_conversational = user_text in CONVERSATIONAL_PHRASES or len(user_text.split()) <= 2

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
            tool_choice="none" if is_conversational else "auto"
        )

        response_message = chat_completion.choices[0].message

        tool_calls = parse_tool_calls(response_message)

        # If the model wants to call a tool
        if tool_calls:
            spinner = Spinner("Fetching lore from Azeroth...")
            spinner.start()

            for tool_call in tool_calls:
                function_name = tool_call.function.name
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_result = "Error parsing tool arguments."
                    continue

                access_token = ensure_valid_token()
                if function_name in TOOL_HANDLERS:
                    tool_result = TOOL_HANDLERS[function_name](function_args, access_token)
                else:
                    tool_result = f"Unknown tool: {function_name}"

                # Add the tool result back to history and get final response
                history.append({"role": "assistant", "content": None, "tool_calls": [tool_call]})
                history.append({"role": "tool", "content": tool_result, "tool_call_id": tool_call.id})

            # Final LLM call with tool results
            final_completion = client.chat.completions.create(
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
                model=MODEL_NAME
            )
            response = final_completion.choices[0].message.content

            spinner.stop()
        else:
            response = response_message.content

        # defensive guard in case final response is None/empty
        if not response:
            response = "(no response)"
        history.append({"role": "assistant", "content": response})
        history = trim_history(history)

        # Prevent model reasoning leakage (local Ollama models often think out loud)
        REASONING_PREFIXES = (
            "let me", "first,", "i got", "i need to", "i should", "i'll try",
            "i will", "i'm going to", "to answer", "since the", "it seems i",
            "i got sidetracked"
        )
        if response and any(response.lower().startswith(prefix) for prefix in REASONING_PREFIXES):
            response = "I'm afraid the ancient scrolls are silent on that specific detail, friend. What other tale from Azeroth would you like to hear?"

        print(f"Loremaster: {response}")
        print("-" * 30)