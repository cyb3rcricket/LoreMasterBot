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
from openai import DefaultHttpxClient, OpenAI
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
    LLM_MODEL,
    LLM_REQUEST_TIMEOUT,
    CLIENT_ID,
    CLIENT_SECRET,
    print_missing_credentials_warning,
    validate_llm_provider,
    llm_provider_label,
)
from src import config as app_config
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

# Cap on distinct tool calls executed in a single user turn.
MAX_TOOL_CALLS_PER_TURN = 5


def create_llm_client():
    """Build the one OpenAI client used by the chat loop.

    A provider is the service that runs the language model (Ollama, Gemini,
    or a custom host). Many of those services accept the same Chat Completions
    request format, so this helper only changes the URL and API key. The chat
    loop below stays the same for every provider.

    API keys stay in environment variables (loaded by src.config) so they are
    not written into source files. A dummy key is used only when a required
    key is missing, because the OpenAI constructor refuses an empty string.
    Startup validation still exits before chat if the active provider is
    incomplete.

    Environment proxies (HTTP_PROXY / HTTPS_PROXY) are disabled on the model
    HTTP client so local Ollama chats and custom HTTP bearer keys are never
    forwarded to an untrusted proxy host.
    """
    http_client = DefaultHttpxClient(trust_env=False, timeout=LLM_REQUEST_TIMEOUT)
    if app_config.LLM_PROVIDER == "gemini":
        return OpenAI(
            base_url=app_config.GEMINI_OPENAI_BASE_URL,
            api_key=app_config.GEMINI_API_KEY or "missing",
            timeout=LLM_REQUEST_TIMEOUT,
            http_client=http_client,
        )
    if app_config.LLM_PROVIDER == "custom":
        return OpenAI(
            base_url=app_config.LLM_BASE_URL or app_config.DEFAULT_OLLAMA_BASE_URL,
            api_key=app_config.LLM_API_KEY or "missing",
            timeout=LLM_REQUEST_TIMEOUT,
            http_client=http_client,
        )
    return OpenAI(
        base_url=app_config.LLM_BASE_URL or app_config.DEFAULT_OLLAMA_BASE_URL,
        api_key=app_config.OLLAMA_API_KEY,
        timeout=LLM_REQUEST_TIMEOUT,
        http_client=http_client,
    )


