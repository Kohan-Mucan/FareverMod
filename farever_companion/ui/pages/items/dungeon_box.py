"""Pane + row widgets for the gear tab's DUNGEONS view.

Split out of `dungeon_view.py`, which sits on the 840-line budget the UI
test enforces. `show_box` is the pane a click on a cache opens; `weapon_chip`
is the compact weapon tile a boss row carries, always painted at the highest
rung the game hands the piece out at. The builders reach back into
`dungeon_view` for the shared row builders, imported INSIDE the functions so
`dungeon_view` can import this module at module level without a cycle.
"""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ... import theme
from ....data import icons
from ....data import items as idata
from .support import projection_rungs


def show_box(page, cache_id: str) -> None:
    """The right-pane card for one CACHE: what is inside the box, in the same
    locked tile grid the faction view uses, under a header naming the box and
    how its roll works (a capped count, or that it scales to you).

    This is what a click on a box in the vendor line opens — the same
    'pick one thing, the pane narrows to it' gesture a boss pick makes, so
    the box does not send you off to the item page to discover its contents.
    Clicking the same box again (or the faction row) releases it.

    Reads the GENERIC container facts (`container_spec`/`container_contents`),
    the SAME source the item page's Contains section renders from: the hand
    table supplies the Heroic/Rift boxes (with their `via` prose for a
    recorded seller), and any box the hand table does not claim falls back to
    the spec derived from its compiler-baked `gain_item`. One source, so the
    two box surfaces cannot disagree about a box's contents.
    """
    from .dungeon_view import _epic_header, _filter_stamp, _locked_grid, _usable
    box = idata.container_contents().get(cache_id) or ()
    if not box:
        return
    spec = idata.container_spec().get(cache_id) or {}
    # the LISTED name, so a box opened from a list keeps the name it was
    # clicked under — the two "Chaotic Gear Cache" boxes must not converge
    name = idata.cache_display_name(cache_id)
    rar = spec.get("rarity") or ""
    # the box's OWN tier is `rar`, but what an open hands out is the span: the
    # Hero Weapon Cache clamps its roll at Epic and can climb to Legendary, so
    # printing the container's rarity alone reads as if every piece were Epic
    floor = spec.get("rarity_min") or rar
    ceiling = spec.get("rarity_max") or rar
    span = f"{floor}+" if ceiling and floor and ceiling != floor else rar
    un = idata.cache_is_unreleased(cache_id)
    page._dg_shown_faction = ""
    page._dg_rendered_boss = ""
    page._dg_rendered_box = cache_id
    page._dg_rendered_class = _filter_stamp(page)
    page._dg_pane_state = "box"
    page._items_shown_id = None
    lay = page._items_detail_lay
    page._items_clear_layout(lay)

    head = QtWidgets.QHBoxLayout()
    head.setSpacing(10)
    emo = QtWidgets.QLabel("🎁")
    emo.setStyleSheet("font-size:32px;background:transparent;")
    head.addWidget(emo)
    info = QtWidgets.QVBoxLayout()
    title = QtWidgets.QLabel(name)
    title.setStyleSheet(
        f"color:{theme.rarity_color(rar) if rar else theme.TEXT};"
        "font-weight:700;font-size:16px;background:transparent;")
    info.addWidget(title)
    bits = [b for b in (span, f"{len(box)} pieces") if b]
    if spec.get("player_scale"):
        bits.append(f"at YOUR level, up to {spec.get('level_max')}")
    elif spec.get("level_max"):
        bits.append(f"gear level {spec['level_max']}")
    if un:
        bits.append("UNRELEASED")
    sub = QtWidgets.QLabel(" · ".join(bits))
    sub.setStyleSheet(
        f"color:{theme.DIM};font-size:11.5px;background:transparent;")
    info.addWidget(sub)
    head.addLayout(info, 1)
    lay.addLayout(head)

    # who hands this box over, in prose: the hand table's `via` where it has
    # one, else the seller the scan actually recorded. Only drawn when the
    # box HAS a seller — a box the hand table never claimed has neither, and
    # the generic fallback must not invent a source for it.
    if not un and (spec.get("via") or idata.cache_vendor(cache_id)):
        vlab = QtWidgets.QLabel(f"via {idata.cache_via(cache_id)}")
        vlab.setWordWrap(True)
        vlab.setMaximumWidth(620)
        vlab.setStyleSheet(
            f"color:{theme.DIM};font-size:11px;background:transparent;")
        lay.addWidget(vlab)

    if un:
        note = QtWidgets.QLabel(
            "UNRELEASED — the box is fully authored, but no boss, vendor, "
            "chest or crate in the game data hands it out.")
        note.setWordWrap(True)
        note.setMaximumWidth(620)
        note.setStyleSheet(
            f"color:{theme.DIM};font-size:12px;background:transparent;")
        lay.addWidget(note)

    pieces = [r["item"] for r in box
              if _usable(page, r["item"], ignore_rarity=True)]
    if pieces:
        lay.addWidget(_epic_header(
            f"{span or 'GEAR'} · {len(pieces)} pieces"
            + (" · UNRELEASED" if un else ""),
            "what one open can hand you"))
        lay.addWidget(_locked_grid(page, pieces))
    page._items_refresh_scroll()


# ----------------------------------------------------------------------


