"""The Boss Records board: one row per boss, one column per difficulty.

Two layers, two contracts, and this file covers the pair the rest of the suite
does not: `tests/test_dps.py` pins the SESSION-level reader (`boss_records`),
while here the reader is the archive INDEX (`records_from_index_rows` — the
sidecar path that makes a board of a season cost one JSON read instead of a
season of gzip parses) and the board is the surface that draws it.

The two honesties the reader refuses to trade away are pinned at both layers,
because the board is where they would be lost: a WIPE is not a kill (a boss you
only wipe on draws no record, and its attempts are shown beside the name), and a
difficulty the game never named is its OWN record rather than a merge into
"normal" (it gets its own column, drawn only when the archive holds one).
"""
from __future__ import annotations

import time
from pathlib import Path


# --- the reader: the archive INDEX as records ------------------------------
#
# These tests build index ROWS, not logs: the row is what the board reads, and
# building one directly is how a shape the writer never produced (a legacy
# rollup without the difficulty dimension, a difficulty the game never named)
# can be exercised without forging a file on disk.

def _roll(boss, mode="", kills=1, attempts=None, best_time=60.0, ranked=None,
          dps=1000.0, damage=500.0, total=None, first=1.0, last=1.0) -> dict:
    """One per-(boss, difficulty) rollup, shaped as `dps_records.summarize` writes."""
    ranked = kills if ranked is None else ranked
    return {"boss": boss, "mode": mode,
            "attempts": attempts if attempts is not None else kills,
            "kills": kills, "ranked_kills": ranked,
            "best_time": best_time,
            "kill_total_time": best_time * ranked if ranked else 0.0,
            "best_dps": dps, "best_damage": damage,
            "total_damage": damage if total is None else total,
            "first_kill": first, "last_kill": last}


def _row(char, rollups, **extra) -> dict:
    """One archive INDEX row: a character plus its sidecar's per-boss rollups."""
    from farever_companion.core.dps_records import rollup_key

    bosses = {(k if isinstance(k, str) and "\x1f" in k else rollup_key(*k)): v
              for k, v in rollups.items()}
    out = {"path": extra.pop("path", f"/archives/{char}.json.gz"), "char": char,
           "kind": "boss", "mtime": 1.0, "size": 10,
           "summary": {"version": 2, "fights": 1, "bosses": bosses}}
    out.update(extra)
    return out


def _one(records, boss, mode):
    for rec in records:
        if rec.boss == boss and (rec.difficulty or "") == (mode or ""):
            return rec
    return None


def test_two_logs_of_one_boss_at_one_difficulty_fold_into_one_record():
    """A season of per-day logs is one record, not one per file.

    Counts and totals sum, bests take the better of the two, and the first/last
    kill straddle both — the same folding `merge_rollup` does for the tracker's
    own writes, applied across the index.
    """
    from farever_companion.core.dps_records import records_from_index_rows

    rows = [
        _row("Kartik", {("King Ratsar", "normal"): _roll(
            "King Ratsar", "normal", kills=2, attempts=3, best_time=80.0,
            dps=1000.0, damage=900.0, total=1700.0, first=10.0, last=99.0)}),
        _row("Kartik", {("King Ratsar", "normal"): _roll(
            "King Ratsar", "normal", kills=1, attempts=1, best_time=70.0,
            dps=1200.0, damage=1500.0, total=1500.0, first=5.0, last=5.0)}),
    ]
    records = records_from_index_rows(rows, "Kartik")
    rec = _one(records, "King Ratsar", "normal")
    assert rec is not None
    assert (rec.kills, rec.attempts) == (3, 4)
    assert rec.best_time == 70.0                    # the FASTER of the two
    assert rec.best_dps == 1200.0
    assert rec.best_damage == 1500.0
    assert rec.total_damage == 3200.0
    assert (rec.first_kill, rec.last_kill) == (5.0, 99.0)
    # mean of the three ranked kill times: 80 + 80 + 70 over 3
    assert abs(rec.avg_time - (80.0 * 2 + 70.0) / 3) < 1e-6


