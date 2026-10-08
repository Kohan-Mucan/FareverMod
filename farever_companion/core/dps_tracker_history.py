"""Fight-history persistence for the shared DPS tracker.

New, clean archive layout — see ``dps_archive``:

    <dir>/<YYYY-MM>/<Boss>.json.gz   every session for that boss that month
    <dir>/<YYYY-MM>/trash.json.gz    boss-less pulls only
    <dir>/<YYYY-MM>/dummy.json.gz    every dummy test
    <dir>/index.json                 the one cache the Fights page reads

No day folders, no per-file ``.summary`` sidecars, no dummy CSV sheet and no
difficulty/outcome/slug filename tokens — every one of those facts is a
per-session property on the payload and a column in ``index.json``.
"""
from __future__ import annotations

import copy
import re
import time
from collections import deque
from pathlib import Path

from .dps_data import (
    KNOWN_HERO_CLASSES, CombatSession, PlayerParse, SkillParse,
    _slug_profile,
)
from . import dps_archive, game_state
from .proc import game_build_version

HISTORY_KIND_STEMS = {
    "boss": "boss", "boss_adds": "boss", "trash": "trash",
    "dummy": "dummy", "overall": "overall",
}
HISTORY_KIND_TOKENS = frozenset(HISTORY_KIND_STEMS.values())
MONTH_DIR_RE = re.compile(r"^\d{4}-\d{2}$")


def history_kind_stem(kind: str | None) -> str:
    return HISTORY_KIND_STEMS.get((kind or "overall").lower(), "overall")


def boss_file_label(boss_name: str) -> str:
    s = (boss_name or "").replace("\U0001f451", "").replace("\U0001f3af", "")
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s or "Unknown Boss"


def _rmdir_if_empty(path: Path) -> None:
    try:
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    except OSError:
        pass


def prune_history_older_than(directory: str | Path, days: float,
                             now: float | None = None) -> dict:
    out = {"folders": 0, "files": 0, "cutoff": ""}
    try:
        days = float(days)
    except (TypeError, ValueError):
        return out
    if days <= 0:
        return out
    base = Path(directory)
    cutoff = (now if now is not None else time.time()) - days * 86400.0
    out["cutoff"] = time.strftime("%Y-%m-%d", time.localtime(cutoff))
    try:
        months = sorted(base.iterdir())
    except OSError:
        return out
    for month in months:
        if not month.is_dir() or not MONTH_DIR_RE.match(month.name):
            continue
        try:
            stamp = time.mktime((int(month.name[:4]), int(month.name[5:7]),
                                 1, 0, 0, 0, 0, 1, -1))
        except (ValueError, OverflowError):
            continue
        if stamp >= cutoff:
            continue
        try:
            files = 0
            for f in month.iterdir():
                if f.is_file():
                    f.unlink()
                    files += 1
            month.rmdir()
        except OSError:
            continue
        out["folders"] += 1
        out["files"] += files
    return out


def remove_log_file(path: str | Path) -> bool:
    p = Path(path)
    gone = True
    try:
        p.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        gone = False
    if gone:
        d = p.parent
        # `<base>/<YYYY-MM>/…` — prune the month folder when the last file leaves.
        if MONTH_DIR_RE.match(d.name):
            _rmdir_if_empty(d)
    return gone


def _absorb_boss_adds(boss: CombatSession, adds: CombatSession) -> None:
    for name, add_parse in adds.players.items():
        dest = boss.players.get(name)
        if dest is None:
            boss.players[name] = copy.deepcopy(add_parse)
        else:
            _absorb_player_parse(dest, add_parse)
    _absorb_seconds(boss.timeline, adds.timeline)
    for player, buckets in getattr(adds, "player_timeline", {}).items():
        _absorb_seconds(boss.player_timeline.setdefault(player, {}), buckets)
    boss.deaths.extend(adds.deaths)
    merged = list(boss.hits) + list(adds.hits)
    merged.sort(key=lambda h: h.timestamp)
    boss.hits = deque(merged, maxlen=boss.hits.maxlen or 60)
    if adds.burst_peak > boss.burst_peak:
        boss.burst_peak = adds.burst_peak
        boss.burst_peak_time = adds.burst_peak_time
    boss.last_event_time = max(boss.last_event_time, adds.last_event_time)
    if boss.end_time and adds.end_time:
        boss.end_time = max(boss.end_time, adds.end_time)


