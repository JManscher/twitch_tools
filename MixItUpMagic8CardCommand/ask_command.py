#!/usr/bin/env python3
"""
Mix It Up Ask Command - Magic 8-Ball powered by a random Scryfall card.

Usage:
    python ask_command.py [question text...]

The question text is accepted but ignored - the verdict comes from the card.
"""

import sys
import time

_start_time = time.perf_counter()

# Ensure the em-dash and any other non-ASCII chars survive whatever code page
# the host (cmd.exe, Mix It Up) is using when it reads stdout.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

try:
    import config
    import scryfall_api
except ImportError:
    print("Error: Missing dependencies. Run: pip install -r requirements.txt")
    sys.exit(1)


def main():
    if config.DEBUG_TIMING:
        elapsed = (time.perf_counter() - _start_time) * 1000
        print(f"[timing] Python startup + imports: {elapsed:.1f}ms", file=sys.stderr)

    # Accept (and discard) any question text so Mix It Up's $arg1text works.
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        if question.startswith("$arg") and question.endswith("text"):
            pass  # Mix It Up sentinel for "no argument"

    try:
        name, verdict, image_path = scryfall_api.draw_card()
        # Line 1: chat message ($externalprogramresult's first line in Mix It Up).
        # Line 2: image path, for the overlay action when reading stdout directly.
        # A pointer file (config.POINTER_FILE) is also written for File Read wiring.
        print(f"The cards say {verdict} — {name}")
        print(image_path)
    except scryfall_api.ScryfallAPIError as e:
        print(f"The cards are silent ({e}).")
        sys.exit(0)

    if config.DEBUG_TIMING:
        total = (time.perf_counter() - _start_time) * 1000
        print(f"[timing] Total: {total:.1f}ms", file=sys.stderr)


if __name__ == "__main__":
    main()
