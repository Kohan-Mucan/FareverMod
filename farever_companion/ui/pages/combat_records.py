"""The Boss Records board: your personal best against each boss, per difficulty.

`core/dps_records` answers the question; this is the board that asks it. One row
per boss, one column per difficulty, so a Heroic personal best can never be read
as a Normal one — the record is per difficulty because the FIGHT is, and a board
that merged them would show a best nobody set (see that module's docstring).

Three rules the drawing keeps, all of them inherited from the reader:

* **A wipe is not a kill.** A difficulty cell shows the fastest CONFIRMED kill.
  A boss you only ever wipe on draws as `—` in every column with its attempt
  count beside the name, because "no record" is the true answer and a 0:00
  placeholder would be the false one.
* **A missing record is not a zero.** No Normal kills draws `—`, never `0`.
* **A record you cannot place is still shown.** Runs archived before the game
  named a difficulty form the unknown-difficulty column, drawn only when the
  archive actually holds one.

The board reads the archive INDEX (one sidecar per log), so a whole season of
records costs one `index.json` read rather than a season of gzip parses — the
same lazy read the Fights list is built on. It is per character, because a
personal best belongs to one character: the selector opens on the character
loaded today and offers every other one the archive knows, plus All characters.
"""
from __future__ import annotations

import time

from PySide6 import QtCore, QtWidgets

from .. import theme
from ..combat import scan_history_dir
from ..dps_source_text import difficulty_label
from ...config import dps_dir
from ...core.dps_records import (
    UNKNOWN_BOSS,
    index_characters,
    records_from_index_rows,
)

#: The difficulties the game reports, in the order the board draws them, with
#: the colour the rest of the app badges them with (dim / orange / gold). The
#: caption is the game's word for the rung (mid = VETERAN); the stored token
#: stays `hard`, because it names the record on disk.
_COLUMNS = tuple(
    (token, difficulty_label(token).upper(), col)
    for token, col in (("normal", theme.DIM), ("hard", theme.ORANGE),
                       ("heroic", theme.GOLD)))

#: Where a run whose difficulty the game never named goes. A real column, not a
#: dustbin: those kills happened, and `dps_records.difficulty_of` already gave
#: them a record of their own rather than folding them into "normal". It is
#: drawn ONLY when such a record exists — a permanent `UNKNOWN` column would be
#: a question mark on every board whose archive can answer it.
_UNKNOWN_COLUMN = ("", "UNKNOWN", theme.MUTED)

_CROWN = "\U0001f451"

#: The character selector's "no scoping" row. Deliberate and labelled, because
#: merging two characters' kills reports a personal best neither of them set.
_ALL_CHARS = "All characters"


def _fmt_pb(seconds: float) -> str:
    """A kill time as mm:ss.d — the format the rest of the app times in."""
    if seconds <= 0.0:
        return "—"
    return f"{int(seconds // 60):02d}:{seconds % 60:04.1f}"


def _fmt_dps(dps: float) -> str:
    """Group DPS, abbreviated: a board cell has no room for 12,345.6/s."""
    if dps <= 0.0:
        return "—"
    return f"{dps / 1000.0:.1f}k/s" if dps >= 1000.0 else f"{dps:,.0f}/s"


def _kills_text(n: int) -> str:
    return f"{n} kill" + ("" if n == 1 else "s")


def boss_rows(records) -> list[tuple[str, dict]]:
    """``[(boss, {difficulty: BossRecord})]``, the boss you are proudest of first.

    Grouping by BOSS is the board's own shape (the reader groups by boss AND
    difficulty), and the order is the reader's priority applied to the group:
    most kills, then most attempts — a boss you keep throwing yourself at is the
    more interesting row when the kill counts tie — then the fastest kill, then
    the name, so the order never depends on dict insertion.
    """

    groups: dict[str, dict] = {}
    for rec in records or ():
        groups.setdefault(rec.boss, {})[rec.difficulty] = rec

    def _key(item):
        boss, by_mode = item
        kills = sum(r.kills for r in by_mode.values())
        attempts = sum(r.attempts for r in by_mode.values())
        best = min((r.best_time for r in by_mode.values() if r.best_time > 0.0),
                   default=float("inf"))
        return (-kills, -attempts, best, boss)

    return sorted(groups.items(), key=_key)


