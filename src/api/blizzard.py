"""Talk to Blizzard's Game Data API: login, search, fetch, and cache.

An API (Application Programming Interface) is a web address that returns
data when you send a correctly formed request. An HTTP request is that
message: GET reads data, POST sends a form such as a login.

This file is the only place that should contact blizzard.com / battle.net.
Handlers call these functions and turn the results into text for the model.
"""
import time

import requests

from src.config import CLIENT_ID, CLIENT_SECRET


# How long to wait for Blizzard before giving up. Without a timeout, a hung
# network call can freeze the chat loop forever.
BLIZZARD_API_TIMEOUT = 10
# Time-to-live: how long a cached WoW Token price may be reused. Token gold
# value changes, so it cannot live in the permanent data_cache.
WOW_TOKEN_CACHE_TTL_SECONDS = 60

# The current login password for Blizzard API calls, plus when it expires.
# Unix time is seconds since 1970-01-01; time.time() returns that number.
blizzard_token = None
token_expiry = 0   # Unix timestamp when the current token expires

# Caches remember earlier answers so the same search or item is not fetched
# again in this process. Keys are tuples so type and id stay paired.
# search_cache: key = (entity_type, search_term.lower()) -> id (from search results)
# data_cache: key = (data_type, id) -> full json data (from detailed fetches)
# wow_token_cache: {"data": result, "timestamp": float} -> cached token price with TTL
search_cache = {}
data_cache = {}
wow_token_cache = {"data": None, "timestamp": 0.0}

# Blizzard's name search misses some well-known legendaries. This map jumps
# straight to the official item ID. Keys stay lowercase so "Thunderfury" and
# "thunderfury" hit the same entry after search_blizzard normalizes the query.
famous_items = {
    "ashbringer": 13262,
    "thunderfury": 19019,
    "sulfuras": 17182,
    "atiesh": 22589,
    "val'anyr": 46017,
    "shadowmourne": 49623,
    "dragonwrath": 78495,
}


def get_access_token():
    """Ask Battle.net for a new access token.

    OAuth here is a simple machine login: we send CLIENT_ID and CLIENT_SECRET
    and receive a temporary token. The function does not write the globals;
    ensure_valid_token() stores the result. Returns (token, expires_in_seconds)
    or (None, None) after three failed tries.

    Retries exist because a single timeout or 500 should not kill startup.
    """
    url = "https://oauth.battle.net/token"
    data = {"grant_type": "client_credentials"}
    auth = (CLIENT_ID, CLIENT_SECRET)

    # Retry logic: up to 3 attempts with 2-second delays between retries for resilience
    for attempt in range(3):
        try:
            response = requests.post(url, data=data, auth=auth, timeout=BLIZZARD_API_TIMEOUT)
            response.raise_for_status()
            json_data = response.json()
            token = json_data.get("access_token")
            expires_in = json_data.get("expires_in", 3600)
            return token, expires_in
        except Exception as e:
            print(f"Error getting access token: {e}")
            if attempt < 2:
                print(f"⚠️ Token refresh failed, retrying (attempt {attempt+1}/3)...")
                time.sleep(2)
            else:
                print("❌ All token refresh attempts failed after 3 tries.")
                return None, None


def ensure_valid_token():
    """Return a usable token, refreshing if it is missing or nearly expired.

    Tokens expire. Refreshing 60 seconds early avoids using a token that dies
    mid-request. Returns None if Blizzard cannot be reached so handlers can
    show an unavailable message instead of crashing.
    """
    global blizzard_token, token_expiry

    # Refresh if we have no token OR if it's expiring within the next 60 seconds
    if not blizzard_token or time.time() >= token_expiry - 60:
        print("🔄 Refreshing Blizzard access token...")
        token, expires_in = get_access_token()

        if token:
            blizzard_token = token
            token_expiry = time.time() + expires_in
            print("✅ Token refreshed successfully!")
        else:
            print("❌ Failed to refresh Blizzard token")
            return None

    return blizzard_token