def test_the_same_boss_at_two_difficulties_is_two_records():
    """The whole point of the board: Heroic is not Normal, and never averages in."""
    from farever_companion.core.dps_records import records_from_index_rows

    rows = [_row("Kartik", {("King Ratsar", "normal"): _roll(
        "King Ratsar", "normal", kills=4, best_time=60.0),
        ("King Ratsar", "heroic"): _roll(
            "King Ratsar", "heroic", kills=1, best_time=240.0)})]
    records = records_from_index_rows(rows, "Kartik")
    assert _one(records, "King Ratsar", "normal").best_time == 60.0
    assert _one(records, "King Ratsar", "heroic").best_time == 240.0
    assert _one(records, "King Ratsar", "hard") is None
    # ...and the reader did NOT fold the two into a 60s "personal best"
    assert len([r for r in records if r.boss == "King Ratsar"]) == 2


def test_records_are_scoped_to_one_character():
    """A personal best belongs to one character: the default must not merge.

    The unscoped read is offered (the board's All characters row) but it is a
    different number on purpose — if the two ever agreed, a board scoped to one
    character would be reporting somebody else's kill.
    """
    from farever_companion.core.dps_records import records_from_index_rows

    rows = [
        _row("Kartik", {("King Ratsar", "normal"): _roll(
            "King Ratsar", "normal", kills=1, best_time=90.0)}, path="/a.json.gz"),
        _row("Mira", {("King Ratsar", "normal"): _roll(
            "King Ratsar", "normal", kills=1, best_time=10.0)}, path="/b.json.gz"),
    ]
    kartik = _one(records_from_index_rows(rows, "Kartik"), "King Ratsar", "normal")
    mira = _one(records_from_index_rows(rows, "Mira"), "King Ratsar", "normal")
    everyone = _one(records_from_index_rows(rows), "King Ratsar", "normal")
    assert (kartik.best_time, kartik.kills) == (90.0, 1)
    assert (mira.best_time, mira.kills) == (10.0, 1)
    assert (everyone.best_time, everyone.kills) == (10.0, 2)


def test_index_characters_lists_every_character_the_archive_knows():
    from farever_companion.core.dps_records import index_characters

    rows = [_row("Zed", {}), _row("Mira", {}), _row("", {}), {"char": None},
            "not a row"]
    assert index_characters(rows) == ["Mira", "Zed"]
    assert index_characters([]) == []


def test_a_row_with_no_sidecar_contributes_nothing():
    """Absent is not zero: a log nobody has described cannot move a record.

    This is the same rule the Fights list draws its failure state from — a
    missing sidecar is "not measured", so the honest contribution is nothing at
    all rather than a kill counted as zero.
    """
    from farever_companion.core.dps_records import records_from_index_rows

    rows = [{"path": "/x.json.gz", "char": "Kartik"},          # no summary
            {"path": "/y.json.gz", "char": "Kartik", "summary": {}},
            {"path": "/z.json.gz", "char": "Kartik", "summary": {"bosses": "nope"}},
            _row("Kartik", {("King Ratsar", "normal"): _roll(
                "King Ratsar", "normal", kills=1, best_time=30.0)})]
    records = records_from_index_rows(rows, "Kartik")
    assert len(records) == 1
    assert _one(records, "King Ratsar", "normal").kills == 1


def test_a_difficulty_the_game_never_named_is_its_own_record():
    """The legacy rollup key (no separator, no mode) reads as UNKNOWN.

    Those runs really happened, so they must not be dropped; but their
    difficulty is genuinely unrecorded, so folding them into "normal" would
    report a Normal personal best set by a fight nobody labelled Normal.
    """
    from farever_companion.core.dps_records import records_from_index_rows

    legacy = dict(_roll("King Ratsar", "", kills=2, best_time=45.0))
    legacy.pop("mode")                     # the shape before the difficulty key
    rows = [{"path": "/old.json.gz", "char": "Kartik",
             "summary": {"bosses": {"King Ratsar": legacy}}},
            _row("Kartik", {("King Ratsar", "normal"): _roll(
                "King Ratsar", "normal", kills=1, best_time=75.0)})]
    records = records_from_index_rows(rows, "Kartik")
    unknown = _one(records, "King Ratsar", "")
    normal = _one(records, "King Ratsar", "normal")
    assert unknown is not None and (unknown.kills, unknown.best_time) == (2, 45.0)
    assert (normal.kills, normal.best_time) == (1, 75.0)


