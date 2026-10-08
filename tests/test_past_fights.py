"""The Past Fights panel is lazy: it lists log FILES from the one index cache and
reads a file only when a row is viewed (or its trash action is used), so opening
a season of logs never parses every file.

This is a UI contract, so it lives here rather than beside the tracker tests:
`scan_history_dir` must stay read-free, and the panel must not touch a log until
something the player did asks for it. The write side — deleting one fight or a
batch — is covered here too.

The layout is the clean one (see `core/dps_archive.py`): `<month>/<Boss>.json.gz`
per boss, `<month>/trash.json.gz`, `<month>/dummy.json.gz`, and one
`index.json` cache. Filenames carry no player/mode/outcome tokens — those are
per-session facts read from the payload.
"""
from __future__ import annotations

import gzip
import json
import time
from pathlib import Path

import pytest


def _fight(kind="boss", name="King Ratsar", start=1000.0,
           target="👑 King Ratsar", damage=500.0, mode="",
           boss_killed=True, boss_label=None) -> dict:
    return {
        "name": name, "kind": kind,
        "boss_label": boss_label if boss_label is not None
                      else (name if kind == "boss" else ""),
        "start_time": start, "end_time": start + 60.0, "state": "PAUSED",
        "target_name": target, "mode": mode,
        "boss_killed": boss_killed,
        "players": [{"name": "Kartik Warrior A1b2 (You)", "is_me": True,
                     "hero_class": "Warrior", "total_damage": damage}],
        "timeline": {}, "deaths": [], "burst_peak": 0.0,
        "burst_peak_time": 0.0,
    }


def _archive_root(base: Path) -> Path:
    """The archive root (where `index.json` lives) for a test path.

    Files are written wherever the test points (`<tmp>/<YYYY-MM>` or the legacy
    `<tmp>/<YYYY-MM>/<DD>`); the index always lives at the scan root, which is
    the top of that tree. Walk up past a `YYYY-MM` month folder (and an optional
    `DD` day folder) to it.
    """
    parts = base.parts
    # Drop a trailing 2-digit day folder, then a trailing YYYY-MM month folder.
    if len(parts) >= 2 and parts[-1].isdigit() and len(parts[-1]) == 2:
        base = base.parent
    if (len(base.parts) >= 2 and len(base.name) == 7 and base.name[4] == "-"
            and base.name[:4].isdigit() and base.name[5:].isdigit()):
        base = base.parent
    return base


def _write_archive(base: Path, filename: str, fights) -> Path:
    """Write a gzipped archive file and rebuild the index cache at its root.

    `base` may be a month or legacy `<month>/<DD>` path; the file lands inside
    it and `index.json` is refreshed at the archive root above it.
    """
    from farever_companion.core import dps_archive

    base.mkdir(parents=True, exist_ok=True)
    p = base / filename
    dps_archive.write_sessions(p, _sessions_from(fights))
    dps_archive.refresh_index(_archive_root(base))
    return p



def _sessions_from(fights):
    from farever_companion.core.dps_data import _session_from_dict
    return [_session_from_dict(f) for f in fights]


# Backwards-friendly alias for the many call sites in this module.
def _write_log(base: Path, filename: str, fights) -> Path:
    return _write_archive(base, filename, fights)


def _log_dir(base: Path, t: float | None = None) -> Path:
    """The month folder a generic `_write_log` lands files in.

    New layout has no `<DD>` day folder — a file's `day` comes from its
    sessions' `start_time`, not the path — so this is just `<base>/<YYYY-MM>`.
    """
    lt = time.localtime(t or time.time())
    return base / time.strftime("%Y-%m", lt)


def _spy_reads(monkeypatch) -> list[Path]:
    """Record every history-file read the index performs."""
    import farever_companion.ui.combat.history_index as hi

    reads: list[Path] = []
    real = hi.read_history_file

    def spy(path):
        reads.append(Path(path))
        return real(path)

    monkeypatch.setattr(hi, "read_history_file", spy)
    return reads



def test_scan_history_dir_reads_no_log_until_a_row_is_opened(tmp_path, monkeypatch):
    """Listing the archive is a readdir and a stat per file — never a parse."""
    import farever_companion.ui.combat.history_index as hi

    day = _log_dir(tmp_path)
    _write_log(day, "King Ratsar.json.gz",
               [_fight("boss"), _fight("boss", start=2000.0)])
    _write_log(day, "trash.json.gz", [_fight("trash")])
    reads = _spy_reads(monkeypatch)

    rows = hi.scan_history_dir(tmp_path)
    assert reads == []                      # the scan opened nothing
    assert len(rows) == 2

    by_name = {r["path"].name: r for r in rows}
    boss_row = by_name["King Ratsar.json.gz"]
    trash_row = by_name["trash.json.gz"]
    # kind/char come from the SESSIONS, surfaced in the index — never the name
    assert boss_row["kind"] == "boss"
    assert boss_row["boss"] == "King Ratsar"
    assert boss_row["char"] == "Kartik Warrior A1b2"
    assert trash_row["kind"] == "trash"

    # asking one row for its fights reads exactly that one file, once
    assert len(boss_row["sessions"]) == 2
    assert reads == [boss_row["path"]]
    _ = list(boss_row["sessions"])
    assert reads == [boss_row["path"]]      # cached, not re-read

    # a different row reads a different file, again only on demand
    assert len(trash_row["sessions"]) == 1
    assert reads == [boss_row["path"], trash_row["path"]]


def test_load_history_sessions_is_the_explicit_on_demand_read(tmp_path):
    import farever_companion.ui.combat.history_index as hi

    day = _log_dir(tmp_path)
    p = _write_log(day, "King Ratsar.json.gz",
                   [_fight("boss")])
    sessions = hi.load_history_sessions(p)
    assert len(sessions) == 1 and sessions[0].kind == "boss"
    assert hi.load_history_sessions(tmp_path / "missing.json") == []


# --- the Combat page's Fights list: DATES -> LOGS -> FIGHTS -----------------

def _fights_host(tmp_path, monkeypatch):
    """A minimal host carrying only what the list mixin needs.

    The mixin reads `cp_content_lay` / `cp_empty_lbl` (built by
    `_build_past_fights_view` on the real page) and calls back into the page
    for loading, so the double supplies those two widgets and records the
    callbacks instead of running them.
    """
    from PySide6 import QtWidgets
    import farever_companion.ui.pages.combat_fights_list as fl

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(fl, "dps_dir", lambda: tmp_path)

    class _Host(fl.CombatFightsListMixin):
        def __init__(self):
            # The REAL view builder, so every test here runs against the same
            # widget tree the app draws — including the frozen toolbar slot.
            from farever_companion.ui.pages.combat_history import (
                CombatHistoryMixin)
            CombatHistoryMixin._build_past_fights_view(self)
            self._cp_fights_filter = "all"
            self.loaded: list = []
            self.deleted: list = []

        def _load_past_fight(self, char, sess):
            self.loaded.append((char, sess))

        def _delete_past_fight(self, path, sess):
            self.deleted.append((path, sess))

        def _get_active_tracker(self):
            return None

        def _sync_history_combo(self):
            pass

        def _render_combat_breakdown(self):
            pass

        def _clear_old_logs(self):
            pass

    return _Host()


def _visible_log_rows(host):
    from PySide6 import QtWidgets
    return [w for w in host.cp_content_container.findChildren(QtWidgets.QFrame)
            if w.objectName() == "PastFightLogRow"]


def _visible_fight_rows(host):
    from PySide6 import QtWidgets
    return [w for w in host.cp_content_container.findChildren(QtWidgets.QFrame)
            if w.objectName() == "PastFightRow"]


def _fold_rows(host):
    """The `N logs with no <Kind> · show` lines the list draws (Phase 2)."""
    from PySide6 import QtWidgets
    return [w for w in host.cp_content_container.findChildren(
        QtWidgets.QPushButton) if w.objectName() == "PastFightsFoldRow"]


def _reveal_folded(host):
    """Unfold the rows the active filter has nothing for, before a render.

    A test that needs to inspect one of those rows has to ask for it: the list
    does not draw them by default, and that IS the fold (`_add_fold_row`). This
    is the same flag the fold line's click sets.
    """
    host._cp_fights_show_nomatch = True


def _drawn_paths(host):
    """The log paths the list actually drew - the fold removes a row entirely."""
    return {e["row"]["path"] for e in host._cp_log_rows}


#: Row chrome that carries no information (the expand chevron).
_ROW_CHROME = {"\u25b8", "\u25be"}


