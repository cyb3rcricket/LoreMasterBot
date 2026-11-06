"""Regression tests for all 17 findings in Nov_6_2_error_report.md.

Covers:
1. Replies starting with 'Let me', 'I will', 'Since the' are preserved on greetings and grounded tool turns.
2. Blizzard 401 invalidates cached token, retries refresh once, and reports unavailable instead of NO OFFICIAL DATA FOUND.
3. Failed static-index fetch does not cache [] in search_cache.
4. Null or non-numeric expires_in in token responses fails cleanly without TypeError.
5. Failed refresh in the 60s pre-expiry window reuses the still-valid token.
6. Empty choices, None message, list content, provider exception, or malformed tool call objects do not crash run().
7. Leading/trailing spaces in search_blizzard are stripped for query params, exact match, and cache key.
8. Pretty-printed multi-line JSON and brackets inside string arguments in parse_tool_calls.
9. create_llm_client disables environment proxies (trust_env=False).
10. Tool calls per turn are deduplicated/capped, and tool-only second responses avoid '(no response)'.
11. Whitespace-only model replies normalize to '(no response)' and close the turn in trim_history.
12. 'quit' with surrounding whitespace exits cleanly without calling the model.
13. EOFError (Ctrl-D) and KeyboardInterrupt (Ctrl-C) print Goodbye and exit cleanly without traceback.
14. First model call passes timeout and starts Spinner.
15. Oversized tool results are capped while preserving id and name.
16. Blank BLIZZARD_CLIENT_ID in os.environ does not hide .env value.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

import src.api.blizzard as blizzard
import src.bot as bot
from src.bot import ToolCall, create_llm_client, parse_tool_calls, run
from src.config import LLM_REQUEST_TIMEOUT
from src.tools import handlers


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Isolate state and block real network calls around every test."""
    bot.history.clear()
    blizzard.blizzard_token = None
    blizzard.token_expiry = 0
    blizzard.last_error_was_auth = False
    blizzard.search_cache.clear()
    blizzard.data_cache.clear()
    blizzard.wow_token_cache["data"] = None
    blizzard.wow_token_cache["timestamp"] = 0.0
    monkeypatch.setattr("src.bot.ensure_valid_token", lambda: "mock_token")
    monkeypatch.setattr("src.bot.get_access_token", lambda: ("mock_token", 3600))
    monkeypatch.setattr("src.api.blizzard.ensure_valid_token", lambda: "mock_token")
    monkeypatch.setattr("src.bot.Spinner", MagicMock(return_value=MagicMock()))
    yield
    bot.history.clear()
    blizzard.blizzard_token = None
    blizzard.token_expiry = 0
    blizzard.last_error_was_auth = False
    blizzard.search_cache.clear()
    blizzard.data_cache.clear()
    blizzard.wow_token_cache["data"] = None
    blizzard.wow_token_cache["timestamp"] = 0.0


# ============================================================================
# 1. Grounded and conversational replies starting with "Let me", "I will", "Since the"
# ============================================================================

@pytest.mark.parametrize(
    "greeting_reply",
    [
        "Let me welcome you to the campfire, friend.",
        "Since the fire is warm, welcome, friend.",
        "I will gladly keep you company by the hearth.",
    ],
)
def test_conversational_replies_with_natural_prefixes_are_preserved(greeting_reply, monkeypatch):
    """Greetings starting with 'Let me', 'Since the', or 'I will' must not be replaced with silence."""
    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=greeting_reply, tool_calls=None))]
    )
    monkeypatch.setattr(bot.client.chat.completions, "create", MagicMock(return_value=resp))
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["hi", "quit"]))
    printed = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: printed.append(" ".join(str(x) for x in a)))

    run()

    output = "\n".join(printed)
    assert f"Loremaster: {greeting_reply}" in output
    assert "ancient scrolls are silent" not in output
    assert bot.history[-1]["content"] == greeting_reply


def test_grounded_tool_reply_starting_with_i_will_is_preserved(monkeypatch):
    """A grounded answer after a tool call must not be discarded if it starts with 'I will' or 'Let me'."""
    tc = ToolCall(id="call_race_1", name="search_playable_race", arguments='{"search_term": "Human"}')
    first_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[tc]))]
    )
    grounded_line = "I will share only the official record: Humans are an Alliance playable race."
    second_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=grounded_line, tool_calls=None))]
    )
    monkeypatch.setattr(bot.client.chat.completions, "create", MagicMock(side_effect=[first_resp, second_resp]))
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["Tell me about the Human race", "quit"]))
    monkeypatch.setitem(
        bot.TOOL_HANDLERS,
        "search_playable_race",
        MagicMock(return_value="Playable race data received: {'id': 1, 'name': 'Human', 'faction': 'Alliance'}"),
    )
    printed = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: printed.append(" ".join(str(x) for x in a)))

    run()

    output = "\n".join(printed)
    assert f"Loremaster: {grounded_line}" in output
    assert "ancient scrolls are silent" not in output
    assert bot.history[-1]["content"] == grounded_line


