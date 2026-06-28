# database.py

import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("Chýba DATABASE_URL")


DEFAULT_WEAPON_PRICES = {
    "AUTO": {"white": 3200, "yellow": 17500, "orange": 25000, "green": 46000},
    "SEMI": {"white": 2200, "yellow": 8800, "orange": 15000, "green": 23000, "blue": 42000},
    "MANUAL": {
        "white": 1300,
        "yellow": 4400,
        "orange": 9500,
        "green": 13000,
        "blue": 30000,
        "purple": 40000,
        "red": 80000,
        "brown": 160000,
    },
}

DEFAULT_SPECIAL_PRICES = {
    "Vesta": 15300,
    "Helma": 11700,
    "Granatomet": 38300,
}


async def connect():
    return await asyncpg.connect(DATABASE_URL)


async def init_db():
    conn = await connect()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS equipment (
                id SERIAL PRIMARY KEY,
                discord_user_id TEXT NOT NULL,
                discord_name TEXT NOT NULL,
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                weapon_type TEXT,
                color TEXT,
                price INTEGER NOT NULL,
                purchased INTEGER NOT NULL DEFAULT 0
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS price_config (
                id SERIAL PRIMARY KEY,
                category TEXT NOT NULL,
                weapon_type TEXT NOT NULL DEFAULT '',
                color TEXT NOT NULL DEFAULT '',
                item_name TEXT NOT NULL DEFAULT '',
                price INTEGER NOT NULL,
                UNIQUE(category, weapon_type, color, item_name)
            )
        """)
    finally:
        await conn.close()


async def seed_default_prices():
    conn = await connect()
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM price_config")

        if count and count > 0:
            return

        for weapon_type, colors in DEFAULT_WEAPON_PRICES.items():
            for color, price in colors.items():
                await conn.execute("""
                    INSERT INTO price_config (category, weapon_type, color, item_name, price)
                    VALUES ('weapon', $1, $2, '', $3)
                    ON CONFLICT(category, weapon_type, color, item_name)
                    DO NOTHING
                """, weapon_type, color, price)

        for item_name, price in DEFAULT_SPECIAL_PRICES.items():
            await conn.execute("""
                INSERT INTO price_config (category, weapon_type, color, item_name, price)
                VALUES ('special', '', '', $1, $2)
                ON CONFLICT(category, weapon_type, color, item_name)
                DO NOTHING
            """, item_name, price)
    finally:
        await conn.close()


async def set_setting(key: str, value: str):
    conn = await connect()
    try:
        await conn.execute("""
            INSERT INTO settings (key, value)
            VALUES ($1, $2)
            ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value
        """, key, value)
    finally:
        await conn.close()


async def get_setting(key: str):
    conn = await connect()
    try:
        return await conn.fetchval(
            "SELECT value FROM settings WHERE key = $1",
            key,
        )
    finally:
        await conn.close()


async def add_equipment(
    discord_user_id: str,
    discord_name: str,
    item_name: str,
    category: str,
    price: int,
    weapon_type: str | None = None,
    color: str | None = None,
):
    conn = await connect()
    try:
        await conn.execute("""
            INSERT INTO equipment (
                discord_user_id,
                discord_name,
                item_name,
                category,
                weapon_type,
                color,
                price,
                purchased
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, 0)
        """, discord_user_id, discord_name, item_name, category, weapon_type, color, price)
    finally:
        await conn.close()


async def get_all_equipment():
    conn = await connect()
    try:
        return await conn.fetch("""
            SELECT id, discord_user_id, discord_name, item_name, category,
                   weapon_type, color, price, purchased
            FROM equipment
            ORDER BY discord_name ASC, id ASC
        """)
    finally:
        await conn.close()


async def get_user_equipment(discord_user_id: str):
    conn = await connect()
    try:
        return await conn.fetch("""
            SELECT id, item_name, category, weapon_type, color, price, purchased
            FROM equipment
            WHERE discord_user_id = $1
            ORDER BY id ASC
        """, discord_user_id)
    finally:
        await conn.close()


async def toggle_purchased(item_id: int, discord_user_id: str):
    conn = await connect()
    try:
        purchased = await conn.fetchval("""
            SELECT purchased
            FROM equipment
            WHERE id = $1 AND discord_user_id = $2
        """, item_id, discord_user_id)

        if purchased is None:
            return False

        new_value = 0 if purchased else 1

        await conn.execute("""
            UPDATE equipment
            SET purchased = $1
            WHERE id = $2 AND discord_user_id = $3
        """, new_value, item_id, discord_user_id)

        return True
    finally:
        await conn.close()


async def delete_equipment(item_id: int, discord_user_id: str):
    conn = await connect()
    try:
        result = await conn.execute("""
            DELETE FROM equipment
            WHERE id = $1 AND discord_user_id = $2
        """, item_id, discord_user_id)

        return result.endswith("1")
    finally:
        await conn.close()


async def get_all_equipment_for_admin():
    conn = await connect()
    try:
        return await conn.fetch("""
            SELECT id, discord_name, item_name, category, weapon_type, color, price, purchased
            FROM equipment
            ORDER BY discord_name ASC, id ASC
        """)
    finally:
        await conn.close()


async def admin_delete_equipment(item_id: int):
    conn = await connect()
    try:
        result = await conn.execute("""
            DELETE FROM equipment
            WHERE id = $1
        """, item_id)

        return result.endswith("1")
    finally:
        await conn.close()


async def delete_all_equipment():
    conn = await connect()
    try:
        await conn.execute("DELETE FROM equipment")
    finally:
        await conn.close()


async def is_adding_locked():
    value = await get_setting("adding_locked")
    return value == "1"


async def set_adding_locked(locked: bool):
    await set_setting("adding_locked", "1" if locked else "0")


async def get_weapon_price(weapon_type: str, color: str):
    conn = await connect()
    try:
        return await conn.fetchval("""
            SELECT price
            FROM price_config
            WHERE category = 'weapon'
            AND weapon_type = $1
            AND color = $2
            AND item_name = ''
        """, weapon_type, color)
    finally:
        await conn.close()


async def get_available_weapon_prices(weapon_type: str):
    conn = await connect()
    try:
        return await conn.fetch("""
            SELECT color, price
            FROM price_config
            WHERE category = 'weapon'
            AND weapon_type = $1
            AND item_name = ''
            ORDER BY id ASC
        """, weapon_type)
    finally:
        await conn.close()


async def get_special_prices():
    conn = await connect()
    try:
        return await conn.fetch("""
            SELECT item_name, price
            FROM price_config
            WHERE category = 'special'
            AND weapon_type = ''
            AND color = ''
            ORDER BY id ASC
        """)
    finally:
        await conn.close()


async def get_special_price(item_name: str):
    conn = await connect()
    try:
        return await conn.fetchval("""
            SELECT price
            FROM price_config
            WHERE category = 'special'
            AND weapon_type = ''
            AND color = ''
            AND item_name = $1
        """, item_name)
    finally:
        await conn.close()


async def update_weapon_price(weapon_type: str, color: str, new_price: int):
    conn = await connect()
    try:
        await conn.execute("""
            INSERT INTO price_config (category, weapon_type, color, item_name, price)
            VALUES ('weapon', $1, $2, '', $3)
            ON CONFLICT(category, weapon_type, color, item_name)
            DO UPDATE SET price = EXCLUDED.price
        """, weapon_type, color, new_price)

        await conn.execute("""
            UPDATE equipment
            SET price = $1
            WHERE category = 'weapon'
            AND weapon_type = $2
            AND color = $3
        """, new_price, weapon_type, color)
    finally:
        await conn.close()


async def update_special_price(item_name: str, new_price: int):
    conn = await connect()
    try:
        await conn.execute("""
            INSERT INTO price_config (category, weapon_type, color, item_name, price)
            VALUES ('special', '', '', $1, $2)
            ON CONFLICT(category, weapon_type, color, item_name)
            DO UPDATE SET price = EXCLUDED.price
        """, item_name, new_price)

        await conn.execute("""
            UPDATE equipment
            SET price = $1
            WHERE category = 'special'
            AND item_name = $2
        """, new_price, item_name)
    finally:
        await conn.close()