def _assert_tooltip_covers_row(tip: str, row_widget) -> None:
    """Shared invariant: every label the row DRAWS appears in its hover text.

    Used by each kind of row in the Fights view (log, fight, dialog file,
    records), so a tooltip that drifts from the row it belongs to fails a test
    instead of only being noticed on screen.
    """
    from PySide6 import QtWidgets

    labels = [w.text() for w in row_widget.findChildren(QtWidgets.QLabel)
              if w.text() and w.text() not in _ROW_CHROME]
    assert labels, "the row drew no text at all"
    for text in labels:
        assert text in tip, f"the row shows {text!r} but its tooltip is {tip!r}"


def test_the_mode_is_a_session_fact_surfaced_by_the_index(tmp_path):
    """A log written in a named instance carries its mode on the SESSION —
    the list shows it, and the character label must not absorb it."""
    import farever_companion.ui.combat.history_index as hi

    day = tmp_path / "2026-10"
    _write_log(day, "trash.json.gz",
               [_fight("trash", mode="hard")])
    _write_log(day, "King Ratsar.json.gz", [_fight("boss")])

    by_name = {r["path"].name: r for r in hi.scan_history_dir(tmp_path)}
    hard = by_name["trash.json.gz"]
    assert hard["mode"] == "hard"
    assert hard["kind"] == "trash"
    assert hard["boss"] == "👑 King Ratsar"  # from boss_label, not the name
    assert hard["char"] == "Kartik Warrior A1b2"  # "Hard" is not a character
    plain = by_name["King Ratsar.json.gz"]
    assert plain["mode"] == ""
    assert plain["boss"] == "King Ratsar"


def test_the_log_row_shows_the_mode_it_was_written_at(tmp_path, monkeypatch):
    """The list badges a log from the index row alone — no file is opened to
    say which mode the run was — and wears the game's word for the rung
    (VETERAN), never the stored token."""
    from PySide6 import QtWidgets

    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    _write_log(day, "trash.json.gz",
               [_fight("trash", mode="heroic")])
    _write_log(day, "Veteran Ratsar.json.gz",
               [_fight("boss", mode="hard")])
    reads = _spy_reads(monkeypatch)
    host._render_past_fights()
    assert reads == []
    texts = [w.text() for w in host.cp_content_container.findChildren(
        QtWidgets.QLabel)]
    assert "HEROIC" in texts
    assert "VETERAN" in texts
    assert "HARD" not in texts


def test_the_fights_list_groups_logs_by_their_day(tmp_path, monkeypatch):
    """A list of fights is asked "which evening was that?", so the rows are
    grouped by DATE — and the date comes off the index row (the archive's own
    `start_time`), not the mtime, so a file restored or copied later still
    lands on its own day."""
    host = _fights_host(tmp_path, monkeypatch)
    d1 = tmp_path / "2026-10" / "01"
    d2 = tmp_path / "2026-10"
    _write_log(d1, "King Ratsar.json.gz",
               [_fight("boss", start=time.mktime((2026, 10, 1, 20, 0, 0, 0, 0, -1)))])
    _write_log(d2, "trash.json.gz",
               [_fight("trash", start=time.mktime((2026, 10, 2, 20, 0, 0, 0, 0, -1)))])

    host._render_past_fights()
    labels = _day_labels(host)
    assert any("2026-10-01" in t and "Thu" in t for t in labels)
    assert any("2026-10-02" in t and "Fri" in t for t in labels)
    # newest day first
    assert labels.index(next(t for t in labels if "2026-10-02" in t)) \
        < labels.index(next(t for t in labels if "2026-10-01" in t))
    assert len(_visible_log_rows(host)) == 2


def test_expanding_one_log_reads_only_that_log(tmp_path, monkeypatch):
    """The list is lazy per log: nothing is parsed until a row is expanded,
    and expanding one row reads exactly that file."""
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    a = _write_log(day, "King Ratsar.json.gz",
                   [_fight("boss"), _fight("boss", start=2000.0)])
    _write_log(day, "trash.json.gz",
               [_fight("trash")])
    reads = _spy_reads(monkeypatch)

    host._render_past_fights()
    assert reads == []                       # listing read nothing
    assert _visible_fight_rows(host) == []   # and shows no fights yet

    # expand the King Ratsar log: its two fights appear, and only it was read
    entry = next(e for e in host._cp_log_rows if e["row"]["path"] == a)
    host._toggle_log_row(entry)
    assert reads == [a]
    assert len(_visible_fight_rows(host)) == 2

    # collapsing hides them without re-reading; expanding again is cached
    host._toggle_log_row(entry)
    assert not entry["holder"].isVisible()
    host._toggle_log_row(entry)
    assert reads == [a]
    assert len(_visible_fight_rows(host)) == 2


def test_a_rebuild_does_not_re_read_an_expanded_log(tmp_path, monkeypatch):
    """Rebuilding the view must not re-parse a log it already read.

    The list re-creates every row whenever the folder changes, so without a
    parse cache each rebuild threw an expanded log's fights away and read the
    file again to draw the very same rows (duration and damage and all).
    """
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    a = _write_log(day, "King Ratsar.json.gz",
                   [_fight("boss")])
    reads = _spy_reads(monkeypatch)

    host._render_past_fights()
    entry = next(e for e in host._cp_log_rows if e["row"]["path"] == a)
    host._toggle_log_row(entry)
    assert reads == [a]

    # a full rebuild re-creates the rows; expanding again is a cache hit
    host._render_past_fights(force=True)
    entry2 = next(e for e in host._cp_log_rows if e["row"]["path"] == a)
    host._toggle_log_row(entry2)
    assert reads == [a], "the rebuild re-read the log it had already parsed"
    assert len(_visible_fight_rows(host)) == 1


def test_a_rewritten_log_is_read_again(tmp_path, monkeypatch):
    """The cache is keyed by (path, mtime, size), so a changed log re-reads."""
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    name = "King Ratsar.json.gz"
    a = _write_log(day, name, [_fight("boss")])
    reads = _spy_reads(monkeypatch)

    host._render_past_fights()
    entry = next(e for e in host._cp_log_rows if e["row"]["path"] == a)
    host._toggle_log_row(entry)
    assert reads == [a]

    # the log gains a fight: a new size, so the cached entry must not be served
    _write_log(day, name, [_fight("boss"), _fight("boss", start=2000.0)])
    host._render_past_fights(force=True)
    entry2 = next(e for e in host._cp_log_rows if e["row"]["path"] == a)
    host._toggle_log_row(entry2)
    assert reads == [a, a], "a changed log must be read again"
    assert len(_visible_fight_rows(host)) == 2


def test_a_fight_rows_tooltip_repeats_what_the_row_shows(tmp_path, monkeypatch):
    """The hover text must agree with the row beside it.

    It used to drop the timestamp and the kind/FAILED badge, so a row showing
    "22:56:30 Boss Fight (Died (Kartik (You))) FAILED 👑 Reblochonk 00:45
    10,636 DMG" hovered as "Boss Fight (Died…) · 👑 Reblochonk · 00:45 ·
    10,636 DMG" — the same fight, two readings. Everything the row draws is
    built from the session it read, so the check is: every label the row shows
    appears in its tooltip.
    """
    from PySide6 import QtWidgets

    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    a = _write_log(day, "King Ratsar.json.gz",
                   [_fight("boss", damage=10636.0)])
    host._render_past_fights()
    entry = next(e for e in host._cp_log_rows if e["row"]["path"] == a)
    host._toggle_log_row(entry)

    row = _visible_fight_rows(host)[0]
    _assert_tooltip_covers_row(row.toolTip(), row)


def test_every_fights_view_row_agrees_with_its_tooltip(tmp_path, monkeypatch):
    """The Fights view's hover text must repeat the row it belongs to.

    The fight row disagreed first (no timestamp, no FAILED badge); auditing the
    rest of the view found the same hole in the collapsed log row — it dropped
    the kind/difficulty badges, the target and the character tag. This one test
    holds both row kinds to the same rule.
    """
    from PySide6 import QtWidgets

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    day = tmp_path / "2026-10"
    _write_log(day, "King Ratsar_Kartik_Warrior_a1b2_HARD.json",
               [_fight("boss", name="Boss Fight (Boss Defeated)",
                       damage=900.0)])
    _write_log(day, "trash.json.gz",
               [_fight("trash")])

    # 1) the Combat & DPS fights list: collapsed log rows, then fight rows
    host = _fights_host(tmp_path, monkeypatch)
    host._render_past_fights()
    log_rows = _visible_log_rows(host)
    assert log_rows, "no log rows rendered"
    for w in log_rows:
        _assert_tooltip_covers_row(w.toolTip(), w)
    for entry in list(host._cp_log_rows):
        host._toggle_log_row(entry)
    fight_rows = _visible_fight_rows(host)
    assert fight_rows, "no fight rows rendered"
    for w in fight_rows:
        _assert_tooltip_covers_row(w.toolTip(), w)


