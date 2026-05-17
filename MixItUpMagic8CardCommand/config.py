"""Configuration for the ask command."""

import os
import sys
import time
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DEBUG_TIMING = os.getenv("DEBUG_TIMING", "").lower() in ("1", "true", "yes")

IMAGE_OUTPUT_DIR = os.getenv("IMAGE_OUTPUT_DIR") or os.path.dirname(__file__)

try:
    KEEP_IMAGES = max(1, int(os.getenv("KEEP_IMAGES", "5")))
except ValueError:
    KEEP_IMAGES = 5

POINTER_FILE = os.path.join(IMAGE_OUTPUT_DIR, "latest_card_path.txt")


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
