# views_add.py

import discord
import asyncio

from database import (
    add_equipment,
    get_available_weapon_prices,
    get_weapon_price,
    get_special_prices,
    get_special_price,
)

from utils import COLOR_EMOJIS, COLOR_NAMES, format_price


async def delete_current_message_after(interaction: discord.Interaction, delay: int = 3):
    try:
        message = await interaction.original_response()
        await asyncio.sleep(delay)
        await message.delete()
    except Exception:
        pass


class WeaponNameModal(discord.ui.Modal):
    def __init__(self, weapon_type: str, color: str, price: int, refresh_func, previous_interaction=None):
        super().__init__(title="Pridať zbraň")
        self.weapon_type = weapon_type
        self.color = color
        self.price = price
        self.refresh_main_message = refresh_func
        self.previous_interaction = previous_interaction

        self.weapon_name = discord.ui.TextInput(
            label="Názov zbrane",
            placeholder="Napr. M4A1, Glock 17, AK74...",
            max_length=50,
        )
        self.add_item(self.weapon_name)

    async def on_submit(self, interaction: discord.Interaction):
        await add_equipment(
            discord_user_id=str(interaction.user.id),
            discord_name=interaction.user.display_name,
            item_name=str(self.weapon_name.value),
            category="weapon",
            weapon_type=self.weapon_type,
            color=self.color,
            price=self.price,
        )

        await self.refresh_main_message(interaction.client)

        if self.previous_interaction:
            try:
                await self.previous_interaction.delete_original_response()
            except Exception:
                pass

        await interaction.response.send_message(
            f"✅ Pridané: **{self.weapon_name.value}** za **{format_price(self.price)}**",
            ephemeral=True,
        )

        asyncio.create_task(delete_current_message_after(interaction, 3))


class ColorSelect(discord.ui.Select):
    def __init__(self, weapon_type: str, price_rows, refresh_func):
        self.weapon_type = weapon_type
        self.refresh_main_message = refresh_func

        options = []

        for color, price in price_rows:
            options.append(
                discord.SelectOption(
                    label=f"{COLOR_NAMES.get(color, color)} — {format_price(price)}",
                    value=color,
                    emoji=COLOR_EMOJIS.get(color, "▫️"),
                )
            )

        super().__init__(
            placeholder="Vyber farbu zbrane",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        color = self.values[0]
        price = await get_weapon_price(self.weapon_type, color)

        if price is None:
            await interaction.response.edit_message(
                content="❌ Táto kombinácia typu a farby nemá nastavenú cenu.",
                view=None,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        await interaction.response.send_modal(
            WeaponNameModal(
                weapon_type=self.weapon_type,
                color=color,
                price=price,
                refresh_func=self.refresh_main_message,
                previous_interaction=interaction,
            )
        )


class ColorSelectView(discord.ui.View):
    def __init__(self, weapon_type: str, price_rows, refresh_func):
        super().__init__(timeout=120)
        self.add_item(ColorSelect(weapon_type, price_rows, refresh_func))


class WeaponTypeSelect(discord.ui.Select):
    def __init__(self, refresh_func):
        self.refresh_main_message = refresh_func

        options = [
            discord.SelectOption(label="AUTO", value="AUTO", emoji="🔫"),
            discord.SelectOption(label="SEMI", value="SEMI", emoji="🎯"),
            discord.SelectOption(label="MANUAL", value="MANUAL", emoji="🏹"),
        ]

        super().__init__(
            placeholder="Vyber režim zbrane",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        weapon_type = self.values[0]
        price_rows = await get_available_weapon_prices(weapon_type)

        if not price_rows:
            await interaction.response.edit_message(
                content="❌ Pre tento typ zbrane nie sú nastavené žiadne ceny.",
                view=None,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        await interaction.response.edit_message(
            content=f"Vybral si **{weapon_type}**. Teraz vyber farbu:",
            view=ColorSelectView(weapon_type, price_rows, self.refresh_main_message),
        )


class WeaponTypeView(discord.ui.View):
    def __init__(self, refresh_func):
        super().__init__(timeout=120)
        self.add_item(WeaponTypeSelect(refresh_func))


class SpecialItemSelect(discord.ui.Select):
    def __init__(self, special_rows, refresh_func):
        self.refresh_main_message = refresh_func

        emoji_map = {
            "Vesta": "🎽",
            "Helma": "🪖",
            "Granatomet": "💥",
        }

        options = []

        for item_name, price in special_rows:
            options.append(
                discord.SelectOption(
                    label=f"{item_name} — {format_price(price)}",
                    value=item_name,
                    emoji=emoji_map.get(item_name, "🎒"),
                )
            )

        super().__init__(
            placeholder="Vyber výbavu",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        item_name = self.values[0]
        price = await get_special_price(item_name)

        if price is None:
            await interaction.response.edit_message(
                content="❌ Táto výbava nemá nastavenú cenu.",
                view=None,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        await add_equipment(
            discord_user_id=str(interaction.user.id),
            discord_name=interaction.user.display_name,
            item_name=item_name,
            category="special",
            price=price,
        )

        await self.refresh_main_message(interaction.client)

        await interaction.response.edit_message(
            content=f"✅ Pridané: **{item_name}** za **{format_price(price)}**",
            view=None,
        )

        asyncio.create_task(delete_current_message_after(interaction, 3))


class SpecialItemView(discord.ui.View):
    def __init__(self, special_rows, refresh_func):
        super().__init__(timeout=120)
        self.add_item(SpecialItemSelect(special_rows, refresh_func))


class AddCategorySelect(discord.ui.Select):
    def __init__(self, refresh_func):
        self.refresh_main_message = refresh_func

        options = [
            discord.SelectOption(label="Zbraň", value="weapon", emoji="🔫"),
            discord.SelectOption(label="Výbava", value="special", emoji="🎒"),
        ]

        super().__init__(
            placeholder="Čo chceš pridať?",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]

        if category == "weapon":
            await interaction.response.edit_message(
                content="Vyber režim zbrane:",
                view=WeaponTypeView(self.refresh_main_message),
            )
            return

        special_rows = await get_special_prices()

        if not special_rows:
            await interaction.response.edit_message(
                content="❌ Nie sú nastavené žiadne ceny výbavy.",
                view=None,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        await interaction.response.edit_message(
            content="Vyber výbavu:",
            view=SpecialItemView(special_rows, self.refresh_main_message),
        )


class AddCategoryView(discord.ui.View):
    def __init__(self, refresh_func):
        super().__init__(timeout=120)
        self.add_item(AddCategorySelect(refresh_func))