import discord
from discord.ext import commands


_RULES_MESSAGE = """
Hello and welcome to the official Audius Song of the Day Discord server! We want everyone to have fun here, regardless of their background, so we've got a few ground rules you'll need to follow:

**1**. Be respectful to anyone and everyone - treat others how you'd like to be treated yourself.
**2**. Avoid debating political or religious topics, as they might be controversial and may offend some members.
**3**. Provoking, insulting, bullying or personally attacking anyone will not be tolerated. This includes, but is not limited to, derogatory terms regarding religion, race/ethnicity, sex/gender, sexual orientation or any other discriminating factor or protected characteristic.
**4**. No NSFW content is allowed in any channel or voice chat -- if it would not be appropriate to look at on public transport or in an office, then it is not allowed here. Gore and violence are not allowed. Swearing may be tolerated in some circumstances, but it is not to be used in a derogatory manner (to attack individuals or groups), or be directed at another person under any circumstances.
**5**. Spam and Discord invite links are not allowed. Excessive use of all caps, large text, bold text etc will be treated as spam. Harassing users with unnecessary mentions will be treated as spam. Sending the same message multiple times in a short period or disrupting conversation will also be treated as spam.
**6**. Advertising is generally frowned upon. You can suggest tools and websites that users may like if they are relevant in conversation, but you should be very clear if you own the asset or receive benefit by sharing it. DMing people with advertisements unless they have agreed in advance in the regular channels is not allowed. One exception to this rule is sharing Audius links in the dedicated self-promotion channel - we encourage this!!
**7**. Please use the channels as they are intended to be used. A Moderator may ask you to move channel if you go off-topic. Please read relevant channel descriptions and rules for more info.
**8**. Be respectful to those in voice channels - playing loud or continuous audio in any voice channel is not allowed. Music is excluded from this as long as all people within the channel have consented. Please refrain from playing excessively explicit music. Don't force others out of a voice chat they are entitled to be in.
**9**. 'Backseat moderation', 'taking matters into your own hands' or 'witchhunting' is not permitted within the server. If you see behaviour which may break the rules, please make any online Staff member aware and they will deal with the situation accordingly.
**10**. There should not be any images or videos of any forms of real-world crash or violence in any channel, where there is likely or confirmed injury or loss-of-life. This may also include some GIFs or memes which contain potentially distressing content.
**11**. Use common sense. If you have to question whether something is allowed, it probably isn't.

If you have any questions regarding these rules or whether something specific would be allowed, speak to a member of staff or just don't do it.

-----

Additional Information:

Warnings stick with your account after leaving and re-joining. Once you reach 6 warnings, you will be permanently banned with no chance for appeal. You may be banned after fewer warnings depending on their severity as each ban is issued on a case-by-case basis after reviewing your moderation history.

**As with any server on Discord, we reserve the right to remove you and your permissions at any time for any reason we deem necessary.** If you build a house, that doesn't mean you have to let every person who knocks on the door come inside and trash the place. If you are someone who is refused entry - your access to one particular house does not inhibit your ability to speak freely outside the house and does not affect your rights. Likewise, if you're let in, that doesn't give you additional rights that you didn't have before joining.

You should keep in mind Discord's ToS and Community Guidelines at all times, which you can find at the links below:
<https://discord.com/terms>
<https://discord.com/guidelines>

By being in this server, you agree to follow these rules. If you do not agree, you may leave at any time. If you have any questions about the rules or their enforcement, please contact a member of Staff. Thank you for being part of our community, and we hope you have a great time here!
"""


class BOCmds(commands.Cog):
    def __init__(self, bot: discord.Bot) -> None:
        self.bot = bot

    @commands.is_owner()
    @commands.slash_command(name="clear", description="Clears the current channel of the SOTD Bot's messages.", contexts=[discord.InteractionContextType.bot_dm, discord.InteractionContextType.guild])
    async def clear_dm(self, ctx: discord.ApplicationContext) -> None:
        """Clear the current channel."""
        await ctx.defer(ephemeral=True)

        try:
            for message in await ctx.channel.history(limit=None).flatten():
                await message.delete() if message.author == self.bot.user else None
            await ctx.respond("Channel cleared.", ephemeral=True, delete_after=5)
        except discord.Forbidden:
            await ctx.respond(
                "I don't have permission to clear the channel.",
                ephemeral=True,
                delete_after=5,
            )
        return

    @commands.is_owner()
    @commands.slash_command(name="send", description="Sends a message to the channel specified.", contexts=[discord.InteractionContextType.bot_dm])
    @discord.option("message_id", str, description="The ID of the message to send.", required=True, choices=['rules'])
    @discord.option("channel", discord.TextChannel, description="The ID of the channel to send the message to.", required=True)
    async def _send_message(self, ctx: discord.ApplicationContext, message_id: str, channel: discord.TextChannel) -> None:
        """Sends a message to the channel specified."""
        if ctx.guild is not None:
            await ctx.respond("This command can only be used in DMs.", ephemeral=True)
            return

        match message_id:
            case "rules":
                await channel.send(_RULES_MESSAGE)
                await ctx.respond("Rules message sent.", ephemeral=True, delete_after=5)
            case _:
                await ctx.respond("Invalid message ID.", ephemeral=True, delete_after=5)
        
        return


def setup(bot: discord.Bot) -> None:
    """Register the BOCmds cog."""
    bot.add_cog(BOCmds(bot))