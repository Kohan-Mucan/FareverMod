"""Lazy index over the archived-fight folder.

The Past Fights panel reads `index.json` (one row per archived file) and never
opens a log just to draw the list. Rows carry a `_LazySessions` for the file's
fights, parsed on first access via the gzip codec in `core.dps_archive`.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path

from ...core.dps_tracker import CombatSession, read_history_file
from ...core import dps_archive
from ...config import dps_dir


class _LazySessions:
    """One history file's archived fights, parsed on FIRST access."""

    __slots__ = ("_path", "_items")

    def __init__(self, path: Path) -> None:
        self._path = path
        self._items: list | None = None

    def _load(self) -> list:
        if self._items is None:
            try:
                self._items = list(read_history_file(self._path) or [])
            except Exception:
                self._items = []
        return self._items

    def __bool__(self) -> bool:
        return bool(self._load())

    def __len__(self) -> int:
        return len(self._load())

    def __iter__(self):
        return iter(self._load())

    def __reversed__(self):
        return reversed(self._load())

    def __getitem__(self, index):
        return self._load()[index]

    def __contains__(self, value) -> bool:
        return value in self._load()

    def index(self, *args):
        return self._load().index(*args)

    def __repr__(self) -> str:
        return f"<_LazySessions {self._path.name}>"


def read_history_file(path: str | Path) -> list[CombatSession]:
    """Parse one archived log through the gzip/plain codec."""
    return list(dps_archive.read_sessions(Path(path)) or [])


def read_history_sessions(path: str | Path) -> list[CombatSession]:
    return read_history_file(path)


def load_history_sessions(path: str | Path) -> list[CombatSession]:
    return read_history_file(path)


_LOADED: "OrderedDict[tuple, list[CombatSession]]" = OrderedDict()
_LOADED_MAX = 8


def cached_history_sessions(path: str | Path, mtime: float | None = None,
                            size: int | None = None) -> list[CombatSession]:
    p = Path(path)
    if mtime is None or size is None:
        try:
            st = p.stat()
            mtime, size = st.st_mtime, st.st_size
        except OSError:
            return []
    key = (str(p), mtime, size)
    hit = _LOADED.get(key)
    if hit is not None:
        _LOADED.move_to_end(key)
        return hit
    sessions = read_history_sessions(p)
    _LOADED[key] = sessions
    while len(_LOADED) > _LOADED_MAX:
        _LOADED.popitem(last=False)
    return sessions


def summary_line(summary: dict | None) -> str:
    if not summary:
        return ""
    count = int(summary.get("fights") or 0)
    if count <= 0:
        return ""
    parts = [f"{count} fight" + ("" if count == 1 else "s")]
    damage = float(summary.get("best_damage") or 0.0)
    if damage > 0.0:
        parts.append(f"best {damage:,.0f} DMG")
    duration = float(summary.get("best_duration") or 0.0)
    if duration > 0.0:
        parts.append(f"{int(duration // 60):02d}:{duration % 60:02.0f}")
    if summary.get("has_failure"):
        parts.append("\u2620")
    return " \u00b7 ".join(parts)


#: How many party names a row's TOOLTIP lists before it summarises the rest.
#: The sidecar itself carries at most `dps_records._MAX_PARTY_NAMES`; the limit
#: here is about a hover a human reads, not about the file.
_PARTY_TIP_NAMES = 10


