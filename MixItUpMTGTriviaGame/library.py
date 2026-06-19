"""Named question lists ("the library").

Each list is a master file `lists/<slug>.json`:
    { "version": 1, "name": <display name>, "updated_at": <epoch>, "questions": [...] }

Exactly one list is *active*; its content is mirrored to questions.json (which
the trivia server loads). The active pointer lives in `lists/_index.json`.

Model: you edit any list's master freely; that never touches questions.json.
A separate "activate"/publish copies a list's master into questions.json.

On startup, sync_library() reconciles the active list with questions.json:
copy questions.json -> active master, UNLESS the master already exists and is
newer (so direct edits to questions.json are imported, but edits made in the
editor are never clobbered, and we never auto-publish).
"""

import json
import os
import re
import time
from typing import List, Optional

import config
import questions

# A master's updated_at must beat questions.json's mtime by this margin before
# we treat questions.json as "edited outside the editor" and re-import it.
_SYNC_EPSILON = 1.0
_INDEX_NAME = "_index"


class LibraryError(Exception):
    """Raised on bad list operations (duplicate name, missing list, etc.)."""
    pass


# ---------- paths ----------
def _index_path() -> str:
    return os.path.join(config.LISTS_DIR, _INDEX_NAME + ".json")


def _master_path(slug: str) -> str:
    return os.path.join(config.LISTS_DIR, slug + ".json")


def _ensure_dir() -> None:
    os.makedirs(config.LISTS_DIR, exist_ok=True)


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s or "list"


def _now() -> float:
    return time.time()


