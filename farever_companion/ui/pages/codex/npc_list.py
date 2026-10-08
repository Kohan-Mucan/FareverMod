"""NPC list view for the Codex Other tab.

The "NPC" chip on the Other sub-bar lists every PLACED NPC in the world: the
`npc` / `vendor` / `petshop` / `mountshop` rows of `poi_locs` (read through
`geo.pois.load_npc_pois`). It is a directory rather than a wall of rows: a
filter rail on the left (one placement family at a time, zone, the dev-only
rows) beside one dense table sorted zone -> place -> name, rendered inside the
grid panel while the chip is active. The rail is a column of toggle buttons, on
purpose: it was hand-drawn checkbox squares first, which is not what a filter
rail is. It also REMEMBERS its last state through the settings (see
`_load_filters`), because this whole view is rebuilt every time the chip is
activated - without that, every reopen reset the rail to the shipped defaults.

The family rail is ONE at a time, and a family's click plots it: "where is a
shop" is a question about the world, so a family button both lists that family
and puts every placement of it on the codex map. Haydn Seek is the last entry of
that same column rather than a section of its own, and he is the SHIPPED
default: opening the list shows his ten placements with their pins already on
the map. The plain NPC family is the exception - its click plots nothing,
because one click there would bury the map in every trainer and guard in the
game.

These NPCs have no codex card of their own — that is the whole reason the list
exists: before it, the plain `npc` placements were in no surface at all (the
minimap plots obelisk/respawn and the shop families only), so the trainers,
prison guards and quest NPCs could not be found anywhere in the app.

Clicking a row tracks that NPC exactly like clicking a minimap marker
(compass needle + Entity HUD waypoint row) and plots the labeled pin on the
codex map; clicking the tracked row again stops and clears the pin. Tracking
uses the generic `pos` waypoint kind, the same one the Entity HUD's loot rows
use, so no new tracker kind is introduced for a static person.

All track/plot resolution lives in `NpcMixin` here (like `SoulstoneMixin`);
this file owns both the view and its page-side helpers.
"""
from __future__ import annotations

import collections
import re
from functools import lru_cache

from PySide6 import QtCore, QtGui, QtWidgets

from ... import theme
from ....data import atlas
from ....data import dungeons
from ....data import icons
from ....data import names
from ....geo import pois as geo_pois

# Two answers per row, and they are different questions. A FAMILY (the rail's
# button) is one of four roles and gets ONE sprite, so the button says what the
# family is. A ROW is one placement and draws the character standing there, when
# the game's unit table and the atlas together can say who that is
# (`placement_unit`) - Hilda Lambert's own face on every placement of her, Job
# Welldon on the trainer, and the FAMILY's sprite only where the atlas has
# nothing better.
#
# Every sprite is an entry of the SHIPPED atlas, so all of them draw without a
# single new asset. The NPC-ish roles read the MINIMAP sheet - the plain person
# (`npc`) and Haydn's `npc_bubble`, the two sprites the game's own map draws for
# them.
#
# The shop counters read the UNITS sheet, where the NPCs' OWN art lives: the
# Guild Merchant (`wanderingmerchant`), the pet-shop keeper (`demonhunterzoey` -
# Zoey, who keeps the pet stands in all three zones) and the mount vendor.
# `role_sheet` carries the sheet and `icons.marker` takes one, so both sheets
# render through one path.
#
# The MOUNT TAMER has no sprite of her own in the atlas: `mounttamer`, `tamer`
# and `perina` are nowhere among its 1632 unit entries. But the game's unit table
# carries exactly ONE mount-keeper character - `StableMaster`, a Human filed as
# "Guild Merchant", the unit the mount stands stand on - and the atlas draws it,
# so the mount shop reads that instead of the plain person. The day a `tamer`
# sprite lands, the sprite contract test's probe list goes red and says to use
# it.
#
# The plain world NPC's own colour. The three shop families deliberately do
# NOT get a colour of their own: they read `theme.KIND_COLOR`, the one table the
# minimap's kiosk rings also read (`minimap_render.poi_pixmap`), so the map and
# this list cannot disagree about what a vendor, a pet shop and a mount shop
# look like - which is how they spent a release as one gold in the kind table
# and one gold on the map.
_NPC_ACCENT = "#7dd3fc"
_ROLE_ART = {
    "npc": ("minimap", "npc"),
    "vendor": ("units", "wanderingmerchant"),
    "petshop": ("units", "demonhunterzoey"),
    # the game's only mount-keeper unit, not a gap: see the note above
    "mountshop": ("units", "stablemaster"),
}
# The placeholder the atlas falls back to when it has no sprite for a character:
# the plain person on the minimap sheet. A row that draws THIS is a placement the
# atlas never drew - see `atlas_cannot_draw`.
_PLAIN_PERSON = _ROLE_ART["npc"]
_ROLE_LABELS = {
    "npc": "NPC",
    "vendor": "Vendor",
    "petshop": "Pet Shop",
    "mountshop": "Mount Shop",
}
# Rail order, and the order the role buttons stack: the shops lead, because
# finding one is the reason to open this list at all.
_ROLE_ORDER = ("vendor", "petshop", "mountshop", "npc")

