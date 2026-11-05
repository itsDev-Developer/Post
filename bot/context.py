"""Turns a Media object into the flat dict every template receives."""
from __future__ import annotations

import html
import math
import re

from .models import Media

# key -> (label, default accent)
TEMPLATES = {
    "split": ("Series Split", "#7c3aed"),
    "card": ("Anime Card", "#7c3aed"),
    "diamond": ("Diamond", "#d6005c"),
    "polaroid": ("Polaroid", "#06b6d4"),
}

COLORS = {
    "purple": "#7c3aed",
    "pink": "#d6005c",
    "cyan": "#06b6d4",
    "orange": "#e0820d",
    "red": "#e11d48",
    "green": "#16a34a",
    "blue": "#2563eb",
}

DEFAULT_TAGLINE = "THE HOME OF COUNTLESS SERIES ADVENTURES"
DEFAULT_PROMO = (
    "Stay connected for exciting updates, exclusive news, release schedules, "
    "and sneak peeks into upcoming shows........"
)
UNIT_SHORT = {"Episodes": "EPS", "Chapters": "CH", "Min": "MIN"}


def clean_text(text: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", text or "", flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:-– ")
    return cut + "…"


def split_title(title: str) -> tuple[str, str]:
    words = title.split()
    if len(words) < 2:
        return title, ""
    k = math.ceil(len(words) / 2)
    return " ".join(words[:k]), " ".join(words[k:])


def size_for(n: int, steps: list[tuple[int, int]], smallest: int) -> int:
    for limit, size in steps:
        if n <= limit:
            return size
    return smallest


def build(
    media: Media,
    *,
    brand: str = "NovaFlix",
    accent: str | None = None,
    template: str = "split",
    tagline: str | None = None,
    promo: str | None = None,
    cutout: str | None = None,
) -> dict:
    accent = accent or TEMPLATES[template][1]
    title = shorten(media.title, 48)
    t1, t2 = split_title(title)

    # "Nova Flix" -> Nova|Flix, "AniCruise" -> Ani|Cruise, "Zeta" -> |Zeta (all accent)
    words = brand.split()
    if len(words) > 1:
        parts = [" ".join(words[:-1]), words[-1]]
    else:
        parts = re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+|[A-Z]+(?![a-z])", brand)
        parts = [parts[0], "".join(parts[1:])] if len(parts) > 1 else ["", brand]
    brand_a, brand_b = parts

    genres = [g.upper() for g in media.genres][:3]
    poster = media.poster or media.backdrop
    backdrop = media.backdrop or media.poster

    pool = [poster, backdrop, *media.extras]
    pool = [p for p in pool if p]
    cards = [pool[i % len(pool)] for i in (1, 2, 0)] if pool else []
    if len(pool) > 3:
        cards = [pool[2], pool[3], pool[0]]

    unit = UNIT_SHORT.get(media.unit, "")
    eps_long = f"{media.episodes} {media.unit}" if media.episodes else ""
    eps_short = f"{media.episodes}({unit})" if media.episodes else ""

    longest_line = max(len(t1), len(t2))
    return {
        "brand": brand,
        "brand_up": brand.upper(),
        "brand_a": brand_a,
        "brand_b": brand_b,
        "brand_lines": [p.upper() for p in (brand_a, brand_b) if p],
        "accent": accent,
        "tagline": (tagline or DEFAULT_TAGLINE).upper(),
        "promo": promo or DEFAULT_PROMO,
        "title": title,
        "t1": t1,
        "t2": t2,
        "year": media.year,
        "eps_long": eps_long,
        "eps_short": eps_short,
        "genres": genres,
        "genre_line": " • ".join(genres[:2]),
        "synopsis": shorten(clean_text(media.synopsis), 190),
        "synopsis_long": shorten(clean_text(media.synopsis), 260),
        "studio": media.studio,
        "status": media.status or "Returning Series",
        "type_label": media.type_label,
        "score": media.score,
        "poster": poster,
        "backdrop": backdrop,
        "cards": cards,
        "cutout": cutout or "",
        # font sizes tuned per template so long titles never overflow
        "fs_split": size_for(len(title), [(14, 56), (20, 46), (26, 38)], 34),
        "fs_card": size_for(len(title), [(14, 56), (20, 44), (28, 34)], 28),
        "fs_caps": size_for(longest_line, [(12, 58), (15, 48), (19, 38)], 32),
    }