def test_a_difficulty_the_game_never_reports_cannot_merge_into_a_real_one():
    """A hand-edited or future value is not a difficulty to scope a record by."""
    from farever_companion.core.dps_records import records_from_index_rows

    rows = [_row("Kartik", {("King Ratsar", "NIGHTMARE"): _roll(
        "King Ratsar", "nightmare", kills=3, best_time=5.0)})]
    records = records_from_index_rows(rows, "Kartik")
    assert _one(records, "King Ratsar", "") is not None
    assert _one(records, "King Ratsar", "normal") is None


def test_a_wipe_only_boss_keeps_a_record_with_no_kill():
    """The rule the whole module turns on: wiping is counted, never ranked."""
    from farever_companion.core.dps_records import records_from_index_rows

    rows = [_row("Kartik", {("Slime King", "hard"): _roll(
        "Slime King", "hard", kills=0, attempts=7, best_time=0.0, ranked=0,
        dps=0.0, damage=0.0)})]
    rec = _one(records_from_index_rows(rows, "Kartik"), "Slime King", "hard")
    assert rec is not None
    assert (rec.attempts, rec.kills, rec.best_time) == (7, 0, 0.0)


def test_boss_rows_groups_difficulties_and_leads_with_the_most_killed():
    """The board's row order: kills, then the boss you keep failing, then name."""
    from farever_companion.core.dps_records import records_from_index_rows
    from farever_companion.ui.pages.combat_records import boss_rows

    rows = [_row("Kartik", {
        ("King Ratsar", "normal"): _roll("King Ratsar", "normal", kills=2,
                                         best_time=60.0),
        ("King Ratsar", "heroic"): _roll("King Ratsar", "heroic", kills=1,
                                         best_time=180.0),
        ("Slime King", "hard"): _roll("Slime King", "hard", kills=0, attempts=6,
                                      best_time=0.0, ranked=0),
        ("Mud Golem", "normal"): _roll("Mud Golem", "normal", kills=3,
                                       best_time=90.0)})]
    grouped = boss_rows(records_from_index_rows(rows, "Kartik"))
    # Kills first: King Ratsar (2 normal + 2 heroic) and Mud Golem (3) tie on
    # 3, then on attempts (3 each), so the FASTER kill separates them - King
    # Ratsar's 60s Normal best over Mud Golem's 90s. The all-wipe boss sorts
    # last but is never dropped, which is the point of the row.
    assert [boss for boss, _ in grouped] == ["King Ratsar", "Mud Golem",
                                             "Slime King"]
    by_mode = dict(grouped)["King Ratsar"]
    assert set(by_mode) == {"normal", "heroic"}
    assert by_mode["normal"].best_time == 60.0


# --- the board: what the surface is allowed to claim -----------------------

def _host(tmp_path, monkeypatch, character: str = ""):
    """A host carrying the records view and nothing else it does not need."""
    from PySide6 import QtWidgets
    import farever_companion.ui.pages.combat_records as cr

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(cr, "dps_dir", lambda: tmp_path)

    class _Host(cr.CombatRecordsMixin):
        def __init__(self):
            cr.CombatRecordsMixin._build_records_view(self)
            self.model = type("M", (), {"character_name": character})()

        def log(self, _msg):        # the page's logger, unused here
            pass

    return _Host()


