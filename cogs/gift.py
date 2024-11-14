import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import hashlib
import json

wos_player_info_url = "https://wos-giftcode-api.centurygame.com/api/player"
wos_giftcode_url = "https://wos-giftcode-api.centurygame.com/api/gift_code"
wos_giftcode_redemption_url = "https://wos-giftcode.centurygame.com"
wos_encrypt_key = "tB87#kPtkxqOS2"

retry_config = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429],
    allowed_methods=["POST"]
)

class GiftCommand(commands.Cog):
    def __init__(self, bot, conn):
        self.bot = bot
        self.conn = conn
        self.c = conn.cursor()
        self.giftcode_check_loop.start()

    def encode_data(self, data):
        secret = wos_encrypt_key
        sorted_keys = sorted(data.keys())
        encoded_data = "&".join(
            [
                f"{key}={json.dumps(data[key]) if isinstance(data[key], dict) else data[key]}"
                for key in sorted_keys
            ]
        )
        sign = hashlib.md5(f"{encoded_data}{secret}".encode()).hexdigest()
        return {"sign": sign, **data}

    def get_stove_info_wos(self, player_id):
        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=retry_config))

        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/x-www-form-urlencoded",
            "origin": wos_giftcode_redemption_url,
        }

        data_to_encode = {
            "fid": f"{player_id}",
            "time": f"{int(datetime.now().timestamp())}",
        }
        data = self.encode_data(data_to_encode)

        response_stove_info = session.post(
            wos_player_info_url,
            headers=headers,
            data=data,
        )
        return session, response_stove_info

    def claim_giftcode_rewards_wos(self, player_id, giftcode):
        session, response_stove_info = self.get_stove_info_wos(player_id=player_id)
        if response_stove_info.json().get("msg") == "success":
            data_to_encode = {
                "fid": f"{player_id}",
                "cdk": giftcode,
                "time": f"{int(datetime.now().timestamp())}",
            }
            data = self.encode_data(data_to_encode)

            response_giftcode = session.post(
                wos_giftcode_url,
                data=data,
            )
            
            response_json = response_giftcode.json()
            print(f"Response for {player_id}: {response_json}")
            
            if response_json.get("msg") == "SUCCESS":
                return session, "SUCCESS"
            elif response_json.get("msg") == "RECEIVED." and response_json.get("err_code") == 40008:
                return session, "ALREADY_RECEIVED"
            elif response_json.get("msg") == "CDK NOT FOUND." and response_json.get("err_code") == 40014:
                return session, "CDK_NOT_FOUND"
            elif response_json.get("msg") == "SAME TYPE EXCHANGE." and response_json.get("err_code") == 40011:
                return session, "ALREADY_RECEIVED"
            else:
                return session, "ERROR"

    async def giftcode_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice]:
        self.c.execute("SELECT giftcode, date FROM gift_codes ORDER BY date DESC LIMIT 1")
        latest_code = self.c.fetchone()

        self.c.execute("SELECT giftcode, date FROM gift_codes")
        gift_codes = self.c.fetchall()

        return [
            app_commands.Choice(
                name=f"{code} - {date} {'(Most recently shared)' if (code, date) == latest_code else ''}",
                value=code
            )
            for code, date in gift_codes if current.lower() in code.lower()
        ][:25]

    @app_commands.command(name="gift", description="Usar el gift code para todos los usuarios de la alianza.")
    @app_commands.describe(giftcode="Elige un gift code")
    @app_commands.autocomplete(giftcode=giftcode_autocomplete)
    async def use_giftcode(self, interaction: discord.Interaction, giftcode: str):
        self.c.execute("SELECT 1 FROM admin WHERE id = ?", (interaction.user.id,))
        if not self.c.fetchone():
            await interaction.response.send_message("No tienes autorizacion para utilizar este comando.", ephemeral=True)
            return

        await interaction.response.defer()

        notify_message = await interaction.followup.send(
            content="Se está verificando la lista de alianzas para verificar el uso del código de regalo, el proceso se completará en aproximadamente 10 minutos."
        )
        await interaction.followup.send(content="https://tenor.com/view/typing-gif-3043127330471612038")

        self.c.execute("SELECT * FROM users")
        users = self.c.fetchall()
        success_results = []
        received_results = []
        error_count = 0

        for user in users:
            fid, nickname, _ = user

            self.c.execute(
                "SELECT status FROM user_giftcodes WHERE fid = ? AND giftcode = ?", 
                (fid, giftcode)
            )
            status = self.c.fetchone()
            
            if status:
                if status[0] in ["SUCCESS", "ALREADY_RECEIVED"]:
                    print(f"[INFO] User {fid} ({nickname}) ya ha usado el código {giftcode}. Skipping.")
                    received_results.append(f"{fid} - {nickname} - ALREADY RECEIVED")
                    continue
                else:
                    print(f"[DEBUG] User {fid} has a different status for code {giftcode}: {status[0]}")

            try:
                _, response_status = self.claim_giftcode_rewards_wos(player_id=fid, giftcode=giftcode)
                
                if response_status == "SUCCESS":
                    success_results.append(f"{fid} - {nickname} - USED")
                    print(f"[SUCCESS] User {fid} ({nickname})  se utilizó con éxito el código {giftcode}.")
                    self.c.execute(
                        """
                        INSERT INTO user_giftcodes (fid, giftcode, status) 
                        VALUES (?, ?, ?) 
                        ON CONFLICT(fid, giftcode) 
                        DO UPDATE SET status = excluded.status
                        """,
                        (fid, giftcode, "SUCCESS")
                    )
                elif response_status == "ALREADY_RECEIVED":
                    received_results.append(f"{fid} - {nickname} - ALREADY RECEIVED")
                    print(f"[INFO] User {fid} ({nickname}) ya habia recibido el codigo {giftcode}.")
                    self.c.execute(
                        """
                        INSERT INTO user_giftcodes (fid, giftcode, status) 
                        VALUES (?, ?, ?) 
                        ON CONFLICT(fid, giftcode) 
                        DO UPDATE SET status = excluded.status
                        """,
                        (fid, giftcode, "ALREADY_RECEIVED")
                    )
                elif response_status == "ERROR":
                    print(f"[ERROR] Ocurrió un error para el usuario {fid} ({nickname}) al usar código {giftcode}.")
                    error_count += 1
                elif response_status == "CDK_NOT_FOUND":
                    print(f"[ERROR] Gift code {giftcode} No encontrado para el usuario {fid} ({nickname}). Stopping process.")
                    await notify_message.delete()
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Gift code invalido",
                            description="El gift code utilizado es incorrecto. Por favor revisalo.",
                            color=discord.Color.red()
                        )
                    )
                    return

            except Exception as e:
                print(f"[EXCEPTION] Error al procesar usuario {fid} ({nickname}): {str(e)}")
                error_count += 1

        self.conn.commit()
        await notify_message.delete()

        if not success_results:
            embed = discord.Embed(
                title="Gift Code Usage",
                description=f"El código de regalo ya ha sido utilizado por todos.",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="Resumen de informacion", 
                value=f"{len(received_results)} users have already used it.\n{error_count} users encountered an error.", 
                inline=False
            )
            await interaction.followup.send(embed=embed)
            return

        await self.send_embeds(interaction, giftcode, success_results, "Success", discord.Color.green(), "El código de regalo se ha utilizado correctamente para estos usuarios.")
        
        if received_results or error_count > 0:
            summary_embed = discord.Embed(
                title="Resumen de informacion",
                color=discord.Color.orange()
            )
            summary_embed.add_field(name="Already Used", value=f"{len(received_results)} usuarios ya lo han usado..", inline=False)
            summary_embed.add_field(name="Error", value=f"{error_count} users encountered an error.", inline=False)
            await interaction.followup.send(embed=summary_embed)

    async def use_giftcode_auto(self, giftcode: str):
        self.c.execute("SELECT * FROM users")
        users = self.c.fetchall()

        for user in users:
            fid = user[0]
            self.c.execute("SELECT 1 FROM used_codes WHERE fid = ? AND gift_code = ?", (fid, giftcode))
            if not self.c.fetchone():
                _, response_status = self.claim_giftcode_rewards_wos(player_id=fid, giftcode=giftcode)
                if response_status == "SUCCESS":
                    self.c.execute("INSERT INTO used_codes (fid, gift_code) VALUES (?, ?)", (fid, giftcode))
                self.conn.commit()

    async def send_embeds(self, interaction, giftcode, results, title_suffix, color, footer_text):
        if not results:
            return

        total_users = len(results)
        embed = discord.Embed(
            title=f"{giftcode} Gift Code - {title_suffix} ({total_users})",
            color=color,
            description="\n".join(results)
        )
        embed.set_footer(text=f"zifox team")
        await interaction.followup.send(embed=embed)

    @tasks.loop(minutes=60)
    async def giftcode_check_loop(self):
        print("Buscando nuevos códigos de regalo..")
        try:
            response = requests.get("https://raw.githubusercontent.com/Reloisback/test/main/gift_codes.txt")
            response.raise_for_status()
            gift_codes = response.text.splitlines()

            self.c.execute("SELECT id FROM admin")
            admin_ids = self.c.fetchall()

            github_gift_codes = set()

            for line in gift_codes:
                try:
                    code, date_str = line.split()
                    day, month, year = date_str.split('.')
                    formatted_date = f"{year}-{month}-{day}"
                    github_gift_codes.add(code)

                    self.c.execute("SELECT 1 FROM gift_codes WHERE giftcode = ?", (code,))
                    if not self.c.fetchone():
                        self.c.execute(
                            "INSERT INTO gift_codes (giftcode, date) VALUES (?, ?)",
                            (code, formatted_date)
                        )
                        self.conn.commit()
                        print(f"Nuevo gift code encontrado y agregado: {code}")

                        for admin_id in admin_ids:
                            try:
                                admin_user = await self.bot.fetch_user(admin_id[0])
                                await admin_user.send(
                                    embed=discord.Embed(
                                        title="¡Se encontró un nuevo gift code!",
                                        description=(
                                            f"Un Nuevo gift code **{code}** ha sido encontrado.\n"
                                            f"Date: {formatted_date}\n"
                                            f"Para utilizar el código, simplemente escriba `/gift {code}` en el canal del servidor de Discord donde está el bot.\n"
                                            f"Dependiendo del número de miembros, la entrega de los obsequios puede tardar entre 1 y 10 minutos."
                                        ),
                                        color=discord.Color.blue()
                                    )
                                )
                            except Exception as e:
                                print(f"Error al enviar DM al admin {admin_id[0]}: {str(e)}")
                except ValueError:
                    print(f"La línea no tiene el formato correcto o falta: {line}")

            self.c.execute("SELECT giftcode FROM gift_codes")
            db_gift_codes = {row[0] for row in self.c.fetchall()}

            codes_to_delete = db_gift_codes - github_gift_codes

            for code in codes_to_delete:
                self.c.execute("DELETE FROM gift_codes WHERE giftcode = ?", (code,))
                print(f"Código eliminado de la base de datos.: {code}")

            self.conn.commit()

        except requests.RequestException as e:
            print(f"Error al descargar códigos de regalo: {e}")

    def cog_unload(self):
        self.giftcode_check_loop.cancel()

async def setup(bot):
    await bot.add_cog(GiftCommand(bot, bot.conn))
