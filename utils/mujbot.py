"""
File that contains the bot class
"""
import logging
import os
import traceback
from typing import List, Union

import discord
from discord.ext import commands
import aiohttp
import orjson
import asyncpg

import config
logger = logging.getLogger("mujbot")

class CustomContext(commands.Context):
    """The custom context class for MUJ Bot"""

class MUJBot(commands.Bot):
    """The main bot class"""

    def __init__(self) -> None:
        super().__init__(command_prefix=config.PREFIX, intents=discord.Intents.all())
        if os.name == "nt":
            self.beta = True
        else:
            self.beta = False
        
        self.config = config
        self.pool: asyncpg.Pool
        self.verifications: List[Union[discord.User, discord.Member]] = []

        self.roles = {
            "membership": discord.Object(id=1134096770511687750)
        }
    
    async def on_ready(self) -> None:
        """Event that triggers when the bot is ready"""
        print(f"Logged in as {self.user}")
    
    async def get_context(self, message, *, cls=CustomContext):
        return await super().get_context(message, cls=cls)
    
    async def setup_hook(self):
        logger.info("Environment: %s", "Development" if self.beta else "Production")
        logger.info("Logged in as: %s", self.user)

        self.session = aiohttp.ClientSession()

        def _encode_jsonb(value):
            return orjson.dumps(value).decode("utf8")

        def _decode_jsonb(value):
            return orjson.loads(value)

        async def init(con: asyncpg.Connection):
            await con.set_type_codec(
                "jsonb",
                schema="pg_catalog",
                encoder=_encode_jsonb,
                decoder=_decode_jsonb,
                format="text",
            )

        self.pool = await asyncpg.create_pool(
            self.config.POSTGRES_URI,
            init=init,
            command_timeout=60,
            max_size=20,
            min_size=20,
        )  # type: ignore

        logger.info("Connected to PostgreSQL")

        initial_extentions = [
            "cogs.authenticate"
        ]
        os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
        os.environ["JISHAKU_NO_DM_TRACEBACK"] = "True"
        os.environ["JISHAKU_HIDE"] = "True"
        await self.load_extension("jishaku")
        for i in initial_extentions:
            name = i.rsplit(".", maxsplit=1)[-1]
            try:
                logger.info("[COG]: Loading %s", name)
                await self.load_extension(i)
                logger.info("[COG]: Loaded %s", name)
            except: # pylint: disable=bare-except
                traceback.print_exc()
