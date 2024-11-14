import discord
from discord.ext import commands
import aiohttp
import hashlib
import ssl
import time
import asyncio
class WCommand(commands.Cog):
    def __init__(self, bot, conn):
        self.bot = bot
        self.conn = conn
        self.c = conn.cursor()
        
        self.level_mapping = {
            31: "30-1", 32: "30-2", 33: "30-3", 34: "30-4",
            35: "FC 1", 36: "FC 1 - 1", 37: "FC 1 - 2", 38: "FC 1 - 3", 39: "FC 1 - 4",
            40: "FC 2", 41: "FC 2 - 1", 42: "FC 2 - 2", 43: "FC 2 - 3", 44: "FC 2 - 4",
            45: "FC 3", 46: "FC 3 - 1", 47: "FC 3 - 2", 48: "FC 3 - 3", 49: "FC 3 - 4",
            50: "FC 4", 51: "FC 4 - 1", 52: "FC 4 - 2", 53: "FC 4 - 3", 54: "FC 4 - 4",
            55: "FC 5", 56: "FC 5 - 1", 57: "FC 5 - 2", 58: "FC 5 - 3", 59: "FC 5 - 4",
            60: "FC 6", 61: "FC 6 - 1", 62: "FC 6 - 2", 63: "FC 6 - 3", 64: "FC 6 - 4",
            65: "FC 7", 66: "FC 7 - 1", 67: "FC 7 - 2", 68: "FC 7 - 3", 69: "FC 7 - 4",
            70: "FC 8", 71: "FC 8 - 1", 72: "FC 8 - 2", 73: "FC 8 - 3", 74: "FC 8 - 4",
            75: "FC 9", 76: "FC 9 - 1", 77: "FC 9 - 2", 78: "FC 9 - 3", 79: "FC 9 - 4",
            80: "FC 10", 81: "FC 10 - 1", 82: "FC 10 - 2", 83: "FC 10 - 3", 84: "FC 10 - 4"
        }

    @discord.app_commands.command(name='w', description='Fetches user info using fid.')
    async def w(self, interaction: discord.Interaction, fid: str):
        await self.fetch_user_info(interaction, fid)

    @w.autocomplete('fid')
    async def autocomplete_fid(self, interaction: discord.Interaction, current: str):
        try:
            self.c.execute("SELECT fid, nickname FROM users")
            users = self.c.fetchall()

            choices = [
                discord.app_commands.Choice(name=f"{nickname} ({fid})", value=str(fid)) 
                for fid, nickname in users
            ]

            if current:
                filtered_choices = [choice for choice in choices if current.lower() in choice.name.lower()][:25]
            else:
                filtered_choices = choices[:25]

            return filtered_choices
        
        except Exception as e:
            print(Fore.GREEN + f"Autocomplete could not be loaded: {e}" + Style.RESET_ALL)
            return []


    async def fetch_user_info(self, interaction: discord.Interaction, fid: str):
        try:
            await interaction.response.defer(thinking=True)
            
            current_time = int(time.time() * 1000)
            form = f"fid={fid}&time={current_time}"
            sign = hashlib.md5((form + self.bot.SECRET).encode('utf-8')).hexdigest()
            form = f"sign={sign}&{form}"

            url = 'https://wos-giftcode-api.centurygame.com/api/player'
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            max_retries = 3
            retry_delay = 60

            for attempt in range(max_retries):
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, data=form, ssl=ssl_context) as response:
                        if response.status == 200:
                            data = await response.json()
                            nickname = data['data']['nickname']
                            fid_value = data['data']['fid']
                            stove_level = data['data']['stove_lv']
                            kid = data['data']['kid']
                            avatar_image = data['data']['avatar_image']
                            stove_lv_content = data['data'].get('stove_lv_content')

                            if stove_level > 30:
                                stove_level_name = self.level_mapping.get(stove_level, f"Level {stove_level}")
                            else:
                                stove_level_name = f"Level {stove_level}"

                            self.c.execute("SELECT * FROM users WHERE fid=?", (fid_value,))
                            result = self.c.fetchone()
                            footer_text = "Registrado en la Lista ✅" o "No registrado en la Lista ❌"

                            embed = discord.Embed(title=nickname, color=0x00ff00)
                            embed.add_field(name='ID', value=fid_value, inline=True)
                            embed.add_field(name='Furnace Level', value=stove_level_name, inline=True)
                            embed.add_field(name='State', value=f"{kid}", inline=True)
                            embed.set_image(url=avatar_image)
                            embed.set_footer(text=footer_text)

                            if isinstance(stove_lv_content, str) and stove_lv_content.startswith("http"):
                                embed.set_thumbnail(url=stove_lv_content)

                            await interaction.followup.send(embed=embed)
                            return 

                        elif response.status == 429:
                            if attempt < max_retries - 1:
                                await interaction.followup.send("Se alcanzó el límite de API, su resultado se mostrará automáticamente en breve...")
                                await asyncio.sleep(retry_delay)
            await interaction.followup.send(f"User with ID {fid} no encontrado o se produjo un error después de varios intentos.")
            
        except Exception as e:
            print(f"An error occurred: {e}")
            await interaction.followup.send("Se produjo un error al obtener la información del usuario.")


async def setup(bot):
    await bot.add_cog(WCommand(bot, bot.conn))