# Haydn Seek is the game's hide-and-seek NPC: an `npc` placement like any
# trainer, but the one character this list gets used to hunt down, so he keeps
# the speech-bubble sprite instead of the plain person.
_HAYDN_NAME = "Haydn Seek"
_HAYDN_ART = ("minimap", "npc_bubble")
# The rail's sprite size: a family's art at button size.
_RAIL_ICON = 16
# The atlas-gap mark, on each row the atlas cannot draw (see
# `atlas_cannot_draw`), and
# the tracking mark those same cells otherwise carry - a row can be both, so
# the cell holds the two joined rather than one or the other.
_GAP_MARK = "◌ no art"
_TRACK_MARK = "◈ TRACKING"

# The rail's family list: what the table lists (ONE at a time) and what that
# family's own click plots. Haydn Seek is last and is not a role, but his entry
# behaves exactly like one - list that family, plot every placement of it - so
# "pin all Haydn" is this rail's own family button rather than a momentary
# button of his own underneath him.
_FAMILY_ORDER = _ROLE_ORDER + ("haydn",)
_FAMILY_LABELS = {**_ROLE_LABELS, "haydn": _HAYDN_NAME}

# The dev-only placements are marked in the NAME and nowhere else - a `poi_locs`
# row carries no flag for them - and they are 14 of the 85 placements, all inside
# two zones (Tyrna reads 13 rows, Lower Ramburg 15, entirely because of them).
_DEBUG_MARK = "(debug)"


def _is_debug(row: dict) -> bool:
    return _DEBUG_MARK in (row.get("name") or "").lower()


def _is_haydn(row: dict) -> bool:
    return (row.get("name") or "") == _HAYDN_NAME


def _role_accent(role: str) -> str:
    """The accent for a role: `theme.KIND_COLOR`'s colour for the three shop
    families, and this list's own sky blue for the plain NPC (`KIND_COLOR` has
    no `npc` entry) - so an unknown role still reads as a person rather than
    losing its colour."""
    return theme.KIND_COLOR.get(role) or _NPC_ACCENT


def _norm_key(text: str) -> str:
    """A unit id or a sheet id as a lookup key: lowercase, punctuation gone."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


# The role word `poi_locs` writes into its ids: `DemonHuntZoey_NPC_Azuram`,
# `WanderingMerchant_Npc_Azuram`, `Codex_NPC_Hilda_Eksod`. The head is the
# character for most of them, so it is the first place to look for art.
_ID_ROLE_WORD = re.compile(r"[_-]npc[_-]", re.IGNORECASE)

# HAND-FACT: _ID_ALIASES
# The two `poi_locs` heads whose character the game's unit table spells
# DIFFERENTLY, so the head route misses it: both Demon Huntresses drop the "er"
# the unit id keeps (`DemonHuntMira_NPC_Azuram` -> `DemonHunterMira`,
# `DemonHuntZoey_NPC_Azuram` -> `DemonHunterZoey`). No sheet row carries the
# mapping - the two ids really are spelled differently, in the game's own data -
# so without this the pet-shop keeper and Mira the vendor both fall through to
# the vendor family's Guild Merchant sprite.
_ID_ALIASES = {
    "demonhuntzoey": "DemonHunterZoey",
    "demonhuntmira": "DemonHunterMira",
}


@lru_cache(maxsize=1)
def _unit_art() -> tuple[dict[str, str], dict[str, str]]:
    """The game's unit table, narrowed to the units the atlas can DRAW, as
    `(by id, by name)` maps of key -> unit id.

    `by name` keeps only names the table uses for ONE unit: "Guild Merchant" is
    two different characters (the wandering merchant and the stable master), and
    a row must not draw whichever of them the table happened to list first.
    Cached: the table is 530 rows and every row of every rebuild asks this.
    """
    from ....data import cdb
    by_id: dict[str, str] = {}
    names: dict[str, str] = {}
    ambiguous: set[str] = set()
    for m in cdb.lines("units"):
        uid = str(m.get("id") or "").strip()
        if not uid:
            continue
        key = _norm_key(uid)
        if key and atlas.find_entry("units", uid) is not None:
            by_id.setdefault(key, uid)
        name = (m.get("name") or "").strip().lower()
        if not name:
            continue
        if names.setdefault(name, uid) != uid:
            ambiguous.add(name)
    by_name = {n: u for n, u in names.items()
               if n not in ambiguous
               and atlas.find_entry("units", u) is not None}
    return by_id, by_name


def placement_unit(row: dict) -> str | None:
    """The unit-table id this PLACEMENT stands for, or None when the sheet's own
    data cannot say.

    Two routes, both keyed on the game's unit table rather than on a guess: the
    head of the `poi_locs` id (`WanderingMerchant_Npc_Azuram` -> the
    `WanderingMerchant` unit, `ProfessionTrainer_Npc_4` -> the trainer), and the
    placement's NAME (`Hilda Lambert`, whose ids are the generic
    `Codex_NPC_Hilda_*`). A unit id that is not in the table is never accepted -
    that is what keeps a generic head like `Critters` or `NPC` from resolving
    against whatever the atlas happens to call it.
    """
    by_id, by_name = _unit_art()
    pid = str(row.get("id") or "")
    head = _norm_key(_ID_ROLE_WORD.split(pid, 1)[0])
    for key in (head, _norm_key(pid), (row.get("name") or "").strip().lower()):
        if not key:
            continue
        unit = _ID_ALIASES.get(key) or by_id.get(key) or by_name.get(key)
        if unit:
            return unit
    return None


def atlas_cannot_draw(row: dict) -> bool:
    """True when this placement draws the atlas's plain-person placeholder.

    That is the atlas gap, exactly as the directory test writes it out: 26 of
    the 38 characters, standing at 34 placements (a character is in more than
    one zone). The route is the DRAWN sprite itself (`role_art`), so the mark a
    row wears and the icon beside it have one answer and cannot disagree.

    Not every unresolved row is a gap. `placement_unit` returns None for the
    mount shop's placements too, yet they draw the unit table's `stablemaster` -
    a real character sprite serving as that family's placeholder - so the atlas
    DOES draw something for them, and the sprite list files Perina Wann with the
    drawn characters rather than the missing ones.
    """
    return role_art(row) == _PLAIN_PERSON


def role_art(row: dict) -> tuple[str, str]:
    """(sheet, sprite) a row is drawn with: this placement's OWN character when
    the atlas draws one, the speech bubble for Haydn Seek, and otherwise the
    role's sprite. An unknown role falls back to the plain person.

    The sheet is half of the answer: the drawn characters come off the units
    sheet, the role placeholders off the minimap one."""
    if _is_haydn(row):
        return _HAYDN_ART
    unit = placement_unit(row)
    if unit:
        return ("units", unit)
    return _ROLE_ART.get(row.get("role") or "") or _ROLE_ART["npc"]


def role_glyph(row: dict) -> str:
    """The sprite NAME a row is drawn with."""
    return role_art(row)[1]


def role_sheet(row: dict) -> str:
    """The atlas sheet that sprite lives on, for `icons.marker(..., sheet=)`."""
    return role_art(row)[0]


def _rail_icon(art: tuple[str, str]) -> QtGui.QIcon:
    """A family's rail sprite, at the rail's size and WITHOUT the accent ring -
    at 16px a ring eats the sprite, and the button's own label is already in the
    family's colour. A row may draw a character of its own instead; that split is
    what `role_art` is for."""
    sheet, name = art
    return QtGui.QIcon(icons.marker(name, _RAIL_ICON, sheet=sheet))


def row_accent(row: dict) -> str:
    """The accent a row is drawn in - its role's colour, or the app accent for
    Haydn Seek, so the table, the pin on the map and the sub-line all match."""
    if _is_haydn(row):
        return theme.ACCENT
    return _role_accent(row.get("role") or "")


def _zone_tag(zone_id: str | None) -> str:
    """'Z2_Azuram_Hub' -> 'Z2' (Crimson folds to Z3), else 'Other'."""
    return dungeons.zone_tag_from_zone_id(zone_id or "") or "Other"


def _zone_sort_key(zone_id: str) -> tuple:
    """Z1 before Z2 before Z3, then anything the sheet doesn't tag."""
    order = {"Z1": 0, "Z2": 1, "Z3": 2}
    return (order.get(_zone_tag(zone_id), 3),
            (names.zone_name(zone_id) or zone_id).lower())


