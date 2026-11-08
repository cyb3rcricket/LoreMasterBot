# Blizzard API coverage scan

## Report back

- **HEAD / branch:** `774e8f1a3f4e581e77617f9dce8462103fdb2ed1` on `main`. That is the requested `774e8f1` ("Merge pull request #4 from cyb3rcricket/gradio-on-hardened"). Working tree at scan start had one untracked file, the job prompt. Nothing was checked out, reset, or pulled.
- **Counts:** covered 26 / clone-able 10 / bespoke 28 / not-lore 12 / retired 7. 83 endpoint groups, and every Game Data and Profile method is in exactly one group (162 game-data methods, 44 profile methods).
- **Schema size:** measured now **13840** characters across **24** tools (`json.dumps(TOOL_SCHEMAS)`, Python default separators). Compact separators are 13413. Per-tool projection for all 10 clone-able groups: **34 tools, 19261 characters**. The same ten groups behind one generic tool: **25 tools, 15030 characters**.
- **Recommendation:** Keep the 24 dedicated tools and add a resolver row (search versus index, detail path, optional media) consumed by `_search_and_fetch` and `_index_search_and_fetch`. Give the five lore-useful clone-able groups their own schema names, because `schemas.py` already says small models confuse similar tools, and land at 29 tools and 16652 characters. One enum tool would stop at 15030 characters and fights the existing item name-versus-id split; ten hand-copied tools would reach 19261.
- **Ground truth:** the 24-tool count, the 13,840-character schema, the three generic paths, and the covered-entity list are confirmed in code. Nothing in that list is refuted. Three corrections sit beside it. The token URL in code is `/data/wow/token/` (`src/api/blizzard.py:376`) while the reference lists `/data/wow/token/index`. `get_entity_media` (`src/api/blizzard.py:721`) is attached for four families only: playable class (`src/tools/handlers.py:365`), specialization (`src/tools/handlers.py:378`), profession (`src/tools/handlers.py:409`), and creature family (`src/tools/handlers.py:481`). Eight tools call `/data/wow/search/{type}` (`src/api/blizzard.py:236`) for types this Game Data reference does not list: quest (`src/tools/handlers.py:210`), achievement (`218`), journal-instance (`226`), reputation-faction (`230`), title (`234`), toy (`238`), pet (`242`), and heirloom (`246`).
- **UNVERIFIED rows:** **0** catalog rows. Every path and namespace below was read from the portal content JSON that the documentation pages render. The retired label on 7 groups is a currency judgment the portal does not state (those endpoints are still published). Seven index-only clone-able groups assume the index document contains `name`; that field was not fetched, because this job does not call the live API. Runtime success of the eight undocumented search URLs was also not called.

## How the docs were opened

`https://develop.battle.net/documentation/world-of-warcraft/game-data-apis` returns a 301 to `https://community.developer.battle.net/documentation/world-of-warcraft/game-data-apis`. That page is an Angular shell. The nav renders, and the endpoint list is served as JSON from the same host. These URLs were fetched and used:

