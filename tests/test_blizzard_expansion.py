"""Regression tests for the official Blizzard Game Data expansion batch.

These tests mock HTTP. They must not contact Blizzard, Gemini, or Ollama.
They cover new tool schemas, handlers, API paths, caching, failures, and
mocked routing for representative natural-language questions.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

import src.api.blizzard as blizzard
import src.bot as bot
from src.bot import ToolCall, run
from src.config import SYSTEM_PROMPT
from src.tools import handlers
from src.tools.handlers import TOOL_HANDLERS
from src.tools.schemas import TOOL_SCHEMAS


EXISTING_TOOL_NAMES = (
    "search_creature",
    "lookup_item",
    "search_item_by_name",
    "search_quest_by_name",
    "search_mount_by_name",
    "search_achievement_by_name",
    "search_spell_by_name",
    "search_journal_instance_by_name",
    "search_faction_by_name",
    "search_title_by_name",
    "search_toy_by_name",
    "search_pet_by_name",
    "search_heirloom_by_name",
    "get_wow_token_price",
)

NEW_TOOL_NAMES = (
    "search_journal_encounter",
    "search_journal_expansion",
    "search_playable_race",
    "search_playable_class",
    "search_specialization",
    "search_profession",
    "search_item_set",
    "search_reputation_tiers",
    "search_creature_family",
    "search_quest_group",
)

EXISTING_GETTERS = (
    (blizzard.get_item_data, 19019, "/data/wow/item/19019"),
    (blizzard.get_creature_data, 123, "/data/wow/creature/123"),
    (blizzard.get_quest_data, 1, "/data/wow/quest/1"),
    (blizzard.get_mount_data, 2, "/data/wow/mount/2"),
    (blizzard.get_achievement_data, 3, "/data/wow/achievement/3"),
    (blizzard.get_spell_data, 4, "/data/wow/spell/4"),
    (blizzard.get_journal_instance_data, 5, "/data/wow/journal-instance/5"),
    (blizzard.get_reputation_faction_data, 6, "/data/wow/reputation-faction/6"),
    (blizzard.get_title_data, 7, "/data/wow/title/7"),
    (blizzard.get_toy_data, 8, "/data/wow/toy/8"),
    (blizzard.get_pet_data, 9, "/data/wow/pet/9"),
    (blizzard.get_heirloom_data, 10, "/data/wow/heirloom/10"),
)


@pytest.fixture(autouse=True)
def reset_test_state(monkeypatch):
    """Isolate caches, history, and network from every test."""
    bot.history.clear()
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
    blizzard.search_cache.clear()
    blizzard.data_cache.clear()
    blizzard.wow_token_cache["data"] = None
    blizzard.wow_token_cache["timestamp"] = 0.0


def _schema(name):
    return next(item["function"] for item in TOOL_SCHEMAS if item["function"]["name"] == name)


def _json_response(payload, status=200):
    mock_response = MagicMock()
    mock_response.status_code = status
    mock_response.json.return_value = payload
    if status == 200:
        mock_response.raise_for_status = MagicMock()
    else:
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("HTTP error")
    return mock_response


def _route_get(routes):
    """Return a requests.get stand-in that matches URL substrings to payloads."""

    def fake_get(url, **kwargs):
        for suffix, payload in routes:
            if suffix in url:
                if isinstance(payload, Exception):
                    raise payload
                if payload == "malformed":
                    response = _json_response({})
                    response.json.side_effect = ValueError("No JSON")
                    return response
                if isinstance(payload, tuple):
                    body, status = payload
                    return _json_response(body, status=status)
                return _json_response(payload)
        raise AssertionError(f"Unexpected URL: {url}")

    return fake_get


def _run_tool_turn(monkeypatch, tool_call, prompt):
    first_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[tool_call]))]
    )
    second_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Official records only.", tool_calls=None))]
    )
    mock_create = MagicMock(side_effect=[first_resp, second_resp])
    monkeypatch.setattr(bot.client.chat.completions, "create", mock_create)
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=[prompt, "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())
    run()
    return mock_create


# ============================================================================
# Tool schemas
# ============================================================================

def test_new_and_existing_tool_names_are_registered():
    """Every expected tool is present on both the schema list and handler map."""
    schema_names = [item["function"]["name"] for item in TOOL_SCHEMAS]
    for name in EXISTING_TOOL_NAMES + NEW_TOOL_NAMES:
        assert name in schema_names
        assert name in TOOL_HANDLERS
    assert schema_names == list(dict.fromkeys(schema_names))
    assert set(schema_names) == set(TOOL_HANDLERS)


@pytest.mark.parametrize("name", NEW_TOOL_NAMES)
def test_new_search_tools_require_search_term(name):
    """New model-facing tools take search_term and have a forceful description."""
    schema = _schema(name)
    assert schema["parameters"]["required"] == ["search_term"]
    assert "search_term" in schema["parameters"]["properties"]
    description = schema["description"]
    assert "MUST call this tool" in description
    assert "never answer from memory" in description.lower() or "training data" in description.lower()


def test_search_creature_is_not_a_lore_biography_tool():
    """Creature lookup must not advertise famous-character biographies."""
    schema = _schema("search_creature")
    blob = (schema["description"] + schema["parameters"]["properties"]["search_term"]["description"]).lower()
    assert "arthas" not in blob
    assert "sylvanas" not in blob
    assert "biography" in schema["description"].lower() or "lore-character" in schema["description"].lower()
    example = schema["parameters"]["properties"]["search_term"]["description"]
    assert "Young Nightsaber" in example or "Ragnaros" in example


def test_system_prompt_forbids_biography_from_memory():
    """The model is told Blizzard data cannot fill character biographies."""
    prompt = SYSTEM_PROMPT.lower()
    assert "lore-character biography" in prompt or "lore character biography" in prompt
    assert "does not provide the requested lore biography" in prompt
    assert "search_playable_race" in prompt
    assert "search_journal_encounter" in prompt


# ============================================================================
# Handler contracts
# ============================================================================

def test_handlers_missing_token_are_unavailable():
    """Every new handler must refuse to call Blizzard without a token."""
    args = {"search_term": "Human"}
    for name in NEW_TOOL_NAMES:
        result = TOOL_HANDLERS[name](args, None)
        assert "unavailable" in result.lower()
        assert "BLIZZARD_CLIENT" not in result
        assert "mock_secret" not in result


@pytest.mark.parametrize("name", NEW_TOOL_NAMES)
def test_handlers_malformed_or_empty_arguments(name, monkeypatch):
    """Blank or non-dict arguments must not call the API."""
    monkeypatch.setattr(handlers, "lookup_static_ids", MagicMock(return_value=[1]))
    monkeypatch.setattr(blizzard, "lookup_static_ids", MagicMock(return_value=[1]))
    monkeypatch.setattr(blizzard, "find_reputation_tiers", MagicMock(return_value={"id": 1}))
    monkeypatch.setattr(handlers, "find_reputation_tiers", MagicMock(return_value={"id": 1}))

    empty = TOOL_HANDLERS[name]({}, "token")
    assert "NO OFFICIAL DATA FOUND" in empty

    malformed = TOOL_HANDLERS[name](["Human"], "token")
    assert "NO OFFICIAL DATA FOUND" in malformed


def test_handle_playable_race_success_and_not_found(monkeypatch):
    monkeypatch.setattr(handlers, "lookup_static_ids", MagicMock(return_value=[1]))
    monkeypatch.setattr(handlers, "get_playable_race_data", MagicMock(return_value={"id": 1, "name": "Human"}))

    result = handlers.handle_search_playable_race({"search_term": "Human"}, "token")
    assert "Playable race data received" in result
    assert "Human" in result
    handlers.get_playable_race_data.assert_called_once_with(1, "token")

    handlers.lookup_static_ids.return_value = []
    missing = handlers.handle_search_playable_race({"search_term": "Not A Race"}, "token")
    assert "NO OFFICIAL DATA FOUND" in missing


def test_handle_playable_class_attaches_media(monkeypatch):
    monkeypatch.setattr(handlers, "lookup_static_ids", MagicMock(return_value=[6]))
    monkeypatch.setattr(
        handlers,
        "get_playable_class_data",
        MagicMock(return_value={"id": 6, "name": "Death Knight"}),
    )
    monkeypatch.setattr(
        handlers,
        "with_official_media",
        MagicMock(return_value={"id": 6, "name": "Death Knight", "official_media": {"assets": []}}),
    )

    result = handlers.handle_search_playable_class({"search_term": "Death Knight"}, "token")
    assert "Death Knight" in result
    handlers.with_official_media.assert_called_once_with(
        {"id": 6, "name": "Death Knight"}, "playable-class", 6, "token"
    )


def test_handle_specialization_returns_multiple_frost_matches(monkeypatch):
    monkeypatch.setattr(handlers, "lookup_static_ids", MagicMock(return_value=[251, 64]))
    monkeypatch.setattr(
        handlers,
        "get_playable_specialization_data",
        MagicMock(side_effect=[
            {"id": 251, "name": "Frost", "playable_class": {"name": "Death Knight"}},
            {"id": 64, "name": "Frost", "playable_class": {"name": "Mage"}},
        ]),
    )
    monkeypatch.setattr(handlers, "with_official_media", lambda data, *args: data)

    result = handlers.handle_search_specialization({"search_term": "Frost"}, "token")
    assert "2 matches" in result
    assert "Death Knight" in result
    assert "Mage" in result


def test_handle_journal_encounter_dispatches_to_encounter_lookup(monkeypatch):
    resolver = MagicMock(return_value=[1103])
    monkeypatch.setattr(handlers, "lookup_journal_encounter_ids", resolver)
    monkeypatch.setattr(
        handlers,
        "get_journal_encounter_data",
        MagicMock(return_value={"id": 1103, "name": "Professor Putricide", "instance": {"name": "Icecrown Citadel"}}),
    )

    result = handlers.handle_search_journal_encounter({"search_term": "Professor Putricide"}, "token")
    assert "Professor Putricide" in result
    assert "Icecrown Citadel" in result
    resolver.assert_called_once_with("Professor Putricide", "token")


def test_handle_profession_success_and_missing_token(monkeypatch):
    monkeypatch.setattr(handlers, "lookup_static_ids", MagicMock(return_value=[164]))
    monkeypatch.setattr(
        handlers,
        "get_profession_data",
        MagicMock(return_value={"id": 164, "name": "Blacksmithing", "skill_tiers": [{"id": 1, "name": "Classic Blacksmithing"}]}),
    )
    monkeypatch.setattr(handlers, "with_official_media", lambda data, *args: data)
    monkeypatch.setattr(handlers, "maybe_matching_skill_tier", MagicMock(return_value=None))

    result = handlers.handle_search_profession({"search_term": "Blacksmithing"}, "token")
    assert "Blacksmithing" in result
    assert handlers.maybe_matching_skill_tier.called

    unavailable = handlers.handle_search_profession({"search_term": "Blacksmithing"}, None)
    assert "unavailable" in unavailable.lower()


def test_handle_item_set_and_reputation_tiers(monkeypatch):
    monkeypatch.setattr(handlers, "lookup_static_ids", MagicMock(return_value=[202]))
    monkeypatch.setattr(
        handlers,
        "get_item_set_data",
        MagicMock(return_value={"id": 202, "name": "Judgement Armor", "items": [{"name": "Judgement Belt"}]}),
    )
    item_set = handlers.handle_search_item_set({"search_term": "Judgement Armor"}, "token")
    assert "Judgement Armor" in item_set

    monkeypatch.setattr(
        handlers,
        "find_reputation_tiers",
        MagicMock(return_value={"standard_standings": {"tiers": [{"name": "Exalted"}]}}),
    )
    tiers = handlers.handle_search_reputation_tiers({"search_term": "reputation levels"}, "token")
    assert "Exalted" in tiers
    handlers.find_reputation_tiers.return_value = None
    missing = handlers.handle_search_reputation_tiers({"search_term": "unknown"}, "token")
    assert "NO OFFICIAL DATA FOUND" in missing


def test_handle_creature_family_and_quest_group(monkeypatch):
    monkeypatch.setattr(handlers, "lookup_static_ids", MagicMock(side_effect=[[1], []]))
    monkeypatch.setattr(handlers, "get_creature_family_data", MagicMock(return_value={"id": 1, "name": "Wolf"}))
    monkeypatch.setattr(handlers, "get_creature_type_data", MagicMock())
    monkeypatch.setattr(handlers, "with_official_media", lambda data, *args: data)

    family = handlers.handle_search_creature_family({"search_term": "Wolf"}, "token")
    assert "Wolf" in family
    assert not handlers.get_creature_type_data.called

    monkeypatch.setattr(handlers, "lookup_static_ids", MagicMock(side_effect=[[12], [], []]))
    monkeypatch.setattr(handlers, "get_quest_area_data", MagicMock(return_value={"id": 12, "name": "Elwynn Forest"}))
    area = handlers.handle_search_quest_group({"search_term": "Elwynn Forest"}, "token")
    assert "Quest area data received" in area
    assert "Elwynn Forest" in area


# ============================================================================
# API layer
# ============================================================================

@pytest.mark.parametrize("getter,entity_id,path_fragment", EXISTING_GETTERS)
def test_existing_entity_getters_keep_official_paths(getter, entity_id, path_fragment, monkeypatch):
    """Previously working entity fetches must keep their paths and static namespace."""
    mock_get = MagicMock(return_value=_json_response({"id": entity_id, "name": "ok"}))
    monkeypatch.setattr("requests.get", mock_get)

    result = getter(entity_id, "token")
    assert result["name"] == "ok"
    url = mock_get.call_args.args[0]
    assert path_fragment in url
    assert mock_get.call_args.kwargs["params"]["namespace"] == "static-us"
    assert mock_get.call_args.kwargs["params"]["locale"] == "en_US"
    assert mock_get.call_args.kwargs["timeout"] == blizzard.BLIZZARD_API_TIMEOUT


def test_playable_race_index_then_detail_and_cache(monkeypatch):
    index = {"races": [{"id": 1, "name": "Human"}, {"id": 2, "name": "Orc"}]}
    detail = {"id": 1, "name": "Human", "faction": {"name": "Alliance"}}
    mock_get = MagicMock(side_effect=[_json_response(index), _json_response(detail)])
    monkeypatch.setattr("requests.get", mock_get)

    ids = blizzard.lookup_static_ids("Human", "playable-race", "token")
    assert ids == [1]
    data = blizzard.get_playable_race_data(1, "token")
    assert data["name"] == "Human"

    first_url = mock_get.call_args_list[0].args[0]
    second_url = mock_get.call_args_list[1].args[0]
    assert first_url.endswith("/data/wow/playable-race/index")
    assert second_url.endswith("/data/wow/playable-race/1")
    for call in mock_get.call_args_list:
        assert call.kwargs["params"]["namespace"] == "static-us"
        assert call.kwargs["params"]["locale"] == "en_US"
        assert call.kwargs["timeout"] == blizzard.BLIZZARD_API_TIMEOUT

    assert blizzard.lookup_static_ids("Human", "playable-race", "token") == [1]
    assert blizzard.get_playable_race_data(1, "token") == data
    assert mock_get.call_count == 2


def test_lookup_static_ids_plural_and_contained_name(monkeypatch):
    class_index = {"classes": [{"id": 6, "name": "Death Knight"}, {"id": 1, "name": "Warrior"}]}
    monkeypatch.setattr("requests.get", MagicMock(return_value=_json_response(class_index)))
    assert blizzard.lookup_static_ids("Death Knights", "playable-class", "token") == [6]

    blizzard.search_cache.clear()
    blizzard.data_cache.clear()
    race_index = {"races": [{"id": 1, "name": "Human"}]}
    monkeypatch.setattr("requests.get", MagicMock(return_value=_json_response(race_index)))
    assert blizzard.lookup_static_ids("the Human race", "playable-race", "token") == [1]


def test_journal_encounter_search_then_detail(monkeypatch):
    search_payload = {
        "results": [
            {"data": {"id": 1103, "name": {"en_US": "Professor Putricide"}}},
        ]
    }
    detail = {"id": 1103, "name": "Professor Putricide", "instance": {"name": "Icecrown Citadel"}}
    mock_get = MagicMock(side_effect=[_json_response(search_payload), _json_response(detail)])
    monkeypatch.setattr("requests.get", mock_get)

    ids = blizzard.lookup_journal_encounter_ids("Professor Putricide", "token")
    assert ids == [1103]
    data = blizzard.get_journal_encounter_data(1103, "token")
    assert data["instance"]["name"] == "Icecrown Citadel"
    assert "/data/wow/search/journal-encounter" in mock_get.call_args_list[0].args[0]
    assert mock_get.call_args_list[0].kwargs["params"]["namespace"] == "static-us"
    assert mock_get.call_args_list[1].args[0].endswith("/data/wow/journal-encounter/1103")


def test_journal_encounter_falls_back_to_index_when_search_fails(monkeypatch):
    index = {"encounters": [{"id": 1103, "name": "Professor Putricide"}]}
    mock_get = MagicMock(side_effect=[
        requests.exceptions.HTTPError("404"),
        requests.exceptions.HTTPError("404"),
        _json_response(index),
    ])
    monkeypatch.setattr("requests.get", mock_get)

    ids = blizzard.lookup_journal_encounter_ids("Professor Putricide", "token")
    assert ids == [1103]
    assert any("/journal-encounter/index" in call.args[0] for call in mock_get.call_args_list)


def test_new_static_endpoints_use_timeout_and_fail_safely(monkeypatch):
    mock_get = MagicMock(side_effect=requests.exceptions.Timeout("timed out"))
    monkeypatch.setattr("requests.get", mock_get)

    assert blizzard.get_index_data("playable-race", "token") is None
    assert blizzard.get_playable_class_data(6, "token") is None
    assert blizzard.get_profession_skill_tier_data(164, 2477, "token") is None
    assert blizzard.get_entity_media("playable-class", 6, "token") is None
    assert blizzard.get_item_set_data(202, "token") is None
    for call in mock_get.call_args_list:
        assert call.kwargs["timeout"] == blizzard.BLIZZARD_API_TIMEOUT


def test_index_http_error_and_malformed_json(monkeypatch):
    monkeypatch.setattr("requests.get", MagicMock(return_value=_json_response({}, status=500)))
    assert blizzard.get_index_data("item-set", "token") is None

    monkeypatch.setattr("requests.get", _route_get([("/playable-race/index", "malformed")]))
    assert blizzard.get_index_data("playable-race", "token") is None

    monkeypatch.setattr("requests.get", MagicMock(return_value=_json_response(["not", "an", "object"])))
    assert blizzard.get_index_data("playable-class", "token") is None


def test_media_is_attached_without_mutating_cache_or_downloading(monkeypatch):
    class_data = {"id": 6, "name": "Death Knight"}
    media = {"assets": [{"key": "icon", "value": "https://render.worldofwarcraft.com/icon.png"}]}
    mock_get = MagicMock(side_effect=[_json_response(class_data), _json_response(media)])
    monkeypatch.setattr("requests.get", mock_get)

    fetched = blizzard.get_playable_class_data(6, "token")
    combined = blizzard.with_official_media(fetched, "playable-class", 6, "token")
    assert combined["official_media"]["assets"][0]["value"].startswith("https://")
    assert "official_media" not in fetched
    assert "/data/wow/media/playable-class/6" in mock_get.call_args_list[1].args[0]
    assert mock_get.call_count == 2


def test_media_failure_does_not_hide_entity(monkeypatch):
    class_data = {"id": 6, "name": "Death Knight"}
    mock_get = MagicMock(side_effect=[_json_response(class_data), _json_response({}, status=404)])
    monkeypatch.setattr("requests.get", mock_get)

    fetched = blizzard.get_playable_class_data(6, "token")
    combined = blizzard.with_official_media(fetched, "playable-class", 6, "token")
    assert combined == fetched
    assert "official_media" not in combined


def test_profession_skill_tier_path_and_optional_recipe_fetch(monkeypatch):
    payload = {"id": 2477, "name": "Classic Blacksmithing", "categories": []}
    mock_get = MagicMock(return_value=_json_response(payload))
    monkeypatch.setattr("requests.get", mock_get)

    data = blizzard.get_profession_skill_tier_data(164, 2477, "token")
    assert data["name"] == "Classic Blacksmithing"
    assert mock_get.call_args.args[0].endswith("/data/wow/profession/164/skill-tier/2477")
    assert mock_get.call_args.kwargs["params"]["namespace"] == "static-us"

    profession = {"id": 164, "name": "Blacksmithing", "skill_tiers": [{"id": 2477, "name": "Classic Blacksmithing"}]}
    matched = blizzard.maybe_matching_skill_tier(profession, "Classic Blacksmithing", "token")
    assert matched["name"] == "Classic Blacksmithing"
    assert blizzard.maybe_matching_skill_tier(profession, "Blacksmithing", "token") is None


def test_reputation_tiers_overview_and_named_standing(monkeypatch):
    index = {"reputation_tiers": [{"id": 2}, {"id": 201}]}
    classic = {
        "id": 2,
        "faction": {"name": "Classic"},
        "tiers": [{"name": "Hated"}, {"name": "Exalted"}],
    }
    other = {
        "id": 201,
        "faction": {"name": "Renown"},
        "tiers": [{"name": "Renown 1"}, {"name": "Renown 40"}],
    }
    mock_get = MagicMock(side_effect=[
        _json_response(index),
        _json_response(classic),
        _json_response(other),
    ])
    monkeypatch.setattr("requests.get", mock_get)

    overview = blizzard.find_reputation_tiers("reputation levels", "token")
    assert overview["standard_standings"]["id"] == 2
    assert any(item.get("faction") == "Renown" for item in overview["other_reputation_systems"])
    assert mock_get.call_args_list[0].args[0].endswith("/data/wow/reputation-tiers/index")
    assert mock_get.call_args_list[1].args[0].endswith("/data/wow/reputation-tiers/2")

    named = blizzard.find_reputation_tiers("Exalted", "token")
    assert named[0]["id"] == 2
    assert mock_get.call_count == 3


def test_quest_area_category_and_type_paths(monkeypatch):
    mock_get = MagicMock(return_value=_json_response({"id": 1, "name": "ok"}))
    monkeypatch.setattr("requests.get", mock_get)

    blizzard.get_quest_area_data(1, "token")
    assert mock_get.call_args.args[0].endswith("/data/wow/quest/area/1")
    blizzard.get_quest_category_data(2, "token")
    assert mock_get.call_args.args[0].endswith("/data/wow/quest/category/2")
    blizzard.get_quest_type_data(3, "token")
    assert mock_get.call_args.args[0].endswith("/data/wow/quest/type/3")


def test_creature_family_and_type_paths(monkeypatch):
    mock_get = MagicMock(return_value=_json_response({"id": 1, "name": "Wolf"}))
    monkeypatch.setattr("requests.get", mock_get)

    assert blizzard.get_creature_family_data(1, "token")["name"] == "Wolf"
    assert mock_get.call_args.args[0].endswith("/data/wow/creature-family/1")
    blizzard.get_creature_type_data(1, "token")
    assert mock_get.call_args.args[0].endswith("/data/wow/creature-type/1")


def test_journal_expansion_path(monkeypatch):
    mock_get = MagicMock(return_value=_json_response({"id": 396, "name": "Wrath of the Lich King"}))
    monkeypatch.setattr("requests.get", mock_get)
    data = blizzard.get_journal_expansion_data(396, "token")
    assert data["name"] == "Wrath of the Lich King"
    assert mock_get.call_args.args[0].endswith("/data/wow/journal-expansion/396")


def test_empty_search_term_does_not_hit_network(monkeypatch):
    mock_get = MagicMock()
    monkeypatch.setattr("requests.get", mock_get)
    assert blizzard.lookup_static_ids("", "playable-race", "token") == []
    assert blizzard.lookup_static_ids(None, "playable-race", "token") == []
    assert not mock_get.called


# ============================================================================
# Integration-style mocked routing
# ============================================================================

def test_routing_human_race(monkeypatch):
    index = {"races": [{"id": 1, "name": "Human"}]}
    detail = {"id": 1, "name": "Human", "faction": {"name": "Alliance"}}
    monkeypatch.setattr("requests.get", _route_get([
        ("/playable-race/index", index),
        ("/playable-race/1", detail),
    ]))
    call = ToolCall(id="call_race_1", name="search_playable_race", arguments='{"search_term": "Human"}')
    mock_create = _run_tool_turn(monkeypatch, call, "Tell me about the Human race.")

    tool_entry = next(item for item in bot.history if item.get("role") == "tool")
    assert "Playable race data received" in tool_entry["content"]
    assert "Human" in tool_entry["content"]
    assert "Alliance" in tool_entry["content"]
    second_messages = mock_create.call_args_list[1].kwargs["messages"]
    assert any(message.get("role") == "tool" and "Human" in message["content"] for message in second_messages)


def test_routing_death_knights(monkeypatch):
    index = {"classes": [{"id": 6, "name": "Death Knight"}]}
    detail = {"id": 6, "name": "Death Knight", "specializations": [{"name": "Blood"}]}
    media = {"assets": [{"key": "icon", "value": "https://render.worldofwarcraft.com/dk.png"}]}
    monkeypatch.setattr("requests.get", _route_get([
        ("/playable-class/index", index),
        ("/media/playable-class/6", media),
        ("/playable-class/6", detail),
    ]))
    call = ToolCall(id="call_class_1", name="search_playable_class", arguments='{"search_term": "Death Knights"}')
    _run_tool_turn(monkeypatch, call, "Tell me about Death Knights.")
    content = next(item["content"] for item in bot.history if item.get("role") == "tool")
    assert "Death Knight" in content
    assert "https://render.worldofwarcraft.com/dk.png" in content


def test_routing_frost_specialization(monkeypatch):
    index = {"character_specializations": [
        {"id": 251, "name": "Frost"},
        {"id": 64, "name": "Frost"},
    ]}
    frost_dk = {"id": 251, "name": "Frost", "playable_class": {"name": "Death Knight"}}
    frost_mage = {"id": 64, "name": "Frost", "playable_class": {"name": "Mage"}}
    monkeypatch.setattr("requests.get", _route_get([
        ("/playable-specialization/index", index),
        ("/media/playable-specialization/", {"assets": []}),
        ("/playable-specialization/251", frost_dk),
        ("/playable-specialization/64", frost_mage),
    ]))
    call = ToolCall(id="call_spec_1", name="search_specialization", arguments='{"search_term": "Frost"}')
    _run_tool_turn(monkeypatch, call, "What is Frost specialization?")
    content = next(item["content"] for item in bot.history if item.get("role") == "tool")
    assert "Frost" in content
    assert "Death Knight" in content
    assert "Mage" in content


def test_routing_professor_putricide(monkeypatch):
    search_payload = {"results": [{"data": {"id": 1103, "name": {"en_US": "Professor Putricide"}}}]}
    detail = {
        "id": 1103,
        "name": "Professor Putricide",
        "description": "The royal apothecary.",
        "instance": {"id": 271, "name": "Icecrown Citadel"},
    }
    monkeypatch.setattr("requests.get", _route_get([
        ("/search/journal-encounter", search_payload),
        ("/journal-encounter/1103", detail),
    ]))
    call = ToolCall(
        id="call_enc_1",
        name="search_journal_encounter",
        arguments='{"search_term": "Professor Putricide"}',
    )
    _run_tool_turn(monkeypatch, call, "Who is Professor Putricide?")
    content = next(item["content"] for item in bot.history if item.get("role") == "tool")
    assert "Professor Putricide" in content
    assert "Icecrown Citadel" in content


def test_routing_blacksmithing(monkeypatch):
    index = {"professions": [{"id": 164, "name": "Blacksmithing"}]}
    detail = {"id": 164, "name": "Blacksmithing", "skill_tiers": [{"id": 2477, "name": "Classic Blacksmithing"}]}
    monkeypatch.setattr("requests.get", _route_get([
        ("/profession/index", index),
        ("/media/profession/164", {"assets": []}),
        ("/profession/164", detail),
    ]))
    call = ToolCall(id="call_prof_1", name="search_profession", arguments='{"search_term": "Blacksmithing"}')
    _run_tool_turn(monkeypatch, call, "Tell me about Blacksmithing.")
    content = next(item["content"] for item in bot.history if item.get("role") == "tool")
    assert "Blacksmithing" in content
    assert "Classic Blacksmithing" in content


def test_routing_judgement_armor(monkeypatch):
    index = {"item_sets": [{"id": 202, "name": "Judgement Armor"}]}
    detail = {"id": 202, "name": "Judgement Armor", "items": [{"name": "Judgement Belt", "id": 22086}]}
    monkeypatch.setattr("requests.get", _route_get([
        ("/item-set/index", index),
        ("/item-set/202", detail),
    ]))
    call = ToolCall(id="call_set_1", name="search_item_set", arguments='{"search_term": "Judgement Armor"}')
    _run_tool_turn(monkeypatch, call, "What is the Judgement Armor set?")
    content = next(item["content"] for item in bot.history if item.get("role") == "tool")
    assert "Judgement Armor" in content
    assert "Judgement Belt" in content


def test_routing_reputation_levels(monkeypatch):
    index = {"reputation_tiers": [{"id": 2}]}
    classic = {
        "id": 2,
        "tiers": [
            {"name": "Hated"},
            {"name": "Hostile"},
            {"name": "Unfriendly"},
            {"name": "Neutral"},
            {"name": "Friendly"},
            {"name": "Honored"},
            {"name": "Revered"},
            {"name": "Exalted"},
        ],
    }
    monkeypatch.setattr("requests.get", _route_get([
        ("/reputation-tiers/index", index),
        ("/reputation-tiers/2", classic),
    ]))
    call = ToolCall(
        id="call_rep_1",
        name="search_reputation_tiers",
        arguments='{"search_term": "reputation levels"}',
    )
    _run_tool_turn(monkeypatch, call, "What reputation levels are there?")
    content = next(item["content"] for item in bot.history if item.get("role") == "tool")
    assert "Exalted" in content
    assert "Hated" in content


def test_routing_arthas_must_not_become_a_creature_biography(monkeypatch):
    """Arthas is not a creature-biography lookup. Empty Blizzard data must stay empty."""
    monkeypatch.setattr("requests.get", _route_get([
        ("/search/creature", {"results": []}),
    ]))
    call = ToolCall(
        id="call_arthas_1",
        name="search_creature",
        arguments='{"search_term": "Arthas Menethil"}',
    )
    mock_create = _run_tool_turn(monkeypatch, call, "Tell me about Arthas Menethil.")

    tool_entry = next(item for item in bot.history if item.get("role") == "tool")
    assert "NO OFFICIAL DATA FOUND" in tool_entry["content"]
    assert "Menethil" in tool_entry["content"]
    second_messages = mock_create.call_args_list[1].kwargs["messages"]
    tool_messages = [message for message in second_messages if message.get("role") == "tool"]
    assert tool_messages
    assert "NO OFFICIAL DATA FOUND" in tool_messages[0]["content"]
    system = second_messages[0]["content"].lower()
    assert "does not provide the requested lore biography" in system
    assert "arthas" not in _schema("search_creature")["parameters"]["properties"]["search_term"]["description"].lower()


def test_existing_thunderfury_item_lookup_still_routes(monkeypatch):
    monkeypatch.setattr("requests.get", _route_get([
        ("/item/19019", {"id": 19019, "name": "Thunderfury, Blessed Blade of the Windseeker"}),
    ]))
    call = ToolCall(id="call_item_1", name="lookup_item", arguments='{"item_id": "19019"}')
    _run_tool_turn(monkeypatch, call, "What is item 19019?")
    content = next(item["content"] for item in bot.history if item.get("role") == "tool")
    assert "Thunderfury" in content


def test_multi_tool_history_still_serializable_with_new_handlers(monkeypatch):
    """Adding tools must not change the multi-call history protocol."""
    call_1 = ToolCall(id="call_a", name="search_playable_race", arguments='{"search_term": "Human"}')
    call_2 = ToolCall(id="call_b", name="lookup_item", arguments='{"item_id": "19019"}')
    first_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call_1, call_2]))]
    )
    second_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Kept together.", tool_calls=None))]
    )
    monkeypatch.setattr(
        bot.client.chat.completions,
        "create",
        MagicMock(side_effect=[first_resp, second_resp]),
    )
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["Human and Thunderfury", "quit"]))
    monkeypatch.setattr("builtins.print", MagicMock())
    monkeypatch.setitem(bot.TOOL_HANDLERS, "search_playable_race", MagicMock(return_value="Race: Human"))
    monkeypatch.setitem(bot.TOOL_HANDLERS, "lookup_item", MagicMock(return_value="Thunderfury: 19019"))

    run()

    roles = [item["role"] for item in bot.history]
    assert roles == ["user", "assistant", "tool", "tool", "assistant"]
    assistant = next(item for item in bot.history if item.get("role") == "assistant" and "tool_calls" in item)
    assert [entry["id"] for entry in assistant["tool_calls"]] == ["call_a", "call_b"]
    assert json.dumps(bot.history)
