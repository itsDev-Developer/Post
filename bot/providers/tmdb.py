"""TMDB provider (movies + TV).

Get a free key at https://www.themoviedb.org/settings/api
Both the v3 "API Key" and the v4 "Read Access Token" work.
Images must be used with TMDB attribution; do not resell them.
"""
from __future__ import annotations

import aiohttp

from ..models import Media, SearchHit

BASE = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/"


class TMDB:
    def __init__(self, session: aiohttp.ClientSession, key: str):
        self.session = session
        self.key = key

    async def _get(self, path: str, **params):
        headers = {}
        if self.key.startswith("eyJ"):  # v4 bearer token
            headers["Authorization"] = f"Bearer {self.key}"
        else:
            params["api_key"] = self.key
        async with self.session.get(
            BASE + path, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=20)
        ) as r:
            r.raise_for_status()
            return await r.json()

    async def search(self, query: str) -> list[SearchHit]:
        data = await self._get("/search/multi", query=query, include_adult="false")
        hits = []
        for r in data.get("results", []):
            kind = r.get("media_type")
            if kind not in ("movie", "tv"):
                continue
            date = r.get("release_date") or r.get("first_air_date") or ""
            hits.append(
                SearchHit("tmdb", kind, r["id"], r.get("title") or r.get("name") or "?", date[:4])
            )
        return hits[:8]

    async def details(self, kind: str, id_: int) -> Media:
        d = await self._get(
            f"/{kind}/{id_}",
            append_to_response="images",
            include_image_language="en,null",
        )
        date = d.get("release_date") or d.get("first_air_date") or ""
        images = d.get("images", {})

        def pick(items, size, textless_first=True):
            items = sorted(
                items or [],
                key=lambda i: (i.get("iso_639_1") is not None, -(i.get("vote_average") or 0)),
            ) if textless_first else (items or [])
            return [IMG + size + i["file_path"] for i in items if i.get("file_path")]

        backdrops = pick(images.get("backdrops"), "w1280")
        posters = pick(images.get("posters"), "w780", textless_first=False)
        backdrop = backdrops[0] if backdrops else (IMG + "w1280" + d["backdrop_path"] if d.get("backdrop_path") else "")
        poster = IMG + "w780" + d["poster_path"] if d.get("poster_path") else (posters[0] if posters else "")

        if kind == "tv":
            episodes, unit = str(d.get("number_of_episodes") or ""), "Episodes"
            company = (d.get("networks") or d.get("production_companies") or [{}])[0].get("name", "")
            type_label = "TV SERIES"
        else:
            episodes, unit = str(d.get("runtime") or ""), "Min"
            company = (d.get("production_companies") or [{}])[0].get("name", "")
            type_label = "MOVIE"

        return Media(
            source="tmdb",
            kind=kind,
            id=id_,
            title=d.get("title") or d.get("name") or "?",
            year=date[:4],
            episodes=episodes,
            unit=unit,
            genres=[g["name"] for g in d.get("genres", [])],
            synopsis=d.get("overview", ""),
            poster=poster,
            backdrop=backdrop,
            extras=backdrops[1:4] + posters[:2],
            studio=company,
            status=(d.get("status") or "").title(),
            type_label=type_label,
            score=f"{d['vote_average']:.1f}" if d.get("vote_average") else "",
        )
