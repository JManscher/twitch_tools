"""Configuration for the MTG Trivia Game server."""

import os
import sys
import time
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

_HERE = os.path.dirname(os.path.abspath(__file__))


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


DEBUG_TIMING = os.getenv("DEBUG_TIMING", "").lower() in ("1", "true", "yes")

PORT = _int_env("PORT", 8765, minimum=1)
# Port for the standalone question editor (editor_server.py). Localhost only.
EDITOR_PORT = _int_env("EDITOR_PORT", 8766, minimum=1)
# When true, the editor opens your default browser to itself on startup.
OPEN_BROWSER = os.getenv("OPEN_BROWSER", "true").lower() in ("1", "true", "yes")
ASK_SECONDS = _int_env("ASK_SECONDS", 30, minimum=5)
REVEAL_SECONDS = _int_env("REVEAL_SECONDS", 8, minimum=2)

QUESTIONS_FILE = os.getenv("QUESTIONS_FILE") or os.path.join(_HERE, "questions.json")
STATIC_DIR = os.path.join(_HERE, "static")
CARDS_DIR = os.path.join(STATIC_DIR, "cards")
# Library of named question lists. The active list is mirrored to QUESTIONS_FILE,
# which the trivia server loads. Managed by the editor.
LISTS_DIR = os.getenv("LISTS_DIR") or os.path.join(_HERE, "lists")

# Comma-separated. Defaults to common chat bots. Lowercase.
_BOT_DEFAULT = "nightbot,streamelements,streamlabs,moobot"
BOT_USERNAMES = {
    name.strip().lower()
    for name in (os.getenv("BOT_USERNAMES") or _BOT_DEFAULT).split(",")
    if name.strip()
}

SKIP_SECRET = os.getenv("SKIP_SECRET") or None

# Scoreboard
SHOW_SCOREBOARD = os.getenv("SHOW_SCOREBOARD", "true").lower() in ("1", "true", "yes")
SCOREBOARD_SIZE = _int_env("SCOREBOARD_SIZE", 5, minimum=1)
# The overlay shows one board at a time and rotates between "This Session" and
# "All-Time" this often.
SCOREBOARD_ROTATE_SECONDS = _int_env("SCOREBOARD_ROTATE_SECONDS", 6, minimum=2)

# All-time leaderboard persistence. Accumulates across server restarts.
# Delete this file to wipe the all-time standings.
SCORES_FILE = os.getenv("SCORES_FILE") or os.path.join(_HERE, "scores.json")

# Points awarded for a correct answer, by question difficulty.
POINTS_EASY = _int_env("POINTS_EASY", 1, minimum=0)
POINTS_MEDIUM = _int_env("POINTS_MEDIUM", 2, minimum=0)
POINTS_DIFFICULT = _int_env("POINTS_DIFFICULT", 3, minimum=0)


def points_for_difficulty(difficulty) -> int:
    """Map a question difficulty to its point value. Unknown difficulties
    score the same as Easy."""
    d = (difficulty or "").strip().lower()
    if d == "medium":
        return POINTS_MEDIUM
    if d == "difficult":
        return POINTS_DIFFICULT
    return POINTS_EASY


@contextmanager
def timer(label: str):
    """Print elapsed time to stderr when DEBUG_TIMING is enabled."""
    if not DEBUG_TIMING:
        yield
        return
    start = time.perf_counter()
    yield
    elapsed = (time.perf_counter() - start) * 1000
    print(f"[timing] {label}: {elapsed:.1f}ms", file=sys.stderr)
