# LoreMasterBot
A friendly campfire companion for exploring Azeroth lore with real-time Blizzard data.

## Features
- 🧙 In-character WoW lore assistant: The bot speaks like a warm, story-rich Loremaster focused on Azeroth.
- 🔎 Natural language understanding: Ask questions conversationally instead of memorizing commands.
- 🧩 Powerful WoW lookups backed by Blizzard Game Data API:
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
- 🤖 Local AI workflow: Runs with local Ollama while using Blizzard API for live game data.
- 🔐 Safer credential handling: Blizzard API credentials are loaded from a local `.env` file.
- 🔁 Token reliability: Automatically fetches and refreshes Blizzard access token when needed.

## Installation & Setup
1. Clone or copy this project into a local folder.
2. Open a terminal in the project directory.
3. Install Python dependencies:

```bash
/usr/bin/python3 -m pip install openai requests python-dotenv
```

4. Install and start Ollama (if you have not already):

```bash
ollama serve
```

5. Pull the model used by the bot:

```bash
ollama pull llama3.1:8b
```

6. Create a `.env` file in the project root with your Blizzard credentials:

```env
BLIZZARD_CLIENT_ID=your_client_id_here
BLIZZARD_CLIENT_SECRET=your_client_secret_here
```

7. Run the bot:

```bash
/usr/bin/python3 bot.py
```

## How to Use
Type naturally, like you are talking to a fellow adventurer by the fire. No slash commands required.

Natural language examples for major features:
- 🐉 Creatures: "Tell me about Arthas Menethil"
- ⚔️ Items by ID: "What is item 19019?"
- 🧪 Items by name: "Tell me about Thunderfury"
- 📜 Quests: "What is the quest The Lich King's Fall?"
- 🐎 Mounts: "Tell me about the mount Invincible"
- 🏆 Achievements: "What is Ahead of the Curve?"
- ✨ Spells: "What does Fireball do?"
- 🏰 Raids/Dungeons: "Tell me the story of Karazhan"
- 🛡️ Factions: "Who are the Nightfallen?"
- 👑 Titles: "Tell me about the title Loremaster"
- 🎁 Toys: "How do I get Mr. Pinchy?"
- 🐾 Pets: "Tell me about Pandaren Fire Spirit"
- 🧵 Heirlooms: "What is Tattered Dreadmist Robe?"
- 💰 WoW Token: "What is the current WoW Token price?"

To quit the bot, type:
- `quit`

## Security Note
- Keep your Blizzard credentials in `.env`, not directly in source code.
- Never share or commit `.env` to public repositories.
- If credentials are missing, the bot warns you and exits to prevent confusing runtime failures.

## Tech Stack
- 🐍 Python
- 🤖 Ollama (local model runtime)
- 🌐 Blizzard Game Data API
- 📦 python-dotenv
- 🔗 requests
- 🧠 OpenAI Python SDK (used for Ollama-compatible chat/tool calling)
