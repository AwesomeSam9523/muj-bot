"""
The entry file of the bot
"""

import logging
import asyncio

from utils import *
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("mujbot")
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(filename="mujbot.log", encoding="utf-8", mode="w")
file_handler.setFormatter(logging.Formatter("%(created)f: [%(funcName)s @ %(filename)s:%(lineno)d] %(levelname)s -> %(message)s"))
logger.addHandler(file_handler)

logger.info("Booting up MUJ Bot...")
bot = mujbot.MUJBot()
bot.remove_command("help")

async def main():
    async with bot:
        await bot.start(bot.config.BOT_TOKEN)

asyncio.run(main())