def _pick_search_id(results, search_term):
    """Choose one ID from a Blizzard search result list.

    Prefer a result whose English name matches the query ignoring case.
    Otherwise take the first result. Search is imperfect, so the first hit
    is a fallback, not a guarantee. Returns None when the list is empty.
    """
    if not results:
        return None

    lowered = search_term.lower()
    for result in results:
        try:
            name = result.get("data", {}).get("name", {}).get("en_US")
        except Exception:
            name = None
        if name and name.lower() == lowered:
            return result.get("data", {}).get("id")
    return results[0]["data"]["id"]


def _search_request(url, params, headers):
    """One search GET. Raises on HTTP errors so the caller can retry or give up."""
    response = requests.get(url, params=params, headers=headers, timeout=BLIZZARD_API_TIMEOUT)
    response.raise_for_status()
    return response.json().get("results")


def search_blizzard(search_term, entity_type, access_token):
    """Search by name and return the chosen entity ID, or None.

    entity_type is the Blizzard search path piece, such as "item" or "quest".
    Quest and achievement name search is unreliable, so those types try
    `name.en_US` first and then plain `name`. Other types try `name.en_US` only.

    Famous items skip the network. Later repeats use search_cache.
    A blank or whitespace-only name is not a search and must not be sent.
    """
    if not isinstance(search_term, str):
        return None

    normalized_type = entity_type.lower() if isinstance(entity_type, str) else str(entity_type)
    # "   " is truthy, so strip before the empty check. Otherwise a blank
    # name still becomes a Blizzard request.
    normalized_term = search_term.strip().lower()
    if not normalized_term:
        return None
    if normalized_type == "item" and normalized_term in famous_items:
        item_id = famous_items[normalized_term]
        key = (normalized_type, normalized_term)
        search_cache[key] = item_id
        return item_id

    key = (normalized_type, normalized_term)
    if key in search_cache:
        return search_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/search/{normalized_type}"
    headers = {"Authorization": f"Bearer {access_token}"}
    base_params = {
        "namespace": "static-us",
        "locale": "en_US",
        "_page": 1,
        "_pageSize": 5,
    }

    if normalized_type in ["quest", "achievement", "journal-encounter"]:
        search_attempts = (
            ("name.en_US", "Error during search with name.en_US"),
            ("name", "Error during search with name"),
        )
    else:
        search_attempts = (("name.en_US", "Error during search"),)

    for name_field, error_prefix in search_attempts:
        params = {**base_params, name_field: search_term}
        try:
            results = _search_request(url, params, headers)
            exact_id = _pick_search_id(results, search_term)
            if exact_id is not None:
                search_cache[key] = exact_id
                return exact_id
        except Exception as e:
            print(f"{error_prefix}: {e}")
    return None