def _page_host(tmp_path, monkeypatch, character: str = "Kartik"):
    """A host carrying the REAL page wiring, not a re-implementation of it.

    The metric chip handler and the body dispatcher are the page's own code, so
    these tests exercise the path a click really takes: `_set_combat_metric` ->
    `_render_combat_breakdown` -> the board.
    """
    from PySide6 import QtWidgets
    import farever_companion.ui.pages.combat_records as cr
    from farever_companion.ui.pages.combat_page import (
        _CP_SEGMENTS,
        CombatPageMixin,
    )

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(cr, "dps_dir", lambda: tmp_path)

    class _Page(CombatPageMixin):
        def __init__(self):
            cr.CombatRecordsMixin._build_records_view(self)
            self.model = type("M", (), {"character_name": character})()
            self._cp_metric = "damage"
            self._cp_segment = "auto"
            self.cp_metric_chips: dict = {}
            # The real chip objects, so `_refresh_segment_chips_hint` (the code
            # that decides what the row SAYS) runs against real widgets.
            self.cp_segment_chips = {
                seg: QtWidgets.QPushButton(lbl) for seg, lbl, _ in _CP_SEGMENTS}
            self.cp_board_container = QtWidgets.QWidget()
            self._cp_rail_container = QtWidgets.QWidget()
            self.cp_full_compare_container = QtWidgets.QWidget()
            self.rendered_past_fights = 0

        # The collaborators the page tick would supply; the dispatcher's own
        # code is left alone.
        def _render_past_fights(self, force=False):
            self.rendered_past_fights += 1

        def _update_combat_rail_for_width(self):
            pass

        def _refresh_rail_compare(self, *a, **k):
            pass

        def _get_displayed_session(self):
            return None

        def log(self, _msg):
            pass

    return _Page()


def _fight(kind="boss", name="King Ratsar", start=1000.0, damage=500.0,
           mode="", boss_killed=True, boss_label=None) -> dict:
    return {
        "name": name, "kind": kind,
        "boss_label": boss_label if boss_label is not None
                      else (name if kind == "boss" else ""),
        "start_time": start, "end_time": start + 60.0, "state": "PAUSED",
        "target_name": f"\U0001f451 {name}", "mode": mode,
        "boss_killed": boss_killed,
        "players": [{"name": "Kartik (You)", "is_me": True,
                     "hero_class": "Warrior", "total_damage": damage}],
        "timeline": {}, "deaths": [], "burst_peak": 0.0, "burst_peak_time": 0.0,
    }


def _write(base: Path, filename: str, fights) -> Path:
    """Write a real archive and refresh the index the board actually reads."""
    from farever_companion.core import dps_archive
    from farever_companion.core.dps_data import _session_from_dict

    month = base / time.strftime("%Y-%m", time.localtime(fights[0]["start_time"]))
    month.mkdir(parents=True, exist_ok=True)
    path = month / filename
    dps_archive.write_sessions(path, [_session_from_dict(f) for f in fights])
    dps_archive.refresh_index(base)
    return path


def _cells(host) -> dict:
    """{(boss, difficulty): cell frame} for whatever the board last drew."""
    from PySide6 import QtWidgets

    out: dict = {}
    for cell in host.cp_records_body.findChildren(QtWidgets.QFrame):
        if cell.objectName() == "BossRecordCell":
            out[(cell.property("boss"), cell.property("difficulty"))] = cell
    return out


def _cell_main(cell) -> str:
    """The cell's headline text (the personal best, or its dash)."""
    from PySide6 import QtWidgets

    return cell.findChildren(QtWidgets.QLabel)[0].text()


def _diff_headers(host) -> list:
    from PySide6 import QtWidgets

    return [lbl.property("difficulty")
            for lbl in host.cp_records_body.findChildren(QtWidgets.QLabel)
            if lbl.objectName() == "BossRecordsDiffHeader"]


def test_the_board_draws_one_column_per_difficulty(tmp_path, monkeypatch):
    """Three columns, three different personal bests for one boss."""
    host = _host(tmp_path, monkeypatch, "Kartik")
    _write(tmp_path, "r.json.gz", [
        _fight(start=1000.0, mode="normal"), _fight(start=2000.0, mode="normal"),
        _fight(start=3000.0, mode="heroic"),
    ])
    host._render_records_board()

    assert _diff_headers(host) == ["normal", "hard", "heroic"]
    cells = _cells(host)
    normal = cells[("King Ratsar", "normal")]
    heroic = cells[("King Ratsar", "heroic")]
    assert _cell_main(normal) == "01:00.0"
    assert _cell_main(heroic) == "01:00.0"
    assert normal.property("has_record") is True
    # the two difficulties are separate cells, not one merged record
    assert normal is not heroic


