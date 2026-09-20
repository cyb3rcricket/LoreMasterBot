# LoreMasterBot entry point.
#
# This file is intentionally tiny. Running `python main.py` imports the chat
# loop from src.bot and starts it. All credential checks, Blizzard login, and
# conversation logic live in the imported modules. This file only decides
# whether to start the bot.
from src.bot import run


# This check is True only when you run this file directly (`python main.py`),
# not when another file imports it. Tests import src.bot without starting the loop.
if __name__ == "__main__":
    run()
