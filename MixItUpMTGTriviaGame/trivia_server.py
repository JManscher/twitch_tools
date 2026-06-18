"""Flask server + entry point for the MTG Trivia Game."""

import os
import sys
import threading

from flask import Flask, jsonify, request, send_from_directory
from waitress import serve

import config
import game_loop
import questions
import scryfall_api
from game_state import GameState


_CHOICE_TO_INDEX = {"A": 0, "B": 1, "C": 2, "D": 3}


def create_app(state: GameState) -> Flask:
    app = Flask(
        __name__,
        static_folder=config.STATIC_DIR,
        static_url_path="/static",
    )

    @app.route("/")
    @app.route("/overlay")
    def overlay():
        return send_from_directory(config.STATIC_DIR, "overlay.html")

    @app.route("/state")
    def state_endpoint():
        return jsonify(state.snapshot())

    @app.route("/vote")
    def vote():
        user = (request.args.get("user") or "").strip().lower()
        choice_raw = (request.args.get("choice") or "").strip().upper()
        display = (request.args.get("display") or "").strip()
        if not user:
            return ("", 200)
        if user in config.BOT_USERNAMES:
            return ("", 200)
        # Accept either a bare letter or a longer message starting with the letter.
        # Mix It Up's $arg1text passes the first word, so "A" is the normal shape,
        # but be permissive.
        choice_letter = choice_raw[:1] if choice_raw else ""
        if choice_letter not in _CHOICE_TO_INDEX:
            return ("", 200)
        state.record_vote(user, _CHOICE_TO_INDEX[choice_letter], display_name=display or None)
        return ("", 200)

    @app.route("/skip", methods=["POST"])
    def skip():
        if not _admin_ok(request):
            return ("forbidden", 403)
        state.request_skip()
        return ("", 200)

    @app.route("/reset", methods=["POST"])
    def reset():
        if not _admin_ok(request):
            return ("forbidden", 403)
        # scope: "session" (default) clears this run's board; "total" clears the
        # all-time board; "all" clears both.
        scope = (request.args.get("scope") or "session").strip().lower()
        if scope not in ("session", "total", "all"):
            scope = "session"
        state.reset_scores(scope)
        return ("", 200)

    return app


def _admin_ok(request) -> bool:
    """Gate /skip and /reset behind SKIP_SECRET when one is configured."""
    if not config.SKIP_SECRET:
        return True
    return request.headers.get("X-Skip-Secret", "") == config.SKIP_SECRET


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    _log(f"[trivia] loading questions from {config.QUESTIONS_FILE}")
    try:
        qs = questions.load(config.QUESTIONS_FILE)
    except questions.QuestionsError as e:
        print(f"[trivia] ERROR: {e}", file=sys.stderr, flush=True)
        return 1

    _log(f"[trivia] loaded {len(qs)} questions")

    card_refs = questions.extract_card_refs(qs)
    _log(f"[trivia] prewarming {len(card_refs)} Scryfall card images...")
    card_info = scryfall_api.prewarm(card_refs, config.CARDS_DIR)
    available = sum(1 for v in card_info.values() if v)
    _log(f"[trivia] prewarmed {available}/{len(card_refs)} card images")

    state = GameState(card_info=card_info)
    bag = questions.ShuffleBag(qs)

    loop_thread = threading.Thread(
        target=game_loop.run,
        args=(state, bag),
        name="trivia-game-loop",
        daemon=True,
    )
    loop_thread.start()

    app = create_app(state)

    _log(f"[trivia] serving overlay at http://localhost:{config.PORT}/overlay")
    _log(f"[trivia] vote endpoint: http://localhost:{config.PORT}/vote?user=<name>&choice=A")
    _log(f"[trivia] close this window or Ctrl+C to stop")

    # waitress: production-quality WSGI server, pure Python, ships on Windows.
    # Quieter than Flask's dev server and no scary warning banner.
    serve(app, host="0.0.0.0", port=config.PORT, threads=8, _quiet=False)
    return 0


if __name__ == "__main__":
    # Ensure cwd-independent imports work when launched via .bat from elsewhere.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
