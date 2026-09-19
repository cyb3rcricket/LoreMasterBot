"""Regression tests for LoreMasterBot P1 reliability hardening.

Covers:
1. Blizzard API Request Timeouts:
   - Shared timeout constant BLIZZARD_API_TIMEOUT used in all requests.get and requests.post.
   - Timeout during OAuth token fetch retries up to 3 times and returns (None, None).
   - Timeout during search and entity fetches fails safely returning None.

2. WoW Token Price Cache TTL:
   - WOW_TOKEN_CACHE_TTL_SECONDS constant defined.
   - Cache hit before TTL expires (no redundant network calls).
   - Fresh fetch after TTL expires (network call made).
   - Safe error handling on network error after TTL expires.

3. Case-Insensitive Famous Item Fallback:
   - Case-insensitive resolution for "Thunderfury", "thunderfury", "THUNDERFURY".
   - Case-insensitive resolution for all entries in famous_items fallback map without network requests.

4. Item Tool Contract / Schema Mismatch:
   - Ambiguity eliminated between lookup_item and search_item_by_name.
   - Schemas enforce item_id for lookup_item and search_term for search_item_by_name.
   - SYSTEM_PROMPT clearly differentiates name searches from ID lookups.
   - Handlers adhere to their respective parameter contracts.

5. Multiple Tool Call History:
   - Two valid tool calls in one assistant response produce one assistant history entry followed by tool results.
   - Correct execution and history ordering.
   - Matching tool_call_ids between tool_calls and tool results.
   - One malformed call alongside one valid call produces safe error without aborting turn.
   - Full history remains cleanly JSON-serializable.
   - Single-tool-call behavior preserved.
"""

import inspect
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

import src.api.blizzard as blizzard
import src.bot as bot
from src.bot import ToolCall, run
from src.config import SYSTEM_PROMPT
from src.tools.handlers import handle_lookup_item, handle_search_item_by_name
from src.tools.schemas import TOOL_SCHEMAS


@pytest.fixture(autouse=True)
def reset_test_state(monkeypatch):
    """Isolate tests, reset caches, token state, and history."""
    bot.history.clear()
    blizzard.search_cache.clear()
    blizzard.data_cache.clear()
    blizzard.wow_token_cache["data"] = None
    blizzard.wow_token_cache["timestamp"] = 0.0
    monkeypatch.setattr("src.bot.ensure_valid_token", lambda: "mock_token")
    monkeypatch.setattr("src.api.blizzard.ensure_valid_token", lambda: "mock_token")
    mock_spinner = MagicMock()
    monkeypatch.setattr("src.bot.Spinner", MagicMock(return_value=mock_spinner))
    yield
    bot.history.clear()
    blizzard.search_cache.clear()
    blizzard.data_cache.clear()
    blizzard.wow_token_cache["data"] = None
    blizzard.wow_token_cache["timestamp"] = 0.0


# ============================================================================
# 1. BLIZZARD API REQUEST TIMEOUTS
# ============================================================================

def test_blizzard_api_timeout_constants_defined():
    """Shared timeout constants must be defined as positive numbers."""
    assert hasattr(blizzard, "BLIZZARD_API_TIMEOUT")
    assert hasattr(blizzard, "BLIZZARD_REQUEST_TIMEOUT")
    assert blizzard.BLIZZARD_API_TIMEOUT > 0
    assert blizzard.BLIZZARD_API_TIMEOUT == blizzard.BLIZZARD_REQUEST_TIMEOUT