def party_chip(summary: dict | None) -> tuple[str, str]:
    """``(chip text, tooltip)`` for the party a log recorded, ``("", "")`` if none.

    A COUNT on the row and the names in the tooltip, because the row is one line
    wide and a party is a list: four names in the row would push the damage the
    row exists for off its right edge. The count is the sidecar's `party_size`
    (the true member count, not the length of a capped name list), and a log
    that recorded nobody returns nothing at all rather than `0` - "never
    captured" is not "a party of none".
    """
    if not isinstance(summary, dict):
        return "", ""
    size = int(summary.get("party_size") or 0)
    if size <= 0:
        return "", ""
    roster = [e for e in (summary.get("party") or []) if isinstance(e, dict)
              and str(e.get("name") or "").strip()]
    names = [f"{e['name']}" + (" (you)" if e.get("is_me") else "")
             for e in roster[:_PARTY_TIP_NAMES]]
    if len(roster) > _PARTY_TIP_NAMES:
        names.append(f"+{len(roster) - _PARTY_TIP_NAMES} more")
    if not names:
        # The count survived a sidecar whose names did not (a raid past the cap,
        # or a hand-edited row): say the size, claim no names.
        return (f"\U0001f465 {size}",
                f"Party of {size} recorded in this log.")
    tip = (f"Party of {size}: " + " · ".join(names)
           + "\nRecorded from the game's own group roster, so it counts members "
             "who were present even if they dealt no damage.")
    if size > len(roster):
        tip += f"\n(the sidecar lists {len(roster)}, capped)"
    return f"\U0001f465 {size}", tip


def build_chip(summary: dict | None) -> tuple[str, str]:
    """``(chip text, tooltip)`` for the client a log was archived on.

    The build is a fact about the RUN, stamped when the fight was archived, so
    it is shown as it was - never compared against whatever client is running
    now from here (that comparison belongs to the surface that knows today's
    build, not to the sidecar reader). Empty for a log that recorded none.
    """
    if not isinstance(summary, dict):
        return "", ""
    build = str(summary.get("game_version") or "").strip()
    if not build:
        return "", ""
    builds = [str(v).strip() for v in (summary.get("game_versions") or [])
              if str(v).strip()]
    if len(builds) > 1:
        return build, (f"Client build this log was played on: {build} (its "
                       f"newest fight).\nThis log spans more than one build: "
                       + ", ".join(builds))
    return build, (f"Client build this log was played on: {build}.\nStamped "
                   f"when the fight was archived, so it describes the patch "
                   f"you were on - not the one you are on now.")


def forget_cached_sessions(path: str | Path | None = None) -> None:
    if path is None:
        _LOADED.clear()
        return
    p = Path(path)
    key_prefix = str(p)
    for k in [k for k in _LOADED if k[0] == key_prefix]:
        _LOADED.pop(k, None)


def history_days(directory: str | Path | None = None) -> list[str]:
    if directory is None:
        directory = dps_dir()
    base = Path(directory)
    if (base / "dps").is_dir():
        base = base / "dps"
    rows = dps_archive.read_index(base)
    if rows is None:
        rows = dps_archive.build_index(base)
    from ...core import dps_archive as _da
    present = {str(f) for f in _da._iter_archive_files(base)}
    known = {r.get("path") for r in rows}
    if present != known:
        rows = dps_archive.build_index(base)
        try:
            dps_archive.write_index(base, rows)
        except OSError:
            pass
    days = {r.get("day") for r in rows if r.get("day")}
    return sorted(days, reverse=True)


def scan_history_dir(directory: str | Path | None = None,
                     day: str | None = None,
                     days: set[str] | None = None) -> list[dict]:
    if directory is None:
        directory = dps_dir()
    base = Path(directory)
    if (base / "dps").is_dir():
        base = base / "dps"
    # The persistent index is validated against the actual file LIST every
    # scan: a write path that goes through the tracker already refreshed it,
    # but a direct file edit (test fixture, external tool) is noticeable as
    # soon as a single rglob of archive names disagrees with the rows.
    from ...core import dps_archive as _da
    present = {str(f) for f in _da._iter_archive_files(base)}
    rows = dps_archive.read_index(base)
    known = {r.get("path") for r in (rows or [])}
    if rows is None or present != known:
        rows = dps_archive.build_index(base)
        try:
            dps_archive.write_index(base, rows)
        except OSError:
            pass
    out = []
    for r in rows:
        if day is not None and r.get("day") != day:
            continue
        if days is not None:
            stamp = r.get("day")
            if stamp and stamp not in days:
                continue
        path = Path(r["path"])
        if not path.exists():
            continue
        out.append({**r, "path": path, "sessions": _LazySessions(path)})
    out.sort(key=lambda r: r.get("mtime") or 0.0, reverse=True)
    return out