def board_totals(records) -> tuple[int, int, int]:
    """``(bosses, kills, wipes)`` over whatever the board is showing.

    Wipes are on the headline because they are half of what the board is about:
    a season of wiping with no kill is a fact the player came here to see, and
    a total that counted only kills would let that season read as a blank board.
    """
    recs = list(records or ())
    attempts = sum(r.attempts for r in recs)
    kills = sum(r.kills for r in recs)
    return len({r.boss for r in recs}), kills, max(0, attempts - kills)


def _record_tooltip(rec, boss: str, label: str) -> str:
    """Everything the record holds, for the cell that shows only its headline."""
    # The column caption is upper case for the header row; in a sentence it is
    # a word, so it reads "no Hard runs" rather than "no HARD runs".
    pretty = ("unknown-difficulty" if label == _UNKNOWN_COLUMN[1]
              else label.title())
    if rec is None or not rec.attempts:
        return (f"<b>{boss}</b> — no {pretty} runs recorded yet.<br>"
                f"<i>Only runs archived at this difficulty show here.</i>")
    lines = [f"<b>{boss}</b> — {pretty}",
             f"Kills: <b>{rec.kills}</b> of {rec.attempts} attempts "
             f"({rec.attempts - rec.kills} wipe"
             f"{'' if rec.attempts - rec.kills == 1 else 's'})"]
    if rec.best_time > 0.0:
        lines.append(f"Fastest kill: <b>{_fmt_pb(rec.best_time)}</b>")
        lines.append(f"Average kill: {_fmt_pb(rec.avg_time)}")
    elif rec.kills:
        # A kill with no clock is still a kill, and the reader counts it as one
        # but refuses to rank it (see `dps_records.boss_records`) — so the cell
        # keeps the `—` and this line is where that gets explained.
        lines.append("<i>Kills recorded without a duration — they count, "
                     "they cannot be ranked.</i>")
    if rec.best_dps > 0.0:
        lines.append(f"Best group DPS: <b>{rec.best_dps:,.1f}/s</b>")
    if rec.best_damage > 0.0:
        lines.append(f"Best kill damage: <b>{rec.best_damage:,.0f}</b>")
        lines.append(f"Damage across kills: {rec.total_damage:,.0f}")
    if rec.last_kill > 0.0:
        lines.append("Last kill: " +
                     time.strftime("%Y-%m-%d %H:%M",
                                   time.localtime(rec.last_kill)))
    lines.append("<i>A wipe is not a kill: only confirmed kills rank here.</i>")
    return "<br>".join(lines)


def _board_cell(rec, boss: str, mode: str, label: str,
                color: str) -> QtWidgets.QFrame:
    """One (boss, difficulty) cell: the personal best, or an honest dash."""
    cell = QtWidgets.QFrame()
    cell.setObjectName("BossRecordCell")
    # The identity rides ON the widget so a test (and a stylesheet) can ask a
    # cell which boss and difficulty it is showing without parsing its text -
    # `boss` is passed in rather than read off `rec`, because the cell that has
    # NO record is exactly the one an empty property would erase.
    cell.setProperty("boss", boss)
    cell.setProperty("difficulty", mode)
    cell.setProperty("has_record", bool(rec is not None and rec.kills))
    cell.setToolTip(_record_tooltip(rec, boss, label))
    cell.setStyleSheet(
        f"QFrame#BossRecordCell {{ background: "
        f"{theme.PANEL_LOW if (rec is not None and rec.kills) else 'transparent'};"
        f" border: 1px solid {theme.BORDER}; border-radius: 4px; }}")
    lay = QtWidgets.QVBoxLayout(cell)
    lay.setContentsMargins(8, 4, 8, 4)
    lay.setSpacing(0)

    big = QtWidgets.QLabel(_fmt_pb(rec.best_time) if rec is not None else "—")
    big.setStyleSheet(
        f"font-size: 13px; font-weight: 800; font-family: monospace; color: "
        f"{color if (rec is not None and rec.best_time > 0.0) else theme.DIM};")
    lay.addWidget(big)

    if rec is not None and rec.attempts:
        sub = _kills_text(rec.kills)
        if rec.best_dps > 0.0:
            sub += f" · {_fmt_dps(rec.best_dps)}"
        elif rec.kills:
            sub += " · unranked"
    else:
        sub = "no runs"
    sub_lbl = QtWidgets.QLabel(sub)
    sub_lbl.setStyleSheet(
        f"font-size: 9.5px; color: "
        f"{theme.MUTED if (rec is not None and rec.kills) else theme.DIM};")
    lay.addWidget(sub_lbl)
    return cell