def test_every_outbound_blizzard_request_uses_timeout_constant(monkeypatch):
    """Every requests.get and requests.post call in src.api.blizzard must pass the shared timeout."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "token123", "expires_in": 3600, "results": [], "price": 2000000000}
    mock_response.raise_for_status = MagicMock()

    mock_get = MagicMock(return_value=mock_response)
    mock_post = MagicMock(return_value=mock_response)
    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr("requests.post", mock_post)

    # 1. OAuth post
    blizzard.get_access_token()
    assert mock_post.called
    assert mock_post.call_args.kwargs.get("timeout") == blizzard.BLIZZARD_API_TIMEOUT

    # 2. Entity fetches
    fetch_functions = [
        (blizzard.search_blizzard, ("custom_query", "item", "token")),
        (blizzard.search_blizzard, ("custom_query", "quest", "token")),
        (blizzard.get_item_data, (12345, "token")),
        (blizzard.get_creature_data, (12345, "token")),
        (blizzard.get_quest_data, (12345, "token")),
        (blizzard.get_mount_data, (12345, "token")),
        (blizzard.get_achievement_data, (12345, "token")),
        (blizzard.get_spell_data, (12345, "token")),
        (blizzard.get_journal_instance_data, (12345, "token")),
        (blizzard.get_reputation_faction_data, (12345, "token")),
        (blizzard.get_title_data, (12345, "token")),
        (blizzard.get_toy_data, (12345, "token")),
        (blizzard.get_pet_data, (12345, "token")),
        (blizzard.get_heirloom_data, (12345, "token")),
        (blizzard.get_wow_token_price, ("token",)),
    ]

    for func, args in fetch_functions:
        mock_get.reset_mock()
        func(*args)
        assert mock_get.called, f"{func.__name__} did not call requests.get"
        assert mock_get.call_args.kwargs.get("timeout") == blizzard.BLIZZARD_API_TIMEOUT, (
            f"{func.__name__} did not pass timeout={blizzard.BLIZZARD_API_TIMEOUT}"
        )


def test_oauth_timeout_retries_and_fails_safely(monkeypatch):
    """A timeout during get_access_token must retry 3 times and return (None, None)."""
    mock_post = MagicMock(side_effect=requests.exceptions.Timeout("Connection timed out"))
    monkeypatch.setattr("requests.post", mock_post)
    monkeypatch.setattr("time.sleep", MagicMock())  # Skip 2s sleep delay

    token, expires_in = blizzard.get_access_token()

    assert mock_post.call_count == 3
    assert token is None
    assert expires_in is None


def test_entity_fetch_timeout_fails_safely(monkeypatch):
    """A timeout during entity fetch must fail safely by returning None."""
    mock_get = MagicMock(side_effect=requests.exceptions.Timeout("Read timed out"))
    monkeypatch.setattr("requests.get", mock_get)

    assert blizzard.get_item_data(99999, "token") is None
    assert blizzard.search_blizzard("Unknown Item", "item", "token") is None
    assert blizzard.get_wow_token_price("token") is None


# ============================================================================
# 2. WOW TOKEN PRICE CACHE TTL
# ============================================================================

def test_wow_token_ttl_constant_defined():
    """WOW_TOKEN_CACHE_TTL_SECONDS must be around 60 seconds."""
    assert hasattr(blizzard, "WOW_TOKEN_CACHE_TTL_SECONDS")
    assert 30 <= blizzard.WOW_TOKEN_CACHE_TTL_SECONDS <= 120


def test_wow_token_cache_hit_before_ttl_expiration(monkeypatch):
    """Within TTL, repeated requests must return cached data without extra network calls."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"price": 2500000000}  # 250,000 gold
    mock_response.raise_for_status = MagicMock()

    mock_get = MagicMock(return_value=mock_response)
    monkeypatch.setattr("requests.get", mock_get)

    current_time = 1000.0
    monkeypatch.setattr("time.time", lambda: current_time)

    # First fetch: makes network call
    first_result = blizzard.get_wow_token_price("token")
    assert mock_get.call_count == 1
    assert first_result["price"] == 250000

    # Advance time by 30 seconds (still within 60s TTL)
    current_time = 1030.0

    second_result = blizzard.get_wow_token_price("token")
    assert mock_get.call_count == 1, "Expected cache hit; network call was made within TTL"
    assert second_result == first_result


