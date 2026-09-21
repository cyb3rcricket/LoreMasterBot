# Settings and the character prompt for LoreMasterBot.
#
# This module is imported by the rest of the program. It must not talk to the
# network. It only loads secrets from the environment and defines the text that
# tells the language model how to behave.
import os
import sys

from dotenv import load_dotenv


# Environment variables are named settings stored outside the program, usually
# in a `.env` file or the operating system. That keeps secret keys out of the
# source code, so they are not committed to git by accident.
#
# load_dotenv() looks for a `.env` file and copies its values into os.environ
# if those names are not already set. os.getenv(...) then reads one name.
load_dotenv()

# Get Blizzard credentials from .env (create a .env file in the same folder).
# These are separate from LLM credentials. Blizzard unlocks Game Data API
# lookups; the LLM provider is who writes the spoken replies.
CLIENT_ID = os.getenv("BLIZZARD_CLIENT_ID")
CLIENT_SECRET = os.getenv("BLIZZARD_CLIENT_SECRET")

# A "provider" is the service that runs the language model. Several providers
# accept the same OpenAI Chat Completions format, so one OpenAI Python client
# can talk to all of them. Only the URL and API key change.
#
# Supported values of LLM_PROVIDER:
#   ollama  — local models, default, no cloud key required
#   gemini  — Google Gemini through its OpenAI-compatible HTTP API
#   custom  — any other OpenAI-compatible endpoint the user supplies
VALID_LLM_PROVIDERS = ("ollama", "gemini", "custom")

# Local Ollama defaults. Ollama is a program that runs models on this computer
# and exposes an OpenAI-compatible API at this URL. Gemini and custom do not
# get invented defaults for keys or model names.
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"

# Google's documented OpenAI-compatible Gemini endpoint. The existing OpenAI
# client can POST Chat Completions here; no extra Gemini SDK is required.
GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Ollama ignores the API key, but the OpenAI client constructor requires one.
OLLAMA_API_KEY = "ollama"


def _env_text(name, default=""):
    """Read one environment value and strip surrounding whitespace.

    Empty or missing values become `default`. Whitespace-only values are
    treated as missing so a blank line in `.env` does not count as a key.
    """
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


# Default provider is local Ollama so an existing `.env` that only has
# Blizzard keys keeps working. Unknown values are stored as-is (lowercased)
# and rejected later at startup, not during import.
LLM_PROVIDER = _env_text("LLM_PROVIDER", "ollama").lower() or "ollama"

# Shared model name used by the chat loop. Ollama may fall back to the
# documented local default. Gemini and custom require the user to set this.
LLM_MODEL = _env_text("LLM_MODEL")
if not LLM_MODEL and LLM_PROVIDER == "ollama":
    LLM_MODEL = DEFAULT_OLLAMA_MODEL

# Base URL for Ollama or a custom OpenAI-compatible server. Gemini ignores
# this and uses GEMINI_OPENAI_BASE_URL instead.
LLM_BASE_URL = _env_text("LLM_BASE_URL")
if not LLM_BASE_URL and LLM_PROVIDER == "ollama":
    LLM_BASE_URL = DEFAULT_OLLAMA_BASE_URL

# LLM_API_KEY is only for LLM_PROVIDER=custom. GEMINI_API_KEY is only for
# gemini. An unused key can be absent without breaking import or startup.
LLM_API_KEY = _env_text("LLM_API_KEY")
GEMINI_API_KEY = _env_text("GEMINI_API_KEY")


def print_missing_credentials_warning():
    """Print the user-facing warning used when Blizzard credentials are missing.

    Called from run() at startup, not during import. Importing this module with
    empty credentials must stay safe so tests can load the package.
    """
    print("⚠️  WARNING: Missing BLIZZARD_CLIENT_ID or BLIZZARD_CLIENT_SECRET in .env file!")
    print("   Please create a .env file in the same folder as this script with these two lines:")
    print("   BLIZZARD_CLIENT_ID=your_client_id_here")
    print("   BLIZZARD_CLIENT_SECRET=your_client_secret_here")
    print("   (Get a new set from https://develop.battle.net if needed)")


def llm_provider_label():
    """Short display name for the selected provider. Never includes secrets."""
    return {
        "ollama": "Ollama",
        "gemini": "Gemini",
        "custom": "Custom",
    }.get(LLM_PROVIDER, LLM_PROVIDER)


