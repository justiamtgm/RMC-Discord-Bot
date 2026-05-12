import discord
from discord.ext import commands
from discord.ui import Select, View
from discord import app_commands
from utils.permissions import check_cog_access
from utils import settings_cache as settings
from constants import RMC_EMBED_COLOR

COG_DESCRIPTIONS = {
    "Anniversary": ("🎉 Годовщина", "Просмотр информации о годовщине сервера"),
    "Rules": ("📜 Правила", "Удобный просмотр пунктов правил сервера"),
    "Wiki": ("📚 Википедия", "Поиск статей по моддингу Hearts of Iron IV"),
    "AdminSettings": ("💎 Админ-роли", "Настройка прав доступа администраторов"),
    "AdminUtils": ("🛠️ Утилиты", "Технические утилиты для обновления бота"),
    "Debug": ("📡 Дебаг", "Отладка работы бота и логирование"),
    "FilterChannels": ("📵 Фильтруемые каналы", "Настройка каналов «только для медиа»"),
    "Isolation": ("🔒 Изолятор", "Управление наказаниями и изоляцией нарушителей"),
    "Messaging": ("📨 Сообщения бота", "Отправка сообщений и ответов через бота"),
    "Omnivisor": ("👁️ Omnivisor", "Omnivisor — система многоуровневого логирования, аудита и аналитического контроля развития сервера."),
    "Reports": ("🚨 Репорты", "Система анонимных жалоб пользователей"),
    "Resolution": ("📝 Резолюции", "Создание официальных голосований-резолюций"),
    "StarChannels": ("⭐ Звёздные каналы", "Настройка авто-веток и реакций для творчества"),
    "Starboard": ("🌟 Starboard", "Настройка доски почёта для лучших работ"),
    "HelpCmd": ("❓ Справка", "Справочная система бота")
}

class CommandWrapper:
    def __init__(self, name, description, prefix):
        self.name = name
        self.description = description
        self.prefix = prefix

class HelpDropdown(Select):
    def __init__(self, categories, is_admin):
        self.categories = categories
        self.is_admin = is_admin
        
        options = []
        for cog_name in categories.keys():
            # Подтягиваем красивые названия и описания из маппинга
            title, desc = COG_DESCRIPTIONS.get(cog_name, (f"🧩 {cog_name}", "Дополнительный функционал"))
            emoji = title.split()[0] if " " in title else "🧩"
            label = title.split(" ", 1)[1] if " " in title else title
            
            options.append(discord.SelectOption(
                label=label,
                description=desc[:100],
                emoji=emoji,
                value=cog_name
            ))
        
        super().__init__(
            placeholder="Выберите раздел документации...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        cog_name = self.values[0]
        commands_list = self.categories[cog_name]
        title, desc = COG_DESCRIPTIONS.get(cog_name, (f"🧩 Раздел: {cog_name}", "Команды этого модуля."))
        
        embed = discord.Embed(
            title=f"{title}",
            description=f"**{desc}**\n\nЗдесь представлен список команд данного раздела. Подробности использования можно узнать, начав вводить команду.",
            color=RMC_EMBED_COLOR
        )
        
        for cmd in commands_list:
            cmd_string = f"`{cmd.prefix}{cmd.name}`" if cmd.prefix != "🖱️" else f"`ПКМ → Приложения → {cmd.name}`"
            embed.add_field(
                name=cmd_string,
                value=cmd.description or "Контекстное меню / Без описания",
                inline=False
            )
            
        embed.set_footer(text="Для перехода к другому разделу, используйте меню ниже ⬇️")
        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(View):
    def __init__(self, categories, is_admin, author):
        super().__init__(timeout=600)
        self.author = author
        self.add_item(HelpDropdown(categories, is_admin))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Вы не можете использовать это меню.", ephemeral=True)
            return False
        return True
        
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            pass # Можно добавить обновление сообщения для блокировки селекта, если нужно
        except Exception:
            pass

class HelpCmd(commands.Cog):
    """Справочная система бота"""
    required_access = None

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True

    @commands.hybrid_command(
        name="help",
        with_app_command=True,
        description="Показывает интерактивную документацию по боту"
    )
    async def help(self, ctx: commands.Context):
        user_roles = getattr(ctx.author, 'roles', [])
        settings_data = settings.load_settings()
        admin_roles = settings_data.get('admin_roles', [])
        
        is_admin = False
        if ctx.author.id == self.bot.owner_id or getattr(ctx.author, 'guild_permissions', discord.Permissions()).administrator:
            is_admin = True
        elif any(role.id in admin_roles for role in user_roles):
            is_admin = True
            
        categories = {}

        # 1. Сбор гибридных и префиксных команд
        for command in self.bot.commands:
            if command.hidden or command.name == "help":
                continue
            
            cog = command.cog
            cog_name = cog.__class__.__name__ if cog else "Остальное"
            req_access = getattr(cog, 'required_access', None) if cog else None
            
            # Фильтр для юзеров (скрываем админские коги)
            if req_access == "admin" and not is_admin:
                continue

            if cog_name not in categories:
                categories[cog_name] = []
                
            prefix = "/" if isinstance(command, commands.HybridCommand) else "!rmc "
            categories[cog_name].append(CommandWrapper(command.name, command.description, prefix))

        # 2. Сбор чистых слэш-команд и контекстных меню
        for cmd in self.bot.tree.walk_commands():
            # Пропускаем, если это гибридная команда (уже есть в bot.commands)
            if any(c.name == cmd.name for c in self.bot.commands):
                continue
            
            cog = cmd.binding if hasattr(cmd, 'binding') else None
            cog_name = cog.__class__.__name__ if cog else "Остальное"
            req_access = getattr(cog, 'required_access', None) if cog else None

            if req_access == "admin" and not is_admin:
                continue

            if cog_name not in categories:
                categories[cog_name] = []

            # Контекстные меню не вызываются через слеш
            if isinstance(cmd, app_commands.ContextMenu):
                prefix = "🖱️"
            else:
                prefix = "/"
                
            categories[cog_name].append(CommandWrapper(cmd.name, cmd.description, prefix))

        # Очистка пустых категорий
        categories = {k: v for k, v in categories.items() if v}
        
        if not categories:
            await ctx.reply("❌ Команды не найдены!")
            return
            
        embed = discord.Embed(
            title="📖 Документация бота РМК",
            description=(
                "Добро пожаловать в справочный центр РМК-Бота!\n\n"
                "Функционал разбит по логическим блокам. Используйте **выпадающее меню ниже**, чтобы выбрать интересующий вас раздел и посмотреть список доступных команд.\n\n"
                f"**Ваш уровень доступа:** {'`Администратор` 👑' if is_admin else '`Пользователь` 👤'}"
            ),
            color=RMC_EMBED_COLOR
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        view = HelpView(categories, is_admin, ctx.author)
        await ctx.reply(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(HelpCmd(bot))