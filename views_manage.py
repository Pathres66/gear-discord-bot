# views_manage.py

import discord
import asyncio
from utils import format_price, delete_ephemeral_later

from database import (
    toggle_purchased,
    delete_equipment,
)


class TogglePurchasedSelect(discord.ui.Select):
    def __init__(self, rows, refresh_func):
        self.refresh_main_message = refresh_func
        options = []

        for row in rows[:25]:
            item_id, item_name, category, weapon_type, color, price, purchased = row
            status = "✅" if purchased else "⬜"

            if category == "weapon":
                label = f"{status} {item_name} / {weapon_type} / {format_price(price)}"
            else:
                label = f"{status} {item_name} / {format_price(price)}"

            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=str(item_id),
                )
            )

        super().__init__(
            placeholder="Vyber položku na prepnutie kúpené/nekúpené",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        item_id = int(self.values[0])

        ok = await toggle_purchased(
            item_id=item_id,
            discord_user_id=str(interaction.user.id),
        )

        if not ok:
            await interaction.response.send_message(
                "❌ Túto položku nemôžeš upraviť.",
                ephemeral=True,
            )
            return

        await self.refresh_main_message(interaction.client)

        await interaction.response.edit_message(
            content="✅ Stav položky bol prepnutý.",
            view=None,
        )

        try:
            message = await interaction.original_response()
            await asyncio.sleep(3)
            await message.delete()
        except Exception:
            pass

class TogglePurchasedView(discord.ui.View):
    def __init__(self, rows, refresh_func):
        super().__init__(timeout=120)
        self.add_item(TogglePurchasedSelect(rows, refresh_func))


class DeleteItemSelect(discord.ui.Select):
    def __init__(self, rows, refresh_func):
        self.refresh_main_message = refresh_func
        options = []

        for row in rows[:25]:
            item_id, item_name, category, weapon_type, color, price, purchased = row

            if category == "weapon":
                label = f"{item_name} / {weapon_type} / {format_price(price)}"
            else:
                label = f"{item_name} / {format_price(price)}"

            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=str(item_id),
                )
            )

        super().__init__(
            placeholder="Vyber položku na zmazanie",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        item_id = int(self.values[0])

        ok = await delete_equipment(
            item_id=item_id,
            discord_user_id=str(interaction.user.id),
        )

        if not ok:
            await interaction.response.send_message(
                "❌ Túto položku nemôžeš zmazať.",
                ephemeral=True,
            )
            return

        await self.refresh_main_message(interaction.client)

        await interaction.response.edit_message(
            content="🗑️ Položka bola zmazaná.",
            view=None,
        )

        try:
            message = await interaction.original_response()
            await asyncio.sleep(3)
            await message.delete()
        except Exception:
            pass

class DeleteItemView(discord.ui.View):
    def __init__(self, rows, refresh_func):
        super().__init__(timeout=120)
        self.add_item(DeleteItemSelect(rows, refresh_func))