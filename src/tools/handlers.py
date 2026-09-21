"""Turn a model's tool request into a text result.

A handler is a Python function the chat loop runs when the model names a
tool. Handlers never print the Loremaster's spoken reply. They return a
string. That string is stored as a tool message, then the model writes the
user-facing answer from it.

TOOL_HANDLERS is the dispatcher: tool name → function. The chat loop looks
up the name and calls the function with (arguments_dict, access_token).
"""
from src.api.blizzard import (
    find_reputation_tiers,
    get_achievement_data,
    get_creature_data,
    get_creature_family_data,
    get_creature_type_data,
    get_heirloom_data,
    get_item_data,
    get_item_set_data,
    get_journal_encounter_data,
    get_journal_expansion_data,
    get_journal_instance_data,
    get_mount_data,
    get_pet_data,
    get_playable_class_data,
    get_playable_race_data,
    get_playable_specialization_data,
    get_profession_data,
    get_quest_area_data,
    get_quest_category_data,
    get_quest_data,
    get_quest_type_data,
    get_reputation_faction_data,
    get_spell_data,
    get_title_data,
    get_toy_data,
    get_wow_token_price,
    list_index_names,
    lookup_journal_encounter_ids,
    lookup_static_ids,
    maybe_matching_skill_tier,
    search_blizzard,
    with_official_media,
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

    Most name-search tools do the same four steps. lookup_item and
    get_wow_token_price stay separate because they do not follow this
    search-by-name pattern. Index-backed tools use _index_search_and_fetch.
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


def _empty_search_term(function_args):
    """Return the raw search_term, or None when it is missing/blank."""
    if not isinstance(function_args, dict):
        return None
    search_term = function_args.get("search_term")
    if not search_term or not isinstance(search_term, str) or not search_term.strip():
        return None
    return search_term


def _format_payloads(result_label, payloads):
    """Turn one or more official documents into a single tool-result string."""
    if len(payloads) == 1:
        return f"{result_label} data received: {payloads[0]}"
    return f"{result_label} data received ({len(payloads)} matches): {payloads}"


def _index_search_and_fetch(
    function_args,
    access_token,
    entity_type,
    fetch_fn,
    result_label,
    noun,
    *,
    media_type=None,
    resolve_ids=None,
    overview_terms=None,
):
    """Shared path for static-index name lookup → detail fetch.

    Some Blizzard families have no Search API. Those tools load the official
    index, match a name, then fetch the detail document. overview_terms lists
    generic phrases that should return the index name list instead of one entity.
    """
    if not access_token:
        return _unavailable(noun)
    if not isinstance(function_args, dict):
        return _not_found("None")
    search_term = _empty_search_term(function_args)
    if search_term is None:
        return _not_found(function_args.get("search_term") if isinstance(function_args, dict) else None)

    if overview_terms and search_term.strip().lower() in overview_terms:
        names = list_index_names(entity_type, access_token)
        if not names:
            return _not_found(search_term)
        return f"{result_label} index received: {names}"

    resolver = resolve_ids or lookup_static_ids
    if resolver is lookup_static_ids:
        entity_ids = lookup_static_ids(search_term, entity_type, access_token)
    else:
        entity_ids = resolver(search_term, access_token)
    if not entity_ids:
        return _not_found(search_term)

    payloads = []
    for entity_id in entity_ids:
        data = fetch_fn(entity_id, access_token)
        if not data:
            continue
        if media_type:
            data = with_official_media(data, media_type, entity_id, access_token)
        payloads.append(data)
    if not payloads:
        return _not_found(search_term)
    return _format_payloads(result_label, payloads)


def handle_search_journal_encounter(function_args, access_token):
    return _index_search_and_fetch(
        function_args,
        access_token,
        "journal-encounter",
        get_journal_encounter_data,
        "Journal encounter",
        "journal encounter",
        resolve_ids=lookup_journal_encounter_ids,
    )


def handle_search_journal_expansion(function_args, access_token):
    return _index_search_and_fetch(
        function_args,
        access_token,
        "journal-expansion",
        get_journal_expansion_data,
        "Journal expansion",
        "journal expansion",
        overview_terms={"expansion", "expansions", "journal expansions"},
    )


def handle_search_playable_race(function_args, access_token):
    return _index_search_and_fetch(
        function_args,
        access_token,
        "playable-race",
        get_playable_race_data,
        "Playable race",
        "playable race",
        overview_terms={"race", "races", "playable race", "playable races"},
    )


def handle_search_playable_class(function_args, access_token):
    return _index_search_and_fetch(
        function_args,
        access_token,
        "playable-class",
        get_playable_class_data,
        "Playable class",
        "playable class",
        media_type="playable-class",
        overview_terms={"class", "classes", "playable class", "playable classes"},
    )


def handle_search_specialization(function_args, access_token):
    return _index_search_and_fetch(
        function_args,
        access_token,
        "playable-specialization",
        get_playable_specialization_data,
        "Specialization",
        "specialization",
        media_type="playable-specialization",
        overview_terms={"specialization", "specializations", "spec", "specs"},
    )


def handle_search_profession(function_args, access_token):
    """Look up a profession and attach media plus a matching skill-tier if named."""
    if not access_token:
        return _unavailable("profession")
    if not isinstance(function_args, dict):
        return _not_found("None")
    search_term = _empty_search_term(function_args)
    if search_term is None:
        return _not_found(function_args.get("search_term"))
    if search_term.strip().lower() in {"profession", "professions"}:
        names = list_index_names("profession", access_token)
        if not names:
            return _not_found(search_term)
        return f"Profession index received: {names}"

    profession_ids = lookup_static_ids(search_term, "profession", access_token)
    if not profession_ids:
        return _not_found(search_term)

    payloads = []
    for profession_id in profession_ids:
        data = get_profession_data(profession_id, access_token)
        if not data:
            continue
        data = with_official_media(data, "profession", profession_id, access_token)
        skill_tier = maybe_matching_skill_tier(data, search_term, access_token)
        if skill_tier:
            data = dict(data)
            data["official_skill_tier"] = skill_tier
        payloads.append(data)
    if not payloads:
        return _not_found(search_term)
    return _format_payloads("Profession", payloads)


def handle_search_item_set(function_args, access_token):
    return _index_search_and_fetch(
        function_args,
        access_token,
        "item-set",
        get_item_set_data,
        "Item set",
        "item set",
    )


def handle_search_reputation_tiers(function_args, access_token):
    if not access_token:
        return _unavailable("reputation tiers")
    if not isinstance(function_args, dict):
        return _not_found("None")
    search_term = _empty_search_term(function_args)
    if search_term is None:
        return _not_found(function_args.get("search_term"))
    data = find_reputation_tiers(search_term, access_token)
    if not data:
        return _not_found(search_term)
    return f"Reputation tiers data received: {data}"


def handle_search_creature_family(function_args, access_token):
    """Resolve a creature family or creature type from the official indexes."""
    if not access_token:
        return _unavailable("creature family")
    if not isinstance(function_args, dict):
        return _not_found("None")
    search_term = _empty_search_term(function_args)
    if search_term is None:
        return _not_found(function_args.get("search_term"))

    query = search_term.strip().lower()
    family_overview = {"creature family", "creature families", "pet family", "pet families", "families"}
    type_overview = {"creature type", "creature types", "types"}
    if query in family_overview:
        names = list_index_names("creature-family", access_token)
        return f"Creature family index received: {names}" if names else _not_found(search_term)
    if query in type_overview:
        names = list_index_names("creature-type", access_token)
        return f"Creature type index received: {names}" if names else _not_found(search_term)

    payloads = []
    family_ids = lookup_static_ids(search_term, "creature-family", access_token)
    for family_id in family_ids:
        data = get_creature_family_data(family_id, access_token)
        if data:
            payloads.append(with_official_media(data, "creature-family", family_id, access_token))
    type_ids = lookup_static_ids(search_term, "creature-type", access_token)
    for type_id in type_ids:
        data = get_creature_type_data(type_id, access_token)
        if data:
            payloads.append(data)
    if not payloads:
        return _not_found(search_term)
    return _format_payloads("Creature family or type", payloads)


def handle_search_quest_group(function_args, access_token):
    """Resolve a quest area, category, or type from the official indexes."""
    if not access_token:
        return _unavailable("quest group")
    if not isinstance(function_args, dict):
        return _not_found("None")
    search_term = _empty_search_term(function_args)
    if search_term is None:
        return _not_found(function_args.get("search_term"))

    query = search_term.strip().lower()
    overview_map = {
        "quest area": ("quest/area", "Quest area"),
        "quest areas": ("quest/area", "Quest area"),
        "quest category": ("quest/category", "Quest category"),
        "quest categories": ("quest/category", "Quest category"),
        "quest type": ("quest/type", "Quest type"),
        "quest types": ("quest/type", "Quest type"),
    }
    if query in overview_map:
        entity_type, label = overview_map[query]
        names = list_index_names(entity_type, access_token)
        return f"{label} index received: {names}" if names else _not_found(search_term)

    lookups = (
        ("quest/area", get_quest_area_data, "Quest area"),
        ("quest/category", get_quest_category_data, "Quest category"),
        ("quest/type", get_quest_type_data, "Quest type"),
    )
    payloads = []
    labels = []
    for entity_type, fetch_fn, label in lookups:
        for entity_id in lookup_static_ids(search_term, entity_type, access_token):
            data = fetch_fn(entity_id, access_token)
            if data:
                payloads.append(data)
                labels.append(label)
    if not payloads:
        return _not_found(search_term)
    if len(payloads) == 1:
        return f"{labels[0]} data received: {payloads[0]}"
    labeled = [
        {**payload, "official_group_kind": label} if isinstance(payload, dict) else payload
        for payload, label in zip(payloads, labels)
    ]
    return f"Quest group data received ({len(payloads)} matches): {labeled}"


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
    "search_journal_encounter": handle_search_journal_encounter,
    "search_journal_expansion": handle_search_journal_expansion,
    "search_playable_race": handle_search_playable_race,
    "search_playable_class": handle_search_playable_class,
    "search_specialization": handle_search_specialization,
    "search_profession": handle_search_profession,
    "search_item_set": handle_search_item_set,
    "search_reputation_tiers": handle_search_reputation_tiers,
    "search_creature_family": handle_search_creature_family,
    "search_quest_group": handle_search_quest_group,
    "get_wow_token_price": handle_get_wow_token_price,
}