def _get_entity_data(entity_type, entity_id, access_token):
    """Fetch one static entity document and remember it in data_cache.

    Static data (items, mounts, and so on) rarely changes, so a permanent
    in-process cache is enough. Item IDs may arrive as 19019 or "19019";
    both must share one cache key or the same item is downloaded twice.

    On any request or JSON error, print a line and return None. The chat
    loop then tells the model no official data was found.
    """
    if entity_type == "item":
        cache_id = int(str(entity_id).strip()) if str(entity_id).strip().isdigit() else entity_id
    else:
        cache_id = entity_id
    key = (entity_type, cache_id)
    if key in data_cache:
        return data_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/{entity_type}/{entity_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "static-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=BLIZZARD_API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        data_cache[key] = data
        return data
    except Exception as e:
        print(f"Error getting {entity_type.replace('-', ' ')} data: {e}")
        return None


def get_item_data(item_id, access_token):
    """Fetches data for a specific item using the access token."""
    return _get_entity_data("item", item_id, access_token)


def get_creature_data(creature_id, access_token):
    """Fetches data for a specific creature using the access token."""
    return _get_entity_data("creature", creature_id, access_token)


def get_quest_data(quest_id, access_token):
    """Fetches data for a specific quest using the access token."""
    return _get_entity_data("quest", quest_id, access_token)


def get_mount_data(mount_id, access_token):
    """Fetches data for a specific mount using the access token."""
    return _get_entity_data("mount", mount_id, access_token)


def get_achievement_data(achievement_id, access_token):
    """Fetches data for a specific achievement using the access token."""
    return _get_entity_data("achievement", achievement_id, access_token)


def get_spell_data(spell_id, access_token):
    """Fetches data for a specific spell using the access token."""
    return _get_entity_data("spell", spell_id, access_token)


def get_journal_instance_data(instance_id, access_token):
    """Fetches data for a specific journal instance (raid or dungeon) using the access token."""
    return _get_entity_data("journal-instance", instance_id, access_token)


def get_reputation_faction_data(faction_id, access_token):
    """Fetches data for a specific reputation faction using the access token."""
    return _get_entity_data("reputation-faction", faction_id, access_token)


def get_title_data(title_id, access_token):
    """Fetches data for a specific title using the access token."""
    return _get_entity_data("title", title_id, access_token)


def get_toy_data(toy_id, access_token):
    """Fetches data for a specific toy using the access token."""
    return _get_entity_data("toy", toy_id, access_token)


def get_pet_data(pet_id, access_token):
    """Fetches data for a specific battle pet using the access token."""
    return _get_entity_data("pet", pet_id, access_token)


def get_heirloom_data(heirloom_id, access_token):
    """Fetches data for a specific heirloom using the access token."""
    return _get_entity_data("heirloom", heirloom_id, access_token)


def get_wow_token_price(access_token):
    """Fetch the current WoW Token gold price, cached for a short TTL.

    Uses the dynamic namespace because this number changes. A missing,
    zero, or non-numeric price is rejected so the bot never reports 0 gold.
    If the system clock jumps backward, elapsed time is treated as invalid
    and the price is fetched again.
    """
    now = time.time()
    if wow_token_cache["data"] is not None and 0 <= (now - wow_token_cache["timestamp"]) < WOW_TOKEN_CACHE_TTL_SECONDS:
        return wow_token_cache["data"]

    url = "https://us.api.blizzard.com/data/wow/token/"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "dynamic-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=BLIZZARD_API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        price_in_copper = data.get("price")
        if not isinstance(price_in_copper, (int, float)) or price_in_copper <= 0:
            print("Error: Invalid or missing price in WoW Token response")
            return None
        price_in_gold = int(price_in_copper) // 10000
        result = {"price": price_in_gold, "raw_data": data}
        wow_token_cache["data"] = result
        wow_token_cache["timestamp"] = now
        return result
    except Exception as e:
        print(f"Error getting WoW Token price: {e}")
        return None


# How many name matches from a static index may be fetched in one lookup.
# Specializations such as "Frost" exist on more than one class.
MAX_INDEX_MATCHES = 5
# Reputation-tier index entries often have IDs and no names. This is a
# safety cap, not the default fetch count. Common queries stop as soon as
# they have enough official data.
MAX_REPUTATION_TIER_DOCS = 40

_GENERIC_REPUTATION_TERMS = frozenset({
    "",
    "reputation",
    "reputation levels",
    "reputation level",
    "reputation tiers",
    "standings",
    "standing",
    "levels",
    "classic",
    "classic reputation",
    "classic standings",
})


def _get_static_document(path, cache_key, access_token):
    """GET a static-us Game Data document and remember it in data_cache.

    path is the piece after /data/wow/, such as playable-race/index.
    cache_key is the data_cache tuple. Returns a dict, or None on HTTP,
    JSON, or type errors so handlers can show a not-found message.
    """
    if cache_key in data_cache:
        return data_cache[cache_key]

    url = f"https://us.api.blizzard.com/data/wow/{path}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "static-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=BLIZZARD_API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            print(f"Error getting {path.replace('-', ' ')} data: expected a JSON object")
            return None
        data_cache[cache_key] = data
        return data
    except Exception as e:
        print(f"Error getting {path.replace('-', ' ')} data: {e}")
        return None


def get_index_data(entity_type, access_token):
    """Fetch /data/wow/{entity_type}/index and cache it as static data."""
    if not entity_type or not isinstance(entity_type, str):
        return None
    return _get_static_document(f"{entity_type}/index", (entity_type, "index"), access_token)


def _entry_name(entry):
    """Return a display name string from an index/detail entry, or None."""
    if not isinstance(entry, dict):
        return None
    name = entry.get("name")
    if isinstance(name, str) and name.strip():
        return name
    if isinstance(name, dict):
        localized = name.get("en_US")
        if isinstance(localized, str) and localized.strip():
            return localized
        for value in name.values():
            if isinstance(value, str) and value.strip():
                return value
    return None


def _iter_named_index_entries(payload):
    """Yield dicts that have both id and name from a Blizzard index document."""
    if isinstance(payload, dict):
        if "id" in payload and _entry_name(payload) is not None:
            yield payload
        for key, value in payload.items():
            if key in ("_links", "key", "href"):
                continue
            yield from _iter_named_index_entries(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_named_index_entries(item)


def _iter_index_ids(payload):
    """Yield id values from an index document, including nameless entries."""
    if isinstance(payload, dict):
        if "id" in payload:
            yield payload["id"]
        for key, value in payload.items():
            if key in ("_links", "key", "href"):
                continue
            yield from _iter_index_ids(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_index_ids(item)


def _unique_ids(ids, limit=MAX_INDEX_MATCHES):
    """Preserve first-seen order and cap how many IDs are returned."""
    unique = []
    seen = set()
    for entity_id in ids:
        if entity_id in seen:
            continue
        seen.add(entity_id)
        unique.append(entity_id)
        if len(unique) >= limit:
            break
    return unique


def _singularize_query(query):
    """Return light English plural foldings of a lowercase query.

    Exact official names are tried first by the caller. These alternatives
    only help when the user typed a common plural such as Night Elves or
    Dwarves. Irregular endings are tried before a trailing 's' so
    'night elves' becomes 'night elf', not 'night elve'.
    """
    if not query:
        return []

    candidates = []
    if query.endswith("elves"):
        candidates.append(query[:-5] + "elf")
    if query.endswith("dwarves"):
        candidates.append(query[:-7] + "dwarf")
    if query.endswith("s") and len(query) > 3:
        candidates.append(query[:-1])

    unique = []
    seen = set()
    for candidate in candidates:
        folded = candidate.strip()
        if not folded or folded == query or folded in seen:
            continue
        seen.add(folded)
        unique.append(folded)
    return unique


def _match_index_ids(index_data, search_term, limit=MAX_INDEX_MATCHES):
    """Choose official IDs whose names match a natural-language query.

    Order of preference:
    1. Exact case-insensitive name.
    2. Exact name after a light English plural folding.
    3. An index name contained in the query (so 'Human race' hits Human).
    4. The query contained in an index name.
    """
    if not index_data or not search_term or not isinstance(search_term, str):
        return []

    query = search_term.strip().lower()
    if not query:
        return []

    entries = []
    seen_pairs = set()
    for entry in _iter_named_index_entries(index_data):
        name = _entry_name(entry)
        entity_id = entry.get("id")
        pair = (entity_id, name)
        if name is None or entity_id is None or pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        entries.append((entity_id, name))

    def exact(candidate):
        return [entity_id for entity_id, name in entries if name.lower() == candidate]

    ids = exact(query)
    if not ids:
        for candidate in _singularize_query(query):
            ids = exact(candidate)
            if ids:
                break
    if not ids:
        contained = [
            (entity_id, name)
            for entity_id, name in entries
            if len(name) >= 3 and name.lower() in query
        ]
        contained.sort(key=lambda item: len(item[1]), reverse=True)
        ids = [entity_id for entity_id, _name in contained]
    if not ids:
        ids = [entity_id for entity_id, name in entries if query in name.lower()]
    return _unique_ids(ids, limit=limit)


def lookup_static_ids(search_term, entity_type, access_token):
    """Resolve a display name to official IDs using a cached static index.

    Used when Blizzard does not offer a Search API for that entity family.
    Returns a list of IDs, possibly empty.
    """
    if not search_term or not isinstance(search_term, str) or not entity_type:
        return []

    normalized_term = search_term.strip().lower()
    if not normalized_term:
        return []

    cache_key = ("index-lookup", entity_type, normalized_term)
    if cache_key in search_cache:
        cached = search_cache[cache_key]
        return list(cached) if isinstance(cached, list) else []

    index_data = get_index_data(entity_type, access_token)
    ids = _match_index_ids(index_data, search_term)
    search_cache[cache_key] = ids
    return ids


def list_index_names(entity_type, access_token):
    """Return official names from a static index, or None if it cannot be loaded."""
    index_data = get_index_data(entity_type, access_token)
    if not index_data:
        return None
    names = []
    seen = set()
    for entry in _iter_named_index_entries(index_data):
        name = _entry_name(entry)
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def lookup_journal_encounter_ids(search_term, access_token):
    """Resolve a boss/encounter name via Search, then the encounter index."""
    found = search_blizzard(search_term, "journal-encounter", access_token)
    if found is not None:
        return [found]
    return lookup_static_ids(search_term, "journal-encounter", access_token)


def get_journal_encounter_data(encounter_id, access_token):
    """Fetches data for a specific dungeon-journal encounter using the access token."""
    return _get_entity_data("journal-encounter", encounter_id, access_token)


def get_journal_expansion_data(expansion_id, access_token):
    """Fetches data for a specific journal expansion using the access token."""
    return _get_entity_data("journal-expansion", expansion_id, access_token)


def get_playable_race_data(race_id, access_token):
    """Fetches data for a specific playable race using the access token."""
    return _get_entity_data("playable-race", race_id, access_token)


def get_playable_class_data(class_id, access_token):
    """Fetches data for a specific playable class using the access token."""
    return _get_entity_data("playable-class", class_id, access_token)


def get_playable_specialization_data(spec_id, access_token):
    """Fetches data for a specific playable specialization using the access token."""
    return _get_entity_data("playable-specialization", spec_id, access_token)


def get_profession_data(profession_id, access_token):
    """Fetches data for a specific profession using the access token."""
    return _get_entity_data("profession", profession_id, access_token)


def get_profession_skill_tier_data(profession_id, skill_tier_id, access_token):
    """Fetches one profession skill-tier document using the access token."""
    profession_text = str(profession_id).strip()
    tier_text = str(skill_tier_id).strip()
    cache_profession = int(profession_text) if profession_text.isdigit() else profession_id
    cache_tier = int(tier_text) if tier_text.isdigit() else skill_tier_id
    return _get_static_document(
        f"profession/{profession_id}/skill-tier/{skill_tier_id}",
        ("profession-skill-tier", (cache_profession, cache_tier)),
        access_token,
    )


def get_item_set_data(item_set_id, access_token):
    """Fetches data for a specific item set using the access token."""
    return _get_entity_data("item-set", item_set_id, access_token)


def get_quest_area_data(quest_area_id, access_token):
    """Fetches data for a specific quest area using the access token."""
    return _get_entity_data("quest/area", quest_area_id, access_token)


def get_quest_category_data(quest_category_id, access_token):
    """Fetches data for a specific quest category using the access token."""
    return _get_entity_data("quest/category", quest_category_id, access_token)


def get_quest_type_data(quest_type_id, access_token):
    """Fetches data for a specific quest type using the access token."""
    return _get_entity_data("quest/type", quest_type_id, access_token)


def get_creature_family_data(family_id, access_token):
    """Fetches data for a specific creature family using the access token."""
    return _get_entity_data("creature-family", family_id, access_token)


def get_creature_type_data(type_id, access_token):
    """Fetches data for a specific creature type using the access token."""
    return _get_entity_data("creature-type", type_id, access_token)


def get_reputation_tiers_data(tiers_id, access_token):
    """Fetches one reputation-tiers document using the access token."""
    return _get_entity_data("reputation-tiers", tiers_id, access_token)


def get_entity_media(media_type, entity_id, access_token):
    """Fetch official media metadata for an entity. Does not download assets."""
    if not media_type or not isinstance(media_type, str):
        return None
    return _get_entity_data(f"media/{media_type}", entity_id, access_token)


def with_official_media(data, media_type, entity_id, access_token):
    """Copy entity data and attach official_media when Blizzard has assets.

    The cached entity document is left unchanged. Media failures are ignored
    so a missing icon does not hide the structured record.
    """
    if not isinstance(data, dict):
        return data
    media = get_entity_media(media_type, entity_id, access_token)
    if not media:
        return data
    combined = dict(data)
    combined["official_media"] = media
    return combined


def _is_classic_reputation_set(document):
    """True when a tiers document includes the classic Hated and Exalted names."""
    names = set()
    for tier in document.get("tiers") or []:
        if isinstance(tier, dict) and isinstance(tier.get("name"), str):
            names.add(tier["name"].lower())
    return "hated" in names and "exalted" in names


def _reputation_tier_summary(document):
    """Project official standing names from one reputation-tiers document."""
    standings = []
    for tier in document.get("tiers") or []:
        if isinstance(tier, dict) and isinstance(tier.get("name"), str):
            standings.append(tier["name"])
    faction = document.get("faction")
    faction_name = faction.get("name") if isinstance(faction, dict) else None
    return {
        "id": document.get("id"),
        "name": document.get("name"),
        "faction": faction_name,
        "standings": standings,
    }


def _reputation_document_matches(document, query):
    """True when query matches a faction, system, or standing name in the document."""
    names = []
    if isinstance(document.get("name"), str):
        names.append(document["name"])
    faction = document.get("faction")
    if isinstance(faction, dict) and isinstance(faction.get("name"), str):
        names.append(faction["name"])
    for tier in document.get("tiers") or []:
        if isinstance(tier, dict) and isinstance(tier.get("name"), str):
            names.append(tier["name"])
    for name in names:
        lowered = name.lower()
        if query == lowered or (len(name) >= 3 and (query in lowered or lowered in query)):
            return True
    return False


def _reputation_index_ids(access_token):
    """Return official reputation-tier IDs from the cached index, or None."""
    index_data = get_index_data("reputation-tiers", access_token)
    if not index_data:
        return None
    return _unique_ids(_iter_index_ids(index_data), limit=MAX_REPUTATION_TIER_DOCS)


def find_reputation_tiers(search_term, access_token):
    """Return official reputation standing data for a generic or named query.

    Detail documents are fetched one at a time from the official index and
    stop as soon as the query is satisfied. Generic standing questions stop
    at the classic Hated through Exalted set. Named queries stop at the
    first matching document.
    """
    ids = _reputation_index_ids(access_token)
    if not ids:
        return None

    query = search_term.strip().lower() if isinstance(search_term, str) else ""
    if query in _GENERIC_REPUTATION_TERMS:
        fetched = []
        classic = None
        for tiers_id in ids:
            data = get_reputation_tiers_data(tiers_id, access_token)
            if not data:
                continue
            fetched.append(data)
            if _is_classic_reputation_set(data):
                classic = data
                break
        if not fetched:
            return None
        standard = classic or fetched[0]
        others = [
            _reputation_tier_summary(doc)
            for doc in fetched
            if doc is not standard
        ]
        return {
            "standard_standings": standard,
            "other_reputation_systems": others,
        }

    matched = []
    for tiers_id in ids:
        data = get_reputation_tiers_data(tiers_id, access_token)
        if not data:
            continue
        if _reputation_document_matches(data, query):
            matched.append(data)
            break
    return matched or None


def maybe_matching_skill_tier(profession_data, search_term, access_token):
    """Fetch a skill-tier document when the query equals an official tier name.

    Profession detail already lists skill-tier names. A second request is only
    made when the user asked for that tier by name, because recipe lists are large.
    """
    if not isinstance(profession_data, dict) or not isinstance(search_term, str):
        return None
    query = search_term.strip().lower()
    if not query:
        return None
    profession_id = profession_data.get("id")
    for tier in profession_data.get("skill_tiers") or []:
        if not isinstance(tier, dict):
            continue
        name = _entry_name(tier)
        tier_id = tier.get("id")
        if name and tier_id is not None and name.lower() == query:
            return get_profession_skill_tier_data(profession_id, tier_id, access_token)
    return None

