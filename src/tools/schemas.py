# Tool schemas sent to the language model.
#
# A schema is a description of a function: its name, what it is for, and
# which arguments it accepts. The model reads this list and chooses a tool
# instead of inventing Warcraft facts from training data.
#
# Descriptions are forceful because a small local model will skip tools
# unless told it must call them first. "required" lists argument names that
# must be present. Changing this wording changes model behavior.


def _search_schema(name, description, search_term_description):
    """Build one name-search tool schema.

    The twelve search tools share this shape. The table below supplies the
    unique name, description, and example so those strings are not copied
    by hand twelve times. The wording itself must stay exactly as written.
    """
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": search_term_description}
                },
                "required": ["search_term"]
            }
        }
    }


# (tool name, model-facing description, search_term example text)
_SEARCH_TOOL_SPECS = (
    (
        "search_creature",
        "You MUST call this tool whenever the user asks about a specific WoW creature by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the creature, e.g. 'Arthas Menethil'",
    ),
    (
        "search_item_by_name",
        "You MUST call this tool whenever the user asks about a specific WoW item by name (e.g. 'Phantom Blade' or 'Thunderfury'). Do NOT use this tool for numeric item IDs; use lookup_item instead. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the item, e.g. 'Phantom Blade' or 'Thunderfury'",
    ),
    (
        "search_quest_by_name",
        "You MUST call this tool whenever the user asks about a specific WoW quest by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the quest, e.g. 'The Lich King’s Fall' or 'The Green Hills of Stranglethorn'",
    ),
    (
        "search_mount_by_name",
        "You MUST call this tool whenever the user asks about a specific WoW mount by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the mount, e.g. 'Invincible' or 'Mimiron\\'s Head'",
    ),
    (
        "search_achievement_by_name",
        "You MUST call this tool whenever the user asks about a specific WoW achievement by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the achievement, e.g. 'Ahead of the Curve' or 'Glory of the Legion Raider'",
    ),
    (
        "search_spell_by_name",
        "You MUST call this tool whenever the user asks about a specific WoW spell or ability by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the spell or ability, e.g. 'Fireball' or 'Frostbolt'",
    ),
    (
        "search_journal_instance_by_name",
        "You MUST call this tool whenever the user asks about a specific WoW raid, dungeon, or journal instance by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the raid or dungeon, e.g. 'Karazhan' or 'Stratholme'",
    ),
    (
        "search_faction_by_name",
        "You MUST call this tool whenever the user asks about a specific WoW reputation faction by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the faction, e.g. 'The Nightfallen' or 'Cenarion Circle'",
    ),
    (
        "search_title_by_name",
        "You MUST call this tool whenever the user asks about a specific WoW title by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the title, e.g. 'the Undying' or 'Loremaster'",
    ),
    (
        "search_toy_by_name",
        "You MUST call this tool whenever the user asks about a specific WoW toy by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the toy, e.g. 'Red Rider Air Rifle' or 'Mr. Pinchy'",
    ),
    (
        "search_pet_by_name",
        "You MUST call this tool whenever the user asks about a specific WoW battle pet by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the battle pet, e.g. 'Mr. Pinchy' or 'Pandaren Fire Spirit'",
    ),
    (
        "search_heirloom_by_name",
        "You MUST call this tool whenever the user asks about a specific WoW heirloom by name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the heirloom, e.g. 'Tattered Dreadmist Robe' or 'Vindictive Gladiator's Chain Helm'",
    ),
)

# lookup_item and get_wow_token_price stay handwritten: they do not take
# search_term. Item-by-ID must stay a different tool from item-by-name so
# the model cannot send "Thunderfury" to the numeric ID endpoint.
TOOL_SCHEMAS = [
    _search_schema(*_SEARCH_TOOL_SPECS[0]),
    {
        "type": "function",
        "function": {
            "name": "lookup_item",
            "description": "You MUST call this tool whenever the user asks about a specific WoW item by its numeric item ID (e.g. '19019'). Do NOT use this tool for item names; use search_item_by_name instead. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "The numeric item ID, e.g. '19019'"}
                },
                "required": ["item_id"]
            }
        }
    },
    *[_search_schema(*spec) for spec in _SEARCH_TOOL_SPECS[1:]],
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
    },
]
