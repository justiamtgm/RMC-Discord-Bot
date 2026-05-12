import discord
import datetime
# import os, aiohttp
from discord.ext import commands
from discord import app_commands
# from discord import Webhook
from constants import RMC_EMBED_COLOR
# try:
#     from dotenv import load_dotenv
#     load_dotenv()
#     TOKEN = os.getenv("TOKEN")
# except:
#     print('Can\'t load TOKEN from .env')
from utils.permissions import check_cog_access, check_admin_interaction
from utils import settings_cache as settings


class Resolution(commands.Cog):
    """Cog для написания резолюций"""
    required_access = "admin"

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True

    @app_commands.command(
        name="resolution",
        description="Создать резолюцию"
    )
    @app_commands.guild_only()
    async def resolution(self, interaction: discord.Interaction):
        await check_admin_interaction(interaction)

        """Создать резолюцию"""
        modal = ResolutionModal()
        await interaction.response.send_modal(modal)


class ResolutionModal(discord.ui.Modal, title="Создание резолюции"):
    number = discord.ui.TextInput(
        label="Номер резолюции",
        placeholder="Например: 23",
        max_length=10
    )
    title_input = discord.ui.TextInput(
        label="Название резолюции",
        placeholder="Например: О бане Кирилла",
        max_length=100
    )
    description = discord.ui.TextInput(
        label="Описание резолюции",
        placeholder="Опиши суть",
        style=discord.TextStyle.paragraph,
        max_length=2000
    )
    duration = discord.ui.TextInput(
        label="Время для голосования (максимум неделя)",
        placeholder="Например: 7",
        max_length=2
    )

    def __init__(self):
        super().__init__()

    async def on_submit(self, interaction: discord.Interaction):
        print(f"[ResolutionModal] submitted by {interaction.user} in {interaction.channel} (guild {interaction.guild})")
        
        # Проверяем число
        try:
            duration_days = int(self.duration.value)
            if duration_days < 1 or duration_days > 7:
                await interaction.response.send_message(
                    "❌ Длительность голосования должна быть от 1 до 7 дней.",
                    ephemeral=True
                )
                return
        except ValueError:
            await interaction.response.send_message(
                "❌ Неверный формат времени! Укажите число.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"Резолюция #{self.number.value}: {self.title_input.value}",
            description=self.description.value,
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Автор: {interaction.user.display_name}")

        await interaction.response.send_message("✅ Резолюция публикуется...", ephemeral=True)
        
        data = settings.load_settings()
        admin_roles_ids = data.get("admin_roles", [])

        admin_mentions = " ".join(
            role.mention
            for rid in admin_roles_ids
            if (role := interaction.guild.get_role(rid))
        ) or "⚠️ (Нет настроенных админ-ролей)"
        
        poll = discord.Poll(
            question=f"Резолюция #{self.number.value}: {self.title_input.value}",
            duration=datetime.timedelta(days=duration_days),
            multiple=False
        )
        poll.add_answer(text="За", emoji=discord.PartialEmoji(name="approved", id=1419728225797541958))
        poll.add_answer(text="Против", emoji=discord.PartialEmoji(name="declined", id=1419728189059502080))
        poll.add_answer(text="Воздерживаюсь", emoji=discord.PartialEmoji(name="abstained", id=1419906353316495471))
        
        await interaction.channel.send(content=admin_mentions, embed=embed, poll=poll)

    # Legacy:
    # async def create_poll(self, interaction: discord.Interaction, duration_days: int):
    #     """Создает опрос через прямой HTTP запрос к Discord API"""
    #     try:
    #         headers = {
    #             "Authorization": f"Bot {TOKEN}",
    #             "Content-Type": "application/json"
    #         }
    #         
    #         poll_data = {
    #             "poll": {
    #                 "question": {
    #                     "text": f"Резолюция #{self.number.value}: {self.title_input.value}"
    #                 },
    #                 "answers": [
    #                     {"poll_media": {"text": "За", "emoji": {"id": 1419728225797541958, "name": "approved"}}}, #<:approved:1422601900737560656>
    #                     {"poll_media": {"text": "Против", "emoji": {"id": 1419728189059502080, "name": "declined"}}}, #<:declined:1422601837370146969>
    #                     {"poll_media": {"text": "Воздерживаюсь", "emoji": {"id": 1419906353316495471,"name": "abstained"}}} #<:abstained:1422601751336321096>
    #                 ],
    #                 "duration": duration_days * 24,
    #                 "allow_multiselect": False
    #             }
    #         }
    #         
    #         async with aiohttp.ClientSession() as session:
    #             async with session.post(
    #                 f"https://discord.com/api/v10/channels/{self.channel.id}/messages",
    #                 headers=headers,
    #                 json=poll_data
    #             ) as response:
    #                 
    #                 if response.status == 200:
    #                     print(f"[ResolutionModal] Poll created successfully in channel {self.channel.id}")
    #                 else:
    #                     error_text = await response.text()
    #                     print(f"[ResolutionModal] Failed to create poll: {response.status} - {error_text}")
    #                     
    #                     error_embed = discord.Embed(
    #                         title="❌ Ошибка при создании опроса",
    #                         description="Не удалось создать опрос для голосования. Проверьте права бота.",
    #                         color=0xff0000
    #                     )
    #                     await self.channel.send(embed=error_embed)
    #                     
    #     except Exception as e:
    #         print(f"[ResolutionModal] Error creating poll: {e}")
    #         
    #         error_embed = discord.Embed(
    #             title="❌ Ошибка при создании опроса",
    #             description=f"Произошла ошибка: {str(e)}",
    #             color=0xff0000
    #         )
    #         await self.channel.send(embed=error_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Resolution(bot))