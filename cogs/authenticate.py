"""
This module handles the authentication of the students into our server
"""

import logging
from typing import Union
import asyncio
import uuid
import datetime

import discord
from discord.ext import commands

from utils import *

bot: mujbot.MUJBot
logger = logging.getLogger("mujbot")

class Approvals(discord.ui.View):
    def __init__(self, userid: int, uuid_: str):
        super().__init__(timeout=None)
        self.userid = userid
        self.uuid = uuid_

        approve = discord.ui.Button(
            label='Accept',
            style=discord.ButtonStyle.green,
            custom_id=f'approval:{self.uuid}',
            emoji=consts.GREEN_TICK
        )
        approve.callback = self.approve
        self.add_item(approve)

        decline = discord.ui.Button(
            label='Decline',
            style=discord.ButtonStyle.red,
            custom_id=f'decline:{self.uuid}',
            emoji=consts.RED_TICK
        )
        decline.callback = self.decline
        self.add_item(decline)
        logger.info("Added view for %s with UUID %s", self.userid, self.uuid)

    async def approve(self, interaction: discord.Interaction):
        mod = interaction.user
        userid = self.userid
        logger.info("Approving %s with UUID %s (Mod: %s)", userid, self.uuid, mod.id)
        await interaction.response.defer(ephemeral=True)
        user = interaction.guild.get_member(userid)  # type: ignore
        if not user:
            return await interaction.followup.send("User not found. They might have left the server.", ephemeral=True)

        await interaction.followup.send(f"{consts.GREEN_TICK} Accepted {user} (`{user.id}`) to the server. The embed will be auto-deleted in 5 seconds.", ephemeral=True)
        
        query = """
        UPDATE verifications
        SET "status" = 'accepted', "mod" = $1, "doneAt" = $2, "isDone" = true
        WHERE "id" = $3
        """
        await bot.pool.execute(query, mod.id, datetime.datetime.utcnow(), self.uuid)
        await user.send(f"{consts.GREEN_TICK} Your verification request has been accepted. Welcome to the server!")
        await user.add_roles(bot.roles["membership"])
        await asyncio.sleep(5)
        await interaction.delete_original_response()
    

    async def decline(self, interaction: discord.Interaction):
        mod = interaction.user
        userid = self.userid
        logger.info("Declining %s with UUID %s (Mod: %s)", userid, self.uuid, mod.id)
        await interaction.response.defer(ephemeral=True)
        user = interaction.guild.get_member(userid)  # type: ignore
        if not user:
            return await interaction.followup.send("User not found. They might have left the server.", ephemeral=True)

        await interaction.followup.send(f"{consts.RED_TICK} Declined {user} (`{user.id}`) from the server. The embed will be auto-deleted in 5 seconds.", ephemeral=True)

        query = """
        UPDATE verifications
        SET "status" = 'declined', "mod" = $1, "doneAt" = $2, "isDone" = true
        WHERE "id" = $3
        """
        await bot.pool.execute(query, mod.id, datetime.datetime.utcnow(), self.uuid)
        await user.send(f"{consts.RED_TICK} Your verification request has been declined. Please try again after getting in touch with our moderators.")
        await asyncio.sleep(5)
        await interaction.delete_original_response()


async def verify_user(user: Union[discord.User, discord.Member]):
    """
    Then that image will be sent to one of our channels.
    An authorized person will have 2 options- "Accept" / "Decline".
    Upon accepting, they will be added a Member role.
    """

    def check(message: discord.Message):
        return message.author == user and message.guild is None

    try:
        message: discord.Message = await bot.wait_for('message', check=check, timeout=300)
    except asyncio.TimeoutError:
        await user.send("You took too long to respond. Please try again.")
        bot.verifications.remove(user)
        return
    
    if not message.attachments:
        await user.send("You did not send any attachments. Please try again by restarting the process.")
        bot.verifications.remove(user)
        return
    
    attachment = message.attachments[0]
    if not attachment.filename.endswith((".png", ".jpg", ".jpeg")):
        await user.send("You did not send a valid image (`png`, `jpg` or `jpeg`). Please try again by restarting the process.")
        bot.verifications.remove(user)
        return
    hard_attachment = await bot.get_channel(1134109174394007602).send(file=await attachment.to_file(filename=f"PAL-{user.id}.png"))  # type: ignore
    link = hard_attachment.attachments[0].url
    await send_verification_embed(user, link)
    await user.send("🟡 Your verification request has been sent to our moderators. Please wait for them to review it.")


async def send_verification_embed(user: Union[discord.User, discord.Member], link: str):
    channel: discord.TextChannel = bot.get_channel(bot.config.MOD_CHANNEL)  # type: ignore
    embed = discord.Embed(
        title="Verification Request",
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="User",
        value=f"{user.mention} | ID: `{user.id}`"
    )
    embed.set_image(url=link)
    uuid_ = str(uuid.uuid4())
    query = """
    INSERT INTO verifications ("id", "user", "image", "createdAt")
    VALUES ($1, $2, $3, $4)
    """
    await bot.pool.execute(query, uuid_, user.id, link, datetime.datetime.utcnow())
    await channel.send(embed=embed, view=Approvals(user.id, uuid_))
    

class Authenticator(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Start', style=discord.ButtonStyle.blurple, custom_id='authenticator_start2', emoji='🔒')
    async def start_authentication(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user in bot.verifications:
            await interaction.response.send_message('You have already begun the process. Please cancel or wait for it to timeout. This should be no longer than 5 minutes.', ephemeral=True)
            return
        try:
            await interaction.user.send("Please upload the document screenshot here. Make sure to hide your application number for security reasons.")
            await interaction.response.defer()
            bot.verifications.append(user)
            await verify_user(user)
        except discord.Forbidden:
            await interaction.response.send_message('I cannot DM you. Please open your DMs to continue.', ephemeral=True)
            return
        

class Authenticate(commands.Cog):

    def __init__(self, bot_: mujbot.MUJBot):
        global bot
        bot = bot_

    async def cog_load(self):
        logger.info("Loaded Authenticate Cog")
        bot.add_view(Authenticator())

        pending_verifications = await bot.pool.fetch("SELECT * FROM verifications WHERE \"isDone\" = false")
        for i in pending_verifications:
            view = Approvals(i["user"], i["id"])
            bot.add_view(view)
    
    @commands.command()
    async def launch(self, ctx: mujbot.CustomContext):
        """Launches the authentication process"""
        embed = discord.Embed(
            title="Authentication",
            description="""
To get full access to the server you must verify yourself that you are a student from Manipal University Jaipur. To verify please upload your Provisional Admission Order or any other proof that shows that you are a student of Manipal University Jaipur.

*Please hide your application number for security reasons.*
""",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="Where do I start?",
            value="Click the button below to start the authentication process!"
        )
        embed.set_footer(text="Make sure to have your DMs open.")
        embed.set_image(url="https://media.discordapp.net/attachments/1134027066208165909/1134095873136140434/Manipal_University1679046981_upload_logo.jpg")
        await ctx.send(embed=embed, view=Authenticator())


async def setup(bot: mujbot.MUJBot):
    await bot.add_cog(Authenticate(bot))