def test_a_difficulty_with_no_record_draws_a_dash_not_a_zero(tmp_path, monkeypatch):
    """No Veteran kill is `—`; a `0` would be a time nobody achieved."""
    host = _host(tmp_path, monkeypatch, "Kartik")
    _write(tmp_path, "r.json.gz", [_fight(start=1000.0, mode="normal")])
    host._render_records_board()

    hard = _cells(host)[("King Ratsar", "hard")]
    assert _cell_main(hard) == "—"
    assert hard.property("has_record") is False
    assert "no Veteran runs recorded" in hard.toolTip()


def test_a_wipe_only_boss_is_drawn_with_no_record(tmp_path, monkeypatch):
    """The boss you cannot kill still owns a row — with its attempt count."""
    from PySide6 import QtWidgets

    host = _host(tmp_path, monkeypatch, "Kartik")
    _write(tmp_path, "w.json.gz", [
        _fight(start=1000.0, name="Slime King", mode="hard", boss_killed=False)])
    host._render_records_board()

    cells = _cells(host)
    cell = cells[("Slime King", "hard")]
    assert _cell_main(cell) == "—"
    assert cell.property("has_record") is False
    assert "of 1 attempts" in cell.toolTip()
    names = [w for w in host.cp_records_body.findChildren(QtWidgets.QWidget)
             if w.objectName() == "BossRecordName"]
    assert len(names) == 1
    assert "1 wipe" in names[0].toolTip()


def test_the_unknown_column_appears_only_when_the_archive_holds_one(
        tmp_path, monkeypatch):
    """A run archived before the game named a difficulty stays visible."""
    host = _host(tmp_path, monkeypatch, "Kartik")
    _write(tmp_path, "r.json.gz", [_fight(start=1000.0, mode="normal")])
    host._render_records_board()
    assert _diff_headers(host) == ["normal", "hard", "heroic"]

    _write(tmp_path, "r2.json.gz", [_fight(start=5000.0, mode="")])
    host._render_records_board(force=True)
    assert _diff_headers(host) == ["normal", "hard", "heroic", ""]
    cells = _cells(host)
    # the unlabelled run is its own record, NOT folded into Normal
    assert _cell_main(cells[("King Ratsar", "")]) == "01:00.0"


def test_the_board_opens_on_the_character_loaded_today(tmp_path, monkeypatch):
    """A personal best is per character, so the default scopes to one."""
    from PySide6 import QtWidgets

    host = _host(tmp_path, monkeypatch, "Mira")
    _write(tmp_path, "r.json.gz", [_fight(start=1000.0, mode="normal")])
    # a second character's log, faster than Kartik's
    month = tmp_path / "2026-01"
    month.mkdir(parents=True, exist_ok=True)
    from farever_companion.core import dps_archive
    from farever_companion.core.dps_data import _session_from_dict
    fight = _fight(start=2000.0, mode="normal")
    fight["players"] = [{"name": "Mira (You)", "is_me": True,
                         "hero_class": "Priest", "total_damage": 500.0}]
    dps_archive.write_sessions(month / "m.json.gz", [_session_from_dict(fight)])
    dps_archive.refresh_index(tmp_path)

    host._render_records_board()
    combo = host.cp_records_char
    assert [combo.itemText(i) for i in range(combo.count())] == \
        ["All characters", "Kartik", "Mira"]
    assert combo.currentText() == "Mira"
    assert len(_cells(host)) == 3          # one boss, three difficulty columns

    # picking the other character re-scopes the board without a rebuild
    combo.setCurrentText("Kartik")
    assert host.cp_records_char.currentText() == "Kartik"
    assert len(_cells(host)) == 3


