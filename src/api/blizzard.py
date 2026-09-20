"""Blizzard API integration: token lifecycle, caching, search, and entity lookups."""
import time

import requests

from src.config import CLIENT_ID, CLIENT_SECRET


# Constants for API timeouts and TTL
BLIZZARD_API_TIMEOUT = 10
WOW_TOKEN_CACHE_TTL_SECONDS = 60

# Global variables for token management
blizzard_token = None
token_expiry = 0   # Unix timestamp when the current token expires

# Global caches to avoid repeated API calls
# search_cache: key = (entity_type, search_term.lower()) -> id (from search results)
# data_cache: key = (data_type, id) -> full json data (from detailed fetches)
# wow_token_cache: {"data": result, "timestamp": float} -> cached token price with TTL
search_cache = {}
data_cache = {}
wow_token_cache = {"data": None, "timestamp": 0.0}

# Famous items fallback for items that may not search well (normalized lowercase keys)
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
    """Fetches a new access token from Blizzard. Pure function - no side effects."""
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
    """Returns a valid Blizzard access token, automatically refreshing it if needed."""
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
    """Prefer an exact case-insensitive name match; otherwise use the first result ID."""
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
    response = requests.get(url, params=params, headers=headers, timeout=BLIZZARD_API_TIMEOUT)
    response.raise_for_status()
    return response.json().get("results")


def search_blizzard(search_term, entity_type, access_token):
    """Searches for an entity and returns the first result's ID. Note: 'quest' and 'achievement' types are known to have spotty name-search support."""
    if not search_term or not isinstance(search_term, str):
        return None

    normalized_type = entity_type.lower() if isinstance(entity_type, str) else str(entity_type)
    normalized_term = search_term.strip().lower()
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

    if normalized_type in ["quest", "achievement"]:
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
    """Fetch and cache a static WoW entity. Item IDs are normalized for int/str cache hits."""
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
    """Fetches the current WoW Token price using the dynamic namespace with TTL caching."""
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
