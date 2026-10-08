"""The SOULWELL tab — the station's window, compressed into one card.

It sits in the Enchants strip (see `enchants.py`, which owns the tab bar and
calls `_ench_soulwell_panel`) because it is the same kind of thing as the
scrolls and gem tables beside it: the game's own sheet rules for one station,
rendered with no game attached.

What is on it, and nothing else:

* the STATION, five slot faces on a ring, slot 1 at the top and clockwise: the
  glyph a player knows the buff by and the game's own name for it. The ring
  is the game window's own arrangement. Each face is its OWN stack: click to
  add a gift to that block (up to five), right-click to take one back off —
  the face wears its count (×n), so the ring reads as a control as well as
  a picture;
* the NUMBERS, one tight table beside the ring: what each buff's luck
  counter pays (base -> cap, off the sheet's own `luckParams`);
* the GIFTS section under the ring — the unit rate and the stacked total
  in ONE line per rarity (`3 × 12m + 15m once = 51m · +30 rep`), so what
  a gift is worth and what the stack buys are never stated twice. The
  minutes ADD per gift and the reputation bonus lands once, and the
  gift-by-gift build-up (`27m → 39m → 51m`) shows the time landing.
  A face fades as its own stack changes, so the change reads as a move rather
  than a snap; the NUMBER is restated at once, so the two never disagree
  about the state, only about how long the look takes to get there.

No live state, and no prose about it: which buffs a station is holding and how
long a live buff has left are runtime state, and this is a drawing of the
station's window, not a view of one. The reader that walked them is retired
(`ai/workspace/buffy/retired/`), so there is nothing here to poll, nothing to
say about polling, and no sentence explaining the absence.
"""
from __future__ import annotations

import math

from PySide6 import QtCore, QtGui, QtWidgets

from ... import components as C
from ... import theme
from ....data import soulwell as soulwell_data

#: How many slots the station has. The game's own window dumps five
#: `ui.win.InventorySlot`s, so the ring draws five — the shape is the station's,
#: not a count the app chose. The sheet also grants five buffs, one face per
#: slot; `test_the_ring_has_one_face_per_luck_buff_in_the_games_order` pins the
#: two together, so a re-tuned sheet is a red test rather than a crowded ring.
_SLOT_COUNT = 5
#: How many gifts one slot stacks: five blocks of five, twenty-five gifts in a
#: full station. The station's own shape (five `ui.win.InventorySlot`s); the
#: totals scale with the count, so a full ring is five times a full slot.
_MAX_PER_SLOT = 5
#: The glyph each of the five buffs wears. Presentation, so it is the app's
#: pick — but keyed by the sheet's own counter id and pinned against that sheet
#: (see the test above), so a renamed counter is a red test rather than a face
#: naming the wrong buff. A counter this table does not know wears the fallback.
_BUFF_EMOJI = {
    "Luck_LegendaryWeapon": "⚔️",
    "Luck_Mount": "🐎",
    "Luck_Glider": "🪂",
    "Luck_RareMaterial": "💎",
    "Luck_PrismaticGear": "✨",
}
_BUFF_EMOJI_FALLBACK = "◆"
#: One slot face: a square holding a glyph and the buff's name — two lines,
#: so the tile stays roomy. 100 is MEASURED, not guessed, and it is the WIDTH
#: that decides it: the widest font this dev box resolves for the app's
#: missing 'Roboto Condensed' wraps 'Legendary Weapon' to two lines once an
#: inner width of 88 is available. 124 leaves room to spare rather than a
#: label Qt has to squeeze (2026-10-10: the tab was hard to read, and the
#: card has the space, so the faces grew 100->124).
#: `test_a_face_holds_its_glyph_and_its_name` measures exactly that, on the
#: laid-out labels, so a size that only fits a narrow font is red here.
_FACE = 124
#: The square the ring is laid out in. 440 grew with the faces (100 -> 124)
#: so adjacent faces still clear each other. The tab's first
#: cut drew this ring at 380px MINIMUM and let it fill the page — 440 is a
#: block in a card that also holds two tables and the stepper, not a page on
#: its own, and it is the shape the game's own window draws.
_RING = 440
#: The glyph's font size, and the box it is GIVEN. An emoji's glyph box is taller
#: than its font size suggests (measured: ~1.25x), and a QLabel's sizeHint is the
#: font's own height — so a label left to its hint clips the emoji it shows. The
#: minimum height is the measured box, and `test_a_face_holds_its_glyph_and_its_
#: name` holds the two together.
_GLYPH_PX = 25
_GLYPH_BOX = round(_GLYPH_PX * 1.25)
#: The card's two number tables read a step above the page's row size — the
#: tab was hard to read at 13.5px and the card has the space — with the small
#: print one step down from that.
_ROW_PX = 15
_MONO = f'font-family:"{theme.MONO_FONT}","Consolas",monospace;'
#: How long a slot face takes to cross-fade between empty and filled. The house
#: pace for a state change is the toggle switch's knob at 120ms
#: (`ui/toggles.py`), and a member whose stepper the user is clicking should have
#: settled well before they look back — so the fade is short enough to feel like
#: the click landed, not like an animation to wait out.
_FILL_MS = 140