def test_the_kind_filter_hides_fights_without_touching_other_logs(
        tmp_path, monkeypatch):
    """A filter that hides rows must not pay for the logs it is hiding: only
    the expanded log is read, and only its matching fights are shown."""
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    a = _write_log(day, "King Ratsar.json.gz", [_fight("boss")])
    _write_log(day, "trash.json.gz",
               [_fight("trash")])
    reads = _spy_reads(monkeypatch)

    host._cp_fights_filter = "trash"
    _reveal_folded(host)          # the fold line would hide the boss row
    host._render_past_fights()
    entry = next(e for e in host._cp_log_rows if e["row"]["path"] == a)
    host._toggle_log_row(entry)
    assert reads == [a]                      # the boss log was read, once
    assert _visible_fight_rows(host) == []   # ...and contributed no rows


# --- the day-limited scan: the cold-start combo/breakdown path ---------------

def test_the_scanner_can_be_limited_to_one_day_folder(tmp_path):
    """`scan_history_dir(day=...)` returns only that day's files, so a caller
    that wants just today never builds rows for a season of logs."""
    import farever_companion.ui.combat.history_index as hi

    t1 = time.mktime((2026, 1, 2, 12, 0, 0, 0, 0, -1))
    t2 = time.mktime((2026, 1, 3, 12, 0, 0, 0, 0, -1))
    _write_log(_log_dir(tmp_path, t1),
               "King Ratsar.json.gz",
               [_fight("boss", start=t1)])
    wanted = _write_log(_log_dir(tmp_path, t2),
                        "King Ratsar.json.gz",
                        [_fight("boss", start=t2)])
    day2 = time.strftime("%Y-%m-%d", time.localtime(t2))

    rows = hi.scan_history_dir(tmp_path, day=day2)
    assert [r["path"] for r in rows] == [wanted]
    assert all(r["day"] == day2 for r in rows)


def test_the_day_filter_parses_only_that_days_logs(tmp_path, monkeypatch):
    """The point of the filter: asking for one day must not parse the others.

    This is the 66-file, ~44 ms cold start, in miniature."""
    import farever_companion.ui.combat.history_index as hi

    t1 = time.mktime((2026, 1, 2, 12, 0, 0, 0, 0, -1))
    t2 = time.mktime((2026, 1, 3, 12, 0, 0, 0, 0, -1))
    old = _write_log(_log_dir(tmp_path, t1),
                     "Old King.json.gz",
                     [_fight("boss", name="Old King", start=t1)])
    new = _write_log(_log_dir(tmp_path, t2),
                     "New King.json.gz",
                     [_fight("boss", name="New King", start=t2)])
    day2 = time.strftime("%Y-%m-%d", time.localtime(t2))
    reads = _spy_reads(monkeypatch)

    rows = hi.scan_history_dir(tmp_path, day=day2)
    for r in rows:
        list(r["sessions"])          # force whatever the caller would ask for

    assert reads == [new], "a day-limited scan parsed another day's log"
    assert old not in reads


def test_the_encounter_combo_source_is_today_only(tmp_path, monkeypatch):
    """The cold-start combo/breakdown fallback parses TODAY'S logs only.

    Live 2026-10-03: this path walked every archived day and iterated each
    row's `_LazySessions`, parsing all 66 logs on the GUI thread (~44 ms) to
    keep at most three. Older days are the 📜 Fights dialog's job, which lists
    them by name and reads one only when a row is viewed.
    """
    from farever_companion.ui.pages import combat_history as ch

    t_old = time.mktime((2026, 1, 2, 12, 0, 0, 0, 0, -1))
    old = _write_log(_log_dir(tmp_path, t_old),
                     "King Ratsar.json.gz", [_fight("boss", start=t_old)])
    now = time.time()
    today_file = _write_log(_log_dir(tmp_path),
                            "King Ratsar.json.gz",
                            [_fight("boss", start=now)])
    monkeypatch.setattr(ch, "dps_dir", lambda: tmp_path)
    reads = _spy_reads(monkeypatch)

    class _Stub:
        _browse_sessions = None

    label, sessions = ch.CombatHistoryMixin._history_source(_Stub(), None)

    assert label == "All Fights"
    assert [s.start_time for s in sessions] == pytest.approx([now])
    assert reads == [today_file], "the cold-start source parsed an older day"
    assert old not in reads


def test_a_trash_row_names_its_boss_from_the_sessions(tmp_path):
    """A trash pull's row says which boss it ran to, read off the SESSIONS.

    The old layout glued `<Dungeon> - <Boss>` into the FILENAME and parsed it
    back out. The clean layout carries the boss on each trash session
    (`boss_label`); the index surfaces it without opening the log, and the
    dungeon is no longer a tracked fact (there is no dungeon field anywhere).
    """
    import farever_companion.ui.combat.history_index as hi

    day = tmp_path / "2026-10"
    _write_log(day, "trash.json.gz",
               [_fight("trash", boss_label="Reblochonk",
                       target="Reblochonk")])

    rows = [r for r in hi.scan_history_dir(tmp_path) if r["kind"] == "trash"]
    assert len(rows) == 1
    row = rows[0]
    assert row["boss"] == "Reblochonk"
    assert row["dungeon"] == ""
    assert row["char"] == "Kartik Warrior A1b2"
    assert row["name"] == "Trash pulls"


# --- the per-log sidecar: the collapsed row and the records are read-free ----

def _FIXME_sidecar_anchor(path) -> None:
    """Deleted."""
    raise AssertionError("sidecar helper removed")


def test_the_collapsed_log_row_shows_aggregates_without_reading_the_log(
        tmp_path, monkeypatch):
    """The collapsed row answers \"how many fights, how big\" from its sidecar.

    The whole point of the Fights list is that a season of logs opens without
    parsing one; drawing an aggregate line must not quietly undo that. Here the
    count / best damage / best time all come from the sidecar — the log is never
    opened (`reads == []`) — and the hover text repeats the line it drew.
    """
    from PySide6 import QtWidgets

    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    a = _write_log(day, "King Ratsar.json.gz",
                   [_fight("boss"), _fight("boss", start=2000.0,
                                           damage=9000.0)])
    reads = _spy_reads(monkeypatch)

    host._render_past_fights()
    assert reads == [], "the collapsed row parsed a log it had a row for"
    texts = [w.text() for w in host.cp_content_container.findChildren(
        QtWidgets.QLabel)]
    agg = next((t for t in texts if t.startswith("2 fights")), None)
    assert agg is not None, texts
    assert "9,000 DMG" in agg and "01:00" in agg, agg

    for w in _visible_log_rows(host):
        _assert_tooltip_covers_row(w.toolTip(), w)


def test_the_batch_bar_is_frozen_above_the_scrolling_list(tmp_path, monkeypatch):
    """The controls must not scroll away with the logs.

    The batch bar used to be a child of `cp_content_lay` — the scroll area's own
    layout — so scrolling down to older files carried Select All, the filters
    and Delete off the top of the page (live 2026-10-04: "the bar goes up the
    page"). It now lives in its own slot ABOVE the scroll area, and the scroll
    body holds only the day headers and log rows.
    """
    from PySide6 import QtWidgets

    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    log = _write_log(day, "King Ratsar.json.gz",
                     [_fight("boss")])
    host._render_past_fights()

    toolbar = host._cp_fights_bar["widget"]
    assert toolbar.parentWidget() is host.cp_fights_toolbar_host
    # it is NOT inside the scrolling body, which is the whole point
    assert not host.cp_content_container.isAncestorOf(toolbar)
    # the scroll body holds just the rows
    rows = _visible_log_rows(host)
    assert rows and all(host.cp_content_container.isAncestorOf(w)
                        for w in rows)
    # the Select All checkbox the report names sits in the frozen bar
    assert [cb for cb in toolbar.findChildren(QtWidgets.QCheckBox)
            if cb.text() == "Select All"], "the bar lost its Select All"

    # a rebuild swaps the bar rather than stacking a second one
    host._render_past_fights(force=True)
    assert host._cp_fights_bar["widget"] is not toolbar
    assert host._cp_fights_toolbar_lay.count() == 1

    # no logs -> no bar, and the slot is emptied (not left holding a stale one)
    log.unlink()
    host._render_past_fights(force=True)
    assert host._cp_fights_toolbar_lay.count() == 0


