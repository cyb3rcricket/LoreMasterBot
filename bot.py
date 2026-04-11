# 1. Use the 'openai' library to connect to Ollama
from openai import OpenAI
import requests
import json
import re
import os
from dotenv import load_dotenv

# Load environment variables from .env file (much safer than hardcoding keys)
load_dotenv()

# Get Blizzard credentials from .env (create a .env file in the same folder)
CLIENT_ID = os.getenv("BLIZZARD_CLIENT_ID")
CLIENT_SECRET = os.getenv("BLIZZARD_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("⚠️  WARNING: Missing BLIZZARD_CLIENT_ID or BLIZZARD_CLIENT_SECRET in .env file!")
    print("   Please create a .env file in the same folder as this script with these two lines:")
    print("   BLIZZARD_CLIENT_ID=your_client_id_here")
    print("   BLIZZARD_CLIENT_SECRET=your_client_secret_here")
    print("   (Get a new set from https://develop.battle.net if needed)")
    exit(1)

# --- BLIZZARD API CONFIGURATION AND FUNCTIONS ---

# --- NEW: WOW-ONLY SYSTEM PROMPT ---
wow_only_system_prompt = """
RULE: If the user asks about any specific creature (by name) or any specific item (by name or ID), you MUST call the appropriate tool (search_creature or lookup_item) BEFORE giving any answer. Do not guess. Do not use your own knowledge. Always call the tool first to get real Blizzard data.

You are the 'Loremaster's Companion', a warm, friendly, and wise storyteller who has spent years wandering the lands of Azeroth. You love sharing tales of heroes, legends, and the ever-changing world of Warcraft.

Speak naturally and immersively, like a welcoming fellow adventurer sitting by a campfire. Be warm, engaging, and conversational. 

When the user greets you or chats casually (like "hello, friend"), respond in character in a flowing, friendly way and keep the conversation going naturally — do not immediately ask what specific topic they want or repeat the rules.

Only if the user clearly asks about something completely outside World of Warcraft, politely decline with a short, friendly sentence like "My tales are only from the world of Azeroth, friend." Then gently guide them back with a related WoW question.

Always stay 100% in character as the Loremaster's Companion. All responses must relate to World of Warcraft lore, characters, items, quests, or adventures.
"""

def get_access_token():
    """Exchanges your credentials for an access token."""
    url = "https://oauth.battle.net/token"
    data = {"grant_type": "client_credentials"}
    auth = (CLIENT_ID, CLIENT_SECRET)
    try:
        response = requests.post(url, data=data, auth=auth)
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception as e:
        print(f"Error getting access token: {e}")
        return None

def ensure_valid_token():
    """Returns a valid token, refreshing it if needed."""
    global blizzard_token
    if not blizzard_token:
        blizzard_token = get_access_token()
    return blizzard_token

def search_blizzard(search_term, entity_type, access_token):
    """Searches for an entity and returns the first result's ID."""
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
        results = response.json().get('results')
        if results:
            return results[0]['data']['id']
    except Exception as e:
        print(f"Error during search: {e}")
    return None

def get_item_data(item_id, access_token):
    """Fetches data for a specific item using the access token."""
    url = f"https://us.api.blizzard.com/data/wow/item/{item_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = { "namespace": "static-us", "locale": "en_US" }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting item data: {e}")
        return None

def get_creature_data(creature_id, access_token):
    """Fetches data for a specific creature using the access token."""
    url = f"https://us.api.blizzard.com/data/wow/creature/{creature_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = { "namespace": "static-us", "locale": "en_US" }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting creature data: {e}")
        return None

def get_quest_data(quest_id, access_token):
    """Fetches data for a specific quest using the access token."""
    url = f"https://us.api.blizzard.com/data/wow/quest/{quest_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = { "namespace": "static-us", "locale": "en_US" }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting quest data: {e}")
        return None

def get_mount_data(mount_id, access_token):
    """Fetches data for a specific mount using the access token."""
    url = f"https://us.api.blizzard.com/data/wow/mount/{mount_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = { "namespace": "static-us", "locale": "en_US" }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting mount data: {e}")
        return None

def get_achievement_data(achievement_id, access_token):
    """Fetches data for a specific achievement using the access token."""
    url = f"https://us.api.blizzard.com/data/wow/achievement/{achievement_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = { "namespace": "static-us", "locale": "en_US" }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting achievement data: {e}")
        return None

