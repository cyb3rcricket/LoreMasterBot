# Tool-call handlers and dispatcher mapping for LoreMasterBot.
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


def handle_search_creature(function_args, access_token):
    if not access_token:
        return "The Blizzard API is currently unavailable, so I cannot look up creature information."
    search_term = function_args.get("search_term")
    creature_id = search_blizzard(search_term, "creature", access_token)
    if creature_id:
        creature_data = get_creature_data(creature_id, access_token)
        return f"Creature data received: {creature_data}" if creature_data else "No creature data found."
    else:
        return f"Could not find creature '{search_term}'."


def handle_lookup_item(function_args, access_token):
    if not access_token:
        return "The Blizzard API is currently unavailable, so I cannot look up item information."
    item_id = function_args.get("item_id")
    item_data = get_item_data(item_id, access_token)
    return f"Item data received: {item_data}" if item_data else f"No data for item ID {item_id}."


def handle_search_item_by_name(function_args, access_token):
    if not access_token:
        return "The Blizzard API is currently unavailable, so I cannot look up item information."
    search_term = function_args.get("search_term")
    item_id = search_blizzard(search_term, "item", access_token)
    if item_id:
        item_data = get_item_data(item_id, access_token)
        return f"Item data received: {item_data}" if item_data else f"No data for item '{search_term}'."
    else:
        return f"Could not find item named '{search_term}'."


def handle_search_quest_by_name(function_args, access_token):
    if not access_token:
        return "The Blizzard API is currently unavailable, so I cannot look up quest information."
    search_term = function_args.get("search_term")
    quest_id = search_blizzard(search_term, "quest", access_token)
    if quest_id:
        quest_data = get_quest_data(quest_id, access_token)
        return f"Quest data received: {quest_data}" if quest_data else f"No data for quest '{search_term}'."
    else:
        return f"Could not find quest named '{search_term}'."


def handle_search_mount_by_name(function_args, access_token):
    if not access_token:
        return "The Blizzard API is currently unavailable, so I cannot look up mount information."
    search_term = function_args.get("search_term")
    mount_id = search_blizzard(search_term, "mount", access_token)
    if mount_id:
        mount_data = get_mount_data(mount_id, access_token)
        return f"Mount data received: {mount_data}" if mount_data else f"No data for mount '{search_term}'."
    else:
        return f"Could not find mount named '{search_term}'."


def handle_search_achievement_by_name(function_args, access_token):
    if not access_token:
        return "The Blizzard API is currently unavailable, so I cannot look up achievement information."
    search_term = function_args.get("search_term")
    achievement_id = search_blizzard(search_term, "achievement", access_token)
    if achievement_id:
        achievement_data = get_achievement_data(achievement_id, access_token)
        return f"Achievement data received: {achievement_data}" if achievement_data else f"No data for achievement '{search_term}'."
    else:
        return f"Could not find achievement named '{search_term}'."


def handle_search_spell_by_name(function_args, access_token):
    if not access_token:
        return "The Blizzard API is currently unavailable, so I cannot look up spell information."
    search_term = function_args.get("search_term")
    spell_id = search_blizzard(search_term, "spell", access_token)
    if spell_id:
        spell_data = get_spell_data(spell_id, access_token)
        return f"Spell data received: {spell_data}" if spell_data else f"No data for spell '{search_term}'."
    else:
        return f"Could not find spell named '{search_term}'."


def handle_search_journal_instance_by_name(function_args, access_token):
    if not access_token:
        return "The Blizzard API is currently unavailable, so I cannot look up journal instance information."
    search_term = function_args.get("search_term")
    instance_id = search_blizzard(search_term, "journal-instance", access_token)
    if instance_id:
        instance_data = get_journal_instance_data(instance_id, access_token)
        return f"Journal instance data received: {instance_data}" if instance_data else f"No data for journal instance '{search_term}'."
    else:
        return f"Could not find journal instance named '{search_term}'."


def handle_search_faction_by_name(function_args, access_token):
    if not access_token:
        return "The Blizzard API is currently unavailable, so I cannot look up faction information."
    search_term = function_args.get("search_term")
    faction_id = search_blizzard(search_term, "reputation-faction", access_token)
    if faction_id:
        faction_data = get_reputation_faction_data(faction_id, access_token)
        return f"Faction data received: {faction_data}" if faction_data else f"No data for faction '{search_term}'."
    else:
        return f"Could not find faction named '{search_term}'."


def handle_search_title_by_name(function_args, access_token):
    if not access_token:
        return "The Blizzard API is currently unavailable, so I cannot look up title information."
    search_term = function_args.get("search_term")
    title_id = search_blizzard(search_term, "title", access_token)
    if title_id:
        title_data = get_title_data(title_id, access_token)
        return f"Title data received: {title_data}" if title_data else f"No data for title '{search_term}'."
    else:
        return f"Could not find title named '{search_term}'."


def handle_search_toy_by_name(function_args, access_token):
    if not access_token:
        return "The Blizzard API is currently unavailable, so I cannot look up toy information."
    search_term = function_args.get("search_term")
    toy_id = search_blizzard(search_term, "toy", access_token)
    if toy_id:
        toy_data = get_toy_data(toy_id, access_token)
        return f"Toy data received: {toy_data}" if toy_data else f"No data for toy '{search_term}'."
    else:
        return f"Could not find toy named '{search_term}'."


def handle_search_pet_by_name(function_args, access_token):
    if not access_token:
        return "The Blizzard API is currently unavailable, so I cannot look up pet information."
    search_term = function_args.get("search_term")
    pet_id = search_blizzard(search_term, "pet", access_token)
    if pet_id:
        pet_data = get_pet_data(pet_id, access_token)
        return f"Pet data received: {pet_data}" if pet_data else f"No data for pet '{search_term}'."
    else:
        return f"Could not find pet named '{search_term}'."


def handle_search_heirloom_by_name(function_args, access_token):
    if not access_token:
        return "The Blizzard API is currently unavailable, so I cannot look up heirloom information."
    search_term = function_args.get("search_term")
    heirloom_id = search_blizzard(search_term, "heirloom", access_token)
    if heirloom_id:
        heirloom_data = get_heirloom_data(heirloom_id, access_token)
        return f"Heirloom data received: {heirloom_data}" if heirloom_data else f"No data for heirloom '{search_term}'."
    else:
        return f"Could not find heirloom named '{search_term}'."


def handle_get_wow_token_price(function_args, access_token):
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