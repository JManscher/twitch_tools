"""Scryfall API integration: fetch cards by name and download images for trivia."""

import os
import re
from typing import Dict, Optional

import requests

import cache
import config

_NAMED_URL = "https://api.scryfall.com/cards/named"
_HEADERS = {
    "User-Agent": "MixItUpMTGTriviaGame/1.0",
    "Accept": "application/json",
}

# Scryfall card data is effectively static for cards already printed.
# A 30-day TTL is plenty conservative.
_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60


class ScryfallAPIError(Exception):
    """Raised when the Scryfall request or image download fails."""
    pass


def _slug(name: str) -> str:
    """Filesystem-safe slug for a card name."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "card"


def _image_url(card: dict) -> Optional[str]:
    uris = card.get("image_uris")
    if uris and uris.get("normal"):
        return uris["normal"]
    faces = card.get("card_faces") or []
    if faces:
        face_uris = faces[0].get("image_uris") or {}
        if face_uris.get("normal"):
            return face_uris["normal"]
    return None


def _download_image(url: str, dest_path: str) -> None:
    tmp_path = dest_path + ".tmp"
    try:
        with requests.get(url, headers=_HEADERS, timeout=15, stream=True) as resp:
            resp.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
        os.replace(tmp_path, dest_path)
    except requests.RequestException as e:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise ScryfallAPIError(f"image download failed: {e}")


def fetch_card_by_name(name: str, set_code: Optional[str] = None) -> dict:
    """Look up a card by fuzzy name, optionally pinned to a Scryfall set code.

    Cached for 30 days. The cache key includes the set so different printings
    of the same card don't shadow each other.
    """
    set_lc = (set_code or "").strip().lower() or None
    suffix = f"|{set_lc}" if set_lc else ""
    # v2 prefix: old entries lack rarity/price; bumping the prefix forces a
    # one-time re-fetch on first startup after upgrade.
    key = f"card:v2:{name.lower().strip()}{suffix}"
    cached = cache.get(key, _CACHE_TTL_SECONDS)
    if cached:
        return cached

    params = {"fuzzy": name}
    if set_lc:
        params["set"] = set_lc

    label = f"Scryfall: named '{name}'" + (f" [set={set_lc}]" if set_lc else "")
    try:
        with config.timer(label):
            resp = requests.get(
                _NAMED_URL,
                params=params,
                headers=_HEADERS,
                timeout=10,
            )
        resp.raise_for_status()
        card = resp.json()
    except requests.RequestException as e:
        raise ScryfallAPIError(f"named lookup failed for '{name}'{suffix}: {e}")
    except ValueError as e:
        raise ScryfallAPIError(f"invalid JSON from Scryfall for '{name}'{suffix}: {e}")

    image = _image_url(card)
    prices = card.get("prices") or {}
    minimal = {
        "name": card.get("name") or name,
        "image_url": image,
        "scryfall_uri": card.get("scryfall_uri"),
        "rarity": card.get("rarity"),
        "price_usd": prices.get("usd"),
        "set": (card.get("set") or set_lc),
    }
    cache.set(key, minimal)
    return minimal


def prewarm(refs, image_dir: str) -> Dict[tuple, Optional[dict]]:
    """Resolve every (card_name, set_code) ref, download its image, and capture metadata.

    Each ref is a 2-tuple: (name, set_code_or_None). When set_code is None
    Scryfall picks the printing; when set_code is given the lookup is pinned
    to that set so different printings of the same card map to different
    images and prices.

    Returns a mapping {(name, set_code): card_info or None}. card_info has:
      image:     relative path served by Flask (e.g. 'cards/lightning-bolt-lea.jpg')
      rarity:    'common' | 'uncommon' | 'rare' | 'mythic' | None
      price_usd: string price like '0.25', or None when Scryfall has no price

    Entries are None when Scryfall couldn't resolve the card or the image
    download failed; callers fall through to a text-only render in that case.
    """
    os.makedirs(image_dir, exist_ok=True)
    result: Dict[tuple, Optional[dict]] = {}
    for ref in refs:
        name, set_code = ref
        if not name:
            continue
        if ref in result:
            continue
        try:
            info = fetch_card_by_name(name, set_code=set_code)
        except ScryfallAPIError as e:
            print(f"[scryfall] lookup failed for '{name}' set={set_code!r}: {e}")
            result[ref] = None
            continue

        image_url = info.get("image_url")
        if not image_url:
            print(f"[scryfall] no image available for '{name}' set={set_code!r}")
            result[ref] = None
            continue

        # File slug always includes the actual Scryfall set so different
        # printings get distinct files on disk.
        actual_set = info.get("set") or set_code or "x"
        slug = f"{_slug(info.get('name') or name)}-{_slug(actual_set)}"
        dest = os.path.join(image_dir, f"{slug}.jpg")
        if not os.path.exists(dest):
            try:
                _download_image(image_url, dest)
            except ScryfallAPIError as e:
                print(f"[scryfall] image download failed for '{name}' set={set_code!r}: {e}")
                result[ref] = None
                continue

        # Path served by Flask's static handler — forward slashes for URL use.
        result[ref] = {
            "image": f"cards/{slug}.jpg",
            "rarity": info.get("rarity"),
            "price_usd": info.get("price_usd"),
        }
    return result