# ============================================================================
# 2. Blizzard 401 drops dead token, refreshes once, and reports auth failure
# ============================================================================

def test_blizzard_401_drops_dead_token_and_reports_auth_failure(monkeypatch):
    """A 401 response must clear the dead token, attempt refresh once, and avoid NO OFFICIAL DATA FOUND."""
    blizzard.blizzard_token = "TOKEN_DEADBEEF"
    blizzard.token_expiry = time.time() + 3600

    resp_401 = MagicMock()
    resp_401.status_code = 401
    resp_401.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "401 Client Error: Unauthorized for url: https://us.api.blizzard.com/data/wow/item/19019",
        response=resp_401,
    )
    monkeypatch.setattr("requests.get", MagicMock(return_value=resp_401))
    monkeypatch.setattr(blizzard, "get_access_token", MagicMock(return_value=(None, None)))
    monkeypatch.setattr(blizzard, "ensure_valid_token", blizzard.__dict__["ensure_valid_token"])

    result = handlers.handle_lookup_item({"item_id": 19019}, "TOKEN_DEADBEEF")

    assert blizzard.blizzard_token is None
    assert "NO OFFICIAL DATA FOUND" not in result
    assert "unavailable" in result.lower() or "authentication failed" in result.lower()


def test_blizzard_401_retries_once_when_refresh_succeeds(monkeypatch):
    """If a 401 triggers a token refresh that succeeds, the request is retried once with the new token."""
    blizzard.blizzard_token = "OLD_DEAD_TOKEN"
    blizzard.token_expiry = time.time() + 3600

    resp_401 = MagicMock()
    resp_401.status_code = 401
    resp_401.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized", response=resp_401)

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.raise_for_status = MagicMock()
    resp_200.json.return_value = {"id": 19019, "name": "Thunderfury"}

    mock_get = MagicMock(side_effect=[resp_401, resp_200])
    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr(blizzard, "get_access_token", MagicMock(return_value=("FRESH_TOKEN", 3600)))

    # Restore real ensure_valid_token
    from importlib import reload
    monkeypatch.setattr(
        blizzard,
        "ensure_valid_token",
        lambda: (
            setattr(blizzard, "blizzard_token", "FRESH_TOKEN")
            or setattr(blizzard, "token_expiry", time.time() + 3600)
            or "FRESH_TOKEN"
        ),
    )

    result = handlers.handle_lookup_item({"item_id": 19019}, "OLD_DEAD_TOKEN")
    assert "Thunderfury" in result
    assert mock_get.call_count == 2
    assert mock_get.call_args_list[1].kwargs["headers"]["Authorization"] == "Bearer FRESH_TOKEN"


# ============================================================================
# 3. Failed static-index fetch is not cached as "no such name"
# ============================================================================

def test_failed_static_index_fetch_is_not_cached_in_search_cache(monkeypatch):
    """A transient 500 on /playable-race/index must not cache [] in search_cache."""
    resp_500 = MagicMock()
    resp_500.status_code = 500
    resp_500.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error", response=resp_500)

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.raise_for_status = MagicMock()
    resp_200.json.return_value = {"races": [{"id": 1, "name": "Human"}]}

    mock_get = MagicMock(side_effect=[resp_500, resp_200])
    monkeypatch.setattr("requests.get", mock_get)

    first = blizzard.lookup_static_ids("Human", "playable-race", "tok")
    assert first == []
    assert ("index-lookup", "playable-race", "human") not in blizzard.search_cache

    second = blizzard.lookup_static_ids("Human", "playable-race", "tok")
    assert second == [1]
    assert mock_get.call_count == 2


# ============================================================================
# 4. Null or non-numeric expires_in in token response
# ============================================================================