def test_the_body_stacks_from_the_top_instead_of_floating_apart(
        tmp_path, monkeypatch):
    """The rows must not spread apart to fill a tall viewport.

    The scroll area is `setWidgetResizable(True)`, so the container is stretched
    to the viewport and its layout hands the leftover height to whatever will
    take it. Two logs in a 760px window leave ~200px spare, and with nothing
    claiming it the day header floated ~50px down the pane while the rows sat
    ~100px apart (live 2026-10-05) - the list read as if it had lost its
    spacing. `_pin_rows_to_top` claims that slack: ONE trailing stretch, added
    last, so the rows stack at the layout's own spacing and every spare pixel
    falls to the bottom however tall the window is, and no rebuild leaves a
    second one behind.
    """
    from PySide6 import QtWidgets

    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    _write_log(day, "King Ratsar.json.gz", [_fight("boss")])
    _write_log(day, "Queen Vex.json.gz",
               [_fight("boss", name="Queen Vex")])

    def spacers():
        lay = host.cp_content_lay
        return [i for i in range(lay.count())
                if lay.itemAt(i).widget() is None
                and lay.itemAt(i).spacerItem() is not None]

    def assert_one_trailing_stretch():
        from PySide6 import QtWidgets

        lay = host.cp_content_lay
        idx = spacers()
        assert len(idx) == 1, ("the body needs exactly one stretch, "
                               "not %d" % len(idx))
        assert idx[0] == lay.count() - 1, "the stretch is not the last item"
        it = lay.itemAt(idx[0])
        assert it.spacerItem() is not None
        # a stretch that can't grow claims nothing, and the rows float again
        assert lay.stretch(idx[0]) == 1, "the trailing stretch does not grow"
        # and nothing ABOVE it may grow: the rows are what must stay put
        assert [lay.stretch(i) for i in range(lay.count())] == (
            [0] * idx[0] + [1]), "a row can stretch, and will float with it"
        tops = []
        for i in range(idx[0]):
            w = lay.itemAt(i).widget()
            # the empty-state label is a permanent item that is hidden while
            # there are rows; it is not part of the stack
            if w is None or w is host.cp_empty_lbl:
                continue
            tops.append((w.objectName(), lay.itemAt(i).geometry().y(),
                         lay.itemAt(i).geometry().height()))
        return tops

    host._render_past_fights()
    tops = assert_one_trailing_stretch()
    names = [t[0] for t in tops]
    assert names[0] == "PastFightsDayHeader", names
    assert names.count("PastFightLogRow") == 2, names

    # extra room must go BELOW the rows: pack the container taller than it
    # needs and re-run the layout, then measure where the rows landed.
    cont = host.cp_content_container
    cont.resize(700, 520)
    host.cp_content_lay.activate()
    host._render_past_fights(force=True)
    for _ in range(4):
        QtWidgets.QApplication.processEvents()
    cont.resize(700, 520)
    host.cp_content_lay.activate()
    drawn = [t for t in assert_one_trailing_stretch()
             if t[2] > 0 and t[0] != "PastFightHolder"]
    assert [t[0] for t in drawn][:3] == ["PastFightsDayHeader",
                                        "PastFightLogRow",
                                        "PastFightLogRow"], drawn
    if len({t[1] for t in drawn}) > 1:
        assert drawn[0][1] <= 4, ("the day header floated %dpx down a tall "
                                  "viewport" % drawn[0][1])
        gaps = [drawn[i + 1][1] - (drawn[i][1] + drawn[i][2])
                for i in range(len(drawn) - 1)]
        assert all(g <= 12 for g in gaps), ("the rows spread apart: gaps %s"
                                            % gaps)

    # rebuilds must not stack stretch on stretch
    host._render_past_fights(force=True)
    host._render_past_fights(force=True)
    assert_one_trailing_stretch()

    # the same holds for the two message branches: a query matching nothing
    # and an empty folder both end in the one stretch, so the message stays up
    host._on_fights_query_changed("nothing-matches-this")
    assert_one_trailing_stretch()
    host._on_fights_query_changed("")
    for log in day.iterdir():
        log.unlink()
    host._render_past_fights(force=True)
    assert_one_trailing_stretch()


def test_the_kind_filter_chips_act_as_a_radio_group(tmp_path, monkeypatch):
    """Clicking the ACTIVE chip must leave it selected, not blank the row.

    The five chips are checkable, so a click on the chip already in force
    unchecked it while `_cp_fights_filter` kept filtering that kind — the bar
    then showed nothing selected over a list that was still filtered, and only
    a click on some other chip put the row back in sync. The chips are a radio
    group: whichever kind is in force is the one shown checked.
    """
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    _write_log(day, "King Ratsar.json.gz", [_fight("boss")])
    host._render_past_fights()

    def chips():
        return (host._cp_fights_bar or {}).get("filters", {})

    assert chips()["all"].isChecked()
    chips()["boss"].click()
    assert host._cp_fights_filter == "boss"
    assert chips()["boss"].isChecked() and not chips()["all"].isChecked()

    # the chip that is ALREADY active must stay checked when clicked again
    chips()["boss"].click()
    assert host._cp_fights_filter == "boss"
    assert chips()["boss"].isChecked(), "the active filter chip unchecked itself"
    assert sum(1 for b in chips().values() if b.isChecked()) == 1


def _log_row(host, path):
    """The entry AND the row widget for one log, by its path.

    The widget is looked up by POSITION rather than from the entry: the entries
    and the rendered rows are appended in the same loop, and keeping a second
    Python reference to a widget the list rebuilds and deletes is how a wrapper
    outlives its C++ object.
    """
    entries = host._cp_log_rows
    rows = _visible_log_rows(host)
    assert len(entries) == len(rows), (len(entries), len(rows))
    i = next(k for k, e in enumerate(entries) if e["row"]["path"] == path)
    return entries[i], rows[i]


def _row_labels(w):
    from PySide6 import QtWidgets
    return [l.text() for l in w.findChildren(QtWidgets.QLabel) if l.text()]


def _holder_text(entry):
    """Every line an expanded log's holder draws (fight rows are not labels)."""
    from PySide6 import QtWidgets
    lay = entry["holder"].layout()
    return [lay.itemAt(i).widget().text() for i in range(lay.count())
            if isinstance(lay.itemAt(i).widget(), QtWidgets.QLabel)
            and lay.itemAt(i).widget().text()]


def test_a_filter_tells_the_row_what_it_will_find_without_reading_a_log(
        tmp_path, monkeypatch):
    """The row answers "is there anything in here for me?" BEFORE it is opened.

    The complaint was having to expand a row to find out. A log whose NAME says
    it cannot hold what the filter asks for says so on the row - a muted
    `no Trash` chip and a dimmed chevron - and the verdict costs no read: the
    name and the sidecar are already on the row.
    """
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    boss = _write_log(day, "King Ratsar.json.gz",
                      [_fight("boss")])
    trash = _write_log(day, "trash.json.gz",
                       [_fight("trash")])
    reads = _spy_reads(monkeypatch)

    host._cp_fights_filter = "trash"
    _reveal_folded(host)          # keep the ruled-out row on screen to read it
    host._render_past_fights(force=True)
    assert reads == [], "the verdict parsed a log to draw itself"

    b_entry, b_row = _log_row(host, boss)
    t_entry, t_row = _log_row(host, trash)
    assert b_entry["verdict"] == "none"
    assert "no Trash" in _row_labels(b_row)
    assert t_entry["verdict"] == "has"
    assert "no Trash" not in _row_labels(t_row)

    # The dim chevron is a HINT, never a lock: the row still opens, and the
    # holder then says why it is bare instead of going blank.
    host._toggle_log_row(b_entry)
    assert _holder_text(b_entry) == ["(no Trash fights in this log)"]
    assert reads == [boss]          # one log, and only because it was opened


def test_a_boss_log_under_failed_is_never_ruled_out(tmp_path, monkeypatch):
    """Only a log that cannot BE a failure is ruled out.

    `summarize` counts only fights that dealt damage, so a boss log whose
    index row reports no failure can still hold a wipe with nothing on the
    board. Failed therefore never says "no Failed" to a boss log; a trash
    log it does.
    """
    from farever_companion.ui import theme

    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    boss = _write_log(day, "King Ratsar.json.gz",
                      [_fight("boss",
                             name="Boss Fight (Boss Defeated)")])
    trash = _write_log(day, "trash.json.gz",
                       [_fight("trash")])
    # a KILL archives as fights=1, has_failure=False — no refresh needed,
    # `_write_log` already rebuilt the index

    host._cp_fights_filter = "failed"
    _reveal_folded(host)          # the trash row folds; it has to be readable
    host._render_past_fights(force=True)
    b_entry, b_row = _log_row(host, boss)
    t_entry, t_row = _log_row(host, trash)
    assert b_entry["verdict"] == "unknown"
    assert "no Failed" not in _row_labels(b_row)
    assert theme.DIM not in b_entry["chev"].styleSheet()
    assert t_entry["verdict"] == "none"
    assert "no Failed" in _row_labels(t_row)
    assert theme.DIM in t_entry["chev"].styleSheet()




def test_every_collapsed_row_always_draws_its_aggregate_line(
        tmp_path, monkeypatch):
    """The collapsed row always has its aggregate line — the index row is the
    sidecar now, written at archive time for every log.

    A row that silently DROPPED the line read as a row that lost its data - the
    other half of "this list looks broken".
    """
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    bare = _write_log(day, "King Ratsar.json.gz",
                      [_fight("boss")])
    counted = _write_log(day, "trash.json.gz",
                         [_fight("trash")])

    host._render_past_fights()
    _e, row = _log_row(host, bare)
    assert any(t.startswith("1 fight") for t in _row_labels(row))
    _e2, row2 = _log_row(host, counted)
    assert any(t.startswith("1 fight") for t in _row_labels(row2))


