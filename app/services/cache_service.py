from __future__ import annotations

import json
import os

from app.utils.paths import EXPORTS_DIR

CACHE_DIR = os.path.join(EXPORTS_DIR, "cache")
CACHE_FILES = {
    "reservas": "reservas.json",
    "dashboard": "dashboard.json",
    "calendar": "calendar.json",
}


def _cache_path(name: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    filename = CACHE_FILES.get(name, f"{name}.json")
    return os.path.join(CACHE_DIR, filename)


def save_cache(name: str, data: dict) -> None:
    try:
        with open(_cache_path(name), "w", encoding="utf-8") as cache_file:
            json.dump(data, cache_file, ensure_ascii=True, indent=2)
    except OSError:
        return


def load_cache(name: str) -> dict | None:
    cache_path = _cache_path(name)
    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, "r", encoding="utf-8") as cache_file:
            return json.load(cache_file)
    except (OSError, json.JSONDecodeError):
        return None


def has_any_cache() -> bool:
    for name in CACHE_FILES:
        if os.path.exists(_cache_path(name)):
            return True
    return False
