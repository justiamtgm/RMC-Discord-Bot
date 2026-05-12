import discord
import time
import re
import asyncio
import io
import openpyxl
from datetime import datetime
from dataclasses import dataclass, asdict
from discord.ext import commands, tasks
from discord import app_commands
from utils.exceptions import NoLogChannelError
from utils.permissions import check_cog_access, check_admin_interaction
from utils import settings_cache as settings
from discord.ui import View, Button
from typing import Optional, List
from constants import RMC_EMBED_COLOR
from cogs.isolation import IsolatedUser

BOT_NAME_REGEXES = [
    re.compile(r"^[a-zA-Z._]+\d{3,8}\.?$", re.IGNORECASE),         # Покрывает: duelist_96035, nikitos511., echoexplorer05448
    re.compile(r"^[a-zA-Z_]+\.[a-zA-Z]{3,5}$", re.IGNORECASE),     # Покрывает: usagii.jjj
    re.compile(r"^[a-zA-Z]+\d+[._]+\d+$", re.IGNORECASE),          # Покрывает: asd2099._19909
    re.compile(r"^[\d._]+$"),                                      # Только цифры и знаки: 12345_67890
    re.compile(r"[bcdfghjklmnpqrstvwxz]{6,}", re.IGNORECASE),      # Набор из 6+ согласных подряд: dfghjkl
    re.compile(r"^(?:[a-zA-Z]+\d+){3,}[a-zA-Z]*$", re.IGNORECASE), # Чередование букв и цифр: a1b2c3d4
    re.compile(r"^[a-f0-9]{10,}$", re.IGNORECASE)                  # Сгенерированные хэши: a8b4f2c9e1
]


async def evaluate_suspicion(member: discord.Member) -> tuple[float, list]:
    score = 0.0
    reasons = []

    account_age_seconds = (discord.utils.utcnow() - member.created_at).total_seconds()

    if account_age_seconds < 86400:
        score += 3
        reasons.append("Аккаунту меньше 24 часов (+3)")
    elif account_age_seconds < 2592000: # 30 дней
        score += 2
        reasons.append("Аккаунту меньше месяца (+2)")
    elif account_age_seconds < 31536000: # 365 дней
        score += 1
        reasons.append("Аккаунту меньше года (+1)")

    if member.avatar is None:
        score += 1
        reasons.append("У аккаунта стандартный аватар (+1)")
    elif member.avatar.is_animated():
        score -= 1.5
        reasons.append("У аккаунта анимированный аватар (-1.5)")

    if member.global_name is None:
        score += 1
        reasons.append("У аккаунта не установлено отображаемое имя (+1)")

    if not member.public_flags.value:
        score += 0.5
        reasons.append("У аккаунта нет значков профиля (+0.5)")

    if any(pattern.match(member.name) for pattern in BOT_NAME_REGEXES):
        score += 3
        reasons.append("Ник попадает под паттерн спам-ботов (+3)")

    return score, reasons

