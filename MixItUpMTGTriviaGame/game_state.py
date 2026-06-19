"""Thread-safe shared state for the trivia game."""

import copy
import json
import os
import threading
import time
from enum import Enum
from typing import Dict, List, Optional

import config


class Phase(str, Enum):
    IDLE = "IDLE"
    ASK = "ASK"
    REVEAL = "REVEAL"


class GameState:
    """Holds the live state read by /state and written by the game loop + /vote."""

    def __init__(self, card_info: Optional[Dict[str, Optional[dict]]] = None):
        self._lock = threading.Lock()
        self._phase: Phase = Phase.IDLE
        self._current_question: Optional[dict] = None
        self._votes: Dict[str, int] = {}
        self._phase_ends_at_ms: float = 0.0
        self._round_number: int = 0
        # Snapshot of the tally at the moment of REVEAL — frozen until the next ASK.
        self._frozen_tally: Optional[Dict[int, int]] = None
        # name -> {image, rarity, price_usd} or None when prewarm failed
        self._card_info: Dict[str, Optional[dict]] = dict(card_info or {})
        # Per-session scoreboard (login -> points). Resets each server run.
        self._scores: Dict[str, int] = {}
        # All-time scoreboard (login -> {"name", "points"}). Persisted to disk;
        # survives restarts until the file is deleted or reset.
        self._total_scores: Dict[str, dict] = self._load_total()
        # user (login) -> display name for nicer scoreboard labels.
        self._display_names: Dict[str, str] = {}
        # Points awarded in the most recent REVEAL — drives the "+N" pop.
        self._last_awards: Dict[str, int] = {}
        # Set when /skip is invoked. Game loop wakes on it.
        self.skip_event = threading.Event()

    # --- All-time persistence -------------------------------------------

    def _load_total(self) -> Dict[str, dict]:
        """Load the all-time scoreboard from disk. Missing/corrupt -> empty."""
        try:
            with open(config.SCORES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        scores = data.get("scores") if isinstance(data, dict) else None
        if not isinstance(scores, dict):
            return {}
        out: Dict[str, dict] = {}
        for login, entry in scores.items():
            if isinstance(entry, dict) and isinstance(entry.get("points"), int):
                out[login] = {"name": entry.get("name") or login, "points": entry["points"]}
        return out

    def _save_total(self) -> None:
        """Write the all-time scoreboard atomically. Called under self._lock."""
        try:
            payload = {"version": 1, "scores": self._total_scores}
            tmp = config.SCORES_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            os.replace(tmp, config.SCORES_FILE)
        except OSError as e:
            print(f"[trivia] WARN: could not save all-time scores: {e}")

    def _info_for(self, name, set_code, print_id=None) -> Optional[dict]:
        if not name:
            return None
        return self._card_info.get((name, set_code, print_id))

    def _image_for(self, name, set_code, print_id=None) -> Optional[str]:
        info = self._info_for(name, set_code, print_id)
        return info.get("image") if info else None

    def start_ask(self, question: dict, ends_at_ms: float) -> None:
        with self._lock:
            self._phase = Phase.ASK
            self._current_question = question
            self._votes = {}
            self._frozen_tally = None
            self._phase_ends_at_ms = ends_at_ms
            self._round_number += 1
            self.skip_event.clear()

    def start_reveal(self, ends_at_ms: float) -> None:
        with self._lock:
            q = self._current_question
            num_opts = len(q["options"]) if q else 4
            tally: Dict[int, int] = {i: 0 for i in range(num_opts)}
            for choice in self._votes.values():
                if 0 <= choice < num_opts:
                    tally[choice] += 1
            self._frozen_tally = tally

            # Award points to everyone who voted for the correct answer.
            # Both the session board and the persistent all-time board get it.
            self._last_awards = {}
            awarded_any = False
            if q:
                correct = q.get("correct")
                points = config.points_for_difficulty(q.get("difficulty"))
                if points > 0:
                    for user, choice in self._votes.items():
                        if choice == correct:
                            self._scores[user] = self._scores.get(user, 0) + points
                            self._last_awards[user] = points
                            total = self._total_scores.get(user) or {"name": user, "points": 0}
                            total["points"] += points
                            total["name"] = self._display_names.get(user, total.get("name") or user)
                            self._total_scores[user] = total
                            awarded_any = True
            if awarded_any:
                self._save_total()

            self._phase = Phase.REVEAL
            self._phase_ends_at_ms = ends_at_ms
            self.skip_event.clear()

    def record_vote(self, user: str, choice_index: int, display_name: Optional[str] = None) -> bool:
        """Record a vote. Returns True if accepted, False if dropped.

        First vote per user locks in — later votes from the same user in the
        same round are ignored, so viewers can't change their answer.
        """
        with self._lock:
            if self._phase != Phase.ASK:
                return False
            if not self._current_question:
                return False
            num_opts = len(self._current_question["options"])
            if not (0 <= choice_index < num_opts):
                return False
            if user in self._votes:
                return False
            self._votes[user] = choice_index
            if display_name:
                self._display_names[user] = display_name
            return True

    def reset_scores(self, scope: str = "session") -> None:
        """Clear scoreboards. scope: 'session' (default), 'total', or 'all'."""
        with self._lock:
            if scope in ("session", "all"):
                self._scores = {}
                self._display_names = {}
                self._last_awards = {}
            if scope in ("total", "all"):
                self._total_scores = {}
                self._save_total()

    def _rank_entries(self, pairs, name_of, limit: int) -> List[dict]:
        """Build a ranked board from (login, score) pairs. Standard competition
        ranking (ties share a rank: 1, 2, 2, 4). Called under self._lock."""
        entries = [(u, s) for u, s in pairs if s > 0]
        entries.sort(key=lambda kv: (-kv[1], name_of(kv[0]).lower()))
        out: List[dict] = []
        rank = 0
        prev_score = None
        for i, (user, score) in enumerate(entries[:limit]):
            if score != prev_score:
                rank = i + 1
                prev_score = score
            out.append({
                "rank": rank,
                "name": name_of(user),
                "score": score,
                "awarded": self._last_awards.get(user, 0),
            })
        return out

    def _scoreboard(self, limit: int) -> List[dict]:
        """Per-session top scorers."""
        return self._rank_entries(
            self._scores.items(),
            lambda u: self._display_names.get(u, u),
            limit,
        )

    def _total_scoreboard(self, limit: int) -> List[dict]:
        """All-time top scorers (loaded from disk + this session's awards)."""
        return self._rank_entries(
            ((u, e["points"]) for u, e in self._total_scores.items()),
            lambda u: (self._total_scores.get(u, {}).get("name") or u),
            limit,
        )

    def request_skip(self) -> None:
        self.skip_event.set()

    @property
    def phase(self) -> Phase:
        with self._lock:
            return self._phase

    def snapshot(self) -> dict:
        """Return a JSON-serializable view of the current state."""
        with self._lock:
            q = copy.deepcopy(self._current_question) if self._current_question else None
            tally: Dict[int, int]
            if self._phase == Phase.REVEAL and self._frozen_tally is not None:
                tally = dict(self._frozen_tally)
            else:
                num_opts = len(q["options"]) if q else 4
                tally = {i: 0 for i in range(num_opts)}
                for choice in self._votes.values():
                    if 0 <= choice < num_opts:
                        tally[choice] += 1

            question_image_path = None
            question_image_hide = []
            question_image_rarity = None
            question_image_price = None
            if q and q.get("question_image"):
                qi = q["question_image"]
                info = self._info_for(qi["card"], qi.get("set"), qi.get("print_id")) or {}
                question_image_path = info.get("image")
                question_image_hide = list(qi.get("hide") or [])
                question_image_rarity = info.get("rarity")
                question_image_price = info.get("price_usd")

            options_view = []
            if q:
                for opt in q["options"]:
                    image_path = self._image_for(opt.get("card"), opt.get("set"), opt.get("print_id"))
                    options_view.append({
                        "text": opt["text"],
                        "image": image_path,
                        "hide": list(opt.get("hide") or []),
                    })

            return {
                "phase": self._phase.value,
                "round_number": self._round_number,
                "phase_ends_at_ms": self._phase_ends_at_ms,
                "server_now_ms": time.time() * 1000,
                "question": (
                    {
                        "id": q["id"],
                        "difficulty": q["difficulty"],
                        "text": q["question"],
                        "question_image": question_image_path,
                        "question_image_alt": (
                            q["question_image"].get("alt_text")
                            if q.get("question_image") else None
                        ),
                        "question_image_hide": question_image_hide,
                        "question_image_rarity": question_image_rarity,
                        "question_image_price": question_image_price,
                        "options": options_view,
                        "correct": q["correct"] if self._phase == Phase.REVEAL else None,
                        "explanation": q.get("explanation") if self._phase == Phase.REVEAL else None,
                    }
                    if q else None
                ),
                "tally": {str(k): v for k, v in tally.items()},
                "total_votes": sum(tally.values()),
                "show_scoreboard": config.SHOW_SCOREBOARD,
                "scoreboard_rotate_ms": config.SCOREBOARD_ROTATE_SECONDS * 1000,
                "scoreboard": (
                    self._scoreboard(config.SCOREBOARD_SIZE)
                    if config.SHOW_SCOREBOARD else []
                ),
                "total_scoreboard": (
                    self._total_scoreboard(config.SCOREBOARD_SIZE)
                    if config.SHOW_SCOREBOARD else []
                ),
                "players": sum(1 for s in self._scores.values() if s > 0),
                "total_players": sum(1 for e in self._total_scores.values() if e.get("points", 0) > 0),
            }