def test_the_board_reads_the_index_and_never_parses_a_log(tmp_path, monkeypatch):
    """The read-free contract the whole view is built on.

    A row is drawn from the sidecar alone, so `_render_records_board` must not
    reach the gzip codec — the same rule `scan_history_dir` keeps for the Fights
    list, and the reason a season of records opens instantly.
    """
    from farever_companion.core import dps_archive

    host = _host(tmp_path, monkeypatch, "Kartik")
    _write(tmp_path, "r.json.gz", [_fight(start=1000.0, mode="normal")])

    reads: list = []
    real = dps_archive.read_sessions
    monkeypatch.setattr(dps_archive, "read_sessions",
                        lambda p: (reads.append(p), real(p))[1])
    host._render_records_board()
    assert reads == []
    assert _cells(host)                     # ...and it drew something anyway


def test_a_rebuild_does_not_re_draw_an_unchanged_board(tmp_path, monkeypatch):
    """The render is on the live tick, so an unchanged archive costs nothing.

    Measured on the widget tree: a second render with nothing new on disk must
    not replace the cells it already drew (the page tick calls this four times a
    second).
    """
    from tests.qt_helpers import drain_deleted

    host = _host(tmp_path, monkeypatch, "Kartik")
    _write(tmp_path, "r.json.gz", [_fight(start=1000.0, mode="normal")])
    host._render_records_board()
    before = _cells(host)[("King Ratsar", "normal")]

    host._render_records_board()
    drain_deleted()
    after = _cells(host)[("King Ratsar", "normal")]
    assert after is before                   # the same widget, not a re-layout


# --- the board's real geometry --------------------------------------------
#
# Both of these were found by MEASURING the rendered board, not by reading it,
# and both are the kind of bug the widget tree hides: the row stretch bug made
# three bosses 144px tall in a 620px pane, and mis-aligned captions are exactly
# what a header row drawn separately from the body would produce.

def _shown(host, w=1180, h=620):
    """Layout the board in a real (offscreen) window and hand it back.

    The window must stay REFERENCED by the test: it takes ownership of the
    board, and a collected window deletes the widget tree the assertions are
    about ("internal C++ object already deleted").
    """
    from PySide6 import QtWidgets

    win = QtWidgets.QMainWindow()
    win.setCentralWidget(host._cp_records_scroll)
    win.resize(w, h)
    win.show()
    _pump()
    return win


def _pump(n: int = 4) -> None:
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    for _ in range(n):
        app.processEvents()


def test_a_tall_pane_does_not_stretch_the_boss_rows(tmp_path, monkeypatch):
    """The slack goes BELOW the board, not into three giant boss rows.

    A QGridLayout stretches its rows to fill its parent, so a three-boss board
    in a 620px pane drew 144px rows — and the stretch that parked the slack lives
    on a row INDEX, so it could also land on a boss after a longer board shrank.
    A cell is one line of time plus one line of counts; anything near the pane
    height is the stretch, not the content.
    """
    host = _page_host(tmp_path, monkeypatch, "Kartik")
    _write(tmp_path, "r.json.gz", [_fight(start=1000.0, mode="normal"),
                                   _fight(start=2000.0, mode="heroic")])
    host._set_combat_metric("records")       # draw the board, as the chip does
    win = _shown(host)                       # keep the window alive (see above)

    cell = _cells(host)[("King Ratsar", "normal")]
    assert cell.height() < 80, f"cell stretched to {cell.height()}px"
    # ...and a LONGER board must not leave a stretch behind on a boss row
    for i in range(6):
        _write(tmp_path, f"more{i}.json.gz",
               [_fight(start=10_000.0 + i, name=f"Boss {i}", mode="normal")])
    host._render_records_board(force=True)
    _pump()
    heights = {cell.height() for cell in _cells(host).values()}
    assert max(heights) < 80, f"stale row stretch grew a boss row: {heights}"
    assert win.centralWidget() is host._cp_records_scroll