def test_wow_token_fresh_fetch_after_ttl_expiration(monkeypatch):
    """After TTL expires, a fresh network call must be made to fetch updated price."""
    mock_response_1 = MagicMock()
    mock_response_1.status_code = 200
    mock_response_1.json.return_value = {"price": 2500000000}  # 250,000 gold
    mock_response_1.raise_for_status = MagicMock()

    mock_response_2 = MagicMock()
    mock_response_2.status_code = 200
    mock_response_2.json.return_value = {"price": 2750000000}  # 275,000 gold
    mock_response_2.raise_for_status = MagicMock()

    mock_get = MagicMock(side_effect=[mock_response_1, mock_response_2])
    monkeypatch.setattr("requests.get", mock_get)

    current_time = 1000.0
    monkeypatch.setattr("time.time", lambda: current_time)

    # First fetch at t=1000
    res1 = blizzard.get_wow_token_price("token")
    assert mock_get.call_count == 1
    assert res1["price"] == 250000

    # Advance time past TTL (61 seconds later)
    current_time = 1000.0 + blizzard.WOW_TOKEN_CACHE_TTL_SECONDS + 1

    # Second fetch: must query Blizzard API again
    res2 = blizzard.get_wow_token_price("token")
    assert mock_get.call_count == 2
    assert res2["price"] == 275000


def test_wow_token_fetch_failure_after_ttl_returns_none(monkeypatch):
    """Network failure on fresh fetch returns None safely."""
    mock_get = MagicMock(side_effect=requests.exceptions.RequestException("Connection error"))
    monkeypatch.setattr("requests.get", mock_get)

    result = blizzard.get_wow_token_price("token")
    assert result is None


# ============================================================================
# 3. CASE-INSENSITIVE FAMOUS ITEM FALLBACK
# ============================================================================

@pytest.mark.parametrize(
    "variant",
    ["Thunderfury", "thunderfury", "THUNDERFURY", "ThUnDeRfUrY", "  Thunderfury  ", "thunderfury  "]
)
def test_famous_item_fallback_thunderfury_capitalization_variants(variant, monkeypatch):
    """Thunderfury in any casing must resolve identically to 19019 without network requests."""
    mock_get = MagicMock()
    monkeypatch.setattr("requests.get", mock_get)

    item_id = blizzard.search_blizzard(variant, "item", "token")
    assert item_id == 19019
    assert not mock_get.called, "Famous item fallback must not make any outbound network calls"


def test_all_famous_items_resolve_case_insensitively(monkeypatch):
    """All entries in famous_items must resolve case-insensitively without network calls."""
    mock_get = MagicMock()
    monkeypatch.setattr("requests.get", mock_get)

    expected_famous_items = {
        "ashbringer": 13262,
        "thunderfury": 19019,
        "sulfuras": 17182,
        "atiesh": 22589,
        "val'anyr": 46017,
        "shadowmourne": 49623,
        "dragonwrath": 78495,
    }

    for name, expected_id in expected_famous_items.items():
        for variant in [name.lower(), name.upper(), name.capitalize()]:
            blizzard.search_cache.clear()
            item_id = blizzard.search_blizzard(variant, "item", "token")
            assert item_id == expected_id, f"Failed resolving famous item '{variant}'"
            assert not mock_get.called


# ============================================================================
# 4. ITEM TOOL CONTRACT / SCHEMA MISMATCH
# ============================================================================

def test_lookup_item_schema_requires_item_id_and_forbids_name():
    """lookup_item schema must strictly describe numeric item ID lookup."""
    schema = next(s["function"] for s in TOOL_SCHEMAS if s["function"]["name"] == "lookup_item")
    assert "item_id" in schema["parameters"]["properties"]
    assert "search_term" not in schema["parameters"]["properties"]
    assert schema["parameters"]["required"] == ["item_id"]
    # Description must clarify numeric ID only, not names
    desc = schema["description"].lower()
    assert "numeric" in desc or "id" in desc
    assert "search_item_by_name" in schema["description"]


def test_search_item_by_name_schema_requires_search_term_and_forbids_id():
    """search_item_by_name schema must strictly describe item name lookup."""
    schema = next(s["function"] for s in TOOL_SCHEMAS if s["function"]["name"] == "search_item_by_name")
    assert "search_term" in schema["parameters"]["properties"]
    assert "item_id" not in schema["parameters"]["properties"]
    assert schema["parameters"]["required"] == ["search_term"]
    # Description must clarify name only, not numeric IDs
    assert "lookup_item" in schema["description"]


