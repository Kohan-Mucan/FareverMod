"""The SOULWELL tab of the Items page (headless Qt, offscreen platform).

It is a tab in the Enchants strip now, not a page of its own, so these tests
cover two things the old page tests could not: that the station shows up as the
right tab of the right page, and that what it draws is the compact strip the
rebuild called for — five slot faces in a row, the sheet's numbers in the page's
own row style, and no live read anywhere.

The card is built standalone (`_Panel`) for the content tests and through the
real Items page for the wiring ones, so a break in either shows up here rather
than only on screen. What it must NOT do is read the game: the standalone build
runs against a model whose every attribute access raises.
"""
from __future__ import annotations

import math
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6 import QtCore, QtTest, QtWidgets  # noqa: E402

from farever_companion import paths  # noqa: E402
from farever_companion.data import soulwell as swd  # noqa: E402
from farever_companion.ui import theme  # noqa: E402
from farever_companion.ui.pages.items import ItemPageMixin  # noqa: E402
from farever_companion.ui.pages.items.soulwell import (  # noqa: E402
    _BUFF_EMOJI, _BUFF_EMOJI_FALLBACK, _FACE,
    _FILL_MS, _MAX_PER_SLOT, _RING, _SLOT_COUNT, SoulwellPanelMixin)


def _data_present() -> bool:
    try:
        return paths.item_drops_path().exists()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _data_present(),
    reason="requires bundled data (assets/data/item_drops.json)")


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _flush(app=None, n: int = 6) -> None:
    app = app or QtWidgets.QApplication.instance()
    for _ in range(n):
        app.processEvents()


class _ExplodingModel:
    """A model whose every read fails the test.

    Proof that the card reads nothing: `__getattr__` only runs for attributes
    the class does not define, which is every model member a UI could want.
    """

    def __getattr__(self, name):
        raise AssertionError(f"Soulwell tab read the game: model.{name}")


class _Panel(QtWidgets.QWidget, SoulwellPanelMixin):
    """The card on its own — no Items page, no Enchants machinery.

    `sheet=True` puts the REAL app sheet on this window, scoped to the widget
    (the pattern `tests/test_speedrun.py` uses) rather than through
    `theme.apply()`: that one registers the app fonts process-wide and sticky,
    so measuring with it would re-face every other module's layout assertions.
    The pixel check below needs the sheet, because the slots' fills are
    transparent-to-the-surface: on the offscreen platform's own white the same
    fill measures 1% of a luminance instead of the app's 35%.
    """

    def __init__(self, model=None, sheet: bool = False):
        super().__init__()
        self.model = model
        self.card = self._ench_soulwell_panel()
        QtWidgets.QVBoxLayout(self).addWidget(self.card)
        if sheet:
            self.setStyleSheet(theme.QSS)
        self.resize(1180, 740)
        self.show()
        _flush()


def _panel(model=None, sheet: bool = False) -> _Panel:
    return _Panel(model, sheet)


class _Page(QtWidgets.QWidget, ItemPageMixin):
    """The real Items page, the way tests/test_enchants_tab.py builds it."""

    def _page_container(self, title=None):
        page = QtWidgets.QWidget()
        return page, QtWidgets.QVBoxLayout(page)

    def _codex_jump_to_unit(self, *args, **kwargs):
        return None


def _items_page() -> _Page:
    p = _Page()
    page = p._page_gear()
    QtWidgets.QVBoxLayout(p).addWidget(page)
    p.show()
    p._items_set_mode("Enchants")
    _flush()
    return p


def _texts(w) -> str:
    return " ".join(lb.text() for lb in w.findChildren(QtWidgets.QLabel))


def _face_ink(img, face, card) -> float:
    """Mean luminance of a slot's INNER area — its glyph and its name, without
    the border — so the reading is what the eye sees inside the cell.

    Luminance rather than a colour comparison, because a slot is two lines of
    text and an emoji over a tint: the question is "is this one darker?", which
    only the painted pixels answer.
    """
    tl = face.mapTo(card, QtCore.QPoint(6, 6))
    tot = n = 0
    for y in range(tl.y(), tl.y() + face.height() - 12):
        for x in range(tl.x(), tl.x() + face.width() - 12):
            c = img.pixelColor(x, y)
            tot += 0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()
            n += 1
    return tot / max(1, n)