def _name_cell(boss: str, by_mode: dict, on_delete=None) -> QtWidgets.QWidget:
    """The row's boss cell: the name, plus what the difficulty cells cannot say.

    Plus a quiet ✕ that purges the row: polluted history (a trash mob the
    engine mislabeled as a 👑 fight) owns a whole Records row, and hunting
    its fights one by one in Past Fights is the wrong shape of work.
    """
    kills = sum(r.kills for r in by_mode.values())
    attempts = sum(r.attempts for r in by_mode.values())
    ranked = [r for r in by_mode.values() if r.best_time > 0.0]

    box = QtWidgets.QWidget()
    box.setObjectName("BossRecordName")
    box.setProperty("boss", boss)
    outer = QtWidgets.QHBoxLayout(box)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(2)
    text = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(text)
    lay.setContentsMargins(2, 2, 0, 2)
    lay.setSpacing(0)

    name = QtWidgets.QLabel(f"{_CROWN} {boss}")
    name.setStyleSheet(
        f"font-size: 12px; font-weight: 800; color: "
        f"{theme.TEXT if kills else theme.MUTED};")
    lay.addWidget(name)

    parts = [_kills_text(kills) if kills else "no kill yet"]
    if attempts > kills:
        parts.append(f"{attempts - kills} wipe"
                     + ("" if attempts - kills == 1 else "s"))
    if len(ranked) > 1:
        parts.append(f"{len(ranked)} difficulties cleared")
    if not ranked and attempts:
        parts.append("nothing ranked yet")
    sub = QtWidgets.QLabel(" · ".join(parts))
    sub.setStyleSheet(
        f"font-size: 9.5px; color: {theme.DIM if not kills else theme.MUTED};")
    lay.addWidget(sub)

    tip = [f"<b>{boss}</b>",
           f"{attempts} boss attempt{'' if attempts == 1 else 's'}, "
           f"{kills} confirmed kill{'' if kills == 1 else 's'}"]
    modes = [m for m in by_mode if m]
    if modes:
        tip.append("Difficulty" + ("" if len(modes) == 1 else "ies") +
                   " recorded: " +
                   ", ".join(sorted(difficulty_label(m) or m for m in modes)))
    if attempts > kills:
        wipes = attempts - kills
        tip.append(f"{wipes} wipe{'' if wipes == 1 else 's'} — a wipe is "
                   f"counted, never ranked as a personal best")
    if boss == UNKNOWN_BOSS:
        tip.append("<i>Runs whose boss could not be named collect here rather "
                   "than under a real boss.</i>")
    box.setToolTip("<br>".join(tip))
    outer.addWidget(text, 1)
    if on_delete is not None:
        erase = QtWidgets.QPushButton("✕")
        erase.setObjectName("BossRecordDelete")
        erase.setProperty("boss", boss)
        erase.setCursor(QtCore.Qt.PointingHandCursor)
        erase.setFlat(True)
        erase.setFixedSize(18, 18)
        erase.setStyleSheet(
            f"QPushButton {{ color: {theme.DIM}; font-size: 10px; "
            f"border: none; background: transparent; }}"
            f"QPushButton:hover {{ color: {theme.DANGER}; }}")
        erase.setToolTip(
            f"Delete every archived fight for {boss} — kills, wipes and "
            f"all, from Records and Past Fights together. Cannot be undone.")
        erase.clicked.connect(lambda _checked=False, b=boss: on_delete(b))
        outer.addWidget(erase, 0, QtCore.Qt.AlignTop)
    return box


