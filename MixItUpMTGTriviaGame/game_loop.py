"""Background thread that drives ASK -> REVEAL phase transitions."""

import time
import traceback

import config
from game_state import GameState
from questions import ShuffleBag


def _now_ms() -> float:
    return time.time() * 1000


def _wait_or_skip(state: GameState, seconds: float) -> None:
    """Sleep until either the duration elapses or skip_event is set."""
    state.skip_event.wait(timeout=seconds)


def run(state: GameState, bag: ShuffleBag) -> None:
    """Drive the game loop forever. Per-iteration try/except so the loop
    survives transient errors without dying mid-stream."""
    while True:
        try:
            question = bag.next()
            ends_at = _now_ms() + config.ASK_SECONDS * 1000
            state.start_ask(question, ends_at)

            _wait_or_skip(state, config.ASK_SECONDS)

            reveal_ends_at = _now_ms() + config.REVEAL_SECONDS * 1000
            state.start_reveal(reveal_ends_at)

            _wait_or_skip(state, config.REVEAL_SECONDS)
        except Exception:
            # Never let the loop die. Log and proceed.
            traceback.print_exc()
            # Brief pause so we don't tightloop on a persistent error.
            time.sleep(1.0)
