"""Turn a model's tool request into a text result.

A handler is a Python function the chat loop runs when the model names a
tool. Handlers never print the Loremaster's spoken reply. They return a
string. That string is stored as a tool message, then the model writes the
user-facing answer from it.

TOOL_HANDLERS is the dispatcher: tool name → function. The chat loop looks
up the name and calls the function with (arguments_dict, access_token).
"""
from src.api.blizzard import (
    get_achievement_data,
    get_creature_data,
    get_heirloom_data,
    get_item_data,
    get_journal_instance_data,
    get_mount_data,
    get_pet_data,
    get_quest_data,
    get_reputation_faction_data,
    get_spell_data,
    get_title_data,
    get_toy_data,
    get_wow_token_price,
    search_blizzard,
)


# Shared ending of the not-found message. The wording is strict on purpose:
# a small local model will invent lore unless the tool result forbids it.
_NOT_FOUND_SUFFIX = (
    "in the Blizzard API. You MUST tell the user that this exact entity could not be found "
    "in official records. You MUST NOT invent, fabricate, guess, or add any lore, stats, or "
    "story details from your own knowledge. Just admit we don't have the data and offer to "
    "talk about something else in Azeroth."
)


def _not_found(term, *, as_item_id=False):
    """Build the official not-found tool result for a name or numeric item ID."""
    label = f"item ID '{term}'" if as_item_id else f"'{term}'"
    return f"TOOL RESULT: NO OFFICIAL DATA FOUND for {label} {_NOT_FOUND_SUFFIX}"


def _unavailable(noun):
    """Tell the model the Blizzard login or network is down."""
    return f"The Blizzard API is currently unavailable, so I cannot look up {noun} information."


def _search_and_fetch(function_args, access_token, entity_type, fetch_fn, result_label, noun):
    """Shared path for name search → ID fetch → success or not-found text.

    Most tools do the same four steps. Keeping them here avoids twelve copies
    drifting apart. lookup_item and get_wow_token_price stay separate because
    they do not follow this search-by-name pattern.
    """
    if not access_token:
        return _unavailable(noun)
    search_term = function_args.get("search_term")
    entity_id = search_blizzard(search_term, entity_type, access_token)
    if not entity_id:
        return _not_found(search_term)
    data = fetch_fn(entity_id, access_token)
    return f"{result_label} data received: {data}" if data else _not_found(search_term)


def handle_search_creature(function_args, access_token):
    return _search_and_fetch(function_args, access_token, "creature", get_creature_data, "Creature", "creature")


def handle_lookup_item(function_args, access_token):
    """Look up one item by numeric ID only.

    Separate from search_item_by_name so a name like Thunderfury is never
    sent to the item-by-ID URL. Non-numeric values must not call the API.
    """
    if not access_token:
        return _unavailable("item")
    if not isinstance(function_args, dict):
        return _not_found("None", as_item_id=True)
    item_id = function_args.get("item_id")
    if item_id is None or not str(item_id).strip() or not str(item_id).strip().isdigit():
        return _not_found(item_id, as_item_id=True)
    item_data = get_item_data(item_id, access_token)
    return f"Item data received: {item_data}" if item_data else _not_found(item_id, as_item_id=True)


def handle_search_item_by_name(function_args, access_token):
    """Look up an item by display name, never by numeric ID."""
    if not access_token:
        return _unavailable("item")
    if not isinstance(function_args, dict):
        return _not_found("None")
    search_term = function_args.get("search_term")
    if not search_term or not isinstance(search_term, str) or not search_term.strip():
        return _not_found(search_term)
    return _search_and_fetch(function_args, access_token, "item", get_item_data, "Item", "item")


def handle_search_quest_by_name(function_args, access_token):
    return _search_and_fetch(function_args, access_token, "quest", get_quest_data, "Quest", "quest")


def handle_search_mount_by_name(function_args, access_token):
    return _search_and_fetch(function_args, access_token, "mount", get_mount_data, "Mount", "mount")


def handle_search_achievement_by_name(function_args, access_token):
    return _search_and_fetch(function_args, access_token, "achievement", get_achievement_data, "Achievement", "achievement")


def handle_search_spell_by_name(function_args, access_token):
    return _search_and_fetch(function_args, access_token, "spell", get_spell_data, "Spell", "spell")


def handle_search_journal_instance_by_name(function_args, access_token):
    return _search_and_fetch(function_args, access_token, "journal-instance", get_journal_instance_data, "Journal instance", "journal instance")


def handle_search_faction_by_name(function_args, access_token):
    return _search_and_fetch(function_args, access_token, "reputation-faction", get_reputation_faction_data, "Faction", "faction")


def handle_search_title_by_name(function_args, access_token):
    return _search_and_fetch(function_args, access_token, "title", get_title_data, "Title", "title")


def handle_search_toy_by_name(function_args, access_token):
    return _search_and_fetch(function_args, access_token, "toy", get_toy_data, "Toy", "toy")


def handle_search_pet_by_name(function_args, access_token):
    return _search_and_fetch(function_args, access_token, "pet", get_pet_data, "Pet", "pet")


def handle_search_heirloom_by_name(function_args, access_token):
    return _search_and_fetch(function_args, access_token, "heirloom", get_heirloom_data, "Heirloom", "heirloom")


def handle_get_wow_token_price(function_args, access_token):
    """Return the current token price in gold, or a short failure string."""
    if not access_token:
        return "The Blizzard API is currently unavailable, so I cannot look up the WoW Token price."
    token_data = get_wow_token_price(access_token)
    if token_data and "price" in token_data:
        return f"WoW Token price received: Current price is {token_data['price']:,} gold."
    else:
        return "Could not retrieve current WoW Token price."


# TOOL_HANDLERS dictionary: maps tool names to handler functions
TOOL_HANDLERS = {
    "search_creature": handle_search_creature,
    "lookup_item": handle_lookup_item,
    "search_item_by_name": handle_search_item_by_name,
    "search_quest_by_name": handle_search_quest_by_name,
    "search_mount_by_name": handle_search_mount_by_name,
    "search_achievement_by_name": handle_search_achievement_by_name,
    "search_spell_by_name": handle_search_spell_by_name,
    "search_journal_instance_by_name": handle_search_journal_instance_by_name,
    "search_faction_by_name": handle_search_faction_by_name,
    "search_title_by_name": handle_search_title_by_name,
    "search_toy_by_name": handle_search_toy_by_name,
    "search_pet_by_name": handle_search_pet_by_name,
    "search_heirloom_by_name": handle_search_heirloom_by_name,
    "get_wow_token_price": handle_get_wow_token_price,
}
