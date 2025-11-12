import discord
from discord.ext import commands
import aiohttp
from dotenv import load_dotenv
import os
from typing import Final
from discord import app_commands
from urllib.parse import quote
from loguru import logger
import sys

load_dotenv()

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level:<7}</level> | <cyan>{message}</cyan>",
    colorize=True,
)

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
    print(f"{bot.user} is online!")
    print(f"Slash commands synced: {len(bot.tree.get_commands())}")
    logger.info("Bot is online as {}", bot.user)
    logger.info("Slash commands synced: {}", len(bot.tree.get_commands()))


@bot.tree.command(
    name="bypass",
    description="Bypass ads on links using the Bypass.vip premium API.",
)
@app_commands.describe(url="URL to bypass (e.g., Linkvertise or Lootlinks)")
async def bypass_link(interaction: discord.Interaction, url: str) -> None:
    if not url.startswith(("http://", "https://")):
        await interaction.response.send_message(
            "Provide a valid URL starting with http:// or https://.", ephemeral=True
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
            if response.status == 201:
                data = await response.json()
                logger.info("/bypass response json={} ", data)
                bypassed_url = data.get("result") or data.get("bypassed_url")
                if not bypassed_url:
                    await interaction.followup.send(str(data))
                    return
                result_payload = {"status": "success", "result": str(bypassed_url)}
                logger.info("/bypass success {}", result_payload)
                await interaction.followup.send(f"Bypassed link: {bypassed_url}")
            else:
                detail = await response.text()
                logger.error("/bypass error status={} body={}", response.status, detail)
                await interaction.followup.send(
                    f"Request error: {response.status}. {detail}"
                )


@bot.command(name="bypass")
async def bypass_prefix(ctx: commands.Context, *, url: str | None = None) -> None:
    await ctx.send(
        "This bot uses slash commands. Use /bypass url:<link> or /refresh url:<link>."
    )


@bot.tree.command(
    name="refresh",
    description="Refresh bypass for links that change frequently (use sparingly).",
)
@app_commands.describe(url="URL to refresh bypass (e.g., dynamic links)")
async def refresh_link(interaction: discord.Interaction, url: str) -> None:
    if not url.startswith(("http://", "https://")):
        await interaction.response.send_message(
            "Provide a valid URL starting with http:// or https://.", ephemeral=True
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
                    f"Refreshed bypass link: {bypassed_url}"
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
        "Command updated to slash. Use /bypass url:<link> or /refresh url:<link>."
    )


TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN is None:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable")
bot.run(TOKEN)
