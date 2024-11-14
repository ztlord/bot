import discord
from discord.ext import commands
from discord import app_commands

class GNCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = bot.conn 
        self.c = self.conn.cursor()

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            self.c.execute("SELECT id FROM admin LIMIT 1")
            result = self.c.fetchone()
            
            if result:
                admin_id = result[0]
                admin_user = await self.bot.fetch_user(admin_id)
                
                if admin_user:
                    embed = discord.Embed(
                        title="Bot Activado",
                        description="El bot esta en linea",
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="L0rdmizteri0",
                        value="zifox Team\n",
                        inline=False
                    )
                    await admin_user.send(embed=embed)
                    print("Mensaje de activación enviado a la usuario administrador.")
                else:
                    print(f"User with Admin ID {admin_id} no hay resutados.")
            else:
                print("No se encontró ningún registro en la tabla de administración.")
        except Exception as e:
            print(f"An error occurred: {e}")

    @app_commands.command(name="channel", description="Conocer el ID de un canal.")
    @app_commands.describe(channel="El canal cuyo ID desea conocer")
    async def channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.send_message(
            f"The ID of the selected channel is: {channel.id}",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(GNCommands(bot))
