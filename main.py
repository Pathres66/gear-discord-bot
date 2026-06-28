import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from utils import COLOR_EMOJIS, COLOR_NAMES, format_price
from views_admin import AdminPanelView
from views_add import AddCategoryView
from views_manage import TogglePurchasedView, DeleteItemView
from render import build_equipment_embed, refresh_main_message

from database import (
    get_available_weapon_prices,
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
    seed_default_prices,
)
from config import EMBED_COLOR
from prices import WEAPON_PRICES, SPECIAL_ITEMS

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("Chýba DISCORD_TOKEN v súbore .env")

ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")



def is_admin(interaction: discord.Interaction) -> bool:
    return (
        str(interaction.user.id) == str(ADMIN_USER_ID)
        or interaction.user.guild_permissions.administrator
    )

async def refresh_with_arsenal_view(bot):
    await refresh_main_message(bot, lambda: ArsenalView())

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
            view=AddCategoryView(refresh_with_arsenal_view),
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
            view=TogglePurchasedView(rows, refresh_with_arsenal_view),
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
            view=DeleteItemView(rows, refresh_with_arsenal_view),
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
            view=AdminPanelView(is_admin, refresh_with_arsenal_view),
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
        await seed_default_prices()
        self.add_view(ArsenalView())
        await self.tree.sync()
        print("Databáza pripravená.")
        print("Slash príkazy synchronizované.")


bot = LarpBot()


@bot.event
async def on_ready():
    print(f"Bot je online ako {bot.user}")
    await refresh_with_arsenal_view(bot)

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