class CombatRecordsMixin:
    """The Boss Records board: one row per boss, one column per difficulty."""

    # --- the view ----------------------------------------------------------#

    def _build_records_view(self) -> QtWidgets.QWidget:
        """The board's shell: header controls over a scrolling grid of bosses.

        Built once and re-POPULATED by `_render_records_board` (unlike the Fights
        list, which rebuilds its body): the selector and the total line own the
        state the player set, and a rebuild would have to restore it.
        """
        outer = QtWidgets.QWidget()
        outer_lay = QtWidgets.QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(6)

        head = QtWidgets.QHBoxLayout()
        head.setSpacing(8)

        cap = QtWidgets.QLabel("🏆 BOSS RECORDS")
        cap.setStyleSheet(
            f"font-size: 11px; font-weight: 800; color: {theme.GOLD}; "
            f"letter-spacing: 0.5px;")
        cap.setToolTip(
            "Your personal best against each boss, per instance difficulty.\n"
            "Read from the archived fights' summaries — the board never parses "
            "a log.")
        head.addWidget(cap)

        self.cp_records_char = QtWidgets.QComboBox()
        self.cp_records_char.setCursor(QtCore.Qt.PointingHandCursor)
        self.cp_records_char.setToolTip(
            "Whose records these are. A personal best belongs to one "
            "character, so the board opens on the one loaded today.")
        self.cp_records_char.setStyleSheet(
            f"QComboBox {{ min-width: 150px; padding: 3px 8px; font-weight: 700; "
            f"font-size: 11px; border: 1px solid {theme.BORDER}; "
            f"border-radius: 4px; background: {theme.PANEL}; "
            f"color: {theme.TEXT}; }}"
            f"QComboBox::drop-down {{ border: none; width: 18px; }}"
            f"QComboBox QAbstractItemView {{ background: {theme.PANEL}; "
            f"border: 1px solid {theme.BORDER}; "
            f"selection-background-color: {theme.ACCENT_DIM}; }}")
        self.cp_records_char.currentTextChanged.connect(
            self._on_records_char_changed)
        head.addWidget(self.cp_records_char)

        self.cp_records_total = QtWidgets.QLabel("")
        self.cp_records_total.setStyleSheet(
            f"font-size: 10px; color: {theme.MUTED};")
        head.addWidget(self.cp_records_total)
        head.addStretch(1)
        outer_lay.addLayout(head)

        self.cp_records_empty = QtWidgets.QLabel("")
        self.cp_records_empty.setWordWrap(True)
        self.cp_records_empty.setStyleSheet(
            f"color: {theme.DIM}; font-size: 11.5px; padding: 24px 0;")
        self.cp_records_empty.setAlignment(QtCore.Qt.AlignCenter)
        outer_lay.addWidget(self.cp_records_empty)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        self.cp_records_body = QtWidgets.QWidget()
        self.cp_records_grid = QtWidgets.QGridLayout(self.cp_records_body)
        self.cp_records_grid.setContentsMargins(0, 0, 0, 0)
        self.cp_records_grid.setHorizontalSpacing(6)
        self.cp_records_grid.setVerticalSpacing(4)
        scroll.setWidget(self.cp_records_body)
        outer_lay.addWidget(scroll, 1)

        outer.hide()
        self._cp_records_scroll = outer
        # `None` = "the player has not picked", which is NOT "All characters":
        # the first render resolves it to whoever is loaded today (see
        # `_records_char`). Storing a resolved default here instead would freeze
        # the answer the moment the view was built, before a model existed.
        self._cp_records_char: str | None = None
        return outer

    # --- the render --------------------------------------------------------#

    def _render_records_board(self, force: bool = False) -> None:
        """Draw the board for the selected character. Read-free, fingerprinted.

        Called from the page's live tick (`_render_combat_breakdown`), so the
        guard matters: the fingerprint is the index's own `(path, mtime, size)`
        rows plus the selection, which is the SAME signal the Fights list
        rebuilds on — a tick with nothing new on disk costs one fingerprint
        comparison after the index read, and never re-lays a widget.
        """
        grid = getattr(self, "cp_records_grid", None)
        if grid is None:
            return
        rows = scan_history_dir(dps_dir())
        chars = index_characters(rows)
        char = self._records_char(chars)
        self._sync_records_chars(chars, char)

        fp = (char, tuple(sorted((str(r.get("path")), r.get("mtime") or 0.0,
                                  r.get("size") or 0) for r in rows)))
        if not force and getattr(self, "_last_records_fp", None) == fp:
            return
        self._last_records_fp = fp

        records = records_from_index_rows(
            rows, None if char == _ALL_CHARS else char)
        self._clear_records_grid()
        bosses, kills, wipes = board_totals(records)
        if not records:
            self.cp_records_empty.setText(
                "No boss records yet. Finish a dungeon boss and its record "
                "appears here — one per difficulty, so a Heroic kill and a "
                "Normal kill are two different personal bests.")
            self.cp_records_empty.show()
            self.cp_records_total.setText("")
            return
        self.cp_records_empty.hide()

        cols = list(_COLUMNS)
        if any(r.difficulty == "" for r in records):
            # Only drawn when the archive holds such a run: see _UNKNOWN_COLUMN.
            cols.append(_UNKNOWN_COLUMN)
        self.cp_records_total.setText(
            f"{bosses} boss{'' if bosses == 1 else 'es'} · {_kills_text(kills)}"
            + (f" · {wipes} wipe{'' if wipes == 1 else 's'}" if wipes else ""))

        self._draw_records_header(cols)
        # One grid ROW per boss, so the header captions and the cells below them
        # share columns and stay aligned however the pane is resized — a header
        # row of labels over body rows that laid their cells out in one widget
        # would drift apart at the first stretch.
        grouped = boss_rows(records)
        for i, (boss, by_mode) in enumerate(grouped, start=1):
            name = _name_cell(boss, by_mode, self._delete_boss_history)
            name.setMinimumWidth(200)
            grid.addWidget(name, i, 0)
            for c, (mode, label, color) in enumerate(cols, start=1):
                grid.addWidget(
                    _board_cell(by_mode.get(mode), boss, mode, label, color),
                    i, c)
        # The slack lives in one trailing empty row, so a short board on a tall
        # pane keeps its rows their natural height instead of stretching three
        # bosses down the whole page.
        pad = QtWidgets.QWidget()
        pad.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                          QtWidgets.QSizePolicy.Expanding)
        last = len(grouped) + 1
        grid.addWidget(pad, last, 0)
        grid.setRowStretch(last, 1)

    def _delete_boss_history(self, boss: str) -> None:
        """Purge one Records row: every archived fight for `boss`, everywhere.

        One confirmation (this cannot be undone), then `purge_boss` drops the
        sessions from their files and rebuilds the index, and the board
        re-renders forced — the fingerprint would catch it anyway, but the
        player just asked for this row to die and should not wait a tick.
        """
        from ...core import dps_archive

        boss = (boss or "").strip()
        if not boss:
            return
        answer = QtWidgets.QMessageBox.question(
            self._cp_records_scroll,
            "Delete records?",
            f"Delete every archived fight for '{boss}'?\n"
            f"Kills, wipes and all — from Records and Past Fights together. "
            f"Cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)
        if answer != QtWidgets.QMessageBox.Yes:
            return
        try:
            dps_archive.purge_boss(dps_dir(), boss)
        except OSError:
            return
        self._render_records_board(force=True)

    def _draw_records_header(self, cols) -> None:
        """The column captions — BOSS, then one per difficulty."""
        grid = self.cp_records_grid
        cap = QtWidgets.QWidget()
        cap.setObjectName("BossRecordsColHeader")
        cl = QtWidgets.QVBoxLayout(cap)
        cl.setContentsMargins(2, 0, 0, 0)
        cl.setSpacing(0)
        boss_hdr = QtWidgets.QLabel("BOSS")
        boss_hdr.setStyleSheet(
            f"font-size: 9.5px; font-weight: 800; color: {theme.DIM}; "
            f"letter-spacing: 0.5px;")
        cl.addWidget(boss_hdr)
        hint = QtWidgets.QLabel("best kill · mm:ss")
        hint.setStyleSheet(f"font-size: 9px; color: {theme.DIM};")
        cl.addWidget(hint)
        cap.setToolTip(
            "Each column is one difficulty; the number is that difficulty's "
            "fastest CONFIRMED kill. A wipe never sets a record.")
        grid.addWidget(cap, 0, 0)
        grid.setColumnStretch(0, 3)
        for c, (mode, label, color) in enumerate(cols, start=1):
            hdr = QtWidgets.QLabel(label)
            hdr.setObjectName("BossRecordsDiffHeader")
            hdr.setProperty("difficulty", mode)
            hdr.setAlignment(QtCore.Qt.AlignCenter)
            hdr.setStyleSheet(
                f"font-size: 9.5px; font-weight: 800; color: {color}; "
                f"letter-spacing: 0.5px;")
            hdr.setToolTip(
                f"Fastest confirmed {label.title()} kill for this boss. "
                f"Different difficulties are different fights, so they are "
                f"different records — never merged.")
            grid.addWidget(hdr, 0, c)
            grid.setColumnStretch(c, 2)

    def _clear_records_grid(self) -> None:
        """Drop every widget the last render put in the grid (headers too).

        The row STRETCHES go too. A QGridLayout keeps them per row INDEX, so a
        board that drew ten bosses and then three would leave the stretch it
        used to park the slack on sitting on a row that now holds a boss — and
        that one row would grow while the rest shrank (measured offscreen: a
        uniform 45px row became 144px).
        """
        grid = self.cp_records_grid
        for r in range(grid.rowCount()):
            grid.setRowStretch(r, 0)
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    # --- the selection -----------------------------------------------------#

    def _records_char(self, chars) -> str:
        """The character the board is scoped to; ``_ALL_CHARS`` = unscoped."""
        picked = getattr(self, "_cp_records_char", None)
        if picked is None:
            return self._default_records_char(chars)
        return picked if picked in [_ALL_CHARS, *chars] else _ALL_CHARS

    def _default_records_char(self, chars) -> str:
        """The character the board opens on: the one loaded today, else all.

        A personal best is per character, so the default is ONE. A name the
        archive does not hold (a fresh install, a rename, a bare test host)
        falls back to All characters rather than to an empty board — an empty
        board would read as "you have no records", which is a different claim.
        """
        model = getattr(self, "model", None)
        name = (getattr(model, "character_name", "") or "").strip()
        return name if name in chars else _ALL_CHARS

    def _sync_records_chars(self, chars, current: str) -> None:
        """Keep the selector's entries in step with the archive, once per change."""
        combo = getattr(self, "cp_records_char", None)
        if combo is None:
            return
        want = [_ALL_CHARS, *chars]
        have = [combo.itemText(i) for i in range(combo.count())]
        if have == want and combo.currentText() == current:
            return
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(want)
        combo.setCurrentText(current)
        combo.blockSignals(False)

    def _on_records_char_changed(self, text: str) -> None:
        """Selector changed: re-scope the board. `force` — the selection IS the

        change the fingerprint holds, so the ordinary guard would already
        render; forcing keeps this honest even when two characters happen to
        describe the same files."""
        self._cp_records_char = text or _ALL_CHARS
        self._render_records_board(force=True)
