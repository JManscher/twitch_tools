"""Scryfall API integration: fetch cards by name and download images for trivia."""

import os
import re
from typing import Dict, Optional

import requests

import cache
import config

_NAMED_URL = "https://api.scryfall.com/cards/named"
_SEARCH_URL = "https://api.scryfall.com/cards/search"
_CARD_URL = "https://api.scryfall.com/cards"  # /cards/<id> for an exact printing
_HEADERS = {
    "User-Agent": "MixItUpMTGTriviaGame/1.0",
    "Accept": "application/json",
}

# Safety cap on printing pages followed (each page is up to 175 cards).
_MAX_PRINT_PAGES = 4

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


def _minimal(card: dict, name_fallback: str = "", set_fallback=None) -> dict:
    prices = card.get("prices") or {}
    return {
        "name": card.get("name") or name_fallback,
        "image_url": _image_url(card),
        "scryfall_uri": card.get("scryfall_uri"),
        "rarity": card.get("rarity"),
        "price_usd": prices.get("usd"),
        "set": (card.get("set") or set_fallback),
        "lang": card.get("lang"),
        "id": card.get("id"),
    }


def fetch_card_by_name(name: str, set_code: Optional[str] = None, print_id: Optional[str] = None) -> dict:
    """Resolve a card's image + metadata.

    When print_id is given, fetch that exact printing via /cards/<id> (this is
    how a specific language/art is pinned — the set code alone can't do it).
    Otherwise look up by fuzzy name, optionally pinned to a set code.
    Cached for 30 days.
    """
    pid = (print_id or "").strip().lower() or None
    if pid:
        key = f"card:v2:id:{pid}"
        cached = cache.get(key, _CACHE_TTL_SECONDS)
        if cached:
            return cached
        try:
            with config.timer(f"Scryfall: card id {pid}"):
                resp = requests.get(f"{_CARD_URL}/{pid}", headers=_HEADERS, timeout=10)
            resp.raise_for_status()
            card = resp.json()
        except requests.RequestException as e:
            raise ScryfallAPIError(f"card id lookup failed for {pid}: {e}")
        except ValueError as e:
            raise ScryfallAPIError(f"invalid JSON from Scryfall for id {pid}: {e}")
        minimal = _minimal(card, name, set_code)
        cache.set(key, minimal)
        return minimal

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

    minimal = _minimal(card, name, set_lc)
    cache.set(key, minimal)
    return minimal


def list_printings(name: str) -> dict:
    """List every printing of a card so the editor can offer a set picker.

    Resolves the canonical name first (fuzzy), then searches all prints.
    Cached for 30 days. Returns:
        { "name": <canonical>, "printings": [ {set, set_name,
          collector_number, rarity, released, image_url, price_usd}, ... ] }
    Raises ScryfallAPIError on failure.
    """
    # Resolve the canonical name so the exact-name search matches.
    canonical = fetch_card_by_name(name).get("name") or name

    key = f"prints:v2:{canonical.lower().strip()}"
    cached = cache.get(key, _CACHE_TTL_SECONDS)
    if cached:
        return cached

    printings = []
    params = {
        "q": f'!"{canonical}"',
        "unique": "prints",
        "order": "released",
        "dir": "asc",
    }
    url = _SEARCH_URL
    pages = 0
    try:
        with config.timer(f"Scryfall: prints '{canonical}'"):
            while url and pages < _MAX_PRINT_PAGES:
                resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
                # A 404 means no prints matched — treat as empty, not an error.
                if resp.status_code == 404:
                    break
                resp.raise_for_status()
                data = resp.json()
                for card in data.get("data") or []:
                    prices = card.get("prices") or {}
                    printings.append({
                        "id": card.get("id"),
                        "lang": card.get("lang"),
                        "set": card.get("set"),
                        "set_name": card.get("set_name"),
                        "collector_number": card.get("collector_number"),
                        "rarity": card.get("rarity"),
                        "released": card.get("released_at"),
                        "image_url": _image_url(card),
                        "price_usd": prices.get("usd"),
                    })
                # Follow pagination via next_page (params already encoded in it).
                url = data.get("next_page") if data.get("has_more") else None
                params = None
                pages += 1
    except requests.RequestException as e:
        raise ScryfallAPIError(f"printings lookup failed for '{name}': {e}")
    except ValueError as e:
        raise ScryfallAPIError(f"invalid JSON from Scryfall for '{name}' printings: {e}")

    result = {"name": canonical, "printings": printings}
    cache.set(key, result)
    return result


def prewarm(refs, image_dir: str) -> Dict[tuple, Optional[dict]]:
    """Resolve every (name, set_code, print_id) ref, download its image, and
    capture metadata.

    print_id pins one exact printing (e.g. a Japanese-language card); otherwise
    set_code pins a set, or Scryfall picks by name.

    Returns a mapping {(name, set_code, print_id): card_info or None}. card_info:
      image:     relative path served by Flask (e.g. 'cards/lightning-bolt-lea.jpg')
      rarity:    'common' | 'uncommon' | 'rare' | 'mythic' | None
      price_usd: string price like '0.25', or None when Scryfall has no price

    Entries are None when Scryfall couldn't resolve the card or the image
    download failed; callers fall through to a text-only render in that case.
    """
    os.makedirs(image_dir, exist_ok=True)
    result: Dict[tuple, Optional[dict]] = {}
    for ref in refs:
        name, set_code, print_id = ref
        if not name:
            continue
        if ref in result:
            continue
        try:
            info = fetch_card_by_name(name, set_code=set_code, print_id=print_id)
        except ScryfallAPIError as e:
            print(f"[scryfall] lookup failed for '{name}' set={set_code!r} id={print_id!r}: {e}")
            result[ref] = None
            continue

        image_url = info.get("image_url")
        if not image_url:
            print(f"[scryfall] no image available for '{name}' set={set_code!r} id={print_id!r}")
            result[ref] = None
            continue

        # A pinned print id is globally unique, so slug by it; otherwise slug by
        # set so different sets of the same card get distinct files.
        if print_id:
            slug = f"{_slug(info.get('name') or name)}-{_slug(print_id[:8])}"
        else:
            actual_set = info.get("set") or set_code or "x"
            slug = f"{_slug(info.get('name') or name)}-{_slug(actual_set)}"
        dest = os.path.join(image_dir, f"{slug}.jpg")
        if not os.path.exists(dest):
            try:
                _download_image(image_url, dest)
            except ScryfallAPIError as e:
                print(f"[scryfall] image download failed for '{name}' set={set_code!r} id={print_id!r}: {e}")
                result[ref] = None
                continue

        # Path served by Flask's static handler — forward slashes for URL use.
        result[ref] = {
            "image": f"cards/{slug}.jpg",
            "rarity": info.get("rarity"),
            "price_usd": info.get("price_usd"),
        }
    return result