def get_spell_data(spell_id, access_token):
    """Fetches data for a specific spell using the access token."""
    url = f"https://us.api.blizzard.com/data/wow/spell/{spell_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = { "namespace": "static-us", "locale": "en_US" }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting spell data: {e}")
        return None

def get_journal_instance_data(instance_id, access_token):
    """Fetches data for a specific journal instance (raid or dungeon) using the access token."""
    url = f"https://us.api.blizzard.com/data/wow/journal-instance/{instance_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = { "namespace": "static-us", "locale": "en_US" }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting journal instance data: {e}")
        return None

def get_reputation_faction_data(faction_id, access_token):
    """Fetches data for a specific reputation faction using the access token."""
    url = f"https://us.api.blizzard.com/data/wow/reputation-faction/{faction_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = { "namespace": "static-us", "locale": "en_US" }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting reputation faction data: {e}")
        return None

def get_title_data(title_id, access_token):
    """Fetches data for a specific title using the access token."""
    url = f"https://us.api.blizzard.com/data/wow/title/{title_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = { "namespace": "static-us", "locale": "en_US" }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting title data: {e}")
        return None

def get_toy_data(toy_id, access_token):
    """Fetches data for a specific toy using the access token."""
    url = f"https://us.api.blizzard.com/data/wow/toy/{toy_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = { "namespace": "static-us", "locale": "en_US" }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting toy data: {e}")
        return None

def get_pet_data(pet_id, access_token):
    """Fetches data for a specific battle pet using the access token."""
    url = f"https://us.api.blizzard.com/data/wow/pet/{pet_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = { "namespace": "static-us", "locale": "en_US" }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting pet data: {e}")
        return None

def get_heirloom_data(heirloom_id, access_token):
    """Fetches data for a specific heirloom using the access token."""
    url = f"https://us.api.blizzard.com/data/wow/heirloom/{heirloom_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = { "namespace": "static-us", "locale": "en_US" }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting heirloom data: {e}")
        return None

def get_wow_token_price(access_token):
    """Fetches the current WoW Token price using the dynamic namespace."""
    url = "https://us.api.blizzard.com/data/wow/token/"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = { "namespace": "dynamic-us", "locale": "en_US" }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        price_in_copper = data.get("price", 0)
        price_in_gold = price_in_copper // 10000
        return {"price": price_in_gold, "raw_data": data}
    except Exception as e:
        print(f"Error getting WoW Token price: {e}")
        return None

# --- Get Blizzard access token once when the script starts ---
print("Authenticating with Blizzard...")
blizzard_token = get_access_token()
if blizzard_token:
    print("Authentication successful!")
else:
    print("Could not authenticate with Blizzard. API lookups will be unavailable.")

# --- Ollama Client Setup ---
client = OpenAI(
    base_url='http://localhost:11434/v1',
    api_key='ollama',
)

# SYSTEM_PROMPT is used on EVERY message so the bot always stays strictly WoW-only
SYSTEM_PROMPT = wow_only_system_prompt