def test_each_caption_sits_over_the_column_it_names(tmp_path, monkeypatch):
    """Or the board would be claiming a number for the wrong difficulty.

    The captions and the cells are laid out in the SAME grid, which is what
    makes a Heroic caption sit over the Heroic best; this measures the rendered
    geometry rather than trusting the layout code.
    """
    from PySide6 import QtWidgets

    host = _page_host(tmp_path, monkeypatch, "Kartik")
    _write(tmp_path, "r.json.gz", [_fight(start=1000.0, mode="normal"),
                                   _fight(start=2000.0, mode="heroic")])
    host._set_combat_metric("records")       # draw the board, as the chip does
    win = _shown(host)                       # keep the window alive (see above)
    body = win.centralWidget()
    cells = _cells(host)
    captions = {lbl.property("difficulty"): lbl
                for lbl in body.findChildren(QtWidgets.QLabel)
                if lbl.objectName() == "BossRecordsDiffHeader"}
    assert set(captions) == {"normal", "hard", "heroic"}
    for mode, caption in captions.items():
        # Any cell in that column, record or dash: the question is where the
        # column IS, and the Hard column here holds a dash precisely because
        # this boss was never killed on Hard.
        mine = next(c for key, c in cells.items() if key[1] == mode)
        cap_x = caption.mapTo(body, caption.rect().center()).x()
        cell_x = mine.mapTo(body, mine.rect().center()).x()
        assert abs(cap_x - cell_x) <= 1, (mode, cap_x, cell_x)


# --- the page: the board's wiring ------------------------------------------

def test_the_records_metric_is_the_only_view_showing_the_board(tmp_path,
                                                               monkeypatch):
    """Picking 🏆 Records swaps the whole body to the board, and back again.

    The real `_render_combat_breakdown` dispatcher, with only the containers it
    touches: the board must take the body over from the roster/rail (which have
    no place behind a records view) and give it back on the next metric.
    """
    host = _page_host(tmp_path, monkeypatch, "Kartik")
    _write(tmp_path, "r.json.gz", [_fight(start=1000.0, mode="normal")])

    host._set_combat_metric("records")
    # `isHidden` is the explicit show/hide flag this dispatcher sets (these
    # widgets have no shown top-level in a headless run), so it is exactly the
    # question "did the render show the board and stand the others down?".
    assert host._cp_records_scroll.isHidden() is False
    assert host.cp_board_container.isHidden() is True
    assert host._cp_rail_container.isHidden() is True
    assert _cells(host)                      # the board actually rendered

    host._set_combat_metric("damage")
    assert host._cp_records_scroll.isHidden() is True
    assert host.cp_board_container.isHidden() is False


def test_the_pane_back_leaves_the_records_board(tmp_path, monkeypatch):
    """← from the board returns to the damage board, like the other views."""
    host = _page_host(tmp_path, monkeypatch, "Kartik")
    host._set_combat_metric("records")
    assert host._cp_metric == "records"
    assert host._on_combat_pane_back() is True
    assert host._cp_metric == "damage"


def test_the_segment_row_says_it_cannot_slice_the_records_board(
        tmp_path, monkeypatch):
    """The SEGMENT chips slice the live run: on the board they have nothing to
    slice, and the hover says so rather than leaving a live-looking control
    that quietly does nothing.
    """
    host = _page_host(tmp_path, monkeypatch, "Kartik")
    _write(tmp_path, "r.json.gz", [_fight(start=1000.0, mode="normal")])
    host._set_combat_metric("records")
    for chip in host.cp_segment_chips.values():
        assert "records board" in chip.toolTip()


# --- purge: deleting a polluted row ----------------------------------------

def test_purge_boss_removes_only_that_boss_everywhere(tmp_path):
    """A trash mob the engine mislabeled as a 👑 fight owns a whole Records
    row (live: "Runner of the Lost City"). Purging it drops exactly its
    sessions — boss AND boss_adds — from every file, keeps the real boss and
    the trash in those files, and rebuilds the index so Records and Fights
    lose the row together."""
    from farever_companion.core import dps_archive

    _write(tmp_path, "m.json.gz", [
        _fight(start=1000.0, name="Runner of the Lost City"),
        _fight(start=2000.0, name="King Ratsar"),
        _fight(start=3000.0, name="Runner of the Lost City"),
        _fight(start=4000.0, name="Trash pulls", kind="trash",
               boss_label=""),
    ])
    out = dps_archive.purge_boss(tmp_path, "Runner of the Lost City")
    assert out == {"files": 1, "sessions": 2}

    sessions = dps_archive.read_sessions(tmp_path / time.strftime(
        "%Y-%m", time.localtime(1000.0)) / "m.json.gz")
    from farever_companion.core.dps_records import boss_of
    assert [boss_of(s) if s.kind == "boss" else s.kind
            for s in sessions] == ["King Ratsar", "trash"]

    rows = dps_archive.read_index(tmp_path)
    bosses = {b for r in rows for b in (r.get("summary") or {}).get(
        "bosses", {})}
    assert not any("Runner" in str(k) for k in bosses)
    assert any("King Ratsar" in str(k) for k in bosses)

    # nothing to purge, and no name at all: both are no-ops, never errors
    assert dps_archive.purge_boss(tmp_path, "Nobody") == {
        "files": 0, "sessions": 0}
    assert dps_archive.purge_boss(tmp_path, "") == {
        "files": 0, "sessions": 0}