def _absorb_player_parse(dest: PlayerParse, src: PlayerParse) -> None:
    dest.total_damage += src.total_damage
    dest.damage_taken += src.damage_taken
    dest.heals += src.heals
    dest.self_heals += src.self_heals
    dest.group_heals += src.group_heals
    dest.hit_count += src.hit_count
    dest.heal_count += src.heal_count
    dest.deaths += src.deaths
    dest.last_hit_ts = max(dest.last_hit_ts, src.last_hit_ts)
    for skill_id, sp in src.skills.items():
        own = dest.skills.get(skill_id)
        if own is None:
            dest.skills[skill_id] = copy.deepcopy(sp)
        else:
            _absorb_skill_parse(own, sp)


def _absorb_skill_parse(dest: SkillParse, src: SkillParse) -> None:
    dest.damage += src.damage
    dest.hit_count += src.hit_count
    dest.crit_count += src.crit_count
    dest.crit_damage += src.crit_damage
    dest.min_hit = min(dest.min_hit, src.min_hit)
    dest.max_hit = max(dest.max_hit, src.max_hit)
    dest.heals += src.heals
    dest.self_heals += src.self_heals
    dest.group_heals += src.group_heals
    dest.heal_count += src.heal_count
    dest.min_heal = min(dest.min_heal, src.min_heal)
    dest.max_heal = max(dest.max_heal, src.max_heal)
    dest.damage_taken += src.damage_taken
    dest.taken_count += src.taken_count
    dest.last_hit_ts = max(dest.last_hit_ts, src.last_hit_ts)
    for affinity, value in src.affinity_damage.items():
        dest.affinity_damage[affinity] = dest.affinity_damage.get(affinity, 0.0) + value
    for affinity, count in src.affinity_hits.items():
        dest.affinity_hits[affinity] = dest.affinity_hits.get(affinity, 0) + count
    for affinity, crits in src.affinity_crits.items():
        dest.affinity_crits[affinity] = dest.affinity_crits.get(affinity, 0) + crits


def _absorb_seconds(dest: dict[int, float], src: dict[int, float]) -> None:
    for second, damage in src.items():
        dest[second] = dest.get(second, 0.0) + damage


