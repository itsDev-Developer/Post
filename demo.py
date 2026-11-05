"""Render every template without Telegram or API keys.

    python demo.py [poster.jpg] [backdrop.jpg] [extra.jpg ...]

Outputs go to ./out/. Without image arguments the templates fall back to flat colour fills.
"""
import asyncio
import sys
from pathlib import Path

from bot.context import TEMPLATES, build
from bot.models import Media
from bot.renderer import Renderer


async def main() -> None:
    imgs = sys.argv[1:]
    media = Media(
        source="demo", kind="anime", id=0,
        title="Alya Sometimes Hides Her Feelings in Russian",
        year="2024", episodes="12", unit="Episodes",
        genres=["Comedy", "Romance", "Slice of Life"],
        synopsis=(
            "Alya is a transfer student enjoying popularity at her new high school, often sporting a cold "
            "shoulder while earning high marks in class. She ignores her nerdy classmate, Kuze, but secretly "
            "whispers sweet words in Russian."
        ),
        poster=imgs[0] if imgs else "", backdrop=imgs[1] if len(imgs) > 1 else "",
        extras=imgs[2:], studio="Doga Kobo", status="Returning Series", type_label="TV SERIES",
    )
    out = Path("out")
    out.mkdir(exist_ok=True)
    r = Renderer(scale=1)
    await r.start()
    try:
        for tpl in TEMPLATES:
            png = await r.render(tpl, build(media, brand="AniCruise", template=tpl))
            (out / f"{tpl}.png").write_bytes(png)
            print("wrote", out / f"{tpl}.png")
    finally:
        await r.stop()


asyncio.run(main())