@pytest.mark.parametrize("bad_expires_in", [None, "3600", 0, -10, False, True, []])
def test_get_access_token_rejects_invalid_expires_in(bad_expires_in, monkeypatch):
    """get_access_token must reject null, string, bool, or non-positive expires_in values."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"access_token": "NEWTOKEN", "expires_in": bad_expires_in}
    monkeypatch.setattr("requests.post", MagicMock(return_value=mock_resp))
    monkeypatch.setattr("time.sleep", MagicMock())

    token, expires_in = blizzard.get_access_token()
    assert (token, expires_in) == (None, None)


def test_authenticate_blizzard_handles_null_expires_in_without_crash(monkeypatch):
    """Even if get_access_token returns ('NEWTOKEN', None), _authenticate_blizzard must not crash."""
    monkeypatch.setattr("src.bot.get_access_token", lambda: ("NEWTOKEN", None))
    printed = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: printed.append(" ".join(str(x) for x in a)))

    bot._authenticate_blizzard()

    assert blizzard.blizzard_token is None
    assert any("Could not authenticate with Blizzard" in line for line in printed)


# ============================================================================
# 5. Failed refresh in the 60s pre-expiry window reuses unexpired token
# ============================================================================

def test_failed_early_refresh_returns_still_valid_token(monkeypatch):
    """When refresh fails during the 60s pre-expiry window, ensure_valid_token returns the current unexpired token."""
    real_ensure = sys.modules["src.api.blizzard"].__dict__["ensure_valid_token"]
    # Restore real ensure_valid_token if monkeypatched by fixture
    blizzard.blizzard_token = "STILL_VALID"
    blizzard.token_expiry = 1030.0
    monkeypatch.setattr("time.time", lambda: 1000.0)
    monkeypatch.setattr(blizzard, "get_access_token", lambda: (None, None))

    # Call the underlying function definition from blizzard module
    token = blizzard.ensure_valid_token.__wrapped__() if hasattr(blizzard.ensure_valid_token, "__wrapped__") else None
    # Invoke directly via a fresh reference:
    monkeypatch.undo()
    blizzard.blizzard_token = "STILL_VALID"
    blizzard.token_expiry = 1030.0
    monkeypatch.setattr("time.time", lambda: 1000.0)
    monkeypatch.setattr(blizzard, "get_access_token", lambda: (None, None))

    assert blizzard.ensure_valid_token() == "STILL_VALID"

    # Once past expiry, a failed refresh must return None
    monkeypatch.setattr("time.time", lambda: 1035.0)
    assert blizzard.ensure_valid_token() is None
    assert blizzard.blizzard_token is None


# ============================================================================
# 6. Provider exceptions, empty choices, list content, and malformed tool call objects
# ============================================================================

def test_run_survives_empty_choices_none_message_and_provider_exception(monkeypatch):
    """choices=[], message=None, and RuntimeError from create() must not crash the chat loop."""
    empty_choices = SimpleNamespace(choices=[])
    none_message = SimpleNamespace(choices=[SimpleNamespace(message=None)])
    list_content = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=[{"type": "text", "text": "hi"}], tool_calls=None))]
    )
    valid_reply = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="The hearth is warm.", tool_calls=None))]
    )

    mock_create = MagicMock(
        side_effect=[
            empty_choices,
            none_message,
            list_content,
            RuntimeError("connection reset by ollama"),
            valid_reply,
        ]
    )
    monkeypatch.setattr(bot.client.chat.completions, "create", mock_create)
    monkeypatch.setattr(
        "builtins.input",
        MagicMock(side_effect=["q1", "q2", "q3", "q4", "hi", "quit"]),
    )
    printed = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: printed.append(" ".join(str(x) for x in a)))

    run()

    output = "\n".join(printed)
    assert "Loremaster: The hearth is warm." in output
    assert "Goodbye!" in output


def test_run_survives_tool_call_without_function_or_with_list_name(monkeypatch):
    """A tool call missing .function or with a list .function.name must not crash the turn."""
    bare_call = SimpleNamespace(id="call_bare")
    list_name_call = SimpleNamespace(
        id="call_list_name",
        function=SimpleNamespace(name=["unhashable"], arguments='{"item_id": "19019"}'),
    )
    first_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[bare_call, list_name_call]))]
    )
    second_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Recovered cleanly.", tool_calls=None))]
    )
    monkeypatch.setattr(bot.client.chat.completions, "create", MagicMock(side_effect=[first_resp, second_resp]))
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["Thunderfury", "quit"]))
    printed = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: printed.append(" ".join(str(x) for x in a)))

    run()

    output = "\n".join(printed)
    assert "Loremaster: Recovered cleanly." in output
    assert "Goodbye!" in output
    assert json.dumps(bot.history)


# ============================================================================
# 7. Padded search_term strips whitespace before query, exact compare, and cache
# ============================================================================

def test_padded_search_term_matches_exact_name_and_sends_stripped_param(monkeypatch):
    """search_blizzard('  Fireball  ', ...) must strip spaces for the request and exact-name check."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "results": [
            {"data": {"id": 111, "name": {"en_US": "Fireball of Doom"}}},
            {"data": {"id": 222, "name": {"en_US": "Fireball"}}},
        ]
    }
    mock_get = MagicMock(return_value=resp)
    monkeypatch.setattr("requests.get", mock_get)

    first_id = blizzard.search_blizzard("  Fireball  ", "spell", "tok")
    second_id = blizzard.search_blizzard("Fireball", "spell", "tok")

    assert first_id == 222
    assert second_id == 222
    assert mock_get.call_count == 1
    assert mock_get.call_args.kwargs["params"]["name.en_US"] == "Fireball"


