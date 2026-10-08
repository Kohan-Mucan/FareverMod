"""Reusable layout, scroll, and container utilities for Tactical Overlay.

Centralizes Qt layout helpers (FlowLayout, wrapping labels, frameless scroll areas,
layout clearing, and box constructors) so pages and components remain lean and modular.
"""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


class FlowLayout(QtWidgets.QLayout):
    """Wrapping horizontal flex layout — items flow onto a new line when the row fills."""

    def __init__(self, parent=None, margin=0, spacing=4):
        super().__init__(parent)
        if parent is not None:
            if isinstance(margin, (int, float)):
                self.setContentsMargins(int(margin), int(margin), int(margin), int(margin))
            elif isinstance(margin, (tuple, list)) and len(margin) == 4:
                self.setContentsMargins(*margin)
        self.setSpacing(spacing)
        self._items: list = []

    def addItem(self, item):
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return QtCore.Qt.Orientations(QtCore.Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        parent = self.parentWidget()
        width = parent.width() if parent is not None else 0
        if width <= 0:
            return self.minimumSize()
        return QtCore.QSize(width, self.heightForWidth(width))

    def minimumSize(self):
        size = QtCore.QSize()
        for it in self._items:
            w = it.widget()
            if w is None or w.isHidden():
                continue
            size = size.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return size + QtCore.QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect: QtCore.QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        x, y = rect.x() + m.left(), rect.y() + m.top()
        line_h, used = 0, 0
        space = self.spacing()
        right = rect.right() - m.right()
        for it in self._items:
            w = it.widget()
            if w is None or w.isHidden():
                continue
            hint = w.sizeHint()
            if x + hint.width() > right and line_h > 0:
                x = rect.x() + m.left()
                y += line_h + space
                line_h = 0
            if not test_only:
                it.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), hint))
            x += hint.width() + space
            line_h = max(line_h, hint.height())
            used = max(used, y + hint.height() + m.bottom())
        return used