def test_expanding_any_log_under_any_filter_never_leaves_a_blank_holder(
        tmp_path, monkeypatch):
    """The acceptance line of the fix, as a contract.

    For every filter and every log on disk, an expanded holder ends in fight rows
    or in one line naming why it has none - the report ("empty rows that I need
    to expand to see nothing in them") turned into a test, so the blank holder
    cannot come back through some other path.

    Every row is revealed first, so "every log on disk" really is every log: a
    folded row is still a row a player can reach in one click, and it owes the
    same answer on its holder as one the filter left out.
    """
    from PySide6 import QtWidgets

    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    _write_log(day, "King Ratsar.json.gz", [_fight("boss")])
    _write_log(day, "trash.json.gz",
               [_fight("trash")])
    _write_log(day, "Boss.json.gz", [])

    for filt in ("all", "boss", "trash", "dummy", "failed"):
        host._cp_fights_filter = filt
        _reveal_folded(host)
        host._render_past_fights(force=True)
        assert host._cp_log_rows, filt
        for entry in list(host._cp_log_rows):
            host._toggle_log_row(entry)
        for entry in host._cp_log_rows:
            lay = entry["holder"].layout()
            drawn = [lay.itemAt(i).widget() for i in range(lay.count())]
            name = entry["row"]["name"]
            assert drawn, (filt, name, "blank holder")
            for w in drawn:
                assert (w.objectName() == "PastFightRow"
                        or (isinstance(w, QtWidgets.QLabel) and w.text())),                     (filt, name, w)


def test_the_filter_line_is_per_row_and_no_neighbour_can_hide_it(
        tmp_path, monkeypatch):
    """The original bug, as a test: a neighbour's fights hid the empty line.

    `state["shown"]` totalled fights across EVERY log, so the single list-level
    "nothing matched" note was already hidden the moment some other log
    contributed a row - and the log the filter had emptied expanded onto a blank
    holder. The line belongs to the row now, so the order the rows are opened in
    cannot change what any of them shows.
    """
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    boss = _write_log(day, "King Ratsar.json.gz",
                      [_fight("boss")])
    trash = _write_log(day, "trash.json.gz",
                       [_fight("trash")])
    host._cp_fights_filter = "trash"
    _reveal_folded(host)          # both rows must be drawable to compare them
    host._render_past_fights(force=True)

    b_entry, _br = _log_row(host, boss)
    t_entry, _tr = _log_row(host, trash)
    # the log that HAS fights is opened first: that is what used to hide it
    host._toggle_log_row(t_entry)
    assert _visible_fight_rows(host), "the Trash filter kept no fight"
    assert _holder_text(b_entry) == []
    host._toggle_log_row(b_entry)
    assert _holder_text(b_entry) == ["(no Trash fights in this log)"]
    # ...and there is no list-level note left to be switched off at all
    assert not hasattr(host, "_cp_fights_filter_note")


# --- Phase 2: the fold -------------------------------------------------------

def test_a_filtered_list_folds_the_rows_it_has_nothing_for(tmp_path, monkeypatch):
    """The filter stops drawing rows it has nothing for, behind one line.

    The row verdict already knows a named log cannot hold what the filter asks
    for; drawing it anyway left the list padded with rows whose only content is
    "nothing here". Those rows are now one line for the day they were in.
    """
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    boss = _write_log(day, "King Ratsar.json.gz",
                      [_fight("boss")])
    trash = _write_log(day, "trash.json.gz",
                       [_fight("trash")])
    # an empty log is not indexed at all (no fights = no row)

    host._cp_fights_filter = "trash"
    host._render_past_fights(force=True)

    drawn = _drawn_paths(host)
    assert boss not in drawn, "a row the filter has nothing for was drawn"
    assert {trash} <= drawn, drawn
    folds = _fold_rows(host)
    assert len(folds) == 1, [f.text() for f in folds]
    assert folds[0].text() == "1 log with no Trash  ·  show"
    assert folds[0].isChecked() is False
    # ...and it sits UNDER the rows of its day, not above them
    lay = host.cp_content_lay
    assert lay.indexOf(folds[0]) > max(lay.indexOf(r)
                                       for r in _visible_log_rows(host))


def test_the_fold_reveals_on_click_and_outlives_the_rebuilds(
        tmp_path, monkeypatch):
    """One click lists the folded rows, and the choice is remembered.

    The reveal is a per-instance toggle, the pattern the day-window control
    already uses: a folder change, a rescan or the token's refresh recreates
    every widget, and a choice that dies with them would have to be re-made on
    every tick.
    """
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    boss = _write_log(day, "King Ratsar.json.gz",
                      [_fight("boss")])
    trash = _write_log(day, "trash.json.gz",
                       [_fight("trash")])

    host._cp_fights_filter = "trash"
    host._render_past_fights(force=True)
    assert boss not in _drawn_paths(host)

    _fold_rows(host)[0].click()             # the real button, the real slot
    assert boss in _drawn_paths(host), "clicking the line did not reveal it"
    assert host._cp_fights_show_nomatch is True
    folds = _fold_rows(host)
    assert len(folds) == 1, "the rebuild left the old fold line behind"
    assert folds[0].text().endswith("hide")
    assert folds[0].isChecked() is True

    # a rebuild - the fingerprint is unchanged, so this is the force path
    host._render_past_fights(force=True)
    assert boss in _drawn_paths(host), "a rebuild folded the rows back"
    assert _fold_rows(host)[0].text().endswith("hide")

    # ...and it folds back, through the fresh line, not a remembered widget
    _fold_rows(host)[0].click()
    assert boss not in _drawn_paths(host)
    assert host._cp_fights_show_nomatch is False
    assert _fold_rows(host)[0].text().endswith("show")


def test_the_fold_never_hides_a_row_the_name_cannot_answer(
        tmp_path, monkeypatch):
    """Only a row the filter's own question RULES OUT is folded.

    `unknown` exists because some names cannot answer - a boss log can hold a
    wipe with nothing on the board - so those rows stay visible, and `all`
    filters nothing at all, so it folds nothing either.
    """
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    _write_log(day, "King Ratsar.json.gz", [_fight("boss")])
    _write_log(day, "trash.json.gz",
               [_fight("trash")])

    for filt in ("all", "dummy"):
        host._cp_fights_filter = filt
        host._render_past_fights(force=True)
        assert _fold_rows(host) == [], filt
        assert len(_visible_log_rows(host)) == 2, filt

    # Failed is the mixed case: the trash log cannot BE a failure, so it folds,
    # while the boss log stays put for the verdict that cannot answer.
    host._cp_fights_filter = "failed"
    host._render_past_fights(force=True)
    assert len(_visible_log_rows(host)) == 1
    assert _fold_rows(host)[0].text() == "1 log with no Failed  ·  show"


def test_a_day_whose_logs_all_fold_keeps_its_header(tmp_path, monkeypatch):
    """The fold is per DAY: a heading over nothing is what it must not leave.

    One line for the whole list would have to either drop the empty day's header
    or strand it, so each day folds its own rows and keeps its date and count.
    """
    host = _fights_host(tmp_path, monkeypatch)
    quiet = tmp_path / "2026-10"          # nothing for the Trash filter
    busy = tmp_path / "2026-10"           # one matching log
    t_q = time.mktime((2026, 10, 1, 12, 0, 0, 0, 0, -1))
    t_b = time.mktime((2026, 10, 2, 12, 0, 0, 0, 0, -1))
    _write_log(quiet, "King Ratsar.json.gz", [_fight("boss", start=t_q)])
    _write_log(busy, "trash.json.gz",
               [_fight("trash", start=t_b)])

    host._cp_fights_filter = "trash"
    host._render_past_fights(force=True)
    assert len(_day_labels(host)) > 2, _day_labels(host)   # both days, named
    assert len(_visible_log_rows(host)) == 1
    assert [f.text() for f in _fold_rows(host)] ==         ["1 log with no Trash  ·  show"]


def test_a_new_filter_starts_folded_again(tmp_path, monkeypatch):
    """The reveal was a decision about the filter that hid those rows."""
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    boss = _write_log(day, "King Ratsar.json.gz",
                      [_fight("boss")])
    trash = _write_log(day, "trash.json.gz",
                       [_fight("trash")])

    host._cp_fights_filter = "trash"
    host._render_past_fights(force=True)
    _fold_rows(host)[0].click()
    assert host._cp_fights_show_nomatch is True

    host._set_fights_filter("boss")
    assert host._cp_fights_show_nomatch is False, "a new filter kept the reveal"
    assert boss in _drawn_paths(host)
    assert trash not in _drawn_paths(host), "the other kind folded instead"
    assert [f.text() for f in _fold_rows(host)] ==         ["1 log with no Boss  ·  show"]