def _mix(a: str, b: str, t: float) -> str:
    """`a` at t=0, `b` at t=1, as `#rrggbb` for QSS.

    The endpoints are returned as the theme's own strings — not re-serialised —
    so a face that has settled wears exactly the colour it always did, and the
    tests that read the sheet read the theme constant (`QColor.name()` would
    round-trip them, but a constant that moved would then move twice).
    """
    if t <= 0.0:
        return a
    if t >= 1.0:
        return b
    ca, cb = QtGui.QColor(a), QtGui.QColor(b)
    return QtGui.QColor(
        round(ca.red() + (cb.red() - ca.red()) * t),
        round(ca.green() + (cb.green() - ca.green()) * t),
        round(ca.blue() + (cb.blue() - ca.blue()) * t),
    ).name()


def _duration_text(seconds: int) -> str:
    """Seconds as '45m' (h:mm past an hour) — how long a buff will run.

    Minutes are the sheet's own unit, so the readout never renders a sub-minute
    value and never rounds a minute away.
    """
    total = max(0, int(seconds))
    if total < 3600:
        return f"{total // 60}m"
    return f"{total // 3600}h {total % 3600 // 60:02d}m"


def _chance_text(counter_id: str | None) -> str:
    """The counter's chance as the sheet's own numbers, base -> cap
    ('2.0% → 5.0%'), or a single value when the counter is flat (no
    increment: a range would read '5.0% → 5.0%'). Empty for a buff with no
    counter — the sheet grants every one, so that is a sheet change, not a
    state."""
    if not counter_id:
        return ""
    base = soulwell_data.luck_chance(counter_id, 0)
    cap = soulwell_data.luck_chance(counter_id, 10_000)
    if base is None or cap is None:
        return ""
    if abs(cap - base) < 1e-9:
        return f"{base * 100:.1f}%"
    return f"{base * 100:.1f}% → {cap * 100:.1f}%"


