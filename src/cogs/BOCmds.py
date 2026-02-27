import discord
from discord.ext import commands


class BOCmds(commands.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    @commands.is_owner()
    @commands.slash_command(name="clear-dm", description="Clears the DM channel.", contexts=[discord.InteractionContextType.bot_dm])
    async def clear_dm(self, ctx: discord.ApplicationContext) -> None:
        """Clear the DM channel."""
        if ctx.guild is not None:
            await ctx.respond("This command can only be used in DMs.", ephemeral=True)
            return

        try:
            for message in await ctx.channel.history(limit=None).flatten():
                await message.delete() if message.author == self.bot.user else None
            await ctx.respond("DM channel cleared.", ephemeral=True, delete_after=5)
        except discord.Forbidden:
            await ctx.respond(
                "I don't have permission to clear the DM channel.",
                ephemeral=True,
                delete_after=5,
            )


def setup(bot: discord.Bot) -> None:
    """Register the BOCmds cog."""
    bot.add_cog(BOCmds(bot))