class DpsTrackerHistory:
    """Persistence service for one DpsTracker instance."""

    def __init__(self, tracker):
        self.tracker = tracker

    def archive_current_encounter(self, reason: str = "Encounter Finished",
                                  boss_name: str = "") -> None:
        t = self.tracker
        if reason == "Trash Mobs Cleared" and callable(t.log_line):
            who = (boss_name or "").strip() or (t.boss_session.target_name or "").strip() or "unknown unit"
            try:
                t.log_line(f"Top DPS: trash run archived as a boss split by '{who}'")
            except Exception:
                pass
        if t.in_dummy_fight or t.dummy_session.group_damage > 0:
            sessions = [t.dummy_session]
        elif t.in_boss_fight or t.boss_session.group_damage > 0:
            sessions = [t.boss_session] if t.boss_session.group_damage > 0 else [t.boss_adds_session]
        elif t.trash_session.group_damage > 0:
            sessions = [t.trash_session]
        else:
            sessions = []
        label = boss_file_label(boss_name) if boss_name else ""
        if not label and sessions:
            head = sessions[0]
            if head.kind in ("boss", "boss_adds"):
                label = boss_file_label(head.target_name)
        for session in sessions:
            if session.group_damage <= 0:
                continue
            archived = copy.deepcopy(session)
            if session is t.boss_session and t.boss_adds_session.group_damage > 0:
                _absorb_boss_adds(archived, t.boss_adds_session)
            archived.pause()
            if reason:
                archived.name = f"{session.name} ({reason})"
            if label:
                archived.boss_label = label
            archived.mode = game_state.instance_mode(t.model)
            # The client this fight was played on (see the field's note), read
            # from the install rather than from us: the build reading the file
            # later answers nothing about the numbers in it. `game_build_version`
            # caches the install, so this is a dict lookup after the first
            # archive, and an unreadable install stores "" rather than a guess.
            archived.game_version = game_build_version()
            if any(x.start_time == archived.start_time for x in t.history):
                continue
            t.history.append(archived)
            if len(t.history) > 25:
                t.history.pop(0)
            self.persist()

    def set_path(self, path: str | Path | None) -> None:
        t = self.tracker
        t._history_path = Path(path) if path else None
        t._history_dir = None
        if t._history_path is not None:
            self.load()

    def set_dir(self, path: str | Path | None) -> None:
        t = self.tracker
        t._history_path = None
        t._history_dir = Path(path) if path else None
        t._active_profile = None
        if t._history_dir is not None:
            self.load()

    def resolve_file(self) -> Path | None:
        t = self.tracker
        if t._history_path is not None:
            return t._history_path
        if t._history_dir is None:
            return None
        if t._active_profile:
            return t._history_dir / f"dps_history_{_slug_profile(t._active_profile)}.json"
        return t._history_dir / "dps_history.json"

    def profile_slug(self) -> str:
        return _slug_profile(self.tracker._active_profile) if self.tracker._active_profile else ""

    def month_dir(self, start_time: float | None) -> Path:
        t = self.tracker
        return dps_archive.month_dir(t._history_dir, start_time)

    def file_for(self, kind: str | None, start_time: float | None,
                 boss_label: str = "", mode: str = "") -> Path:
        """`<base>/<YYYY-MM>/<Boss>.json.gz` per boss, or `<kind>.json.gz`."""
        if boss_label:
            return self.month_dir(start_time) / f"{boss_file_label(boss_label)}.json.gz"
        return self.month_dir(start_time) / f"{history_kind_stem(kind)}.json.gz"

    _KNOWN_CLASS_TOKENS = frozenset(KNOWN_HERO_CLASSES)

    def persist(self) -> None:
        t = self.tracker
        if t._history_path is not None:
            try:
                dps_archive.write_sessions(Path(t._history_path), t.history)
            except OSError:
                pass
            return
        if t._history_dir is None:
            return
        buckets: dict[Path, list] = {}
        for session in t.history:
            key = (session.boss_label or history_kind_stem(session.kind),
                   self.month_dir(session.start_time))
            buckets.setdefault(key, []).append(session)
        written: set[Path] = set()
        for (bucket, month), sessions in buckets.items():
            path = self.file_for(sessions[0].kind, sessions[0].start_time,
                                 sessions[0].boss_label)
            try:
                old = dps_archive.read_sessions(path)
            except OSError:
                old = []
            # The archive rounds start_time to 2 dp, so a live session and its
            # on-disk copy must dedupe on the SAME rounded value, or every
            # persist re-writes an already-saved session as a near-duplicate.
            merged = {(round(getattr(s, "start_time", None) or 0.0, 2), s.name): s
                      for s in old}
            for s in sessions:
                merged[(round(s.start_time or 0.0, 2), s.name)] = s
            ordered = sorted(merged.values(), key=lambda s: s.start_time or 0)
            try:
                dps_archive.write_sessions(path, ordered)
                written.add(path)
            except OSError:
                continue
        try:
            for month in t._history_dir.iterdir():
                if month.is_dir() and MONTH_DIR_RE.match(month.name):
                    _rmdir_if_empty(month)
        except OSError:
            pass
        try:
            dps_archive.refresh_index(t._history_dir)
        except Exception:
            pass

    def prune_older_than(self, days: float, directory: str | Path | None = None) -> dict:
        t = self.tracker
        base = Path(directory) if directory else t._history_dir
        if base is None:
            return {"folders": 0, "files": 0, "cutoff": ""}
        out = prune_history_older_than(base, days)
        try:
            keep_from = (time.time() - float(days) * 86400.0) if float(days) > 0 else 0.0
        except (TypeError, ValueError):
            keep_from = 0.0
        if keep_from and t.history:
            t.history = [s for s in t.history if (s.start_time or 0.0) >= keep_from]
        return out

    def load(self) -> None:
        t = self.tracker
        if t._history_path is not None:
            path = Path(t._history_path)
            if not path.exists():
                return
            loaded = dps_archive.read_sessions(path)
            if loaded:
                t.history = loaded[-25:]
            return
        if t._history_dir is None:
            return
        today = time.strftime("%Y-%m-%d", time.localtime())
        month = t._history_dir / time.strftime("%Y-%m", time.localtime())
        loaded: list[CombatSession] = []
        if month.is_dir():
            for path in sorted(month.iterdir()):
                if path.is_file() and (path.name.endswith(".json.gz") or path.suffix == ".json"):
                    for s in dps_archive.read_sessions(path):
                        if s.start_time and time.strftime("%Y-%m-%d", time.localtime(s.start_time)) == today:
                            loaded.append(s)
        loaded.sort(key=lambda session: session.start_time or 0.0)
        if loaded:
            t.history = loaded[-25:]
