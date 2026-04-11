# LoreMasterBot
A friendly campfire companion for exploring Azeroth lore with real-time Blizzard data.

## Features
- In-character WoW lore assistant focused on Azeroth.
- Natural language conversations with tool-based Blizzard lookups.
- Blizzard Game Data API coverage:
  - Creatures
  - Items (by name or item ID)
  - Quests
  - Mounts
  - Achievements
  - Spells and abilities
  - Raids and dungeons (Journal Instances)
  - Reputation factions
  - Titles
  - Toys
  - Battle pets
  - Heirlooms
  - Current WoW Token price
- Local model workflow with Ollama.
- Credential loading from `.env`.
- Automatic token refresh with retry logic.
- In-memory caching for repeated API requests.
- Loading spinner during Blizzard API fetches for better UX.
- Smart conversation history management (keeps ~7 full turns for context).

## Project Structure
The project is organized into a clean, modular structure for maintainability:

```text
LoreMasterBot/
├── main.py                 # Entry point
├── requirements.txt        # Python dependencies
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

3. Install and start Ollama (if not already running):

```bash
ollama serve
```

4. Pull the model used by the bot:

```bash
ollama pull llama3.1:8b
```

5. Create a `.env` file in the project root:

```env
BLIZZARD_CLIENT_ID=your_client_id_here
BLIZZARD_CLIENT_SECRET=your_client_secret_here
```

6. Run the bot:

```bash
python main.py
```

## How to Use
Type naturally, like you are talking to a fellow adventurer by the fire.

Examples:
- "Tell me about Arthas Menethil"
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

Type `quit` to exit.

## Security Note
- Keep Blizzard credentials in `.env`.
- Never commit `.env`.
- If credentials are missing, the bot exits with a clear warning.
