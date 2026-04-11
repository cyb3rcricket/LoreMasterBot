# Main bot runtime: client setup, tool schema, chat loop, and tool-call orchestration.
from openai import OpenAI
import json
import re
import time

from src.api import blizzard as blizzard_api
from src.api.blizzard import ensure_valid_token, get_access_token
from src.config import SYSTEM_PROMPT
from src.tools.handlers import TOOL_HANDLERS


# --- Get Blizzard access token once when the script starts ---
print("Authenticating with Blizzard...")
token, expires_in = get_access_token()
if token:
    blizzard_api.blizzard_token = token
    blizzard_api.token_expiry = time.time() + expires_in
    print("Authentication successful!")
else:
    print("Could not authenticate with Blizzard. API lookups will be unavailable.")

# --- Ollama Client Setup ---
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

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
                    "search_term": {"type": "string", "description": "The name of the heirloom, e.g. 'Tattered Dreadmist Robe' or 'Vindictive Gladiator's Chain Helm'"}
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


def run():
    global history

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

        if user_prompt.lower() == "quit":
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
            json_matches = re.findall(r"\[.*?\]", response_message.content)
            for match in json_matches:
                try:
                    parsed = json.loads(match)
                    if isinstance(parsed, list) and parsed:
                        for item in parsed:
                            if isinstance(item, dict) and "name" in item and "arguments" in item:
                                # Create a mock tool_call object
                                class MockToolCall:
                                    def __init__(self, name, args):
                                        self.function = type("Function", (), {"name": name, "arguments": json.dumps(args)})()

                                tool_calls.append(MockToolCall(item["name"], item["arguments"]))
                                break
                except Exception:
                    continue
            # Remove the tool call JSON from the content
            if tool_calls:
                response_message.content = re.sub(r"\[.*?\]$", "", response_message.content).strip()

        # If the model wants to call a tool
        if tool_calls:
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_result = "Error parsing tool arguments."
                    continue

                access_token = ensure_valid_token()
                if function_name in TOOL_HANDLERS:
                    tool_result = TOOL_HANDLERS[function_name](function_args, access_token)
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