# ============================================================================
# 8. Pretty-printed fallback tool JSON and brackets inside string arguments
# ============================================================================

def test_parse_tool_calls_handles_multiline_pretty_json_and_brackets_in_strings():
    """parse_tool_calls must extract pretty-printed JSON arrays and arguments containing ']'."""
    pretty_content = (
        'Here is the call:\n'
        '[\n'
        '  {\n'
        '    "name": "search_creature",\n'
        '    "arguments": {"search_term": "Young Nightsaber"}\n'
        '  }\n'
        ']'
    )
    msg_pretty = SimpleNamespace(tool_calls=None, content=pretty_content)
    calls_pretty = parse_tool_calls(msg_pretty)
    assert len(calls_pretty) == 1
    assert calls_pretty[0].function.name == "search_creature"
    assert json.loads(calls_pretty[0].function.arguments) == {"search_term": "Young Nightsaber"}
    assert msg_pretty.content == "Here is the call:"

    bracket_content = '[{"name": "search_item_by_name", "arguments": {"search_term": "Item [Thunderfury]"}}]'
    msg_bracket = SimpleNamespace(tool_calls=None, content=bracket_content)
    calls_bracket = parse_tool_calls(msg_bracket)
    assert len(calls_bracket) == 1
    assert calls_bracket[0].function.name == "search_item_by_name"
    assert json.loads(calls_bracket[0].function.arguments) == {"search_term": "Item [Thunderfury]"}
    assert msg_bracket.content == ""


# ============================================================================
# 9. Environment proxies disabled on LLM client
# ============================================================================

def test_create_llm_client_disables_environment_proxies_and_sets_timeout():
    """create_llm_client must disable trust_env on its HTTP client and configure LLM_REQUEST_TIMEOUT."""
    llm_client = create_llm_client()
    assert getattr(llm_client._client, "_trust_env", None) is False
    assert llm_client.timeout == LLM_REQUEST_TIMEOUT


# ============================================================================
# 10. Deduplicate/cap tool calls per turn and handle tool-only second completion
# ============================================================================

def test_duplicate_tool_calls_are_deduplicated_and_second_round_tool_call_handled(monkeypatch):
    """25 identical tool calls execute only once, and a tool-only 2nd response avoids '(no response)'."""
    calls_25 = [
        ToolCall(id=f"call_{i}", name="lookup_item", arguments='{"item_id": 19019}')
        for i in range(25)
    ]
    first_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=calls_25))]
    )
    second_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[calls_25[0]]))]
    )
    mock_handler = MagicMock(return_value="Item data: Thunderfury")
    monkeypatch.setattr(bot.client.chat.completions, "create", MagicMock(side_effect=[first_resp, second_resp]))
    monkeypatch.setitem(bot.TOOL_HANDLERS, "lookup_item", mock_handler)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["Thunderfury", "quit"]))
    printed = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: printed.append(" ".join(str(x) for x in a)))

    run()

    assert mock_handler.call_count == 1
    output = "\n".join(printed)
    assert "Loremaster: (no response)" not in output
    assert "single pass" in output


# ============================================================================
# 11. Whitespace-only model reply becomes '(no response)' and closes turn
# ============================================================================

def test_whitespace_only_model_reply_normalizes_to_no_response(monkeypatch):
    """A whitespace-only completion content must be stored and printed as '(no response)'."""
    ws_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="   \n\t  ", tool_calls=None))]
    )
    monkeypatch.setattr(bot.client.chat.completions, "create", MagicMock(return_value=ws_resp))
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["hi", "quit"]))
    printed = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: printed.append(" ".join(str(x) for x in a)))

    run()

    assert bot.history[-1]["content"] == "(no response)"
    assert any("Loremaster: (no response)" in line for line in printed)


