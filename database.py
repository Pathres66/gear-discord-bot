# database.py

import aiosqlite

DB_NAME = "gear.db"


DEFAULT_WEAPON_PRICES = {
    "AUTO": {
        "white": 3200,
        "yellow": 17500,
        "orange": 25000,
        "green": 46000,
    },
    "SEMI": {
        "white": 2200,
        "yellow": 8800,
        "orange": 15000,
        "green": 23000,
        "blue": 42000,
    },
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


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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

        await db.execute("""
            CREATE TABLE IF NOT EXISTS price_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                weapon_type TEXT NOT NULL DEFAULT '',
                color TEXT NOT NULL DEFAULT '',
                item_name TEXT NOT NULL DEFAULT '',
                price INTEGER NOT NULL,
                UNIQUE(category, weapon_type, color, item_name)
            )
        """)

        await db.commit()


async def seed_default_prices():
    async with aiosqlite.connect(DB_NAME) as db:
        count_cursor = await db.execute("SELECT COUNT(*) FROM price_config")
        count_row = await count_cursor.fetchone()
        current_count = count_row[0] if count_row else 0

        if current_count > 0:
            return

        for weapon_type, colors in DEFAULT_WEAPON_PRICES.items():
            for color, price in colors.items():
                await db.execute("""
                    INSERT INTO price_config (
                        category, weapon_type, color, item_name, price
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, ("weapon", weapon_type, color, "", price))

        for item_name, price in DEFAULT_SPECIAL_PRICES.items():
            await db.execute("""
                INSERT INTO price_config (
                    category, weapon_type, color, item_name, price
                )
                VALUES (?, ?, ?, ?, ?)
            """, ("special", "", "", item_name, price))

        await db.commit()


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        await db.commit()


async def get_setting(key: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def add_equipment(
    discord_user_id: str,
    discord_name: str,
    item_name: str,
    category: str,
    price: int,
    weapon_type: str | None = None,
    color: str | None = None,
):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
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
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            discord_user_id,
            discord_name,
            item_name,
            category,
            weapon_type,
            color,
            price,
        ))
        await db.commit()


async def get_all_equipment():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT id, discord_user_id, discord_name, item_name, category,
                   weapon_type, color, price, purchased
            FROM equipment
            ORDER BY discord_name ASC, id ASC
        """)
        return await cursor.fetchall()


async def get_user_equipment(discord_user_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT id, item_name, category, weapon_type, color, price, purchased
            FROM equipment
            WHERE discord_user_id = ?
            ORDER BY id ASC
        """, (discord_user_id,))
        return await cursor.fetchall()


async def toggle_purchased(item_id: int, discord_user_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT purchased
            FROM equipment
            WHERE id = ? AND discord_user_id = ?
        """, (item_id, discord_user_id))

        row = await cursor.fetchone()
        if not row:
            return False

        new_value = 0 if row[0] else 1

        await db.execute("""
            UPDATE equipment
            SET purchased = ?
            WHERE id = ? AND discord_user_id = ?
        """, (new_value, item_id, discord_user_id))

        await db.commit()
        return True


async def delete_equipment(item_id: int, discord_user_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT id
            FROM equipment
            WHERE id = ? AND discord_user_id = ?
        """, (item_id, discord_user_id))

        row = await cursor.fetchone()
        if not row:
            return False

        await db.execute("""
            DELETE FROM equipment
            WHERE id = ? AND discord_user_id = ?
        """, (item_id, discord_user_id))

        await db.commit()
        return True


async def get_all_equipment_for_admin():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT id, discord_name, item_name, category, weapon_type, color, price, purchased
            FROM equipment
            ORDER BY discord_name ASC, id ASC
        """)
        return await cursor.fetchall()


async def admin_delete_equipment(item_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT id
            FROM equipment
            WHERE id = ?
        """, (item_id,))

        row = await cursor.fetchone()
        if not row:
            return False

        await db.execute("""
            DELETE FROM equipment
            WHERE id = ?
        """, (item_id,))

        await db.commit()
        return True


async def delete_all_equipment():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM equipment")
        await db.commit()


async def is_adding_locked():
    value = await get_setting("adding_locked")
    return value == "1"


async def set_adding_locked(locked: bool):
    await set_setting("adding_locked", "1" if locked else "0")


async def get_weapon_price(weapon_type: str, color: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT price
            FROM price_config
            WHERE category = 'weapon'
            AND weapon_type = ?
            AND color = ?
            AND item_name = ''
        """, (weapon_type, color))
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_available_weapon_prices(weapon_type: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT color, price
            FROM price_config
            WHERE category = 'weapon'
            AND weapon_type = ?
            AND item_name = ''
            ORDER BY id ASC
        """, (weapon_type,))
        return await cursor.fetchall()


async def get_special_prices():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT item_name, price
            FROM price_config
            WHERE category = 'special'
            AND weapon_type = ''
            AND color = ''
            ORDER BY id ASC
        """)
        return await cursor.fetchall()


async def get_special_price(item_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT price
            FROM price_config
            WHERE category = 'special'
            AND weapon_type = ''
            AND color = ''
            AND item_name = ?
        """, (item_name,))
        row = await cursor.fetchone()
        return row[0] if row else None


async def update_weapon_price(weapon_type: str, color: str, new_price: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO price_config (category, weapon_type, color, item_name, price)
            VALUES ('weapon', ?, ?, '', ?)
            ON CONFLICT(category, weapon_type, color, item_name)
            DO UPDATE SET price = excluded.price
        """, (weapon_type, color, new_price))

        await db.execute("""
            UPDATE equipment
            SET price = ?
            WHERE category = 'weapon'
            AND weapon_type = ?
            AND color = ?
        """, (new_price, weapon_type, color))

        await db.commit()


async def update_special_price(item_name: str, new_price: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO price_config (category, weapon_type, color, item_name, price)
            VALUES ('special', '', '', ?, ?)
            ON CONFLICT(category, weapon_type, color, item_name)
            DO UPDATE SET price = excluded.price
        """, (item_name, new_price))

        await db.execute("""
            UPDATE equipment
            SET price = ?
            WHERE category = 'special'
            AND item_name = ?
        """, (new_price, item_name))

        await db.commit()