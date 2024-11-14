import discord
from discord import app_commands
from discord.ext import commands
import sqlite3

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = bot.conn

    @app_commands.command(name="addadmin", description="Agrega un administrador por ID de Discord. Solo puede ser utilizado por el administrador inicial.")
    async def addadmin(self, interaction: discord.Interaction, member: discord.Member):
        cursor = self.conn.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY)''')
        self.conn.commit()

        cursor.execute("SELECT COUNT(*) FROM admin")
        admin_count = cursor.fetchone()[0]

        if admin_count == 0:
            if interaction.user.id != member.id:
                await interaction.response.send_message(
                    "Este es el primer admin que se agrega. Utilice el comando solo para usted; "
                    "No se permite agregar a otra persona.",
                    ephemeral=True
                )
                return
            cursor.execute("INSERT INTO admin (id) VALUES (?)", (member.id,))
            self.conn.commit()
            await interaction.response.send_message(f"{member.mention} ha sido agregado exitosamente como administrador.", ephemeral=True)
        else:
            cursor.execute("SELECT id FROM admin WHERE id = ?", (interaction.user.id,))
            is_authorized = cursor.fetchone()
            if not is_authorized:
                await interaction.response.send_message("Sólo los admin pueden usar este comando.", ephemeral=True)
                return

            cursor.execute("SELECT id FROM admin WHERE id = ?", (member.id,))
            if cursor.fetchone():
                await interaction.response.send_message(f"{member.mention} Ya está agregada como admin", ephemeral=True)
            else:
                cursor.execute("INSERT INTO admin (id) VALUES (?)", (member.id,))
                self.conn.commit()
                await interaction.response.send_message(f"{member.mention} ha sido agregado exitosamente como admin.", ephemeral=True)

    @app_commands.command(name="listadmins", description="Lista de administradores.")
    async def listadmins(self, interaction: discord.Interaction):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM admin")
        admin_list = cursor.fetchall()

        if admin_list:
            admin_mentions = [f"<@{admin_id[0]}>" for admin_id in admin_list]
            await interaction.response.send_message("Admins:\n" + "\n".join(admin_mentions), ephemeral=True)
        else:
            await interaction.response.send_message("No se ha agregado ningún admin.", ephemeral=True)

    @app_commands.command(name="removeadmin", description="Elimina un administrador por ID de Discord. Sólo el administrador inicial puede usar esto.")
    async def removeadmin(self, interaction: discord.Interaction, member: discord.Member):
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT id FROM admin ORDER BY id LIMIT 1")
        initial_admin = cursor.fetchone()
        
        if initial_admin and initial_admin[0] == interaction.user.id:
            cursor.execute("SELECT id FROM admin WHERE id = ?", (member.id,))
            if cursor.fetchone():
                cursor.execute("DELETE FROM admin WHERE id = ?", (member.id,))
                self.conn.commit()
                await interaction.response.send_message(f"{member.mention} ha sido eliminado exitosamente de la lista de admin.", ephemeral=True)
            else:
                await interaction.response.send_message(f"{member.mention} no está en la lista de administradores.", ephemeral=True)
        else:
            await interaction.response.send_message("Sólo el administrador principal puede usar este comando.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
