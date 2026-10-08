"""Fight-history archive codec: gzipped JSON files + the one index cache.

New clean layout (no migration from the per-day / per-sid​ mode folders):

    dps/
      index.json                      <- one row per archive file; Fights list
      2026-10/
        Nightking Maat Demon.json.gz  <- every session for that boss in the month
        trash.json.gz                 <- boss-less pulls only
        dummy.json.gz                 <- every dummy test

A boss file holds its kills, fails, adds and in-run trash all in one `history`
list — `kind`/`mode`/`outcome` are per-session facts, not filename tokens.

The archive payload is the same `{"history": […]}` JSON the plain-text writer
always wrote, wrapped in gzip and tagged `{"v": 3}`. The reader is
forward-compatible: a plain `.json` file (`v` absent) reads through the same
code path, so no migration or rename pass is ever required — old trees simply
keep reading as plain JSON, while every new write is gzipped.
"""
from __future__ import annotations

import gzip
import json
import os
import time
from pathlib import Path

from ..runtime.persist import atomic_write_json, atomic_write_text
from .dps_data import _session_to_dict, _session_from_dict
from .dps_records import summarize, fight_failed, boss_of

ARCHIVE_SUFFIX = ".json.gz"
LEGACY_SUFFIXES = (".json",)
INDEX_NAME = "index.json"
#: Bumped to 4 when the per-file index row gained the difficulty dimension of
#: `dps_records.summarize`'s per-boss rollups. The index's own version is what
#: forces a rebuild: `refresh_index` reuses a cached row verbatim while a
#: file's `(mtime, size)` are unchanged, so a shape change that only bumped the
#: SUMMARY_VERSION inside a row would never reach the rows already written -
#: bumping THIS one makes `read_index` refuse the whole index and re-describe
#: every file.
#: Bumped to 5 for the same reason: the summary gained the recorded party and
#: the client build (`dps_records._party_and_build`), which only reach a row
#: that is described again.
PAYLOAD_VERSION = 5
_ME_SUFFIXES = (" (you)", " (You)")


def month_dir(base: Path, start_time: float | None = None) -> Path:
    lt = time.localtime(start_time or time.time())
    return base / time.strftime("%Y-%m", lt)


def _iter_archive_files(base: Path):
    for f in sorted(base.rglob("*")):
        if not f.is_file():
            continue
        name = f.name
        if name == INDEX_NAME:
            continue
        if name.endswith(ARCHIVE_SUFFIX) or f.suffix == ".json":
            yield f


def read_sessions(path: Path) -> list:
    """Parse an archived log's sessions (gzip or legacy plain JSON)."""
    try:
        if path.name.endswith(ARCHIVE_SUFFIX):
            raw = gzip.decompress(path.read_bytes()).decode("utf-8")
        else:
            raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError, EOFError):
        return []
    return [_session_from_dict(d) for d in (data.get("history") or [])]


def write_sessions(path: Path, sessions) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"v": PAYLOAD_VERSION,
                          "history": [_session_to_dict(s) for s in sessions]},
                         ensure_ascii=False, separators=(",", ":"))
    tmp = path.with_suffix(path.suffix + ".tmp")
    if path.name.endswith(ARCHIVE_SUFFIX):
        tmp.write_bytes(gzip.compress(payload.encode("utf-8"), compresslevel=9))
    else:
        tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def _me_char(sessions) -> str:
    for s in sessions:
        players = getattr(s, "players", {}) or {}
        vals = players.values() if hasattr(players, "values") else players
        for p in vals:
            if getattr(p, "is_me", False):
                name = (getattr(p, "name", "") or getattr(p, "hero_class", ""))
                if isinstance(name, str):
                    low = name.lower()
                    for suf in _ME_SUFFIXES:
                        if low.endswith(suf.lower()):
                            name = name[: -len(suf)]
                            break
                    return name or "Current Character"
    return "Current Character"