def test_the_row_delete_button_purges_the_boss(tmp_path, monkeypatch):
    """Every Records row carries its own ✕: confirming deletes that boss's
    fights from the archive and the row leaves the board, while the real
    boss beside it stays."""
    from PySide6 import QtWidgets

    host = _host(tmp_path, monkeypatch, "Kartik")
    _write(tmp_path, "r.json.gz", [
        _fight(start=1000.0, name="Runner of the Lost City"),
        _fight(start=2000.0, name="King Ratsar"),
    ])
    host._render_records_board()
    btns = [b for b in host.cp_records_body.findChildren(
        QtWidgets.QPushButton) if b.objectName() == "BossRecordDelete"]
    assert {b.property("boss") for b in btns} == {
        "Runner of the Lost City", "King Ratsar"}

    monkeypatch.setattr(QtWidgets.QMessageBox, "question",
                        lambda *a, **k: QtWidgets.QMessageBox.Yes)
    next(b for b in btns
         if b.property("boss") == "Runner of the Lost City").click()
    _pump()
    names = {w.property("boss")
             for w in host.cp_records_body.findChildren(QtWidgets.QWidget)
             if w.objectName() == "BossRecordName"}
    assert names == {"King Ratsar"}


# --- merge: uncrowned "boss" history re-files as trash ----------------------

def test_merge_uncrowned_bosses_refiles_phantom_fights_as_trash(tmp_path):
    """A champion pack archived as a boss fight (uncertain claims were left
    uncrowned on purpose) is trash with a flag bit, not a boss. Merging moves
    exactly those sessions into the month's trash file — damage and all — and
    drops the phantom boss file, while a crowned real boss stays put."""
    from farever_companion.core import dps_archive

    def fight(name, crowned, start, kind="boss"):
        f = _fight(start=start, name=name)
        f["kind"] = kind
        f["target_name"] = (f"\U0001f451 {name}" if crowned else name)
        f["boss_label"] = name
        return f

    _write(tmp_path, "Runner of the Lost City.json.gz",
           [fight("Runner of the Lost City", False, 1000.0)])
    _write(tmp_path, "King Ratsar.json.gz",
           [fight("King Ratsar", True, 2000.0)])
    out = dps_archive.merge_uncrowned_bosses(tmp_path)
    assert out["sessions"] == 1, out
    assert out["bosses"] == ["Runner of the Lost City"], out

    month = tmp_path / time.strftime("%Y-%m", time.localtime(1000.0))
    assert not (month / "Runner of the Lost City.json.gz").exists()
    trash = dps_archive.read_sessions(month / "trash.json.gz")
    assert len(trash) == 1 and trash[0].kind == "trash"
    assert trash[0].boss_label == ""
    assert trash[0].group_damage > 0.0           # the damage moved with it
    ratsar = dps_archive.read_sessions(month / "King Ratsar.json.gz")
    assert len(ratsar) == 1 and ratsar[0].kind == "boss"
    # ...and the index no longer rolls the phantom boss up
    rows = dps_archive.read_index(tmp_path)
    bosses = {b for r in rows for b in (r.get("summary") or {}).get(
        "bosses", {})}
    assert not any("Runner" in str(k) for k in bosses)