# The chip's edge is full-strength rung colour: it is a 2px frame, not a
# tint over the panel, so anything below solid reads as a smudge against it.
# (The old banded fill carried its colour at 90 over the card body; the edge
# carries it at full strength around a plain body.)
_CHIP_EDGE_ALPHA = 255
#: The frame's thickness: the outer frame's layout margin, so the gradient
#: behind the body reads as a border this wide.
_CHIP_EDGE_PX = 2


def _chip_block_style(rungs: tuple[str, ...], read: str) -> str:
    """The colour style of the FRAME around a weapon chip's icon and name.

    The rungs are painted as HARD-STOP segments of the frame — flat colour,
    never a smooth gradient — left to right, one segment per rung the reading
    spans (a single rung is a solid frame in its colour). The body inside
    stays plain panel: the bands-across-the-card fill read as noise, while
    the edge states the same ladder in the space a frame already occupies.

    `rungs` is the reading the chip shows. An EMPTY tuple means the piece is
    being read at the tier it actually drops at, so the frame is that single
    tier's colour rather than nothing at all.

    The object-name selector is required: the frame's own body is a QFrame
    too, and a bare `QFrame` rule would paint the gradient behind the icon
    and the name as well as around them.
    """
    cols = tuple(rungs) or (read,)
    span = len(cols)
    stops = []
    for i, rung in enumerate(cols):
        col = theme.with_alpha(theme.rarity_color(rung), _CHIP_EDGE_ALPHA)
        lo = i / span
        hi = (i + 1) / span
        stops.append(f"stop:{lo:.4f} {col}, stop:{hi - 0.0005:.4f} {col}")
    return ("QFrame#Card { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            + ", ".join(stops)
            + "); border: none; border-radius: 6px; }"
            + f"QFrame#WeaponChipBody {{ background: {theme.PANEL}; "
              "border: none; border-radius: 4px; }")


def paint_weapon_chip(chip: QtWidgets.QFrame, tier: str | None = None) -> None:
    """Repaint an existing weapon chip's icon + name at `tier`.

    ONE source of a chip's colours: `weapon_chip` builds through this, so the
    two can never disagree.

    `tier` is the rung the chip is read at — the owner passes the highest rung
    the game hands the piece out at; None falls back to the item's own
    authored tier (every weapon in the catalog is authored Rare). A boss
    weapon read at Legendary states the rungs its dungeon rolls, so nothing
    here touches the item, the list or the filters.

    The chip carries its own item id (`weapon_iid`), so a repaint needs no
    side registry: the row that owns the chip is the only thing that has to
    know which item it is showing.
    """
    iid = str(chip.property("weapon_iid") or "")
    if not iid:
        return
    it = idata.item(iid) or {}
    name = it.get("name") or iid
    read = tier or idata.item_display_rarity(iid)
    col = theme.rarity_color(read)
    marks = projection_rungs(iid, read)
    # the FRAME carries the ladder (see _chip_block_style) — the icon stays
    # a plain tile in the read colour, exactly like every other item tile in
    # the app (the browse grid, the Collection cards). Split-colour bands at
    # 32px read as noise next to the weapon art; the frame around the card
    # is where the colours have room to read.
    chip.setStyleSheet(_chip_block_style(marks, read))
    icon = chip.findChild(QtWidgets.QLabel, "WeaponChipIcon")
    if icon is not None:
        # the fill is the item's tier as READ, like its name — and the tile
        # wears NO rung frame here: the chip's own frame already states the
        # ladder, so a second one at 32px would double-stutter it
        icon.setPixmap(icons.item_tile(iid, name, 32, col, rungs=()))
    nm = chip.findChild(QtWidgets.QLabel, "WeaponChipName")
    if nm is not None:
        nm.setStyleSheet(
            f"color:{col};font-weight:600;font-size:11.5px;"
            "background:transparent;")


def weapon_chip(page, iid: str,
                tier: str | None = None) -> QtWidgets.QFrame:
    """Compact weapon tile for the boss row: icon + rarity-colored name,
    click opens the item detail (accepting the event keeps it from also
    triggering the row's select).

    `tier` is the highest rung the game hands the piece out at (see
    `paint_weapon_chip`). The chip still shows ONE weapon: the row repeats
    nothing, it just reads each weapon at its own max.
    """
    it = idata.item(iid) or {}
    name = it.get("name") or iid
    frame = QtWidgets.QFrame()
    frame.setObjectName("Card")
    frame.setProperty("weapon_iid", iid)
    outer = QtWidgets.QHBoxLayout(frame)
    # the margin IS the frame: the gradient behind the body shows through
    # here as a border `_CHIP_EDGE_PX` wide
    outer.setContentsMargins(_CHIP_EDGE_PX, _CHIP_EDGE_PX,
                             _CHIP_EDGE_PX, _CHIP_EDGE_PX)
    outer.setSpacing(0)
    body = QtWidgets.QFrame()
    body.setObjectName("WeaponChipBody")
    outer.addWidget(body)
    h = QtWidgets.QHBoxLayout(body)
    h.setContentsMargins(6, 4, 6, 4)
    h.setSpacing(6)
    icon = QtWidgets.QLabel()
    icon.setObjectName("WeaponChipIcon")
    h.addWidget(icon)
    nm = QtWidgets.QLabel(name)
    nm.setObjectName("WeaponChipName")
    nm.setWordWrap(True)
    h.addWidget(nm, 1)
    frame.setCursor(QtCore.Qt.PointingHandCursor)
    paint_weapon_chip(frame, tier)

    def _open(ev, _p=page, _i=iid):
        _p._items_show_id(_i)
        ev.accept()
    frame.mouseReleaseEvent = _open
    return frame