def test_a_day_header_names_how_many_logs_the_day_holds(tmp_path, monkeypatch):
    """The day header carries the day's count, never a partial fight total.

    The fight total is drawn only when EVERY log on the day has a sidecar;
    otherwise it would be a partial sum dressed as a total, which is worse than
    the plain log count it replaces.
    """
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    _write_log(day, "King Ratsar.json.gz", [_fight("boss")])
    _write_log(day, "trash.json.gz",
               [_fight("trash")])

    host._render_past_fights()
    shown = _day_labels(host)
    # the index row carries the summary, so the header reads the fights at once
    assert any(t == "2 logs · 2 fights" for t in shown), shown



# --- the day window: a long season draws fresh ------------------------------

def _day_labels(host):
    """Every label a day header draws, found by the header's objectName.

    The header used to be recognised by its `-  date  -` decoration; it now
    carries an objectName, so the rule and the log count beside the date can
    change without a test parsing the header's text.
    """
    from PySide6 import QtWidgets
    heads = [w for w in host.cp_content_container.findChildren(
        QtWidgets.QFrame) if w.objectName() == "PastFightsDayHeader"]
    return [w.text() for h in heads
            for w in h.findChildren(QtWidgets.QLabel) if w.text()]


def _season(tmp_path, days):
    for day in days:
        _write_log(tmp_path / "2026-10" / day[-2:],
                   "King Ratsar.json.gz", [_fight("boss")])


def test_the_fights_list_shows_only_the_most_recent_days(tmp_path, monkeypatch):
    """A long season draws a bounded number of days, not every log ever.

    Live 2026-10-04: the list built a widget per log across the whole season, so
    opening it over months of archives crawled. It now draws only the newest
    `_FIGHTS_RECENT_DAYS` days, with the rest behind a control that says how
    many it is holding back.
    """
    from PySide6 import QtWidgets
    import farever_companion.ui.pages.combat_fights_list as fl

    host = _fights_host(tmp_path, monkeypatch)
    days = [f"2026-10-{d:02d}" for d in range(1, 11)]        # 10 days > 7
    _season(tmp_path, days)

    host._render_past_fights()

    n = fl._FIGHTS_RECENT_DAYS
    assert len(_visible_log_rows(host)) == n
    shown = _day_labels(host)
    for day in days[-n:]:                                    # 10-04 .. 10-10
        assert any(day in t for t in shown), (day, shown)
    for day in days[:-n]:                                    # 10-01 .. 10-03
        assert not any(day in t for t in shown), (day, shown)

    # the control names the number of days it is hiding, and starts unlit
    btn = next(b for b in host._cp_fights_bar["widget"].findChildren(
        QtWidgets.QPushButton) if b.text().startswith("Show all days"))
    assert "(+3)" in btn.text(), btn.text()
    assert not btn.isChecked()


def test_show_all_days_reveals_the_whole_season_and_folds_back(
        tmp_path, monkeypatch):
    """The day window is a toggle that survives the rebuilds it triggers.

    The preference lives on the instance, so the folder-change rebuilds that
    recreate the whole list do not silently snap the view back to 7 days — and
    a player who opened a season can put it away again without leaving the page.
    """
    from PySide6 import QtWidgets
    import farever_companion.ui.pages.combat_fights_list as fl

    host = _fights_host(tmp_path, monkeypatch)
    days = [f"2026-10-{d:02d}" for d in range(1, 11)]
    _season(tmp_path, days)
    host._render_past_fights()
    assert len(_visible_log_rows(host)) == fl._FIGHTS_RECENT_DAYS

    def day_btn():
        return next(b for b in host._cp_fights_bar["widget"].findChildren(
            QtWidgets.QPushButton) if b.isCheckable() and "days" in b.text())

    day_btn().click()
    assert host._cp_fights_show_all_days is True
    assert len(_visible_log_rows(host)) == len(days)
    shown = _day_labels(host)
    for day in days:
        assert any(day in t for t in shown), (day, shown)

    # the choice is remembered across a folder-change rebuild
    host._render_past_fights(force=True)
    assert len(_visible_log_rows(host)) == len(days)
    assert day_btn().isChecked(), "the control did not reflect the open window"

    # ...and it folds back, because it is a toggle, not a one-way door
    day_btn().click()
    assert host._cp_fights_show_all_days is False
    assert len(_visible_log_rows(host)) == fl._FIGHTS_RECENT_DAYS


def test_the_day_window_follows_the_user_setting(tmp_path, monkeypatch):
    """The window size is a user setting, not a hard-coded 7.

    Settings > DPS > Combat DPS Meter > Fights list window. A non-default value
    changes both how many days draw and what the "Show all days" control says
    it is holding back; 0 means show every day, with nothing left to toggle.
    """
    from PySide6 import QtWidgets
    import types

    host = _fights_host(tmp_path, monkeypatch)
    host.s = types.SimpleNamespace(dps_fights_recent_days=3)
    days = [f"2026-10-{d:02d}" for d in range(1, 11)]        # 10 days > 3
    _season(tmp_path, days)

    host._render_past_fights()
    assert len(_visible_log_rows(host)) == 3
    btn = next(b for b in host._cp_fights_bar["widget"].findChildren(
        QtWidgets.QPushButton) if b.text().startswith("Show all days"))
    assert "(+7)" in btn.text(), btn.text()

    # 0 = show every day; there is then nothing for the toggle to reveal, so
    # the control is gone rather than offering to hide what is already shown.
    host.s.dps_fights_recent_days = 0
    host._render_past_fights(force=True)
    assert len(_visible_log_rows(host)) == len(days)
    assert not any(b.isCheckable() and "days" in b.text()
                   for b in host._cp_fights_bar["widget"].findChildren(
                       QtWidgets.QPushButton)), \
        "a show-all toggle survived over an already-open window"


def test_history_days_lists_day_folders_newest_first_without_stats(tmp_path):
    """The cheap half of the scan: day folders by name, no file described.

    The Fights list sizes its day window from this before it describes a single
    log, so it must count only folders that actually hold a log — an empty day
    folder left behind by a delete must not fill the window.
    """
    import farever_companion.ui.combat.history_index as hi

    t1 = time.mktime((2026, 1, 2, 12, 0, 0, 0, 0, -1))
    t2 = time.mktime((2026, 1, 3, 12, 0, 0, 0, 0, -1))
    _write_log(_log_dir(tmp_path, t1),
               "Day One.json.gz", [_fight("boss", name="Day One", start=t1)])
    _write_log(_log_dir(tmp_path, t2),
               "Day Two.json.gz", [_fight("boss", name="Day Two", start=t2)])
    (tmp_path / "2026-01" / "04").mkdir(parents=True)      # empty day folder

    d1 = time.strftime("%Y-%m-%d", time.localtime(t1))
    d2 = time.strftime("%Y-%m-%d", time.localtime(t2))
    assert hi.history_days(tmp_path) == [d2, d1]


def test_the_day_window_scan_describes_only_the_kept_days(tmp_path, monkeypatch):
    """A log outside the window costs no sidecar read — the scan-level saving.

    The render window is only "instant" if the scan skips the work too: the
    stamp is checked BEFORE `_file_descriptor`, so an out-of-window log is never
    stat-ed and its sidecar is never opened.
    """
    import farever_companion.ui.combat.history_index as hi

    t1 = time.mktime((2026, 1, 2, 12, 0, 0, 0, 0, -1))
    t2 = time.mktime((2026, 1, 3, 12, 0, 0, 0, 0, -1))
    old = _write_log(_log_dir(tmp_path, t1),
                     "Old King.json.gz",
                     [_fight("boss", name="Old King", start=t1)])
    new = _write_log(_log_dir(tmp_path, t2),
                     "New King.json.gz",
                     [_fight("boss", name="New King", start=t2)])
    day2 = time.strftime("%Y-%m-%d", time.localtime(t2))

    reads = _spy_reads(monkeypatch)
    rows = hi.scan_history_dir(tmp_path, days={day2})
    assert [r["path"] for r in rows] == [new]
    assert reads == [], "the windowed scan parsed a log"
    assert old not in reads