def test_system_prompt_distinguishes_item_name_and_item_id():
    """SYSTEM_PROMPT must tell the model to use search_item_by_name for names and lookup_item for IDs."""
    prompt_lower = SYSTEM_PROMPT.lower()
    assert "search_item_by_name" in prompt_lower
    assert "lookup_item" in prompt_lower


def test_handle_lookup_item_contract(monkeypatch):
    """handle_lookup_item uses item_id and passes to get_item_data."""
    mock_get_data = MagicMock(return_value={"name": "Thunderfury"})
    monkeypatch.setattr("src.tools.handlers.get_item_data", mock_get_data)

    res = handle_lookup_item({"item_id": "19019"}, "token")
    assert "Thunderfury" in res
    mock_get_data.assert_called_once_with("19019", "token")

    # Empty item_id returns official not found message without calling get_item_data
    mock_get_data.reset_mock()
    empty_res = handle_lookup_item({}, "token")
    assert "NO OFFICIAL DATA FOUND" in empty_res
    assert not mock_get_data.called


def test_handle_search_item_by_name_contract(monkeypatch):
    """handle_search_item_by_name uses search_term and passes to search_blizzard."""
    mock_search = MagicMock(return_value=19019)
    mock_get_data = MagicMock(return_value={"name": "Thunderfury"})
    monkeypatch.setattr("src.tools.handlers.search_blizzard", mock_search)
    monkeypatch.setattr("src.tools.handlers.get_item_data", mock_get_data)

    res = handle_search_item_by_name({"search_term": "Thunderfury"}, "token")
    assert "Thunderfury" in res
    mock_search.assert_called_once_with("Thunderfury", "item", "token")
    mock_get_data.assert_called_once_with(19019, "token")

    # Empty search_term returns official not found message without calling search
    mock_search.reset_mock()
    empty_res = handle_search_item_by_name({}, "token")
    assert "NO OFFICIAL DATA FOUND" in empty_res
    assert not mock_search.called


# ============================================================================
# 5. MULTIPLE TOOL CALL HISTORY
# ============================================================================

