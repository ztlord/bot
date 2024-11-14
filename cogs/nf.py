import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

class NF(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def user_autocomplete(self, interaction: discord.Interaction, current: str):
        cursor = self.bot.conn.cursor()
        cursor.execute("SELECT fid, nickname FROM users WHERE nickname LIKE ?", (f"%{current}%",))
        results = cursor.fetchall()
        return [
            app_commands.Choice(name=f"{nickname} (ID: {fid})", value=str(fid))
            for fid, nickname in results[:25]
        ]

    @app_commands.command(name="nickname", description="Muestra todos los cambios de apodo de la usuario.")
    @app_commands.describe(user="Username or ID)
    @app_commands.autocomplete(user=user_autocomplete)
    async def nickname(self, interaction: discord.Interaction, user: str):
        fid = int(user)
        cursor = self.bot.conn.cursor()

        cursor.execute("SELECT nickname FROM users WHERE fid = ?", (fid,))
        result = cursor.fetchone()
        current_nickname = result[0] if result else "Unknown"

        cursor.execute("SELECT old_nickname, new_nickname, change_date FROM nickname_changes WHERE fid = ? ORDER BY change_date ASC", (fid,))
        changes = cursor.fetchall()
        
        if not changes:
            await interaction.response.send_message("No se encontraron registros de cambio de nombre para este usuario.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{current_nickname} Name Changes ({len(changes)})",
            color=discord.Color.blue()
        )
        description = ""
        for old_nickname, new_nickname, change_date in changes:
            description += f"{change_date} - **{old_nickname}** → **{new_nickname}**\n"
        embed.description = description
        embed.set_footer(text=f"Game ID: {fid}")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="furnace", description="Muestra todos los cambios de nivel del horno del usuario.")
    @app_commands.describe(user="Usuario o ID")
    @app_commands.autocomplete(user=user_autocomplete)
    async def furnace(self, interaction: discord.Interaction, user: str):
        fid = int(user)
        cursor = self.bot.conn.cursor()

        cursor.execute("SELECT nickname FROM users WHERE fid = ?", (fid,))
        result = cursor.fetchone()
        current_nickname = result[0] if result else "Unknown"

        cursor.execute("SELECT old_furnace_lv, new_furnace_lv, change_date FROM furnace_changes WHERE fid = ? ORDER BY change_date ASC", (fid,))
        changes = cursor.fetchall()
        
        if not changes:
            await interaction.response.send_message("No se encontró ningún registro de un cambio de nivel de caldera para este usuario.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{current_nickname} Actualizo su nivel de horo",
            color=discord.Color.orange()
        )
        description = ""
        for old_furnace_lv, new_furnace_lv, change_date in changes:
            description += f"{change_date} - **{old_furnace_lv}** → **{new_furnace_lv}**\n"
        embed.description = description
        embed.set_footer(text=f"Game ID: {fid}")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(NF(bot))
