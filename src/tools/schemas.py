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

    The search tools share this shape. The table below supplies the unique
    name, description, and example so those strings are not copied by hand.
    Descriptions must stay distinct: small models confuse similarly named tools.
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
        "You MUST call this tool whenever the user asks about a specific in-game WoW creature or NPC record by name (beasts, mobs, and named NPC game entities). Do NOT use this tool for lore-character biographies, playable races, playable classes, dungeon-journal bosses, creature families, or creature types. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the creature or NPC record, e.g. 'Young Nightsaber' or 'Stormwind Guard'",
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
    (
        "search_journal_encounter",
        "You MUST call this tool whenever the user asks about a specific WoW dungeon-journal boss or encounter (for example Professor Putricide or a named raid encounter write-up). Use this instead of search_creature for journal bosses. This is not a general lore-biography tool. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the journal encounter or boss, e.g. 'Professor Putricide' or 'The Lich King'",
    ),
    (
        "search_journal_expansion",
        "You MUST call this tool whenever the user asks about a WoW expansion's dungeon journal (which raids and dungeons belong to an expansion such as Wrath of the Lich King). Do NOT use this for a single raid or dungeon name; use search_journal_instance_by_name for that. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the expansion, e.g. 'Wrath of the Lich King' or 'The Burning Crusade'",
    ),
    (
        "search_playable_race",
        "You MUST call this tool whenever the user asks about a playable World of Warcraft race such as Human, Orc, or Night Elf. Do NOT use search_creature. This is not a lore-biography tool. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the playable race, e.g. 'Human' or 'Night Elf'",
    ),
    (
        "search_playable_class",
        "You MUST call this tool whenever the user asks about a playable World of Warcraft class such as Death Knight, Mage, or Paladin. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the playable class, e.g. 'Death Knight' or 'Mage'",
    ),
    (
        "search_specialization",
        "You MUST call this tool whenever the user asks about a playable class specialization such as Frost, Holy, or Fury, including official spec role or fantasy text. Do NOT invent talent trees. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the specialization, e.g. 'Frost' or 'Holy'",
    ),
    (
        "search_profession",
        "You MUST call this tool whenever the user asks about a WoW crafting or gathering profession such as Blacksmithing or Alchemy, including its official skill tiers. Do NOT use this for a named quest; use search_quest_by_name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the profession, e.g. 'Blacksmithing' or 'Alchemy'",
    ),
    (
        "search_item_set",
        "You MUST call this tool whenever the user asks about a named WoW item set such as Judgement Armor. Do NOT use this for a single item name; use search_item_by_name for individual items. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The name of the item set, e.g. 'Judgement Armor'",
    ),
    (
        "search_reputation_tiers",
        "You MUST call this tool whenever the user asks about reputation levels, standings, or tiers such as Hated, Friendly, Exalted, or Renown. For a named faction's identity use search_faction_by_name instead. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "A standing name or a generic request such as 'reputation levels' or 'Exalted'",
    ),
    (
        "search_creature_family",
        "You MUST call this tool whenever the user asks about a creature family (Wolf, Bear, Cat) or a creature type classification (Beast, Dragonkin, Undead, Humanoid). Do NOT use this for a named NPC, lore character, or journal boss; use search_creature or search_journal_encounter. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The family or type name, e.g. 'Wolf' or 'Dragonkin'",
    ),
    (
        "search_quest_group",
        "You MUST call this tool whenever the user asks about a WoW quest area (a zone's quest grouping), quest category, or quest type such as Raid or Dungeon. Do NOT use this for a named quest; use search_quest_by_name. This is non-negotiable. Always call the tool FIRST — never answer from memory or your training data, even if you think you know it.",
        "The quest area, category, or type name, e.g. 'Elwynn Forest' or 'Raid'",
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
