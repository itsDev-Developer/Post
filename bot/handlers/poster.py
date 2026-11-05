from __future__ import annotations

import asyncio
import logging
import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .. import store
from ..context import COLORS, TEMPLATES, build
from ..providers.anilist import AniList
from ..providers.tmdb import TMDB
from ..renderer import Renderer

log = logging.getLogger(__name__)
router = Router()

# user_id -> {"media": Media, "tpl": str, "color": str|None}. In-memory, lost on restart.
sessions: dict[int, dict] = {}

HELP = (
    "🎬 Poster & thumbnail maker\n\n"
    "Send a title (or /poster <title>) to search movies, series, anime and manga.\n"
    "Then pick a result → a template → an accent colour.\n\n"
    "/brand <name> – set the brand shown on posters (e.g. /brand Nova Flix)\n"
    "/tagline <text> – set the small header tagline\n"
    "/help – show this message"
)


def _session(uid: int) -> dict:
    if len(sessions) > 500:
        sessions.pop(next(iter(sessions)))
    return sessions.setdefault(uid, {})


# ------------------------------------------------------------------ commands
@router.message(CommandStart())
@router.message(Command("help"))
async def start(m: Message):
    await m.answer(HELP)


@router.message(Command("brand"))
async def brand(m: Message, command: CommandObject):
    name = (command.args or "").strip()[:24]
    if not name:
        await m.answer("Usage: /brand Nova Flix  (tip: CamelCase like AniCruise also splits into two colours)")
        return
    store.put(m.from_user.id, "brand", name)
    await m.answer(f"✅ Brand set to: {name}")


@router.message(Command("tagline"))
async def tagline(m: Message, command: CommandObject):
    text = (command.args or "").strip()[:60]
    if not text:
        await m.answer("Usage: /tagline The home of countless series adventures")
        return
    store.put(m.from_user.id, "tagline", text)
    await m.answer("✅ Tagline saved.")


@router.message(Command("poster"))
async def poster_cmd(m: Message, command: CommandObject, tmdb: TMDB | None, anilist: AniList):
    if not command.args:
        await m.answer("Usage: /poster Stranger Things")
        return
    await search(m, command.args.strip(), tmdb, anilist)


@router.message(F.text & ~F.text.startswith("/") & (F.chat.type == "private"))
async def plain_text(m: Message, tmdb: TMDB | None, anilist: AniList):
    await search(m, m.text.strip(), tmdb, anilist)


# ------------------------------------------------------------------ search
async def search(m: Message, query: str, tmdb: TMDB | None, anilist: AniList):
    wait = await m.answer(f"🔎 Searching “{query}”…")
    jobs = [anilist.search(query)] + ([tmdb.search(query)] if tmdb else [])
    results = await asyncio.gather(*jobs, return_exceptions=True)
    hits = []
    for r in results:
        if isinstance(r, Exception):
            log.warning("search failed: %r", r)
        else:
            hits += r
    if not hits:
        await wait.edit_text("😕 Nothing found. Try another spelling.")
        return

    kb = InlineKeyboardBuilder()
    icons = {"movie": "🎬", "tv": "📺", "anime": "🍥", "manga": "📖"}
    for h in hits[:12]:
        label = f"{icons.get(h.kind, '•')} {h.title[:40]}{f' ({h.year})' if h.year else ''}"
        kb.button(text=label, callback_data=f"p:{h.source}:{h.kind}:{h.id}")
    kb.adjust(1)
    await wait.edit_text("Pick one:", reply_markup=kb.as_markup())


# ------------------------------------------------------------------ pick → template → colour
def template_menu():
    kb = InlineKeyboardBuilder()
    for key, (label, _) in TEMPLATES.items():
        kb.button(text=f"🖼 {label}", callback_data=f"t:{key}")
    kb.adjust(2)
    return kb.as_markup()


def color_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="✨ Template default", callback_data="c:default")
    for name in COLORS:
        kb.button(text=name.title(), callback_data=f"c:{name}")
    kb.adjust(1, 3, 3, 1)
    return kb.as_markup()


@router.callback_query(F.data.startswith("p:"))
async def pick(cb: CallbackQuery, tmdb: TMDB | None, anilist: AniList):
    _, source, kind, id_ = cb.data.split(":")
    await cb.answer("Loading…")
    try:
        media = await (tmdb.details(kind, int(id_)) if source == "tmdb" else anilist.details(int(id_)))
    except Exception:
        log.exception("details failed")
        await cb.message.edit_text("⚠️ Couldn't load that title. Try again.")
        return
    s = _session(cb.from_user.id)
    s.update(media=media, tpl="split", color=None)
    await cb.message.edit_text(f"✅ {media.title}\n\nChoose a template:", reply_markup=template_menu())


@router.callback_query(F.data.startswith("t:"))
async def pick_template(cb: CallbackQuery):
    s = _session(cb.from_user.id)
    if "media" not in s:
        await cb.answer("Search a title first.", show_alert=True)
        return
    s["tpl"] = cb.data.split(":")[1]
    await cb.answer()
    await cb.message.edit_text("Choose an accent colour:", reply_markup=color_menu())


@router.callback_query(F.data.startswith("c:"))
async def pick_color(cb: CallbackQuery, renderer: Renderer):
    s = _session(cb.from_user.id)
    if "media" not in s:
        await cb.answer("Search a title first.", show_alert=True)
        return
    name = cb.data.split(":")[1]
    s["color"] = None if name == "default" else COLORS[name]
    await cb.answer("Rendering…")
    await cb.message.edit_text("🎨 Rendering your poster…")

    uid = cb.from_user.id
    try:
        data = build(
            s["media"],
            brand=store.get(uid, "brand", "Nova Flix"),
            accent=s["color"],
            template=s["tpl"],
            tagline=store.get(uid, "tagline"),
        )
        png = await renderer.render(s["tpl"], data)
    except Exception:
        log.exception("render failed")
        await cb.message.edit_text("⚠️ Rendering failed. Try again or pick another template.")
        return

    fname = re.sub(r"[^a-z0-9]+", "_", s["media"].title.lower()).strip("_")[:40] + f"_{s['tpl']}.png"
    again = InlineKeyboardBuilder()
    again.button(text="🖼 Template", callback_data="m:t")
    again.button(text="🎨 Colour", callback_data="m:c")
    again.adjust(2)

    await cb.message.delete()
    await cb.message.answer_photo(BufferedInputFile(png, fname))
    await cb.message.answer_document(
        BufferedInputFile(png, fname), caption="Full quality file 👆", reply_markup=again.as_markup()
    )


@router.callback_query(F.data.in_({"m:t", "m:c"}))
async def reopen(cb: CallbackQuery):
    if "media" not in _session(cb.from_user.id):
        await cb.answer("Session expired — search again.", show_alert=True)
        return
    await cb.answer()
    if cb.data == "m:t":
        await cb.message.answer("Choose a template:", reply_markup=template_menu())
    else:
        await cb.message.answer("Choose an accent colour:", reply_markup=color_menu())