class SuspicionActionView(discord.ui.View):
    def __init__(self, target_member: discord.Member, bot: commands.Bot, score: float):
        super().__init__(timeout=None)
        self.target_member = target_member
        self.bot = bot
        self.score = score

    @discord.ui.button(label="Изолировать", style=discord.ButtonStyle.danger)
    async def btn_isolate(self, interaction: discord.Interaction, button: discord.ui.Button):   
        user_roles = [
            role for role in self.target_member.roles 
            if not role.is_default() and not role.managed and role < interaction.guild.me.top_role
        ]
        user_role_ids = [role.id for role in user_roles]
        isolation_cog = self.bot.get_cog("Isolation")
        if not isolation_cog:
            return await interaction.response.send_message("❌ Ошибка: Модуль изоляции не найден.", ephemeral=True)

        isolated_user = IsolatedUser(
            roles=user_role_ids,
            isolated_at=time.time(),
            isolated_by=interaction.user.id,
            reason=f"[Omnivisor] Изолирован из-за высокого уровна подозрительности {self.score}"
        )

        async with isolation_cog._file_lock:
            isolated_data = await isolation_cog.load_isolated_data()
            isolated_data[str(self.target_member.id)] = isolated_user
            await isolation_cog.save_isolated_data(isolated_data)

        settings_data = settings.load_settings()
        isolation_role_id = settings_data.get('isolation_role_id')
        isolation_role = interaction.guild.get_role(isolation_role_id)

        if isolation_role:
            try:
                if user_roles:
                    await self.target_member.remove_roles(*user_roles, reason=f"Изолирован {interaction.user} через Omnivisor.")
                await self.target_member.add_roles(isolation_role, reason=f"Изолирован {interaction.user} через Omnivisor.")
            except discord.Forbidden:
                pass # Игнорируем недостаток прав, чтобы кнопка успела изменить состояние

        from utils import omnivisor_db as db
        await db.log_action(
            action_type="Изоляция",
            display_name=self.target_member.display_name,
            username=self.target_member.name,
            user_id=self.target_member.id,
            moderator_id=interaction.user.id,
            reason=isolated_user.reason,
            timestamp=int(isolated_user.isolated_at),
            joined_at=int(self.target_member.joined_at.timestamp()) if self.target_member.joined_at else 0
        )

        for child in self.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.add_field(
            name = "🛡️ Решение",
            value = f"✅ Изолирован модератором {interaction.user.mention}"
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Проигнорировать", style=discord.ButtonStyle.secondary)
    async def btn_ignore(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True

        from utils import omnivisor_db as db
        await db.log_action(
            action_type="Игнорирование подозрения",
            display_name=self.target_member.display_name,
            username=self.target_member.name,
            user_id=self.target_member.id,    
            moderator_id=interaction.user.id,
            reason="Модератор счел аккаунт безопасным",
            timestamp=int(time.time()),
            joined_at=int(self.target_member.joined_at.timestamp()) if self.target_member.joined_at else 0
        )
        embed = interaction.message.embeds[0]
        embed.add_field(
            name = "🛡️ Решение",
            value = f"👀 Проигнорирован модератором {interaction.user.mention}"
        )
        await interaction.response.edit_message(embed=embed, view=self)

class Omnivisor(commands.Cog):
    """Cog для организации работы проекта Омнивизор через РМК-Бота"""
    required_access = "admin"

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invites_cache = {}
        self.send_periodic_report.start()

    def cog_unload(self):
        self.send_periodic_report.cancel()

    async def cog_load(self):
        from utils import omnivisor_db as db
        await db.init_db()
        self.bot.loop.create_task(self.update_invite_cache_startup())

    async def update_invite_cache_startup(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                self.invites_cache[guild.id] = {invite.code: invite for invite in invites}
            except discord.Forbidden:
                self.invites_cache[guild.id] = {}

    @tasks.loop(minutes=30)
    async def send_periodic_report(self):
        settings_data = settings.load_settings()
        interval_hours = settings_data.get('report_interval_hours')

        if not interval_hours or interval_hours <= 0:
            return

        last_run = settings_data.get('last_report_timestamp', 0)
        
        if (time.time() - last_run) < (interval_hours * 3600):
            return

        log_channel_id = settings_data.get('log_channel')
        if not log_channel_id:
            return

        guild_to_process = None
        for guild in self.bot.guilds:
            if guild.get_channel(log_channel_id):
                guild_to_process = guild
                break
        
        if not guild_to_process:
            return

        print(f"Omnivisor: Running periodic report for guild {guild_to_process.name}")
        await self._send_report_and_clear_db(guild_to_process, settings_data)

        settings_data['last_report_timestamp'] = time.time()
        settings.save_settings(settings_data)

    @send_periodic_report.before_loop
    async def before_send_periodic_report(self):
        await self.bot.wait_until_ready()

    async def _generate_report_file(self, logs: list, guild: discord.Guild) -> Optional[discord.File]:
        if not logs:
            return None

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Omnivisor Logs"

        headers = [
            "ID Лога", "Действие", "Никнейм", "Имя аккаунта", 
            "ID Пользователя", "Дата действия", "Дата захода", 
            "Модератор (ID)", "Причина"
        ]
        ws.append(headers)

        mod_names_cache = {}

        for row in logs:
            action_time = datetime.fromtimestamp(row['timestamp']).strftime('%d.%m.%Y %H:%M:%S') if row['timestamp'] else "Неизвестно"
            join_time = datetime.fromtimestamp(row['joined_at']).strftime('%d.%m.%Y %H:%M:%S') if row['joined_at'] and row['joined_at'] > 0 else "Неизвестно"

            mod_name = "Система/Бот"
            mod_id = row['moderator_id']

            if mod_id:
                if mod_id in mod_names_cache:
                    mod_name = mod_names_cache[mod_id]
                else:
                    mod = guild.get_member(mod_id) 
                    if not mod:
                        try:
                            mod = await self.bot.fetch_user(mod_id)
                        except discord.NotFound:
                            mod = None
                    
                    mod_name = f"{getattr(mod, 'display_name', mod.name)} (@{mod.name})" if mod else f"Неизвестно (ID: {mod_id})"
                    mod_names_cache[mod_id] = mod_name

            ws.append([
                row['log_id'], row['action_type'], row['display_name'],
                row['username'], str(row['user_id']), action_time,
                join_time, mod_name, row['reason']
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        file_name = f"omnivisor_logs_{datetime.now().strftime('%d_%m_%Y_%H%M')}.xlsx"
        return discord.File(fp=buffer, filename=file_name)

    async def _send_report_and_clear_db(self, guild: discord.Guild, settings_data: dict):
        from utils import omnivisor_db as db
        logs = await db.get_logs_for_export()
        if not logs:
            print("Omnivisor: No logs to report. Skipping.")
            return

        report_file = await self._generate_report_file(logs, guild)
        if not report_file: return

        log_channel = self._get_log_channel(guild)
        report_embed = discord.Embed(title="📅 Периодический отчёт Omnivisor", description=f"Автоматически сформированный отчёт. Содержит **{len(logs)}** записей.", color=RMC_EMBED_COLOR, timestamp=discord.utils.utcnow())

        if log_channel:
            try:
                await log_channel.send(embed=report_embed, file=report_file)
            except discord.Forbidden:
                print(f"Omnivisor: Failed to send report to log channel {log_channel.id} due to permissions.")
            report_file.fp.seek(0)

        if settings_data.get('report_dm_enabled', False):
            role_ids = set(settings_data.get('auto_stat_roles', []))
            if role_ids:
                dm_count = 0
                for member in guild.members:
                    if not role_ids.isdisjoint({role.id for role in member.roles}):
                        try:
                            await member.send(embed=report_embed, file=report_file)
                            dm_count += 1
                            report_file.fp.seek(0)
                        except discord.Forbidden:
                            pass
                print(f"Omnivisor: Sent report via DM to {dm_count} users.")

        if settings_data.get('report_clear_db', False):
            await db.clear_action_logs()
            print("Omnivisor: Action logs cleared after sending report.")
        else:
            print("Omnivisor: Action logs kept intact after sending report.")

    async def cog_check(self, ctx: commands.Context):
        allowed = await check_cog_access(ctx, self.required_access)
        if not allowed:
            raise commands.CheckFailure()
        return True
    
    def _get_log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        """Загружает канал для логов из настроек"""
        settings_data = settings.load_settings()
        channel_id = settings_data.get('log_channel')
        log_channel = guild.get_channel(channel_id) if channel_id else None
        
        return log_channel
    
    def _get_omnivisor_roles(self) -> str:
        """Загружает роли для пинга в логировании из настроек"""
        settings_data = settings.load_settings()

        if not settings_data.get('auto_stat_enabled', True):
            return ""
        
        omnivisor_roles_ids = settings_data.get('auto_stat_roles', [])
        omnivisor_roles = " ".join([f"<@&{r}>" for r in omnivisor_roles_ids])
        return omnivisor_roles

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if invite.guild:
            if invite.guild.id not in self.invites_cache:
                self.invites_cache[invite.guild.id] = {}
            self.invites_cache[invite.guild.id][invite.code] = invite

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        if invite.guild and invite.guild.id in self.invites_cache:
            self.invites_cache[invite.guild.id].pop(invite.code, None)
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        from utils import omnivisor_db as db

        used_invite = None
        try:
            new_invites = await member.guild.invites()
            old_invites = self.invites_cache.get(member.guild.id, {})
            
            for invite in new_invites:
                old_invite = old_invites.get(invite.code)
                if old_invite and invite.uses > old_invite.uses:
                    used_invite = invite
                    break
                    
            self.invites_cache[member.guild.id] = {inv.code: inv for inv in new_invites}
        except discord.Forbidden:
            pass

        score, reasons = await evaluate_suspicion(member)

        await db.log_action(
            action_type="Новый участник на сервере",
            display_name=member.display_name,
            username=member.name,
            user_id=member.id,
            moderator_id=None,
            timestamp=int(time.time()),
            joined_at=int(member.joined_at.timestamp()) if member.joined_at else 0
        )

        settings_data = settings.load_settings()
        log_channel = self._get_log_channel(member.guild)
        omnivisor_roles = self._get_omnivisor_roles()
        
        if not log_channel:
            return # Предотвращаем падение с AttributeError, если канал не задан

        user_name = member.global_name or member.name
        
        log_embed = discord.Embed(
            title="📥 Новый участник на сервере",
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        log_embed.add_field(name="Участник", value=f"{member.mention}\nID: `{member.id}`\n@{user_name}", inline=True)
        log_embed.add_field(name="📅 Даты", value=f"Дата создания аккаунта: <t:{int(member.created_at.timestamp())}:d> | Зашёл на сервер: <t:{int(member.joined_at.timestamp())}:d>", inline=True)

        if used_invite:
            inviter_mention = used_invite.inviter.mention if used_invite.inviter else "Неизвестен"
            invite_info = f"**Ссылка:** {used_invite.url}\n**Создатель:** {inviter_mention}\n**Использований:** {used_invite.uses}"
        else:
            invite_info = "Ссылка неизвестна (vanity URL, виджет или API не успел обновиться)"
        log_embed.add_field(name="🔗 Приглашение", value=invite_info, inline=False)

        reasons_text = "\n".join(reasons) if reasons else "Подозрений нет"
        log_embed.add_field(name=f"📊 Индекс подозрения: {score}", value=f"```{reasons_text}```", inline=False)
        log_embed.set_thumbnail(url=member.display_avatar.url)

        if score >= 3:
            ping_roles = " ".join([f"<@&{r}>" for r in settings_data.get('admin_roles', [])])
            view = SuspicionActionView(member, self.bot, score)
            await log_channel.send(content=f"⚠️ {ping_roles} **Внимание, обнаружен вход подозрительного аккаунта!** Требуется внимание администрации", embed=log_embed, view=view)
        else:
            await log_channel.send(content=f"{omnivisor_roles}",embed=log_embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        from utils import omnivisor_db as db
        await asyncio.sleep(2)

        action_type = "Выход с сервера"
        moderator_id = None
        reason = "Самостоятельный выход"

        try:
            async for entry in member.guild.audit_logs(limit=3, action=discord.AuditLogAction.kick):
                if entry.target.id == member.id:
                    action_type = "Кик"
                    moderator_id = entry.user.id
                    reason = entry.reason or "Причина не указана"
                    break
        except discord.Forbidden:
            pass

        await db.log_action(
            action_type=action_type,
            display_name=member.display_name,
            username=member.name,
            user_id=member.id,
            moderator_id=moderator_id,
            timestamp=int(time.time()),
            joined_at=0,
            reason=reason
        )

        log_channel = self._get_log_channel(member.guild)
        omnivisor_roles = self._get_omnivisor_roles()

        if log_channel:
            log_embed = discord.Embed(
                title="📤 Участник покинул сервер",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            )
            log_embed.add_field(name="Участник", value=f"{member.mention} (`{member.id}`)\n@{member.name}", inline=True)
            log_embed.add_field(name="Действие", value=action_type, inline=True)
            if moderator_id:
                log_embed.add_field(name="Модератор", value=f"<@{moderator_id}>", inline=True)
                log_embed.add_field(name="Причина", value=f"```{reason}```", inline=False)

            await log_channel.send(content=omnivisor_roles, embed=log_embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        from utils import omnivisor_db as db
        
        await asyncio.sleep(2)
        action_type = "Бан"
        moderator_id = None
        reason = "Причина не указана"

        try:
            async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    moderator_id = entry.user.id
                    reason = entry.reason or "Причина не указана"
                    break
        except discord.Forbidden:
            pass

        display_name = getattr(user, 'display_name', user.name)

        await db.log_action(
            action_type = action_type, 
            display_name = display_name, 
            username = user.name, 
            user_id = user.id, 
            timestamp = int(time.time()), 
            joined_at = 0, 
            moderator_id = moderator_id, 
            reason = reason
        )

        settings_data = settings.load_settings()
        log_channel = self._get_log_channel(guild)
        omnivisor_roles = self._get_omnivisor_roles()

        if log_channel:
            log_embed = discord.Embed(
                title="🔨 Участник был забанен",
                color=RMC_EMBED_COLOR,
                timestamp=discord.utils.utcnow()
            ) 
            log_embed.add_field(name="Участник", value=f"{user.mention} (`{user.id}`)\n@{user.name}", inline=True)
            if moderator_id:
                log_embed.add_field(name="Модератор", value=f"<@{moderator_id}>", inline=True)
                log_embed.add_field(name="Причина", value=f"```{reason}```", inline=False)
            await log_channel.send(content=omnivisor_roles, embed=log_embed)

    @app_commands.command(
        name="omnivisor_export_logs",
        description="Выгрузить отчёт Omnivisor в Excel"
    )
    @app_commands.describe(
        clear_db="Очистить базу данных после выгрузки отчёта?"
    )
    @app_commands.choices(clear_db=[
        app_commands.Choice(name='Нет', value=0),
        app_commands.Choice(name='Да', value=1),
    ])
    async def omnivisor_export_logs(self, interaction: discord.Interaction, clear_db: int = 0):
        await check_admin_interaction(interaction)
        
        await interaction.response.defer(ephemeral=True)

        clear_db_bool = bool(clear_db)

        from utils import omnivisor_db as db
        logs = await db.get_logs_for_export()

        if not logs:
            return await interaction.followup.send("📭 База данных пуста. Действий для выгрузки нет.", ephemeral=True)
        
        discord_file = await self._generate_report_file(logs, interaction.guild)

        if not discord_file:
            return await interaction.followup.send("❌ Произошла ошибка при генерации файла отчёта.", ephemeral=True)

        response_embed = discord.Embed(
            title="✅ Выгрузка журнала успешно завершена!",
            description=f"Файл с **{len(logs)}** записями прикреплен к сообщению.",
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )
        if clear_db_bool:
            response_embed.add_field(
                name="🗑️ Очистка",
                value="База данных логов была очищена согласно запросу."
            )

        await interaction.followup.send(embed=response_embed, file=discord_file)

        if clear_db_bool:
            await db.clear_action_logs()
   
    @app_commands.command(
        name="omnivisor_test_report",
        description="Симулирует создание и отправку отчёта Omnivisor (без очистки БД)."
    )
    async def omnivisor_test_report(self, interaction: discord.Interaction):
        await check_admin_interaction(interaction)

        await interaction.response.defer(ephemeral=True)

        from utils import omnivisor_db as db
        logs = await db.get_logs_for_export()

        if not logs:
            return await interaction.followup.send("📭 База данных пуста. Действий для симуляции отчёта нет.", ephemeral=True)

        discord_file = await self._generate_report_file(logs, interaction.guild)

        if not discord_file:
            return await interaction.followup.send("❌ Произошла ошибка при генерации файла отчёта.", ephemeral=True)

        embed = discord.Embed(
            title="🧪 Тестовый отчёт Omnivisor",
            description=f"Это симуляция создания отчёта. Он содержит **{len(logs)}** записей.\n\n**Важно:** База данных **не была** очищена.",
            color=discord.Color.orange(), timestamp=discord.utils.utcnow())
        
        settings_data = settings.load_settings()
        log_channel = self._get_log_channel(interaction.guild)
        
        if log_channel:
            try:
                await log_channel.send(embed=embed, file=discord_file)
            except discord.Forbidden:
                pass
            discord_file.fp.seek(0)

        dm_count = 0
        if settings_data.get('report_dm_enabled', False):
            role_ids = set(settings_data.get('auto_stat_roles', []))
            if role_ids:
                for member in interaction.guild.members:
                    if not role_ids.isdisjoint({role.id for role in member.roles}):
                        try:
                            await member.send(embed=embed, file=discord_file)
                            dm_count += 1
                            discord_file.fp.seek(0)
                        except discord.Forbidden:
                            pass

        await interaction.followup.send(f"✅ Симуляция завершена. Отчёт отправлен в канал логов и в ЛС ({dm_count} пользователям).", ephemeral=True)

    @app_commands.command(
       name="omnivisor_sync_db",
       description="Создать слепок участников сервера для дополнения Протокол-ξ."
    )
    @app_commands.guild_only()
    async def omnivisor_sync_db(self, interaction: discord.Interaction):
        await check_admin_interaction(interaction)
        
        await interaction.response.defer(ephemeral=True)

        members_to_sync = []

        for member in interaction.guild.members:
            if member.bot:
                continue

            roles_list = [role.name for role in member.roles if not role.is_default()]
            roles_str = ", ".join(roles_list) if roles_list else "Нет ролей"

            joined_at = int(member.joined_at.timestamp()) if member.joined_at else 0
            created_at = int(member.created_at.timestamp())

            members_to_sync.append((
                "Синхронизация",        # action_type
                member.display_name,    # display_name
                member.name,            # username
                member.id,              # user_id
                created_at,             # created_at
                joined_at,              # joined_at
                roles_str               # roles
            ))

        from utils import omnivisor_db as db
        await db.sync_members(members_to_sync)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Server Snapshot"

        headers = [
            "Тип записи", "Никнейм", "Имя аккаунта", 
            "ID Пользователя", "Дата создания", "Дата захода", "Список ролей"
        ]
        ws.append(headers)

        for data in members_to_sync:
            c_time = datetime.fromtimestamp(data[4]).strftime('%d.%m.%Y %H:%M:%S')
            j_time = datetime.fromtimestamp(data[5]).strftime('%d.%m.%Y %H:%M:%S') if data[5] > 0 else "Неизвестно"
            
            ws.append([
                data[0], 
                data[1], 
                data[2], 
                str(data[3]), 
                c_time, 
                j_time, 
                data[6]  
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        file_name = f"omnivisor_snapshot_{datetime.now().strftime('%d_%m_%Y_%H%M')}.xlsx"
        discord_file = discord.File(fp=buffer, filename=file_name)

        response_embed = discord.Embed(
            title="🔄 База данных синхронизирована",
            description=(
                f"Данные участников обновлены в БД.\n"
                f"Всего обработано: **{len(members_to_sync)}** чел.\n\n"
                f"💾 Актуальный слепок прикреплен к сообщению."
            ),
            color=RMC_EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )

        await interaction.followup.send(embed=response_embed, file=discord_file)

    @app_commands.command(
        name="omnivisor_settings",
        description="Настройки системы уведомлений и мониторинга Omnivisor"
    )
    @app_commands.describe(
        notifications="Включить или выключить упоминания ролей Омнивизора",
        add_role="Добавить роль в список для пингов/рассылки отчётов",
        remove_role="Удалить роль из списка для пингов/рассылки отчётов",
        report_interval="Интервал отправки отчёта в часах (0 для отключения)",
        dm_reports="Отправлять отчёт в ЛС пользователям с ролями Омнивизора?",
        clear_db="Очищать БД после отправки периодического отчёта?"
    )
    async def omnivisor_settings(self, interaction: discord.Interaction, 
                                 notifications: Optional[bool] = None, 
                                 add_role: Optional[discord.Role] = None, 
                                 remove_role: Optional[discord.Role] = None,
                                 report_interval: Optional[app_commands.Range[int, 0, 720]] = None,
                                 dm_reports: Optional[bool] = None,
                                 clear_db: Optional[bool] = None):
        await check_admin_interaction(interaction)

        settings_data = settings.load_settings()
        changes = []

        if notifications is not None:
            settings_data['auto_stat_enabled'] = notifications
            status = "Включены" if notifications else "Выключены"
            changes.append(f"Уведомления: **{status}**")

        if add_role:
            roles = settings_data.get('auto_stat_roles', [])
            if add_role.id not in roles:
                roles.append(add_role.id)
                settings_data['auto_stat_roles'] = roles
                changes.append(f"Добавлена роль: {add_role.mention}")
            else:
                changes.append(f"⚠️ Роль {add_role.mention} уже есть в списке")

        if remove_role:
            roles = settings_data.get('auto_stat_roles', [])
            if remove_role.id in roles:
                roles.remove(remove_role.id)
                settings_data['auto_stat_roles'] = roles
                changes.append(f"Удалена роль: {remove_role.mention}")
            else:
                changes.append(f"⚠️ Роль {remove_role.mention} не найдена в списке")

        if report_interval is not None:
            settings_data['report_interval_hours'] = report_interval
            if report_interval > 0:
                changes.append(f"Интервал автоматических отчётов: **{report_interval} ч.**")
                settings_data['last_report_timestamp'] = time.time()
            else:
                changes.append("Автоматические отчёты: **Отключены**")

        if dm_reports is not None:
            settings_data['report_dm_enabled'] = dm_reports
            status = "Включена" if dm_reports else "Выключена"
            changes.append(f"Отправка отчётов в ЛС: **{status}**")

        if clear_db is not None:
            settings_data['report_clear_db'] = clear_db
            status = "Включена" if clear_db else "Выключена"
            changes.append(f"Очистка БД после авто-отчёта: **{status}**")

        if changes:
            settings.save_settings(settings_data)
            embed = discord.Embed(
                title="✅ Настройки Omnivisor обновлены",
                description="\n".join(changes),
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            await interaction.response.send_message(embed=embed)
        else:
            is_enabled = settings_data.get('auto_stat_enabled', True)
            roles_ids = settings_data.get('auto_stat_roles', [])
            roles_mentions = " ".join([f"<@&{r}>" for r in roles_ids]) if roles_ids else "Не настроены"
            report_interval_val = settings_data.get('report_interval_hours', 0)
            dm_enabled = settings_data.get('report_dm_enabled', False)
            clear_db_val = settings_data.get('report_clear_db', False)
            
            embed = discord.Embed(
                title="⚙️ Текущие настройки Omnivisor",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Уведомления о входе (пинги)", value="✅ Включены" if is_enabled else "❌ Выключены", inline=False)
            embed.add_field(name="Роли для уведомлений", value=roles_mentions, inline=False)
            if report_interval_val > 0:
                embed.add_field(name="Авто-отчёты", value=f"✅ Включены, раз в **{report_interval_val} ч.**", inline=True)
            else:
                embed.add_field(name="Авто-отчёты", value="❌ Выключены", inline=True)
            embed.add_field(name="Отправка отчётов в ЛС", value="✅ Включена" if dm_enabled else "❌ Выключена", inline=True)
            embed.add_field(name="Очистка БД после авто-отчёта", value="✅ Включена" if clear_db_val else "❌ Выключена", inline=True)
            embed.set_footer(text="Используйте параметры команды для изменения этих настроек")
            await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Omnivisor(bot))