def test_an_old_layout_day_folder_is_carried_by_the_window(tmp_path):
    """Pre-month-split `<YYYY-MM-DD>/` folders are DATED, not undated.

    Reading them as undated (always shown) would defeat the day window on an
    install that upgraded mid-season, when those folders are the whole season.
    The folder name is the day, so the window includes and excludes them like
    the current `<YYYY-MM>/<DD>/` layout.
    """
    import farever_companion.ui.combat.history_index as hi

    _write_log(tmp_path / "2026-01-02",
               "King Ratsar.json.gz", [_fight("boss")])

    assert [r["day"] for r in hi.scan_history_dir(tmp_path)] == ["2026-01-02"]
    assert [r["day"] for r in hi.scan_history_dir(
        tmp_path, days={"2026-01-02"})] == ["2026-01-02"]
    assert hi.scan_history_dir(tmp_path, days={"2026-01-03"}) == []
    assert hi.history_days(tmp_path) == ["2026-01-02"]


# --- the Fights search box: read-free, name/boss/char only -------------------

def test_the_search_matches_index_fields_without_parsing(tmp_path, monkeypatch):
    """A keystroke must not undo the lazy index.

    The filter matches the row's own index fields (name / boss / character) and
    never parses a log: the whole list stays lazy while the box narrows a season.
    """
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    boss = _write_log(day, "King Ratsar.json.gz", [_fight("boss")])
    pulls = _write_log(day, "trash.json.gz",
                       [_fight("trash", boss_label="Reblochonk",
                               target="Reblochonk")])
    ice = _write_log(day, "Ice Queen.json.gz",
                     [_fight("boss", name="Ice Queen")])
    reads = _spy_reads(monkeypatch)

    def shown(q):
        host._cp_fights_query = q
        host._render_past_fights(force=True)
        return sorted(e["row"]["path"] for e in host._cp_log_rows)

    assert shown("ice") == [ice]                 # row name
    assert shown("reblochonk") == [pulls]        # boss label
    assert shown("kartik") == sorted([boss, pulls, ice])   # character
    assert shown("") == sorted([boss, pulls, ice])
    assert reads == [], "the search parsed a log"

    # typing in the box drives the same filter (the box lives outside the tree)
    host.cp_fights_search.setText("ice")
    assert host._cp_fights_query == "ice"
    assert [e["row"]["path"] for e in host._cp_log_rows] == [ice]

    # a query that matches nothing says so WITHOUT hiding the box to clear it
    host.cp_fights_search.setText("nothing-matches-this")
    assert host._cp_log_rows == []
    assert not host.cp_fights_search.isHidden()


def test_the_search_box_does_not_read_a_log_to_answer(tmp_path, monkeypatch):
    """The whole point: the index stays lazy while the box filters a season."""
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    for i in range(5):
        _write_log(day, f"Boss{i}.json.gz",
                   [_fight("boss", name=f"Boss{i}")])
    reads = _spy_reads(monkeypatch)

    host.cp_fights_search.setText("boss3")
    assert len(host._cp_log_rows) == 1
    host.cp_fights_search.setText("")
    assert len(host._cp_log_rows) == 5
    assert reads == []


# --- deleting archived fights: the file goes when its last fight does --------

def _yes_to_confirm(monkeypatch):
    """Answer every confirm dialog Yes without opening one."""
    from PySide6 import QtWidgets
    monkeypatch.setattr(QtWidgets.QMessageBox, "question",
                        staticmethod(lambda *a, **k: QtWidgets.QMessageBox.Yes))


def test_deleting_every_fight_removes_the_log_and_its_empty_folders(
        tmp_path, monkeypatch):
    """A log whose LAST fight is deleted is removed, not left as an empty stub.

    Rewriting `{"history": []}` left a valid JSON file every scanner kept
    listing — an empty row, a husk on disk and an empty day folder that survived
    on disk while the app showed nothing (live 2026-10-05: "it renders empty
    folders and the files are still on the pc"). The file, its sidecar and any
    folder the removal empties all go.
    """
    import farever_companion.ui.combat.past_fights as pf
    import farever_companion.ui.combat.history_index as hi
    from farever_companion.ui.combat.history_index import load_history_sessions

    _yes_to_confirm(monkeypatch)
    day = tmp_path / "2026-10"
    log = _write_log(day, "King Ratsar.json.gz",
                     [_fight("boss", start=1000.0),
                      _fight("boss", start=2000.0)])
    sessions = load_history_sessions(log)

    assert pf.delete_past_fights_batch(
        None, [(log, s) for s in sessions], active_tracker=None) is True

    assert not log.exists(), "the emptied log file stayed on disk"
    assert not day.exists(), "the emptied month folder stayed"
    assert hi.scan_history_dir(tmp_path) == []


def test_deleting_one_of_several_fights_keeps_the_log_with_the_rest(
        tmp_path, monkeypatch):
    """Only the selected fight goes; the file survives while it still holds one."""
    import farever_companion.ui.combat.past_fights as pf
    from farever_companion.ui.combat.history_index import load_history_sessions

    _yes_to_confirm(monkeypatch)
    day = tmp_path / "2026-10"
    log = _write_log(day, "King Ratsar.json.gz",
                     [_fight("boss", start=1000.0),
                      _fight("boss", name="Other", start=2000.0,
                             target="👑 Other")])
    sessions = load_history_sessions(log)

    assert pf.delete_past_fights_batch(
        None, [(log, sessions[0])], active_tracker=None) is True

    assert log.exists(), "the log still held a fight but was deleted"
    assert day.exists(), "the folder still holds the surviving log"
    kept = load_history_sessions(log)
    assert [s.start_time for s in kept] == [2000.0]


def test_deleting_the_only_fight_removes_the_file(tmp_path, monkeypatch):
    """The single-fight trash path follows the same rule as the batch one."""
    import farever_companion.ui.combat.past_fights as pf
    from farever_companion.ui.combat.history_index import load_history_sessions

    _yes_to_confirm(monkeypatch)
    day = tmp_path / "2026-10"
    log = _write_log(day, "King Ratsar.json.gz", [_fight("boss")])
    sess = load_history_sessions(log)[0]

    assert pf.delete_past_fight(None, log, sess, active_tracker=None) is True
    assert not log.exists(), "the emptied log file stayed on disk"
    assert not day.exists(), "its empty day folder stayed"


# --- Select All: the selection must be visible -----------------------------

def test_select_all_reveals_every_fight_it_selects(tmp_path, monkeypatch):
    """Select All must SHOW what it will delete, not select hidden fights.

    It used to read every listed log and select their fights while leaving the
    logs collapsed, so a bulk delete could remove fights hidden inside rows the
    player never opened (live 2026-10-05: "select all ... looks like it got rid
    of them all"). Ticking it now expands every log that holds a matching
    fight, so the rows about to be deleted are on screen.
    """
    from PySide6 import QtWidgets

    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    _write_log(day, "King Ratsar.json.gz", [_fight("boss")])
    _write_log(day, "Queen Vex.json.gz",
               [_fight("boss", name="Queen Vex", target="👑 Queen Vex")])
    host._render_past_fights()

    cb = next(c for c in host._cp_fights_bar["widget"].findChildren(
        QtWidgets.QCheckBox) if c.text() == "Select All")
    cb.setChecked(True)                     # fires on_select_all

    # both logs are open, and every fight they hold is visible and selected
    assert len(host._cp_log_rows) == 2
    assert all(e["expanded"] and not e["holder"].isHidden()
               for e in host._cp_log_rows), "a selected log stayed collapsed"
    assert len(host._cp_fight_rows) == 2
    assert all(st["selected"] for st in host._cp_fight_rows)
    assert len(_visible_fight_rows(host)) == 2

    # unchecking deselects every fight again
    cb.setChecked(False)
    assert not any(st["selected"] for st in host._cp_fight_rows)


def test_select_all_leaves_a_log_with_nothing_matching_closed(tmp_path, monkeypatch):
    """A log the active filter hides carries no selection, so it stays shut."""
    from PySide6 import QtWidgets

    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    _write_log(day, "King Ratsar.json.gz", [_fight("boss")])
    _write_log(day, "trash_Kartik_Warrior_a1b2.json", [_fight("trash")])
    host._cp_fights_filter = "boss"
    # The trash row folds under this filter, so ask for it: Select All still has
    # to leave it closed once it IS drawn.
    _reveal_folded(host)
    host._render_past_fights()

    cb = next(c for c in host._cp_fights_bar["widget"].findChildren(
        QtWidgets.QCheckBox) if c.text() == "Select All")
    cb.setChecked(True)

    trash = next(e for e in host._cp_log_rows
                 if e["row"]["kind"] == "trash")
    assert not trash["expanded"], "Select All opened a log with no matching fight"
    assert len(host._cp_fight_rows) == 1
    assert host._cp_fight_rows[0]["selected"]


