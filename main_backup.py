import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from database import (
    init_db,
    set_setting,
    get_setting,
    get_all_equipment,
    add_equipment,
    get_user_equipment,
    toggle_purchased,
    delete_equipment,
    get_all_equipment_for_admin,
    admin_delete_equipment,
    delete_all_equipment,
    is_adding_locked,
    set_adding_locked,
)
from config import EMBED_COLOR
from prices import WEAPON_PRICES, SPECIAL_ITEMS

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("Chýba DISCORD_TOKEN v súbore .env")

ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

print("TOKEN:", TOKEN)
print("ADMIN_USER_ID:", ADMIN_USER_ID)


def is_admin(interaction: discord.Interaction) -> bool:
    return str(interaction.user.id) == ADMIN_USER_ID or is_admin(interaction)

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
        (
            item_id,
            user_id,
            discord_name,
            item_name,
            category,
            weapon_type,
            color,
            price,
            purchased,
        ) = row

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
                f"{status} `{item_id}` {color_icon} "
                f"**{weapon_type}** / {color_name} — "
                f"{item_name} — **{format_price(price)}**"
            )
        else:
            line = (
                f"{status} `{item_id}` 🎒 "
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


async def refresh_main_message(bot: commands.Bot):
    channel_id = await get_setting("equipment_channel_id")
    message_id = await get_setting("equipment_message_id")

    if not channel_id or not message_id:
        return

    channel = bot.get_channel(int(channel_id))
    if channel is None:
        return

    message = await channel.fetch_message(int(message_id))
    embed = await build_equipment_embed()
    await message.edit(embed=embed, view=ArsenalView())


class WeaponNameModal(discord.ui.Modal):
    def __init__(self, weapon_type: str, color: str, price: int):
        super().__init__(title="Pridať zbraň")
        self.weapon_type = weapon_type
        self.color = color
        self.price = price

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

        await refresh_main_message(interaction.client)

        await interaction.response.send_message(
            f"✅ Pridané: **{self.weapon_name.value}** za **{format_price(self.price)}**",
            ephemeral=True,
        )


class ColorSelect(discord.ui.Select):
    def __init__(self, weapon_type: str):
        self.weapon_type = weapon_type

        options = []
        for color, price in WEAPON_PRICES[weapon_type].items():
            options.append(
                discord.SelectOption(
                    label=f"{COLOR_NAMES[color]} — {format_price(price)}",
                    value=color,
                    emoji=COLOR_EMOJIS[color],
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
        price = WEAPON_PRICES[self.weapon_type][color]

        await interaction.response.send_modal(
            WeaponNameModal(
                weapon_type=self.weapon_type,
                color=color,
                price=price,
            )
        )


class ColorSelectView(discord.ui.View):
    def __init__(self, weapon_type: str):
        super().__init__(timeout=120)
        self.add_item(ColorSelect(weapon_type))


class WeaponTypeSelect(discord.ui.Select):
    def __init__(self):
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

        await interaction.response.send_message(
            f"Vybral si **{weapon_type}**. Teraz vyber farbu:",
            view=ColorSelectView(weapon_type),
            ephemeral=True,
        )


class WeaponTypeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(WeaponTypeSelect())


class SpecialItemSelect(discord.ui.Select):
    def __init__(self):
        options = []

        emoji_map = {
            "Vesta": "🎽",
            "Helma": "🪖",
            "Granatomet": "💥",
        }

        for item_name, price in SPECIAL_ITEMS.items():
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
        price = SPECIAL_ITEMS[item_name]

        await add_equipment(
            discord_user_id=str(interaction.user.id),
            discord_name=interaction.user.display_name,
            item_name=item_name,
            category="special",
            price=price,
        )

        await refresh_main_message(interaction.client)

        await interaction.response.send_message(
            f"✅ Pridané: **{item_name}** za **{format_price(price)}**",
            ephemeral=True,
        )


class SpecialItemView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(SpecialItemSelect())


class AddCategorySelect(discord.ui.Select):
    def __init__(self):
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
            await interaction.response.send_message(
                "Vyber režim zbrane:",
                view=WeaponTypeView(),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "Vyber výbavu:",
                view=SpecialItemView(),
                ephemeral=True,
            )


class AddCategoryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(AddCategorySelect())

class TogglePurchasedSelect(discord.ui.Select):
    def __init__(self, rows):
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

        await refresh_main_message(interaction.client)

        await interaction.response.send_message(
            "✅ Stav položky bol prepnutý.",
            ephemeral=True,
        )


class TogglePurchasedView(discord.ui.View):
    def __init__(self, rows):
        super().__init__(timeout=120)
        self.add_item(TogglePurchasedSelect(rows))


class DeleteItemSelect(discord.ui.Select):
    def __init__(self, rows):
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

        await refresh_main_message(interaction.client)

        await interaction.response.send_message(
            "🗑️ Položka bola zmazaná.",
            ephemeral=True,
        )


class DeleteItemView(discord.ui.View):
    def __init__(self, rows):
        super().__init__(timeout=120)
        self.add_item(DeleteItemSelect(rows))        

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
        if not is_admin(interaction):
            await interaction.response.send_message(
                "❌ Toto môže používať iba admin.",
                ephemeral=True,
            )
            return

        item_id = int(self.values[0])

        ok = await admin_delete_equipment(item_id)

        if not ok:
            await interaction.response.send_message(
                "❌ Položka sa nenašla.",
                ephemeral=True,
            )
            return

        await refresh_main_message(interaction.client)

        await interaction.response.send_message(
            "🗑️ Admin zmazal položku.",
            ephemeral=True,
        )


class AdminDeleteView(discord.ui.View):
    def __init__(self, rows):
        super().__init__(timeout=120)
        self.add_item(AdminDeleteSelect(rows))
class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    
    @discord.ui.button(
        label="Zamknúť pridávanie",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
    )
    async def lock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message(
                "❌ Toto môže používať iba admin.",
                ephemeral=True,
            )
            return

        await set_adding_locked(True)
        await interaction.response.send_message(
            "🔒 Pridávanie bolo uzamknuté.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Odomknúť pridávanie",
        emoji="🔓",
        style=discord.ButtonStyle.success,
    )
    async def unlock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message(
                "❌ Toto môže používať iba admin.",
                ephemeral=True,
            )
            return

        await set_adding_locked(False)
        await interaction.response.send_message(
            "🔓 Pridávanie bolo odomknuté.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Reset tabuľky",
        emoji="🧹",
        style=discord.ButtonStyle.danger,
    )
    async def reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message(
                "❌ Toto môže používať iba admin.",
                ephemeral=True,
            )
            return

        await delete_all_equipment()
        await refresh_main_message(interaction.client)

        await interaction.response.send_message(
            "🧹 Celá tabuľka bola vymazaná.",
            ephemeral=True,
        )

class ArsenalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Pridať",
        emoji="➕",
        style=discord.ButtonStyle.success,
        custom_id="arsenal_add",
    )
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await is_adding_locked():
            await interaction.response.send_message(
                "🔒 Pridávanie je momentálne uzamknuté administrátorom.",
                ephemeral=True,
            )
            return
    
        await interaction.response.send_message(
            "Vyber, čo chceš pridať:",
            view=AddCategoryView(),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Kúpené",
        emoji="✅",
        style=discord.ButtonStyle.primary,
        custom_id="arsenal_toggle_purchased",
    )
    async def purchased_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        rows = await get_user_equipment(str(interaction.user.id))

        if not rows:
            await interaction.response.send_message(
                "Nemáš zatiaľ žiadne položky.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Vyber položku, ktorej chceš prepnúť stav kúpené/nekúpené:",
            view=TogglePurchasedView(rows),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Zmazať",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="arsenal_delete",
    )
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        rows = await get_user_equipment(str(interaction.user.id))

        if not rows:
            await interaction.response.send_message(
                "Nemáš zatiaľ žiadne položky na zmazanie.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Vyber položku, ktorú chceš zmazať:",
            view=DeleteItemView(rows),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Admin zmazať",
        emoji="🛡️",
        style=discord.ButtonStyle.danger,
        custom_id="arsenal_admin_delete",
    )
    async def admin_delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message(
                "❌ Toto tlačidlo môže používať iba admin.",
                ephemeral=True,
            )
            return

        rows = await get_all_equipment_for_admin()

        if not rows:
            await interaction.response.send_message(
                "Nie sú tu žiadne položky na zmazanie.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Vyber položku, ktorú chceš ako admin zmazať:",
            view=AdminDeleteView(rows),
            ephemeral=True,
        )
    @discord.ui.button(
        label="Admin",
        emoji="⚙️",
        style=discord.ButtonStyle.secondary,
        custom_id="arsenal_admin_panel",
    )
    async def admin_panel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message(
                "❌ Toto tlačidlo môže používať iba admin.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "⚙️ Admin panel:",
            view=AdminPanelView(),
            ephemeral=True,
        )
    @discord.ui.button(
        label="Obnoviť",
        emoji="🔄",
        style=discord.ButtonStyle.secondary,
        custom_id="arsenal_refresh",
    )
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = await build_equipment_embed()
        await interaction.response.edit_message(embed=embed, view=self)

class LarpBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    async def setup_hook(self):
        await init_db()
        self.add_view(ArsenalView())
        await self.tree.sync()
        print("Databáza pripravená.")
        print("Slash príkazy synchronizované.")


bot = LarpBot()


@bot.event
async def on_ready():
    print(f"Bot je online ako {bot.user}")


@bot.tree.command(name="ping", description="Test, či bot funguje")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Bot funguje!", ephemeral=True)

@bot.tree.command(name="moje_id", description="Debug admin")
async def moje_id(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Moje ID: {interaction.user.id}\n"
        f"ADMIN_USER_ID: {ADMIN_USER_ID}\n"
        f"Match: {str(interaction.user.id) == str(ADMIN_USER_ID)}\n"
        f"is_admin: {is_admin(interaction)}",
        ephemeral=True
    )


@bot.tree.command(name="setup", description="Vytvorí hlavnú tabuľku tímového vybavenia")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    embed = await build_equipment_embed()
    view = ArsenalView()

    await interaction.response.send_message(embed=embed, view=view)

    message = await interaction.original_response()
    await set_setting("equipment_channel_id", str(interaction.channel_id))
    await set_setting("equipment_message_id", str(message.id))


bot.run(TOKEN)