def llm_provider_error():
    """Return a short startup error for the active provider, or None if valid.

    Only the selected provider is checked. Ollama does not need a cloud key.
    Gemini does not need LLM_API_KEY. Custom does not need GEMINI_API_KEY.
    This function does not print keys and does not talk to the network.
    """
    if LLM_PROVIDER not in VALID_LLM_PROVIDERS:
        return (
            f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'.\n"
            "Valid choices: ollama, gemini, custom."
        )

    if LLM_PROVIDER == "ollama":
        return None

    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            return (
                "Gemini is selected, but GEMINI_API_KEY is missing.\n"
                "Add GEMINI_API_KEY to your .env file."
            )
        if not LLM_MODEL:
            return (
                "Gemini is selected, but LLM_MODEL is missing.\n"
                "Add LLM_MODEL to your .env file."
            )
        return None

    # custom
    if not LLM_BASE_URL:
        return (
            "Custom provider is selected, but LLM_BASE_URL is missing.\n"
            "Add LLM_BASE_URL to your .env file."
        )
    if not LLM_API_KEY:
        return (
            "Custom provider is selected, but LLM_API_KEY is missing.\n"
            "Add LLM_API_KEY to your .env file."
        )
    if not LLM_MODEL:
        return (
            "Custom provider is selected, but LLM_MODEL is missing.\n"
            "Add LLM_MODEL to your .env file."
        )
    return None


def validate_llm_provider():
    """Exit cleanly if the selected LLM provider is missing required settings.

    Called from run() at startup, before Blizzard checks. Importing this
    module with an unused provider's key missing must stay safe.
    """
    error = llm_provider_error()
    if error:
        print(error)
        sys.exit(1)


# SYSTEM_PROMPT is attached to EVERY model request. A language model is a
# program that writes text from a prompt. This long instruction keeps the bot
# in character and forbids it from inventing Warcraft lore when a tool finds
# nothing. Do not edit the prompt string unless you intend to change behavior.
SYSTEM_PROMPT = """
CRITICAL RULE: If a tool returns "NO OFFICIAL DATA FOUND", you MUST respond with only: "I couldn't find official records for that in the Blizzard API. Would you like to ask about something else in Azeroth?" You are FORBIDDEN from adding any lore, story, or details from your own knowledge. No exceptions.

RULE: If the user asks about any specific in-game creature or NPC record (by name), item by name (use search_item_by_name), or item by numeric ID (use lookup_item), you MUST call the appropriate tool (search_creature, search_item_by_name, or lookup_item) BEFORE giving any answer. Do not guess. Do not use your own knowledge. Always call the tool first to get real Blizzard data.

RULE: search_creature is only for in-game creature and NPC records. It is NOT a lore-character biography database. Do NOT use it to tell the life story of famous Warcraft figures.

RULE: For playable races use search_playable_race. For playable classes use search_playable_class. For specializations use search_specialization. For dungeon-journal bosses use search_journal_encounter. For professions use search_profession. For item sets use search_item_set. For reputation standings use search_reputation_tiers.

CRITICAL RULE: If the user asks for a lore character biography (for example the life story of a famous Warcraft figure) and the tool results do not contain that biography, you MUST say that Blizzard's available structured API data does not provide the requested lore biography. You MUST NOT invent the biography from memory. No exceptions.

CRITICAL RULE: If any tool returns a message that contains 'NO OFFICIAL DATA FOUND' or 'could not be found', you MUST respond ONLY with a polite in-character admission that the records do not contain that specific detail. You MUST NOT invent any lore, characters, events, stats, or story details. Never guess. Never make up new information. Simply say something warm like 'I'm afraid the ancient scrolls are silent on that exact tale, friend' and offer to share a different story from Azeroth.

RULE: When you receive tool data, you MUST only reference what is explicitly in that tool result. Do NOT invent drop locations, boss names, raid names, lore, stats, biographies, relationships, historical events, or flavor text that is not present in the data. If the data is sparse, respond honestly: "The official records only tell us [what was returned]. I don't have further details on that, friend."
RULE: If the user asks about a specific named WoW entity in any message — including follow-up questions — you MUST call the appropriate tool before answering. Never use conversation history as a substitute for a fresh tool call.

You are the 'Loremaster's Companion', a warm, friendly, and wise storyteller who has spent years wandering the lands of Azeroth. You love sharing tales of heroes, legends, and the ever-changing world of Warcraft.

Speak naturally and immersively, like a welcoming fellow adventurer sitting by a campfire. Be warm, engaging, and conversational.

When the user greets you or chats casually (like "hello, friend"), respond in character in a flowing, friendly way and keep the conversation going naturally — do not immediately ask what specific topic they want or repeat the rules.

Only if the user clearly asks about something completely outside World of Warcraft, politely decline with a short, friendly sentence like "My tales are only from the world of Azeroth, friend." Then gently guide them back with a related WoW question.

Always stay 100% in character as the Loremaster's Companion. All responses must relate to World of Warcraft lore, characters, items, quests, or adventures.
"""
