import discord
from discord.ext import commands
from discord import app_commands
from constants import RMC_EMBED_COLOR


class EmbedSender(commands.Cog):
    """Cog для отправки embed-сообщений через префикс и Slash команды."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ===== Общая функция для отправки embed =====
    async def _send_embed(
        self,
        *,
        channel: discord.TextChannel,
        title: str,
        description: str,
        color: str,
        reply_func,
        image_url: str | None = None,
        thumbnail_url: str | None = None
    ):
        try:
            try:
                color_int = int(color, 16)
            except (ValueError, TypeError):
                color_int = int(RMC_EMBED_COLOR, 16)

            embed = discord.Embed(
                title=title,
                description=description,
                color=color_int
            )

            if image_url:
                embed.set_image(url=image_url)

            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            embed.set_footer(text="")
            await channel.send(embed=embed)
            await reply_func(f"Embed отправлен в {channel.mention}")

        except Exception as e:
            await reply_func(f"Произошла ошибка при отправке embed: {e}")

    # ===== Slash команда /embed create =====
    embed = app_commands.Group(
        name="embed",
        description="Управление embed-сообщениями"
    )

    @embed.command(name="create", description="Создать и отправить embed")
    async def embed_create(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        description: str,
        color: str = RMC_EMBED_COLOR,
        image_url: str | None = None,
        thumbnail_url: str | None = None
    ):
        await self._send_embed(
            channel=channel,
            title=title,
            description=description,
            color=color,
            image_url=image_url,
            thumbnail_url=thumbnail_url,
            reply_func=lambda msg: interaction.response.send_message(msg, ephemeral=True)
        )

    # ===== Префикс команда !rmc createembed =====
    @commands.command(name="createembed")
    async def createembed(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        title: str,
        description: str,
        color: str = RMC_EMBED_COLOR,
        image_url: str | None = None,
        thumbnail_url: str | None = None
    ):
        await self._send_embed(
            channel=channel,
            title=title,
            description=description,
            color=color,
            image_url=image_url,
            thumbnail_url=thumbnail_url,
            reply_func=ctx.reply
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedSender(bot))
