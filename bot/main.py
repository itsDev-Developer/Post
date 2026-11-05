import asyncio
import logging
import os

import aiohttp
from aiogram import Bot, Dispatcher

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from .handlers import poster
from .providers.anilist import AniList
from .providers.tmdb import TMDB
from .renderer import Renderer


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("Set BOT_TOKEN (see .env.example)")

    tmdb_key = os.getenv("TMDB_API_KEY")
    renderer = Renderer(
        scale=float(os.getenv("RENDER_SCALE", "1.5")),
        concurrency=int(os.getenv("RENDER_CONCURRENCY", "2")),
    )
    await renderer.start()

    async with aiohttp.ClientSession(headers={"User-Agent": "poster-bot/1.0"}) as session:
        tmdb = TMDB(session, tmdb_key) if tmdb_key else None
        if not tmdb:
            logging.warning("TMDB_API_KEY not set: movie/TV search disabled, AniList still works")
        anilist = AniList(session)

        bot = Bot(token)
        dp = Dispatcher()
        dp.include_router(poster.router)
        try:
            await dp.start_polling(bot, tmdb=tmdb, anilist=anilist, renderer=renderer)
        finally:
            await renderer.stop()
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
