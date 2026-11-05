"""AniList provider (anime + manga/manhwa/manhua). GraphQL, no API key needed."""
from __future__ import annotations

import aiohttp

from ..models import Media, SearchHit

URL = "https://graphql.anilist.co"

SEARCH = """
query ($q: String) {
  Page(perPage: 8) {
    media(search: $q, sort: SEARCH_MATCH, isAdult: false) {
      id type format
      title { romaji english }
      startDate { year }
    }
  }
}"""

DETAIL = """
query ($id: Int) {
  Media(id: $id) {
    id type format status countryOfOrigin
    title { romaji english }
    startDate { year }
    episodes chapters
    description(asHtml: false)
    genres averageScore
    coverImage { extraLarge large }
    bannerImage
    studios(isMain: true) { nodes { name } }
    characters(sort: FAVOURITES_DESC, perPage: 4) { nodes { image { large } } }
  }
}"""

STATUS = {
    "FINISHED": "Completed",
    "RELEASING": "Returning Series",
    "NOT_YET_RELEASED": "Upcoming",
    "CANCELLED": "Cancelled",
    "HIATUS": "On Hiatus",
}
COUNTRY_LABEL = {"KR": "MANHWA", "CN": "MANHUA", "TW": "MANHUA"}
FORMAT_LABEL = {"TV": "TV SERIES", "TV_SHORT": "TV SHORT", "MOVIE": "MOVIE", "OVA": "OVA", "ONA": "ONA", "SPECIAL": "SPECIAL"}


class AniList:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def _q(self, query: str, variables: dict):
        async with self.session.post(
            URL, json={"query": query, "variables": variables}, timeout=aiohttp.ClientTimeout(total=20)
        ) as r:
            r.raise_for_status()
            return (await r.json())["data"]

    async def search(self, query: str) -> list[SearchHit]:
        data = await self._q(SEARCH, {"q": query})
        hits = []
        for m in data["Page"]["media"]:
            t = m["title"]
            hits.append(
                SearchHit(
                    "anilist",
                    m["type"].lower(),  # anime | manga
                    m["id"],
                    t.get("english") or t.get("romaji") or "?",
                    str((m.get("startDate") or {}).get("year") or ""),
                )
            )
        return hits

    async def details(self, id_: int) -> Media:
        m = (await self._q(DETAIL, {"id": id_}))["Media"]
        t = m["title"]
        is_anime = m["type"] == "ANIME"
        if is_anime:
            episodes, unit = str(m.get("episodes") or ""), "Episodes"
            type_label = FORMAT_LABEL.get(m.get("format"), "ANIME")
        else:
            episodes, unit = str(m.get("chapters") or ""), "Chapters"
            type_label = COUNTRY_LABEL.get(m.get("countryOfOrigin"), "MANGA")
        cover = m["coverImage"]["extraLarge"] or m["coverImage"]["large"] or ""
        chars = [c["image"]["large"] for c in m["characters"]["nodes"] if c.get("image")]
        studios = m["studios"]["nodes"]
        status = STATUS.get(m.get("status"), "")
        if not is_anime and m.get("status") == "RELEASING":
            status = "Ongoing"
        return Media(
            source="anilist",
            kind=m["type"].lower(),
            id=id_,
            title=t.get("english") or t.get("romaji") or "?",
            year=str((m.get("startDate") or {}).get("year") or ""),
            episodes=episodes,
            unit=unit,
            genres=m.get("genres") or [],
            synopsis=m.get("description") or "",
            poster=cover,
            backdrop=m.get("bannerImage") or cover,
            extras=chars + [cover],
            studio=studios[0]["name"] if studios else "",
            status=status,
            type_label=type_label,
            score=f"{m['averageScore'] / 10:.1f}" if m.get("averageScore") else "",
        )
