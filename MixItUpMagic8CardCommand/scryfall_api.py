"""Scryfall API integration: draw a random Magic card and download its image."""

import glob
import hashlib
import os
import time
from typing import Tuple

import requests

import config

_IMAGE_PREFIX = "card-"
_IMAGE_EXT = ".jpg"
_IMAGE_GLOB = f"{_IMAGE_PREFIX}*{_IMAGE_EXT}"

_RANDOM_URL = "https://api.scryfall.com/cards/random"
_PARAMS = {"q": "has:image"}
_HEADERS = {
    "User-Agent": "MixItUpMagic8CardCommand/1.0",
    "Accept": "application/json",
}

VERDICTS = [
    "IT IS CERTAIN",
    "IT IS DECIDEDLY SO",
    "WITHOUT A DOUBT",
    "YES DEFINITELY",
    "YOU MAY RELY ON IT",
    "AS I SEE IT, YES",
    "MOST LIKELY",
    "OUTLOOK GOOD",
    "YES",
    "SIGNS POINT TO YES",
    "REPLY HAZY, TRY AGAIN",
    "ASK AGAIN LATER",
    "BETTER NOT TELL YOU NOW",
    "CANNOT PREDICT NOW",
    "CONCENTRATE AND ASK AGAIN",
    "DON'T COUNT ON IT",
    "MY REPLY IS NO",
    "MY SOURCES SAY NO",
    "OUTLOOK NOT SO GOOD",
    "VERY DOUBTFUL",
]


class ScryfallAPIError(Exception):
    """Raised when the Scryfall request or image download fails."""
    pass


def _pick_verdict(card_id: str) -> str:
    h = int(hashlib.sha1(card_id.encode("utf-8")).hexdigest(), 16)
    return VERDICTS[h % len(VERDICTS)]


def _image_url(card: dict) -> str:
    uris = card.get("image_uris")
    if uris and uris.get("normal"):
        return uris["normal"]
    faces = card.get("card_faces") or []
    if faces:
        face_uris = faces[0].get("image_uris") or {}
        if face_uris.get("normal"):
            return face_uris["normal"]
    raise ScryfallAPIError("card has no image")


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


def _prune_old_images(keep: int) -> None:
    """Delete old card-*.jpg files, keeping the `keep` most recently modified."""
    pattern = os.path.join(config.IMAGE_OUTPUT_DIR, _IMAGE_GLOB)
    existing = glob.glob(pattern)
    if len(existing) <= keep:
        return
    existing.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    for stale in existing[keep:]:
        try:
            os.remove(stale)
        except OSError:
            pass


def _write_pointer(path: str) -> None:
    try:
        with open(config.POINTER_FILE, "w", encoding="utf-8") as f:
            f.write(path)
    except OSError:
        pass


def draw_card() -> Tuple[str, str, str]:
    """Fetch a random card, save its image, and pick a verdict.

    Returns:
        (card_name, verdict, image_path_written)
    """
    try:
        with config.timer("Scryfall: random card"):
            response = requests.get(
                _RANDOM_URL, params=_PARAMS, headers=_HEADERS, timeout=10
            )
        response.raise_for_status()
        card = response.json()
    except requests.RequestException as e:
        raise ScryfallAPIError(f"random card request failed: {e}")
    except ValueError as e:
        raise ScryfallAPIError(f"invalid JSON from Scryfall: {e}")

    name = card.get("name") or "Unknown Card"
    card_id = card.get("id") or name
    url = _image_url(card)

    os.makedirs(config.IMAGE_OUTPUT_DIR, exist_ok=True)
    filename = f"{_IMAGE_PREFIX}{int(time.time() * 1000)}{_IMAGE_EXT}"
    dest_path = os.path.join(config.IMAGE_OUTPUT_DIR, filename)

    with config.timer("Scryfall: download image"):
        _download_image(url, dest_path)

    # Prune AFTER writing — keeps the just-written image safe even if KEEP_IMAGES=1.
    _prune_old_images(config.KEEP_IMAGES)
    _write_pointer(dest_path)

    return name, _pick_verdict(card_id), dest_path
