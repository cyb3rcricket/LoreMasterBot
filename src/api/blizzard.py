# Blizzard API integration: token lifecycle, caching, search, and entity lookups.
import time

import requests

from src.config import CLIENT_ID, CLIENT_SECRET


# Global variables for token management
blizzard_token = None
token_expiry = 0   # Unix timestamp when the current token expires

# Global caches to avoid repeated API calls
# search_cache: key = (entity_type, search_term.lower()) -> id (from search results)
# data_cache: key = (data_type, id) -> full json data (from detailed fetches)
search_cache = {}
data_cache = {}


def get_access_token():
    """Fetches a new access token from Blizzard. Pure function - no side effects."""
    url = "https://oauth.battle.net/token"
    data = {"grant_type": "client_credentials"}
    auth = (CLIENT_ID, CLIENT_SECRET)

    # Retry logic: up to 3 attempts with 2-second delays between retries for resilience
    for attempt in range(3):
        try:
            response = requests.post(url, data=data, auth=auth)
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


def search_blizzard(search_term, entity_type, access_token):
    """Searches for an entity and returns the first result's ID."""
    key = (entity_type, search_term.lower())
    if key in search_cache:
        return search_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/search/{entity_type}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "namespace": "static-us",
        "locale": "en_US",
        "name.en_US": search_term,
        "_page": 1
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        results = response.json().get("results")
        if results:
            id = results[0]["data"]["id"]
            search_cache[key] = id
            return id
    except Exception as e:
        print(f"Error during search: {e}")
    return None


def get_item_data(item_id, access_token):
    """Fetches data for a specific item using the access token."""
    key = ("item", item_id)
    if key in data_cache:
        return data_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/item/{item_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "static-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        data_cache[key] = data
        return data
    except Exception as e:
        print(f"Error getting item data: {e}")
        return None


def get_creature_data(creature_id, access_token):
    """Fetches data for a specific creature using the access token."""
    key = ("creature", creature_id)
    if key in data_cache:
        return data_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/creature/{creature_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "static-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        data_cache[key] = data
        return data
    except Exception as e:
        print(f"Error getting creature data: {e}")
        return None


def get_quest_data(quest_id, access_token):
    """Fetches data for a specific quest using the access token."""
    key = ("quest", quest_id)
    if key in data_cache:
        return data_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/quest/{quest_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "static-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        data_cache[key] = data
        return data
    except Exception as e:
        print(f"Error getting quest data: {e}")
        return None


def get_mount_data(mount_id, access_token):
    """Fetches data for a specific mount using the access token."""
    key = ("mount", mount_id)
    if key in data_cache:
        return data_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/mount/{mount_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "static-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        data_cache[key] = data
        return data
    except Exception as e:
        print(f"Error getting mount data: {e}")
        return None


def get_achievement_data(achievement_id, access_token):
    """Fetches data for a specific achievement using the access token."""
    key = ("achievement", achievement_id)
    if key in data_cache:
        return data_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/achievement/{achievement_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "static-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        data_cache[key] = data
        return data
    except Exception as e:
        print(f"Error getting achievement data: {e}")
        return None


def get_spell_data(spell_id, access_token):
    """Fetches data for a specific spell using the access token."""
    key = ("spell", spell_id)
    if key in data_cache:
        return data_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/spell/{spell_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "static-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        data_cache[key] = data
        return data
    except Exception as e:
        print(f"Error getting spell data: {e}")
        return None


def get_journal_instance_data(instance_id, access_token):
    """Fetches data for a specific journal instance (raid or dungeon) using the access token."""
    key = ("journal-instance", instance_id)
    if key in data_cache:
        return data_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/journal-instance/{instance_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "static-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        data_cache[key] = data
        return data
    except Exception as e:
        print(f"Error getting journal instance data: {e}")
        return None


def get_reputation_faction_data(faction_id, access_token):
    """Fetches data for a specific reputation faction using the access token."""
    key = ("reputation-faction", faction_id)
    if key in data_cache:
        return data_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/reputation-faction/{faction_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "static-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        data_cache[key] = data
        return data
    except Exception as e:
        print(f"Error getting reputation faction data: {e}")
        return None


def get_title_data(title_id, access_token):
    """Fetches data for a specific title using the access token."""
    key = ("title", title_id)
    if key in data_cache:
        return data_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/title/{title_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "static-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        data_cache[key] = data
        return data
    except Exception as e:
        print(f"Error getting title data: {e}")
        return None


def get_toy_data(toy_id, access_token):
    """Fetches data for a specific toy using the access token."""
    key = ("toy", toy_id)
    if key in data_cache:
        return data_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/toy/{toy_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "static-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        data_cache[key] = data
        return data
    except Exception as e:
        print(f"Error getting toy data: {e}")
        return None


def get_pet_data(pet_id, access_token):
    """Fetches data for a specific battle pet using the access token."""
    key = ("pet", pet_id)
    if key in data_cache:
        return data_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/pet/{pet_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "static-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        data_cache[key] = data
        return data
    except Exception as e:
        print(f"Error getting pet data: {e}")
        return None


def get_heirloom_data(heirloom_id, access_token):
    """Fetches data for a specific heirloom using the access token."""
    key = ("heirloom", heirloom_id)
    if key in data_cache:
        return data_cache[key]

    url = f"https://us.api.blizzard.com/data/wow/heirloom/{heirloom_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "static-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        data_cache[key] = data
        return data
    except Exception as e:
        print(f"Error getting heirloom data: {e}")
        return None


def get_wow_token_price(access_token):
    """Fetches the current WoW Token price using the dynamic namespace."""
    key = ("wow_token", "price")
    if key in data_cache:
        return data_cache[key]

    url = "https://us.api.blizzard.com/data/wow/token/"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"namespace": "dynamic-us", "locale": "en_US"}
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        price_in_copper = data.get("price", 0)
        price_in_gold = price_in_copper // 10000
        result = {"price": price_in_gold, "raw_data": data}
        data_cache[key] = result
        return result
    except Exception as e:
        print(f"Error getting WoW Token price: {e}")
        return None