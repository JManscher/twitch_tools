"""Load + validate questions.json and provide a shuffled iterator."""

import json
import os
import random
import shutil
from typing import List, Set


ALLOWED_DIFFICULTIES = {"Easy", "Medium", "Difficult"}

# Named regions of a Magic card that can be censored on the overlay.
# Coordinates live in overlay CSS; only the names are validated here.
VALID_HIDE_REGIONS = {
    # Card-image regions: covered with a sage block over the card.
    "name",       # Title bar at the top
    "mana_cost",  # Top-right mana cost
    "art",        # Card artwork
    "type",       # Type line between art and rules text
    "text",       # Rules / flavor text box
    "pt",         # Power/Toughness corner
    "artist",     # Artist credit at the bottom
    "set",        # Set / expansion symbol on the type line (its colour encodes rarity)
    "collector",  # Bottom-left collector line (prints the rarity letter C/U/R/M)
    # Info chips: rendered above the card. Hiding them shows a "?" placeholder
    # during ASK; the real value is revealed during REVEAL.
    "rarity",     # Common / Uncommon / Rare / Mythic
    "price",      # Scryfall USD market price
}


class QuestionsError(Exception):
    """Raised when questions.json is missing, malformed, or schema-invalid."""
    pass


def _check(condition: bool, where: str, msg: str) -> None:
    if not condition:
        raise QuestionsError(f"{where}: {msg}")


def _validate_set_code(value, where: str):
    """Validate an optional Scryfall set code. Lowercased, alnum-only,
    typically 3 characters but Scryfall has 2-, 4-, and 5-char codes too.
    Returns the normalized lowercase string, or None if not present."""
    if value is None:
        return None
    _check(isinstance(value, str), where, "must be a string when present")
    s = value.strip().lower()
    _check(s != "", where, "must not be empty when present")
    _check(
        all(c.isalnum() for c in s) and 1 <= len(s) <= 8,
        where,
        f"must be 1-8 alphanumeric characters (got {value!r}). Examples: 'lea' (Alpha), '2x2' (Double Masters 2022).",
    )
    return s


def _validate_print_id(value, where: str):
    """Validate an optional Scryfall print id (a UUID), used to pin one exact
    printing — including a specific language/art the set code alone can't
    target. Returns the lowercase id, or None if not present."""
    if value is None:
        return None
    _check(isinstance(value, str), where, "must be a string when present")
    s = value.strip().lower()
    if s == "":
        return None
    _check(
        all(c in "0123456789abcdef-" for c in s) and 8 <= len(s) <= 40,
        where,
        f"must be a Scryfall print id (UUID) when present (got {value!r}).",
    )
    return s


def _validate_hide(value, where: str) -> list:
    """Validate an optional 'hide' array of region names. Returns the
    list (possibly empty); raises QuestionsError on invalid input."""
    if value is None:
        return []
    _check(isinstance(value, list), where, "must be a list of region names when present")
    out = []
    for i, region in enumerate(value):
        _check(isinstance(region, str), f"{where}[{i}]", "must be a string")
        _check(
            region in VALID_HIDE_REGIONS,
            f"{where}[{i}]",
            f"unknown region '{region}' (allowed: {sorted(VALID_HIDE_REGIONS)})",
        )
        if region not in out:
            out.append(region)
    return out


def _validate_question(q, index: int) -> dict:
    where = f"questions[{index}]"
    _check(isinstance(q, dict), where, "must be an object")

    qid = q.get("id")
    if qid is None:
        qid = f"q-{index:03d}"
    else:
        _check(isinstance(qid, str) and qid.strip() != "", where + ".id", "must be a non-empty string when present")

    difficulty = q.get("difficulty")
    _check(isinstance(difficulty, str), where + ".difficulty", "must be a string")
    # Unknown difficulties render with a neutral badge — we don't reject here so
    # the streamer can add new difficulty labels without code changes.

    question_text = q.get("question")
    _check(isinstance(question_text, str) and question_text.strip() != "", where + ".question", "must be a non-empty string")

    question_image = q.get("question_image")
    normalized_qimage = None
    if question_image is not None:
        _check(isinstance(question_image, dict), where + ".question_image", "must be null or an object")
        card_ref = question_image.get("card")
        _check(isinstance(card_ref, str) and card_ref.strip() != "", where + ".question_image.card", "must be a non-empty string")
        alt = question_image.get("alt_text")
        if alt is not None:
            _check(isinstance(alt, str), where + ".question_image.alt_text", "must be a string when present")
        set_code = _validate_set_code(question_image.get("set"), where + ".question_image.set")
        print_id = _validate_print_id(question_image.get("print_id"), where + ".question_image.print_id")
        hide_qi = _validate_hide(question_image.get("hide"), where + ".question_image.hide")
        normalized_qimage = {
            "card": card_ref,
            "set": set_code,
            "print_id": print_id,
            "alt_text": alt,
            "hide": hide_qi,
        }

    options = q.get("options")
    _check(isinstance(options, list), where + ".options", "must be a list")
    _check(len(options) == 4, where + ".options", f"must contain exactly 4 entries (got {len(options)})")
    normalized_options = []
    for i, opt in enumerate(options):
        opt_where = f"{where}.options[{i}]"
        _check(isinstance(opt, dict), opt_where, "must be an object")
        text = opt.get("text")
        _check(isinstance(text, str) and text.strip() != "", opt_where + ".text", "must be a non-empty string")
        card = opt.get("card")
        if card is not None:
            _check(isinstance(card, str) and card.strip() != "", opt_where + ".card", "must be null or a non-empty string")
        set_code = _validate_set_code(opt.get("set"), opt_where + ".set")
        print_id = _validate_print_id(opt.get("print_id"), opt_where + ".print_id")
        hide_opt = _validate_hide(opt.get("hide"), opt_where + ".hide")
        normalized_options.append({
            "text": text,
            "card": card,
            "set": set_code,
            "print_id": print_id,
            "hide": hide_opt,
        })

    correct = q.get("correct")
    _check(isinstance(correct, int) and not isinstance(correct, bool), where + ".correct", "must be an integer 0..3")
    _check(0 <= correct <= 3, where + ".correct", f"must be in 0..3 (got {correct})")

    explanation = q.get("explanation")
    if explanation is not None:
        _check(isinstance(explanation, str), where + ".explanation", "must be a string when present")

    return {
        "id": qid,
        "difficulty": difficulty,
        "question": question_text,
        "question_image": normalized_qimage,
        "options": normalized_options,
        "correct": correct,
        "explanation": explanation,
    }