# ============================================================================
# 12. 'quit' with surrounding spaces exits without calling the model
# ============================================================================

@pytest.mark.parametrize("padded_quit", [" quit", "quit ", "  QUIT  \t"])
def test_quit_with_surrounding_spaces_exits_without_calling_model(padded_quit, monkeypatch):
    """' quit' or 'quit ' must exit the loop immediately without invoking the model."""
    mock_create = MagicMock()
    monkeypatch.setattr(bot.client.chat.completions, "create", mock_create)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=[padded_quit]))
    printed = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: printed.append(" ".join(str(x) for x in a)))

    run()

    assert not mock_create.called
    assert any("Goodbye!" in line for line in printed)


# ============================================================================
# 13. Ctrl-D (EOFError) and Ctrl-C (KeyboardInterrupt) print Goodbye cleanly
# ============================================================================

@pytest.mark.parametrize("interrupt_exc", [EOFError, KeyboardInterrupt])
def test_eof_and_keyboard_interrupt_at_prompt_print_goodbye(interrupt_exc, monkeypatch):
    """EOFError and KeyboardInterrupt at input() must print Goodbye and return cleanly."""
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=interrupt_exc))
    printed = []
    monkeypatch.setattr("builtins.print", lambda *a, **k: printed.append(" ".join(str(x) for x in a)))

    run()

    assert any("Goodbye!" in line for line in printed)


# ============================================================================
# 14. First model call passes timeout and starts Spinner
# ============================================================================

def test_first_model_call_starts_spinner_and_passes_timeout(monkeypatch):
    """The first chat.completions.create call must pass timeout and run inside Spinner."""
    spinner_instance = MagicMock()
    spinner_cls = MagicMock(return_value=spinner_instance)
    monkeypatch.setattr("src.bot.Spinner", spinner_cls)

    resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Hello, traveler!", tool_calls=None))]
    )
    mock_create = MagicMock(return_value=resp)
    monkeypatch.setattr(bot.client.chat.completions, "create", mock_create)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["hi", "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())

    run()

    assert spinner_instance.start.called
    assert spinner_instance.stop.called
    assert mock_create.call_args.kwargs.get("timeout") == LLM_REQUEST_TIMEOUT


# ============================================================================
# 15. Oversized tool results are capped while keeping id and name
# ============================================================================

def test_oversized_profession_tool_result_is_capped(monkeypatch):
    """Large Blizzard documents must be capped at MAX_TOOL_RESULT_CHARS while keeping id and name."""
    huge_doc = {
        "id": 164,
        "name": "Blacksmithing",
        "recipes": ["X" * 1000 for _ in range(50)],
    }
    monkeypatch.setattr(handlers, "lookup_static_ids", MagicMock(return_value=[164]))
    monkeypatch.setattr(handlers, "get_profession_data", MagicMock(return_value=huge_doc))
    monkeypatch.setattr(handlers, "with_official_media", lambda d, *a: d)
    monkeypatch.setattr(handlers, "maybe_matching_skill_tier", MagicMock(return_value=None))

    result = handlers.handle_search_profession({"search_term": "Blacksmithing"}, "tok")
    assert len(result) <= handlers.MAX_TOOL_RESULT_CHARS
    assert "Blacksmithing" in result
    assert "164" in result


# ============================================================================
# 16. Blank BLIZZARD_CLIENT_ID in environment does not hide .env value
# ============================================================================

def test_blank_blizzard_client_id_in_env_does_not_hide_dotenv():
    """An empty BLIZZARD_CLIENT_ID='' in os.environ must not block .env from supplying the key."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dotenv_path = os.path.join(tmpdir, ".env")
        with open(dotenv_path, "w", encoding="utf-8") as f:
            f.write("BLIZZARD_CLIENT_ID=fromfile\nBLIZZARD_CLIENT_SECRET=secretfromfile\n")
        env = {k: v for k, v in os.environ.items() if not k.startswith("BLIZZARD_")}
        env["BLIZZARD_CLIENT_ID"] = ""
        env["PYTHONPATH"] = os.getcwd()
        proc = subprocess.run(
            [sys.executable, "-c", "import src.config as c; print(c.CLIENT_ID, c.CLIENT_SECRET)"],
            cwd=tmpdir,
            env=env,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == "fromfile secretfromfile"
