"""Tiny JSON settings store (per-user brand name). Swap for a real DB if you need persistence on
hosts with an ephemeral disk."""
from __future__ import annotations

import json
import os
from pathlib import Path

PATH = Path(os.getenv("DATA_DIR", "data")) / "settings.json"
_data: dict[str, dict] = {}


def _load() -> None:
    global _data
    try:
        _data = json.loads(PATH.read_text())
    except Exception:
        _data = {}


def get(user_id: int, key: str, default=None):
    if not _data:
        _load()
    return _data.get(str(user_id), {}).get(key, default)


def put(user_id: int, key: str, value) -> None:
    if not _data:
        _load()
    _data.setdefault(str(user_id), {})[key] = value
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(_data))