def test_multiple_tool_calls_stored_in_single_assistant_message(monkeypatch):
    """When model outputs multiple tool calls, history must store them in a single assistant entry followed by tool results."""
    call_1 = ToolCall(id="call_001_aaa", name="search_creature", arguments='{"search_term": "Ragnaros"}')
    call_2 = ToolCall(id="call_002_bbb", name="search_item_by_name", arguments='{"search_term": "Sulfuras"}')

    llm_first_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call_1, call_2]))]
    )
    llm_final_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="By fire be purged!", tool_calls=None))]
    )

    mock_create = MagicMock(side_effect=[llm_first_response, llm_final_response])
    monkeypatch.setattr(bot.client.chat.completions, "create", mock_create)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["Tell me about Ragnaros and Sulfuras", "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())

    handler_creature = MagicMock(return_value="Creature: Ragnaros")
    handler_item = MagicMock(return_value="Item: Sulfuras")
    monkeypatch.setitem(bot.TOOL_HANDLERS, "search_creature", handler_creature)
    monkeypatch.setitem(bot.TOOL_HANDLERS, "search_item_by_name", handler_item)

    run()

    # Find the assistant tool_calls entry
    assistant_tool_entries = [h for h in bot.history if h.get("role") == "assistant" and "tool_calls" in h]
    assert len(assistant_tool_entries) == 1, (
        f"Expected exactly 1 assistant entry with tool_calls, but found {len(assistant_tool_entries)}"
    )

    assistant_entry = assistant_tool_entries[0]
    assert assistant_entry["content"] is None
    assert len(assistant_entry["tool_calls"]) == 2

    # Verify both tool calls inside the single assistant entry
    tc1 = assistant_entry["tool_calls"][0]
    assert tc1["id"] == "call_001_aaa"
    assert tc1["type"] == "function"
    assert tc1["function"]["name"] == "search_creature"
    assert json.loads(tc1["function"]["arguments"]) == {"search_term": "Ragnaros"}

    tc2 = assistant_entry["tool_calls"][1]
    assert tc2["id"] == "call_002_bbb"
    assert tc2["type"] == "function"
    assert tc2["function"]["name"] == "search_item_by_name"
    assert json.loads(tc2["function"]["arguments"]) == {"search_term": "Sulfuras"}

    # Verify tool results entries follow in order with matching tool_call_ids
    tool_entries = [h for h in bot.history if h.get("role") == "tool"]
    assert len(tool_entries) == 2
    assert tool_entries[0]["tool_call_id"] == "call_001_aaa"
    assert tool_entries[0]["content"] == "Creature: Ragnaros"
    assert tool_entries[1]["tool_call_id"] == "call_002_bbb"
    assert tool_entries[1]["content"] == "Item: Sulfuras"

    # Execution order check
    assert handler_creature.called
    assert handler_item.called

    # JSON serializability check
    serialized = json.dumps(bot.history)
    deserialized = json.loads(serialized)
    assert len(deserialized) == len(bot.history)


def test_multiple_tool_calls_ordering_in_history(monkeypatch):
    """Verify that execution and history preserve the exact order of tool calls."""
    execution_order = []

    def mock_h1(args, token):
        execution_order.append("tool_1")
        return "Result 1"

    def mock_h2(args, token):
        execution_order.append("tool_2")
        return "Result 2"

    call_1 = ToolCall(id="call_x1", name="search_creature", arguments='{"search_term": "A"}')
    call_2 = ToolCall(id="call_x2", name="search_item_by_name", arguments='{"search_term": "B"}')

    llm_first = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call_1, call_2]))]
    )
    llm_final = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Done.", tool_calls=None))]
    )

    monkeypatch.setattr(bot.client.chat.completions, "create", MagicMock(side_effect=[llm_first, llm_final]))
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["Check A and B", "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())
    monkeypatch.setitem(bot.TOOL_HANDLERS, "search_creature", mock_h1)
    monkeypatch.setitem(bot.TOOL_HANDLERS, "search_item_by_name", mock_h2)

    run()

    assert execution_order == ["tool_1", "tool_2"]

    # History shape check: User -> Assistant (with 2 calls) -> Tool 1 -> Tool 2 -> Assistant (final)
    roles = [h["role"] for h in bot.history]
    assert roles == ["user", "assistant", "tool", "tool", "assistant"]
    assert bot.history[2]["tool_call_id"] == "call_x1"
    assert bot.history[3]["tool_call_id"] == "call_x2"


def test_malformed_tool_call_alongside_valid_tool_call(monkeypatch):
    """A malformed tool call must produce an error result without preventing the valid tool call from executing."""
    call_bad = ToolCall(id="call_bad_111", name="search_creature", arguments="{not_valid_json!")
    call_good = ToolCall(id="call_good_222", name="search_item_by_name", arguments='{"search_term": "Thunderfury"}')

    llm_first = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call_bad, call_good]))]
    )
    llm_final = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Here is your blade info.", tool_calls=None))]
    )

    mock_good_handler = MagicMock(return_value="Thunderfury Item Data")
    mock_bad_handler = MagicMock()

    monkeypatch.setattr(bot.client.chat.completions, "create", MagicMock(side_effect=[llm_first, llm_final]))
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["Thunderfury lore", "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())
    monkeypatch.setitem(bot.TOOL_HANDLERS, "search_creature", mock_bad_handler)
    monkeypatch.setitem(bot.TOOL_HANDLERS, "search_item_by_name", mock_good_handler)

    run()

    # The bad handler was never called because argument parsing failed
    assert not mock_bad_handler.called
    # The good handler was called successfully
    assert mock_good_handler.called

    # Assistant message contains both tool calls
    assistant_entry = next(h for h in bot.history if h.get("role") == "assistant" and "tool_calls" in h)
    assert len(assistant_entry["tool_calls"]) == 2
    assert assistant_entry["tool_calls"][0]["id"] == "call_bad_111"
    assert assistant_entry["tool_calls"][0]["function"]["arguments"] == "{not_valid_json!"
    assert assistant_entry["tool_calls"][1]["id"] == "call_good_222"

    # Tool results: bad call produced safe error, good call produced data
    tool_entries = [h for h in bot.history if h.get("role") == "tool"]
    assert len(tool_entries) == 2
    assert tool_entries[0]["tool_call_id"] == "call_bad_111"
    assert tool_entries[0]["content"] == "Error parsing tool arguments."
    assert tool_entries[1]["tool_call_id"] == "call_good_222"
    assert tool_entries[1]["content"] == "Thunderfury Item Data"

    # Entire history is JSON-serializable
    assert json.dumps(bot.history) is not None


def test_single_tool_call_behavior_preserved(monkeypatch):
    """Single tool call behavior remains backwards-compatible."""
    call = ToolCall(id="call_single_123", name="lookup_item", arguments='{"item_id": "19019"}')

    llm_first = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call]))]
    )
    llm_final = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Single item response.", tool_calls=None))]
    )

    mock_handler = MagicMock(return_value="Single Item Data")
    monkeypatch.setattr(bot.client.chat.completions, "create", MagicMock(side_effect=[llm_first, llm_final]))
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["19019", "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())
    monkeypatch.setitem(bot.TOOL_HANDLERS, "lookup_item", mock_handler)

    run()

    assistant_entries = [h for h in bot.history if h.get("role") == "assistant" and "tool_calls" in h]
    assert len(assistant_entries) == 1
    assert len(assistant_entries[0]["tool_calls"]) == 1
    assert assistant_entries[0]["tool_calls"][0]["id"] == "call_single_123"

    tool_entries = [h for h in bot.history if h.get("role") == "tool"]
    assert len(tool_entries) == 1
    assert tool_entries[0]["tool_call_id"] == "call_single_123"
    assert tool_entries[0]["content"] == "Single Item Data"

    assert json.dumps(bot.history) is not None


# ============================================================================
# 6. HARDENED EDGE CASES & DEFENSIVE INTEGRITY
# ============================================================================

def test_lookup_item_rejects_non_numeric_item_name(monkeypatch):
    """handle_lookup_item must reject non-numeric item names without calling Blizzard API."""
    mock_get_data = MagicMock()
    monkeypatch.setattr("src.tools.handlers.get_item_data", mock_get_data)

    res = handle_lookup_item({"item_id": "Thunderfury"}, "token")
    assert "NO OFFICIAL DATA FOUND" in res
    assert not mock_get_data.called, "get_item_data should not be called with a non-numeric item name"


def test_get_item_data_cache_hit_between_int_and_string_id(monkeypatch):
    """get_item_data must share cache entries between int(19019) and str('19019')."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": 19019, "name": "Thunderfury"}
    mock_response.raise_for_status = MagicMock()

    mock_get = MagicMock(return_value=mock_response)
    monkeypatch.setattr("requests.get", mock_get)

    # First fetch with int 19019
    data1 = blizzard.get_item_data(19019, "token")
    assert mock_get.call_count == 1
    assert data1["name"] == "Thunderfury"

    # Second fetch with str '19019'
    data2 = blizzard.get_item_data("19019", "token")
    assert mock_get.call_count == 1, "Expected cache hit; network call was made for string ID"
    assert data2 == data1


def test_wow_token_clock_skew_backwards_refetches(monkeypatch):
    """If the system clock adjusts backwards, WoW Token cache must refetch rather than serving stale data."""
    mock_response_1 = MagicMock()
    mock_response_1.status_code = 200
    mock_response_1.json.return_value = {"price": 2500000000}
    mock_response_1.raise_for_status = MagicMock()

    mock_response_2 = MagicMock()
    mock_response_2.status_code = 200
    mock_response_2.json.return_value = {"price": 2600000000}
    mock_response_2.raise_for_status = MagicMock()

    mock_get = MagicMock(side_effect=[mock_response_1, mock_response_2])
    monkeypatch.setattr("requests.get", mock_get)

    current_time = 1000.0
    monkeypatch.setattr("time.time", lambda: current_time)

    res1 = blizzard.get_wow_token_price("token")
    assert mock_get.call_count == 1
    assert res1["price"] == 250000

    # System clock moves backwards to 950.0 (negative elapsed time)
    current_time = 950.0
    res2 = blizzard.get_wow_token_price("token")
    assert mock_get.call_count == 2, "Expected fresh fetch when clock moved backwards"
    assert res2["price"] == 260000


@pytest.mark.parametrize("invalid_payload", [
    {},
    {"price": 0},
    {"price": -100},
    {"price": None},
    {"price": "not a number"},
])
def test_wow_token_invalid_missing_price_returns_none(invalid_payload, monkeypatch):
    """Missing, non-positive, or non-numeric price from Blizzard must return None and avoid caching 0 gold."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = invalid_payload
    mock_response.raise_for_status = MagicMock()

    monkeypatch.setattr("requests.get", MagicMock(return_value=mock_response))

    result = blizzard.get_wow_token_price("token")
    assert result is None
    assert blizzard.wow_token_cache["data"] is None


def test_wow_token_recovery_after_failed_fetch_after_ttl(monkeypatch):
    """When a fetch after TTL fails, the subsequent request can recover and fetch fresh data once network restores."""
    mock_response_1 = MagicMock()
    mock_response_1.status_code = 200
    mock_response_1.json.return_value = {"price": 2500000000}
    mock_response_1.raise_for_status = MagicMock()

    mock_response_3 = MagicMock()
    mock_response_3.status_code = 200
    mock_response_3.json.return_value = {"price": 2700000000}
    mock_response_3.raise_for_status = MagicMock()

    # Call 1: success, Call 2: timeout, Call 3: success
    mock_get = MagicMock(side_effect=[
        mock_response_1,
        requests.exceptions.Timeout("Read timeout"),
        mock_response_3,
    ])
    monkeypatch.setattr("requests.get", mock_get)

    current_time = 1000.0
    monkeypatch.setattr("time.time", lambda: current_time)

    # Call 1: t=1000 (initial)
    res1 = blizzard.get_wow_token_price("token")
    assert res1["price"] == 250000

    # Call 2: t=1070 (expired, network failure)
    current_time = 1070.0
    res2 = blizzard.get_wow_token_price("token")
    assert res2 is None

    # Call 3: t=1075 (network restored)
    current_time = 1075.0
    res3 = blizzard.get_wow_token_price("token")
    assert res3["price"] == 270000
    assert blizzard.wow_token_cache["data"]["price"] == 270000


def test_non_dict_json_arguments_produce_safe_error_without_crash(monkeypatch):
    """Tool call arguments that parse to non-dicts (list, int, str) must produce safe error without crashing the chat loop."""
    call_list = ToolCall(id="call_list_1", name="search_creature", arguments='["Ragnaros", "Onyxia"]')
    call_int = ToolCall(id="call_int_2", name="search_creature", arguments='12345')
    call_valid = ToolCall(id="call_valid_3", name="lookup_item", arguments='{"item_id": "19019"}')

    first_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call_list, call_int, call_valid]))]
    )
    second_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Final summary.", tool_calls=None))]
    )

    mock_create = MagicMock(side_effect=[first_resp, second_resp])
    mock_item_handler = MagicMock(return_value="Thunderfury: 19019")

    monkeypatch.setattr(bot.client.chat.completions, "create", mock_create)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["Check list and int args", "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())
    monkeypatch.setitem(bot.TOOL_HANDLERS, "lookup_item", mock_item_handler)

    run()

    # The valid call handler must have executed
    assert mock_item_handler.called

    # Assistant message contains all 3 tool calls
    assistant_entry = next(h for h in bot.history if h.get("role") == "assistant" and "tool_calls" in h)
    assert len(assistant_entry["tool_calls"]) == 3

    # Results: first 2 are safe errors, 3rd is valid
    tool_entries = [h for h in bot.history if h.get("role") == "tool"]
    assert len(tool_entries) == 3
    assert tool_entries[0]["content"] == "Error parsing tool arguments."
    assert tool_entries[1]["content"] == "Error parsing tool arguments."
    assert tool_entries[2]["content"] == "Thunderfury: 19019"


def test_tool_handler_exception_isolated_in_multi_call(monkeypatch):
    """An unhandled exception in one tool handler must not crash the chat loop or prevent other tool calls."""
    call_bad = ToolCall(id="call_crash_1", name="search_creature", arguments='{"search_term": "Ragnaros"}')
    call_good = ToolCall(id="call_good_2", name="lookup_item", arguments='{"item_id": "19019"}')

    first_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call_bad, call_good]))]
    )
    second_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Handled safely.", tool_calls=None))]
    )

    def failing_handler(args, token):
        raise RuntimeError("Unexpected Blizzard connection abort")

    good_handler = MagicMock(return_value="Thunderfury Item Data")

    monkeypatch.setattr(bot.client.chat.completions, "create", MagicMock(side_effect=[first_resp, second_resp]))
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["Crash test", "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())
    monkeypatch.setitem(bot.TOOL_HANDLERS, "search_creature", failing_handler)
    monkeypatch.setitem(bot.TOOL_HANDLERS, "lookup_item", good_handler)

    run()

    assert good_handler.called

    tool_entries = [h for h in bot.history if h.get("role") == "tool"]
    assert len(tool_entries) == 2
    assert "Error executing tool" in tool_entries[0]["content"]
    assert tool_entries[1]["content"] == "Thunderfury Item Data"


def test_fallback_multiple_tool_calls_in_content():
    """parse_tool_calls must extract all tool calls from a fallback array, not just the first."""
    content = 'Thinking... [{"name": "search_creature", "arguments": {"search_term": "Ragnaros"}}, {"name": "search_item_by_name", "arguments": {"search_term": "Sulfuras"}}]'
    response_message = SimpleNamespace(tool_calls=None, content=content)

    tool_calls = bot.parse_tool_calls(response_message)
    assert len(tool_calls) == 2
    assert tool_calls[0].function.name == "search_creature"
    assert json.loads(tool_calls[0].function.arguments) == {"search_term": "Ragnaros"}
    assert tool_calls[1].function.name == "search_item_by_name"
    assert json.loads(tool_calls[1].function.arguments) == {"search_term": "Sulfuras"}
    assert response_message.content == "Thinking..."


def test_famous_items_with_custom_capitalized_entries(monkeypatch):
    """Famous items fallback must resolve case-insensitively even if entries have mixed-case keys."""
    monkeypatch.setitem(blizzard.famous_items, "Frostmourne", 12345)
    mock_get = MagicMock()
    monkeypatch.setattr("requests.get", mock_get)

    assert blizzard.search_blizzard("frostmourne", "item", "token") == 12345
    assert blizzard.search_blizzard("Frostmourne", "item", "token") == 12345
    assert blizzard.search_blizzard("FROSTMOURNE", "item", "token") == 12345
    assert blizzard.search_blizzard("  Frostmourne  ", "ITEM", "token") == 12345
    assert not mock_get.called


def test_clean_schema_examples_for_quests_mounts_spells():
    """Schemas for quests, mounts, and spells must not use item examples like Thunderfury or Phantom Blade."""
    quest_schema = next(s["function"] for s in TOOL_SCHEMAS if s["function"]["name"] == "search_quest_by_name")
    assert "Phantom Blade" not in quest_schema["parameters"]["properties"]["search_term"]["description"]

    mount_schema = next(s["function"] for s in TOOL_SCHEMAS if s["function"]["name"] == "search_mount_by_name")
    assert "Phantom Blade" not in mount_schema["parameters"]["properties"]["search_term"]["description"]

    spell_schema = next(s["function"] for s in TOOL_SCHEMAS if s["function"]["name"] == "search_spell_by_name")
    assert "Thunderfury" not in spell_schema["parameters"]["properties"]["search_term"]["description"]

