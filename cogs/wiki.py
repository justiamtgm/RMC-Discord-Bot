import discord
from typing import Optional
from discord import app_commands
from discord.ext import commands
from constants import RMC_EMBED_COLOR
from utils.permissions import check_cog_access

class Wiki(commands.Cog):
    required_access = None
    """Cog для просмотра страниц Вики"""

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.wiki_map = {
            #"help": "Заменено на сообщение справки. Получается, этот вариант отныне невозможно вызвать?",
            "map": "\n - https://hoi4.paradoxwikis.com/Map_modding \n - https://hoi4.paradoxwikis.com/State_modding \n - https://hoi4.paradoxwikis.com/Supply_areas_modding \n - https://hoi4.paradoxwikis.com/Strategic_region_modding \n - https://hoi4.paradoxwikis.com/Nudger",
            "country": "https://hoi4.paradoxwikis.com/Country_creation",
            "data_structures": "https://hoi4.paradoxwikis.com/Data_structures",
            "effect": "https://hoi4.paradoxwikis.com/Effect",
            "defines": "https://hoi4.paradoxwikis.com/Defines",
            "scopes": "https://hoi4.paradoxwikis.com/Scopes",
            "on_actions": "https://hoi4.paradoxwikis.com/On_actions",
            "achievement": "https://hoi4.paradoxwikis.com/Achievement_modding",
            "autonomy": "https://hoi4.paradoxwikis.com/Autonomy_state_modding",
            "building": "https://hoi4.paradoxwikis.com/Building_modding",
            "cosmetic_tag": "https://hoi4.paradoxwikis.com/Cosmetic_tag_modding",
            "division": "https://hoi4.paradoxwikis.com/Division_modding",
            "equipment": "https://hoi4.paradoxwikis.com/Equipment_modding",
            "event": "https://hoi4.paradoxwikis.com/Event_modding",
            "ideology": "https://hoi4.paradoxwikis.com/Ideology_modding",
            "mio": "https://hoi4.paradoxwikis.com/Military_industrial_organization_modding",
            "decision": "https://hoi4.paradoxwikis.com/Decision_modding",
            "resources": "https://hoi4.paradoxwikis.com/Resources_modding",
            "unit": "https://hoi4.paradoxwikis.com/Unit_modding",
            "entity": "https://hoi4.paradoxwikis.com/Entity_modding",
            "font": "https://hoi4.paradoxwikis.com/Font_modding",
            "music": "https://hoi4.paradoxwikis.com/Music_modding",
            "sound": "https://hoi4.paradoxwikis.com/Sound_modding",
            "portrait": "https://hoi4.paradoxwikis.com/Portrait_modding",
            "namelist": "https://hoi4.paradoxwikis.com/Namelist_modding",
            "mod_structure": "https://hoi4.paradoxwikis.com/Mod_structure",
            "console": "https://hoi4.paradoxwikis.com/Console_commands",
            "troubleshooting": "https://hoi4.paradoxwikis.com/Troubleshooting",
            "scripted_gui": "https://hoi4.paradoxwikis.com/Scripted_GUI_modding",
            "interface": "https://hoi4.paradoxwikis.com/Interface_modding",
            "modifiers": "\n - https://hoi4.paradoxwikis.com/Modifiers \n - https://hoi4.paradoxwikis.com/List_of_modifiers",
            "idea": "https://hoi4.paradoxwikis.com/Idea_modding",
            "technology": "https://hoi4.paradoxwikis.com/Technology_modding",
            "bop": "https://hoi4.paradoxwikis.com/Balance_of_power_modding",
            "bookmark": "https://hoi4.paradoxwikis.com/Bookmark_modding",
            "gfx": "\n - https://hoi4.paradoxwikis.com/Graphical_asset_modding \n - https://hoi4.paradoxwikis.com/Posteffect_modding \n - https://hoi4.paradoxwikis.com/Particle_modding",
            "ai": "\n - https://hoi4.paradoxwikis.com/AI_modding \n - https://hoi4.paradoxwikis.com/AI_focuses",
            "character": "https://hoi4.paradoxwikis.com/Character_modding",
            "localisation": "https://hoi4.paradoxwikis.com/Localisation",
            "national_focuses": "https://hoi4.paradoxwikis.com/National_focus_modding",
        }
    @commands.hybrid_command(
        name="wiki",
        with_app_command=True,
        description="Посмотреть страницу вики по моддингу."
    )
    @app_commands.describe(wiki_id="Выберите статью вики")
    
    async def wiki(self, ctx: commands.Context, wiki_id: Optional[str] = None):
        """Показать статью вики по идентификатору."""
        
        articles_list = []

        for article_name in self.wiki_map.keys():
            articles_list.append(f"- `{article_name}`")

        if wiki_id is None or wiki_id == "help":
            available_articles = ", ".join([f"`{key}`" for key in self.wiki_map.keys()])
            embed = discord.Embed(
                title="📚 Доступные статьи вики",
                description=f"Всего статей: {len(self.wiki_map)}\n\n{available_articles}",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text="Для повторной справки используйте !rmc wiki help")
            await ctx.send(embed=embed)
            return
            
        answer = self.wiki_map.get(wiki_id)
        if answer:
            embed = discord.Embed(
                title=f"📖Статья `{wiki_id}`",
                description=f"🔗{answer}",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text="Список доступных статей можно посмотреть по !rmc wiki help")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Такой статьи нет в базе!",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text="Список доступных статей можно посмотреть по !rmc wiki help")
            await ctx.send(embed=embed)

    @wiki.autocomplete('wiki_id')
    async def wiki_autocomplete(self, interaction: discord.Interaction, current: str):
        """Автодополнение для поиска статей"""
        choices = []
        
        if not current or "help".startswith(current.lower()):
            choices.append(app_commands.Choice(name="📚 Полный список статей", value="help"))
        
        for key in self.wiki_map.keys():
            display_name = key.replace('_', ' ').title()
            
            if (not current or  
                current.lower() in key.lower() or 
                current.lower() in display_name.lower()):
                
                if len(choices) < 24:  
                    choices.append(app_commands.Choice(name=display_name, value=key))
                else:
                    break
        
        return choices

async def setup(bot: commands.Bot):
    await bot.add_cog(Wiki(bot))
