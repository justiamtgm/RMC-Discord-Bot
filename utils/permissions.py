import utils.settings_cache as settings
import discord
from utils.exceptions import AdminAccessDeniedError

def load_admin_roles():
    data = settings.load_settings()
    return {int(r) for r in data.get("admin_roles", [])}


async def check_admin(ctx):
    """Проверка, является ли пользователь администратором или имеет роль из admin_roles."""
    admin_roles = load_admin_roles()

    if ctx.author.id == ctx.bot.owner_id:
        return True
    elif ctx.author.guild_permissions.administrator:
        return True
    elif any(role.id in admin_roles for role in ctx.author.roles):
        return True

    return False

async def check_admin_interaction(interaction: discord.Interaction) -> bool: ##use: await check_admin_interaction(interaction)
    """Проверка, является ли пользователь администратором или имеет роль из admin_roles (для slash-команд)."""
    admin_roles = load_admin_roles()

    # Проверка на администратора сервера
    if getattr(interaction.user, 'guild_permissions', discord.Permissions()).administrator:
        return True
        
    # Проверка по ролям
    if hasattr(interaction.user, 'roles'):
        if any(role.id in admin_roles for role in interaction.user.roles):
            return True
            
    raise AdminAccessDeniedError()

async def check_cog_access(ctx, required_access=None):
    """
    Универсальная проверка прав доступа для когов.
    """

    if required_access == "admin":
        return await check_admin(ctx)

    # пример добавления новых уровней 
    #if required_access == "analytics":
    #    return ctx.author.id in analytics_admins

    return True
