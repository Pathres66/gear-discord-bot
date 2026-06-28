# views_admin.py

import discord
import asyncio

from database import (
    delete_all_equipment,
    set_adding_locked,
    get_all_equipment_for_admin,
    admin_delete_equipment,
    update_weapon_price,
    update_special_price,
    get_available_weapon_prices,
    get_special_prices,
)

from utils import format_price, COLOR_EMOJIS, COLOR_NAMES


async def delete_current_message_after(interaction: discord.Interaction, delay: int = 3):
    try:
        message = await interaction.original_response()
        await asyncio.sleep(delay)
        await message.delete()
    except Exception:
        pass


class PriceEditModal(discord.ui.Modal):
    def __init__(
        self,
        refresh_func,
        price_type: str,
        weapon_type: str | None = None,
        color: str | None = None,
        item_name: str | None = None,
        previous_interaction=None
    ):
        super().__init__(title="Upraviť cenu")
        self.refresh_main_message = refresh_func
        self.price_type = price_type
        self.weapon_type = weapon_type
        self.color = color
        self.item_name = item_name

        self.new_price = discord.ui.TextInput(
            label="Nová cena",
            placeholder="Napr. 42000",
            max_length=10,
        )
        self.add_item(self.new_price)
        self.previous_interaction = previous_interaction

    async def on_submit(self, interaction: discord.Interaction):
        try:
            price = int(str(self.new_price.value).replace(" ", ""))
        except ValueError:
            await interaction.response.send_message(
                "❌ Cena musí byť číslo.",
                ephemeral=True,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        if price < 0:
            await interaction.response.send_message(
                "❌ Cena nemôže byť záporná.",
                ephemeral=True,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        if self.price_type == "weapon":
            await update_weapon_price(self.weapon_type, self.color, price)
            label = f"{self.weapon_type} / {COLOR_NAMES.get(self.color, self.color)}"
        else:
            await update_special_price(self.item_name, price)
            label = self.item_name

        await self.refresh_main_message(interaction.client)

        if self.previous_interaction:
             try:
                 await self.previous_interaction.delete_original_response()
             except Exception:
                 pass
             
        await interaction.response.send_message(
            f"💰 Cena upravená: **{label}** → **{format_price(price)}**",
            ephemeral=True,
        )
       
        asyncio.create_task(delete_current_message_after(interaction, 3))


class PriceWeaponColorSelect(discord.ui.Select):
    def __init__(self, weapon_type: str, rows, refresh_func):
        self.weapon_type = weapon_type
        self.refresh_main_message = refresh_func

        options = []
        for color, price in rows[:25]:
            options.append(
                discord.SelectOption(
                    label=f"{COLOR_NAMES.get(color, color)} — aktuálne {format_price(price)}",
                    value=color,
                    emoji=COLOR_EMOJIS.get(color, "▫️"),
                )
            )

        super().__init__(
            placeholder="Vyber farbu, ktorej chceš zmeniť cenu",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        color = self.values[0]

        await interaction.response.send_modal(
             PriceEditModal(
         refresh_func=self.refresh_main_message,
        price_type="weapon",
        weapon_type=self.weapon_type,
        color=color,
        previous_interaction=interaction,
    )
)


class PriceWeaponColorView(discord.ui.View):
    def __init__(self, weapon_type: str, rows, refresh_func):
        super().__init__(timeout=120)
        self.add_item(PriceWeaponColorSelect(weapon_type, rows, refresh_func))


class PriceWeaponTypeSelect(discord.ui.Select):
    def __init__(self, refresh_func):
        self.refresh_main_message = refresh_func

        options = [
            discord.SelectOption(label="AUTO", value="AUTO", emoji="🔫"),
            discord.SelectOption(label="SEMI", value="SEMI", emoji="🎯"),
            discord.SelectOption(label="MANUAL", value="MANUAL", emoji="🏹"),
        ]

        super().__init__(
            placeholder="Vyber typ zbrane",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        weapon_type = self.values[0]
        rows = await get_available_weapon_prices(weapon_type)

        if not rows:
            await interaction.response.edit_message(
                content="❌ Pre tento typ zbrane nie sú nastavené ceny.",
                view=None,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        await interaction.response.edit_message(
            content=f"Vybral si **{weapon_type}**. Teraz vyber farbu:",
            view=PriceWeaponColorView(weapon_type, rows, self.refresh_main_message),
        )


class PriceWeaponTypeView(discord.ui.View):
    def __init__(self, refresh_func):
        super().__init__(timeout=120)
        self.add_item(PriceWeaponTypeSelect(refresh_func))


class PriceSpecialSelect(discord.ui.Select):
    def __init__(self, rows, refresh_func):
        self.refresh_main_message = refresh_func

        emoji_map = {
            "Vesta": "🎽",
            "Helma": "🪖",
            "Granatomet": "💥",
        }

        options = []
        for item_name, price in rows[:25]:
            options.append(
                discord.SelectOption(
                    label=f"{item_name} — aktuálne {format_price(price)}",
                    value=item_name,
                    emoji=emoji_map.get(item_name, "🎒"),
                )
            )

        super().__init__(
            placeholder="Vyber výbavu, ktorej chceš zmeniť cenu",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        item_name = self.values[0]

        await interaction.response.send_modal(
             PriceEditModal(
              refresh_func=self.refresh_main_message,
                price_type="special",
                item_name=item_name,
                previous_interaction=interaction,
             )
        )


class PriceSpecialView(discord.ui.View):
    def __init__(self, rows, refresh_func):
        super().__init__(timeout=120)
        self.add_item(PriceSpecialSelect(rows, refresh_func))


class PriceCategorySelect(discord.ui.Select):
    def __init__(self, refresh_func):
        self.refresh_main_message = refresh_func

        options = [
            discord.SelectOption(label="Zbraň", value="weapon", emoji="🔫"),
            discord.SelectOption(label="Výbava", value="special", emoji="🎒"),
        ]

        super().__init__(
            placeholder="Čomu chceš zmeniť cenu?",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]

        if category == "weapon":
            await interaction.response.edit_message(
                content="Vyber typ zbrane:",
                view=PriceWeaponTypeView(self.refresh_main_message),
            )
            return

        rows = await get_special_prices()

        if not rows:
            await interaction.response.edit_message(
                content="❌ Nie sú nastavené žiadne ceny výbavy.",
                view=None,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        await interaction.response.edit_message(
            content="Vyber výbavu:",
            view=PriceSpecialView(rows, self.refresh_main_message),
        )


class PriceCategoryView(discord.ui.View):
    def __init__(self, refresh_func):
        super().__init__(timeout=120)
        self.add_item(PriceCategorySelect(refresh_func))


class AdminPanelView(discord.ui.View):
    def __init__(self, is_admin_func, refresh_func):
        super().__init__(timeout=120)
        self.is_admin = is_admin_func
        self.refresh_main_message = refresh_func

    @discord.ui.button(
        label="Zamknúť pridávanie",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
    )
    async def lock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.edit_message(
                content="❌ Toto môže používať iba admin.",
                view=None,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        await set_adding_locked(True)

        await interaction.response.edit_message(
            content="🔒 Pridávanie bolo uzamknuté.",
            view=None,
        )
        asyncio.create_task(delete_current_message_after(interaction, 3))

    @discord.ui.button(
        label="Odomknúť pridávanie",
        emoji="🔓",
        style=discord.ButtonStyle.success,
    )
    async def unlock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.edit_message(
                content="❌ Toto môže používať iba admin.",
                view=None,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        await set_adding_locked(False)

        await interaction.response.edit_message(
            content="🔓 Pridávanie bolo odomknuté.",
            view=None,
        )
        asyncio.create_task(delete_current_message_after(interaction, 3))

    @discord.ui.button(
        label="Reset tabuľky",
        emoji="🧹",
        style=discord.ButtonStyle.danger,
    )
    async def reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.edit_message(
                content="❌ Toto môže používať iba admin.",
                view=None,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        await delete_all_equipment()
        await self.refresh_main_message(interaction.client)

        await interaction.response.edit_message(
            content="🧹 Celá tabuľka bola vymazaná.",
            view=None,
        )
        asyncio.create_task(delete_current_message_after(interaction, 3))

    @discord.ui.button(
        label="Upraviť cenu",
        emoji="💰",
        style=discord.ButtonStyle.primary,
    )
    async def edit_price_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.edit_message(
                content="❌ Toto môže používať iba admin.",
                view=None,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        await interaction.response.edit_message(
            content="Vyber, čomu chceš zmeniť cenu:",
            view=PriceCategoryView(self.refresh_main_message),
        )

    @discord.ui.button(
        label="Admin zmazať",
        emoji="🛡️",
        style=discord.ButtonStyle.secondary,
    )
    async def admin_delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.edit_message(
                content="❌ Toto môže používať iba admin.",
                view=None,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        rows = await get_all_equipment_for_admin()

        if not rows:
            await interaction.response.edit_message(
                content="Nie sú tu žiadne položky.",
                view=None,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        await interaction.response.edit_message(
            content="Vyber položku na admin zmazanie:",
            view=AdminDeleteView(rows, self.refresh_main_message),
        )


class AdminDeleteSelect(discord.ui.Select):
    def __init__(self, rows):
        options = []

        for row in rows[:25]:
            item_id, discord_name, item_name, category, weapon_type, color, price, purchased = row

            if category == "weapon":
                label = f"{discord_name}: {item_name} / {weapon_type} / {format_price(price)}"
            else:
                label = f"{discord_name}: {item_name} / {format_price(price)}"

            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=str(item_id),
                )
            )

        super().__init__(
            placeholder="Admin: vyber položku na zmazanie",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        item_id = int(self.values[0])

        ok = await admin_delete_equipment(item_id)

        if not ok:
            await interaction.response.edit_message(
                content="❌ Položka sa nenašla.",
                view=None,
            )
            asyncio.create_task(delete_current_message_after(interaction, 3))
            return

        await self.view.refresh_main_message(interaction.client)

        await interaction.response.edit_message(
            content="🗑️ Admin zmazal položku.",
            view=None,
        )
        asyncio.create_task(delete_current_message_after(interaction, 3))


class AdminDeleteView(discord.ui.View):
    def __init__(self, rows, refresh_func):
        super().__init__(timeout=120)
        self.refresh_main_message = refresh_func
        self.add_item(AdminDeleteSelect(rows))