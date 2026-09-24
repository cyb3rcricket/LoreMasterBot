"""P0 regression tests: bugs that already broke the chat loop.

A regression test proves an old failure cannot silently return. These
tests do not talk to Ollama or Blizzard. monkeypatch temporarily replaces
a function for one test. MagicMock is a fake object that records calls
and can return canned values.

This file covers:
1. Short WoW names are not treated as casual conversation.
2. Fallback tool calls receive valid IDs.
3. Tool-call history is JSON-serializable and correctly linked.
4. Malformed tool arguments do not crash the turn.
5. Missing Blizzard credentials fail cleanly when the app starts.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import src.bot
from src.bot import ToolCall, is_conversational_prompt, parse_tool_calls, run


@pytest.fixture(autouse=True)
def reset_state_and_mock_environment(monkeypatch):
    """Run around every test: clear history and block real network calls.

    autouse=True means pytest applies this fixture without each test
    asking for it. yield returns control to the test, then cleanup runs.
    """
    src.bot.history.clear()
    monkeypatch.setattr("src.bot.ensure_valid_token", lambda: "mock_token")
    monkeypatch.setattr("src.bot.get_access_token", lambda: ("mock_token", 3600))
    monkeypatch.setattr("src.api.blizzard.ensure_valid_token", lambda: "mock_token")

    # Mock Spinner to prevent threaded stdout animation during test runs
    mock_spinner_instance = MagicMock()
    monkeypatch.setattr("src.bot.Spinner", MagicMock(return_value=mock_spinner_instance))
    yield
    src.bot.history.clear()


# ============================================================================
# 1. Short WoW prompts are not treated as casual conversation
# ============================================================================
# A past bug classified "Invincible" as chit-chat (tool_choice="none"), so
# the model invented mount lore. The allowlist must stay exact-match only.

SHORT_WOW_PROMPTS = ["Invincible", "Thunderfury", "Mr. Pinchy", "Karazhan"]
CONVERSATIONAL_PHRASES = ["hi", "thank you", "thanks", "hello", "hey", "cool", "ok", "okay"]


@pytest.mark.parametrize("prompt", SHORT_WOW_PROMPTS)
def test_short_wow_prompts_classified_as_not_conversational(prompt):
    """Short WoW queries (<= 2 words) must not be treated as casual conversation."""
    assert is_conversational_prompt(prompt) is False
    # Punctuation/casing variations should also remain non-conversational
    assert is_conversational_prompt(f"{prompt}!") is False
    assert is_conversational_prompt(prompt.lower()) is False


@pytest.mark.parametrize("phrase", CONVERSATIONAL_PHRASES)
def test_conversational_phrases_classified_as_conversational(phrase):
    """Known conversational phrases must continue to be treated as conversational."""
    assert is_conversational_prompt(phrase) is True
    assert is_conversational_prompt(f"{phrase}!") is True
    assert is_conversational_prompt(f"  {phrase.upper()}? ") is True


def test_chat_loop_tool_choice_required_for_short_wow_prompts(monkeypatch):
    """In the chat loop, short WoW prompts must set tool_choice='required'."""
    mock_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Ancient lore response.", tool_calls=None))]
    )
    mock_create = MagicMock(return_value=mock_response)
    monkeypatch.setattr(src.bot.client.chat.completions, "create", mock_create)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["Invincible", "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())

    run()

    assert mock_create.called
    first_call_kwargs = mock_create.call_args_list[0].kwargs
    assert first_call_kwargs.get("tool_choice") == "required"


def test_chat_loop_tool_choice_none_for_conversational_phrases(monkeypatch):
    """In the chat loop, casual conversation must set tool_choice='none'."""
    mock_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Greetings, traveler!", tool_calls=None))]
    )
    mock_create = MagicMock(return_value=mock_response)
    monkeypatch.setattr(src.bot.client.chat.completions, "create", mock_create)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["hi", "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())

    run()

    assert mock_create.called
    first_call_kwargs = mock_create.call_args_list[0].kwargs
    assert first_call_kwargs.get("tool_choice") == "none"


# ============================================================================
# 2. Fallback tool calls receive valid IDs
# ============================================================================
# Local models sometimes write tool JSON into message text. Those fake
# calls still need call_<hex> ids so history can link results later.

def test_fallback_tool_calls_receive_valid_uuid_ids():
    """Fallback JSON tool call in content must receive a valid call_<32 hex> id."""
    raw_json = '[{"name": "lookup_item", "arguments": {"item_name": "Thunderfury"}}]'
    response_message = SimpleNamespace(tool_calls=[], content=raw_json)

    tool_calls = parse_tool_calls(response_message)

    assert len(tool_calls) == 1
    tc = tool_calls[0]
    assert isinstance(tc, ToolCall)
    assert tc.id is not None
    assert re.match(r"^call_[0-9a-f]{32}$", tc.id), f"Tool call ID '{tc.id}' did not match expected regex"
    assert tc.function.name == "lookup_item"
    assert json.loads(tc.function.arguments) == {"item_name": "Thunderfury"}
    # The JSON string must be stripped from content
    assert response_message.content == ""


def test_fallback_tool_calls_strips_json_with_preceding_text():
    """Preceding text is preserved while the trailing tool call JSON is stripped."""
    content = 'Consulting the library: [{"name": "lookup_item", "arguments": {"item_name": "Thunderfury"}}]'
    response_message = SimpleNamespace(tool_calls=None, content=content)

    tool_calls = parse_tool_calls(response_message)

    assert len(tool_calls) == 1
    tc = tool_calls[0]
    assert re.match(r"^call_[0-9a-f]{32}$", tc.id)
    assert response_message.content == "Consulting the library:"


def test_standard_tool_calls_not_overwritten_by_fallback():
    """Existing tool_calls list is preserved and content fallback is not triggered."""
    existing_tc = ToolCall(id="call_existing_123", name="lookup_item", arguments='{"item_name": "Ashbringer"}')
    response_message = SimpleNamespace(
        tool_calls=[existing_tc],
        content='[{"name": "lookup_item", "arguments": {"item_name": "Ignored"}}]'
    )

    tool_calls = parse_tool_calls(response_message)

    assert tool_calls == [existing_tc]
    assert tool_calls[0].id == "call_existing_123"
    # Content is left untouched when standard tool_calls are present
    assert response_message.content == '[{"name": "lookup_item", "arguments": {"item_name": "Ignored"}}]'


def test_blank_assistant_reply_does_not_split_chat_session():
    """A whitespace-only reply must not end a turn and orphan the tool result."""
    history = [
        {"role": "user", "content": "older question"},
        {"role": "assistant", "content": "older answer"},
        {"role": "user", "content": "Thunderfury"},
        {"role": "assistant", "content": "   "},
        {"role": "tool", "tool_call_id": "call_session", "content": "Item data"},
        {"role": "assistant", "content": "The records name Thunderfury."},
    ]

    trimmed = src.bot.trim_history(history, max_turns=1)

    assert trimmed[0]["content"] == "Thunderfury"
    assert trimmed[-2]["role"] == "tool"
    assert trimmed[-1]["content"] == "The records name Thunderfury."


# ============================================================================
# 3. Tool-call history is serializable and correctly linked
# ============================================================================
# JSON serialization means converting history to a text format the next
# request can send. If history contains a ToolCall object instead of a
# dict, json.dumps raises and the turn dies. tool_call_id must equal the
# request id so the model can pair each result with the right call.

def test_tool_call_history_serializable_and_correctly_linked(monkeypatch):
    """History appending must store plain dicts with matching tool_call_id and serialize cleanly."""
    call_id = "call_a1b2c3d4e5f60718293a4b5c6d7e8f90"
    tool_call = ToolCall(id=call_id, name="lookup_item", arguments='{"item_name": "Thunderfury"}')

    llm_tool_choice_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[tool_call]))]
    )
    llm_final_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Thunderfury is a legendary blade.", tool_calls=None))]
    )

    mock_create = MagicMock(side_effect=[llm_tool_choice_resp, llm_final_resp])
    mock_handler = MagicMock(return_value="Thunderfury: Item ID 19019")

    monkeypatch.setattr(src.bot.client.chat.completions, "create", mock_create)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["Thunderfury", "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())
    monkeypatch.setitem(src.bot.TOOL_HANDLERS, "lookup_item", mock_handler)

    run()

    # Verify assistant history entry with tool_calls
    assistant_entry = next(h for h in src.bot.history if h.get("role") == "assistant" and "tool_calls" in h)
    assert isinstance(assistant_entry, dict)
    assert assistant_entry["content"] is None
    assert len(assistant_entry["tool_calls"]) == 1

    tool_call_dict = assistant_entry["tool_calls"][0]
    assert isinstance(tool_call_dict, dict), "tool_calls element must be a dict, not a ToolCall object"
    assert not isinstance(tool_call_dict, ToolCall)
    assert tool_call_dict["id"] == call_id
    assert tool_call_dict["type"] == "function"
    assert tool_call_dict["function"] == {
        "name": "lookup_item",
        "arguments": '{"item_name": "Thunderfury"}'
    }

    # Verify tool result history entry
    tool_entry = next(h for h in src.bot.history if h.get("role") == "tool")
    assert isinstance(tool_entry, dict)
    assert tool_entry["content"] == "Thunderfury: Item ID 19019"
    assert tool_entry["tool_call_id"] == call_id
    assert tool_entry["tool_call_id"] == tool_call_dict["id"], "tool_call_id must link directly to tool_calls id"

    # Entire history must serialize cleanly to JSON
    serialized = json.dumps(src.bot.history)
    deserialized = json.loads(serialized)
    assert isinstance(deserialized, list)
    assert len(deserialized) == len(src.bot.history)


# ============================================================================
# 4. Malformed tool arguments do not crash the turn
# ============================================================================
# Models send arguments as a JSON string, a dict, broken text, or None.
# Every case must keep history as strings and still finish the turn.

@pytest.mark.parametrize(
    "raw_args,is_valid,expected_handler_arg,expected_tool_result,expected_stored_args",
    [
        ('{"item_name": "Thunderfury"}', True, {"item_name": "Thunderfury"}, "Thunderfury: 19019", '{"item_name": "Thunderfury"}'),
        ({"item_name": "Thunderfury"}, True, {"item_name": "Thunderfury"}, "Thunderfury: 19019", '{"item_name": "Thunderfury"}'),
        ("{invalid json", False, None, "Error parsing tool arguments.", "{invalid json"),
        (None, False, None, "Error parsing tool arguments.", "null"),
    ],
    ids=["valid_json_string", "dict_argument", "malformed_json_string", "none_argument"]
)
def test_tool_argument_variants_handling(raw_args, is_valid, expected_handler_arg, expected_tool_result, expected_stored_args, monkeypatch):
    """Valid, dict, malformed, and None tool arguments must not crash the turn and preserve history linkage."""
    call_id = "call_arg_test_1234567890abcdef1234"
    tool_call = ToolCall(id=call_id, name="lookup_item", arguments=raw_args)

    first_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[tool_call]))]
    )
    second_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Final companion response.", tool_calls=None))]
    )

    mock_create = MagicMock(side_effect=[first_resp, second_resp])
    mock_handler = MagicMock(return_value="Thunderfury: 19019")

    monkeypatch.setattr(src.bot.client.chat.completions, "create", mock_create)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["Thunderfury", "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())
    monkeypatch.setitem(src.bot.TOOL_HANDLERS, "lookup_item", mock_handler)

    # Should not raise any uncaught exceptions
    run()

    if is_valid:
        assert mock_handler.called
        assert mock_handler.call_args[0][0] == expected_handler_arg
    else:
        assert not mock_handler.called

    # Check tool result entry in history
    tool_entry = next(h for h in src.bot.history if h.get("role") == "tool")
    assert tool_entry["content"] == expected_tool_result
    assert tool_entry["tool_call_id"] == call_id

    # Check assistant tool_calls entry
    assistant_entry = next(h for h in src.bot.history if h.get("role") == "assistant" and "tool_calls" in h)
    assert assistant_entry["tool_calls"][0]["id"] == call_id
    stored_arguments = assistant_entry["tool_calls"][0]["function"]["arguments"]
    assert stored_arguments == expected_stored_args
    assert isinstance(stored_arguments, str)
    assert not isinstance(stored_arguments, (dict, type(None))), "no raw non-string value may be stored"
    if isinstance(raw_args, dict):
        assert not isinstance(stored_arguments, dict)

    # History must remain JSON-serializable
    assert json.dumps(src.bot.history) is not None


# ============================================================================
# 5. Missing Blizzard credentials fail cleanly
# ============================================================================
# Startup checks run in a subprocess (a brand-new Python process) so they
# cannot see this test process's dummy keys. import src.bot must not exit.
# python main.py / run() with empty keys must exit 1 and print the warning.

def _run_main_without_credentials(env, cwd=None):
    return subprocess.run(
        [sys.executable, os.path.join(os.getcwd(), "main.py")],
        env=env,
        cwd=cwd or os.getcwd(),
        capture_output=True,
        text=True,
    )


def test_importing_bot_does_not_exit_or_authenticate_when_credentials_missing():
    """Importing src.bot must not exit or call Blizzard, even with empty credentials."""
    env = {**os.environ, "BLIZZARD_CLIENT_ID": "", "BLIZZARD_CLIENT_SECRET": ""}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import src.api.blizzard as blizzard;"
                "blizzard.get_access_token = lambda: (_ for _ in ()).throw(RuntimeError('network'));"
                "import src.bot"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Traceback" not in result.stderr


def test_missing_credentials_empty_env_exits_cleanly():
    """Empty credentials must trigger a clean startup exit (code 1) with warning and no traceback."""
    env = {**os.environ, "BLIZZARD_CLIENT_ID": "", "BLIZZARD_CLIENT_SECRET": ""}
    result = _run_main_without_credentials(env)

    assert result.returncode == 1
    assert "WARNING: Missing BLIZZARD_CLIENT_ID or BLIZZARD_CLIENT_SECRET" in result.stdout
    assert "MissingCredentialsError" not in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_credentials_absent_env_exits_cleanly():
    """Absent credentials (no .env file, unset env) must exit with code 1 and no traceback."""
    with tempfile.TemporaryDirectory() as temp_dir:
        clean_env = {k: v for k, v in os.environ.items() if "BLIZZARD" not in k}
        clean_env["PYTHONPATH"] = os.getcwd()

        # Use -c so dotenv cannot discover the project's .env via main.py's path.
        result = subprocess.run(
            [sys.executable, "-c", "from src.bot import run; run()"],
            env=clean_env,
            cwd=temp_dir,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "WARNING: Missing BLIZZARD_CLIENT_ID or BLIZZARD_CLIENT_SECRET" in result.stdout
        assert "MissingCredentialsError" not in result.stderr
        assert "Traceback" not in result.stderr
