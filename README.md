# Poster Bot

Telegram bot that turns a title (movie, series, anime, manga/manhwa) into a poster/thumbnail using
HTML/CSS templates rendered by headless Chromium.

Templates: **Series Split**, **Anime Card**, **Diamond**, **Polaroid**.

## Run

```bash
pip install -r requirements.txt
playwright install --with-deps chromium
cp .env.example .env        # fill BOT_TOKEN (+ TMDB_API_KEY for movies/TV)
python -m bot.main
```

Try the templates without Telegram or keys:

```bash
python demo.py poster.jpg backdrop.jpg extra1.jpg extra2.jpg   # writes ./out/*.png
```

Docker / Render: use the included `Dockerfile` as a **Background Worker**.
Chromium needs roughly 250–400 MB RAM while rendering; set `RENDER_CONCURRENCY=1` on small plans.

## Bot flow

Send a title → pick result → pick template → pick colour → get a photo + full-quality PNG document.
`/brand Nova Flix` and `/tagline ...` customise the text on posters (stored in `data/settings.json`).

## Data sources

| Source | Used for | Key |
|---|---|---|
| TMDB | movies, TV: posters, backdrops, overview | free key |
| AniList | anime + manga/manhwa: covers, banners, characters | none |

Ideas to add under `bot/providers/`: Fanart.tv (transparent logos/backgrounds), Jikan (MyAnimeList),
MangaDex (covers), Kitsu. A provider only has to return a `Media` object (`bot/models.py`).
TMDB requires attribution and its images can't be sold as a product; posters/art are copyrighted by
their owners, so use this for fan/channel content.

## Add a template

1. Create `bot/templates/mytemplate.html` extending `base.html` (canvas is 1280×720, absolute positioning).
2. Register it in `TEMPLATES` in `bot/context.py`: `"mytemplate": ("Label", "#default-accent")`.

Every template gets the same data: `title t1 t2 year eps_long eps_short genres genre_line synopsis
studio status type_label poster backdrop cards cutout brand brand_a brand_b accent tagline promo`.
The accent colour is the CSS variable `--accent`.

## Notes

- Fonts: Poppins is embedded from `/fonts` (Regular, Medium, Bold). Drop `Poppins-SemiBold.ttf`,
  `Poppins-ExtraBold.ttf` or `Poppins-Black.ttf` in there for heavier titles; they're picked up automatically.
- The Diamond template can show a transparent character PNG popping out of the diamond: pass
  `cutout=` to `build()` (e.g. from Fanart.tv or a background remover such as `rembg`).
- Sessions live in memory, so users restart their flow after a bot restart.