class _SlotFace(QtWidgets.QFrame):
    """One of the station's five slots: a buff's glyph and its name.

    Two lines, like the game's own inventory slot. It is also its OWN STACK:
    click to add a gift to this block (up to `_MAX_PER_SLOT`), right-click to
    take one back off. The face wears its count (×n badge), so the ring reads
    as a control as well as a picture (`changed` -> the panel totals). The
    counter's scope (`luck_scope` — what each buff's luck ticks on) lives in
    the data layer and the LUCK PER BUFF table's stead, not on the tile.
    """

    #: this slot's stack changed — the panel re-reads every face's `.count`
    #: rather than being told a number, so the faces stay the one source.
    changed = QtCore.Signal()

    def __init__(self, glyph: str, label: str, index: int, parent=None):
        super().__init__(parent)
        self.setObjectName("SoulwellFace")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setFixedSize(_FACE, _FACE)
        #: where this face sits in the game's own order, 1-based — the number
        #: is what makes the ring's order readable instead of implied
        self.index = index
        #: how many gifts this block holds (0.._MAX_PER_SLOT) — the state the
        #: clicks ask for (read as `.count`), beside how far the fill fade to
        #: it has got (read as `.fill_t`, driven by whether the stack is
        #: non-empty). Kept apart on purpose: the STATE lands on the click, so
        #: the number and the picture never disagree about what is in the
        #: station, while the LOOK travels there.
        self._count = 0
        self._fill_target: bool | None = None
        self._fill_t = 0.0
        self._anim = QtCore.QPropertyAnimation(self, b"fill", self)
        self._anim.setDuration(_FILL_MS)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(4, 5, 4, 4)
        v.setSpacing(1)
        self._icon = QtWidgets.QLabel(glyph)
        self._icon.setAlignment(QtCore.Qt.AlignCenter)
        self._icon.setMinimumHeight(_GLYPH_BOX)
        self._icon.setStyleSheet(
            f"background:transparent;font-size:{_GLYPH_PX}px;")
        v.addWidget(self._icon, 0)
        self._name = QtWidgets.QLabel(label)
        self._name.setWordWrap(True)
        self._name.setAlignment(QtCore.Qt.AlignCenter)
        v.addWidget(self._name, 1)
        self._count_badge = QtWidgets.QLabel("", self)
        self._count_badge.setGeometry(_FACE - 40, 2, 36, 16)
        self._count_badge.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
        self._count_badge.setStyleSheet(
            f"color:{theme.GOLD};font-size:11px;font-weight:800;"
            "background:transparent;")
        self._count_badge.setVisible(False)
        self.set_filled(False, animate=False)
        self._mark = QtWidgets.QLabel(str(index), self)
        self._mark.setGeometry(4, 2, 14, 12)
        self._mark.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self._mark.setStyleSheet(
            f"color:{theme.DIM};font-size:11px;font-weight:700;"
            "background:transparent;")
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self._refresh_tip()
        # the glyph, name, count and number are decoration: a click anywhere
        # in the box has to reach the face, so they are transparent to the
        # mouse rather than relying on Qt walking an ignored press up the tree
        for lb in (self._icon, self._name, self._mark, self._count_badge):
            lb.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

    @property
    def count(self) -> int:
        """Gifts stacked in this block (0.._MAX_PER_SLOT)."""
        return self._count

    def _refresh_tip(self) -> None:
        self.setToolTip(
            f"Slot {self.index}: {self._count}/{_MAX_PER_SLOT} — "
            f"click to add, right-click to remove")

    def set_count(self, n: int, animate: bool = True) -> None:
        """Stack `n` gifts in this block, clamped to 0.._MAX_PER_SLOT.

        The panel calls this (Clear) and the clicks call it on themselves; the
        fill follows the stack (non-empty lights the face) and `changed` tells
        the panel to restate the totals. A no-op when nothing moves, so a fade
        in flight is never restarted for the same stack.
        """
        n = max(0, min(_MAX_PER_SLOT, int(n)))
        if n == self._count and (n > 0) == bool(self._fill_target):
            return
        self._count = n
        self._count_badge.setText(f"×{n}" if n else "")
        self._count_badge.setVisible(bool(n))
        self._refresh_tip()
        self.set_filled(bool(n), animate=animate)
        self.changed.emit()

    def mousePressEvent(self, e):
        """Left-click stacks one more gift here (a full block wraps to empty,
        so a misclick is one more click to undo, not a hunt for the off switch);
        right-click takes one back off.

        On the PRESS, like the overlay's selectable rows
        (`ui/overlays/entity_rows.py`), so the ring answers as fast as a button
        does. The whole 100px box is the target: the labels over it are
        transparent to the mouse (see `__init__`), so a glyph or a name is as
        clickable as the empty tile around it.
        """
        if e.button() == QtCore.Qt.LeftButton:
            self.set_count(0 if self._count >= _MAX_PER_SLOT
                           else self._count + 1)
        elif e.button() == QtCore.Qt.RightButton:
            self.set_count(self._count - 1)
        super().mousePressEvent(e)

    @property
    def filled(self) -> bool:
        """True when a gift is in this slot — the state the stepper asked for,
        which lands the moment it moves; `fill_t` is where the look has got."""
        return bool(self._fill_target)

    @property
    def fill_t(self) -> float:
        """How filled this slot LOOKS right now: 0.0 empty, 1.0 filled, and
        somewhere between while the fade is running."""
        return self._fill_t

    def _get_fill(self) -> float:
        return self._fill_t

    def _set_fill(self, t: float) -> None:
        """The animated channel: every frame of the fade lands here."""
        self._fill_t = max(0.0, min(1.0, float(t)))
        self._apply_fill()

    fill = QtCore.Property(float, _get_fill, _set_fill)

    def set_filled(self, filled: bool, animate: bool = True) -> None:
        """Fill or empty this slot.

        Each face follows its own stack: a block holding gifts takes the accent
        tint, an empty one the dim edge. An empty slot keeps its glyph and name
        — the buff is still a fact about the station — but wears the dim edge
        and the dim label, while a filled one takes the accent tint.

        The state changes here and now; the tint FADES to it (`_FILL_MS`) so a
        stepper move reads as the ring moving, not blinking. `animate=False` is
        the instant path — the initial build, where there is nothing to move
        from — and a second call that asks for the state already targetted is a
        no-op, so a fade in flight is never restarted from scratch.
        """
        filled = bool(filled)
        if filled == self._fill_target:
            return
        self._fill_target = filled
        self._anim.stop()
        end = 1.0 if filled else 0.0
        if not animate or self._fill_t == end:
            self._set_fill(end)
            return
        # from where the look IS, not from the opposite end: a click arriving
        # mid-fade carries on from the tint already on screen
        self._anim.setStartValue(self._fill_t)
        self._anim.setEndValue(end)
        self._anim.start()

    def finish_fill(self) -> None:
        """Put the look where the state already is, without waiting it out."""
        self._anim.stop()
        if self._fill_target is not None:
            self._set_fill(1.0 if self._fill_target else 0.0)

    def _apply_fill(self) -> None:
        """Paint the face at `_fill_t`: the accent tint fades in as an ALPHA (so
        the surface keeps showing through), the edges and the two label colours
        interpolate between the empty look and the filled one."""
        t = self._fill_t
        if t <= 0.0:
            bg, edge, name = ("transparent", theme.BORDER, theme.DIM)
        elif t >= 1.0:
            bg, edge, name = (theme.with_alpha(theme.ACCENT, 30),
                              theme.ACCENT_BORDER, theme.TEXT)
        else:
            bg = theme.with_alpha(theme.ACCENT, round(30 * t))
            edge = _mix(theme.BORDER, theme.ACCENT_BORDER, t)
            name = _mix(theme.DIM, theme.TEXT, t)
        # the hover rule is the affordance: the fill says what IS, the edge
        # brightening under the pointer says what the face DOES (the cursor is
        # the other half — see `__init__`)
        self.setStyleSheet(
            f"QFrame#SoulwellFace {{ background:{bg}; border:1px solid {edge}; "
            f"border-radius:6px; }}"
            f"QFrame#SoulwellFace:hover {{ border-color:{theme.MUTED}; }}")
        self._name.setStyleSheet(
            f"color:{name};font-size:13px;font-weight:600;"
            "background:transparent;")


