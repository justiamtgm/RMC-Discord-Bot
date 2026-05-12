import aiosqlite
import os

# Путь к файлу базы данных SQLite
DB_PATH = "omnivisor.db"

async def init_db():
    # Создаем таблицы, если они отсутствуют
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS action_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT,
                display_name TEXT,
                username TEXT,
                user_id INTEGER,
                timestamp INTEGER,
                joined_at INTEGER,
                moderator_id INTEGER,
                reason TEXT
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS members_sync (
                sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT,
                display_name TEXT,
                username TEXT,
                user_id INTEGER,
                created_at INTEGER,
                joined_at INTEGER,
                roles_str TEXT
            )
        ''')
        await db.commit()

async def log_action(action_type, display_name, username, user_id, timestamp, joined_at, moderator_id=None, reason=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO action_logs (action_type, display_name, username, user_id, timestamp, joined_at, moderator_id, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (action_type, display_name, username, user_id, timestamp, joined_at, moderator_id, reason))
        await db.commit()

async def get_logs_for_export():
    async with aiosqlite.connect(DB_PATH) as db:
        # Используем Row для возврата данных в виде словаря (ожидается в вашем коде omnivisor.py)
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM action_logs') as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def clear_action_logs():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM action_logs')
        await db.commit()

async def sync_members(members_to_sync):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany('''
            INSERT INTO members_sync (action_type, display_name, username, user_id, created_at, joined_at, roles_str)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', members_to_sync)
        await db.commit()