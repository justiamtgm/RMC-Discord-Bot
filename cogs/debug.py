from discord.ext import commands
import discord,json,io
from discord import app_commands
from utils.exceptions import NoLogChannelError
from utils.permissions import check_cog_access
from utils import settings_cache as settings
from constants import MAX_MESSAGE,RMC_EMBED_COLOR



class Debug(commands.Cog):
    required_access = "admin"
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True

    @commands.hybrid_command(name="ping", with_app_command=True, description="Проверка бота и вывод ошибок")
    async def ping(self, ctx: commands.Context):
        latency_ms = round(self.bot.latency * 1000)

        embed = discord.Embed(title="📡 Ping", color=discord.Color.green())
        embed.add_field(name="Задержка", value=f"{latency_ms} ms", inline=False)

        # Ошибки загрузки когов
        if getattr(self.bot, "load_errors", []):
            errors_text = "\n".join(self.bot.load_errors)
            embed.add_field(name="⚠ Ошибки при загрузке когов", value=f"```{errors_text}```", inline=False)

        # Последняя критическая ошибка
        if getattr(self.bot, "last_critical_error", None):
            embed.add_field(name="💥 Последняя критическая ошибка", 
                            value=f"```{self.bot.last_critical_error[-1000:]}```",  # обрезка до 1000 символов
                            inline=False)

        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="showjson", with_app_command=True, description="Вывести содержимое settings.json")
    async def showjson(self, ctx: commands.Context):
        # Загрузка настроек из кэша или файла
        data = settings.load_settings()

        if not data:
            await ctx.reply("❌ Файл `settings.json` пуст или отсутствует.")
            return

        # Форматируем красиво
        pretty_json = json.dumps(data, indent=4, ensure_ascii=False)

        if len(pretty_json) <= MAX_MESSAGE:
            embed=discord.Embed( description="```json\n" + pretty_json + "\n```", color=RMC_EMBED_COLOR )
            await ctx.reply(embed=embed)
            return

        file_bytes = io.BytesIO(pretty_json.encode("utf-8"))
        embed=discord.Embed( description="⚠️ Содержимое файла слишком большое для отправки в сообщении, отправляю как файл.", color=RMC_EMBED_COLOR )
        await ctx.reply(
            embed=embed,
            file=discord.File(file_bytes, filename="settings.json")
        )
    
    @commands.hybrid_command(
        name="set_log",
        with_app_command=True,
        description="Установить канал для отправки логов"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        log_channel="Канал для отправки логов",
    )
    async def set_log(self, ctx: commands.Context, log_channel: discord.TextChannel):
        
        if not log_channel.permissions_for(ctx.guild.me).send_messages:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"У бота нет прав писать в канал {log_channel.mention}",
                color=RMC_EMBED_COLOR
            )
            await ctx.send(embed=embed)
            return
        
        try:
            settings_data = settings.load_settings()
            settings_data['log_channel'] = log_channel.id
            settings.save_settings(settings_data)

            embed = discord.Embed(
                title="✅ Канал для логов успешно установлен",
                description=f"Установленный канал: {log_channel.mention}",
                color=RMC_EMBED_COLOR
            )
            await ctx.send(embed=embed)
            
            log_embed = discord.Embed(
                title="✅ Этот канал успешно установлен для отправки логов",
                description=f"Для изменения используйте `/set_log`",
                color=RMC_EMBED_COLOR
            )
            await log_channel.send(embed=log_embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Ошибка установки канала для логов",
                description=f"Ошибка `{e}`",
                color=RMC_EMBED_COLOR
            )
            await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="show_log",
        with_app_command=True,
        description="Посмотреть установленный канал для логов"
    )
    @app_commands.guild_only()
    async def show_log(self, ctx: commands.Context):
        
        settings_data = settings.load_settings()
        channel_id = settings_data.get('log_channel')
        log_channel = ctx.guild.get_channel(channel_id) if channel_id else None
        
        if log_channel:
            embed = discord.Embed(
                title="📃 Канал для логов",
                description=f"Для логов установлен этот канал: {log_channel.mention}",
                color=RMC_EMBED_COLOR
            )
            await ctx.send(embed=embed)
        else:
            raise NoLogChannelError()


async def setup(bot):
    await bot.add_cog(Debug(bot))