def test_every_fight_row_carries_its_selection_box(tmp_path, monkeypatch):
    """Variant C's `cb` column: a fight SHOWS whether it is selected.

    Selection used to be invisible - a click tinted the row and nothing else, so
    "what will Delete Selected (N) take?" could only be read off the toolbar
    count. The box is the visible half of that same state: it starts unchecked,
    Select All checks it, ticking it changes the selection, and a click on the
    row moves it back - one state, reached from either side.
    """
    from PySide6 import QtWidgets
    from tests.qt_helpers import click

    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    log = _write_log(day, "King Ratsar.json.gz",
                     [_fight("boss"), _fight("boss", name="Queen Vex")])
    host._render_past_fights()
    entry, _row = _log_row(host, log)
    host._toggle_log_row(entry)

    def box_of(row):
        return row.findChild(QtWidgets.QCheckBox, "PastFightSelect")

    rows = _visible_fight_rows(host)
    assert len(rows) == 2, "the log did not expand into its fights"
    for r in rows:
        assert box_of(r) is not None, "a fight row has no selection box"
        assert not box_of(r).isChecked()

    # Select All reaches the boxes (it sets the very state the box draws)
    bar_cb = next(c for c in host._cp_fights_bar["widget"].findChildren(
        QtWidgets.QCheckBox) if c.text() == "Select All")
    bar_cb.setChecked(True)
    assert len(host._cp_fight_rows) == 2
    assert all(box_of(r).isChecked() for r in rows)

    # ...ticking ONE box deselects exactly that fight
    box_of(rows[0]).setChecked(False)
    assert sum(1 for st in host._cp_fight_rows if st["selected"]) == 1

    # ...and a click on the ROW moves the box, because the row's own repaint is
    # what syncs the two
    click(rows[0])
    assert box_of(rows[0]).isChecked()
    assert all(st["selected"] for st in host._cp_fight_rows)


def test_a_killed_boss_fight_says_so_on_its_own_row(tmp_path, monkeypatch):
    """Variant C's outcome chip: KILLED is the other half of FAILED.

    A wipe already said FAILED on its row; the kill had no marker at all, so the
    list could not be scanned for the fights that went right. Gated on the KIND,
    because `was_killed` is a fact about the BOSS: a trash pull that lulls out
    killed nothing, whatever the archive's name claims.
    """
    def labels_of_one_fight(day_name, filename, fight):
        """One log, one fight, on its own day: no list ORDER to assume.

        Fight rows come back in their holder's order, not in the order the logs
        were opened, so expanding three logs in one list and then indexing the
        rows reads whichever one the tree happens to list first (found by this
        test failing). A day per case leaves exactly one row to look at.
        """
        host = _fights_host(tmp_path, monkeypatch)
        day = tmp_path / "2026-10"
        _write_log(day, filename, [fight])
        host._render_past_fights()
        entry, _row = _log_row(host, day / filename)
        host._toggle_log_row(entry)
        rows = _visible_fight_rows(host)
        assert len(rows) == 1, (filename, len(rows))
        return _row_labels(rows[0])

    assert "✔ KILLED" in labels_of_one_fight(
        "02", "King Ratsar.json.gz",
        _fight("boss", name="Boss Fight (Boss Defeated)"))
    # a wipe keeps the outcome it already had, and gets no kill chip
    wipe = labels_of_one_fight("03", "Queen Vex.json.gz",
                               _fight("boss", name="Boss Fight (Died)",
                                      boss_killed=False))
    assert "✔ KILLED" not in wipe
    assert "FAILED" in wipe
    # a trash pull whose name claims a kill: the KIND gate is what stops it
    assert "✔ KILLED" not in labels_of_one_fight(
        "04", "trash.json.gz",
        _fight("trash", name="Boss Fight (Boss Defeated)"))


# --- the recorded party and the client build on a row (2026-10-09) ----------#
#
# Two facts the archive has recorded since 2026-10-09 and nothing drew: who was
# PRESENT (the game's own group roster, which counts a member who dealt no
# damage - the archived player rows are culled to whoever scored) and the client
# build the run was played on. Both reach a row two ways, and that is the point
# of this section: a collapsed LOG row has only the sidecar (the list must stay
# read-free), while a FIGHT row has the parsed session.

def _fight_with_party(kind="boss", name="King Ratsar", start=1000.0, mode="",
                      party=(), build="", **kw) -> dict:
    """A fight dict carrying the party roster and the client build."""
    fight = _fight(kind, name=name, start=start, mode=mode, **kw)
    fight["roster"] = [{"name": n, "hero_class": c, "is_me": m}
                       for n, c, m in party]
    fight["game_version"] = build
    return fight


def test_a_log_row_says_how_many_were_present_and_which_client(
        tmp_path, monkeypatch):
    """The count is a chip on the row; the names are the hover.

    A party is a list and the row is one line, so four names in the row would
    push the damage it exists for off its right edge. The count has to be the
    sidecar's `party_size` (the true member count) rather than the number of
    names the sidecar stored, because that list is capped.
    """
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    _write_log(day, "King Ratsar.json.gz", [
        _fight_with_party(start=1000.0, mode="heroic",
                          party=[("Kartik", "warrior", True),
                                 ("Mira", "priest", False)],
                          build="steam-25782799")])
    host._render_past_fights()
    _entry, row_w = _log_row(host, day / "King Ratsar.json.gz")
    labels = _row_labels(row_w)

    assert "\U0001f465 2" in labels, labels
    assert "steam-25782799" in labels, labels
    tip = row_w.toolTip()
    assert "Kartik (you)" in tip and "Mira" in tip, tip
    _assert_tooltip_covers_row(tip, row_w)


def test_a_log_that_recorded_no_party_draws_no_chip(tmp_path, monkeypatch):
    """Absent is not zero: no chip, and the hover says which fact is missing.

    Every archive written before the capture lands here, so the honest render is
    a row that looks exactly as it did before - and a tooltip that admits the
    build is unrecorded rather than a chip reading "unknown", which would look
    like data the game gave us.
    """
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    _write_log(day, "King Ratsar.json.gz", [_fight("boss")])
    host._render_past_fights()
    _entry, row_w = _log_row(host, day / "King Ratsar.json.gz")
    labels = _row_labels(row_w)

    assert not any("\U0001f465" in t for t in labels), labels
    assert not any("steam" in t for t in labels), labels
    assert "client build not recorded" in row_w.toolTip()


def test_the_party_chip_is_the_largest_party_in_the_log(tmp_path, monkeypatch):
    """One log, two attempts, two different parties: the log's answer is the
    wider one - a member who joined for the kill was still there for that run."""
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    _write_log(day, "King Ratsar.json.gz", [
        _fight_with_party(start=1000.0,
                          party=[("Kartik", "warrior", True)],
                          build="steam-100"),
        _fight_with_party(start=2000.0,
                          party=[("Kartik", "warrior", True),
                                 ("Mira", "priest", False),
                                 ("Thornblade", "rogue", False)],
                          build="steam-200")])
    host._render_past_fights()
    _entry, row_w = _log_row(host, day / "King Ratsar.json.gz")
    labels = _row_labels(row_w)

    assert "\U0001f465 3" in labels, labels
    # the NEWEST session's build is the log's answer...
    assert "steam-200" in labels, labels
    # ...and a log that spans a patch says so on hover
    tip = row_w.toolTip()
    assert "steam-100" in tip and "spans more than one build" in tip, tip


def test_a_fight_row_counts_present_apart_from_scored(tmp_path, monkeypatch):
    """"N players" counted SCORERS; a party of three with one scorer said 1.

    The row was already printing a number it could not explain. Both facts are
    known here (the session holds the party AND the player rows), so the slot
    states them labelled - and the hover names who was present, which is the
    only place the difference is legible.
    """
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    _write_log(day, "King Ratsar.json.gz", [
        _fight_with_party(name="King Ratsar (Boss Defeated)",
                          party=[("Kartik", "warrior", True),
                                 ("Mira", "priest", False),
                                 ("Thornblade", "rogue", False)],
                          build="steam-25782799")])
    host._render_past_fights()
    entry, _row = _log_row(host, day / "King Ratsar.json.gz")
    host._toggle_log_row(entry)

    rows = _visible_fight_rows(host)
    assert len(rows) == 1
    labels = _row_labels(rows[0])
    assert any("3 present" in t and "1 scored" in t for t in labels), labels
    assert "steam-25782799" in labels, labels
    tip = rows[0].toolTip()
    for who in ("Kartik", "Mira", "Thornblade"):
        assert who in tip, tip
    _assert_tooltip_covers_row(tip, rows[0])


def test_a_fight_row_without_a_party_keeps_the_count_it_always_had(
        tmp_path, monkeypatch):
    """An archive from before the capture must not lose the number it had."""
    host = _fights_host(tmp_path, monkeypatch)
    day = tmp_path / "2026-10"
    _write_log(day, "King Ratsar.json.gz", [_fight("boss")])
    host._render_past_fights()
    entry, _row = _log_row(host, day / "King Ratsar.json.gz")
    host._toggle_log_row(entry)

    labels = _row_labels(_visible_fight_rows(host)[0])
    assert any("1 players" in t for t in labels), labels
    assert not any("present" in t for t in labels), labels