def npc_rows() -> list[dict]:
    """Every placed NPC as a plain row dict, zone-ordered.

    Read-only and pure: `geo.pois` owns the index, this only reshapes it for
    the view (and for the tests, which walk the same list the view renders).
    """
    rows = []
    for p in geo_pois.load_npc_pois():
        rows.append({
            "id": p.id,
            "name": p.name or p.id,
            "role": p.sub_kind,
            "zone": p.zone or "",
            "zone_tag": _zone_tag(p.zone),
            "place": names.zone_name(p.zone) or p.zone or "",
            "x": p.x, "y": p.y, "z": p.z,
        })
    rows.sort(key=lambda r: (_zone_sort_key(r["zone"]), r["name"].lower(), r["id"]))
    return rows


class _RailOption(QtWidgets.QPushButton):
    """One rail filter, as a real BUTTON.

    The rail drew a 13x13 square per option and called it a checkbox. It was not
    a `QCheckBox` (so Qt styled nothing about it: no hover, no focus, no
    keyboard, no checked state), and it read as a checkbox sitting in a column of
    what are on/off buttons anyway. It is a checkable `QPushButton` now, in the
    segment-button language the rest of the app speaks - left-aligned label with
    the count trailing it, accent-tinted while the option is on, and a hover that
    says it is clickable.

    Checked means "this is the one listed" for the family buttons (they are one
    at a time) and INCLUDED for the zone options (the `FilterChip` convention);
    the view options are named for what they turn on, so the button that is lit
    is always the button whose effect is active. Nothing here is a
    tooltip: the flat-list convention this view already followed.
    """

    def __init__(self, label: str, count: int, on: bool, color: str,
                 art: tuple[str, str] | None = None, parent=None):
        super().__init__(parent)
        self._color = color
        self.setCheckable(True)
        self.setText(f"{label}  {count}")
        if art:
            self.setIcon(_rail_icon(art))
            self.setIconSize(QtCore.QSize(_RAIL_ICON, _RAIL_ICON))
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip("")
        self.setStyleSheet(self._qss())
        self.set_on(on)

    def _qss(self) -> str:
        """Both states carry the same 1px border and padding, so toggling an
        option can never reflow the rail's column."""
        col = self._color
        return (
            "QPushButton { background:transparent; border:1px solid transparent;"
            f" color:{theme.MUTED}; text-align:left; padding:4px 10px;"
            " font-size:12.5px; border-radius:4px; }"
            f"QPushButton:hover {{ background:{theme.with_alpha(theme.PANEL_HI, 90)};"
            f" color:{theme.TEXT}; }}"
            f"QPushButton:checked {{ background:{theme.with_alpha(col, 45)};"
            f" border:1px solid {theme.with_alpha(col, 120)}; color:{col};"
            " font-weight:600; }"
            f"QPushButton:checked:hover {{ background:{theme.with_alpha(col, 62)}; }}")

    def set_on(self, on: bool) -> None:
        """Set the state WITHOUT re-emitting `toggled`: the rail has already
        decided what is true (`_sync_rail`), so this is the rail telling the
        button, never the button telling the rail."""
        self.blockSignals(True)
        self.setChecked(bool(on))
        self.blockSignals(False)

    def is_on(self) -> bool:
        return self.isChecked()