class StretchFlow(FlowLayout):
    """FlowLayout whose items fill each row edge to edge.

    Items are grouped so a row only takes as many as can share the width at
    or above their minimum size; rows are then stretched so the items spread
    across the full width (like a grid row). When the viewport is too narrow
    to keep everything in one row the layout wraps to fewer per row instead of
    overflowing horizontally. A lone leftover item keeps its natural width.

    With ``set_min_share(px)`` the flow becomes a fixed COLUMN GRID instead:
    the column count is decided once for the whole flow (the most columns that
    can hold ``px`` per card, never more than the cards present), and every row
    - including a short last one - gives each card that same column width. Its
    cards therefore line up as real columns at any width, where the default
    per-row packing lets a row of one wide card sit over a row of two narrow
    ones and the columns drift apart.

    With ``set_balance_columns(True)`` on that grid, cards are packed into
    COLUMNS balanced by height instead of into top-aligned rows — see
    `set_balance_columns` for why a row grid cannot help when the cards' heights
    are far apart.
    """

    def __init__(self, parent=None, margin=0, spacing=4):
        super().__init__(parent, margin, spacing)
        self._min_share = 0
        self._balance = False

    def set_min_share(self, px: int) -> None:
        """Turn on the fixed-column grid: each card gets at least this width
        before the flow gives up a column (0 restores the default packing)."""
        self._min_share = max(0, int(px))
        self.invalidate()

    def set_balance_columns(self, on: bool = True) -> None:
        """Pack the fixed-column grid into balanced COLUMNS, not rows.

        The row grid top-aligns every card at its OWN height inside a row as tall
        as its tallest member, so the shorter card in a row leaves its leftover
        as a hole under itself. Reordering the cards cannot fix that when the
        heights are spread out: the Settings DPS bottom grid measured 449 / 292 /
        191 / 189 / 111 px, and the closest any row pairing gets is 160px of hole
        (the 449px card has no partner within reach), so the best re-pairing is
        within a few px of the worst.

        Balanced columns instead place each card in whichever column is currently
        shortest, so a tall card is followed by short cards STACKED UNDER IT and
        the hole is filled rather than opened. Every card keeps its own height
        and the single column width, so the columns still line up; what changes
        is that the flow stops reserving a band per row. Measured on that same
        grid at 1600px: 149px of holes in three rows became 45px of difference
        between two columns, and the grid lost ~85px of height.

        Ties (and near-ties, within 1px) keep the LEFT column, so the first two
        cards stay side by side and the packing is stable across passes.
        """
        self._balance = bool(on)
        self.invalidate()

    def _do_layout(self, rect: QtCore.QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        space = self.spacing()
        avail = max(0, rect.width() - m.left() - m.right())
        items = [it for it in self._items
                 if it.widget() is not None and not it.widget().isHidden()]
        if not items or avail <= 0:
            return 0

        def _share(n: int) -> float:
            return (avail - space * (n - 1)) / n if n else 0.0

        fixed = self._min_share > 0
        col_w = 0
        if fixed:
            cols = 1
            for n in range(2, len(items) + 1):
                if _share(n) >= self._min_share:
                    cols = n
                else:
                    break
            col_w = int(_share(cols))
            if self._balance and cols >= 2:
                return self._layout_balanced(rect, items, cols, col_w, m, space,
                                             test_only)
            rows: list[list] = [items[i:i + cols]
                                for i in range(0, len(items), cols)]
        else:
            # Group into rows: a candidate row must fit every member at least
            # at its own minimum width when the row's width is shared equally.
            rows = []
            row: list = []
            row_max_min = 0
            for it in items:
                w = it.widget()
                mn = max(it.minimumSize().width(), w.minimumSizeHint().width())
                n = len(row) + 1
                if row and _share(n) < row_max_min - 1:
                    rows.append(row)
                    row, row_max_min = [], 0
                row.append(it)
                row_max_min = max(row_max_min, mn)
            if row:
                rows.append(row)

        y = rect.y() + m.top()
        for row in rows:
            n = len(row)
            if fixed:
                w_i = col_w
            else:
                widths = [it.sizeHint().width() for it in row]
                w_i = (min(avail, widths[0]) if n == 1
                       else int((avail - space * (n - 1)) / n))
            row_h = 0
            for it in row:
                h = it.heightForWidth(w_i)
                if h < 0:
                    h = it.sizeHint().height()
                    wdg = it.widget()
                    if wdg is not None:
                        # A widget whose sizeHint is not yet computed (or
                        # collapsed by an earlier squeeze) reports 1; the
                        # minimum never lies. This keeps a card alive when
                        # it joins a flow row pre-polish.
                        h = max(h, wdg.minimumSizeHint().height())
                row_h = max(row_h, h)
            if not test_only:
                x = rect.x() + m.left()
                for it in row:
                    h_i = row_h
                    if fixed:
                        # Top-aligned at its OWN height: a card is never
                        # stretched to the tallest in its row, so the Top DPS
                        # card keeps its ~280px body under the divider instead
                        # of growing to the Test Dummy card's ~400px.
                        h_i = it.heightForWidth(w_i)
                        if h_i < 0:
                            h_i = it.sizeHint().height()
                        wdg = it.widget()
                        if wdg is not None:
                            h_i = max(h_i, wdg.minimumSizeHint().height())
                    it.setGeometry(QtCore.QRect(x, y, w_i, h_i))
                    x += w_i + space
            y += row_h + space
        return y - space + m.bottom() if rows else 0


    @staticmethod
    def _card_height(it, w_i: int) -> int:
        """The height `it` really wants at width `w_i` (the balanced path's
        measurement).

        The same rule the fixed-column ROW grid already places its cards by: ask
        the item for its height at the assigned width, and when it has no answer,
        fall back to its sizeHint floored by its minimum — a widget whose sizeHint
        is not yet computed (or collapsed by an earlier squeeze) reports 1, and
        the minimum never lies. Kept beside the row path rather than folded into
        it on purpose: the row grid is what every other `StretchFlow` runs, and
        its two measurements (the band, and the card placed in it) are not this
        one rule.
        """
        h = it.heightForWidth(w_i)
        if h < 0:
            h = it.sizeHint().height()
            wdg = it.widget()
            if wdg is not None:
                h = max(h, wdg.minimumSizeHint().height())
        return h

    def _layout_balanced(self, rect: QtCore.QRect, items: list, cols: int,
                         col_w: int, m: QtCore.QMargins, space: int,
                         test_only: bool) -> int:
        """Place `items` into `cols` columns, each next card in the shortest.

        Heights are measured ONCE at the column width the whole grid shares, so
        the choice of column matches the height the card will really take. The
        tallest column is the flow's height; the only leftover in the whole grid
        is the difference between the columns at the bottom, instead of a hole
        under every shorter card in every row.
        """
        heights = [self._card_height(it, col_w) for it in items]
        col_h = [0] * cols
        columns: list[list[int]] = [[] for _ in range(cols)]
        for i, h in enumerate(heights):
            pick = 0
            for c in range(1, cols):
                # `- 1` keeps a sub-pixel/near tie on the LEFT column, which is
                # what stops the two columns swapping on every resize pass.
                if col_h[c] < col_h[pick] - 1:
                    pick = c
            columns[pick].append(i)
            col_h[pick] += h + space
        if test_only:
            return max(col_h) - space + m.bottom()
        for k, members in enumerate(columns):
            x = rect.x() + m.left() + k * (col_w + space)
            y = rect.y() + m.top()
            for i in members:
                items[i].setGeometry(
                    QtCore.QRect(x, y, col_w, heights[i]))
                y += heights[i] + space
        return max(col_h) - space + m.bottom()


class FlowRow(QtWidgets.QWidget):
    """A widget hosting a wrapping FlowLayout whose sizeHint mirrors its
    container's width (less container margins), so nested wrapping layouts can't
    size it to a stale default width."""

    def __init__(self, parent=None, spacing: int = 6, margins: int = 0):
        super().__init__(parent)
        self._flow = FlowLayout(self, margin=margins, spacing=spacing)
        self.setLayout(self._flow)

    def layout(self) -> FlowLayout:
        return self._flow

    def sizeHint(self):
        gp = self.parentWidget()
        container = gp.parentWidget() if gp is not None else None
        w = container.width() if container is not None else self.width()
        lm = QtCore.QMargins()
        if container is not None and container.layout() is not None:
            lm = container.layout().contentsMargins()
        m = self._flow.contentsMargins()
        avail = max(0, w - lm.left() - lm.right() - m.left() - m.right())
        if avail <= 0:
            return self.minimumSize()
        return QtCore.QSize(avail, self._flow.heightForWidth(avail))


class WrapLabel(QtWidgets.QLabel):
    """Word-wrapping label that enforces its wrapped text height at the ACTUAL
    assigned width as a minimum height, preventing nested box/grid layouts from
    squashing its lines."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWordWrap(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        if w > 30 and self.text():
            need = self.heightForWidth(w)
            if need > 0 and abs(need - self.minimumHeight()) > 1:
                self.setMinimumHeight(need)


class CardScroll(QtWidgets.QScrollArea):
    """Detail-pane scroll area whose card hugs its content: it fills the pane width,
    sizes to the content's sizeHint, and only scrolls when content is taller than the pane.
    Top-anchored: QScrollArea centers a short widget by default, which left short
    cards (and their item names) floating mid-pane — alignment pins them up top."""

    def __init__(self, card: QtWidgets.QWidget, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setStyleSheet("QScrollArea{background:transparent;border:0;}")
        self.setAlignment(QtCore.Qt.AlignTop)
        self.setWidget(card)
        self._card = card

    def _fit(self) -> None:
        if self._card is None:
            return
        w = self.viewport().width()
        if w <= 0:
            return
        card = self._card
        lay = card.layout()
        h = -1
        if lay is not None and lay.hasHeightForWidth():
            h = lay.heightForWidth(w)
        if h <= 0:
            h = card.sizeHint().height()
        card.resize(w, max(h, 1))
        if lay is not None:
            lay.activate()
        deficit = 0
        for lbl in card.findChildren(QtWidgets.QLabel):
            if lbl.isHidden() or not lbl.wordWrap() or not lbl.text():
                continue
            w_lbl = lbl.width()
            if w_lbl <= 30:
                continue
            need = lbl.heightForWidth(w_lbl)
            if need > 0 and lbl.height() < need:
                deficit = max(deficit, need - lbl.height())
        if deficit > 2:
            card.resize(w, card.height() + deficit)
            if lay is not None:
                lay.activate()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._fit()


def make_scroll(widget: QtWidgets.QWidget, h_scroll: bool = False,
                v_scroll: bool = True, parent=None) -> QtWidgets.QScrollArea:
    """Create a transparent, borderless QScrollArea hosting the given widget."""
    sa = QtWidgets.QScrollArea(parent)
    sa.setWidgetResizable(True)
    sa.setFrameShape(QtWidgets.QFrame.NoFrame)
    sa.setStyleSheet("QScrollArea{background:transparent;border:0;}")
    sa.setHorizontalScrollBarPolicy(
        QtCore.Qt.ScrollBarAsNeeded if h_scroll else QtCore.Qt.ScrollBarAlwaysOff)
    sa.setVerticalScrollBarPolicy(
        QtCore.Qt.ScrollBarAsNeeded if v_scroll else QtCore.Qt.ScrollBarAlwaysOff)
    sa.setWidget(widget)
    return sa


def span_trailing_row(grid: QtWidgets.QGridLayout, cols: int = 2,
                      from_row: int = 0) -> None:
    """Make a partly-filled last row span the grid's full width.

    The tile grids in Settings (the Layers matrix and both Pages sections)
    fill row-major two at a time, so an odd number of tiles left the final
    row half empty and the hole read as a layout bug — three Sidebar Elements
    in a frozen build, where the dev-only Dev Icons tile is absent, was the
    case that shipped. Re-adding the trailing item across every column closes
    the hole and hands the odd one out the width it was missing anyway.

    `from_row` scopes the search, which is what a grid holding several groups
    needs: the Layers matrix is ONE grid with a row range per layer group, so
    it calls this once per group (right after adding that group's cards) and
    an odd group in the middle is closed just like one at the bottom. Items
    already spanning `cols` — the group's own `// HEADER` label — are left
    alone; a header is a lone cell too, and re-adding it is a no-op.
    """
    rows: dict[int, list[tuple[int, int, int]]] = {}
    for i in range(grid.count()):
        r, c, _rs, cs = grid.getItemPosition(i)
        if r < from_row:
            continue
        rows.setdefault(r, []).append((c, cs, i))
    if not rows:
        return
    last = max(rows)
    cells = rows[last]
    if len(cells) != 1:
        return                      # full row, nothing to close up
    col, cs, idx = cells[0]
    if col != 0 or cs >= cols:
        return                      # not the odd-one-out (already spans)
    item = grid.takeAt(idx)
    if item is not None:
        grid.addItem(item, last, 0, 1, cols)


def place_popup(pop: QtWidgets.QWidget, pos: QtCore.QPoint) -> None:
    """Put `pop` at `pos`, clamped inside the screen it lands on, and show it.

    A popup anchored under a row can hang off the bottom or right edge of the
    monitor it opens on; clamping against that screen's available geometry
    keeps a long list readable instead of cut off. The Combat rail's skill
    popup and the Items skill section's both needed exactly this."""
    scr = QtGui.QGuiApplication.screenAt(pos)
    if scr is None:
        scr = QtGui.QGuiApplication.primaryScreen()
    if scr is not None:
        geo = scr.availableGeometry()
        pos.setX(max(geo.left(), min(pos.x(), geo.right() - pop.width())))
        pos.setY(max(geo.top(), min(pos.y(), geo.bottom() - pop.height())))
    pop.move(pos)
    pop.show()


def clear_layout(layout: QtWidgets.QLayout | None) -> None:
    """Safely remove and delete all child widgets and nested items from a layout.

    Detached + hidden synchronously (not just deleteLater'd): rebuilt rows
    (filter chips, flow tiles) would otherwise stay findable — and painted
    for a frame — until the event loop delivers the deferred deletion, which
    headless tests never do."""
    if layout is None:
        return
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        child_lay = item.layout()
        if child_lay is not None:
            clear_layout(child_lay)


def vbox(parent: QtWidgets.QWidget | None = None,
         margins: int | tuple[int, int, int, int] = 0,
         spacing: int = 6) -> QtWidgets.QVBoxLayout:
    """Construct a QVBoxLayout with default zero-margins and configured spacing."""
    lay = QtWidgets.QVBoxLayout(parent) if parent is not None else QtWidgets.QVBoxLayout()
    if isinstance(margins, (int, float)):
        lay.setContentsMargins(int(margins), int(margins), int(margins), int(margins))
    elif isinstance(margins, (tuple, list)) and len(margins) == 4:
        lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return lay


def hbox(parent: QtWidgets.QWidget | None = None,
         margins: int | tuple[int, int, int, int] = 0,
         spacing: int = 6) -> QtWidgets.QHBoxLayout:
    """Construct a QHBoxLayout with default zero-margins and configured spacing."""
    lay = QtWidgets.QHBoxLayout(parent) if parent is not None else QtWidgets.QHBoxLayout()
    if isinstance(margins, (int, float)):
        lay.setContentsMargins(int(margins), int(margins), int(margins), int(margins))
    elif isinstance(margins, (tuple, list)) and len(margins) == 4:
        lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return lay
