"""Regression tests for provider extra fields on structured tool calls.

Gemini 3 may attach extra_content.google.thought_signature to a function
call through Google's OpenAI-compatible API. History must send that
signature back unchanged. These tests never contact Gemini, Ollama, or
Blizzard.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)

import src.bot
from src.bot import ToolCall, parse_tool_calls, run


THOUGHT_SIGNATURE = "test-signature"
GEMINI_EXTRA_CONTENT = {
    "google": {
        "thought_signature": THOUGHT_SIGNATURE,
    }
}


@pytest.fixture(autouse=True)
def reset_state_and_block_network(monkeypatch):
    """Isolate each test and keep the chat loop off the network."""
    src.bot.history.clear()
    monkeypatch.setattr("src.bot.ensure_valid_token", lambda: "mock_token")
    monkeypatch.setattr("src.bot.get_access_token", lambda: ("mock_token", 3600))
    monkeypatch.setattr("src.api.blizzard.ensure_valid_token", lambda: "mock_token")
    monkeypatch.setattr("src.bot.Spinner", MagicMock(return_value=MagicMock()))
    yield
    src.bot.history.clear()


def _structured_gemini_tool_call(
    call_id,
    name="lookup_item",
    arguments='{"item_id": "19019"}',
    extra_content=None,
):
    """Build a real OpenAI SDK tool-call object with optional extra_content."""
    payload = {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }
    if extra_content is not None:
        payload["extra_content"] = extra_content
    return ChatCompletionMessageFunctionToolCall.model_validate(payload)


def _run_tool_turn(monkeypatch, tool_calls, prompt="Thunderfury"):
    """Drive one tool-using chat turn and return the mocked create()."""
    first_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=tool_calls))]
    )
    second_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Final companion response.", tool_calls=None))]
    )
    mock_create = MagicMock(side_effect=[first_resp, second_resp])
    monkeypatch.setattr(src.bot.client.chat.completions, "create", mock_create)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=[prompt, "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())
    monkeypatch.setitem(src.bot.TOOL_HANDLERS, "lookup_item", MagicMock(return_value="Thunderfury: 19019"))
    monkeypatch.setitem(src.bot.TOOL_HANDLERS, "search_creature", MagicMock(return_value="Creature: Ragnaros"))
    run()
    return mock_create


def test_gemini_thought_signature_preserved_in_history_and_final_request(monkeypatch):
    """A structured Gemini tool call must keep extra_content exactly as received."""
    call_id = "call_gemini_aaaaaaaaaaaaaaaaaaaaaaaa"
    tool_call = _structured_gemini_tool_call(
        call_id,
        extra_content=GEMINI_EXTRA_CONTENT,
    )

    mock_create = _run_tool_turn(monkeypatch, [tool_call])

    assistant_entry = next(h for h in src.bot.history if h.get("role") == "assistant" and "tool_calls" in h)
    stored = assistant_entry["tool_calls"][0]
    assert stored["extra_content"] == GEMINI_EXTRA_CONTENT
    assert stored["extra_content"]["google"]["thought_signature"] == THOUGHT_SIGNATURE
    assert stored["function"]["arguments"] == '{"item_id": "19019"}'
    assert isinstance(stored["function"]["arguments"], str)
    assert stored["id"] == call_id

    tool_entry = next(h for h in src.bot.history if h.get("role") == "tool")
    assert tool_entry["tool_call_id"] == call_id

    assert mock_create.call_count == 2
    final_messages = mock_create.call_args_list[1].kwargs["messages"]
    final_assistant = next(m for m in final_messages if m.get("role") == "assistant" and "tool_calls" in m)
    assert final_assistant["tool_calls"][0]["extra_content"] == GEMINI_EXTRA_CONTENT
    assert json.dumps(src.bot.history)


def test_gemini_thought_signature_still_normalizes_dict_arguments(monkeypatch):
    """Provider extra fields must not skip argument-string normalization."""
    call_id = "call_gemini_bbbbbbbbbbbbbbbbbbbbbbbb"
    tool_call = SimpleNamespace(
        id=call_id,
        type="function",
        extra_content=GEMINI_EXTRA_CONTENT,
        function=SimpleNamespace(name="lookup_item", arguments={"item_id": "19019"}),
    )

    _run_tool_turn(monkeypatch, [tool_call])

    assistant_entry = next(h for h in src.bot.history if h.get("role") == "assistant" and "tool_calls" in h)
    stored = assistant_entry["tool_calls"][0]
    assert stored["extra_content"]["google"]["thought_signature"] == THOUGHT_SIGNATURE
    assert stored["function"]["arguments"] == '{"item_id": "19019"}'
    assert isinstance(stored["function"]["arguments"], str)
    assert not isinstance(stored["function"]["arguments"], dict)


def test_multi_tool_preserves_per_call_extra_content(monkeypatch):
    """Each structured tool call keeps its own extra_content; order stays intact."""
    call_1 = _structured_gemini_tool_call(
        "call_001_aaa",
        name="search_creature",
        arguments='{"search_term": "Ragnaros"}',
        extra_content={"google": {"thought_signature": "sig-one"}},
    )
    call_2 = _structured_gemini_tool_call(
        "call_002_bbb",
        name="lookup_item",
        arguments='{"item_id": "19019"}',
        extra_content={"google": {"thought_signature": "sig-two"}},
    )

    mock_create = _run_tool_turn(monkeypatch, [call_1, call_2], prompt="Ragnaros and Thunderfury")

    assistant_entries = [h for h in src.bot.history if h.get("role") == "assistant" and "tool_calls" in h]
    assert len(assistant_entries) == 1
    stored_calls = assistant_entries[0]["tool_calls"]
    assert len(stored_calls) == 2
    assert stored_calls[0]["id"] == "call_001_aaa"
    assert stored_calls[0]["extra_content"]["google"]["thought_signature"] == "sig-one"
    assert stored_calls[1]["id"] == "call_002_bbb"
    assert stored_calls[1]["extra_content"]["google"]["thought_signature"] == "sig-two"

    tool_entries = [h for h in src.bot.history if h.get("role") == "tool"]
    assert [t["tool_call_id"] for t in tool_entries] == ["call_001_aaa", "call_002_bbb"]
    assert [h["role"] for h in src.bot.history] == ["user", "assistant", "tool", "tool", "assistant"]

    final_messages = mock_create.call_args_list[1].kwargs["messages"]
    final_assistant = next(m for m in final_messages if m.get("role") == "assistant" and "tool_calls" in m)
    assert final_assistant["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == "sig-one"
    assert final_assistant["tool_calls"][1]["extra_content"]["google"]["thought_signature"] == "sig-two"


def test_ollama_style_tool_call_without_extra_content_unchanged(monkeypatch):
    """Ordinary structured tool calls must not grow invented extra_content."""
    call_id = "call_ollama_cccccccccccccccccccccccc"
    tool_call = _structured_gemini_tool_call(call_id)

    _run_tool_turn(monkeypatch, [tool_call])

    assistant_entry = next(h for h in src.bot.history if h.get("role") == "assistant" and "tool_calls" in h)
    stored = assistant_entry["tool_calls"][0]
    assert stored == {
        "id": call_id,
        "type": "function",
        "function": {
            "name": "lookup_item",
            "arguments": '{"item_id": "19019"}',
        },
    }
    assert "extra_content" not in stored
    tool_entry = next(h for h in src.bot.history if h.get("role") == "tool")
    assert tool_entry["tool_call_id"] == call_id


def test_fallback_toolcall_does_not_invent_extra_content(monkeypatch):
    """Text-parsed ToolCall objects stay as the current minimal history dict."""
    call_id = "call_fallback_dddddddddddddddddddddddd"
    tool_call = ToolCall(id=call_id, name="lookup_item", arguments='{"item_id": "19019"}')

    _run_tool_turn(monkeypatch, [tool_call])

    assistant_entry = next(h for h in src.bot.history if h.get("role") == "assistant" and "tool_calls" in h)
    stored = assistant_entry["tool_calls"][0]
    assert stored == {
        "id": call_id,
        "type": "function",
        "function": {
            "name": "lookup_item",
            "arguments": '{"item_id": "19019"}',
        },
    }
    assert "extra_content" not in stored
    assert not hasattr(tool_call, "extra_content")


def test_fallback_parse_tool_calls_still_builds_minimal_toolcall():
    """parse_tool_calls fallback path is unchanged and does not add extra_content."""
    raw_json = '[{"name": "lookup_item", "arguments": {"item_id": "19019"}}]'
    response_message = SimpleNamespace(tool_calls=[], content=raw_json)

    tool_calls = parse_tool_calls(response_message)

    assert len(tool_calls) == 1
    tc = tool_calls[0]
    assert isinstance(tc, ToolCall)
    assert json.loads(tc.function.arguments) == {"item_id": "19019"}
    assert not hasattr(tc, "extra_content")
    assert response_message.content == ""


def test_generated_call_id_still_keeps_thought_signature(monkeypatch):
    """A missing tool-call id is generated without dropping extra_content."""
    tool_call = SimpleNamespace(
        id=None,
        type="function",
        extra_content=GEMINI_EXTRA_CONTENT,
        function=SimpleNamespace(name="lookup_item", arguments='{"item_id": "19019"}'),
    )

    _run_tool_turn(monkeypatch, [tool_call])

    assistant_entry = next(h for h in src.bot.history if h.get("role") == "assistant" and "tool_calls" in h)
    stored = assistant_entry["tool_calls"][0]
    assert stored["id"].startswith("call_")
    assert stored["extra_content"]["google"]["thought_signature"] == THOUGHT_SIGNATURE
    tool_entry = next(h for h in src.bot.history if h.get("role") == "tool")
    assert tool_entry["tool_call_id"] == stored["id"]