class _SlotRing(QtWidgets.QWidget):
    """The station's five slots on a ring, in the game's order.

    Slot 1 sits at the top and the ring runs CLOCKWISE from there, which is the
    arrangement the game's window draws and the reason the faces carry their
    index: on a row the order is left-to-right and needs no label, around a
    circle it has to be stated.

    The widget is a fixed square (`_RING`) and places its children by hand — the
    same shape the game's own window uses, at a fraction of the size the tab's
    first cut drew it.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(_RING, _RING)
        self._faces: list[_SlotFace] = []

    def add_face(self, face: _SlotFace) -> None:
        face.setParent(self)
        self._faces.append(face)

    def total(self) -> int:
        """Gifts stacked across every block — the number the totals read."""
        return sum(f.count for f in self._faces)

    def clear(self) -> None:
        """Empty every block (the Clear button); each face fades its own way."""
        for face in self._faces:
            face.set_count(0)

    def settle(self) -> None:
        """Jump every fade to its end: the ring as the stepper says it, now.

        For a caller that needs the picture rather than the motion — a test
        reading painted pixels, or a surface being photographed.
        """
        for face in self._faces:
            face.finish_fill()

    def _place(self) -> None:
        """Slot 1 at the top, then clockwise every 72°."""
        radius = _RING / 2.0 - _FACE / 2.0 - 8
        cx = cy = _RING / 2.0
        for i, face in enumerate(self._faces):
            ang = math.radians(-90 + i * (360.0 / _SLOT_COUNT))
            face.move(int(round(cx + radius * math.cos(ang) - _FACE / 2.0)),
                      int(round(cy + radius * math.sin(ang) - _FACE / 2.0)))
            face.show()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place()


class SoulwellPanelMixin:
    """The Soulwell tab's one card. Built by `_page_enchants` and shown by the
    tab bar like every other Enchants card; mixed into `ItemPageMixin`."""

    def _ench_soulwell_panel(self) -> QtWidgets.QWidget:
        """The station's window as one card: the ring between its two tables, and
        the gift-count readout under them.

        The card is built here rather than through the Enchants family's own
        `_ench_card` helper (`enchants_rows.py`): this tab rebuilds nothing on
        filter, so it needs none of that helper's row plumbing, and the other
        standalone tabs (`merchants.py`, `farm.py`) title themselves with
        `C.SectionHeader` the same way.
        """
        card = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(C.SectionHeader("Soulwell"))
        lay.addLayout(self._soulwell_sides())
        lay.addLayout(self._soulwell_gift_row())
        return card

    def _soulwell_sides(self) -> QtWidgets.QHBoxLayout:
        """The ring with its one table beside it: LUCK PER BUFF left.

        What each slot's counter PAYS — one row per face, so it reads as an
        annotation on the ring beside it. It sits on the ring's own centre
        line (`AlignVCenter`) because it is much shorter than the ring:
        top-aligned it would leave the ring's lower half with nothing
        beside it. What a gift is worth lives UNDER the ring now, merged
        into the GIFTS section (`_soulwell_gift_row`) — a second side
        table stated the same unit rates the stacked lines already carry.

        The readout is NOT a second column (it is added below, full
        width): it carries the stepper, the per-rarity lines and the rep-5
        condition in one row, and in a side column that row is the first
        thing to squeeze.
        """
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(24)
        self._soulwell_luck_col = self._soulwell_luck_table()
        row.addLayout(self._soulwell_luck_col)
        row.addWidget(self._soulwell_ring(), 0, QtCore.Qt.AlignVCenter)
        row.addStretch(1)
        row.setAlignment(self._soulwell_luck_col, QtCore.Qt.AlignVCenter)
        return row

    # --- the station's five slots ----------------------------------------
    def _soulwell_ring(self) -> _SlotRing:
        """The five slot faces on the ring, one per buff the sheet grants, in
        the sheet's own order — which is the game's: `constant.json`'s
        `Soulwell_Statuses.skills` array and `counter.json`'s row order agree on
        it (Legendary Weapon, Mount, Glider, Rare Material, Prismatic Gear).

        The order is NOT a scan result: the client bytecode never names one of
        these buffs (`ai/workspace/soulwell_offer/CONCLUSION.md`), so the sheets
        are the only order the game carries.
        """
        self._soulwell_ring_w = _SlotRing()
        self._soulwell_faces: list[_SlotFace] = []
        for i, buff in enumerate(soulwell_data.luck_buffs(), 1):
            face = _SlotFace(_BUFF_EMOJI.get(buff.counter_id or "",
                                             _BUFF_EMOJI_FALLBACK),
                             buff.label, i)
            face.changed.connect(self._soulwell_refresh_totals)
            self._soulwell_faces.append(face)
            self._soulwell_ring_w.add_face(face)
        return self._soulwell_ring_w

    # --- what each buff pays ------------------------------------------------
    def _soulwell_luck_table(self) -> QtWidgets.QVBoxLayout:
        rows = [(b.label, _chance_text(b.counter_id))
                for b in soulwell_data.luck_buffs()]
        return self._soulwell_table("LUCK PER BUFF", rows)

    def _soulwell_table(self, head: str,
                        rows: list[tuple[str, str]]) -> QtWidgets.QVBoxLayout:
        """One labeled table in the page's row style: a dim mono caption over
        alternating rows of a name and its value (the durations read GOLD, the
        same way the scrolls and food cards flag a timer).

        Both labels WRAP, which is what lets this table live in a side column:
        a label without wrapping reports its whole text as its minimum width,
        so the ring plus an unwrapped table becomes a hard floor on the card —
        wider than the app's own 1000px minimum window, where the table would
        then be clipped silently rather than wrapped. Wrapped, each column
        shrinks to its longest WORD and the rows stay single-line until the
        card is genuinely too narrow for them.
        """
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(2)
        cap = QtWidgets.QLabel(head)
        cap.setStyleSheet(
            f"color:{theme.DIM};{_MONO}font-size:12px;font-weight:700;"
            "letter-spacing:1px;")
        col.addWidget(cap)
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(3)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnStretch(1, 1)
        for r, (label, value) in enumerate(rows):
            bg = theme.with_alpha(theme.TEXT, 10) if r % 2 else "transparent"
            name = QtWidgets.QLabel(label)
            name.setWordWrap(True)
            name.setStyleSheet(
                f"color:{theme.TEXT};font-size:{_ROW_PX}px;background:{bg};")
            val = QtWidgets.QLabel(value)
            val.setWordWrap(True)
            val.setStyleSheet(
                f"color:{theme.GOLD};{_MONO}font-size:{_ROW_PX}px;"
                f"background:{bg};")
            grid.addWidget(name, r, 0)
            grid.addWidget(val, r, 1)
        col.addLayout(grid)
        return col

    # --- what the stack buys ---------------------------------------------
    def _soulwell_gift_row(self) -> QtWidgets.QHBoxLayout:
        """The unit rate and the stacked total in one line per rarity.

        Minutes ADD per gift and the reputation bonus lands once
        (`data.soulwell.offering_seconds`), so the total is whatever the five
        blocks hold (0..25) — the faces are the only counter, and every face
        reports here through `changed`, so the count, the lines and the
        fills cannot disagree. The rate and the total share the line
        (`_soulwell_gift_lines`) because a side table stating the same unit
        rates twice is what this section replaces: an empty station states
        the rates, a stacked one the arithmetic and what it comes to.
        """
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)
        cap = QtWidgets.QLabel("GIFTS STACKED")
        cap.setStyleSheet(
            f"color:{theme.DIM};{_MONO}font-size:12px;font-weight:700;"
            "letter-spacing:1px;")
        row.addWidget(cap)
        self._soulwell_total_lbl = QtWidgets.QLabel("0")
        self._soulwell_total_lbl.setStyleSheet(
            f"color:{theme.TEXT};{_MONO}font-size:17px;font-weight:800;")
        row.addWidget(self._soulwell_total_lbl)
        self._soulwell_clear = QtWidgets.QPushButton("Clear")
        self._soulwell_clear.setToolTip("Empty every block")
        self._soulwell_clear.setStyleSheet("padding: 4px 10px; font-weight: 700;")
        self._soulwell_clear.clicked.connect(self._soulwell_clear_stacks)
        row.addWidget(self._soulwell_clear)
        # the answer, then how it lands: two blocks rather than two more
        # columns, because this row already carries the caption, the total
        # and the rep-5 condition and is the widest thing on the card.
        # One rarity per LINE (see `_soulwell_gift_lines`): a wrapped label
        # in a nested layout is handed the width of its NEIGHBOUR, so left
        # to wrap the break lands wherever the font happens to put it — the
        # explicit newline is the same two rows on every machine, and
        # wrapping stays on only as the last resort for a card narrower
        # than one line of arithmetic
        readout = QtWidgets.QVBoxLayout()
        readout.setSpacing(1)
        self._soulwell_lines = QtWidgets.QLabel("")
        self._soulwell_lines.setWordWrap(True)
        self._soulwell_lines.setStyleSheet(
            f"color:{theme.GOLD};{_MONO}font-size:{_ROW_PX}px;font-weight:700;")
        readout.addWidget(self._soulwell_lines)
        self._soulwell_steps = QtWidgets.QLabel("")
        # the build-up can run long (one entry per stacked gift), so it
        # wraps like the lines above it rather than stretching the row
        self._soulwell_steps.setWordWrap(True)
        self._soulwell_steps.setStyleSheet(
            f"color:{theme.MUTED};{_MONO}font-size:12.5px;")
        readout.addWidget(self._soulwell_steps)
        row.addLayout(readout)
        # the readout above INCLUDES the reputation bonus, which the game only
        # grants at Riftstalkers reputation level 5 — so a player below it reads
        # 15 minutes more than their run will hold. Said here rather than as a
        # second total: the pair would be two numbers for one event, and the
        # stepper's own count is the number this row exists to answer.
        self._soulwell_bonus_note = QtWidgets.QLabel(self._bonus_note())
        self._soulwell_bonus_note.setStyleSheet(
            f"color:{theme.DIM};font-size:12.5px;")
        row.addWidget(self._soulwell_bonus_note)
        row.addStretch(1)
        # the readout opens on the empty station rather than an arbitrary fill
        self._soulwell_refresh_totals()
        return row

    def _soulwell_clear_stacks(self) -> None:
        """Empty every block — the planner's reset, not an offering."""
        self._soulwell_ring_w.clear()

    def _soulwell_stack_total(self) -> int:
        """Gifts stacked across the five blocks (0..25)."""
        return self._soulwell_ring_w.total()

    def _bonus_note(self) -> str:
        """What the totals row assumes about the player's reputation: the
        sheet's `Reputation_Duration_Bonus` minutes are granted at Riftstalkers
        reputation level 5 and not below it, so the readout is a ceiling.

        The number is read from the sheet, so a re-tuned bonus moves the note
        with it instead of leaving a stale constant behind."""
        bonus = soulwell_data.reputation_duration_bonus()
        return f"+{bonus} min of that needs Riftstalkers rep 5"

    def _soulwell_gift_lines(self, gifts: int) -> str:
        """The unit rate and the stacked total on one line per rarity.

        An empty station states what one gift is worth (`12m · 10 rep each`)
        — the rates the old PER GIFT side table carried, so they stay
        visible with nowhere stacked. A stacked station states the count
        times that rate, the reputation bonus ONCE, and what the two come
        to (`3 × 12m + 15m once = 51m · +30 rep`): the arithmetic and its
        answer on the same line instead of in two labels saying one thing.

        Every number is read from the sheet (`buff_duration_minutes`,
        `reputation_gain`, `reputation_duration_bonus`, `offering_seconds`),
        so a re-tuned gift moves the rate, the sum and the total together
        rather than leaving one behind. The count is the stepper's own, so
        the line moves with the fill: five lit slots read as five gifts'
        worth. Reputation lands per gift with no rep-5 condition on it —
        unlike the duration bonus, which the note beside this row calls out.
        """
        if gifts <= 0:
            return "\n".join(
                f"{name} {soulwell_data.buff_duration_minutes(rar)}m"
                f" · {soulwell_data.reputation_gain(rar)} rep each"
                for name, rar in (("Rare", "rare"), ("Epic", "epic")))
        bonus = soulwell_data.reputation_duration_bonus()
        # ONE LINE PER RARITY: the work and what it comes to, so the two
        # can never drift into disagreement the way two labels could
        return "\n".join(
            f"{name} {gifts} × {soulwell_data.buff_duration_minutes(rar)}m"
            f" + {bonus}m once"
            f" = {_duration_text(soulwell_data.offering_seconds(rar, gifts))}"
            f" · +{gifts * soulwell_data.reputation_gain(rar)} rep"
            for name, rar in (("Rare", "rare"), ("Epic", "epic")))

    def _soulwell_gift_steps(self, gifts: int) -> str:
        """The time landing gift by gift: the running total after each of
        the `gifts` stacked offerings, one line per rarity.

        The first gift carries the reputation bonus
        (`offering_seconds` adds it once), every later one adds only its
        rarity's minutes — so the steps part from the lines above them:
        the lines state the rule and its answer, the steps show the time
        landing (`27m → 39m → 51m …`). Read from the sheet through
        `offering_seconds`, so the lines above and these steps can never
        disagree about what a stack buys.
        """
        lines = []
        for name, rar in (("Rare", "rare"), ("Epic", "epic")):
            runs = [_duration_text(soulwell_data.offering_seconds(rar, k))
                    for k in range(1, gifts + 1)]
            lines.append(f"{name} {' → '.join(runs)}")
        return "\n".join(lines)

    def _soulwell_refresh_totals(self) -> None:
        """A stack moved: restate what the station's total buys.

        The number is restated NOW while each changed face fades to it, which
        is the one place the two are allowed to differ: the reading is what the
        user is about to act on, and the ring is the picture of it arriving —
        which is the whole reason the fill is animated at all. An empty station
        states the invitation instead of a zeroed sum.
        """
        gifts = self._soulwell_stack_total()
        self._soulwell_total_lbl.setText(str(gifts))
        self._soulwell_lines.setText(self._soulwell_gift_lines(gifts))
        if gifts <= 0:
            self._soulwell_steps.setText(
                "Click a block to stack gifts — up to "
                f"{_MAX_PER_SLOT} in each")
            return
        self._soulwell_steps.setText(self._soulwell_gift_steps(gifts))
