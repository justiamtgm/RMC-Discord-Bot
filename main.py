import discord, os, traceback
import aiosqlite
from discord.ext import commands
from discord import app_commands  
from dotenv import load_dotenv
from constants import RMC_EMBED_COLOR
import healthcheck
from utils.exceptions import NoLogChannelError, AdminAccessDeniedError

load_dotenv()
TOKEN = os.getenv("TOKEN")
if TOKEN:
    print(f"TOKEN найден!")
else:
    print("Ошибка загрузки токена")
COGS_DIR = "cogs"

print("🚀 Старт main.py")


print("🔄 Запуск healthcheck...")
healthcheck.start_in_background()
print("✅ Healthcheck инициализирован")




intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!rmc ", intents=intents, help_command=None)

bot.load_errors = []       # список ошибок при загрузке когов
bot.last_critical_error = None  # текст последней критической ошибки



@bot.event
async def on_ready():
    print(f"🎊 Бот запущен как {bot.user}")
    try:
        synced = await bot.tree.sync()  # глобальная регистрация
        print(f"🌍 Синхронизированы глобальные команды: {len(synced)}")
    except Exception as e:
        print(f"❌ Ошибка глобальной синхронизации: {e}")

    for guild in bot.guilds:
        try:
            synced = await bot.tree.sync(guild=guild)
            print(f"📂 Синхронизированы команды в гильдии {guild.name}: {len(synced)}")
        except discord.errors.Forbidden:
            print(f"⚠ Нет доступа для синхронизации в гильдии {guild.id} ({guild.name})")


async def load_cogs():
    print("🔄 Загрузка когов...")
    for filename in os.listdir(COGS_DIR):
        if filename.endswith(".py"):
            cog_name = f"{COGS_DIR}.{filename[:-3]}"
            try:
                await bot.load_extension(cog_name)
                print(f"✅ Ког {cog_name} загружен")
            except Exception as e:
                tb = traceback.format_exc()
                bot.load_errors.append(f"Ошибка загрузки {cog_name}: {e}")
                bot.last_critical_error = tb
                print(f"⚠ Ошибка при загрузке {cog_name}:\n{tb}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        if hasattr(ctx, "interaction") and ctx.interaction:
            await ctx.interaction.response.send_message(
                "❌ У вас нет прав для этого раздела команд. Если вы считаете это ошибкой, свяжитесь с администратором.",
                ephemeral=True
            )
        else:
            await ctx.send("❌ У вас нет прав для этого раздела команд. Если вы считаете это ошибкой, свяжитесь с администратором.")
        return

    raise error

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    error_text = "❌ Произошла непредвиденная ошибка при выполнении команды."

    if isinstance(error, NoLogChannelError):
        error_text = "Канал для логов не настроен. Пожалуйста, настройте канал с помощью команды `/set_log`."
    
    elif isinstance(error, AdminAccessDeniedError):
        error_text = "❌ Недостаточно прав для выполнения этой команды." 
    
    elif isinstance(error, app_commands.MissingPermissions):
        error_text = f"У вас недостаточно прав для выполнения этой команды. Требуемые права: {', '.join(error.missing_permissions)}"
    
    elif isinstance(error, app_commands.CommandInvokeError):
        original = error.original
        if isinstance(original, aiosqlite.OperationalError) and "no such table" in str(original):
            error_text = "❌ Ошибка базы данных: таблица не найдена. Попробуйте перезапустить бота для инициализации БД."
        else:
            error_text = f"❌ Произошла ошибка при выполнении команды: {str(original)}"

    if interaction.response.is_done():
        await interaction.followup.send(error_text, ephemeral=True)
    else:
        await interaction.response.send_message(error_text, ephemeral=True)




@bot.event
async def on_error(event, *args, **kwargs):
    bot.last_critical_error = traceback.format_exc()



async def main():
    async with bot:
        await load_cogs()
        print("🔑 Запуск авторизации Discord...")
        await bot.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