def _rail_head(text: str) -> QtWidgets.QLabel:
    lbl = QtWidgets.QLabel(text.upper())
    lbl.setStyleSheet(
        f"color:{theme.DIM}; font-size:11px; letter-spacing:1px;"
        " margin-top:7px; margin-bottom:2px;")
    return lbl


class NpcListView(QtWidgets.QFrame):
    """The placed-NPC directory: a filter rail beside one dense table.

    This list has two jobs that want two different orders, which is why it is no
    longer the 2-column zone-block list it replaced. A vendor is only useful if
    you know where to walk, so the rows stay sorted zone -> place -> name and the
    Place and Zone columns carry the location; and the rail is what lets the two
    questions people actually arrive with - "where is a shop", "where is Haydn" -
    be asked directly instead of scraped out of 33 zone headers.

    Every placement is still reachable: the family buttons are one at a time, so
    the invariant is that walking all five of them (every zone on, the dev rows
    shown) lists every placement in the index - which is what the contract test
    does via `show_family()`. The shipped default decides what is on screen FIRST
    (Haydn Seek, every zone on, the dev-only rows hidden); after that the
    rail restores what the last visit left behind, so a table opened onto the
    mount shops stays on the mount shops.
    One row is one placement, always: `poi_locs` names every spot separately, so
    there is nothing to fold and no `count` on a row - the rail used to offer a
    "Fold repeats" toggle whose only effect was on the debug merchant, which the
    default filter hides anyway, so it was a control that did nothing.
    """

    COLUMNS = ("", "Name", "Role", "Place", "Zone", "")
    # (width, mode) per column: only the name stretches.
    # The last column holds the atlas-gap mark and the tracking mark together,
    # so it is wide enough for both ("◌ no art · ◈ TRACKING").
    _COL_WIDTHS = ((38, "fixed"), (0, "stretch"), (98, "fixed"),
                   (196, "fixed"), (54, "fixed"), (140, "fixed"))
    _ROW_H = 30

    def __init__(self, ui, parent=None):
        super().__init__(parent)
        self.ui = ui
        self._all: list[dict] = npc_rows()
        self._rows: list[dict] = []
        self.row_count = 0
        # ONE family at a time (see `toggle_family`); the zones stay multi-select.
        # Haydn Seek opens the list: his ten placements with their map pins.
        self._family = "haydn"
        self._zones = {r["zone_tag"] for r in self._all}
        # per-family / per-zone placement counts: the rail numbers, and the data
        # for the open-on-a-listing-family fallback in `_load_filters`
        self._role_counts = collections.Counter(r["role"] for r in self._all)
        self._family_counts = dict(self._role_counts)
        # Haydn Seek has a family button of his own, so his placements are not
        # also counted under the plain NPCs (and `_keep` refuses them there):
        # the NPC family is every OTHER world NPC.
        self._family_counts["npc"] = sum(
            1 for r in self._all if r["role"] == "npc" and not _is_haydn(r))
        self._family_counts["haydn"] = sum(1 for r in self._all if _is_haydn(r))
        self._zone_counts = collections.Counter(
            r["zone_tag"] for r in self._all)
        self._show_debug = False
        # the atlas-gap listing (see `toggle_noart`): the whole index rather
        # than one family, because the point is to see every placement the
        # atlas cannot draw in one place
        self._noart_only = False
        self._rail: dict[tuple[str, str], _RailOption] = {}
        self._load_filters()

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_rail())
        root.addWidget(self._build_right(), 1)

        self._rebuild()
        # The opening family arrives plotted, like its button had been clicked:
        # the default is Haydn with his pins on the map, not a list waiting
        # for a click to explain where its rows stand.
        self._plot_selected_family()

        self._tr = getattr(getattr(ui, "overlay_mgr", None), "tracker", None)
        if self._tr is not None:
            self._tr.changed.connect(self.refresh_tracked)
        self.refresh_tracked()

    # ---- rail ------------------------------------------------------------
    def _build_rail(self) -> QtWidgets.QFrame:
        rail = QtWidgets.QFrame()
        rail.setObjectName("NpcRail")
        rail.setFixedWidth(224)
        rail.setStyleSheet(
            f"QFrame#NpcRail {{ background:{theme.LOWEST};"
            f" border-right:1px solid {theme.BORDER}; }}")
        box = QtWidgets.QVBoxLayout(rail)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(2)

        # ONE family at a time, and the click plots it: the family buttons are
        # what answer "where is a shop", so they carry the map action too.
        box.addWidget(_rail_head("Role"))
        for key in _FAMILY_ORDER:
            self._add_opt(box, "role", key, _FAMILY_LABELS[key],
                          self._family_counts.get(key, 0),
                          self._family_accent(key),
                          lambda k=key: self.toggle_family(k),
                          art=self._family_art(key))

        box.addWidget(_rail_head("Zone"))
        tags = sorted({r["zone_tag"] for r in self._all})
        for tag in tags:
            n = self._zone_counts[tag]
            label = f"Zone {tag[1:]}" if tag.startswith("Z") else tag
            self._add_opt(box, "zone", tag, label, n, theme.ACCENT,
                          lambda t=tag: self.toggle_zone(t))

        box.addWidget(_rail_head("View"))
        self._add_opt(box, "view", "debug", "PTS debug npcs",
                      sum(1 for r in self._all if _is_debug(r)),
                      theme.DANGER, self.toggle_debug,
                      art=_ROLE_ART["npc"])
        # The atlas gap, as a listing of its own: the 26-character hole in the
        # sprite atlas used to be visible only to a test. Clicking this lists
        # every placement the atlas cannot draw - all roles, all zones - which
        # is the whole point of a view that ignores the other two filters.
        self._add_opt(box, "view", "noart", "No atlas sprite",
                      sum(1 for r in self._all if atlas_cannot_draw(r)),
                      theme.ORANGE, self.toggle_noart,
                      art=_PLAIN_PERSON)
        self._noart_hint = QtWidgets.QLabel(
            "Every placement whose character the atlas never drew, in every "
            "zone: each falls back to the plain person. The count includes the "
            "PTS-only rows, which follow the 'PTS debug npcs' toggle.")
        self._noart_hint.setWordWrap(True)
        self._noart_hint.setStyleSheet(
            f"color:{theme.DIM}; font-size:10.5px; margin:0 2px 0 2px;")
        self._noart_hint.setVisible(False)
        box.addWidget(self._noart_hint)
        box.addStretch(1)
        return rail

    def _add_opt(self, box, group: str, key: str, label: str, count: int,
                 color: str, slot, art=None) -> None:
        opt = _RailOption(label, count, self._opt_is_on(group, key), color, art)
        opt.toggled.connect(lambda _on, s=slot: s())
        self._rail[(group, key)] = opt
        box.addWidget(opt)

    @staticmethod
    def _family_art(key: str) -> tuple[str, str]:
        """The rail sprite for a family: its role's art, or Haydn's bubble."""
        if key == "haydn":
            return _HAYDN_ART
        return _ROLE_ART.get(key) or _ROLE_ART["npc"]

    def _family_accent(self, key: str) -> str:
        """A family's rail colour: its role's, with the app accent for Haydn
        Seek - the same pair `row_accent` gives his rows."""
        if key == "haydn":
            return theme.ACCENT
        return _role_accent(key)

    def _opt_is_on(self, group: str, key: str) -> bool:
        if group == "role":
            return key == self._family
        if group == "zone":
            return key in self._zones
        if group == "view":
            return self._show_debug if key == "debug" else self._noart_only
        return self._show_debug

    def _sync_rail(self) -> None:
        for (group, key), opt in self._rail.items():
            opt.set_on(self._opt_is_on(group, key))
        hint = getattr(self, "_noart_hint", None)
        if hint is not None:
            hint.setVisible(self._noart_only)

    # ---- persistence -----------------------------------------------------
    # The rail remembers its last state across rebuilds, the way the rest of the
    # Codex persists a filter: through the panel's `s` (Settings), guarded with
    # `hasattr` so a page built on a bare settings object still works, and
    # `save()`d on the change (see `ui/pages/codex/page.py`'s `codex_compact`).
    # This list is rebuilt every time the NPC chip is activated, so without this
    # every reopen would silently reset to the shipped defaults.
    def _load_filters(self) -> None:
        """Restore the rail's last state from the settings, if it is there.

        The selected family is a key of its own and the zones are the OFF set
        (see `codex_npc_role` / `codex_npc_zones_off` in `config/model.py`):
        absent from the file means ON, so a zone tag a game patch adds arrives ON
        rather than filtered out of a view whose whole point is that no placement
        has anywhere else to be seen. A saved family the game no longer has - or
        one whose family has no placement left - falls back to a family that
        lists something: a blank table reads as a broken view, not as an empty
        choice.
        """
        s = getattr(self.ui, "s", None)
        if s is None:
            return
        saved = getattr(s, "codex_npc_role", None)
        if not (isinstance(saved, str) and saved in _FAMILY_ORDER
                and self._family_counts.get(saved)):
            # No usable save: Haydn first, then the rail's own order — a blank
            # table reads as a broken view, not as an empty choice.
            saved = next((k for k in ("haydn",) + _FAMILY_ORDER
                          if self._family_counts.get(k)), self._family)
        self._family = saved
        off_zones = getattr(s, "codex_npc_zones_off", None)
        if off_zones is not None:
            kept = {t for t in self._zone_counts if t not in set(off_zones)}
            self._zones = kept or set(self._zone_counts)
        if hasattr(s, "codex_npc_show_debug"):
            self._show_debug = bool(s.codex_npc_show_debug)

    def _save_filters(self) -> None:
        """Write the rail's state back out.

        The OFF set is DERIVED (`declared - on`), so a zone tag the game drops
        stops being listed the first time this runs - the file can never
        accumulate keys for buttons that no longer exist.
        """
        s = getattr(self.ui, "s", None)
        if s is None:
            return
        if hasattr(s, "codex_npc_role"):
            s.codex_npc_role = self._family
        if hasattr(s, "codex_npc_zones_off"):
            s.codex_npc_zones_off = sorted(set(self._zone_counts) - self._zones)
        if hasattr(s, "codex_npc_show_debug"):
            s.codex_npc_show_debug = self._show_debug
        save = getattr(s, "save", None)
        if callable(save):
            save()

    def family_rows(self, key: str | None = None) -> list[dict]:
        """Every placement of one family in the whole index - never the filtered
        rows: the zone rail can leave a family with three of its twelve vendors
        listed, and the question a family's click answers is still "where are the
        vendors"."""
        key = key or self._family
        if key == "haydn":
            return [r for r in self._all if _is_haydn(r)]
        if key == "npc":
            # the same split `_keep` makes: Haydn Seek is his own family
            return [r for r in self._all
                    if r["role"] == "npc" and not _is_haydn(r)]
        return [r for r in self._all if r["role"] == key]

    # ---- table -----------------------------------------------------------
    def _build_right(self) -> QtWidgets.QWidget:
        right = QtWidgets.QWidget()
        col = QtWidgets.QVBoxLayout(right)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        table = QtWidgets.QTableWidget(0, len(self.COLUMNS), right)
        self._table = table
        table.setHorizontalHeaderLabels(list(self.COLUMNS))
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setFrameShape(QtWidgets.QFrame.NoFrame)
        table.setIconSize(QtCore.QSize(26, 26))
        table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setFocusPolicy(QtCore.Qt.NoFocus)
        table.setCursor(QtCore.Qt.PointingHandCursor)
        table.setToolTip("")
        # The codex grid already lives in a QScrollArea, so this table must not
        # grow a second scrollbar inside it: it is sized to its content instead
        # and the page does the scrolling (see `_fit_table`).
        table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        vh = table.verticalHeader()
        vh.setDefaultSectionSize(self._ROW_H)
        vh.setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        hh = table.horizontalHeader()
        hh.setHighlightSections(False)
        for i, (width, mode) in enumerate(self._COL_WIDTHS):
            hh.setSectionResizeMode(
                i, QtWidgets.QHeaderView.Stretch if mode == "stretch"
                else QtWidgets.QHeaderView.Fixed)
            if mode == "fixed":
                table.setColumnWidth(i, width)
        table.cellClicked.connect(self._on_cell_clicked)
        col.addWidget(table)
        # The RAIL is what decides this pane's height (five families, three
        # zones and the view toggle is taller than most families are), so the
        # table's column is usually far taller than the rows in it. Without a
        # trailing stretch the layout has nowhere to put that surplus and Qt
        # centers the table in the column - a blank band above the first row,
        # sized by the rail, which reads as an empty list with a few rows
        # floating under the middle. The rows belong at the top.
        col.addStretch(1)
        return right

    def _fit_table(self) -> None:
        """Size the table to exactly its rows: the codex page owns the only
        scrollbar, so a nested one is never needed and never steals the wheel."""
        head = self._table.horizontalHeader().sizeHint().height()
        self._table.setFixedHeight(
            head + self._table.rowCount() * self._ROW_H + 2)

    def _keep(self, row: dict) -> bool:
        """True when the row is in the selected family, its zone is on, and the
        debug toggle is not hiding it.

        The plain NPC family leaves Haydn Seek out. He is a world NPC like the
        rest, but he has a family button of his own, so showing him under both
        would answer "where are the other NPCs" with the one name the rail
        already has a button for.
        """
        if self._noart_only:
            # the gap listing ignores the family AND the zones: it answers
            # "what can the atlas not draw", which is not a place question
            return (self._show_debug or not _is_debug(row)) \
                and atlas_cannot_draw(row)
        if self._show_debug:
            # the debug listing: every dev-only row, whatever family or zone
            # claims it. A toggle that only revealed a family's own dev rows
            # would show nothing at all on families that have none (Haydn has
            # zero of the 14), which reads as a dead button rather than a view.
            return _is_debug(row)
        if row["zone_tag"] not in self._zones:
            return False
        if self._family == "haydn":
            if not _is_haydn(row):
                return False
        elif row["role"] != self._family:
            return False
        elif self._family == "npc" and _is_haydn(row):
            # the one plain NPC the NPC family leaves out: he has his own
            # button, so he is not also an "other NPC" row
            return False
        return not _is_debug(row)

    def _rebuild(self) -> None:
        """Re-filter the whole index into `_rows`. One row is one placement:
        `poi_locs` names every spot separately, so nothing is collapsed here and
        a row carries no `count`."""
        self._rows = [r for r in self._all if self._keep(r)]
        self.row_count = len(self._rows)
        self._fill_table()

    def _fill_table(self) -> None:
        table = self._table
        table.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows):
            accent = row_accent(r)
            dim = _is_debug(r)
            icon = QtWidgets.QTableWidgetItem()
            icon.setIcon(QtGui.QIcon(
                icons.marker(role_glyph(r), 26, accent=accent,
                             sheet=role_sheet(r))))
            table.setItem(i, 0, icon)
            table.setItem(i, 1, self._cell(
                r["name"], theme.DIM if dim else theme.TEXT, bold=True))
            table.setItem(i, 2, self._cell(
                _ROLE_LABELS.get(r["role"], r["role"]), accent))
            table.setItem(i, 3, self._cell(r["place"], theme.DIM))
            table.setItem(i, 4, self._cell(r["zone_tag"], theme.DIM))
            tracked = bool(self._track_mark(r))
            table.setItem(i, 5, self._cell(
                self._row_marks(r),
                theme.ACCENT if tracked else theme.DIM))
            table.setRowHeight(i, self._ROW_H)
        self._fit_table()

    @staticmethod
    def _cell(text: str, color: str, bold: bool = False):
        item = QtWidgets.QTableWidgetItem(text)
        item.setForeground(QtGui.QColor(color))
        if bold:
            f = item.font()
            f.setBold(True)
            item.setFont(f)
        return item

    def _on_cell_clicked(self, index: int, _col: int) -> None:
        if 0 <= index < len(self._rows):
            self.ui._track_npc(self._rows[index])

    # ---- tracking --------------------------------------------------------
    def _track_mark(self, row: dict) -> str:
        return _TRACK_MARK if self.ui._is_npc_tracked(row) else ""

    def art_mark(self, row: dict) -> str:
        """The atlas-gap mark this row shows, '' when the atlas can draw the
        character standing there (see `atlas_cannot_draw`)."""
        return _GAP_MARK if atlas_cannot_draw(row) else ""

    def _row_marks(self, row: dict) -> str:
        """The right-hand cell's text: the atlas-gap mark, then the tracking
        mark, so a row that is both reads as both."""
        return " · ".join(m for m in (self.art_mark(row), self._track_mark(row))
                          if m)

    def refresh_tracked(self) -> None:
        if not self.isVisible():
            return
        for i, r in enumerate(self._rows):
            item = self._table.item(i, 5)
            if item is not None:
                item.setText(self._row_marks(r))
                item.setForeground(QtGui.QColor(
                    theme.ACCENT if self._track_mark(r) else theme.DIM))

    # ---- filters ---------------------------------------------------------
    def toggle_family(self, key: str) -> None:
        """Select one family - the family buttons are one at a time.

        There is no "none" state: the rail's refusal to open onto a blank table
        is why exactly one family is always selected, so clicking the lit button
        re-plots it instead of switching everything off. The click also PLOTS the
        family on the codex map (`_plot_selected_family`), which is the action
        `Pin all Haydn` used to be a button of its own for.

        The click leaves the two diagnostic listings (the debug rows, the
        atlas gap): while either drives the table the newly picked family
        would only light up behind it, so the click looks dead. They are one
        click away to re-enter, and the zones are untouched.
        """
        self._family = key
        self._show_debug = False
        self._noart_only = False
        self._apply()
        self._plot_selected_family()

    def _plot_selected_family(self) -> None:
        """Plot the selected family on the codex map - the family click's second
        half.

        The plain NPC family plots NOTHING: one click there would put every
        trainer, guard and quest-giver in the game on the map at once.
        """
        rows = [] if self._family == "npc" else self.family_rows()
        plot = getattr(self.ui, "_plot_family", None)
        if callable(plot):
            plot(_FAMILY_LABELS.get(self._family, ""), rows)

    def toggle_zone(self, tag: str) -> None:
        """As `toggle_family` for the zones: the last zone that still has rows
        stays on."""
        if tag in self._zones and not self._another_zone_lists(tag):
            self._sync_rail()
            return
        self._zones.symmetric_difference_update({tag})
        self._apply()

    def _another_zone_lists(self, tag: str) -> bool:
        return any(o in self._zones and self._zone_counts.get(o)
                   for o in self._zone_counts if o != tag)

    def toggle_debug(self) -> None:
        """List the dev-only placements, all 14 across every family and zone.

        A listing of its own (like the atlas-gap one), not a per-family
        filter: the dev rows belong to whatever family claims them, so
        revealing only the current family's would strand families that have
        none behind a button that shows nothing. Lit means the 14 debug rows
        are listed; off restores the family view exactly as it was, because
        this never touches the family or the zones.

        Named for what it turns ON, like every other button in this rail. It
        read `Hide debug PTS npcs` and was lit while HIDING them - the one
        option whose light meant the opposite of its neighbours'.
        """
        self._show_debug = not self._show_debug
        self._apply()

    def toggle_noart(self) -> None:
        """Toggle the atlas-gap listing (see `atlas_cannot_draw`).

        On, the table lists every placement the atlas cannot draw, across every
        role and zone: the family and zone filters do not apply to a listing
        whose question is "what is missing from the atlas". Off, those two are
        back exactly as they were left, because this never touched them.
        """
        self._noart_only = not self._noart_only
        self._apply()

    def _apply(self) -> None:
        """The ONE exit every rail button takes: re-light the rail, then
        rebuild the table.

        Every option ends here, so a new option cannot forget to sync its own
        state - which is how a control ends up lit over a table it did not
        filter. A refused toggle re-lights the rail without rebuilding (it
        changed no state), which is what puts the button back on."""
        self._sync_rail()
        self._save_filters()
        self._rebuild()

    def show_family(self, key: str) -> None:
        """Reset the rail onto one family, every zone on, the debug listing off.

        The state the reachability contract walks: with the family buttons one at
        a time, "every placement is still reachable" means the five of them, all
        zones on, plus the debug listing, together list every placement in the
        index. This is the table-side reset and does NOT plot (a click does -
        see `toggle_family`).
        """
        if key in _FAMILY_ORDER:
            self._family = key
        self._zones = {r["zone_tag"] for r in self._all}
        self._show_debug = False
        self._noart_only = False      # a family reset leaves the gap listing
        self._apply()

    # ---- read-only accessors (the table's own shape, for callers and tests)
    def shown_rows(self) -> list[dict]:
        """The rows listed right now, in table order (post filter)."""
        return list(self._rows)

    def track_mark(self, row: dict) -> str:
        """The row's TRACKING mark, '' when it is not tracked.

        Read off the TRACKER rather than off the cell: the cell also carries
        the atlas-gap mark now (`art_mark`), so its text is no longer the
        tracking token on its own."""
        for r in self._rows:
            if r is row:
                return self._track_mark(r)
        return ""

    @property
    def show_debug(self) -> bool:
        return self._show_debug

    @property
    def noart_only(self) -> bool:
        """True while the table lists the atlas gap instead of a family."""
        return self._noart_only

    @property
    def family(self) -> str:
        return self._family

    def rail_option(self, group: str, key: str) -> QtWidgets.QPushButton | None:
        """The rail's own button for one filter, or None.

        The handle a caller or a test uses to CLICK an option, so the check runs
        through the button a user would press rather than the `toggle_*` method
        behind it."""
        return self._rail.get((group, key))