# Simple conversation memory - keeps the last 8 turns so the bot remembers context
history = []

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_creature",
            "description": "You MUST call this tool whenever the user asks about a specific WoW creature by name. Always call it first — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "The name of the creature, e.g. 'Arthas Menethil'"}
                },
                "required": ["search_term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_item",
            "description": "You MUST call this tool whenever the user asks about a specific WoW item by name or ID. Always call it first — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "The numeric item ID, e.g. '19019'"}
                },
                "required": ["item_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_item_by_name",
            "description": "You MUST call this tool whenever the user asks about a specific WoW item by name (not ID). Always call it first — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "The name of the item, e.g. 'Phantom Blade' or 'Thunderfury'"}
                },
                "required": ["search_term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_quest_by_name",
            "description": "You MUST call this tool whenever the user asks about a specific WoW quest by name. Always call it first — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "The name of the quest, e.g. 'The Lich King’s Fall' or 'Phantom Blade'"}
                },
                "required": ["search_term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_mount_by_name",
            "description": "You MUST call this tool whenever the user asks about a specific WoW mount by name. Always call it first — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "The name of the mount, e.g. 'Invincible' or 'Phantom Blade'"}
                },
                "required": ["search_term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_achievement_by_name",
            "description": "You MUST call this tool whenever the user asks about a specific WoW achievement by name. Always call it first — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "The name of the achievement, e.g. 'Ahead of the Curve' or 'Glory of the Legion Raider'"}
                },
                "required": ["search_term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_spell_by_name",
            "description": "You MUST call this tool whenever the user asks about a specific WoW spell or ability by name. Always call it first — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "The name of the spell or ability, e.g. 'Fireball' or 'Thunderfury'"}
                },
                "required": ["search_term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_journal_instance_by_name",
            "description": "You MUST call this tool whenever the user asks about a specific WoW raid, dungeon, or journal instance by name. Always call it first — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "The name of the raid or dungeon, e.g. 'Karazhan' or 'Stratholme'"}
                },
                "required": ["search_term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_faction_by_name",
            "description": "You MUST call this tool whenever the user asks about a specific WoW reputation faction by name. Always call it first — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "The name of the faction, e.g. 'The Nightfallen' or 'Cenarion Circle'"}
                },
                "required": ["search_term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_title_by_name",
            "description": "You MUST call this tool whenever the user asks about a specific WoW title by name. Always call it first — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "The name of the title, e.g. 'the Undying' or 'Loremaster'"}
                },
                "required": ["search_term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_toy_by_name",
            "description": "You MUST call this tool whenever the user asks about a specific WoW toy by name. Always call it first — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "The name of the toy, e.g. 'Red Rider Air Rifle' or 'Mr. Pinchy'"}
                },
                "required": ["search_term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_pet_by_name",
            "description": "You MUST call this tool whenever the user asks about a specific WoW battle pet by name. Always call it first — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "The name of the battle pet, e.g. 'Mr. Pinchy' or 'Pandaren Fire Spirit'"}
                },
                "required": ["search_term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_heirloom_by_name",
            "description": "You MUST call this tool whenever the user asks about a specific WoW heirloom by name. Always call it first — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "The name of the heirloom, e.g. 'Tattered Dreadmist Robe' or 'Vindictive Gladiator\'s Chain Helm'"}
                },
                "required": ["search_term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_wow_token_price",
            "description": "You MUST call this tool whenever the user asks about the current WoW Token price or gold value of a token. Always call it first — never answer from memory.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
    
]

# --- Updated Welcome Message ---
print("\n🤖 Hello! I'm your Loremaster's Companion. (Type 'quit' to exit)")
print("You can now ask me about anything in Azeroth naturally!")
print("Examples:")
print("   • Tell me about the mount Invincible")
print("   • What is the achievement Ahead of the Curve?")
print("   • How do I get the toy Mr. Pinchy?")
print("   • Tell me the story of the raid Karazhan")
print("   • What does the spell Thunderfury do?")
print("-" * 30)