def describe_file(path: Path) -> dict | None:
    """One index row for an archived log. None when the file holds no fights."""
    try:
        st = path.stat()
    except OSError:
        return None
    sessions = read_sessions(path)
    if not sessions:
        return None
    newest = max(sessions, key=lambda s: getattr(s, "start_time", 0.0) or 0.0)
    kind = "boss"
    stem = path.name
    low = stem.lower()
    if low.startswith("dummy"):
        kind = "dummy"
    elif low.startswith("trash") or low.startswith("trash_") or " trash" in low.replace("_", " "):
        kind = "trash"
    elif low.startswith("overall") or low.startswith("dps_history"):
        kind = "overall"
    boss = getattr(newest, "boss_label", "") or getattr(newest, "target_name", "") or ""
    boss = boss.strip() or path.stem.replace(".json", "")
    if kind == "boss":
        name = boss
    else:
        name = {"dummy": "Test dummy", "trash": "Trash pulls",
                "overall": "Overall"}.get(kind, kind.title())
    mode = ""
    for s in sessions:
        if getattr(s, "mode", ""):
            mode = s.mode.lower()
            break
    boss_sessions = [s for s in sessions if getattr(s, "kind", "") in ("boss", "boss_adds")]
    outcome = ""
    if boss_sessions:
        outcome = ("pass" if any(not fight_failed(s) for s in boss_sessions)
                   else "failed")
    summary = summarize(sessions)
    lt = time.localtime(getattr(newest, "start_time", 0.0) or st.st_mtime)
    day = time.strftime("%Y-%m-%d", lt)
    parent = path.parent
    if parent.name.isdigit() and len(parent.name) == 2:
        gp = parent.parent.name
        if len(gp) == 7 and gp[4] == "-":
            day = f"{gp}-{parent.name}"
    elif (len(parent.name) == 10 and parent.name[4] == "-"
          and parent.name[7] == "-" and parent.name[:4].isdigit()):
        day = parent.name
    return {"path": str(path), "char": _me_char(sessions), "kind": kind,
            "name": name, "boss": boss, "mtime": st.st_mtime, "size": st.st_size,
            "day": day, "mode": mode, "dungeon": "", "outcome": outcome,
            "summary": summary}


def purge_boss(base: Path, boss: str) -> dict:
    """Delete every archived boss/boss_adds session belonging to `boss`.

    For polluted history: fights the engine mislabeled as a boss (a champion
    trash mob archived as a 👑 fight before the engagement gate) own a whole
    Records row, and hunting them one by one in Past Fights is the wrong
    shape of work — one row, one purge. Matching is on `boss_of`, the same
    reading the Records board groups by, so exactly the sessions behind that
    row go and nothing else: trash/dummy/overall sessions sharing the file
    stay, and other bosses in the same file stay.

    Files left with no sessions are deleted (empty month folders pruned like
    any other delete); changed files are rewritten and the index refreshed,
    so the row is gone from Records AND Fights together. Returns
    `{"files": n, "sessions": m}`.
    """
    want = (boss or "").strip()
    out = {"files": 0, "sessions": 0}
    if not want:
        return out
    base = Path(base)
    for path in list(_iter_archive_files(base)):
        sessions = read_sessions(path)
        if not sessions:
            continue
        kept = [s for s in sessions
                if not (getattr(s, "kind", "") in ("boss", "boss_adds")
                        and boss_of(s) == want)]
        dropped = len(sessions) - len(kept)
        if not dropped:
            continue
        out["sessions"] += dropped
        try:
            if kept:
                write_sessions(path, kept)
            else:
                path.unlink()
                parent = path.parent
                try:
                    if parent.is_dir() and not any(parent.iterdir()):
                        parent.rmdir()
                except OSError:
                    pass
            out["files"] += 1
        except OSError:
            continue
    refresh_index(base)
    return out


