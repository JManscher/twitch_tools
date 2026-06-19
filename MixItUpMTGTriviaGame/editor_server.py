"""Standalone, localhost-only web editor for the question library.

Manages named question lists (lists/<slug>.json). You edit any list; a
separate "activate" publishes a list into questions.json, which the trivia
server loads. Live Scryfall card previews + a set/printing picker included.

Bound to 127.0.0.1 — it writes files, so it stays off the LAN. Switching the
active list (and edits) apply the next time you (re)start the trivia server.
"""

import os
import sys
import threading
import time
import webbrowser

from flask import Flask, jsonify, request, send_from_directory
from waitress import serve

import config
import library
import questions
import scryfall_api


def _log(msg: str) -> None:
    print(msg, flush=True)


def _err(e, code=400):
    return jsonify({"ok": False, "error": str(e)}), code


def _open_browser_when_ready() -> None:
    """Open the editor in the default browser once the server is up."""
    url = f"http://localhost:{config.EDITOR_PORT}/"
    time.sleep(1.0)  # give waitress a moment to bind
    try:
        webbrowser.open(url)
    except Exception:
        pass  # never let browser-launch trouble take down the editor


def create_editor_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=config.STATIC_DIR,
        static_url_path="/static",
    )

    @app.route("/")
    @app.route("/editor")
    def editor():
        return send_from_directory(config.STATIC_DIR, "editor.html")

    @app.route("/api/meta")
    def meta():
        return jsonify({
            "difficulties": sorted(questions.ALLOWED_DIFFICULTIES),
            "hide_regions": sorted(questions.VALID_HIDE_REGIONS),
            "questions_file": config.QUESTIONS_FILE,
        })

    # ---- Question lists (the library) ----
    @app.route("/api/lists", methods=["GET"])
    def lists_index():
        return jsonify(library.list_all())

    @app.route("/api/lists", methods=["POST"])
    def lists_create():
        body = request.get_json(silent=True) or {}
        try:
            meta = library.create_list(body.get("name"), copy_from=body.get("copy_from"))
        except (library.LibraryError, questions.QuestionsError) as e:
            return _err(e)
        _log(f"[editor] created list {meta['slug']!r}")
        return jsonify({"ok": True, **meta})

    @app.route("/api/lists/<slug>", methods=["GET"])
    def lists_get(slug):
        try:
            return jsonify(library.get_list(slug))
        except library.LibraryError as e:
            return _err(e, 404)

    @app.route("/api/lists/<slug>", methods=["PUT"])
    def lists_save(slug):
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get("questions"), list):
            return _err("body must be {\"questions\": [...]}")
        try:
            meta = library.save_list(slug, body["questions"], name=body.get("name"))
        except (library.LibraryError, questions.QuestionsError) as e:
            return _err(e)
        _log(f"[editor] saved list {slug!r} ({meta['count']} questions)")
        return jsonify({"ok": True, **meta})

    @app.route("/api/lists/<slug>/activate", methods=["POST"])
    def lists_activate(slug):
        try:
            res = library.activate(slug)
        except (library.LibraryError, questions.QuestionsError) as e:
            return _err(e)
        _log(f"[editor] activated list {slug!r} -> questions.json")
        return jsonify({"ok": True, **res})

    @app.route("/api/lists/<slug>/rename", methods=["POST"])
    def lists_rename(slug):
        body = request.get_json(silent=True) or {}
        try:
            meta = library.rename_list(slug, body.get("name"))
        except (library.LibraryError, questions.QuestionsError) as e:
            return _err(e)
        return jsonify({"ok": True, **meta})

    @app.route("/api/lists/<slug>", methods=["DELETE"])
    def lists_delete(slug):
        try:
            library.delete_list(slug)
        except library.LibraryError as e:
            return _err(e)
        _log(f"[editor] deleted list {slug!r}")
        return jsonify({"ok": True})

    @app.route("/api/card")
    def card():
        name = (request.args.get("name") or "").strip()
        set_code = (request.args.get("set") or "").strip() or None
        print_id = (request.args.get("print_id") or "").strip() or None
        if not name and not print_id:
            return jsonify({"ok": False, "error": "name is required"}), 400
        try:
            info = scryfall_api.fetch_card_by_name(name, set_code=set_code, print_id=print_id)
        except scryfall_api.ScryfallAPIError as e:
            return jsonify({"ok": False, "error": str(e)})
        return jsonify({"ok": True, **info})

    @app.route("/api/printings")
    def printings():
        name = (request.args.get("name") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "name is required"}), 400
        try:
            result = scryfall_api.list_printings(name)
        except scryfall_api.ScryfallAPIError as e:
            return jsonify({"ok": False, "error": str(e)})
        return jsonify({"ok": True, **result})

    return app


def main() -> int:
    result = library.sync_library()
    _log(f"[editor] library synced: {result}")
    app = create_editor_app()
    _log(f"[editor] questions file: {config.QUESTIONS_FILE}")
    _log(f"[editor] lists dir: {config.LISTS_DIR}")
    _log(f"[editor] open the editor at http://localhost:{config.EDITOR_PORT}/")
    _log("[editor] close this window to stop. Restart the trivia server to apply edits.")
    if config.OPEN_BROWSER:
        threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    # Localhost only — this endpoint writes files.
    serve(app, host="127.0.0.1", port=config.EDITOR_PORT, threads=4, _quiet=False)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