class NpcMixin:
    """Track / plot helpers for the placed-NPC list."""

    def _npc_track_key(self, row: dict) -> str:
        """Tracker waypoint key for an NPC ('x,y,z|name|poi_id').

        The `pos` kind reads exactly this shape (see `ui.tracker._target`),
        and the trailing poi id is what the Entity HUD's waypoint row keys its
        selection on — the same shape a chest/orb row builds.
        """
        return (f"{float(row.get('x', 0.0)):.1f},{float(row.get('y', 0.0)):.1f},"
                f"{float(row.get('z', 0.0)):.1f}|{row.get('name') or row.get('id')}"
                f"|{row.get('id')}")

    def _is_npc_tracked(self, row: dict) -> bool:
        """True when the tracker target is this NPC placement."""
        tr = getattr(getattr(self, "overlay_mgr", None), "tracker", None)
        if tr is None:
            return False
        return tr.is_tracked("pos", self._npc_track_key(row))

    def _track_npc(self, row: dict) -> None:
        """Track an NPC exactly like clicking its minimap marker (compass
        needle + Entity HUD waypoint row), and plot the same spot as a labeled
        pin on the codex map. Click again to stop — the untrack clears the pin
        too, so the second click leaves nothing behind."""
        tr = getattr(getattr(self, "overlay_mgr", None), "tracker", None)
        key = self._npc_track_key(row)
        if tr is None:
            return
        tr.toggle("pos", key)
        if tr.is_tracked("pos", key):
            self._plot_npc_on_map(row)
        else:
            self._clear_codex_map_selection()

    def _plot_npc_on_map(self, row: dict) -> None:
        """Plot one NPC as a labeled pin (their name under the marker) and
        report name + zone in the info line."""
        canvas = self._codex_map_canvas()
        if canvas is None:
            return
        accent = row_accent(row)
        name = row.get("name") or row.get("id") or "NPC"
        canvas.set_multi_pins(name, [{
            "x": row.get("x", 0.0), "y": row.get("y", 0.0),
            "color": QtGui.QColor(accent),
            "name": name,
            "show_label": True,
        }])
        lbl = self._codex_info_label()
        if lbl is not None:
            zone = names.zone_name(row.get("zone")) or ""
            role = _ROLE_LABELS.get(row.get("role") or "", "")
            bits = " · ".join(b for b in (role, zone) if b)
            lbl.setText(f"{name} — {bits}" if bits else name)

    def _plot_family(self, title: str, rows: list[dict]) -> None:
        """Plot one rail family's placements at once - the family click's map
        half.

        Tracking a placement is a needle and an Entity HUD row, which is not what
        "where are the vendors" means: the answer is a map with all of them on
        it. Each pin is labeled with the PLACE it stands in rather than the
        family name, because a dozen pins all reading "Vendor" would be a dozen
        identical labels on top of each other. An empty list CLEARS the family
        pins instead, so the plain NPC family leaves the map as it found it
        rather than still showing the family selected before it.
        """
        canvas = self._codex_map_canvas()
        if canvas is None:
            return
        if not rows:
            canvas.set_multi_pins("", [])
            lbl = self._codex_info_label()
            if lbl is not None:
                lbl.setText("")
            return
        pins = [{
            "x": r.get("x", 0.0), "y": r.get("y", 0.0),
            "color": QtGui.QColor(row_accent(r)),
            "name": r.get("place") or r.get("zone") or "Haydn Seek",
            "show_label": True,
        } for r in rows]
        canvas.set_multi_pins(title, pins)
        lbl = self._codex_info_label()
        if lbl is not None:
            lbl.setText(f"{len(pins)} {title} placements plotted")
