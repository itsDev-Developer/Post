"""HTML template -> PNG using headless Chromium (Playwright)."""
from __future__ import annotations

import asyncio
import base64
import mimetypes
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.async_api import Browser, Playwright, async_playwright

ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "templates"
FONT_DIR = ROOT.parent / "fonts"

FONT_WEIGHTS = {"regular": 400, "medium": 500, "semibold": 600, "bold": 700, "extrabold": 800, "black": 900}


def _font_css() -> str:
    """Embed every Poppins-*.ttf in /fonts as base64 so renders look identical on any host."""
    css = []
    for f in sorted(FONT_DIR.glob("Poppins-*.ttf")):
        weight = FONT_WEIGHTS.get(f.stem.split("-", 1)[1].lower())
        if not weight:
            continue
        b64 = base64.b64encode(f.read_bytes()).decode()
        css.append(
            f"@font-face{{font-family:'Poppins';font-weight:{weight};"
            f"src:url(data:font/ttf;base64,{b64}) format('truetype');}}"
        )
    return "\n".join(css)


class Renderer:
    def __init__(self, scale: float = 1.5, concurrency: int = 2):
        self.scale = scale
        self.sem = asyncio.Semaphore(concurrency)
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html"])
        )
        self.font_css = _font_css()
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._session = None  # aiohttp session, created lazily
        self._cache: dict[str, str] = {}

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        if self._session:
            await self._session.close()

    # ---- images -> data URIs (avoids hotlink blocks and slow network at render time)
    async def _to_data_uri(self, src: str) -> str:
        if not src or src.startswith("data:"):
            return src
        if src in self._cache:
            return self._cache[src]
        if os.path.exists(src):
            mime = mimetypes.guess_type(src)[0] or "image/jpeg"
            raw = Path(src).read_bytes()
        else:
            try:
                import aiohttp

                if self._session is None:
                    self._session = aiohttp.ClientSession(
                        headers={"User-Agent": "poster-bot/1.0"},
                        timeout=aiohttp.ClientTimeout(total=25),
                    )
                async with self._session.get(src) as r:
                    r.raise_for_status()
                    raw = await r.read()
                    mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
            except Exception:
                return ""  # templates fall back to a gradient when an image is missing
        uri = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
        if len(self._cache) > 40:
            self._cache.pop(next(iter(self._cache)))
        self._cache[src] = uri
        return uri

    async def _inline(self, data: dict) -> dict:
        data = dict(data)
        for key in ("poster", "backdrop", "cutout"):
            data[key] = await self._to_data_uri(data.get(key, ""))
        data["cards"] = list(
            await asyncio.gather(*(self._to_data_uri(u) for u in data.get("cards", [])))
        )
        return data

    async def render(self, template: str, data: dict) -> bytes:
        data = await self._inline(data)
        html = self.env.get_template(f"{template}.html").render(font_css=self.font_css, **data)
        async with self.sem:
            ctx = await self._browser.new_context(
                viewport={"width": 1280, "height": 720}, device_scale_factor=self.scale
            )
            try:
                page = await ctx.new_page()
                await page.set_content(html, wait_until="load", timeout=30000)
                await page.evaluate("document.fonts.ready")
                return await page.screenshot(type="png")
            finally:
                await ctx.close()