def _face_bg(img, face, card) -> str:
    """The colour a slot's face paints just inside its left border: its own
    tint when filled, whatever surface shows through when empty."""
    tl = face.mapTo(card, QtCore.QPoint(0, 0))
    return img.pixelColor(tl.x() + 4, tl.y() + face.height() // 2).name()


def _beside(card, ring, x_from: int, x_to: int):
    """(top, bottom, label) for every label in that band that is LEVEL with the
    ring — i.e. exactly the table on that side of it.

    The ring's own labels are skipped (they are inside it, not beside it), and
    so is anything outside the ring's vertical span: the card header above it
    and the note below. Without those two filters the "column" would be every
    label on the card whose x happens to be on the left, which is how a test
    like this ends up asserting nothing about the arrangement.
    """
    top = ring.mapTo(card, QtCore.QPoint(0, 0)).y()
    bottom = top + ring.height()
    out = []
    for lb in card.findChildren(QtWidgets.QLabel):
        if not lb.text() or not lb.isVisible() or ring.isAncestorOf(lb):
            continue
        pt = lb.mapTo(card, QtCore.QPoint(0, 0))
        if pt.x() < x_from or pt.x() + lb.width() > x_to:
            continue
        if pt.y() >= bottom or pt.y() + lb.height() <= top:
            continue
        out.append((pt.y(), pt.y() + lb.height(), lb))
    return out


def _squeezed(card, ring):
    """Labels the card has squeezed past a WORD of their own text.

    A wrapping label cannot go below its longest word, so a column narrower than
    that is a label cut mid-word with nothing to say so — the one failure a
    layout this wide can have that no text census sees. The ring's own labels
    are excluded: the faces are a fixed 124px by design and their names are
    checked against their own geometry by the face tests.
    """
    out = []
    for lb in card.findChildren(QtWidgets.QLabel):
        if not lb.text() or not lb.isVisible() or ring.isAncestorOf(lb):
            continue
        widest = max((lb.fontMetrics().horizontalAdvance(w)
                      for w in lb.text().split()), default=0)
        if lb.width() < widest:
            out.append((lb.text()[:30], lb.width(), widest))
    return out


def _chance_text(counter_id: str) -> str:
    """The chance string the card must show for one counter, derived from the
    sheet — the same rule the tab uses, so a re-tuned sheet moves both."""
    base = swd.luck_chance(counter_id, 0)
    cap = swd.luck_chance(counter_id, 10_000)
    if abs(cap - base) < 1e-9:
        return f"{base * 100:.1f}%"
    return f"{base * 100:.1f}% → {cap * 100:.1f}%"


# --- it is a tab of the Items page ----------------------------------------
def test_the_station_is_a_tab_of_the_items_page_enchants_strip():
    """The station moved here from its own nav page: it is one more card in the
    Enchants strip, and the strip — not the card — decides when it shows."""
    p = _items_page()
    try:
        tabs = p._ench_tabs
        assert "Soulwell" in tabs._btns, list(tabs._btns)
        assert not p._ench_soulwell_card.isVisible(), (
            "the station card shows on a tab that is not its own")
        assert p._ench_gems_card.isVisible()

        tabs._btns["Soulwell"].click()
        _flush()
        assert tabs.currentText() == "Soulwell"
        assert p._ench_soulwell_card.isVisible()
        assert not p._ench_gems_card.isVisible()
        assert not p._ench_scrolls_card.isVisible()

        tabs._btns["Gems"].click()
        _flush()
        assert not p._ench_soulwell_card.isVisible()
        assert p._ench_gems_card.isVisible()
    finally:
        p.deleteLater()


def test_the_station_standalone_nav_page_is_gone():
    """No page of its own any more: the nav entry, the page builder and the
    mixin that built it are all removed, so the tab is the only way in."""
    from farever_companion.ui.control_panel import ControlPanel
    from farever_companion.ui.nav_registry import NAV

    keys = [row[0] for row in NAV]
    assert "soulwell" not in keys, keys
    assert "soulwell" not in ControlPanel._PAGE_BUILDERS
    assert not hasattr(ControlPanel, "_page_soulwell")
    assert not os.path.exists(os.path.join(
        os.path.dirname(__file__), "..", "farever_companion", "ui", "pages",
        "soulwell.py")), "the old page module is still on disk"


# --- the strip ------------------------------------------------------------
def test_the_ring_has_one_face_per_luck_buff_in_the_games_order():
    """Five faces on a RING, one per buff the sheet grants, in the game's own
    order — slot 1 at the top and the rest clockwise from it.

    The order and the arrangement are separate claims, so both are checked: the
    labels come back in `luck_buffs()` order (the constant sheet's
    `Soulwell_Statuses` array, which agrees with `counter.json`'s row order and
    is the only order the game carries — the client bytecode never names one of
    these buffs), and the GEOMETRY puts them around the circle in that order
    rather than on a line. A sheet that grants a sixth buff is red either way:
    the station has five slots.
    """
    buffs = swd.luck_buffs()
    assert len(buffs) == _SLOT_COUNT == 5
    p = _panel()
    try:
        faces = p._soulwell_faces
        assert [f._name.text() for f in faces] == [b.label for b in buffs]
        assert [f._icon.text() for f in faces] == [
            _BUFF_EMOJI[b.counter_id] for b in buffs]
        assert [f.index for f in faces] == [1, 2, 3, 4, 5], (
            "the faces lost the index that says where the game puts them")
        assert all((f.width(), f.height()) == (_FACE, _FACE) for f in faces)

        ring = p._soulwell_ring_w
        assert (ring.width(), ring.height()) == (_RING, _RING)
        cx = cy = _RING / 2.0
        centres = [(f.x() + f.width() / 2.0, f.y() + f.height() / 2.0)
                   for f in faces]
        # one circle: every face the same distance from the centre
        radii = [math.hypot(x - cx, y - cy) for x, y in centres]
        assert max(radii) - min(radii) < 1.5, radii
        assert min(radii) > _FACE / 2.0, "a face sits on the centre"
        # slot 1 at the top, then clockwise in sheet order
        assert centres[0][1] == min(y for _x, y in centres)
        assert abs(centres[0][0] - cx) <= 1
        angs = [math.degrees(math.atan2(y - cy, x - cx)) for x, y in centres]
        assert sorted(range(len(faces)), key=lambda i: (angs[i] + 450) % 360) \
            == list(range(len(faces))), angs
        # and no two faces touch — 88px squares on a 118px radius leave 24px of
        # air, so a face that grew (or a ring that shrank) shows up here rather
        # than as two overlapping slots on screen
        for i in range(len(faces)):
            for j in range(i + 1, len(faces)):
                assert not faces[i].geometry().intersects(faces[j].geometry()), (
                    faces[i]._name.text(), faces[j]._name.text())
    finally:
        p.deleteLater()


def _style_px(w):
    """The font size a widget's own stylesheet declares, in px, or None when it
    declares none (a widget styled by the app's QSS or a parent).

    The DECLARED size is what makes the checks below portable: measured font
    metrics move with whatever font the machine resolves — the app's own
    'Roboto Condensed' is missing on a dev box, where every glyph comes back
    full-width — so a budget built on metrics measures the fallback, not the app.
    """
    for chunk in w.styleSheet().split(";"):
        if chunk.strip().startswith("font-size:"):
            return float(chunk.split(":", 1)[1].strip().removesuffix("px"))
    return None


def test_a_face_holds_its_glyph_and_its_name():
    """The face is a fixed square, so BOTH of its lines have to fit inside
    it: a 25px glyph and up to two 13px name lines, plus the layout's margins
    and spacing. The old third line (the counter's scope — 'any item' where
    the sheet scopes it to nothing) is gone: the tile is a stack control, and
    the ×n badge is the info it shows when gifts land on it.

    Two checks, because each misses what the other catches: the DECLARED sizes
    against the cell (an emoji's measured box is taller than its font size and
    moves with the platform's font, so a hint-based budget is a flaky test —
    which is how the 62px face passed alone and failed in the full suite), and
    the REAL laid-out labels against their own wrapped line count, which catches
    a squeeze the arithmetic cannot see.
    """
    p = _panel()
    try:
        face = p._soulwell_faces[0]
        glyph, name = _style_px(face._icon), _style_px(face._name)
        assert (glyph, name) == (25, 13)
        assert not hasattr(face, "_scope"), \
            "the scope line is gone — the face is glyph, name and count"
        assert _FACE >= (round(glyph * 1.25) + 2 * round(name * 1.3) + 11), (
            f"a {_FACE}px face cannot hold a {glyph}px glyph and two {name}px "
            f"name lines")
        # every label that declares a font size must be at least that tall on
        # screen — a shorter box is a clipped line. Declared px, not metrics, so
        # whichever font the machine resolves cannot change the verdict.
        checked = 0
        for w in p.card.findChildren(QtWidgets.QLabel):
            px = _style_px(w)
            if not w.text() or not w.isVisible() or px is None:
                continue
            checked += 1
            assert w.height() >= px, (w.text()[:40], w.height(), px)
        assert checked >= 10, checked       # the faces' two labels each alone
        # the WRAPPED name fits what it actually wraps to: Qt gives a label
        # `fm.height()` for its first line and `lineSpacing()` for each EXTRA
        # one, so that — not `lines * lineSpacing()`, which demands a whole
        # leading from a single line — is what the allocated height must cover.
        # On this box the widest font it resolves wraps 'Legendary Weapon' to
        # two lines: 31 (glyph) + 34 (name) + the layout's 11 = 76 of the
        # face's 124, room to spare.
        fm = face._name.fontMetrics()
        lines = math.ceil(
            fm.horizontalAdvance(face._name.text()) / face._name.width())
        need = fm.height() + (lines - 1) * fm.lineSpacing()
        assert face._name.height() >= need, \
            (face._name.text(), face._name.height(), need, lines)
        # the emoji is not clipped by its own label: the box it is given is the
        # glyph box an emoji resolves to, not the font's own height
        assert face._icon.height() >= round(glyph * 1.25), (
            face._icon.height(), glyph)
    finally:
        p.deleteLater()


def test_every_luck_buff_has_an_emoji_of_its_own():
    """The glyph table is keyed by the SHEET's counter ids and covers exactly
    the buffs the sheet grants, so a re-tuned sheet — a buff added, a counter
    renamed — is a red test rather than a face wearing the wrong glyph.

    Which glyph a buff wears is the app's pick (presentation, so nothing derives
    it), and that is exactly why it is pinned against the sheet instead: the
    keys must track the game's counters, and no two buffs may share a glyph or
    the faces would stop telling them apart.
    """
    counters = {b.counter_id for b in swd.luck_buffs()}
    assert counters == set(_BUFF_EMOJI), (
        "the glyph table and the sheet's buffs have drifted apart: "
        f"sheet-only={sorted(counters - set(_BUFF_EMOJI))} "
        f"table-only={sorted(set(_BUFF_EMOJI) - counters)}")
    assert len(set(_BUFF_EMOJI.values())) == len(_BUFF_EMOJI), (
        "two buffs share a glyph, so the faces would not say which is which")
    assert _BUFF_EMOJI_FALLBACK
    assert _BUFF_EMOJI_FALLBACK not in _BUFF_EMOJI.values()


# --- the numbers ----------------------------------------------------------
def test_the_sheet_numbers_are_on_the_card():
    """The sheet's own numbers: the merged lines state each gift's rate
    with nowhere stacked (a Rare gift is 12 minutes and 10 reputation,
    an Epic 24 and 20), and each of the five luck counters prints its
    chance as the sheet's base -> cap (a flat counter prints a single
    value — no '5.0% → 5.0%')."""
    p = _panel()
    try:
        texts = _texts(p.card)
        assert "LUCK PER BUFF" in texts
        assert "PER GIFT" not in texts, "the merged lines replaced that table"
        assert p._soulwell_lines.text() == \
            "Rare 12m · 10 rep each\nEpic 24m · 20 rep each"
        for buff in swd.luck_buffs():
            assert buff.label in texts
            assert _chance_text(buff.counter_id) in texts, buff.label
        # the numbers the tab prints are the sheet's, not a copy of them
        assert swd.buff_duration_minutes("rare") == 12
        assert swd.buff_duration_minutes("epic") == 24
        assert swd.reputation_duration_bonus() == 15
        assert swd.reputation_gain("rare") == 10
        assert swd.reputation_gain("epic") == 20
    finally:
        p.deleteLater()


def test_the_bonus_note_says_the_readout_needs_rep_5():
    """The merged lines are a CEILING and say so: the sheet's
    `Reputation_Duration_Bonus` minutes are granted at Riftstalkers reputation
    level 5 and not below it, so the readout beside the stepper carries that
    condition instead of a second, lower total — two numbers for one event, one
    of which a rep-5 player never sees.

    The note is read off the sheet, and the bonus it explains is stated
    once per merged line (`+15m once`), so a re-tuned bonus moves both
    rather than leaving a stale "+15" on the card.
    """
    p = _panel()
    try:
        bonus = swd.reputation_duration_bonus()
        note = p._soulwell_bonus_note.text()
        assert f"+{bonus} min" in note and "rep 5" in note, note
        texts = _texts(p.card)
        assert note in texts
        # one gift per block: five gifts buy what the old stepper opened on
        for face in p._soulwell_faces:
            face.set_count(1, animate=False)
        lines = p._soulwell_lines.text()
        assert (f"Rare 5 × 12m + {bonus}m once = 1h 15m · +50 rep"
                in lines), lines
        assert (f"Epic 5 × 24m + {bonus}m once = 2h 15m · +100 rep"
                in lines), lines
    finally:
        p.deleteLater()


def test_the_card_is_compact():
    """The complaint the rebuild answers: the old page was a 380px-minimum ring
    with the rest of the surface empty. The ring is back (it is the game's
    arrangement), but it is a block inside a card whose height is now the RING's
    height — the luck table sits beside it instead of under it, and the card
    is one header, one ring, one stepper row and one note.
    """
    p = _panel()
    try:
        hint = p.card.sizeHint()
        # Measured on this box: 451px natural height (ring 360 + a header, the
        # stepper row and the note) and 718px when a window forces it taller.
        # The budget is the ring plus 160 rather than the measured 91 so that a
        # taller fallback font still passes — and it is deliberately below the
        # ~600px a STACKED card wants (ring + header + tables + stepper + note),
        # because putting the tables back under the ring is the regression this
        # arrangement exists to prevent.
        assert hint.height() <= _RING + 160, (
            f"the Soulwell card wants {hint.height()}px at its natural size — "
            f"more than its {_RING}px ring plus one stepper row and a note, "
            f"which means the tables are stacking again")
        assert p.card.width() <= 1180
    finally:
        p.deleteLater()


def test_the_luck_table_sits_beside_the_ring_and_nothing_else_does():
    """The arrangement the card ships, read off the LAID-OUT widgets.

    LUCK PER BUFF sits left of the ring — one row per face, an annotation on
    the picture beside it — and nothing sits right of it: what a gift is
    worth merged into the GIFTS lines below, so a second side table would
    state the same unit rates twice. A text census cannot see this: the
    caption is on the card either way. The readout stays BELOW the ring,
    because that row (stepper + lines + the rep-5 condition) is the first
    thing to squeeze in a side column.
    """
    p = _panel()
    try:
        ring = p._soulwell_ring_w
        top = ring.mapTo(p.card, QtCore.QPoint(0, 0)).y()
        bottom = top + ring.height()
        mid = top + ring.height() // 2
        left_x = ring.mapTo(p.card, QtCore.QPoint(0, 0)).x()
        right_x = left_x + ring.width()

        left_col = _beside(p.card, ring, 0, left_x)
        assert [lb.text() for _a, _b, lb in left_col].count("LUCK PER BUFF") == 1
        assert _beside(p.card, ring, right_x, p.card.width()) == [], \
            "a second side table is back beside the ring"
        # the table rides with the ring: beside it, top to bottom, level
        # with its MIDDLE rather than pinned to its top edge
        tops = [t for t, _b, _lb in left_col]
        bots = [b for _t, b, _lb in left_col]
        assert min(tops) >= top and max(bots) <= bottom, (
            min(tops), max(bots), (top, bottom))
        assert min(tops) < mid < max(bots), (min(tops), mid, max(bots))
        total = p._soulwell_total_lbl.mapTo(p.card, QtCore.QPoint(0, 0))
        assert total.y() >= bottom, "the readout is not below the ring"
    finally:
        p.deleteLater()


def test_the_side_columns_squeeze_rather_than_clip_at_the_minimum_window():
    """The card has to survive the app's own smallest window (ControlPanel sets
    1000x640 minimum), where the ring plus its table is wider than the space
    they get: a label with no wrapping reports its whole text as a MINIMUM, so
    the column would be cut off mid-word with nothing to say so. Wrapped, a
    squeezed column shrinks to its longest word and its rows go to two lines,
    which is the trade this arrangement makes (measured: at 1000px the table
    keeps its column and no label is cut).
    """
    p = _panel()
    try:
        p.resize(1000, 640)              # ControlPanel.setMinimumSize(1000, 640)
        for face in p._soulwell_faces:
            face.set_count(1, animate=False)
        _flush()
        # the merged lines are the newest thing on that row, and the one that
        # could push the row wider than the card
        assert p._soulwell_lines.text().count(chr(10)) == 1, "one line per rarity"
        ring = p._soulwell_ring_w
        left_x = ring.mapTo(p.card, QtCore.QPoint(0, 0)).x()
        col = _beside(p.card, ring, 0, left_x)
        assert col, "the LUCK PER BUFF table is not beside the ring at 1000px"
        # nothing ANYWHERE on the card is cut mid-word — the side table,
        # and the readout row under it, which is the widest row on the card
        # (caption + stepper + two merged lines + the note)
        assert not _squeezed(p.card, ring), _squeezed(p.card, ring)
    finally:
        p.deleteLater()


# --- the stacked count ----------------------------------------------------
def test_the_station_opens_empty_and_counts_every_stack():
    """The planner opens on an empty station — no gifts stacked, nothing
    implied — and the total is whatever the five blocks hold: each block stacks
    up to five, so the ceiling is twenty-five, not five.
    """
    p = _panel()
    try:
        assert p._soulwell_stack_total() == 0
        assert p._soulwell_total_lbl.text() == "0"
        # nowhere stacked, so the lines state the unit rates instead of a
        # zeroed sum — the same rates the old side table carried
        assert p._soulwell_lines.text() == \
            "Rare 12m · 10 rep each\nEpic 24m · 20 rep each"
        assert [f.count for f in p._soulwell_faces] == [0] * _SLOT_COUNT
        assert [f.filled for f in p._soulwell_faces] == [False] * _SLOT_COUNT
        assert _MAX_PER_SLOT == 5
        assert p._soulwell_stack_total() <= _SLOT_COUNT * _MAX_PER_SLOT
    finally:
        p.deleteLater()


def test_the_merged_lines_state_the_rate_and_what_the_stack_comes_to():
    """One line per rarity carries the WORK and its answer: the count times
    what ONE gift adds, the reputation bonus ONCE, what the buff time comes
    to, and the reputation the stack earns.

    Two things make it worth pinning. Every number has to be the sheet's own
    — so each half is checked against `data.soulwell` rather than against
    the literal the code builds, and a re-tuned gift moves the rate, the sum
    and the answer together instead of leaving a hard-coded copy of today's
    numbers behind. And the lines have to MOVE with the stepper: the point of
    showing them at all is that a lit slot explains the number beside it,
    which a line reading '5 × 12m' under a stepper showing 3 does not do. The
    time answer is also checked against `offering_seconds`, the function the
    line reads it from, so the rule and its answer cannot drift apart.
    """
    p = _panel()
    try:
        faces, lines_lb = p._soulwell_faces, p._soulwell_lines
        bonus = swd.reputation_duration_bonus()
        # spread across blocks: 2 + 2 + 1 — the total is what matters, not
        # which block holds what
        for gifts, dist in ((5, (2, 2, 1, 0, 0)), (3, (3, 0, 0, 0, 0)),
                            (1, (0, 0, 0, 0, 1))):
            for face, n in zip(faces, dist):
                face.set_count(n, animate=False)
            assert p._soulwell_stack_total() == gifts, dist
            for name, rar in (("Rare", "rare"), ("Epic", "epic")):
                per_gift = swd.buff_duration_minutes(rar)
                gain = swd.reputation_gain(rar)
                assert (f"{name} {gifts} × {per_gift}m + {bonus}m once = "
                        in lines_lb.text()), lines_lb.text()
                assert f"+{gifts * gain} rep" in lines_lb.text()
                # the arithmetic ADDS UP to the answer on the same line
                assert swd.offering_seconds(rar, gifts) == \
                    (gifts * per_gift + bonus) * 60, (rar, gifts)
        for face in faces:
            face.set_count(1, animate=False)
        assert ("Rare 5 × 12m + 15m once = 1h 15m · +50 rep"
                in lines_lb.text()), lines_lb.text()
        # the bonus is one-off per rarity, never multiplied by the count
        assert lines_lb.text().count("once") == 2, lines_lb.text()
    finally:
        p.deleteLater()


def test_the_merged_lines_carry_what_the_stack_earns():
    """The lines answer what the stack EARNS, not just how long it lasts:
    reputation lands per gift, with no rep-5 condition on it (unlike the
    duration bonus the note already calls out) — and clearing the station
    puts the unit rates back.

    Both halves come from the sheet's `reputation_gain`, so a re-tuned gift
    moves the readout with it.
    """
    p = _panel()
    try:
        faces = p._soulwell_faces
        for gifts, dist in ((5, (2, 2, 1, 0, 0)), (3, (3, 0, 0, 0, 0)),
                            (1, (0, 0, 0, 0, 1))):
            for face, n in zip(faces, dist):
                face.set_count(n, animate=False)
            for name, rar in (("Rare", "rare"), ("Epic", "epic")):
                assert (f"+{gifts * swd.reputation_gain(rar)} rep"
                        in p._soulwell_lines.text()), p._soulwell_lines.text()
        assert swd.reputation_gain("rare") == 10
        assert swd.reputation_gain("epic") == 20
        assert ("Epic 1 × 24m + 15m once = 39m · +20 rep"
                in p._soulwell_lines.text())
        p._soulwell_clear.click()
        assert p._soulwell_lines.text() == \
            "Rare 12m · 10 rep each\nEpic 24m · 20 rep each"
    finally:
        p.deleteLater()


def test_stacking_shows_the_time_landing_gift_by_gift():
    """The readout shows the build-up, not just the finished stack: the
    running total after each stacked offering, one line per rarity.

    The first gift carries the reputation bonus once and every later one
    adds only its rarity's minutes (`offering_seconds`), so the steps
    agree with the merged lines above them by construction — both read
    the same function. Empty shows the hint rather than a zeroed run."""
    p = _panel()
    try:
        # nowhere stacked, the rates state the worth and the steps carry
        # the invitation instead of a zeroed run
        assert "Click a block to stack gifts" in p._soulwell_steps.text()
        faces = p._soulwell_faces
        for face, n in zip(faces, (1, 1, 1, 0, 0)):
            face.set_count(n, animate=False)
        steps = p._soulwell_steps.text()
        assert "Rare 27m → 39m → 51m" in steps, steps
        assert "Epic 39m → 1h 03m → 1h 27m" in steps, steps
        # every step after the first adds exactly one gift's minutes
        rare = swd.buff_duration_minutes("rare") * 60
        assert (swd.offering_seconds("rare", 3)
                - swd.offering_seconds("rare", 2)) == rare
        p._soulwell_clear.click()
        assert "Click a block to stack gifts" in p._soulwell_steps.text()
    finally:
        p.deleteLater()


def test_each_block_stacks_up_to_five_and_lights_its_own_face():
    """Every block stacks its own gifts: a block holding any lights only its
    own face, and the lit/unlit looks must actually differ on screen, or the
    fill says nothing.
    """
    p = _panel()
    try:
        faces = p._soulwell_faces
        assert [f.count for f in faces] == [0] * _SLOT_COUNT
        faces[0].set_count(3, animate=False)
        faces[2].set_count(_MAX_PER_SLOT, animate=False)
        assert [f.count for f in faces] == [3, 0, 5, 0, 0]
        assert [f.filled for f in faces] == [True, False, True, False, False]
        assert p._soulwell_stack_total() == 8
        assert p._soulwell_total_lbl.text() == "8"
        # clamping: no more than five in one block, no fewer than none
        faces[2].set_count(99, animate=False)
        faces[1].set_count(-4, animate=False)
        assert faces[2].count == _MAX_PER_SLOT
        assert faces[1].count == 0
        # the two looks are different, and each carries its own edge colour.
        # Read after the fill has settled: the tint FADES to the new state
        # (see `test_the_fill_fades_to_...`), so a sheet read mid-fade is
        # neither look — which is exactly what the fade is.
        p._soulwell_ring_w.settle()
        lit, dark = faces[0], faces[1]
        assert lit.styleSheet() != dark.styleSheet()
        assert theme.ACCENT_BORDER in lit.styleSheet()
        assert theme.BORDER in dark.styleSheet()
        assert theme.TEXT in lit._name.styleSheet()
        assert theme.DIM in dark._name.styleSheet()
        # the count badge rides on the stacked face only
        assert faces[0]._count_badge.isVisible()
        assert faces[0]._count_badge.text() == "×3"
        assert not faces[1]._count_badge.isVisible()
    finally:
        p.deleteLater()


def test_clicking_a_block_stacks_one_gift_in_it():
    """The picture IS the counter: left-click stacks one gift in that block,
    right-click takes one back off, and everything hangs off the faces — the
    total, the fill, the buff time and the arithmetic.

    Checked through the panel total (the interface a click has to reach), so a
    click that painted its own face without moving the count would be red even
    though the ring looked right.
    """
    p = _panel()
    try:
        faces = p._soulwell_faces
        assert p._soulwell_stack_total() == 0
        QtTest.QTest.mouseClick(faces[2], QtCore.Qt.LeftButton)
        QtTest.QTest.mouseClick(faces[2], QtCore.Qt.LeftButton)
        QtTest.QTest.mouseClick(faces[0], QtCore.Qt.LeftButton)
        assert [f.count for f in faces] == [1, 0, 2, 0, 0]
        assert p._soulwell_stack_total() == 3
        assert ("Rare 3 × 12m + 15m once = 51m · +30 rep"
                in p._soulwell_lines.text())
        # right-click takes one back off the same block
        QtTest.QTest.mouseClick(faces[2], QtCore.Qt.RightButton)
        assert [f.count for f in faces] == [1, 0, 1, 0, 0]
        assert ("Rare 2 × 12m + 15m once = 39m · +20 rep"
                in p._soulwell_lines.text())
        # a full block wraps to empty — the misclick's own undo
        faces[4].set_count(_MAX_PER_SLOT, animate=False)
        QtTest.QTest.mouseClick(faces[4], QtCore.Qt.LeftButton)
        assert faces[4].count == 0
        # Clear empties every block at once
        p._soulwell_clear.click()
        assert [f.count for f in faces] == [0] * _SLOT_COUNT
        assert p._soulwell_stack_total() == 0
        assert p._soulwell_lines.text() == \
            "Rare 12m · 10 rep each\nEpic 24m · 20 rep each"
    finally:
        p.deleteLater()


def test_a_slot_is_a_click_target_and_not_another_button():
    """Clickable is an affordance, not a new button.

    The card's standing contract is that Clear is the ONLY push button on it —
    the station's one action is the player's to make, and this app never offers
    anything — and that survives: the faces stay frames, with the two things
    that say "pressable" (a pointing-hand cursor and an edge that brightens
    under the pointer). The decoration over each face is transparent to the
    mouse, which is what makes the whole tile the target rather than only the
    few pixels of bare frame between the labels.
    """
    p = _panel()
    try:
        assert set(p.card.findChildren(QtWidgets.QPushButton)) == \
            {p._soulwell_clear}
        for face in p._soulwell_faces:
            assert face.cursor().shape() == QtCore.Qt.PointingHandCursor
            assert "QFrame#SoulwellFace:hover" in face.styleSheet()
            tip = face.toolTip().lower()
            assert "click to add" in tip and "right-click" in tip, tip
            assert str(face.index) in tip, tip
            for lb in (face._icon, face._name, face._mark,
                       face._count_badge):
                assert lb.testAttribute(QtCore.Qt.WA_TransparentForMouseEvents), \
                    f"{lb.text()!r} would swallow a click meant for slot {face.index}"
            # …and Qt's own hit-test agrees about what sits under the pointer,
            # which is the half the click test above cannot see (it hands the
            # event straight to the face)
            under = p.card.childAt(face.mapTo(p.card, face.rect().center()))
            assert under is face, (
                f"a click at slot {face.index}'s centre lands on "
                f"{type(under).__name__}, not the face")
    finally:
        p.deleteLater()


def test_the_fill_reads_on_screen_and_not_only_in_the_stylesheet():
    """The picture and the number must agree where a player looks: on screen.

    A stylesheet STRING is not evidence — two slots with different sheets can
    paint identically (a property Qt ignores, a rule an ancestor sheet wins),
    and the fill itself is a tint over the surface, so measured without the app
    sheet behind it the same two slots came back 1% apart instead of 35%. So
    this reads the PAINTED pixels under the real sheet: at three gifts the
    three filled slots are each measurably brighter than both empty ones, by a
    margin wide enough that a fill which stops showing up is red rather than
    merely different (measured 50.7 vs 32.7, i.e. 1.55x, when this was written).
    """
    p = _panel(sheet=True)
    try:
        faces = p._soulwell_faces
        for face in faces[:3]:
            face.set_count(2, animate=False)
        p._soulwell_ring_w.settle()      # the fade is not what is measured here
        _flush()
        img = p.card.grab().toImage()
        ink = [_face_ink(img, f, p.card) for f in faces]
        bg = [_face_bg(img, f, p.card) for f in faces]
        assert all(v > 12 for v in ink), ink      # a blank grab proves nothing
        lit, dark = ink[:3], ink[3:]
        assert min(lit) > max(dark), (ink, "a filled slot is not the brighter one")
        assert sum(lit) / 3 >= 1.25 * (sum(dark) / 2), ink
        # and the two looks come from different paint, not a different string:
        # a filled slot wears the accent tint, an empty one shows the surface
        assert bg[3] == bg[4] == theme.SURFACE, bg
        assert bg[0] == bg[1] == bg[2] != theme.SURFACE, bg
    finally:
        p.deleteLater()


def test_the_fill_fades_to_the_new_state_instead_of_snapping_to_it():
    """A stepper move MOVES the picture.

    The STATE lands on the click — `filled` is already False the instant the
    stepper drops, so the number and the picture never disagree about what is in
    the station — while the LOOK travels there over `_FILL_MS`: at the moment of
    the click the face is still wearing the filled tint, part way it is wearing
    neither, and it arrives on its own rather than being pushed.

    The mid-fade sample is taken by seeking the animation rather than sleeping
    for half of it, so the assertion is the same on a fast box as on a starved
    one; the landing is waited for for real, because that is the part whose
    failure (a fade that never finishes) would leave a slot stuck between the
    two looks.
    """
    p = _panel()
    try:
        faces = p._soulwell_faces
        emptying, still_lit = faces[-1], faces[-2]
        still_lit.set_count(2, animate=False)
        emptying.set_count(1, animate=False)
        p._soulwell_ring_w.settle()
        assert (emptying.filled, emptying.fill_t) == (True, 1.0)

        emptying.set_count(0)
        assert emptying.filled is False, "the state waits for the fade"
        assert emptying.fill_t == 1.0, emptying.fill_t
        assert emptying._anim.state() == QtCore.QAbstractAnimation.State.Running

        emptying._anim.pause()
        emptying._anim.setCurrentTime(_FILL_MS // 2)
        assert 0.0 < emptying.fill_t < 1.0, emptying.fill_t
        assert theme.with_alpha(theme.ACCENT, 30) not in emptying.styleSheet()
        assert theme.BORDER not in emptying.styleSheet()

        emptying._anim.resume()
        QtTest.QTest.qWait(_FILL_MS + 80)
        assert emptying.fill_t == 0.0, "the fade never landed"
        assert theme.BORDER in emptying.styleSheet()
        assert theme.DIM in emptying._name.styleSheet()
        assert still_lit.fill_t == 1.0          # an untouched slot never moved

        # and the other direction, with several slots changing at once
        for face in faces:
            face.set_count(1)
        QtTest.QTest.qWait(_FILL_MS + 80)
        assert [f.fill_t for f in faces] == [1.0] * _SLOT_COUNT
    finally:
        p.deleteLater()


def test_a_second_click_mid_fade_carries_on_from_the_tint_on_screen():
    """Interrupting a fade does not snap it.

    Clicking − then + quickly is one gesture from the user's side, so the face
    it turns around must pick up from the tint that is on screen — restarting
    from the far end would blink the slot through a state it never reached.
    """
    p = _panel()
    try:
        faces = p._soulwell_faces
        emptying = faces[-1]
        emptying.set_count(1, animate=False)
        p._soulwell_ring_w.settle()
        emptying.set_count(0)
        emptying._anim.pause()
        emptying._anim.setCurrentTime(_FILL_MS // 2)
        mid = emptying.fill_t
        assert 0.0 < mid < 1.0, mid

        emptying.set_count(2)                    # the user changes their mind
        assert emptying.filled is True
        assert float(emptying._anim.startValue()) == mid, (
            "the fade restarted from the far end instead of from the tint")
        QtTest.QTest.qWait(_FILL_MS + 80)
        assert emptying.fill_t == 1.0
        assert theme.ACCENT_BORDER in emptying.styleSheet()
    finally:
        p.deleteLater()


def test_opening_the_tab_sets_the_ring_instead_of_fading_it_in():
    """Opening the card is not an event.

    The ring is drawn at the stepper's value (every slot filled) rather than
    fading up from an empty station: motion on a click the user did not make
    reads as the app doing something, and the first thing a visitor sees should
    not be a station that looks empty for a sixth of a second.
    """
    p = _panel()
    try:
        assert [f.count for f in p._soulwell_faces] == [0] * _SLOT_COUNT
        assert [f.fill_t for f in p._soulwell_faces] == [0.0] * _SLOT_COUNT
        assert all(f._anim.state() == QtCore.QAbstractAnimation.State.Stopped
                   for f in p._soulwell_faces)
    finally:
        p.deleteLater()


def test_stacking_up_shows_what_more_gifts_are_worth():
    """One gift is the sheet's minute plus the single bonus — 1620s and 2340s,
    the two durations the live log recorded — and each gift stacked removes or
    adds exactly one gift's minutes, never the bonus."""
    p = _panel()
    try:
        faces = p._soulwell_faces
        faces[0].set_count(1, animate=False)
        assert ("Rare 1 × 12m + 15m once = 27m · +10 rep"
                in p._soulwell_lines.text())
        assert swd.offering_seconds("rare", 1) == 1620
        assert swd.offering_seconds("epic", 1) == 2340

        faces[1].set_count(1, animate=False)
        assert ("Rare 2 × 12m + 15m once = 39m · +20 rep"
                in p._soulwell_lines.text())
        for face in faces:
            face.set_count(_MAX_PER_SLOT, animate=False)
        assert p._soulwell_stack_total() == 25
        assert ("Rare 25 × 12m + 15m once = 5h 15m · +250 rep"
                in p._soulwell_lines.text())
        # the clicks, not just set_count: a click is what a player presses
        QtTest.QTest.mouseClick(faces[0], QtCore.Qt.RightButton)
        assert p._soulwell_stack_total() == 24
        assert ("Rare 24 × 12m + 15m once = 5h 03m · +240 rep"
                in p._soulwell_lines.text())
    finally:
        p.deleteLater()


def test_the_tab_offers_nothing_and_reads_nothing():
    """Read-only station: Clear is the ONLY push button on the card and it
    moves a reading, not the game. The card also builds against a model whose
    every read raises, so "it reads nothing" is asserted rather than assumed."""
    p = _panel(_ExplodingModel())
    try:
        assert set(p.card.findChildren(QtWidgets.QPushButton)) == \
            {p._soulwell_clear}
        texts = _texts(p.card)
        assert "never makes an offering" not in texts
        assert "Make an offering" not in texts
        assert _chance_text(swd.luck_buffs()[0].counter_id) in texts
    finally:
        p.deleteLater()


def test_the_card_carries_no_process_talk():
    """Nothing on the card describes reading, scanning or attaching to the
    game: it reads none, so a sentence about reading one has nothing to
    describe — a badge or note claiming a read is the junk this rebuild
    removed. Word-bounded, or the rule's own words would false-trip it."""
    p = _panel()
    try:
        texts = _texts(p.card).lower()
        for gone in ("read", "scan", "offline", "running", "attached",
                     "process", "mock-up", "current offer"):
            assert not re.search(rf"\b{gone}", texts), (gone, texts)
    finally:
        p.deleteLater()
