#!/usr/bin/env python
from discord.ext import commands
from discord.ext.commands import has_permissions
import cogs.colourEmbed as functions
import traceback
import sqlite3


class adminCommands(commands.Cog, name="🛠️ Admin Commands"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(description=f"embedsettings [colour code e.g. 0xffff0]**\n\nChanges the colour of the embed.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    @has_permissions(administrator=True)
    async def embedsettings(self, ctx, colour: str):

        try:
            colourCode = int(colour, 16)
            if not 16777216 >= colourCode >= 0:
                return await functions.errorEmbedTemplate(ctx, f"The colour code input is invalid, please try again.", ctx.author)
            await functions.colourChange(ctx, colour)

        except ValueError:
            traceback.print_exc()
            return await functions.errorEmbedTemplate(ctx, f"The colour code input is invalid, please try again.", ctx.author)



def setup(bot):
    bot.add_cog(adminCommands(bot))
