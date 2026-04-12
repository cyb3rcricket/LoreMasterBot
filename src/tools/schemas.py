# Tool schemas for OpenAI API tool calling.

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_creature",
            "description": "You MUST call this tool whenever the user asks about a specific WoW creature by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
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
            "description": "You MUST call this tool whenever the user asks about a specific WoW item by name or ID. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
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
            "description": "You MUST call this tool whenever the user asks about a specific WoW item by name (not ID). This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
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
            "description": "You MUST call this tool whenever the user asks about a specific WoW quest by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
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
            "description": "You MUST call this tool whenever the user asks about a specific WoW mount by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
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
            "description": "You MUST call this tool whenever the user asks about a specific WoW achievement by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
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
            "description": "You MUST call this tool whenever the user asks about a specific WoW spell or ability by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
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
            "description": "You MUST call this tool whenever the user asks about a specific WoW raid, dungeon, or journal instance by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
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
            "description": "You MUST call this tool whenever the user asks about a specific WoW reputation faction by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
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
            "description": "You MUST call this tool whenever the user asks about a specific WoW title by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
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
            "description": "You MUST call this tool whenever the user asks about a specific WoW toy by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
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
            "description": "You MUST call this tool whenever the user asks about a specific WoW battle pet by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
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
            "description": "You MUST call this tool whenever the user asks about a specific WoW heirloom by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
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
            "description": "You MUST call this tool whenever the user asks about the current WoW Token price or gold value of a token. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]