def validate_questions(raw_questions) -> List[dict]:
    """Validate and normalize a list of question dicts.

    Returns the normalized list. Raises QuestionsError with a clear,
    actionable message (including the offending path) on any problem.
    """
    _check(isinstance(raw_questions, list), "questions", "must be a list")
    _check(len(raw_questions) >= 1, "questions", "must contain at least 1 question")

    validated = [_validate_question(q, i) for i, q in enumerate(raw_questions)]

    seen = set()
    for q in validated:
        qid = q["id"]
        if qid in seen:
            raise QuestionsError(f"duplicate question id: {qid!r}")
        seen.add(qid)

    return validated


def load(path: str) -> List[dict]:
    """Read, parse, and validate the questions JSON file.

    Raises QuestionsError with a clear, actionable message on any problem.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        raise QuestionsError(f"questions file not found: {path}")
    except json.JSONDecodeError as e:
        raise QuestionsError(f"questions file is not valid JSON: {path} (line {e.lineno}, col {e.colno}: {e.msg})")

    _check(isinstance(raw, dict), "root", "must be an object with 'version' and 'questions'")
    version = raw.get("version")
    _check(version == 1, "root.version", f"must be 1 (got {version!r})")

    return validate_questions(raw.get("questions"))


def save(path: str, questions) -> List[dict]:
    """Validate `questions`, back up any existing file, and atomically write
    `{ "version": 1, "questions": [...] }`. Returns the normalized list.

    Raises QuestionsError (before touching the file) if validation fails, so
    a bad edit never overwrites a good questions.json.
    """
    validated = validate_questions(questions)

    payload = {"version": 1, "questions": validated}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    # Back up the previous good file before replacing it.
    if os.path.exists(path):
        try:
            shutil.copy2(path, path + ".bak")
        except OSError:
            pass

    os.replace(tmp, path)
    return validated


def extract_card_refs(questions: List[dict]) -> Set[tuple]:
    """Return all unique (card_name, set_code, print_id) tuples referenced
    across all questions. set_code/print_id are None when not pinned."""
    refs: Set[tuple] = set()
    for q in questions:
        qi = q.get("question_image")
        if qi and qi.get("card"):
            refs.add((qi["card"], qi.get("set"), qi.get("print_id")))
        for opt in q["options"]:
            if opt.get("card"):
                refs.add((opt["card"], opt.get("set"), opt.get("print_id")))
    return refs


class ShuffleBag:
    """Iterate questions in shuffled order, reshuffling on exhaustion.

    Guarantees the new first question never matches the previous last
    (provided there are at least 2 questions). With a single question,
    just yields it repeatedly.
    """

    def __init__(self, questions: List[dict]):
        if not questions:
            raise ValueError("ShuffleBag requires at least 1 question")
        self._questions = list(questions)
        self._order: List[dict] = []
        self._last_seen: dict | None = None
        self._reshuffle()

    def _reshuffle(self) -> None:
        if len(self._questions) == 1:
            self._order = [self._questions[0]]
            return
        new_order = self._questions[:]
        random.shuffle(new_order)
        # Avoid adjacent repeat across cycles: if the new first matches the
        # previously yielded question, rotate it out.
        if self._last_seen is not None and new_order[0]["id"] == self._last_seen["id"]:
            new_order.append(new_order.pop(0))
        self._order = new_order

    def next(self) -> dict:
        if not self._order:
            self._reshuffle()
        q = self._order.pop(0)
        self._last_seen = q
        return q