# --- Main Chat Loop ---
while True:
    user_prompt = input("You: ")

    history.append({"role": "user", "content": user_prompt})
    # Keep only the last 8 turns
    if len(history) > 8:
        history = history[-8:]

    if user_prompt.lower() == 'quit':
        print("Goodbye! 👋")
        break

    # --- NEW TOOL-AWARE LLM CALL ---
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
] + history

    chat_completion = client.chat.completions.create(
        messages=messages,
        model="llama3.1:8b",
        tools=tools,
        tool_choice="auto"
    )

    response_message = chat_completion.choices[0].message

    # Check for tool calls (either in tool_calls or in content)
    tool_calls = response_message.tool_calls or []
    if not tool_calls and response_message.content:
        # Try to parse tool calls from content (for models that output tools in text)
        json_matches = re.findall(r'\[.*?\]', response_message.content)
        for match in json_matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, list) and parsed:
                    for item in parsed:
                        if isinstance(item, dict) and 'name' in item and 'arguments' in item:
                            # Create a mock tool_call object
                            class MockToolCall:
                                def __init__(self, name, args):
                                    self.function = type('Function', (), {'name': name, 'arguments': json.dumps(args)})()
                            tool_calls.append(MockToolCall(item['name'], item['arguments']))
                            break
            except:
                continue
        # Remove the tool call JSON from the content
        if tool_calls:
            response_message.content = re.sub(r'\[.*?\]$', '', response_message.content).strip()

    # If the model wants to call a tool
    if tool_calls:
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            try:
                function_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_result = "Error parsing tool arguments."
                continue

            if function_name == "search_creature":
                if not blizzard_token:
                    tool_result = "The Blizzard API is currently unavailable, so I cannot look up creature information."
                else:
                    search_term = function_args.get("search_term")
                    creature_id = search_blizzard(search_term, "creature", ensure_valid_token())
                    if creature_id:
                        creature_data = get_creature_data(creature_id, ensure_valid_token())
                        tool_result = f"Creature data received: {creature_data}" if creature_data else "No creature data found."
                    else:
                        tool_result = f"Could not find creature '{search_term}'."
            elif function_name == "lookup_item":
                if not blizzard_token:
                    tool_result = "The Blizzard API is currently unavailable, so I cannot look up item information."
                else:
                    item_id = function_args.get("item_id")
                    item_data = get_item_data(item_id, ensure_valid_token())
                    tool_result = f"Item data received: {item_data}" if item_data else f"No data for item ID {item_id}."
            elif function_name == "search_item_by_name":
                if not blizzard_token:
                    tool_result = "The Blizzard API is currently unavailable, so I cannot look up item information."
                else:
                    search_term = function_args.get("search_term")
                    item_id = search_blizzard(search_term, "item", ensure_valid_token())
                    if item_id:
                        item_data = get_item_data(item_id, ensure_valid_token())
                        tool_result = f"Item data received: {item_data}" if item_data else f"No data for item '{search_term}'."
                    else:
                        tool_result = f"Could not find item named '{search_term}'."
            elif function_name == "search_quest_by_name":
                if not blizzard_token:
                    tool_result = "The Blizzard API is currently unavailable, so I cannot look up quest information."
                else:
                    search_term = function_args.get("search_term")
                    quest_id = search_blizzard(search_term, "quest", ensure_valid_token())
                    if quest_id:
                        quest_data = get_quest_data(quest_id, ensure_valid_token())
                        tool_result = f"Quest data received: {quest_data}" if quest_data else f"No data for quest '{search_term}'."
                    else:
                        tool_result = f"Could not find quest named '{search_term}'."
            elif function_name == "search_mount_by_name":
                if not blizzard_token:
                    tool_result = "The Blizzard API is currently unavailable, so I cannot look up mount information."
                else:
                    search_term = function_args.get("search_term")
                    mount_id = search_blizzard(search_term, "mount", ensure_valid_token())
                    if mount_id:
                        mount_data = get_mount_data(mount_id, ensure_valid_token())
                        tool_result = f"Mount data received: {mount_data}" if mount_data else f"No data for mount '{search_term}'."
                    else:
                        tool_result = f"Could not find mount named '{search_term}'."
            elif function_name == "search_achievement_by_name":
                if not blizzard_token:
                    tool_result = "The Blizzard API is currently unavailable, so I cannot look up achievement information."
                else:
                    search_term = function_args.get("search_term")
                    achievement_id = search_blizzard(search_term, "achievement", ensure_valid_token())
                    if achievement_id:
                        achievement_data = get_achievement_data(achievement_id, ensure_valid_token())
                        tool_result = f"Achievement data received: {achievement_data}" if achievement_data else f"No data for achievement '{search_term}'."
                    else:
                        tool_result = f"Could not find achievement named '{search_term}'."
            elif function_name == "search_spell_by_name":
                if not blizzard_token:
                    tool_result = "The Blizzard API is currently unavailable, so I cannot look up spell information."
                else:
                    search_term = function_args.get("search_term")
                    spell_id = search_blizzard(search_term, "spell", ensure_valid_token())
                    if spell_id:
                        spell_data = get_spell_data(spell_id, ensure_valid_token())
                        tool_result = f"Spell data received: {spell_data}" if spell_data else f"No data for spell '{search_term}'."
                    else:
                        tool_result = f"Could not find spell named '{search_term}'."
            elif function_name == "search_journal_instance_by_name":
                if not blizzard_token:
                    tool_result = "The Blizzard API is currently unavailable, so I cannot look up journal instance information."
                else:
                    search_term = function_args.get("search_term")
                    instance_id = search_blizzard(search_term, "journal-instance", ensure_valid_token())
                    if instance_id:
                        instance_data = get_journal_instance_data(instance_id, ensure_valid_token())
                        tool_result = f"Journal instance data received: {instance_data}" if instance_data else f"No data for journal instance '{search_term}'."
                    else:
                        tool_result = f"Could not find journal instance named '{search_term}'."
            elif function_name == "search_faction_by_name":
                if not blizzard_token:
                    tool_result = "The Blizzard API is currently unavailable, so I cannot look up faction information."
                else:
                    search_term = function_args.get("search_term")
                    faction_id = search_blizzard(search_term, "reputation-faction", ensure_valid_token())
                    if faction_id:
                        faction_data = get_reputation_faction_data(faction_id, ensure_valid_token())
                        tool_result = f"Faction data received: {faction_data}" if faction_data else f"No data for faction '{search_term}'."
                    else:
                        tool_result = f"Could not find faction named '{search_term}'."
            elif function_name == "search_title_by_name":
                if not blizzard_token:
                    tool_result = "The Blizzard API is currently unavailable, so I cannot look up title information."
                else:
                    search_term = function_args.get("search_term")
                    title_id = search_blizzard(search_term, "title", ensure_valid_token())
                    if title_id:
                        title_data = get_title_data(title_id, ensure_valid_token())
                        tool_result = f"Title data received: {title_data}" if title_data else f"No data for title '{search_term}'."
                    else:
                        tool_result = f"Could not find title named '{search_term}'."
            elif function_name == "search_toy_by_name":
                if not blizzard_token:
                    tool_result = "The Blizzard API is currently unavailable, so I cannot look up toy information."
                else:
                    search_term = function_args.get("search_term")
                    toy_id = search_blizzard(search_term, "toy", ensure_valid_token())
                    if toy_id:
                        toy_data = get_toy_data(toy_id, ensure_valid_token())
                        tool_result = f"Toy data received: {toy_data}" if toy_data else f"No data for toy '{search_term}'."
                    else:
                        tool_result = f"Could not find toy named '{search_term}'."
            elif function_name == "search_pet_by_name":
                if not blizzard_token:
                    tool_result = "The Blizzard API is currently unavailable, so I cannot look up pet information."
                else:
                    search_term = function_args.get("search_term")
                    pet_id = search_blizzard(search_term, "pet", ensure_valid_token())
                    if pet_id:
                        pet_data = get_pet_data(pet_id, ensure_valid_token())
                        tool_result = f"Pet data received: {pet_data}" if pet_data else f"No data for pet '{search_term}'."
                    else:
                        tool_result = f"Could not find pet named '{search_term}'."
            elif function_name == "search_heirloom_by_name":
                if not blizzard_token:
                    tool_result = "The Blizzard API is currently unavailable, so I cannot look up heirloom information."
                else:
                    search_term = function_args.get("search_term")
                    heirloom_id = search_blizzard(search_term, "heirloom", ensure_valid_token())
                    if heirloom_id:
                        heirloom_data = get_heirloom_data(heirloom_id, ensure_valid_token())
                        tool_result = f"Heirloom data received: {heirloom_data}" if heirloom_data else f"No data for heirloom '{search_term}'."
                    else:
                        tool_result = f"Could not find heirloom named '{search_term}'."
            elif function_name == "get_wow_token_price":
                if not blizzard_token:
                    tool_result = "The Blizzard API is currently unavailable, so I cannot look up the WoW Token price."
                else:
                    token_data = get_wow_token_price(ensure_valid_token())
                    if token_data and "price" in token_data:
                        tool_result = f"WoW Token price received: Current price is {token_data['price']:,} gold."
                    else:
                        tool_result = "Could not retrieve current WoW Token price."
            else:
                tool_result = f"Unknown tool: {function_name}"

            # Add the tool result back to history and get final response
            history.append({"role": "assistant", "content": None, "tool_calls": [tool_call]})
            history.append({"role": "tool", "content": tool_result, "tool_call_id": tool_call.id})

        # Final LLM call with tool results
        final_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
            model="llama3.1:8b"
        )
        response = final_completion.choices[0].message.content
    else:
        response = response_message.content

    history.append({"role": "assistant", "content": response})
    # Keep only the last 8 turns
    if len(history) > 8:
        history = history[-8:]
    print(f"Loremaster: {response}")
    print("-" * 30)