def merge_uncrowned_bosses(base: Path) -> dict:
    """Re-file "boss" sessions the tracker never crowned as trash pulls.

    An uncrowned boss target is the exact signature of the engine's
    mislabeled trash: every real engagement grafts the 👑 onto the target
    (scan and hit path both), while an uncertain claim — a hard/heroic
    champion mob in an instance naming no boss — was deliberately left
    uncrowned. Those packs archived as 👑 fights anyway (one "Boss Defeated"
    row per pack), which is the polluted history this repairs: the sessions
    keep every point of damage and move into the month's `trash.json.gz`, so
    the Fights list shows them as Trash pulls and the Records board drops
    the phantom boss row. Going forward nothing like them is written (the
    engagement gate refuses uncertain claims), so this is one-time cleanup.

    Only kind == "boss" with a NAMED but uncrowned target moves: boss_adds
    sessions never wear the crown, so the crown says nothing about them, and
    an unnameable target ("Unknown Boss") is a missing name, not a wrong
    one. Returns `{"files": n, "sessions": m, "bosses": [...]}`.
    """
    from .dps_records import UNKNOWN_BOSS

    base = Path(base)
    # Pass 1 — decide, touching nothing: origin path -> (keep, move).
    plans: dict[Path, tuple[list, list]] = {}
    for path in list(_iter_archive_files(base)):
        sessions = read_sessions(path)
        if not sessions:
            continue
        keep, move = [], []
        for s in sessions:
            target = (getattr(s, "target_name", "") or "")
            boss = boss_of(s)
            if (getattr(s, "kind", "") == "boss" and boss
                    and boss != UNKNOWN_BOSS
                    and not target.startswith("\U0001f451")):
                move.append(s)
            else:
                keep.append(s)
        if move:
            plans[path] = (keep, move)
    if not plans:
        return {"files": 0, "sessions": 0, "bosses": []}
    # Pass 2 — land the moved sessions in the month's trash file FIRST, so a
    # failed write leaves the origin intact rather than losing the fight.
    landed: dict[Path, list] = {}
    for path, (_keep, move) in plans.items():
        saved = [(s, getattr(s, "boss_label", "")) for s in move]
        for s in move:
            s.kind = "trash"
            s.boss_label = ""
        month = month_dir(base, getattr(move[0], "start_time", None))
        dest = month / "trash.json.gz"
        try:
            old = read_sessions(dest) if dest.exists() else []
            write_sessions(dest, old + move)
        except OSError:
            for s, label in saved:
                s.kind = "boss"
                s.boss_label = label
            continue
        landed[path] = move
    if not landed:
        return {"files": 0, "sessions": 0, "bosses": []}
    # Pass 3 — shrink the origins whose sessions all landed.
    touched = 0
    for path, (keep, _move) in plans.items():
        if path not in landed:
            for s in plans[path][1]:
                s.kind = "boss"
            continue
        touched += 1
        try:
            if keep:
                write_sessions(path, keep)
            else:
                path.unlink()
                parent = path.parent
                try:
                    if parent.is_dir() and not any(parent.iterdir()):
                        parent.rmdir()
                except OSError:
                    pass
        except OSError:
            continue
    refresh_index(base)
    names: set[str] = set()
    for path in landed:
        for s in plans[path][1]:
            label = (getattr(s, "target_name", "") or "").strip()
            if label:
                names.add(label)
    total = sum(len(plans[p][1]) for p in landed)
    return {"files": touched, "sessions": total, "bosses": sorted(names)}


def build_index(base: Path) -> list[dict]:
    rows = []
    for f in _iter_archive_files(base):
        d = describe_file(f)
        if d:
            rows.append(d)
    rows.sort(key=lambda r: r.get("mtime") or 0.0, reverse=True)
    return rows


def index_path(base: Path) -> Path:
    return base / INDEX_NAME


def read_index(base: Path) -> list[dict] | None:
    try:
        data = json.loads(index_path(base).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("v") != PAYLOAD_VERSION:
        return None
    return data.get("files") if isinstance(data.get("files"), list) else None


def write_index(base: Path, rows: list[dict]) -> None:
    base.mkdir(parents=True, exist_ok=True)
    atomic_write_json(index_path(base), {"v": PAYLOAD_VERSION, "files": rows})


def refresh_index(base: Path) -> list[dict]:
    """Rewrite index.json from the archive folder; returns the new rows.

    Validation is per-row `(mtime, size)`: a row whose file moved or shrank is
    rebuilt, and a file with no row yet is described. That keeps the list
    correct after a delete, a write, or an older client's stray edit, without
    re-parsing every session up front.
    """
    old = {r.get("path"): r for r in (read_index(base) or []) if r.get("path")}
    rows: list[dict] = []
    for f in _iter_archive_files(base):
        try:
            st = f.stat()
        except OSError:
            continue
        hit = old.get(str(f))
        if hit and hit.get("mtime") == st.st_mtime and hit.get("size") == st.st_size:
            hit["mtime"], hit["size"] = st.st_mtime, st.st_size
            rows.append(hit)
            continue
        d = describe_file(f)
        if d:
            rows.append(d)
    rows.sort(key=lambda r: r.get("mtime") or 0.0, reverse=True)
    write_index(base, rows)
    return rows
