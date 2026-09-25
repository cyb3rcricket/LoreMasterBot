# LoreMasterBot
A friendly campfire companion for exploring Azeroth lore with real-time Blizzard data.

## Features
- In-character WoW lore assistant focused on Azeroth.
- Natural language conversations with tool-based Blizzard lookups.
- Blizzard Game Data API coverage:
  - Creatures and NPC records
  - Creature families and types
  - Items (by name or item ID)
  - Item sets
  - Quests, plus quest areas, categories, and types
  - Mounts
  - Achievements
  - Spells and abilities
  - Raids and dungeons (Journal Instances)
  - Journal encounters (dungeon-journal bosses)
  - Journal expansions
  - Playable races, classes, and specializations
  - Professions and official skill-tier names
  - Reputation factions and reputation standings/tiers
  - Titles
  - Toys
  - Battle pets
  - Heirlooms
  - Official media metadata (icon/asset URLs) for supported entities
  - Current WoW Token price
- Local model workflow with Ollama by default, plus optional Gemini or custom OpenAI-compatible endpoints.
- Credential loading from `.env`.
- Automatic token refresh with retry logic.
- In-memory caching for repeated API requests.
- Loading spinner during Blizzard API fetches for better UX.
- Smart conversation history management (keeps ~7 full turns for context).

LoreMasterBot answers from official Blizzard structured Game Data only. It does **not** provide general character biographies, unofficial lore write-ups, or location guides beyond what those APIs return. If Blizzard has no structured record for a question, the bot will say so rather than inventing an answer.

## Project Structure
The project is organized into a clean, modular structure for maintainability:

```text
LoreMasterBot/
├── main.py                 # Entry point
├── requirements.txt        # Python dependencies
├── requirements-dev.txt    # Test dependencies
├── .env.example            # Example environment file
├── README.md               # This file
└── src/                    # Main source code
    ├── __init__.py
    ├── config.py           # Configuration, prompts, and credentials
    ├── api/
    │   ├── __init__.py
    │   └── blizzard.py     # Blizzard API client with caching
    ├── tools/
    │   ├── __init__.py
    │   ├── schemas.py      # OpenAI tool schemas
    │   └── handlers.py     # Tool call handlers
    └── bot.py              # Main chat loop and orchestration
```

## Installation & Setup
1. Open a terminal in the project directory.
2. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

For local development and tests, also install:

```bash
python -m pip install -r requirements-dev.txt
```

3. Install and start Ollama (if not already running):

```bash
ollama serve
```

4. Pull the model used by the bot:

```bash
ollama pull llama3.1:8b
```

5. Create a `.env` file in the project root (see `.env.example`). Minimum for the default local setup:

```env
BLIZZARD_CLIENT_ID=your_client_id_here
BLIZZARD_CLIENT_SECRET=your_client_secret_here
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
LLM_BASE_URL=http://localhost:11434/v1
```

6. Run the bot:

```bash
python main.py
```

## How to Use
Type naturally, like you are talking to a fellow adventurer by the fire.

Examples:
- "Tell me about the Human race"
- "Tell me about Death Knights"
- "What is Frost specialization?"
- "Who is Professor Putricide?"
- "Tell me about Blacksmithing"
- "What is the Judgement Armor set?"
- "What reputation levels are there?"
- "What is item 19019?"
- "Tell me about Thunderfury"
- "What is the quest The Lich King's Fall?"
- "Tell me about the mount Invincible"
- "What is Ahead of the Curve?"
- "What does Fireball do?"
- "Tell me the story of Karazhan"
- "Who are the Nightfallen?"
- "Tell me about the title Loremaster"
- "How do I get Mr. Pinchy?"
- "Tell me about Pandaren Fire Spirit"
- "What is Tattered Dreadmist Robe?"
- "What is the current WoW Token price?"

Questions about a famous character's life story (for example a full biography) are outside what Blizzard's structured Game Data APIs provide. The bot will admit that rather than filling the gap from model memory.

Type `quit` to exit.

## AI Provider

LoreMasterBot talks to the language model through the existing OpenAI Python client. The same chat loop is used for every provider. Set `LLM_PROVIDER` in `.env` to choose one:

- **Ollama** — local/private. No cloud API key required.
- **Gemini** — cloud mode using your Gemini API key and Google's OpenAI-compatible endpoint.
- **Custom** — any compatible OpenAI-style endpoint.

Ollama:

```env
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
LLM_BASE_URL=http://localhost:11434/v1
```

Gemini:

```env
LLM_PROVIDER=gemini
LLM_MODEL=<your Gemini model>
GEMINI_API_KEY=<your key>
```

Custom:

```env
LLM_PROVIDER=custom
LLM_MODEL=<model>
LLM_BASE_URL=<endpoint>
LLM_API_KEY=<key>
```

Do not commit real API keys. Unused provider keys can be left blank.

## Run tests

```bash
python -m pytest -q
```

## Security Note
- Keep Blizzard and LLM credentials in `.env`.
- Never commit `.env`.
- If required credentials for the selected provider are missing, the bot exits with a clear warning.