# ---------- low-level read/write ----------
def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json_atomic(path: str, payload: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _read_master(slug: str) -> dict:
    try:
        data = _read_json(_master_path(slug))
    except FileNotFoundError:
        raise LibraryError(f"list not found: {slug}")
    except json.JSONDecodeError as e:
        raise LibraryError(f"list '{slug}' is corrupt JSON: {e}")
    if not isinstance(data, dict):
        raise LibraryError(f"list '{slug}' is malformed")
    return data


def _write_master(slug: str, name: str, qs: list, updated_at: float) -> dict:
    """Validate questions, then write the master file. Returns its metadata."""
    validated = questions.validate_questions(qs)
    payload = {
        "version": 1,
        "name": name,
        "updated_at": updated_at,
        "questions": validated,
    }
    _write_json_atomic(_master_path(slug), payload)
    return {"slug": slug, "name": name, "updated_at": updated_at, "count": len(validated)}


# ---------- index (active pointer only; list set derived from files) ----------
def _read_active() -> Optional[str]:
    try:
        idx = _read_json(_index_path())
        return idx.get("active") if isinstance(idx, dict) else None
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_active(slug: Optional[str]) -> None:
    _write_json_atomic(_index_path(), {"active": slug})


def _all_slugs() -> List[str]:
    if not os.path.isdir(config.LISTS_DIR):
        return []
    out = []
    for fn in os.listdir(config.LISTS_DIR):
        if not fn.endswith(".json"):
            continue
        slug = fn[:-5]
        if slug == _INDEX_NAME:
            continue
        out.append(slug)
    return out


def _name_in_use(name: str, exclude_slug: Optional[str] = None) -> bool:
    target = (name or "").strip().lower()
    for slug in _all_slugs():
        if slug == exclude_slug:
            continue
        try:
            if (_read_master(slug).get("name") or "").strip().lower() == target:
                return True
        except LibraryError:
            continue
    return False


# ---------- public API ----------
def list_all() -> dict:
    """Return { active, active_unpublished, lists: [ {slug,name,updated_at,count,is_active} ] }.

    active_unpublished is True when the active list's master has been edited
    more recently than questions.json — i.e. the live stream is behind, and a
    re-publish would push the changes.
    """
    active = _read_active()
    lists = []
    active_updated = 0
    for slug in _all_slugs():
        try:
            m = _read_master(slug)
        except LibraryError:
            continue
        qs = m.get("questions") or []
        updated = m.get("updated_at") or 0
        if slug == active:
            active_updated = updated
        lists.append({
            "slug": slug,
            "name": m.get("name") or slug,
            "updated_at": updated,
            "count": len(qs) if isinstance(qs, list) else 0,
            "is_active": slug == active,
        })
    lists.sort(key=lambda x: x["name"].lower())

    active_unpublished = False
    if active:
        try:
            qmtime = os.path.getmtime(config.QUESTIONS_FILE)
            active_unpublished = active_updated > qmtime + _SYNC_EPSILON
        except OSError:
            active_unpublished = True
    return {"active": active, "active_unpublished": active_unpublished, "lists": lists}


def get_list(slug: str) -> dict:
    m = _read_master(slug)
    qs = m.get("questions") or []
    return {
        "slug": slug,
        "name": m.get("name") or slug,
        "updated_at": m.get("updated_at") or 0,
        "count": len(qs),
        "is_active": slug == _read_active(),
        "questions": qs,
    }


def save_list(slug: str, qs: list, name: Optional[str] = None) -> dict:
    """Save edits to a list's master (validates first). Bumps updated_at."""
    existing = _read_master(slug)
    final_name = (name or existing.get("name") or slug).strip()
    if not final_name:
        raise LibraryError("list name cannot be empty")
    if name is not None and _name_in_use(final_name, exclude_slug=slug):
        raise LibraryError(f"a list named {final_name!r} already exists")
    return _write_master(slug, final_name, qs, _now())


def create_list(name: str, copy_from: Optional[str] = None) -> dict:
    _ensure_dir()
    name = (name or "").strip()
    if not name:
        raise LibraryError("list name is required")
    if _name_in_use(name):
        raise LibraryError(f"a list named {name!r} already exists")

    if copy_from:
        qs = _read_master(copy_from).get("questions") or []
    else:
        # A fresh list needs at least one question to be valid; seed a starter.
        qs = [{
            "id": "q-001",
            "difficulty": "Easy",
            "question": "New question — edit me!",
            "question_image": None,
            "options": [
                {"text": "Answer A", "card": None, "set": None, "hide": []},
                {"text": "Answer B", "card": None, "set": None, "hide": []},
                {"text": "Answer C", "card": None, "set": None, "hide": []},
                {"text": "Answer D", "card": None, "set": None, "hide": []},
            ],
            "correct": 0,
            "explanation": None,
        }]

    base = _slugify(name)
    slug = base
    i = 2
    while os.path.exists(_master_path(slug)) or slug == _INDEX_NAME:
        slug = f"{base}-{i}"
        i += 1
    return _write_master(slug, name, qs, _now())


def rename_list(slug: str, name: str) -> dict:
    m = _read_master(slug)
    name = (name or "").strip()
    if not name:
        raise LibraryError("list name is required")
    if _name_in_use(name, exclude_slug=slug):
        raise LibraryError(f"a list named {name!r} already exists")
    return _write_master(slug, name, m.get("questions") or [], m.get("updated_at") or _now())


def delete_list(slug: str) -> None:
    if slug == _read_active():
        raise LibraryError("cannot delete the active list — activate another list first")
    path = _master_path(slug)
    if not os.path.exists(path):
        raise LibraryError(f"list not found: {slug}")
    if len(_all_slugs()) <= 1:
        raise LibraryError("cannot delete the only list")
    os.remove(path)


def activate(slug: str) -> dict:
    """Publish a list: copy its master into questions.json and mark it active.
    Aligns the master's updated_at to questions.json so the next load-sync
    treats them as in sync (no spurious re-import)."""
    m = _read_master(slug)
    qs = questions.validate_questions(m.get("questions") or [])
    questions.save(config.QUESTIONS_FILE, qs)  # writes {version,questions} + .bak
    try:
        synced = os.path.getmtime(config.QUESTIONS_FILE)
    except OSError:
        synced = _now()
    _write_master(slug, m.get("name") or slug, qs, synced)
    _write_active(slug)
    return {"active": slug, "count": len(qs)}


# ---------- startup reconciliation ----------
def sync_library() -> dict:
    """Bootstrap the library and reconcile the active list with questions.json.

    - First run (no masters): import questions.json as a "default" list.
    - Otherwise: if questions.json is newer than the active master, import it
      into that master; if the master is newer (edited in the editor, not yet
      published), leave both alone. Never auto-publishes.
    """
    _ensure_dir()
    slugs = _all_slugs()

    # Bootstrap from questions.json on first run.
    if not slugs:
        try:
            qs = questions.load(config.QUESTIONS_FILE)
        except questions.QuestionsError:
            qs = None
        try:
            qmtime = os.path.getmtime(config.QUESTIONS_FILE)
        except OSError:
            qmtime = _now()
        if qs:
            _write_master("default", "default", qs, qmtime)
            _write_active("default")
            return {"bootstrapped": "default", "active": "default"}
        # No usable questions.json — start empty; editor can create a list.
        _write_active(None)
        return {"bootstrapped": None, "active": None}

    active = _read_active()
    if active is None or not os.path.exists(_master_path(active)):
        # Lost/absent active pointer: adopt the first list, leave files as-is.
        active = sorted(slugs)[0]
        _write_active(active)

    master = _read_master(active)
    mu = master.get("updated_at") or 0
    try:
        qmtime = os.path.getmtime(config.QUESTIONS_FILE)
    except OSError:
        qmtime = None

    if qmtime is None:
        # questions.json missing — republish the active master so trivia has it.
        try:
            qs = questions.validate_questions(master.get("questions") or [])
            questions.save(config.QUESTIONS_FILE, qs)
        except questions.QuestionsError:
            pass
        return {"active": active, "action": "republished"}

    if qmtime > mu + _SYNC_EPSILON:
        # questions.json edited outside the editor -> import into active master.
        try:
            qs = questions.load(config.QUESTIONS_FILE)
            _write_master(active, master.get("name") or active, qs, qmtime)
            return {"active": active, "action": "imported questions.json"}
        except questions.QuestionsError:
            return {"active": active, "action": "import skipped (questions.json invalid)"}

    return {"active": active, "action": "in sync"}
