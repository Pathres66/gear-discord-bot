# render.py

import discord
from discord.ext import commands

from config import EMBED_COLOR
from database import get_all_equipment, get_setting
from utils import COLOR_EMOJIS, COLOR_NAMES, format_price


async def build_equipment_embed() -> discord.Embed:
    rows = await get_all_equipment()

    embed = discord.Embed(
        title="📦 Tímové vybavenie",
        description="Prehľad zbraní a výbavy tímu.",
        color=EMBED_COLOR,
    )

    if not rows:
        embed.add_field(
            name="Zatiaľ bez položiek",
            value="Klikni na **➕ Pridať** a pridaj prvú zbraň alebo výbavu.",
            inline=False,
        )
        return embed

    players = {}
    total_price = 0
    purchased_count = 0
    waiting_count = 0

    for row in rows:
        item_id, user_id, discord_name, item_name, category, weapon_type, color, price, purchased = row

        players.setdefault(discord_name, [])
        total_price += price

        status = "✅" if purchased else "⬜"
        if purchased:
            purchased_count += 1
        else:
            waiting_count += 1

        if category == "weapon":
            color_icon = COLOR_EMOJIS.get(color, "▫️")
            color_name = COLOR_NAMES.get(color, color)
            line = (
                f"{status} {color_icon} "
                f"**{weapon_type}** / {color_name} — "
                f"{item_name} — **{format_price(price)}**"
            )
        else:
            line = (
                f"{status} 🎒 "
                f"**VÝBAVA** — {item_name} — **{format_price(price)}**"
            )

        players[discord_name].append(line)

    for player_name, items in players.items():
        embed.add_field(
            name=f"👤 {player_name}",
            value="\n".join(items),
            inline=False,
        )

    embed.add_field(
        name="Súhrn",
        value=(
            f"💰 Celková hodnota: **{format_price(total_price)}**\n"
            f"✅ Kúpené: **{purchased_count}**\n"
            f"⬜ Čaká na kúpu: **{waiting_count}**"
        ),
        inline=False,
    )

    return embed


async def refresh_main_message(bot: commands.Bot, view_factory):
    channel_id = await get_setting("equipment_channel_id")
    message_id = await get_setting("equipment_message_id")

    print("REFRESH channel_id:", channel_id)
    print("REFRESH message_id:", message_id)

    if not channel_id or not message_id:
        print("REFRESH STOP: chýba channel_id alebo message_id")
        return

    try:
        channel = bot.get_channel(int(channel_id))

        if channel is None:
            print("REFRESH: channel nie je v cache, skúšam fetch_channel")
            channel = await bot.fetch_channel(int(channel_id))

        message = await channel.fetch_message(int(message_id))
        embed = await build_equipment_embed()

        await message.edit(embed=embed, view=view_factory())
        print("REFRESH OK")

    except Exception as e:
        print("REFRESH ERROR:", repr(e))