- Game Data catalog, **DOCS-VERIFIED**: [https://develop.battle.net/documentation/world-of-warcraft/game-data-apis](https://develop.battle.net/documentation/world-of-warcraft/game-data-apis) via [https://community.developer.battle.net/api/pages/content/documentation/world-of-warcraft/game-data-apis.json](https://community.developer.battle.net/api/pages/content/documentation/world-of-warcraft/game-data-apis.json). 38 resources, 162 methods.
- Profile catalog, **DOCS-VERIFIED**: [https://develop.battle.net/documentation/world-of-warcraft/profile-apis](https://develop.battle.net/documentation/world-of-warcraft/profile-apis) via [https://community.developer.battle.net/api/pages/content/documentation/world-of-warcraft/profile-apis.json](https://community.developer.battle.net/api/pages/content/documentation/world-of-warcraft/profile-apis.json). 20 resources, 44 methods.
- Search guide, **DOCS-VERIFIED**: [https://develop.battle.net/documentation/world-of-warcraft/guides/search](https://develop.battle.net/documentation/world-of-warcraft/guides/search). It says only `realm` and `connected-realm` support search. The Game Data reference on the same portal lists more search methods. This scan treats the reference method list as the endpoint catalog and treats the guide as the query syntax.
- Namespaces, **DOCS-VERIFIED**: [https://develop.battle.net/documentation/world-of-warcraft/guides/namespaces](https://develop.battle.net/documentation/world-of-warcraft/guides/namespaces). Categories are `static-{region}`, `dynamic-{region}`, and `profile-{region}`.
- Known issues, **DOCS-VERIFIED**: [https://develop.battle.net/documentation/world-of-warcraft/guides/known-issues](https://develop.battle.net/documentation/world-of-warcraft/guides/known-issues). The page only discusses child documents that 404 or 401. It does not retire any API.
- WoW landing and the documentation index, **DOCS-VERIFIED**: [https://develop.battle.net/documentation/world-of-warcraft](https://develop.battle.net/documentation/world-of-warcraft) and [https://develop.battle.net/documentation](https://develop.battle.net/documentation).
- `documentation/world-of-warcraft/community-apis` returns **404**. The current WoW landing lists guides, Game Data APIs, and Profile APIs.

Diablo III, Hearthstone, StarCraft II, and WoW Classic each have their own portal section (player profile, cards and decks, ladder, and classic class/race data respectively) and are out of scope. Hosts, from the Game Data page: `{region}.api.blizzard.com` for us, eu, kr, and tw, and `gateway.battlenet.com.cn` for China. The bot hardcodes `us.api.blizzard.com`.

Namespace defaults below are the example values on each method (`static-us`, `dynamic-us`, `profile-us`, and `dynamic-cn` for the China token index). The category column drops the region.

## Ground truth

| Claim | Result | Where |
| --- | --- | --- |
| 24 tools, schemas and handlers agree | Confirmed. 24 names, same set, same order. | `src/tools/schemas.py` `TOOL_SCHEMAS`; `src/tools/handlers.py` `TOOL_HANDLERS`; `tests/test_blizzard_expansion.py` asserts the sets match |
| Serialized schemas about 13,840 characters | Confirmed. `json.dumps(TOOL_SCHEMAS)` is 13840. Compact form is 13413. | Measured in this scan by importing `TOOL_SCHEMAS` |
| Generic search, index, and detail paths | Confirmed. | `search_blizzard` builds `/data/wow/search/{type}`; `get_index_data` builds `/data/wow/{type}/index`; `_get_entity_data` builds `/data/wow/{type}/{id}` |
| `get_*_data` wrappers and `get_entity_media` | Confirmed. Media is fetched only when a handler passes `media_type`. | `get_entity_media` / `with_official_media` in `src/api/blizzard.py`; call sites in `src/tools/handlers.py` for playable class, specialization, profession, and creature family |
| Covered entity list | Confirmed. Every named family has a tool. Profession skill tier is inside `search_profession`. Quest area, category, and type share `search_quest_group`. Creature family and creature type share `search_creature_family`. | Handlers in `src/tools/handlers.py` |

Tool order: `search_creature`, `lookup_item`, `search_item_by_name`, `search_quest_by_name`, `search_mount_by_name`, `search_achievement_by_name`, `search_spell_by_name`, `search_journal_instance_by_name`, `search_faction_by_name`, `search_title_by_name`, `search_toy_by_name`, `search_pet_by_name`, `search_heirloom_by_name`, `search_journal_encounter`, `search_journal_expansion`, `search_playable_race`, `search_playable_class`, `search_specialization`, `search_profession`, `search_item_set`, `search_reputation_tiers`, `search_creature_family`, `search_quest_group`, `get_wow_token_price`.

`search_blizzard` and `_get_entity_data` always send `namespace=static-us`. `get_wow_token_price` is the one dynamic call, and its path is `/data/wow/token/` rather than the documented `/data/wow/token/index`.

## 1. Inventory

Media "yes" means the handler attaches `official_media`. Several documented media methods exist for rows marked no.

| Entity | Tool | Resolution | Detail getter | Media |
| --- | --- | --- | --- | --- |
| Creature | `search_creature` | Search API `/data/wow/search/creature` (documented `name.en_US`) | `get_creature_data` | no |
| Item by id | `lookup_item` | Numeric id only. Non-digits never call the API. | `get_item_data` | no |
| Item by name | `search_item_by_name` | Search API `/data/wow/search/item` (documented `name.en_US`). Famous names skip the network via `famous_items`. | `get_item_data` | no |
| Quest | `search_quest_by_name` | Search API `/data/wow/search/quest` (not in the current reference) | `get_quest_data` | no |
| Mount | `search_mount_by_name` | Search API `/data/wow/search/mount` (documented `name.en_US`) | `get_mount_data` | no |
| Achievement | `search_achievement_by_name` | Search API `/data/wow/search/achievement` (not in the current reference) | `get_achievement_data` | no |
| Spell | `search_spell_by_name` | Search API `/data/wow/search/spell` (documented `name.en_US`) | `get_spell_data` | no |
| Journal instance | `search_journal_instance_by_name` | Search API `/data/wow/search/journal-instance` (not in the current reference) | `get_journal_instance_data` | no |
| Reputation faction | `search_faction_by_name` | Search API `/data/wow/search/reputation-faction` (not in the current reference) | `get_reputation_faction_data` | no |
| Title | `search_title_by_name` | Search API `/data/wow/search/title` (not in the current reference) | `get_title_data` | no |
| Toy | `search_toy_by_name` | Search API `/data/wow/search/toy` (not in the current reference) | `get_toy_data` | no |
| Pet | `search_pet_by_name` | Search API `/data/wow/search/pet` (not in the current reference) | `get_pet_data` | no |
| Heirloom | `search_heirloom_by_name` | Search API `/data/wow/search/heirloom` (not in the current reference) | `get_heirloom_data` | no |
| Journal encounter | `search_journal_encounter` | Search API `/data/wow/search/journal-encounter`, then the encounter index | `get_journal_encounter_data` | no |
| Journal expansion | `search_journal_expansion` | Static index `/data/wow/journal-expansion/index` | `get_journal_expansion_data` | no |
| Playable race | `search_playable_race` | Static index `/data/wow/playable-race/index` | `get_playable_race_data` | no |
| Playable class | `search_playable_class` | Static index `/data/wow/playable-class/index` | `get_playable_class_data` | yes (`playable-class`) |
| Specialization | `search_specialization` | Static index `/data/wow/playable-specialization/index` | `get_playable_specialization_data` | yes (`playable-specialization`) |
| Profession and skill tier | `search_profession` | Static index `/data/wow/profession/index`, then an optional skill-tier document | `get_profession_data`, `get_profession_skill_tier_data` | yes (`profession`) |
| Item set | `search_item_set` | Static index `/data/wow/item-set/index` | `get_item_set_data` | no |
| Reputation tiers | `search_reputation_tiers` | Index `/data/wow/reputation-tiers/index`, then a document scan in `find_reputation_tiers` | `get_reputation_tiers_data` | no |
| Creature family | `search_creature_family` | Static index `/data/wow/creature-family/index` | `get_creature_family_data` | yes (`creature-family`) |
| Creature type | `search_creature_family` | Static index `/data/wow/creature-type/index` | `get_creature_type_data` | no |
| Quest area | `search_quest_group` | Static index `/data/wow/quest/area/index` | `get_quest_area_data` | no |
| Quest category | `search_quest_group` | Static index `/data/wow/quest/category/index` | `get_quest_category_data` | no |
| Quest type | `search_quest_group` | Static index `/data/wow/quest/type/index` | `get_quest_type_data` | no |
| WoW Token | `get_wow_token_price` | No search. Code path `/data/wow/token/` on `dynamic-us`. | `get_wow_token_price` | no |

Search-API tools share `_search_and_fetch`. Index tools share `_index_search_and_fetch`, except profession, creature family/type, quest group, and reputation tiers, which have their own handlers on top of the same index helpers.

## 2. Catalog

Paths, namespace defaults, and example search fields below are **DOCS-VERIFIED** from the two content documents linked above. Path parameters such as `{achievementId}` are omitted from the search-field column. `orderby` and `_page` are listed when the reference includes them on a search method.

### Game Data APIs

#### Achievement API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Achievements Index | `/data/wow/achievement/index` | `static-us` |  |
| Achievement | `/data/wow/achievement/{achievementId}` | `static-us` |  |
| Achievement Media | `/data/wow/media/achievement/{achievementId}` | `static-us` |  |
| Achievement Categories Index | `/data/wow/achievement-category/index` | `static-us` |  |
| Achievement Category | `/data/wow/achievement-category/{achievementCategoryId}` | `static-us` |  |

#### Auction House API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Auctions | `/data/wow/connected-realm/{connectedRealmId}/auctions` | `dynamic-us` |  |
| Commodities | `/data/wow/auctions/commodities` | `dynamic-us` |  |

#### Azerite Essence API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Azerite Essences Index | `/data/wow/azerite-essence/index` | `static-us` |  |
| Azerite Essence | `/data/wow/azerite-essence/{azeriteEssenceId}` | `static-us` |  |
| Azerite Essence Search | `/data/wow/search/azerite-essence` | `static-us` | `allowed_specializations.id`, `orderby`, `_page` |
| Azerite Essence Media | `/data/wow/media/azerite-essence/{azeriteEssenceId}` | `static-us` |  |

#### Connected Realm API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Connected Realms Index | `/data/wow/connected-realm/index` | `dynamic-us` |  |
| Connected Realm | `/data/wow/connected-realm/{connectedRealmId}` | `dynamic-us` |  |
| Connected Realm Search | `/data/wow/search/connected-realm` | `dynamic-us` | `status.type`, `realms.timezone`, `orderby`, `_page` |

#### Covenant API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Covenant Index | `/data/wow/covenant/index` | `static-us` |  |
| Covenant | `/data/wow/covenant/{covenantId}` | `static-us` |  |
| Covenant Media | `/data/wow/media/covenant/{covenantId}` | `static-us` |  |
| Soulbind Index | `/data/wow/covenant/soulbind/index` | `static-us` |  |
| Soulbind | `/data/wow/covenant/soulbind/{soulbindId}` | `static-us` |  |
| Conduit Index | `/data/wow/covenant/conduit/index` | `static-us` |  |
| Conduit | `/data/wow/covenant/conduit/{conduitId}` | `static-us` |  |

#### Creature API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Creature | `/data/wow/creature/{creatureId}` | `static-us` |  |
| Creature Search | `/data/wow/search/creature` | `static-us` | `name.en_US`, `orderby`, `_page` |
| Creature Display Media | `/data/wow/media/creature-display/{creatureDisplayId}` | `static-us` |  |
| Creature Families Index | `/data/wow/creature-family/index` | `static-us` |  |
| Creature Family | `/data/wow/creature-family/{creatureFamilyId}` | `static-us` |  |
| Creature Family Media | `/data/wow/media/creature-family/{creatureFamilyId}` | `static-us` |  |
| Creature Types Index | `/data/wow/creature-type/index` | `static-us` |  |
| Creature Type | `/data/wow/creature-type/{creatureTypeId}` | `static-us` |  |

#### Guild Crest API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Guild Crest Components Index | `/data/wow/guild-crest/index` | `static-us` |  |
| Guild Crest Border Media | `/data/wow/media/guild-crest/border/{borderId}` | `static-us` |  |
| Guild Crest Emblem Media | `/data/wow/media/guild-crest/emblem/{emblemId}` | `static-us` |  |

#### Heirloom API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Heirloom Index | `/data/wow/heirloom/index` | `static-us` |  |
| Heirloom | `/data/wow/heirloom/{heirloomId}` | `static-us` |  |

#### Housing Decor API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Decor Index | `/data/wow/decor/index` | `static-us` |  |
| Decor | `/data/wow/decor/{decorId}` | `static-us` |  |
| Decor Search | `/data/wow/search/decor` | `static-us` | `name.en_US`, `orderby`, `_page` |
| Fixture Index | `/data/wow/fixture/index` | `static-us` |  |
| Fixture | `/data/wow/fixture/{fixtureId}` | `static-us` |  |
| Fixture Search | `/data/wow/search/fixture` | `static-us` | `name.en_US`, `orderby`, `_page` |
| Fixture Hook Index | `/data/wow/fixture-hook/index` | `static-us` |  |
| Fixture Hook | `/data/wow/fixture-hook/{fixtureHookId}` | `static-us` |  |
| Fixture Hook Search | `/data/wow/search/fixture-hook` | `static-us` | `orderby`, `_page` |
| Room Index | `/data/wow/room/index` | `static-us` |  |
| Room | `/data/wow/room/{roomId}` | `static-us` |  |
| Room Search | `/data/wow/search/room` | `static-us` | `name.en_US`, `orderby`, `_page` |

#### Item API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Item | `/data/wow/item/{itemId}` | `static-us` |  |
| Item Search | `/data/wow/search/item` | `static-us` | `name.en_US`, `orderby`, `_page` |
| Item Media | `/data/wow/media/item/{itemId}` | `static-us` |  |
| Item Classes Index | `/data/wow/item-class/index` | `static-us` |  |
| Item Class | `/data/wow/item-class/{itemClassId}` | `static-us` |  |
| Item Sets Index | `/data/wow/item-set/index` | `static-us` |  |
| Item Set | `/data/wow/item-set/{itemSetId}` | `static-us` |  |
| Item Subclass | `/data/wow/item-class/{itemClassId}/item-subclass/{itemSubclassId}` | `static-us` |  |

#### Item Appearance API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Item Appearance | `/data/wow/item-appearance/{appearanceId}` | `static-us` |  |
| Item Appearance Search | `/data/wow/search/item-appearance` | `static-us` | `slot.type`, `orderby`, `_page` |
| Item Appearance Sets Index | `/data/wow/item-appearance/set/index` | `static-us` |  |
| Item Appearance Set | `/data/wow/item-appearance/set/{appearanceSetId}` | `static-us` |  |
| Item Appearance Slot Index | `/data/wow/item-appearance/slot/index` | `static-us` |  |
| Item Appearance Slot | `/data/wow/item-appearance/slot/{slotType}` | `static-us` |  |

#### Journal API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Journal Expansions Index | `/data/wow/journal-expansion/index` | `static-us` |  |
| Journal Expansion | `/data/wow/journal-expansion/{journalExpansionId}` | `static-us` |  |
| Journal Encounters Index | `/data/wow/journal-encounter/index` | `static-us` |  |
| Journal Encounter | `/data/wow/journal-encounter/{journalEncounterId}` | `static-us` |  |
| Journal Encounter Search | `/data/wow/search/journal-encounter` | `static-us` | `instance.name.en_US`, `orderby`, `_page` |
| Journal Instances Index | `/data/wow/journal-instance/index` | `static-us` |  |
| Journal Instance | `/data/wow/journal-instance/{journalInstanceId}` | `static-us` |  |
| Journal Instance Media | `/data/wow/media/journal-instance/{journalInstanceId}` | `static-us` |  |

#### Media Search API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Media Search | `/data/wow/search/media` | `static-us` | `tags`, `orderby`, `_page` |

#### Modified Crafting API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Modified Crafting Index | `/data/wow/modified-crafting/index` | `static-us` |  |
| Modified Crafting Category Index | `/data/wow/modified-crafting/category/index` | `static-us` |  |
| Modified Crafting Category | `/data/wow/modified-crafting/category/{categoryId}` | `static-us` |  |
| Modified Crafting Reagent Slot Type Index | `/data/wow/modified-crafting/reagent-slot-type/index` | `static-us` |  |
| Modified Crafting Reagent Slot Type | `/data/wow/modified-crafting/reagent-slot-type/{slotTypeId}` | `static-us` |  |

#### Mount API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Mounts Index | `/data/wow/mount/index` | `static-us` |  |
| Mount | `/data/wow/mount/{mountId}` | `static-us` |  |
| Mount Search | `/data/wow/search/mount` | `static-us` | `name.en_US`, `orderby`, `_page` |

#### Mythic Keystone Affix API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Mythic Keystone Affixes Index | `/data/wow/keystone-affix/index` | `static-us` |  |
| Mythic Keystone Affix | `/data/wow/keystone-affix/{keystoneAffixId}` | `static-us` |  |
| Mythic Keystone Affix Media | `/data/wow/media/keystone-affix/{keystoneAffixId}` | `static-us` |  |

#### Mythic Keystone Dungeon API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Mythic Keystone Index | `/data/wow/mythic-keystone/index` | `dynamic-us` |  |
| Mythic Keystone Dungeons Index | `/data/wow/mythic-keystone/dungeon/index` | `dynamic-us` |  |
| Mythic Keystone Dungeon | `/data/wow/mythic-keystone/dungeon/{dungeonId}` | `dynamic-us` |  |
| Mythic Keystone Periods Index | `/data/wow/mythic-keystone/period/index` | `dynamic-us` |  |
| Mythic Keystone Period | `/data/wow/mythic-keystone/period/{periodId}` | `dynamic-us` |  |
| Mythic Keystone Seasons Index | `/data/wow/mythic-keystone/season/index` | `dynamic-us` |  |
| Mythic Keystone Season | `/data/wow/mythic-keystone/season/{seasonId}` | `dynamic-us` |  |

#### Mythic Keystone Leaderboard API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Mythic Keystone Leaderboards Index | `/data/wow/connected-realm/{connectedRealmId}/mythic-leaderboard/index` | `dynamic-us` |  |
| Mythic Keystone Leaderboard | `/data/wow/connected-realm/{connectedRealmId}/mythic-leaderboard/{dungeonId}/period/{period}` | `dynamic-us` |  |

#### Mythic Raid Leaderboard API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Mythic Raid Leaderboard | `/data/wow/leaderboard/hall-of-fame/{raid}/{faction}` | `dynamic-us` |  |

#### Neighborhood API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Neighborhood Map Index | `/data/wow/neighborhood-map/index` | `dynamic-us` |  |
| Neighborhood Map | `/data/wow/neighborhood-map/{neighborhoodMapId}` | `dynamic-us` |  |
| Neighborhood | `/data/wow/neighborhood-map/{neighborhoodMapId}/neighborhood/{neighborhoodId}` | `dynamic-us` |  |

#### Pet API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Pets Index | `/data/wow/pet/index` | `static-us` |  |
| Pet | `/data/wow/pet/{petId}` | `static-us` |  |
| Pet Media | `/data/wow/media/pet/{petId}` | `static-us` |  |
| Pet Abilities Index | `/data/wow/pet-ability/index` | `static-us` |  |
| Pet Ability | `/data/wow/pet-ability/{petAbilityId}` | `static-us` |  |
| Pet Ability Media | `/data/wow/media/pet-ability/{petAbilityId}` | `static-us` |  |

#### Playable Class API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Playable Classes Index | `/data/wow/playable-class/index` | `static-us` |  |
| Playable Class | `/data/wow/playable-class/{classId}` | `static-us` |  |
| Playable Class Media | `/data/wow/media/playable-class/{playableClassId}` | `static-us` |  |
| PvP Talent Slots | `/data/wow/playable-class/{classId}/pvp-talent-slots` | `static-us` |  |

#### Playable Race API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Playable Races Index | `/data/wow/playable-race/index` | `static-us` |  |
| Playable Race | `/data/wow/playable-race/{playableRaceId}` | `static-us` |  |

#### Playable Specialization API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Playable Specializations Index | `/data/wow/playable-specialization/index` | `static-us` |  |
| Playable Specialization | `/data/wow/playable-specialization/{specId}` | `static-us` |  |
| Playable Specialization Media | `/data/wow/media/playable-specialization/{specId}` | `static-us` |  |

#### Power Type API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Power Types Index | `/data/wow/power-type/index` | `static-us` |  |
| Power Type | `/data/wow/power-type/{powerTypeId}` | `static-us` |  |

#### Profession API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Professions Index | `/data/wow/profession/index` | `static-us` |  |
| Profession | `/data/wow/profession/{professionId}` | `static-us` |  |
| Profession Media | `/data/wow/media/profession/{professionId}` | `static-us` |  |
| Profession Skill Tier | `/data/wow/profession/{professionId}/skill-tier/{skillTierId}` | `static-us` |  |
| Recipe | `/data/wow/recipe/{recipeId}` | `static-us` |  |
| Recipe Media | `/data/wow/media/recipe/{recipeId}` | `static-us` |  |

#### PvP Season API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| PvP Seasons Index | `/data/wow/pvp-season/index` | `dynamic-us` |  |
| PvP Season | `/data/wow/pvp-season/{pvpSeasonId}` | `dynamic-us` |  |
| PvP Leaderboards Index | `/data/wow/pvp-season/{pvpSeasonId}/pvp-leaderboard/index` | `dynamic-us` |  |
| PvP Leaderboard | `/data/wow/pvp-season/{pvpSeasonId}/pvp-leaderboard/{pvpBracket}` | `dynamic-us` |  |
| PvP Rewards Index | `/data/wow/pvp-season/{pvpSeasonId}/pvp-reward/index` | `dynamic-us` |  |

#### PvP Tier API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| PvP Tiers Index | `/data/wow/pvp-tier/index` | `static-us` |  |
| PvP Tier | `/data/wow/pvp-tier/{pvpTierId}` | `static-us` |  |
| PvP Tier Media | `/data/wow/media/pvp-tier/{pvpTierId}` | `static-us` |  |

#### Quest API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Quests Index | `/data/wow/quest/index` | `static-us` |  |
| Quest | `/data/wow/quest/{questId}` | `static-us` |  |
| Quest Categories Index | `/data/wow/quest/category/index` | `static-us` |  |
| Quest Category | `/data/wow/quest/category/{questCategoryId}` | `static-us` |  |
| Quest Areas Index | `/data/wow/quest/area/index` | `static-us` |  |
| Quest Area | `/data/wow/quest/area/{questAreaId}` | `static-us` |  |
| Quest Types Index | `/data/wow/quest/type/index` | `static-us` |  |
| Quest Type | `/data/wow/quest/type/{questTypeId}` | `static-us` |  |

#### Realm API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Realms Index | `/data/wow/realm/index` | `dynamic-us` |  |
| Realm | `/data/wow/realm/{realmSlug}` | `dynamic-us` |  |
| Realm Search | `/data/wow/search/realm` | `dynamic-us` | `timezone`, `orderby`, `_page` |

#### Region API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Regions Index | `/data/wow/region/index` | `dynamic-us` |  |
| Region | `/data/wow/region/{regionId}` | `dynamic-us` |  |

#### Reputations API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Reputation Factions Index | `/data/wow/reputation-faction/index` | `static-us` |  |
| Reputation Faction | `/data/wow/reputation-faction/{reputationFactionId}` | `static-us` |  |
| Reputation Tiers Index | `/data/wow/reputation-tiers/index` | `static-us` |  |
| Reputation Tiers | `/data/wow/reputation-tiers/{reputationTiersId}` | `static-us` |  |

#### Spell API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Spell | `/data/wow/spell/{spellId}` | `static-us` |  |
| Spell Media | `/data/wow/media/spell/{spellId}` | `static-us` |  |
| Spell Search | `/data/wow/search/spell` | `static-us` | `name.en_US`, `orderby`, `_page` |

#### Talent API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Talent Tree Index | `/data/wow/talent-tree/index` | `static-us` |  |
| Talent Tree | `/data/wow/talent-tree/{talentTreeId}/playable-specialization/{specId}` | `static-us` |  |
| Talent Tree Nodes | `/data/wow/talent-tree/{talentTreeId}` | `static-us` |  |
| Talents Index | `/data/wow/talent/index` | `static-us` |  |
| Talent | `/data/wow/talent/{talentId}` | `static-us` |  |
| PvP Talents Index | `/data/wow/pvp-talent/index` | `static-us` |  |
| PvP Talent | `/data/wow/pvp-talent/{pvpTalentId}` | `static-us` |  |

#### Tech Talent API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Tech Talent Tree Index | `/data/wow/tech-talent-tree/index` | `static-us` |  |
| Tech Talent Tree | `/data/wow/tech-talent-tree/{techTalentTreeId}` | `static-us` |  |
| Tech Talent Index | `/data/wow/tech-talent/index` | `static-us` |  |
| Tech Talent | `/data/wow/tech-talent/{techTalentId}` | `static-us` |  |
| Tech Talent Media | `/data/wow/media/tech-talent/{techTalentId}` | `static-us` |  |

#### Title API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Titles Index | `/data/wow/title/index` | `static-us` |  |
| Title | `/data/wow/title/{titleId}` | `static-us` |  |

#### Toy API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Toy Index | `/data/wow/toy/index` | `static-us` |  |
| Toy | `/data/wow/toy/{toyId}` | `static-us` |  |

#### WoW Token API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| WoW Token Index (US, EU, KR, TW) | `/data/wow/token/index` | `dynamic-us` |  |
| WoW Token Index (CN) | `/data/wow/token/index` | `dynamic-cn` |  |


### Profile APIs

#### Account Profile API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Account Profile Summary | `/profile/user/wow` | `profile-us` |  |
| Protected Character Profile Summary | `/profile/user/wow/protected-character/{realmId}-{characterId}` | `profile-us` |  |
| Account Collections Index | `/profile/user/wow/collections` | `profile-us` |  |
| Account Decor Collection Summary | `/profile/user/wow/collections/decor` | `profile-us` |  |
| Account Heirlooms Collection Summary | `/profile/user/wow/collections/heirlooms` | `profile-us` |  |
| Account Mounts Collection Summary | `/profile/user/wow/collections/mounts` | `profile-us` |  |
| Account Pets Collection Summary | `/profile/user/wow/collections/pets` | `profile-us` |  |
| Account Toys Collection Summary | `/profile/user/wow/collections/toys` | `profile-us` |  |
| Account Transmog Collection Summary | `/profile/user/wow/collections/transmogs` | `profile-us` |  |

#### Character Achievements API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Achievements Summary | `/profile/wow/character/{realmSlug}/{characterName}/achievements` | `profile-us` |  |
| Character Achievement Statistics | `/profile/wow/character/{realmSlug}/{characterName}/achievements/statistics` | `profile-us` |  |

#### Character Appearance API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Appearance Summary | `/profile/wow/character/{realmSlug}/{characterName}/appearance` | `profile-us` |  |

#### Character Collections API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Collections Index | `/profile/wow/character/{realmSlug}/{characterName}/collections` | `profile-us` |  |
| Character Decor Collection Summary | `/profile/wow/character/{realmSlug}/{characterName}/collections/decor` | `profile-us` |  |
| Character Heirlooms Collection Summary | `/profile/wow/character/{realmSlug}/{characterName}/collections/heirlooms` | `profile-us` |  |
| Character Mounts Collection Summary | `/profile/wow/character/{realmSlug}/{characterName}/collections/mounts` | `profile-us` |  |
| Character Pets Collection Summary | `/profile/wow/character/{realmSlug}/{characterName}/collections/pets` | `profile-us` |  |
| Character Toys Collection Summary | `/profile/wow/character/{realmSlug}/{characterName}/collections/toys` | `profile-us` |  |
| Character Transmog Collection Summary | `/profile/wow/character/{realmSlug}/{characterName}/collections/transmogs` | `profile-us` |  |

#### Character Encounters API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Encounters Summary | `/profile/wow/character/{realmSlug}/{characterName}/encounters` | `profile-us` |  |
| Character Dungeons | `/profile/wow/character/{realmSlug}/{characterName}/encounters/dungeons` | `profile-us` |  |
| Character Raids | `/profile/wow/character/{realmSlug}/{characterName}/encounters/raids` | `profile-us` |  |

#### Character Equipment API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Equipment Summary | `/profile/wow/character/{realmSlug}/{characterName}/equipment` | `profile-us` |  |

#### Character House API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character House Summary | `/profile/wow/character/{realmSlug}/{characterName}/house/house-{houseNumber}` | `profile-us` |  |

#### Character Hunter Pets API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Hunter Pets Summary | `/profile/wow/character/{realmSlug}/{characterName}/hunter-pets` | `profile-us` |  |

#### Character Media API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Media Summary | `/profile/wow/character/{realmSlug}/{characterName}/character-media` | `profile-us` |  |

#### Character Mythic Keystone Profile API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Mythic Keystone Profile Index | `/profile/wow/character/{realmSlug}/{characterName}/mythic-keystone-profile` | `profile-us` |  |
| Character Mythic Keystone Season Details | `/profile/wow/character/{realmSlug}/{characterName}/mythic-keystone-profile/season/{seasonId}` | `profile-us` |  |

#### Character Professions API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Professions Summary | `/profile/wow/character/{realmSlug}/{characterName}/professions` | `profile-us` |  |

#### Character Profile API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Profile Summary | `/profile/wow/character/{realmSlug}/{characterName}` | `profile-us` |  |
| Character Profile Status | `/profile/wow/character/{realmSlug}/{characterName}/status` | `profile-us` |  |

#### Character PvP API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character PvP Bracket Statistics | `/profile/wow/character/{realmSlug}/{characterName}/pvp-bracket/{pvpBracket}` | `profile-us` |  |
| Character PvP Summary | `/profile/wow/character/{realmSlug}/{characterName}/pvp-summary` | `profile-us` |  |

#### Character Quests API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Quests | `/profile/wow/character/{realmSlug}/{characterName}/quests` | `profile-us` |  |
| Character Completed Quests | `/profile/wow/character/{realmSlug}/{characterName}/quests/completed` | `profile-us` |  |

#### Character Reputations API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Reputations Summary | `/profile/wow/character/{realmSlug}/{characterName}/reputations` | `profile-us` |  |

#### Character Soulbinds API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Soulbinds | `/profile/wow/character/{realmSlug}/{characterName}/soulbinds` | `profile-us` |  |

#### Character Specializations API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Specializations Summary | `/profile/wow/character/{realmSlug}/{characterName}/specializations` | `profile-us` |  |

#### Character Statistics API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Statistics Summary | `/profile/wow/character/{realmSlug}/{characterName}/statistics` | `profile-us` |  |

#### Character Titles API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Character Titles Summary | `/profile/wow/character/{realmSlug}/{characterName}/titles` | `profile-us` |  |

#### Guild API

| Method | Path | Namespace default | Example search fields |
| --- | --- | --- | --- |
| Guild | `/data/wow/guild/{realmSlug}/{nameSlug}` | `profile-us` |  |
| Guild Activity | `/data/wow/guild/{realmSlug}/{nameSlug}/activity` | `profile-us` |  |
| Guild Achievements | `/data/wow/guild/{realmSlug}/{nameSlug}/achievements` | `profile-us` |  |
| Guild Roster | `/data/wow/guild/{realmSlug}/{nameSlug}/roster` | `profile-us` |  |


## 3. Gap table

One row per endpoint group. Covered rows stay in the table. Paths are **DOCS-VERIFIED**. Notes describe the bot when a tool already calls the group, and they flag arguable labels in one line.

Primary counts: covered 26, clone-able 10, bespoke 28, not-lore 12, retired 7.

### Game Data

| Endpoint group | Paths | Namespace | Name search or index? | Classification | Notes |
| --- | --- | --- | --- | --- | --- |
| Achievement | `/data/wow/achievement/index`<br>`/data/wow/achievement/{achievementId}`<br>`/data/wow/media/achievement/{achievementId}` | static | index `/data/wow/achievement/index` | **COVERED** | Tool `search_achievement_by_name` calls `/data/wow/search/achievement`, which this reference does not list. Documented access is the index plus id. Media endpoint exists; the tool does not attach it. |
| Achievement category | `/data/wow/achievement-category/index`<br>`/data/wow/achievement-category/{achievementCategoryId}` | static | index `/data/wow/achievement-category/index` | **CLONE-ABLE** | Static index plus id, same shape as item sets. Whether index entries include `name` was not fetched (live API not called). |
| Auctions and commodities | `/data/wow/connected-realm/{connectedRealmId}/auctions`<br>`/data/wow/auctions/commodities` | dynamic | neither | **NOT-LORE** | Connected-realm auction dumps and the commodity snapshot. Market data. |
| Azerite essence | `/data/wow/azerite-essence/index`<br>`/data/wow/azerite-essence/{azeriteEssenceId}`<br>`/data/wow/search/azerite-essence`<br>`/data/wow/media/azerite-essence/{azeriteEssenceId}` | static | search `/data/wow/search/azerite-essence` (allowed_specializations.id); index `/data/wow/azerite-essence/index` | **RETIRED** | Arguable CLONE-ABLE: index, id, and media fit the static pattern, but the documented search field is `allowed_specializations.id`, not a name. Arguable RETIRED: Battle for Azeroth Heart of Azeroth essences are still published here and the page does not mark them retired. |
| Connected realm | `/data/wow/connected-realm/index`<br>`/data/wow/connected-realm/{connectedRealmId}`<br>`/data/wow/search/connected-realm` | dynamic | search `/data/wow/search/connected-realm` (status.type, realms.timezone); index `/data/wow/connected-realm/index` | **NOT-LORE** | Dynamic realm status, population, and timezone. Search fields are `status.type` and `realms.timezone`. |
| Covenant | `/data/wow/covenant/index`<br>`/data/wow/covenant/{covenantId}`<br>`/data/wow/media/covenant/{covenantId}` | static | index `/data/wow/covenant/index` | **RETIRED** | Arguable CLONE-ABLE: four named covenants with index, id, and media. Arguable RETIRED: Shadowlands covenant choice is still published; the page does not mark it retired. |
| Soulbind | `/data/wow/covenant/soulbind/index`<br>`/data/wow/covenant/soulbind/{soulbindId}` | static | index `/data/wow/covenant/soulbind/index` | **RETIRED** | Arguable RETIRED: Shadowlands soulbinds, still listed. Index plus id would otherwise match the static pattern. |
| Conduit | `/data/wow/covenant/conduit/index`<br>`/data/wow/covenant/conduit/{conduitId}` | static | index `/data/wow/covenant/conduit/index` | **RETIRED** | Arguable RETIRED: Shadowlands conduits, still listed. Index plus id would otherwise match the static pattern. |
| Creature | `/data/wow/creature/{creatureId}`<br>`/data/wow/search/creature`<br>`/data/wow/media/creature-display/{creatureDisplayId}` | static | search `/data/wow/search/creature` (name.en_US) | **COVERED** | Documented name search on `name.en_US`. Tool `search_creature` uses that path and does not attach media. Documented media is `media/creature-display/{creatureDisplayId}`, not `media/creature/{creatureId}`. |
| Creature family | `/data/wow/creature-family/index`<br>`/data/wow/creature-family/{creatureFamilyId}`<br>`/data/wow/media/creature-family/{creatureFamilyId}` | static | index `/data/wow/creature-family/index` | **COVERED** | Tool `search_creature_family` resolves the family index and attaches creature-family media. |
| Creature type | `/data/wow/creature-type/index`<br>`/data/wow/creature-type/{creatureTypeId}` | static | index `/data/wow/creature-type/index` | **COVERED** | Same tool as creature family. No media method on this reference. |
| Guild crest | `/data/wow/guild-crest/index`<br>`/data/wow/media/guild-crest/border/{borderId}`<br>`/data/wow/media/guild-crest/emblem/{emblemId}` | static | index `/data/wow/guild-crest/index` | **NOT-LORE** | Border and emblem media components, not a lore record. |
| Heirloom | `/data/wow/heirloom/index`<br>`/data/wow/heirloom/{heirloomId}` | static | index `/data/wow/heirloom/index` | **COVERED** | Tool `search_heirloom_by_name` calls `/data/wow/search/heirloom`, which this reference does not list. Documented access is index plus id. No media method. |
| Housing decor | `/data/wow/decor/index`<br>`/data/wow/decor/{decorId}`<br>`/data/wow/search/decor` | static | search `/data/wow/search/decor` (name.en_US); index `/data/wow/decor/index` | **CLONE-ABLE** | Documented name search on `name.en_US`, plus index and id. Exact `search_blizzard` shape. No media method. |
| Housing fixture | `/data/wow/fixture/index`<br>`/data/wow/fixture/{fixtureId}`<br>`/data/wow/search/fixture` | static | search `/data/wow/search/fixture` (name.en_US); index `/data/wow/fixture/index` | **CLONE-ABLE** | Arguable NOT-LORE: a fixture may be a housing attachment record rather than a lore subject. Documented search field is `name.en_US`; the field description on this page says "The name of the decor." |
| Housing fixture hook | `/data/wow/fixture-hook/index`<br>`/data/wow/fixture-hook/{fixtureHookId}`<br>`/data/wow/search/fixture-hook` | static | search `/data/wow/search/fixture-hook` (no name field in the example list); index `/data/wow/fixture-hook/index` | **BESPOKE** | Search is listed, and its example fields are only `orderby` and `_page` (no name). Index plus id exist. Whether index rows carry `name` was not fetched. |
| Housing room | `/data/wow/room/index`<br>`/data/wow/room/{roomId}`<br>`/data/wow/search/room` | static | search `/data/wow/search/room` (name.en_US); index `/data/wow/room/index` | **CLONE-ABLE** | Documented name search on `name.en_US`, plus index and id. No media method. |
| Item | `/data/wow/item/{itemId}`<br>`/data/wow/search/item`<br>`/data/wow/media/item/{itemId}` | static | search `/data/wow/search/item` (name.en_US) | **COVERED** | Tools `search_item_by_name` and `lookup_item`. Documented name search. Media method exists; neither tool attaches it. Famous-item ids are hardcoded in `famous_items`. |
| Item class | `/data/wow/item-class/index`<br>`/data/wow/item-class/{itemClassId}` | static | index `/data/wow/item-class/index` | **CLONE-ABLE** | Static index plus id (Weapon, Armor, and so on). Whether index entries include `name` was not fetched. |
| Item set | `/data/wow/item-set/index`<br>`/data/wow/item-set/{itemSetId}` | static | index `/data/wow/item-set/index` | **COVERED** | Tool `search_item_set` uses the index, then id. No media method. |
| Item subclass | `/data/wow/item-class/{itemClassId}/item-subclass/{itemSubclassId}` | static | neither | **BESPOKE** | Path needs both an item-class id and a subclass id. It does not fit `{entity}/{id}`. |
| Item appearance | `/data/wow/item-appearance/{appearanceId}`<br>`/data/wow/search/item-appearance` | static | search `/data/wow/search/item-appearance` (slot.type) | **BESPOKE** | Detail is by appearance id. The documented search example field is `slot.type`, not a name. No flat appearance index. |
| Item appearance set | `/data/wow/item-appearance/set/index`<br>`/data/wow/item-appearance/set/{appearanceSetId}` | static | index `/data/wow/item-appearance/set/index` | **CLONE-ABLE** | Index plus id under `item-appearance/set`, the same slash-path shape as `quest/area`. Whether index entries include `name` was not fetched. Distinct from gear item sets. |
| Item appearance slot | `/data/wow/item-appearance/slot/index`<br>`/data/wow/item-appearance/slot/{slotType}` | static | index `/data/wow/item-appearance/slot/index` | **NOT-LORE** | Equipment-slot enum (head, chest, and so on), not a lore subject. |
| Journal expansion | `/data/wow/journal-expansion/index`<br>`/data/wow/journal-expansion/{journalExpansionId}` | static | index `/data/wow/journal-expansion/index` | **COVERED** | Tool `search_journal_expansion` uses the index. No media method. No search method. |
| Journal encounter | `/data/wow/journal-encounter/index`<br>`/data/wow/journal-encounter/{journalEncounterId}`<br>`/data/wow/search/journal-encounter` | static | search `/data/wow/search/journal-encounter` (instance.name.en_US); index `/data/wow/journal-encounter/index` | **COVERED** | Tool `search_journal_encounter` searches `name.en_US` and then the index. The reference's example search field is `instance.name.en_US`. Encounter-name search behavior was not called. |
| Journal instance | `/data/wow/journal-instance/index`<br>`/data/wow/journal-instance/{journalInstanceId}`<br>`/data/wow/media/journal-instance/{journalInstanceId}` | static | index `/data/wow/journal-instance/index` | **COVERED** | Tool `search_journal_instance_by_name` calls `/data/wow/search/journal-instance`, which this reference does not list. Documented access is index, id, and media. The tool does not attach media. |
| Media search | `/data/wow/search/media` | static | search `/data/wow/search/media` (tags) | **BESPOKE** | Cross-type media query by `tags`. Not a named lore entity. |
| Modified crafting | `/data/wow/modified-crafting/index`<br>`/data/wow/modified-crafting/category/index`<br>`/data/wow/modified-crafting/category/{categoryId}`<br>`/data/wow/modified-crafting/reagent-slot-type/index`<br>`/data/wow/modified-crafting/reagent-slot-type/{slotTypeId}` | static | index `/data/wow/modified-crafting/index`, `/data/wow/modified-crafting/category/index`, `/data/wow/modified-crafting/reagent-slot-type/index` | **NOT-LORE** | Crafting-reagent category and slot-type documents. Mechanic metadata. |
| Mount | `/data/wow/mount/index`<br>`/data/wow/mount/{mountId}`<br>`/data/wow/search/mount` | static | search `/data/wow/search/mount` (name.en_US); index `/data/wow/mount/index` | **COVERED** | Tool `search_mount_by_name`. Documented name search on `name.en_US`. No media method on this API. |
| Mythic keystone affix | `/data/wow/keystone-affix/index`<br>`/data/wow/keystone-affix/{keystoneAffixId}`<br>`/data/wow/media/keystone-affix/{keystoneAffixId}` | static | index `/data/wow/keystone-affix/index` | **CLONE-ABLE** | Arguable NOT-LORE: affixes are dungeon modifiers (Fortified, Tyrannical). Index, id, and media fit the static pattern. Whether index entries include `name` was not fetched. |
| Mythic keystone dungeon | `/data/wow/mythic-keystone/index`<br>`/data/wow/mythic-keystone/dungeon/index`<br>`/data/wow/mythic-keystone/dungeon/{dungeonId}` | dynamic | index `/data/wow/mythic-keystone/index`, `/data/wow/mythic-keystone/dungeon/index` | **BESPOKE** | Dynamic namespace and a current-season dungeon list. A named raid or dungeon question is already covered by journal instance. |
| Mythic keystone periods and seasons | `/data/wow/mythic-keystone/period/index`<br>`/data/wow/mythic-keystone/period/{periodId}`<br>`/data/wow/mythic-keystone/season/index`<br>`/data/wow/mythic-keystone/season/{seasonId}` | dynamic | index `/data/wow/mythic-keystone/period/index`, `/data/wow/mythic-keystone/season/index` | **NOT-LORE** | Dynamic schedule buckets, not lore records. |
| Mythic keystone leaderboard | `/data/wow/connected-realm/{connectedRealmId}/mythic-leaderboard/index`<br>`/data/wow/connected-realm/{connectedRealmId}/mythic-leaderboard/{dungeonId}/period/{period}` | dynamic | index `/data/wow/connected-realm/{connectedRealmId}/mythic-leaderboard/index` | **NOT-LORE** | Per-realm ranking for a dungeon and period. |
| Mythic raid leaderboard | `/data/wow/leaderboard/hall-of-fame/{raid}/{faction}` | dynamic | neither | **NOT-LORE** | Hall of Fame board for a raid and faction. |
| Neighborhood | `/data/wow/neighborhood-map/index`<br>`/data/wow/neighborhood-map/{neighborhoodMapId}`<br>`/data/wow/neighborhood-map/{neighborhoodMapId}/neighborhood/{neighborhoodId}` | dynamic | index `/data/wow/neighborhood-map/index` | **BESPOKE** | Dynamic housing maps. Neighborhood detail needs both a map id and a neighborhood id. |
| Pet | `/data/wow/pet/index`<br>`/data/wow/pet/{petId}`<br>`/data/wow/media/pet/{petId}` | static | index `/data/wow/pet/index` | **COVERED** | Tool `search_pet_by_name` calls `/data/wow/search/pet`, which this reference does not list. Documented access is index, id, and media. The tool does not attach media. |
| Pet ability | `/data/wow/pet-ability/index`<br>`/data/wow/pet-ability/{petAbilityId}`<br>`/data/wow/media/pet-ability/{petAbilityId}` | static | index `/data/wow/pet-ability/index` | **CLONE-ABLE** | Index, id, and media. Whether index entries include `name` was not fetched. The ability index may be large; item-set already loads a full index the same way. |
| Playable class | `/data/wow/playable-class/index`<br>`/data/wow/playable-class/{classId}`<br>`/data/wow/media/playable-class/{playableClassId}` | static | index `/data/wow/playable-class/index` | **COVERED** | Tool `search_playable_class` uses the index and attaches playable-class media. PvP talent slots are a separate row. |
| PvP talent slots | `/data/wow/playable-class/{classId}/pvp-talent-slots` | static | neither | **BESPOKE** | One document per class id (`playable-class/{classId}/pvp-talent-slots`). Slot layout, not a name search. |
| Playable race | `/data/wow/playable-race/index`<br>`/data/wow/playable-race/{playableRaceId}` | static | index `/data/wow/playable-race/index` | **COVERED** | Tool `search_playable_race` uses the index. No media method. No search method. |
| Playable specialization | `/data/wow/playable-specialization/index`<br>`/data/wow/playable-specialization/{specId}`<br>`/data/wow/media/playable-specialization/{specId}` | static | index `/data/wow/playable-specialization/index` | **COVERED** | Tool `search_specialization` uses the index and attaches specialization media. No search method. |
| Power type | `/data/wow/power-type/index`<br>`/data/wow/power-type/{powerTypeId}` | static | index `/data/wow/power-type/index` | **NOT-LORE** | Arguable CLONE-ABLE: index plus id is the static pattern (Mana, Rage, Energy). These are combat-resource enums, so the primary label is NOT-LORE. |
| Profession and skill tier | `/data/wow/profession/index`<br>`/data/wow/profession/{professionId}`<br>`/data/wow/media/profession/{professionId}`<br>`/data/wow/profession/{professionId}/skill-tier/{skillTierId}` | static | index `/data/wow/profession/index` | **COVERED** | Tool `search_profession` uses the profession index, attaches profession media, and may attach one matching skill-tier document. Skill tier is a two-id path and is already handled. |
| Recipe | `/data/wow/recipe/{recipeId}`<br>`/data/wow/media/recipe/{recipeId}` | static | neither | **BESPOKE** | Recipe by id and recipe media only. This reference has no recipe index and no recipe search. |
| PvP season, leaderboards, and rewards | `/data/wow/pvp-season/index`<br>`/data/wow/pvp-season/{pvpSeasonId}`<br>`/data/wow/pvp-season/{pvpSeasonId}/pvp-leaderboard/index`<br>`/data/wow/pvp-season/{pvpSeasonId}/pvp-leaderboard/{pvpBracket}`<br>`/data/wow/pvp-season/{pvpSeasonId}/pvp-reward/index` | dynamic | index `/data/wow/pvp-season/index`, `/data/wow/pvp-season/{pvpSeasonId}/pvp-leaderboard/index`, `/data/wow/pvp-season/{pvpSeasonId}/pvp-reward/index` | **NOT-LORE** | Dynamic season documents, bracket leaderboards, and reward indexes. |
| PvP tier | `/data/wow/pvp-tier/index`<br>`/data/wow/pvp-tier/{pvpTierId}`<br>`/data/wow/media/pvp-tier/{pvpTierId}` | static | index `/data/wow/pvp-tier/index` | **CLONE-ABLE** | Arguable NOT-LORE: Combatant, Rival, Gladiator, and similar ranks are competitive labels. Index, id, and media fit the static pattern. Whether index entries include `name` was not fetched. |
| Quest | `/data/wow/quest/index`<br>`/data/wow/quest/{questId}` | static | index `/data/wow/quest/index` | **COVERED** | Tool `search_quest_by_name` calls `/data/wow/search/quest`, which this reference does not list. The documented index is described as "the parent index for quests," not a flat name list. |
| Quest category | `/data/wow/quest/category/index`<br>`/data/wow/quest/category/{questCategoryId}` | static | index `/data/wow/quest/category/index` | **COVERED** | Tool `search_quest_group` reads this index. Reference description: quests for a class, profession, or storyline. |
| Quest area | `/data/wow/quest/area/index`<br>`/data/wow/quest/area/{questAreaId}` | static | index `/data/wow/quest/area/index` | **COVERED** | Same tool. Detail path `quest/area/{id}` already goes through `_get_entity_data`. |
| Quest type | `/data/wow/quest/type/index`<br>`/data/wow/quest/type/{questTypeId}` | static | index `/data/wow/quest/type/index` | **COVERED** | Same tool. Reference examples: PvP, raid, or account quests. |
| Realm | `/data/wow/realm/index`<br>`/data/wow/realm/{realmSlug}`<br>`/data/wow/search/realm` | dynamic | search `/data/wow/search/realm` (timezone); index `/data/wow/realm/index` | **NOT-LORE** | Dynamic realm status. Search example field is `timezone`. |
| Region | `/data/wow/region/index`<br>`/data/wow/region/{regionId}` | dynamic | index `/data/wow/region/index` | **NOT-LORE** | Dynamic region index and region by id. |
| Reputation faction | `/data/wow/reputation-faction/index`<br>`/data/wow/reputation-faction/{reputationFactionId}` | static | index `/data/wow/reputation-faction/index` | **COVERED** | Tool `search_faction_by_name` calls `/data/wow/search/reputation-faction`, which this reference does not list. Documented access is index plus id. No media method. |
| Reputation tiers | `/data/wow/reputation-tiers/index`<br>`/data/wow/reputation-tiers/{reputationTiersId}` | static | index `/data/wow/reputation-tiers/index` | **COVERED** | Tool `search_reputation_tiers` loads the index, then scans tier documents for standing names such as Exalted. That scanner is already more than a one-row index match. No media method. |
| Spell | `/data/wow/spell/{spellId}`<br>`/data/wow/media/spell/{spellId}`<br>`/data/wow/search/spell` | static | search `/data/wow/search/spell` (name.en_US) | **COVERED** | Tool `search_spell_by_name`. Documented name search on `name.en_US`. Media method exists; the tool does not attach it. No spell index on this reference. |
| Talent tree and talents | `/data/wow/talent-tree/index`<br>`/data/wow/talent-tree/{talentTreeId}/playable-specialization/{specId}`<br>`/data/wow/talent-tree/{talentTreeId}`<br>`/data/wow/talent/index`<br>`/data/wow/talent/{talentId}` | static | index `/data/wow/talent-tree/index`, `/data/wow/talent/index` | **BESPOKE** | Tree-by-spec is a two-id path. The nodes document is described as useful for loadout export codes. A single talent id is the wrong answer shape for "what talents does this spec have." |
| PvP talent | `/data/wow/pvp-talent/index`<br>`/data/wow/pvp-talent/{pvpTalentId}` | static | index `/data/wow/pvp-talent/index` | **CLONE-ABLE** | Arguable BESPOKE: a named PvP talent fits index plus id, while the useful class layout is the separate PvP talent slots document. Whether index entries include `name` was not fetched. No media method. |
| Tech talent tree | `/data/wow/tech-talent-tree/index`<br>`/data/wow/tech-talent-tree/{techTalentTreeId}` | static | index `/data/wow/tech-talent-tree/index` | **RETIRED** | Arguable RETIRED: Shadowlands covenant tech trees, still listed. Index plus id would otherwise match the static pattern. |
| Tech talent | `/data/wow/tech-talent/index`<br>`/data/wow/tech-talent/{techTalentId}`<br>`/data/wow/media/tech-talent/{techTalentId}` | static | index `/data/wow/tech-talent/index` | **RETIRED** | Arguable RETIRED: Shadowlands tech talents, still listed, including media. |
| Title | `/data/wow/title/index`<br>`/data/wow/title/{titleId}` | static | index `/data/wow/title/index` | **COVERED** | Tool `search_title_by_name` calls `/data/wow/search/title`, which this reference does not list. Documented access is index plus id. No media method. |
| Toy | `/data/wow/toy/index`<br>`/data/wow/toy/{toyId}` | static | index `/data/wow/toy/index` | **COVERED** | Tool `search_toy_by_name` calls `/data/wow/search/toy`, which this reference does not list. Documented access is index plus id. No media method. |
| WoW Token | `/data/wow/token/index` | dynamic (dynamic-us, dynamic-cn) | index `/data/wow/token/index` | **COVERED** | Tool `get_wow_token_price` already returns the gold price. Code GETs `/data/wow/token/` with `dynamic-us` at `src/api/blizzard.py:376`. This reference lists `/data/wow/token/index` for `dynamic-us` and again for `dynamic-cn`. Market data that is already wired. |

### Profile

| Endpoint group | Paths | Namespace | Name search or index? | Classification | Notes |
| --- | --- | --- | --- | --- | --- |
| Account Profile | `/profile/user/wow`<br>`/profile/user/wow/protected-character/{realmId}-{characterId}`<br>`/profile/user/wow/collections`<br>`/profile/user/wow/collections/decor`<br>`/profile/user/wow/collections/heirlooms`<br>`/profile/user/wow/collections/mounts`<br>`/profile/user/wow/collections/pets`<br>`/profile/user/wow/collections/toys`<br>`/profile/user/wow/collections/transmogs` | profile | neither | **BESPOKE** | Account Profile Summary states it requires an access token with the `wow.profile` scope from the authorization-code flow. Collections and the protected-character summary are per-account, not world lore. |
| Character Achievements | `/profile/wow/character/{realmSlug}/{characterName}/achievements`<br>`/profile/wow/character/{realmSlug}/{characterName}/achievements/statistics` | profile | neither | **BESPOKE** | Per-character achievement progress. Identity is realm slug plus character name. This page's descriptions do not state an OAuth scope. |
| Character Appearance | `/profile/wow/character/{realmSlug}/{characterName}/appearance` | profile | neither | **BESPOKE** | Per-character appearance settings. This page does not state an OAuth scope. |
| Character Collections | `/profile/wow/character/{realmSlug}/{characterName}/collections`<br>`/profile/wow/character/{realmSlug}/{characterName}/collections/decor`<br>`/profile/wow/character/{realmSlug}/{characterName}/collections/heirlooms`<br>`/profile/wow/character/{realmSlug}/{characterName}/collections/mounts`<br>`/profile/wow/character/{realmSlug}/{characterName}/collections/pets`<br>`/profile/wow/character/{realmSlug}/{characterName}/collections/toys`<br>`/profile/wow/character/{realmSlug}/{characterName}/collections/transmogs` | profile | neither | **BESPOKE** | Per-character collection summaries, including decor. This page does not state an OAuth scope. |
| Character Encounters | `/profile/wow/character/{realmSlug}/{characterName}/encounters`<br>`/profile/wow/character/{realmSlug}/{characterName}/encounters/dungeons`<br>`/profile/wow/character/{realmSlug}/{characterName}/encounters/raids` | profile | neither | **BESPOKE** | Per-character dungeon and raid progress. This page does not state an OAuth scope. |
| Character Equipment | `/profile/wow/character/{realmSlug}/{characterName}/equipment` | profile | neither | **BESPOKE** | Per-character equipped items. This page does not state an OAuth scope. |
| Character House | `/profile/wow/character/{realmSlug}/{characterName}/house/house-{houseNumber}` | profile | neither | **BESPOKE** | Per-character player-housing plot. This page does not state an OAuth scope. |
| Character Hunter Pets | `/profile/wow/character/{realmSlug}/{characterName}/hunter-pets` | profile | neither | **BESPOKE** | Returns hunter pets, or 404 when the character is not a hunter. This page does not state an OAuth scope. |
| Character Media | `/profile/wow/character/{realmSlug}/{characterName}/character-media` | profile | neither | **BESPOKE** | Character render summary. This page does not state an OAuth scope. See also the character-renders guide. |
| Character Mythic Keystone Profile | `/profile/wow/character/{realmSlug}/{characterName}/mythic-keystone-profile`<br>`/profile/wow/character/{realmSlug}/{characterName}/mythic-keystone-profile/season/{seasonId}` | profile | neither | **BESPOKE** | Per-character Mythic Keystone season profile. This page does not state an OAuth scope. |
| Character Professions | `/profile/wow/character/{realmSlug}/{characterName}/professions` | profile | neither | **BESPOKE** | Per-character profession progress. This page does not state an OAuth scope. |
| Character Profile | `/profile/wow/character/{realmSlug}/{characterName}`<br>`/profile/wow/character/{realmSlug}/{characterName}/status` | profile | neither | **BESPOKE** | Character summary and the status/id validity check. This page does not state an OAuth scope. |
| Character PvP | `/profile/wow/character/{realmSlug}/{characterName}/pvp-bracket/{pvpBracket}`<br>`/profile/wow/character/{realmSlug}/{characterName}/pvp-summary` | profile | neither | **BESPOKE** | Per-character bracket statistics. This page does not state an OAuth scope. |
| Character Quests | `/profile/wow/character/{realmSlug}/{characterName}/quests`<br>`/profile/wow/character/{realmSlug}/{characterName}/quests/completed` | profile | neither | **BESPOKE** | Active quests and a link to completed quests for one character. This page does not state an OAuth scope. |
| Character Reputations | `/profile/wow/character/{realmSlug}/{characterName}/reputations` | profile | neither | **BESPOKE** | Per-character reputation progress. This page does not state an OAuth scope. |
| Character Soulbinds | `/profile/wow/character/{realmSlug}/{characterName}/soulbinds` | profile | neither | **RETIRED** | Arguable RETIRED: Shadowlands soulbind loadout for one character, still listed. Profile identity, not a static lore document. |
| Character Specializations | `/profile/wow/character/{realmSlug}/{characterName}/specializations` | profile | neither | **BESPOKE** | Per-character spec summary. This page does not state an OAuth scope. |
| Character Statistics | `/profile/wow/character/{realmSlug}/{characterName}/statistics` | profile | neither | **BESPOKE** | Per-character combat statistics. This page does not state an OAuth scope. |
| Character Titles | `/profile/wow/character/{realmSlug}/{characterName}/titles` | profile | neither | **BESPOKE** | Titles a character has earned. This page does not state an OAuth scope. |
| Guild | `/data/wow/guild/{realmSlug}/{nameSlug}`<br>`/data/wow/guild/{realmSlug}/{nameSlug}/activity`<br>`/data/wow/guild/{realmSlug}/{nameSlug}/achievements`<br>`/data/wow/guild/{realmSlug}/{nameSlug}/roster` | profile | neither | **BESPOKE** | Guild, activity, achievements, and roster by realm slug and guild slug. Namespace default on this page is `profile-us` even though the path is under `/data/wow/guild/`. Descriptions do not state an OAuth scope. |

## 4. Architecture cost

Current measurement, from importing `src.tools.schemas.TOOL_SCHEMAS` and `src.tools.handlers.TOOL_HANDLERS`:

| | Tools | `json.dumps` characters |
| --- | ---: | ---: |
| Now | 24 | 13840 |
| Every clone-able group becomes its own tool | 34 | 19261 |
| Those same 10 groups behind one generic tool | 25 | 15030 |
| Bounded pass: five distinct names on a shared resolver (the recommendation) | 29 | 16652 |

The per-tool number was measured by building ten schemas with `_search_schema` in the same "You MUST call this tool" voice as the current search tools, dumping each with `json.dumps`, and adding one comma per new array element (5421 characters added). The generic number is one `search_game_data` schema with an `entity_type` enum for those ten families (1189 characters, plus one comma). Descriptions for tools that do not exist yet are illustrations for the size math, not copy to ship.

What already supports a map:

- `search_blizzard(search_term, entity_type)` builds `/data/wow/search/{entity_type}` and picks an id.
- `_get_entity_data(entity_type, entity_id)` builds `/data/wow/{entity_type}/{entity_id}`. Slash types already work: `quest/area`, `quest/category`, `quest/type`.
- `get_index_data` and `lookup_static_ids` resolve a display name from a static index when search is absent.
- `_search_and_fetch` and `_index_search_and_fetch` are the two handler shapes. `_SEARCH_TOOL_SPECS` is already a schema table.
- `with_official_media(data, media_type, entity_id)` attaches `/data/wow/media/{type}/{id}`.

What blocks "add the type string and stop":

- There is no resolver table. Each family is a getter function plus a handler. A new family is still a new schema row, a new handler entry, and a new mapping.
- `search_blizzard` and `_get_entity_data` hardcode `namespace=static-us`. Dynamic groups (token, realms, keystones, neighborhoods, PvP seasons) cannot use them unchanged. The token URL is also not the generic `{type}/{id}` path.
- Documented search fields are not all `name.en_US`. Journal encounter's example field is `instance.name.en_US`. Azerite essence uses `allowed_specializations.id`. Item appearance uses `slot.type`. Fixture-hook search lists no name field.
- Eight current tools already call search types the reference does not list. Extending that pattern to new types would repeat a path the current catalog does not publish. Index-backed families should use `lookup_static_ids` when the reference has an index and no name search.
- Several covered tools are already special cases a single row cannot express: profession skill tier, reputation-tier document scan, creature family plus creature type, quest area plus category plus type, and item id versus item name.
- `get_entity_media` assumes `media/{type}/{id}`. Creature media on the reference is `media/creature-display/{creatureDisplayId}`.
- Index name matching only works when the index JSON contains `name`. That is true for the indexes the bot already uses. It was not fetched for the new indexes. `schemas.py` says descriptions must stay distinct because a small model confuses similar tools, and item name and item id are separate tools for that reason. One enum tool is smaller and easier to mis-route.

**Recommendation.** Add one resolver table in `src/api/blizzard.py` with mode (`search` or `index`), the detail path, and an optional media type, and dispatch it through the two existing handlers. Expose decor, room, achievement category, item class, and item appearance set as their own schema rows so the model sees distinct names. Leave pet ability, PvP tier, keystone affix, fixture, and PvP talent as later rows on that table. Do not collapse the current 24 tools into one enum, and do not copy ten new handlers by hand.

## 5. Job 2 shortlist

One bounded pass can ship the resolver table plus the five groups below. Each one is static, returns a single document, and needs a schema row, a handler entry or a map dispatch, an endpoint mapping, and mocked tests. Files for the whole pass: `src/api/blizzard.py`, `src/tools/schemas.py`, `src/tools/handlers.py`, `tests/test_blizzard_expansion.py`. Tests stay mocked. They must not call Blizzard.

### Ship in that pass

1. **`search_decor`** — housing decor. Documented `/data/wow/search/decor` with `name.en_US`, then `/data/wow/decor/{decorId}`. Mode `search`. Tests: schema registered and `search_term` required; mocked search returns an id and the detail GET is the decor path; blank term does not call the network; a miss returns the not-found string; HTTP 401 returns the auth-failure string.
2. **`search_room`** — housing room. Same shape on `/data/wow/search/room` and `/data/wow/room/{roomId}`. Same tests, with the room paths. Assert it does not call the decor URL.
3. **`search_achievement_category`** — index `/data/wow/achievement-category/index`, detail `/data/wow/achievement-category/{id}`. Mode `index`. Tests: mocked index with a named entry resolves that id; detail GET uses that id; an unknown name returns not-found; a failed index returns not-found or the auth string. If the live index has no `name` field, this row waits, because that was not fetched here.
4. **`search_item_class`** — index `/data/wow/item-class/index`, detail `/data/wow/item-class/{id}`. Same index tests. Assert a class name is not sent to `search_item_by_name`.
5. **`search_item_appearance_set`** — index `/data/wow/item-appearance/set/index`, detail `/data/wow/item-appearance/set/{id}`. Same index tests. Assert it does not call `search_item_set` or `/data/wow/item-set/`.

Shared test for the pass: `TOOL_SCHEMAS` and `TOOL_HANDLERS` still match, and the new names are the only additions.

### Later

6. **`search_pet_ability`** — index `/data/wow/pet-ability/index` plus media `/data/wow/media/pet-ability/{id}`. Same pattern, with a larger index and a media assertion. Ship after the resolver exists.
7. **`search_pvp_tier`** — index `/data/wow/pvp-tier/index`, detail, and media. Arguable NOT-LORE (rank labels).
8. **`search_keystone_affix`** — index `/data/wow/keystone-affix/index`, detail, and media. Arguable NOT-LORE (dungeon modifiers).
9. **`search_fixture`** — documented name search `/data/wow/search/fixture`. Arguable NOT-LORE (housing attachment records). The reference's field blurb says "The name of the decor."
10. **`search_pvp_talent`** — index `/data/wow/pvp-talent/index` and `/data/wow/pvp-talent/{id}`. Arguable BESPOKE, because the class slot layout is `/data/wow/playable-class/{classId}/pvp-talent-slots`.

Not in this list, on purpose: recipe and item appearance have no name index or name search; talent trees are two-id loadout documents; profile APIs are per character, guild, or account; auction, realm, and leaderboard groups are market or ranking data; covenant, soulbind, conduit, azerite essence, and tech talent stay retired-arguable while the portal still publishes them.
