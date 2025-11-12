import discord
from discord.ext import commands
import aiohttp
from dotenv import load_dotenv
import os
from typing import Final
from discord import app_commands
from urllib.parse import quote
from loguru import logger

load_dotenv()

API_KEY = os.getenv("API_KEY")
if API_KEY is None:
    raise RuntimeError("Missing API_KEY environment variable")
BASE_URL = "https://api.bypass.vip/premium"
HEADERS: Final[dict[str, str]] = {"x-api-key": API_KEY, "Accept": "application/json"}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    await bot.tree.sync()
    print(f"{bot.user} está online!")
    print(f"Comandos slash sincronizados: {len(bot.tree.get_commands())}")
    logger.info("Bot is online as {}", bot.user)
    logger.info("Slash commands synced: {}", len(bot.tree.get_commands()))


@bot.tree.command(
    name="bypass",
    description="Contorna anúncios em links usando a API premium do Bypass.vip.",
)
@app_commands.describe(url="URL do link para bypass (ex: Linkvertise ou Lootlinks).")
async def bypass_link(interaction: discord.Interaction, url: str) -> None:
    if not url.startswith(("http://", "https://")):
        await interaction.response.send_message(
            "Forneça uma URL válida começando com http:// ou https://.", ephemeral=True
        )
        return

    await interaction.response.defer()

    async with aiohttp.ClientSession() as session:
        encoded = quote(url, safe="")
        logger.info("/bypass requested url={}, encoded={} ", url, encoded)
        async with session.get(
            f"{BASE_URL}/bypass?url={encoded}", headers=HEADERS
        ) as response:
            logger.info("/bypass status={} ", response.status)
            if response.status == 200:
                data = await response.json()
                logger.info("/bypass response json={} ", data)
                bypassed_url = data.get("result") or data.get("bypassed_url")
                if not bypassed_url:
                    await interaction.followup.send(str(data))
                    return
                result_payload = {"status": "success", "result": str(bypassed_url)}
                logger.info("/bypass success {}", result_payload)
                await interaction.followup.send(f"Link bypassado: {bypassed_url}")
            else:
                detail = await response.text()
                logger.error("/bypass error status={} body={}", response.status, detail)
                await interaction.followup.send(
                    f"Erro na requisição: {response.status}. {detail}"
                )


@bot.command(name="bypass")
async def bypass_prefix(ctx: commands.Context, *, url: str | None = None) -> None:
    await ctx.send(
        "Este bot usa comandos slash. Use /bypass url:<link> ou /refresh url:<link>."
    )


@bot.tree.command(
    name="refresh",
    description="Faz refresh no bypass para links que mudam frequentemente (use com moderação).",
)
@app_commands.describe(url="URL do link para refresh bypass (ex: links dinâmicos).")
async def refresh_link(interaction: discord.Interaction, url: str) -> None:
    if not url.startswith(("http://", "https://")):
        await interaction.response.send_message(
            "Forneça uma URL válida começando com http:// ou https://.", ephemeral=True
        )
        return

    await interaction.response.defer()

    async with aiohttp.ClientSession() as session:
        encoded = quote(url, safe="")
        logger.info("/refresh requested url={}, encoded={} ", url, encoded)
        async with session.get(
            f"{BASE_URL}/refresh?url={encoded}", headers=HEADERS
        ) as response:
            logger.info("/refresh status={} ", response.status)
            if response.status == 200:
                data = await response.json()
                logger.info("/refresh response json={} ", data)
                bypassed_url = data.get("result") or data.get("bypassed_url")
                if not bypassed_url:
                    await interaction.followup.send(str(data))
                    return
                result_payload = {"status": "success", "result": str(bypassed_url)}
                logger.info("/refresh success {}", result_payload)
                await interaction.followup.send(
                    f"Link refresh bypassado: {bypassed_url}"
                )
            else:
                detail = await response.text()
                logger.error(
                    "/refresh error status={} body={}", response.status, detail
                )
                await interaction.followup.send(
                    f"Erro na requisição: {response.status}. {detail}"
                )


@bot.command(name="bypass_link")
async def bypass_link_prefix(ctx: commands.Context, *, url: str | None = None) -> None:
    await ctx.send(
        "Comando atualizado para slash. Use /bypass url:<link> ou /refresh url:<link>."
    )


TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN is None:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable")
bot.run(TOKEN)