# Built at import so existing tests can patch client.chat.completions.create.
# Import does not contact Ollama, Gemini, or Blizzard.
client = create_llm_client()

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
    instead of filling tool_calls. This function scrapes those arrays using
    JSONDecoder (supporting multi-line formatting and brackets inside strings)
    and builds ToolCall objects. Each fallback call gets a generated
    `call_<32 hex digits>` id because later history messages must link a
    result to a request. Without an id, the next model call can fail.

    Returns a list of ToolCall-like objects.
    Modifies response_message.content in place if tool calls are parsed from content.
    """
    if response_message is None:
        return []
    raw_tool_calls = getattr(response_message, "tool_calls", None)
    tool_calls = list(raw_tool_calls) if isinstance(raw_tool_calls, (list, tuple)) and raw_tool_calls else []
    content = getattr(response_message, "content", None)
    if not tool_calls and isinstance(content, str) and content:
        decoder = json.JSONDecoder()
        spans_to_remove = []
        idx = 0
        while True:
            start = content.find("[", idx)
            if start == -1:
                break
            try:
                parsed, end = decoder.raw_decode(content, start)
            except Exception:
                idx = start + 1
                continue
            matched_calls = []
            if isinstance(parsed, list) and parsed:
                for item in parsed:
                    if isinstance(item, dict) and "name" in item and "arguments" in item:
                        matched_calls.append(
                            ToolCall(
                                id=f"call_{uuid.uuid4().hex}",
                                name=item["name"],
                                arguments=json.dumps(item["arguments"]),
                            )
                        )
            if matched_calls:
                tool_calls.extend(matched_calls)
                spans_to_remove.append((start, end))
                idx = end
            else:
                idx = start + 1

        if spans_to_remove:
            parts = []
            cursor = 0
            for start, end in spans_to_remove:
                parts.append(content[cursor:start])
                cursor = end
            parts.append(content[cursor:])
            response_message.content = "".join(parts).strip()
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
                content = history[j].get('content')
                if isinstance(content, str):
                    content = content.strip()
                if history[j]['role'] == 'assistant' and content:
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


def _structured_tool_call_extras(tool_call):
    """Copy extra fields from a real provider tool call.

    Some OpenAI-compatible APIs attach extra data to a tool call besides
    id, type, and function. Gemini 3, for example, may send
    extra_content.google.thought_signature. That signature must be sent
    back unchanged with the assistant tool call, or the next request can
    fail.

    Fallback ToolCall objects are built by LoreMasterBot's text parser.
    They are not provider objects, so they get no invented extra fields.
    """
    if isinstance(tool_call, ToolCall):
        return {}

    payload = None
    dump = getattr(tool_call, "model_dump", None)
    if callable(dump):
        try:
            payload = dump(mode="json")
        except TypeError:
            payload = dump()
    elif isinstance(tool_call, dict):
        payload = dict(tool_call)
    else:
        extra_content = getattr(tool_call, "extra_content", None)
        if extra_content is not None:
            payload = {"extra_content": extra_content}

    if not isinstance(payload, dict):
        return {}

    extras = {}
    for key, value in payload.items():
        if key in ("id", "type", "function") or value is None:
            continue
        extras[key] = value
    return extras


def _history_tool_call_entry(tool_call, call_id, function_name, stored_arguments):
    """Build the assistant-history dict for one tool request.

    Normalized fields always win:
    - id is the real call id, or a generated call_<hex> id
    - type stays "function" unless the provider already set one
    - function.arguments is always a string

    Any other provider fields (such as extra_content) are copied through
    so the follow-up model request sees them.
    """
    entry = {
        "id": call_id,
        "type": getattr(tool_call, "type", None) or "function",
        "function": {
            "name": function_name,
            "arguments": stored_arguments,
        },
    }
    extras = _structured_tool_call_extras(tool_call)
    if not extras:
        return entry
    return {**extras, **entry}


def _authenticate_blizzard():
    """Ask Blizzard for an access token when the chat loop actually starts.

    An access token is a short-lived password for API calls. This is not run
    at import time, so `import src.bot` does not hit the network.
    """
    print("Authenticating with Blizzard...")
    token, expires_in = get_access_token()
    if (
        isinstance(token, str)
        and token.strip()
        and not isinstance(expires_in, bool)
        and isinstance(expires_in, (int, float))
        and expires_in > 0
    ):
        blizzard_api.blizzard_token = token
        blizzard_api.token_expiry = time.time() + expires_in
        print("Authentication successful!")
    else:
        blizzard_api.blizzard_token = None
        blizzard_api.token_expiry = 0
        print("Could not authenticate with Blizzard. API lookups will be unavailable.")


def _extract_completion_message(completion):
    """Return choices[0].message from a completion, or None if missing/empty."""
    choices = getattr(completion, "choices", None)
    if not isinstance(choices, (list, tuple)) or not choices:
        return None
    return getattr(choices[0], "message", None)


def _message_text(message):
    """Return string content from a completion message, or None."""
    if message is None:
        return None
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    return None


_SCRATCH_CLAUSE_RE = re.compile(
    r"^(?:let me\s+(?:look|check|search|find|see|call|use|query|consult)|first,\s*i|i got sidetracked|i got\b|i need to\b|i should\b|i'll try\b|i'm going to\b|to answer\b|it seems i\b)[^.!?\n]*[.!?]?\s*",
    re.IGNORECASE,
)


def _clean_reasoning_prefix(response, *, is_conversational, used_tools):
    """Strip a leading meta-reasoning scratch clause when no tool was called.

    Conversational greetings ("Let me welcome you...", "Since the fire is warm...")
    and grounded answers generated after tool calls ("I will share only the official
    record...") are kept intact. If a non-conversational turn with no tool calls
    consists solely of a scratchpad thought, return the in-character fallback.
    """
    if not response or not isinstance(response, str):
        return response
    if is_conversational or used_tools:
        return response
    match = _SCRATCH_CLAUSE_RE.match(response.strip())
    if not match:
        return response
    remainder = response.strip()[match.end():].strip()
    if remainder:
        return remainder
    return "I'm afraid the ancient scrolls are silent on that specific detail, friend. What other tale from Azeroth would you like to hear?"


def _select_turn_tool_calls(tool_calls):
    """Deduplicate identical valid tool calls and cap the count per turn."""
    selected = []
    seen_signatures = set()
    for tc in tool_calls:
        fn = getattr(tc, "function", None)
        raw_name = getattr(fn, "name", None) if fn is not None else None
        raw_args = getattr(fn, "arguments", None) if fn is not None else None
        norm_name = raw_name if isinstance(raw_name, str) else str(raw_name)
        parsed_args, norm_stored_args = _normalize_tool_arguments(raw_args)
        if fn is not None and isinstance(raw_name, str) and isinstance(parsed_args, dict):
            sig = (norm_name, norm_stored_args)
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)
        selected.append(tc)
        if len(selected) >= MAX_TOOL_CALLS_PER_TURN:
            break
    return selected


def run():
    """Start the interactive chat loop.

    1. Validate the selected LLM provider (exit code 1, no traceback).
    2. Refuse to start without Blizzard credentials (exit code 1, no traceback).
    3. Authenticate with Blizzard.
    4. Read user lines until they type quit.
    5. For each line, call the model, run any tools, then print a reply.
    """
    global history

    validate_llm_provider()

    if not CLIENT_ID or not CLIENT_SECRET:
        print_missing_credentials_warning()
        sys.exit(1)

    _authenticate_blizzard()

    # --- Updated Welcome Message ---
    print("\n🤖 Hello! I'm your Loremaster's Companion. (Type 'quit' to exit)")
    print(f"AI provider: {llm_provider_label()} / {LLM_MODEL}")
    print("You can now ask me about anything in Azeroth naturally!")
    print("Examples:")
    print("   • Tell me about the mount Invincible")
    print("   • What is the achievement Ahead of the Curve?")
    print("   • Tell me about the Human race")
    print("   • Who is Professor Putricide?")
    print("   • Tell me the story of the raid Karazhan")
    print("   • What does the spell Fireball do?")
    print("-" * 30)

    # --- Main Chat Loop ---
    while True:
        try:
            user_prompt = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! 👋")
            break

        # Detect purely conversational messages that don't need a tool lookup
        is_conversational = is_conversational_prompt(user_prompt)

        # Check for quit before adding to history
        if user_prompt.strip().lower() == "quit":
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

        first_spinner = Spinner("Consulting the ancient scrolls...")
        first_spinner.start()
        try:
            chat_completion = client.chat.completions.create(
                messages=messages,
                model=LLM_MODEL,
                tools=TOOL_SCHEMAS,
                tool_choice="none" if is_conversational else "required",
                timeout=LLM_REQUEST_TIMEOUT,
            )
        except (EOFError, KeyboardInterrupt):
            first_spinner.stop()
            print("\nGoodbye! 👋")
            break
        except Exception as e:
            first_spinner.stop()
            print(f"Error communicating with AI provider: {e}")
            response = "(no response)"
            history.append({"role": "assistant", "content": response})
            history = trim_history(history)
            print(f"Loremaster: {response}")
            print("-" * 30)
            continue
        finally:
            first_spinner.stop()

        response_message = _extract_completion_message(chat_completion)
        tool_calls = _select_turn_tool_calls(parse_tool_calls(response_message))

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
                    fn = getattr(tool_call, "function", None)
                    raw_name = getattr(fn, "name", None) if fn is not None else None
                    raw_arguments = getattr(fn, "arguments", None) if fn is not None else None
                    function_name = raw_name if isinstance(raw_name, str) else str(raw_name)
                    function_args, stored_arguments = _normalize_tool_arguments(raw_arguments)

                    call_id = tool_call.id if getattr(tool_call, "id", None) else f"call_{uuid.uuid4().hex}"
                    assistant_tool_calls.append(
                        _history_tool_call_entry(
                            tool_call,
                            call_id,
                            function_name,
                            stored_arguments,
                        )
                    )

                    if fn is None or function_args is None or not isinstance(function_args, dict):
                        tool_result = "Error parsing tool arguments."
                    elif isinstance(raw_name, str) and raw_name in TOOL_HANDLERS:
                        access_token = ensure_valid_token()
                        # Isolate handler crashes so one bad tool does not
                        # abort the rest of the turn.
                        try:
                            tool_result = TOOL_HANDLERS[raw_name](function_args, access_token)
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
                try:
                    final_completion = client.chat.completions.create(
                        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
                        model=LLM_MODEL,
                        timeout=LLM_REQUEST_TIMEOUT,
                    )
                    final_message = _extract_completion_message(final_completion)
                    response = _message_text(final_message)
                    if (not response or not response.strip()) and parse_tool_calls(final_message):
                        response = (
                            "I could not finish consulting the official records in a single pass, friend. "
                            "Try asking about one specific detail at a time."
                        )
                except (EOFError, KeyboardInterrupt):
                    print("\nGoodbye! 👋")
                    break
                except Exception as e:
                    print(f"Error communicating with AI provider: {e}")
                    response = "(no response)"
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye! 👋")
                break
            finally:
                spinner.stop()
        else:
            response = _message_text(response_message)

        # defensive guard in case final response is None, non-string, or whitespace-only
        if not response or not isinstance(response, str) or not response.strip():
            response = "(no response)"

        response = _clean_reasoning_prefix(
            response,
            is_conversational=is_conversational,
            used_tools=bool(tool_calls),
        )

        history.append({"role": "assistant", "content": response})
        history = trim_history(history)

        print(f"Loremaster: {response}")
        print("-" * 30)

