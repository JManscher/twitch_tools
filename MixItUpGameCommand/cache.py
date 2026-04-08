"""Simple file-based JSON cache with per-key TTL."""

import json
import os
import time

_CACHE_FILE = os.path.join(os.path.dirname(__file__), ".cache.json")


def _load() -> dict:
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


def get(key: str, max_age_seconds: int):
    """Return cached value if present and not expired, otherwise None."""
    entry = _load().get(key)
    if entry and time.time() - entry["ts"] < max_age_seconds:
        return entry["value"]
    return None


def set(key: str, value) -> None:
    """Store a value with the current timestamp."""
    data = _load()
    data[key] = {"ts": time.time(), "value": value}
    _save(data)
