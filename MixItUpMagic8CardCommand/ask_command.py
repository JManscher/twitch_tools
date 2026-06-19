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
        name, verdict, _ = scryfall_api.draw_card()
        # Stdout is exactly one line so Mix It Up's $externalprogramresult is
        # safe to drop straight into a Chat action. The image path is written
        # to config.POINTER_FILE for the Overlay action to pick up via File Read.
        print(f"The cards say {verdict}: {name}")
    except scryfall_api.ScryfallAPIError as e:
        print(f"The cards are silent ({e}).")
        sys.exit(0)

    if config.DEBUG_TIMING:
        total = (time.perf_counter() - _start_time) * 1000
        print(f"[timing] Total: {total:.1f}ms", file=sys.stderr)


if __name__ == "__main__":
    main()
