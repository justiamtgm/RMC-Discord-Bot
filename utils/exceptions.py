from discord import app_commands

class NoLogChannelError(Exception):
    """Исключение, возникающее когда канал логов не настроен или не найден"""
    pass
class AdminAccessDeniedError(app_commands.AppCommandError):
    """Исключение, возникающее при отсутствии прав администратора для слеш-команд"""
    pass