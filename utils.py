# utils.py
import asyncio

COLOR_EMOJIS = {
    "white": "⚪",
    "yellow": "🟡",
    "orange": "🟠",
    "green": "🟢",
    "blue": "🔵",
    "purple": "🟣",
    "red": "🔴",
    "brown": "🟤",
}

COLOR_NAMES = {
    "white": "biela",
    "yellow": "žltá",
    "orange": "oranžová",
    "green": "zelená",
    "blue": "modrá",
    "purple": "fialová",
    "red": "červená",
    "brown": "hnedá",
}


def format_price(price: int) -> str:
    return f"{price:,}".replace(",", " ")


async def delete_ephemeral_later(interaction, delay: int = 3):
    await asyncio.sleep(delay)
    try:
        await interaction.delete_original_response()
    except Exception:
        pass