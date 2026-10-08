"""Codex subsystem: enemy filter, soulstone list, jump navigation,
data flow, and species grouping (headless + headless Qt)."""
from farever_companion.data import units


def test_codex_types_exclude_internals():
    ids = {tid for tid, _ in units.codex_types()}
    # nameless internals + non-attackable categories never reach the filter
    for bad in ("Totem", "Environment", "Human", "Mount", "Critter"):
        assert bad not in ids
    # real bestiary types stay
    for good in ("Wolf", "Manfish", "Kobold", "Slime", "Bee", "Golem"):
        assert good in ids


def test_codex_types_have_display_names():
    for tid, name in units.codex_types():
        assert name.strip(), tid
    # sorted by display name
    names_ = [n for _, n in units.codex_types()]
    assert names_ == sorted(names_)


def test_codex_unit_ids():
    ids = units.codex_unit_ids()
    assert len(ids) == len(set(ids))
    ctypes = {tid for tid, _ in units.codex_types()}
    for u in ids:
        # Bosses and uniques are allowed even if their type is internal/nameless
        assert units.unit_type(u) in ctypes or units.is_boss(u) or units.is_unique(u), u
    # templates are excluded, real (even TODO_-prefixed) enemies are not
    assert "BaseMob" not in ids
    assert "Base_Critter" not in ids
    assert "Golem_Base" not in ids
    assert "Crimson_Base" not in ids
    assert "TODO_SnowPanther_White" in ids       # type Wolf, "Snow Leopard"
    # no mounts / totems / companions slip in
    assert not any(units.unit_type(u) in ("Mount", "Totem", "Critter") for u in ids)


def test_type_name():
    assert units.type_name("Manfish") == "Nepsids"
    assert units.type_name("Wolf") == "Wolves"


def test_find_unit_region():
    """find_unit_region resolves a codex card to its region — the lookup
    that powers the Drops From codex jumps."""
    from farever_companion.data import codex
    # the Mount Tamer vendor's card lives on the Others tab
    assert codex.find_unit_region("TODO_StableMaster") == "Z0"
    assert codex.find_unit_region("TODO_Slime_King") == "Z0"
    # non-codex ids (vendor spawn ids, arbitrary strings) never resolve
    assert codex.find_unit_region("MountTamer_NPC_1") is None
    assert codex.find_unit_region("") is None
    assert codex.find_unit_region(None) is None


def test_stable_master_plots_perinas_shop_spots():
    """The Mount Tamer card resolves Perina Wann's real shop coordinates —
    taken from the drop records of the mounts/gliders she sells — instead
    of the todo placeholder's 'No Map Locations'."""
    from farever_companion.data import codex
    coords, title, is_rift = codex.resolve_locations("TODO_StableMaster")
    assert len(coords) == 2
    assert {round(c["x"], 1) for c in coords} == {1218.4, -397.3}
    assert {round(c["y"], 1) for c in coords} == {221.6, 1502.1}
    assert title == "Vendor: Perina Wann (2 Locations)"
    assert is_rift is False


def test_vendor_card_coords_only_for_real_vendors():
    """Plain todo placeholders still resolve to nothing — only the Stable
    Master (whose shop spots the codex data carries on the items she sells)
    gets coordinates. The Wandering Merchant card has no vendor records in
    the codex data, so it stays unplotted."""
    from farever_companion.data import codex
    assert codex.resolve_locations("TODO_Slime_King") == ((), "", False)
    assert codex.resolve_locations("TODO_WanderingMerchant") == ((), "", False)


# The codex placeholder cards the scan must keep (spec rule 7). The app resolves
# them by id, so a missing card silently breaks region / vendor jumps. These
# four lost the `TODO_` prefix on their unit icons in the 2026-10-01 content
# refresh, which is why scan_codex.py names them in `_RENAMED_PLACEHOLDER_STEMS`
# instead of relying on the filename. A later rename that is not added there
# drops the card with no build failure - which is exactly what happened.
_PLACEHOLDER_CARD_IDS = (
    "TODO_StableMaster",
    "TODO_WanderingMerchant",
    "TODO_ProfessionTrainer",
    "TODO_DemonNightgod",
)


def _missing_placeholder_cards(present_ids) -> list[str]:
    """The placeholder ids `present_ids` is missing, in the pinned order."""
    present = set(present_ids)
    return [cid for cid in _PLACEHOLDER_CARD_IDS if cid not in present]


def test_placeholder_cards_survive_a_content_refresh():
    """Every `TODO_*` placeholder card must survive a data refresh.

    They vanish silently when a refresh renames a unit icon out of the `TODO_`
    prefix: the scan stops emitting the card and nothing fails until a lookup
    misses. This pins the four the app knows about so the next rename fails
    HERE with the cause and the fix, instead of surfacing as mystery drift.
    """
    from farever_companion.data import codex
    z0 = {e["id"]: e for e in codex.units_by_region("Z0")}
    missing = _missing_placeholder_cards(z0)
    assert not missing, (
        f"codex placeholder card(s) vanished: {missing}. A content refresh "
        "renamed their unit icons out of the `TODO_` prefix, so scan_codex.py's "
        "`_RENAMED_PLACEHOLDER_STEMS` no longer matches. Add the new stems "
        "there and regenerate assets/data/codex.json.")
    for cid in _PLACEHOLDER_CARD_IDS:
        assert z0[cid].get("type") == "Misc", (cid, z0[cid].get("type"))
        assert z0[cid].get("kind") == "todo", (cid, z0[cid].get("kind"))


def test_the_placeholder_card_guard_actually_detects():
    """Pin the check so it cannot pass vacuously: a full set passes, a set one
    id short reports exactly that id, and an empty set reports all four."""
    assert _missing_placeholder_cards(set(_PLACEHOLDER_CARD_IDS)) == []
    one_short = set(_PLACEHOLDER_CARD_IDS) - {"TODO_StableMaster"}
    assert _missing_placeholder_cards(one_short) == ["TODO_StableMaster"]
    assert _missing_placeholder_cards(set()) == list(_PLACEHOLDER_CARD_IDS)


def test_vendor_sold_glider_plots_only_its_own_spot():
    """A mount/glider card resolves exactly the vendor spot(s) where IT is
    sold — the Almazean Owl sells from one of Perina Wann's two shops, so
    its card plots one pin (this is why the Drops From row jumps to the
    item's card, not the vendor's aggregated one)."""
    from farever_companion.data import codex
    coords, title, is_rift = codex.resolve_locations("Glider_Owl_Brown02")
    assert len(coords) == 1
    assert round(coords[0]["x"], 1) == -397.3
    assert round(coords[0]["y"], 1) == 1502.1
    assert title == "Vendor: Perina Wann"
    assert is_rift is False
    # the wolf (sold from the OTHER shop) pins its own single spot
    coords2, title2, _ = codex.resolve_locations("Mount_Wolf_01")
    assert len(coords2) == 1
    assert round(coords2[0]["x"], 1) == 1218.4
    assert round(coords2[0]["y"], 1) == 221.6
    assert title2 == "Vendor: Perina Wann"


# ======================================================================
# test_codex_soulstone_list
# ======================================================================

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6 import QtCore, QtWidgets  # noqa: E402

from farever_companion.data import codex  # noqa: E402
from farever_companion.ui.pages.codex.map_ui import CodexMapUiMixin  # noqa: E402
from farever_companion.ui.pages.codex.soulstones import (  # noqa: E402
    SoulstoneListView, SoulstoneMixin)


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    """One offscreen QApplication for the whole module (widgets need one)."""
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _Tracker(QtCore.QObject):
    changed = QtCore.Signal()

    def __init__(self, tracked=()):
        super().__init__()
        self._tracked = set(tracked)
        self.toggled = []

    def is_tracked(self, kind, key):
        return (kind, key) in self._tracked

    def toggle(self, kind, key):
        self.toggled.append((kind, key))


class _ToggleTracker(QtCore.QObject):
    """Tracker that really toggles: first click tracks, second untracks."""

    changed = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self._target = None

    def is_tracked(self, kind, key):
        return self._target == (kind, key)

    def toggle(self, kind, key):
        if self.is_tracked(kind, key):
            self._target = None
        else:
            self._target = (kind, key)
        self.changed.emit()


class _FakeMapWidget:
    """Minimal stand-in for CodexZoneMapCanvas: records the plotted pins."""

    def __init__(self):
        self.pins = []
        self.selected = ""

    def set_multi_pins(self, label, pins):
        self.pins = list(pins or [])
        self.selected = label

    def set_selected_mob(self, name, coords, item=None):
        self.pins = list(coords or [])
        self.selected = name


class _Label:
    def __init__(self):
        self.text = ""

    def setText(self, t):
        self.text = t


class _UntrackPage(SoulstoneMixin, CodexMapUiMixin):
    """Page with the real track handlers: toggles the tracker and plots /
    clears the map pin."""

    def __init__(self, tracker):
        self.overlay_mgr = _Ov(tracker)
        self.s = _Settings()
        self.model = None
        self._codex_map_widget = _FakeMapWidget()
        self._map_info_lbl = _Label()
        self._last_codex_item = None
        self._zone_pins_active = False
        self.clears = 0

    def _clear_codex_map_selection(self):
        self.clears += 1
        self._codex_map_widget.pins = []


class _Ov:
    def __init__(self, tracker):
        self.tracker = tracker


class _Settings:
    hud_accent = "#38bdf8"
    track_kind = ""
    track_id = ""


class _FakePage:
    """Minimal page: the attributes SoulstoneListView touches plus the track
    handlers it wires the cells to."""

    def __init__(self, zone="All", tracker=None):
        self._dungeon_zone = zone
        self.s = _Settings()
        self.overlay_mgr = _Ov(tracker or _Tracker())
        self.tracked = []

    def _is_soulstone_tracked(self, poi):
        tr = self.overlay_mgr.tracker
        from farever_companion.ui.pages.codex.soulstones import SoulstoneMixin
        key = SoulstoneMixin._soulstone_track_key(self, poi)
        return tr.is_tracked("soulstone", key)

    def _track_soulstone(self, poi):
        self.tracked.append(poi)


def test_list_renders_all_eight_summon_spots():
    """All 8 soulstone bosses render as rows with their boss name and summon
    zone (the dungeon-list shape: name + sub-line)."""
    page = _FakePage()
    view = SoulstoneListView(page)
    assert view.row_count == 8
    names = [c.poi["name"] for c in view._cells]
    assert "Ariana Grandemon" in names and "Baphometal" in names
    assert len(set(names)) == 8
    # sub-line shows the summon zone, not the raw zone id
    sub = view._cells[0]._sub_lbl.text()
    assert sub and "Z1_" not in sub and "Z2_" not in sub


def test_cell_has_no_tooltip():
    """Flat rows with a subtle hover: the Soulstones list deliberately shows
    no tooltips (the summon cost used to be the hover text, but the rows are
    plain text rows now), so every cell hovers empty."""
    view = SoulstoneListView(_FakePage())
    for cell in view._cells:
        assert cell.toolTip() == "", cell.toolTip()


def test_zone_filter_slices_the_list():
    """The Dungeons-tab zone keys (All / Z1 / Z2) filter the summon spots by
    zone — Z1 has 4, Z2 has 4."""
    z1 = SoulstoneListView(_FakePage(zone="Z1"))
    z2 = SoulstoneListView(_FakePage(zone="Z2"))
    assert z1.row_count == 4
    assert z2.row_count == 4
    from farever_companion.data import dungeons
    for c in z1._cells:
        assert dungeons.zone_tag_from_zone_id(c.poi.get("zone") or "") == "Z1"
    for c in z2._cells:
        assert dungeons.zone_tag_from_zone_id(c.poi.get("zone") or "") == "Z2"


def test_cell_click_tracks_and_plots_the_summon_spot():
    """Clicking a row fires the page's _track_soulstone with that spot, so the
    real page toggles the minimap-style tracker and plots the labeled pin."""
    page = _FakePage()
    view = SoulstoneListView(page)
    cell = view._cells[0]
    cell.pick.emit(cell.poi)
    assert page.tracked and page.tracked[0]["id"] == cell.poi["id"]


def test_tracked_row_shows_tracking_label():
    """A spot the tracker already targets renders its '◈ TRACKING' row, like
    the dungeon list's tracked cells."""
    key = SoulstoneMixin._soulstone_track_key(_FakePage(), codex.soulstone_pois()[0])
    page = _FakePage(tracker=_Tracker(tracked=[("soulstone", key)]))
    view = SoulstoneListView(page)
    # isHidden(), not isVisible(): the list is never shown in the test, so a
    # widget only reports its own explicit visibility state.
    assert not view._cells[0]._track_lbl.isHidden()
    assert view._cells[1]._track_lbl.isHidden()


def test_untrack_soulstone_clears_pin():
    """Clicking a tracked soulstone row again stops tracking AND clears the
    labeled pin from the codex map — the second click leaves nothing."""
    tracker = _ToggleTracker()
    page = _UntrackPage(tracker)
    poi = codex.soulstone_pois()[0]
    key = SoulstoneMixin._soulstone_track_key(page, poi)

    page._track_soulstone(poi)
    assert tracker.is_tracked("soulstone", key)
    assert len(page._codex_map_widget.pins) == 1
    assert page._codex_map_widget.pins[0]["name"] == poi["name"]

    page._track_soulstone(poi)
    assert not tracker.is_tracked("soulstone", key)
    assert page.clears >= 1
    assert page._codex_map_widget.pins == []


def test_dungeon_cell_tooltip_shows_only_extra_info():
    """Dungeon rows already show boss + level · name on the row, so the
    hover tooltip keeps only the extra info: the rift tracking note, the
    missing-entrance explanation, or nothing at all."""
    from farever_companion.data import dungeons
    from farever_companion.ui.pages.codex.dungeon_list import (
        DungeonListCell, DungeonListView)
    page = _UntrackPage(_ToggleTracker())
    view = DungeonListView(page)
    # normal dungeons: everything is already on the row -> no tooltip
    plain = [c for c in view._cells
             if c.dungeon.get("entrance_zone") != "Rifts" and c.key]
    assert plain
    for c in plain:
        assert c.toolTip() == "", c.toolTip()
    # rifts: the row can't show that it tracks the live/next-due rift
    rifts = [c for c in view._cells if c.dungeon.get("entrance_zone") == "Rifts"]
    assert rifts
    for c in rifts:
        tip = c.toolTip()
        assert "tracks the active rift" in tip.lower(), tip
        assert c._sub_lbl.text() not in tip, tip
    # a row with no resolvable entrance explains why it's dimmed
    d = dungeons.load_dungeons()[0]
    cell = DungeonListCell(page, d, None)
    assert "no entrance location found" in cell.toolTip().lower()


def test_dungeon_list_hides_rows_that_name_no_dungeon():
    """The dungeon list is the only surface that renders EVERY payload row, so
    it used to show the boss-less POI `Z1_POI_Dungeon_ManfishGeyser` - no name,
    no boss, no entrance zone, no location, only a level - as a bare `?  Lv 10`.
    A row that names nothing is not a dungeon the app can show or track, and the
    rows that do name one are listed exactly as before."""
    from farever_companion.data import dungeons
    from farever_companion.ui.pages.codex.dungeon_list import DungeonListView

    # the rule itself, on the row's own shape (independent of today's payload)
    assert not dungeons.is_listable(
        {"id": "Z1_POI_Dungeon_ManfishGeyser", "kind": "dungeon", "level": 10,
         "ambient": "Default", "faction": "Manfish", "flags": 32})
    # a name, a boss id or a boss name is enough to be listed
    assert dungeons.is_listable({"id": "x", "name": "Cheese Station"})
    assert dungeons.is_listable({"id": "x", "boss_id": "Nepsilon"})
    assert dungeons.is_listable({"id": "x", "boss_name": "Nepsilon"})

    rows = dungeons.load_dungeons()
    listed_ok = {d["id"] for d in rows if dungeons.is_listable(d)}
    view = DungeonListView(_UntrackPage(_ToggleTracker()))
    listed = {c.dungeon["id"] for c in view._cells}
    assert listed == listed_ok
    assert len(view._cells) == len(listed_ok)
    # the reported row is not a cell, whether or not a rebuild ships it again
    assert "Z1_POI_Dungeon_ManfishGeyser" not in listed
    # and no cell is left rendering the '?' placeholder as its boss line
    for c in view._cells:
        assert c.dungeon.get("boss_name") or c.dungeon.get("boss_id") \
            or c.dungeon.get("name"), c.dungeon["id"]


def test_untrack_dungeon_clears_pin():
    """Same toggle behavior on the Dungeon List: the second click on a
    tracked dungeon row untracks it and clears its entrance pin."""
    from farever_companion.data import dungeons
    tracker = _ToggleTracker()
    page = _UntrackPage(tracker)
    d = next((dd for dd in dungeons.load_dungeons()
              if dd.get("entrance_zone") != "Rifts"
              and page._dungeon_track_key(dd) is not None), None)
    assert d is not None
    kind, key = page._dungeon_track_key(d)

    page._track_dungeon(d)
    assert tracker.is_tracked(kind, key)
    assert len(page._codex_map_widget.pins) == 1

    page._track_dungeon(d)
    assert not tracker.is_tracked(kind, key)
    assert page.clears >= 1
    assert page._codex_map_widget.pins == []


def test_each_rift_row_tracks_the_gate_in_its_own_zone():
    """Both rifts resolve to BOTH gates (they share the one "Rifts" entrance
    zone), so `coords[0]` is always the Z2 Krisomal gate: every rift row used
    to track and pin that same spot, putting the Z1 rift in the wrong zone.
    Each rift row must track the gate in its own zone."""
    from farever_companion.data import dungeons
    from farever_companion.geo import pois as geo_pois

    page = _UntrackPage(_Tracker())
    rifts = [d for d in dungeons.load_dungeons()
             if d.get("entrance_zone") == "Rifts"]
    assert len(rifts) == 2

    keys = {}
    for d in rifts:
        got = page._dungeon_track_key(d)
        assert got is not None, d["id"]
        kind, key = got
        assert kind == "rift"
        keys[d["id"]] = key

    # Two rifts, two different gates — not one shared pin.
    assert len(set(keys.values())) == len(rifts), keys
    for d in rifts:
        zone = dungeons.zone_tag(d)
        gate = next(p for p in geo_pois.load_pois()
                    if p.sub_kind == "rift"
                    and dungeons.zone_tag_from_zone_id(p.zone or "") == zone)
        assert keys[d["id"]].split("|")[-1] == gate.id, (d["id"], keys[d["id"]])
        assert keys[d["id"]].split("|")[0] == \
            f"{float(gate.x):.1f},{float(gate.y):.1f},{float(gate.z):.1f}"


# ======================================================================
# test_codex_jump
# ======================================================================

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from farever_companion.ui.pages.codex.map_ui import CodexMapUiMixin  # noqa: E402
from farever_companion.ui.pages.codex.soulstones import SoulstoneMixin  # noqa: E402


class _FakeCard(QtCore.QObject):
    selected = QtCore.Signal(str)

    def __init__(self, uid: str):
        super().__init__()
        self.uid = uid


class _FakeScroll:
    def __init__(self):
        self._body = QtWidgets.QWidget()
        self.ensured = []

    def widget(self):
        return self._body

    def ensureWidgetVisible(self, w, xmargin=0, ymargin=0):
        self.ensured.append(w)


class _FakeBtn:
    def __init__(self, checked=False):
        self._checked = checked

    def setChecked(self, on):
        self._checked = bool(on)

    def isChecked(self):
        return self._checked

    def blockSignals(self, _on):
        return False


class _FakeTabs:
    def __init__(self):
        self._text = ""

    def setCurrentText(self, t):
        self._text = t

    def currentText(self):
        return self._text

    def blockSignals(self, _on):
        return False


class _FakeSearch:
    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text

    def setText(self, t):
        self._text = t

    def blockSignals(self, _on):
        return False


class _FakeDungeonList:
    def __init__(self, cells=None):
        self._cells = list(cells or [])

    def layout(self):
        return None


class _FakeSubBtn:
    """Collection sub-view button: records clicks (the real handler refreshes
    the grid, which the fake page's refresh already covers)."""

    def __init__(self, label):
        self.label = label
        self.clicks = 0

    def click(self):
        self.clicks += 1


class _FakeSoulstoneCell(QtCore.QObject):
    pick = QtCore.Signal(object)

    def __init__(self, poi):
        super().__init__()
        self.poi = poi
        self.picked = []
        self.pick.connect(lambda p: self.picked.append(p))


class _FakeSoulstoneList:
    def __init__(self, pois):
        self._cells = [_FakeSoulstoneCell(p) for p in pois]


class _FakeChestCell(QtCore.QObject):
    pick = QtCore.Signal(object)

    def __init__(self, cid):
        super().__init__()
        self.item = {"id": cid}
        self.picked = []
        self.pick.connect(lambda it: self.picked.append(it))


class _FakeChestList:
    def __init__(self, ids):
        self._cells = [_FakeChestCell(i) for i in ids]


class _FakeJumpPage(CodexMapUiMixin, SoulstoneMixin):
    """Minimal page: provides just the attributes _codex_jump_to_unit and
    friends touch; _refresh_codex_grid renders the stored cards."""

    def __init__(self, cards):
        self._nav = None
        self._codex_tabs = _FakeTabs()
        self._codex_scroll = _FakeScroll()
        self._cards = list(cards)
        self._codex_cards = []
        self._clicks = []
        self._map_clears = 0
        for c in self._cards:
            c.selected.connect(lambda uid: self._clicks.append(uid))
        self._dungeon_list_mode = True
        self._chest_orb_kind = None

    def _select_nav(self, key):
        self._nav = key

    def _refresh_codex_grid(self, reset_scroll=False):
        self._codex_cards = list(self._cards)

    def _clear_codex_map_selection(self):
        self._map_clears += 1


def _mk(uid: str):
    return _FakeCard(uid)


def test_vendor_jump_lands_on_others_tab_and_clicks_card():
    """Perina Wann (a vendor) jumps to the Others tab and clicks the Stable
    Master card like a real user."""
    page = _FakeJumpPage([_mk("TODO_StableMaster"), _mk("TODO_Slime_King")])
    page._codex_jump_to_unit("TODO_StableMaster", "Perina Wann")
    QtCore.QCoreApplication.processEvents()
    assert page._nav == "codex"
    assert page._codex_tabs.currentText() == "Other"
    assert page._dungeon_list_mode is False
    assert page._clicks == ["TODO_StableMaster"]
    assert page._codex_scroll.ensured \
        and page._codex_scroll.ensured[0].uid == "TODO_StableMaster"
    assert page._map_clears == 1


def test_zone_mob_jump_lands_on_its_region_tab():
    """A world mob (Krabby Jacob on Z1) lands on the Z1 zone tab and clicks
    its card — no Others/Collection sub-view juggling needed."""
    page = _FakeJumpPage([_mk("Crawler_Z1W_E")])
    page._codex_jump_to_unit("Crawler_Z1W_E", "Krabby Jacob")
    QtCore.QCoreApplication.processEvents()
    assert page._codex_tabs.currentText() == "Skover Island"  # Z1 region tab
    assert page._clicks == ["Crawler_Z1W_E"]


def test_dungeon_list_falls_back_to_card_grid():
    """A dungeon mob that isn't a dungeon-list row (no boss row matches)
    switches to the mobs card grid and clicks its card."""
    page = _FakeJumpPage([_mk("RobinHoofDog01")])
    page._codex_dungeon_list = _FakeDungeonList()   # no matching row
    page._btn_dungeon_mobs = _FakeBtn()
    page._btn_dungeon_list = _FakeBtn()
    page._dungeon_list_mode = True
    page._codex_click_unit("RobinHoofDog01", "Crimson Hunting Dog")
    QtCore.QCoreApplication.processEvents()
    assert page._dungeon_list_mode is False
    assert page._btn_dungeon_mobs.isChecked()
    assert page._btn_dungeon_list.isChecked() is False
    assert page._clicks == ["RobinHoofDog01"]


def test_mount_jump_lands_on_collection_mounts_and_clicks_card():
    """A mount item's VIEW IN CODEX link lands on the Collection tab's
    Mounts sub-view and clicks the mount's card like a real user."""
    page = _FakeJumpPage([_mk("Mount_Goat_01")])
    page._collection_sub_btns = {lbl: _FakeSubBtn(lbl)
                                 for lbl in ("Pets", "Mounts", "Gliders",
                                             "Chests", "Orbs")}
    page._codex_jump_to_unit("Mount_Goat_01", "Goat")
    QtCore.QCoreApplication.processEvents()
    assert page._nav == "codex"
    assert page._codex_tabs.currentText() == "Collection"
    assert page._collection_sub_btns["Mounts"].clicks == 1
    assert page._clicks == ["Mount_Goat_01"]
    assert page._codex_scroll.ensured \
        and page._codex_scroll.ensured[0].uid == "Mount_Goat_01"


def test_soulstone_jump_lands_on_dungeons_soulstones_and_clicks_row():
    """A soulstone demon boss (Ariana Grandemon — no codex card of her own)
    lands on the Dungeons tab's Soulstones list and clicks her summon-spot
    row like a real user."""
    from farever_companion.data import codex
    page = _FakeJumpPage([])
    page._btn_dungeon_soulstones = _FakeBtn()
    poi = next(p for p in codex.soulstone_pois()
               if p["spawn_unit"] == "FaerieDemon_Z1_Soulstone_Leg")
    page._codex_soulstone_list = _FakeSoulstoneList([poi])
    page._codex_jump_to_unit("FaerieDemon_Z1_Soulstone_Leg", "Ariana Grandemon")
    QtCore.QCoreApplication.processEvents()
    assert page._nav == "codex"
    assert page._codex_tabs.currentText() == "Dungeons"
    assert page._btn_dungeon_soulstones.isChecked()
    cell = page._codex_soulstone_list._cells[0]
    assert cell.picked and cell.picked[0]["id"] == poi["id"]
    assert page._codex_scroll.ensured \
        and page._codex_scroll.ensured[0] is cell


def test_chest_jump_lands_on_collection_chests_and_clicks_row():
    """A single-chest drop source lands on the Collection tab's Chests view
    and clicks the chest's row (tracks it + plots it like a manual click)."""
    page = _FakeJumpPage([])
    page._collection_sub_btns = {lbl: _FakeSubBtn(lbl)
                                 for lbl in ("Pets", "Mounts", "Gliders",
                                             "Chests", "Orbs")}
    page._zone_widgets = {"All": _FakeBtn(checked=True)}
    page._codex_chest_list = _FakeChestList(
        ["W1_Siagarta_WorldChest_54", "VaultChest_1"])
    page._codex_jump_to_unit("W1_Siagarta_WorldChest_54",
                             "W1_Siagarta_WorldChest_54 (x2)")
    QtCore.QCoreApplication.processEvents()
    assert page._nav == "codex"
    assert page._codex_tabs.currentText() == "Collection"
    assert page._collection_sub_btns["Chests"].clicks == 1
    cell = page._codex_chest_list._cells[0]
    assert cell.picked and cell.picked[0]["id"] == \
        "W1_Siagarta_WorldChest_54"
    assert page._codex_scroll.ensured \
        and page._codex_scroll.ensured[0].item["id"] == \
        "W1_Siagarta_WorldChest_54"


def test_jump_clears_filters_that_could_hide_the_card():
    """A stale search query, the spark toggle and source-badge filters are
    cleared before the jump so the target card can't be hidden."""
    page = _FakeJumpPage([_mk("TODO_StableMaster")])
    page._codex_search = _FakeSearch("stable")
    page._status_widgets = {"All": _FakeBtn(checked=True)}
    page._spark_only = True
    page._spark_filter_btn = _FakeBtn(checked=True)
    page._source_filters = {"npc"}
    page._source_filter_btns = {"npc": _FakeBtn(checked=True)}
    page._codex_reset_jump_filters()
    assert page._codex_search.text() == ""
    assert page._spark_only is False
    assert page._spark_filter_btn.isChecked() is False
    assert page._source_filters == set()
    assert page._source_filter_btns["npc"].isChecked() is False


# ======================================================================
# test_codex_data
# ======================================================================

from farever_companion.data import codex


def test_all_regions_compiled():
    d = codex.codex_order()
    assert {"Z1", "Z2", "Z3", "Mounts", "Gliders", "Pets", "Z0", "Bosses"} <= set(d)
    for rid in ("Z1", "Z2", "Z3", "Mounts", "Gliders", "Pets", "Bosses"):
        assert len(d[rid]) > 40, rid
    assert len(d["Z0"]) >= 25


def test_schema_fields_survive_compilation():
    d = codex.codex_order()
    # species families for pets/mounts
    assert any(e.get("group") for e in d["Pets"])
    assert any(e.get("group") for e in d["Mounts"])
    # world source metadata
    assert any(e.get("vendor_npc") for e in d["Gliders"])
    assert any(e.get("chest_loc") for e in d["Mounts"])
    # Z0 misc carries locked kind flags (todo / unreleased)
    assert any(e.get("kind") for e in d["Z0"])


def test_units_by_region_z0_merges_mounts_and_gliders():
    z0 = codex.units_by_region("Z0")
    ids = {e["id"] for e in z0}
    assert any(i.startswith("Mount_") for i in ids)
    assert any(i.startswith("Glider_") for i in ids)
    # every entry has a resolvable display name
    assert all(e.get("name") for e in z0)


def test_others_all_excludes_released_mounts_gliders():
    """The Others tab is the 'no home yet' bucket: cash-shop items,
    unreleased content, and todo placeholders. Released mounts/gliders
    (world drops and achievement rewards) belong on the Collection tab, so
    the Others 'All' sub-view must not include them."""
    d = codex.codex_order()

    # Every released / achievement mount & glider is excluded from Others...
    for zone in ("Mounts", "Gliders"):
        for e in d[zone]:
            k = (e.get("kind") or "").lower()
            if k in ("unreleased", "todo"):
                continue  # not released yet — belongs in Others
            # shop items are buyable NOW, so they stay in Others (Shop view)
            if codex.is_shop_item(e):
                assert codex.belongs_in_others(e), e["id"]
            else:
                assert not codex.belongs_in_others(e), e["id"]

    # ...and the merged Z0 rows the Others tab renders carry only shop /
    # unreleased / todo rows once the released mounts & gliders are removed.
    others_all = [e for e in codex.units_by_region("Z0") if codex.belongs_in_others(e)]
    assert others_all
    for e in others_all:
        assert (codex.is_shop_item(e)
                or (e.get("kind") or "").lower() in ("unreleased", "todo")
                or "todo" in (e.get("id") or "").lower()
                or "todo" in (e.get("name") or "").lower()), e["id"]
    # released mounts/gliders are exactly the rows Others drops
    dropped = [e for e in codex.units_by_region("Z0") if not codex.belongs_in_others(e)]
    assert dropped
    assert all((e.get("kind") or "").lower() not in ("unreleased", "todo")
               for e in dropped)


def test_pets_grouped_by_species():
    pets = codex.units_by_region("Pets")
    species = {p.get("type") for p in pets}
    assert len(species) >= 5, species          # not one flat "Critter" group
    assert "Critter" not in species


def test_z0_mounts_gliders_carry_species_group():
    """Mounts/gliders keep their compiled `group` family on the merged Z0
    rows so the Collection Mounts/Gliders views can sub-header by species
    family just like Pets does."""
    z0 = codex.units_by_region("Z0")
    mounts = [e for e in z0 if e["id"].startswith("Mount_")]
    gliders = [e for e in z0 if e["id"].startswith("Glider_")]
    assert mounts and gliders
    # every collectible mount/glider row carries a species family
    assert all(e.get("group") for e in mounts), [e["id"] for e in mounts if not e.get("group")]
    assert all(e.get("group") for e in gliders), [e["id"] for e in gliders if not e.get("group")]
    # the families are meaningful — several distinct groups, not one flat bucket
    assert len({e["group"] for e in mounts}) >= 5
    assert len({e["group"] for e in gliders}) >= 5


def test_units_by_region_no_duplicates():
    for rid in codex.codex_order():
        ids = [e["id"] for e in codex.units_by_region(rid)]
        assert len(ids) == len(set(ids)), rid


def test_bosses_carry_dungeon_metadata():
    bosses = codex.units_by_region("Bosses")
    assert any(e.get("is_dungeon") for e in bosses)
    assert any(e.get("level") for e in bosses)


def test_enemies_data_merges_cdb_and_codex_keys():
    info = codex.enemies_data()
    assert len(info) > 100
    # a raw_codex entry enriched over the CDB row keeps both key styles
    m = next((v for v in info.values() if v.get("vendor_npc")), {})
    assert m and "id" in m and "name" in m


def test_bosses_resolve_via_compile_time_dungeon_loc():
    """Dungeon mobs carry the entrance location baked in, so the resolver is a
    direct lookup instead of a per-click POI fuzzy search."""
    bosses = codex.units_by_region("Bosses")
    d_entries = [e for e in bosses if e.get("dungeon_loc")]
    assert d_entries, "compiler should stamp dungeon_loc on dungeon mobs"
    # every dungeon-marked mob resolves to its entrance coords
    for e in d_entries[:25]:
        coords, title, _ = codex.resolve_locations(e["id"])
        assert coords, e["id"]
        assert title, e["id"]


def test_mounts_gliders_resolve_via_drops_from_or_vendor_chest():
    """Mounts/gliders carry their drop-mob links (or vendor/chest sources) so
    the resolver is a dict lookup, not a full enemies_data scan."""
    d = codex.codex_order()
    linked = [e for e in d["Mounts"] + d["Gliders"]
              if e.get("drops_from") or e.get("vendor_npc") or e.get("chest_loc")
              or e.get("dungeon_loc") or e.get("coords")]
    assert len(linked) >= 90, len(linked)
    # every non-todo/unreleased mount/glider resolves to map coords
    # (achievement-only rewards are coords-less by design — they resolve to
    # their achievement title instead)
    for zone in ("Mounts", "Gliders"):
        resolvable = [e for e in d[zone]
                      if (e.get("kind") or "").lower() not in ("todo", "unreleased", "achievement")]
        assert resolvable
        for e in resolvable:
            coords, _t, _r = codex.resolve_locations(e["id"])
            assert coords, (zone, e["id"])
    # drops_from references real enemies (dungeon mobs resolve via dungeon_loc,
    # wild mobs via embedded spawn coords)
    resolved = [e for e in d["Mounts"] + d["Gliders"] if e.get("drops_from")]
    assert resolved
    for e in resolved[:10]:
        for df in e["drops_from"]:
            assert df["id"] in codex.enemies_data(), (e["id"], df["id"])


def test_rift_reward_items_resolve_to_arena():
    """Rift reward tables (Rift_Tier6 / Rift_BonusChest / Rift_Bosschest) are
    anchored at the rift arena entrance, so rift-sourced mounts/gliders get a
    real location instead of being locked as unreleased."""
    d = codex.codex_order()
    rift_items = [e for e in d["Mounts"] + d["Gliders"]
                  if (e.get("chest_id") or "").startswith("Rift_")
                  or (e.get("dungeon_name") or "") in ("Rift Arena", "Rift")]
    assert rift_items, "no rift-sourced mounts/gliders in the codex"
    for e in rift_items:
        # never locked as unreleased once it has a rift source
        assert (e.get("kind") or "").lower() not in ("todo", "unreleased"), e["id"]
        coords, title, _r = codex.resolve_locations(e["id"])
        assert coords, e["id"]
        assert title, e["id"]
    # the tier-6 glider (Niflelian Dragoon) is the canonical regression
    dragoon = next((e for e in d["Gliders"] if e["id"] == "Glider_Dragon_Demon"), None)
    assert dragoon, "Glider_Dragon_Demon (Rift_Tier6) missing from Gliders"
    coords, title, _r = codex.resolve_locations(dragoon["id"])
    assert coords and title, dragoon["id"]


def test_achievement_rewards_stamp_source_info():
    """Mounts/gliders awarded by achievements (ach.json rewards) carry the
    achievement baked into the compiled codex, so the source shows instead of
    a blank 'unreleased' card."""
    d = codex.codex_order()
    by_id = {e["id"]: e for e in d["Mounts"] + d["Gliders"]}
    goat = by_id.get("Mount_Goat_04")
    assert goat, "Crimson Goat (Savior of Skover reward) missing"
    assert goat.get("achievement", {}).get("name") == "Savior of Skover"
    assert goat["achievement"]["category"] == "Combat"
    assert goat["achievement"]["points"] == 10
    # achievement rewards are obtainable in-game — never mislabeled unreleased
    assert goat.get("kind") == "achievement"
    assert (goat.get("kind") or "").lower() not in ("todo", "unreleased")
    # desc resolves the same [Z1_Region] placeholders as the name
    assert goat["achievement"]["desc"] == "Complete all the Dungeons in Skover Island."
    # [Z1_Region] style placeholders resolve to the region name
    bestiary = by_id.get("Mount_Goat_05")
    assert bestiary.get("achievement", {}).get("name") == "Bestiary of Skover Island"
    owl = by_id.get("Glider_Owl_BlackWarm")
    assert owl.get("achievement", {}).get("name") == "Collector of Skover Island"
    # collection-count milestones have no display name in ach.json — the
    # compiler derives one from the id ('CollectMounts_10' -> 'Collect Mounts 10')
    # and resolves the ::targetValue:: template token from the same id
    boar = by_id.get("Mount_Boar_05")
    assert boar.get("achievement", {}).get("name") == "Collect Mounts 10"
    assert boar["achievement"]["desc"] == "Collect 10 Mounts."


def test_achievement_sources_resolve_as_titles_not_locations():
    """Achievement-sourced mounts have no map coords (achievements are
    meta-goals, not spawns) but the resolver reports the achievement as the
    source title so the map label shows where the item comes from."""
    coords, title, _r = codex.resolve_locations("Mount_Goat_04")
    assert not coords
    assert title == "Achievement · Savior of Skover"
    coords, title, _r = codex.resolve_locations("Mount_Goat_05")
    assert not coords
    assert title == "Achievement · Bestiary of Skover Island"


def test_achievement_only_items_not_flagged_unreleased():
    """The compiler reflags achievement-only rewards (no world coords) from
    codex.json's 'unreleased' to 'achievement' — an achievement reward IS
    obtainable in-game, so calling it unreleased would be wrong. World-drop
    mounts that also carry an achievement keep their real spawn coords."""
    d = codex.codex_order()
    flagged = [e for e in d["Mounts"] + d["Gliders"]
               if (e.get("kind") or "").lower() == "unreleased" and e.get("achievement")]
    assert not flagged, [e["id"] for e in flagged]
    # the two cohorts stay distinct: achievement-only (no coords) vs drop (coords)
    only = [e for e in d["Mounts"] + d["Gliders"]
            if (e.get("kind") or "").lower() == "achievement"]
    drops = [e for e in d["Mounts"] + d["Gliders"]
             if e.get("achievement") and e.get("coords")]
    assert only, "achievement-only cohort empty"
    assert drops, "drop+achievement cohort empty"
    assert all(not e.get("coords") for e in only)
    assert all((e.get("kind") or "") not in ("todo", "unreleased") for e in drops)


def test_soulstone_dropped_mounts_resolve_to_summon_spots():
    """Mounts/gliders dropped by the soulstone demon bosses (the Niflelian
    family) plot exactly their 4 summon spots — never every species sibling.

    The soulstone bosses (Ariana Grandemon, Baphometal, ...) carry no coords
    of their own; the resolver reads their spots from the poi_locs dataset.
    Before the fix the Niflelian Skunk fell through to the species-group
    fallback and pinned all 7 'Skunk'-named entities (the other skunk mounts
    included); the demon crab/bat/wingfish painted 301/133/40 pins the same
    way."""
    from farever_companion.data import raw_data
    ss = {p["spawn_unit"]: p["world_pos"]
          for p in (raw_data.DATA.get("poi_locs") or [])
          if p.get("sub_kind") == "soulstone" and p.get("spawn_unit")}
    cases = {
        # Z1 soulstone family (Ariana Grandemon, Baphometal, Belzebeat,
        # Luciferrari)
        "Mount_Skunk_06": ("FaerieDemon_Z1_Soulstone_Leg",
                            "Demon_Z1_Claws_Soulstone",
                            "ImpDemon_Z1_Soulstone",
                            "Demon_Z1_Spear_Soulstone"),
        "Glider_FlyingFish_Demon": ("FaerieDemon_Z1_Soulstone_Leg",
                                     "Demon_Z1_Claws_Soulstone",
                                     "ImpDemon_Z1_Soulstone",
                                     "Demon_Z1_Spear_Soulstone"),
        # Z2 soulstone family (Asmodeaf, Kristian Belial, Lilithium,
        # Mortalkombaal)
        "Mount_Crab_Demonic": ("ImpDemon_Z2_Soulstone",
                                "Demon_Z2_Spear_Soulstone_Leg",
                                "FaerieDemon_Z2_Soulstone",
                                "Demon_Z2_Claws_Soulstone"),
        "Glider_Bat_Demon": ("ImpDemon_Z2_Soulstone",
                              "Demon_Z2_Spear_Soulstone_Leg",
                              "FaerieDemon_Z2_Soulstone",
                              "Demon_Z2_Claws_Soulstone"),
    }
    for uid, droppers in cases.items():
        coords, title, _ = codex.resolve_locations(uid)
        # exactly the 4 soulstone summon spots, in their world positions
        assert len(coords) == 4, (uid, len(coords))
        expected = {(round(ss[d]["x"], 1), round(ss[d]["y"], 1))
                    for d in droppers}
        got = {(round(c["x"], 1), round(c["y"], 1)) for c in coords}
        assert got == expected, (uid, got, expected)
        assert title.startswith("Mob Drop:"), (uid, title)
        # each pin carries its boss name so the map can label it
        names = sorted(p.get("name") for p in coords)
        expected_names = sorted(codex.enemies_data()[d]["name"] for d in droppers)
        assert names == expected_names, (uid, names, expected_names)


def test_soulstone_pois_carry_summon_metadata():
    """The soulstone_pois accessor exposes the 8 demon-boss summon spots with
    their world positions, zones, and costs — the Dungeons tab's Soulstones
    list reads this (the resolver's soulstone fallback reads the same rows)."""
    pois = codex.soulstone_pois()
    assert len(pois) == 8
    for p in pois:
        assert p.get("name") and p.get("spawn_unit") and p.get("id")
        wp = p.get("world_pos") or {}
        assert "x" in wp and "y" in wp, p
        assert p.get("zone", "").startswith("Z"), p
        assert p.get("cost_item"), p
    # every summon spot is a real enemies_data boss the resolver can name
    ed = codex.enemies_data()
    for p in pois:
        assert ed[p["spawn_unit"]]["name"] == p["name"], p


def test_z0_todo_unreleased_short_circuit():
    """todo/unreleased entries resolve no locations from the fallback chain —
    the resolver returns empty immediately instead of guessing. The one
    deliberate exception is the vendor NPC cards (`codex._VENDOR_NPC_UNITS`):
    their coords come from the items they sell, not from a world spawn, which
    test_vendor_card_coords_only_for_real_vendors pins from the other side."""
    z0 = codex.units_by_region("Z0")
    flagged = [e for e in z0 if (e.get("kind") or "").lower() in ("todo", "unreleased")]
    assert flagged
    vendor_cards = set(codex._VENDOR_NPC_UNITS)
    for e in flagged[:15]:
        coords, _title, _rift = codex.resolve_locations(e["id"])
        if e["id"] in vendor_cards:
            continue
        assert not coords, e["id"]


def test_resolver_coverage_is_lookup_driven():
    """Almost every resolvable entry gets coords; only genuinely sourceless
    entries (todo/unreleased, one known pet) stay empty — never a fuzzy POI
    guess that pins the wrong dungeon."""
    d = codex.codex_order()
    unresolved = []
    for entries in d.values():
        for e in entries:
            if (e.get("kind") or "").lower() in ("todo", "unreleased", "achievement"):
                continue
            coords, _t, _r = codex.resolve_locations(e["id"])
            if not coords:
                unresolved.append(e["id"])
    # Brawler Benoit used to fuzzy-pin to Crimson Barracks (a dungeon it does
    # not belong to) — now codex.json supplies his spawn next to Brawler Brahim.
    # Zone mobs without recorded spawn coords stay empty too: the species-group
    # fallback must never misread the zone tag in their id ('Z1W' in the Kobold
    # ids) as a mob family, which used to paint every zone-tagged mob's spawns
    # as 'Mob Drop: Z2W Mobs (83 Species)'. ('OgreManfish_Z2W_FS_Claws' was the
    # original motivating example; it is now a drop-source-only mob, no longer
    # a codex entry, so it cannot appear here — the Kobold pair still exercises
    # the guard end to end.) The early-access Sparktail pet stays empty too:
    # it's a cash-shop item (its `group` is just the Collection species-family
    # header, not a drop family), so the fallback must not paint every Rabbit
    # mob's spawns for a pet you buy.
    #
    # Set comparison (not list order): the exact order these unresolved ids
    # surface in depends on the compiled shim's zone ordering, which can
    # legitimately change when the shims are rebuilt from the current
    # codex.json — the coverage (these four, no more) is what matters.
    assert set(unresolved) == {"Kobold_Z1W_Caster", "Kobold_Z1W_Daggers",
                               "Rabbit_EarlyAccess_Spark", "YellowRabbits"}, unresolved


# ======================================================================
# test_codex_grouping
# ======================================================================

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtCore, QtWidgets  # noqa: E402

from farever_companion.data import codex  # noqa: E402
from farever_companion.ui.pages.codex.grid import CodexGridMixin  # noqa: E402
from farever_companion.ui.pages.codex.grouping import CodexGroupingMixin  # noqa: E402


class _FakeSettings:
    """Settings stub: hidden companion set drives the Visible/Hidden counts."""

    def __init__(self, hidden_comps=()):
        self.codex_compact = False
        self.codex_pets_compact = True
        self._hidden_comps = set(hidden_comps)

    def get_companion_hidden_units(self, profile):
        return self._hidden_comps

    def get_entity_hidden_units(self, profile):
        return set()


class _FakeGridPage(QtCore.QObject, CodexGridMixin, CodexGroupingMixin):
    """Minimal page: just enough of the grid pipeline for the grouping tests."""

    def __init__(self):
        super().__init__()
        self.s = _FakeSettings()
        self.model = None
        self._body = QtWidgets.QWidget()
        self._codex_grid = QtWidgets.QGridLayout(self._body)
        self._codex_cards = []

    def _set_companion_hidden(self, *_a, **_k):
        pass

    def _set_unit_hidden(self, *_a, **_k):
        pass

    def _on_codex_mob_selected(self, *_a, **_k):
        pass

    def _codex_is_collection_view(self, current_rid, tab_label):
        return current_rid in ("Pets", "Z0", "Mounts", "Gliders") \
            or tab_label in ("Others", "Other", "Pets", "Collection",
                             "Mounts", "Gliders")

    def _codex_current_region(self):
        return getattr(self, "_cur_rid", "Z1"), getattr(self, "_cur_tab", "Skover Island")


def _sub_view_items(page, sub_tag):
    """Z0 rows the Collection sub-view actually renders (unreleased excluded)."""
    return [it for it in codex.units_by_region("Z0", ingame_order=True)
            if page._codex_collection_ok(it, sub_tag)]


def _group_key(it: dict, sub_tag: str) -> str:
    """The grouping key the page actually renders for `it`: the species
    family for pets / the compiled `group` for mounts & gliders — except
    cash-shop / early-access items, which group under the general 'Shop'
    family instead of masquerading as a species (SparkHorse_01 -> 'Shop',
    not 'Spark Horse'). Mirrors _codex_sub_group / _codex_group_counts."""
    if codex.is_shop_item(it):
        return "Shop"
    return (it.get("type") if sub_tag == "pets" else it.get("group") or "").strip()


def _rendered_header_labels(page):
    """Top-level QLabel widgets in the grid = the sub-header rows."""
    labels = []
    for i in range(page._codex_grid.count()):
        w = page._codex_grid.itemAt(i).widget()
        if isinstance(w, QtWidgets.QLabel):
            labels.append(w.text())
    return labels


def test_sub_group_key_family_vs_type_bucket():
    """The shared grouping key: species family on Collection mounts/gliders,
    raw type everywhere else (Pets species, Bosses dungeon, Z0 Others)."""
    page = _FakeGridPage()
    assert page._codex_sub_group({"type": "Mount", "group": "Aries"}, "Z0", True) == "Aries"
    assert page._codex_sub_group({"type": "Mount"}, "Z0", True) == "Mount"   # group-less fallback
    assert page._codex_sub_group({"type": "Mount", "group": "Aries"}, "Z0", False) == "Mount"
    assert page._codex_sub_group({"type": "Rabbit"}, "Pets", False) == "Rabbit"
    assert page._codex_sub_group({"type": "Crimson Sacristy"}, "Bosses", False) == "Crimson Sacristy"


def test_group_label_pretty_prints_camelcase():
    page = _FakeGridPage()
    assert page._codex_group_label("Aries") == "Aries"
    assert page._codex_group_label("FlyingFish") == "Flying Fish"
    assert page._codex_group_label("SparkHorse") == "Spark Horse"


@pytest.mark.parametrize("sub_tag", ["mounts", "gliders"])
def test_collection_sort_and_render_group_by_family(sub_tag):
    """Mounts/Gliders sort by species family and render one sub-header per
    family (mirroring Pets' species headers) on the Collection views."""
    page = _FakeGridPage()
    items = _sub_view_items(page, sub_tag)
    assert items
    matches = [(it["id"], it, True, True, 0) for it in items]
    page._sort_codex_matches(matches, "Z0", "ALL", "", collection_tab=True)

    groups = [_group_key(m[1], sub_tag) for m in matches]
    assert groups == sorted(groups)                      # families stay contiguous
    assert len(set(groups)) >= 5, groups

    page._render_codex_region("Z0", sub_tag.capitalize(), matches, 0,
                              False, "ALL", "Pets", True)
    labels = _rendered_header_labels(page)
    assert labels, "no sub-headers rendered"
    assert sorted(set(labels)) == sorted(labels)         # one header per family
    assert set(labels) == {page._codex_group_label(g).upper() for g in groups}
    # camelCase families read as spaced words ('FlyingFish' -> 'FLYING FISH')
    if "FlyingFish" in groups:
        assert "FLYING FISH" in labels
    # cash-shop items render under one general SHOP header, never a species
    # family ('Spark Horse') that makes a shop mount look farmable
    if "Shop" in groups:
        assert "SHOP" in labels


def test_pets_headers_use_spaced_species_labels():
    """Pets species sub-headers read as spaced words ('DEMON DOG',
    'STINK BUG') — the same labels as the group sub-menu, matching the
    Mounts/Gliders family headers."""
    page = _FakeGridPage()
    items = codex.units_by_region("Pets")
    matches = [(it["id"], it, True, True, 0) for it in items]
    page._sort_codex_matches(matches, "Pets", "ALL", "", collection_tab=True)
    page._render_codex_region("Pets", "Pets", matches, 0, False, "ALL", "Pets", True)
    labels = _rendered_header_labels(page)
    species = list(dict.fromkeys(_group_key(it, "pets") for it in items))
    assert set(labels) == {page._codex_group_label(s).upper() for s in species}
    if "DemonDog" in species:
        assert "DEMON DOG" in labels
    if "StinkBug" in species:
        assert "STINK BUG" in labels


def test_others_z0_still_buckets_by_type():
    """The Others tab keeps its Mounts/Gliders/Misc type buckets — species
    families only group the Collection Mounts/Gliders views."""
    page = _FakeGridPage()
    items = [it for it in codex.units_by_region("Z0", ingame_order=True)
             if codex.belongs_in_others(it)]
    matches = [(it["id"], it, True, False, 0) for it in items]
    page._sort_codex_matches(matches, "Z0", "ALL", "", collection_tab=False)
    types = [page._codex_type_header("Z0", m[1].get("type")) for m in matches]
    assert types == sorted(types)
    page._render_codex_region("Z0", "Other", matches, 0, False, "ALL", "Z0", False)
    labels = _rendered_header_labels(page)
    assert labels
    assert all(l in ("MOUNTS", "GLIDERS", "MISC") for l in labels)


def test_group_counts_match_rendered_families():
    """The group sub-menu's All + family buttons cover exactly the families
    the current sub-view renders (order = in-game order), with counts equal
    to the cards each family actually renders (summing to the ZONE TOTAL)."""
    page = _FakeGridPage()
    for sub_tag in ("pets", "mounts", "gliders"):
        counts = page._codex_group_counts(sub_tag)
        assert counts, sub_tag
        keys = [k for k, _c in counts]
        assert "All" not in keys
        items = (codex.units_by_region("Pets") if sub_tag == "pets"
                 else _sub_view_items(page, sub_tag))
        rendered = [_group_key(it, sub_tag) for it in items]
        assert set(keys) == set(rendered), sub_tag
        for key, count in counts:
            assert count == rendered.count(key), (sub_tag, key)
        assert sum(c for _k, c in counts) == len(items)   # sums to the total


def test_group_bar_buttons_show_family_counts():
    """The rebuilt sub-menu labels read 'Family (count)' — e.g. 'Wolf (6)' —
    and 'All (total)', keyed by the raw family so filtering still works."""
    page = _FakeGridPage()
    page._build_codex_group_sub_bar()
    page._rebuild_codex_group_bar("mounts")
    counts = dict(page._codex_group_counts("mounts"))
    assert page._group_sub_btns["All"].text() == f"All ({sum(counts.values())})"
    wolf = page._group_sub_btns.get("Wolf")
    assert wolf is not None
    assert wolf.text() == f"Wolf ({counts['Wolf']})"
    assert wolf.property("groupKey") == "Wolf"
    # cash-shop mounts use one general Shop chip instead of a species family
    # ('Spark Horse (1)' is gone — the shop horse reads as a shop item)
    assert "SparkHorse" not in page._group_sub_btns
    shop = page._group_sub_btns.get("Shop")
    assert shop is not None
    assert shop.text() == f"Shop ({counts['Shop']})"
    assert shop.property("groupKey") == "Shop"


def test_the_collection_family_bar_wraps_six_to_a_row():
    """The family bar is two tidy lines, not one row that wraps where the
    window ends.

    Pets holds twelve keys (All + eleven families: StinkBug, Frog, Turtle,
    Squirrel, DemonDog, Goat, Sheep, Ladybug, Lizard, Rabbit, Shop), which read
    as one long row and re-flowed whenever the window changed width. It is a
    fixed six-wide grid now: the first six keys are the first line, the seventh
    starts the second, and a chip never moves because the window moved. Mounts
    (14) and Gliders (12) share the same six so all three sub-views break at the
    same place.
    """
    page = _FakeGridPage()
    page._build_codex_group_sub_bar()
    for sub_tag, expected in (("pets", 12), ("gliders", 12), ("mounts", 14)):
        page._rebuild_codex_group_bar(sub_tag)
        lay = page._group_sub_lay
        assert lay.count() == expected, sub_tag
        keys = ["All"] + [k for k, _c in page._codex_group_counts(sub_tag)]
        assert len(keys) == expected, sub_tag
        cells = {lay.getItemPosition(lay.indexOf(page._group_sub_btns[k]))[:2]
                 for k in keys}
        assert cells == {(i // 6, i % 6) for i in range(expected)}, sub_tag
        # read in order, the keys land six to a line
        assert [lay.getItemPosition(lay.indexOf(page._group_sub_btns[k]))[:2]
                for k in keys] == [(i // 6, i % 6) for i in range(expected)], \
            sub_tag


def test_group_counts_follow_visible_hidden_status():
    """The chip counts respect the Visible/Hidden status filter: VISIBLE
    counts active cards per family, HIDDEN counts hidden ones, ALL counts
    everything. Zero-count families stay listed (chips don't reflow), and
    Nearby keeps full family sizes."""
    page = _FakeGridPage()
    all_counts = dict(page._codex_group_counts("mounts", "ALL"))
    # a Wolf mounting that is NOT a shop item: shop-sold mounts group under
    # the general 'Shop' family, so hiding one would move the Shop count, not
    # Wolf's (the species family this test is about).
    wolf = next(it for it in _sub_view_items(page, "mounts")
                if it.get("group") == "Wolf" and not codex.is_shop_item(it))
    page.s = _FakeSettings(hidden_comps={wolf["id"]})

    visible = dict(page._codex_group_counts("mounts", "VISIBLE"))
    hidden = dict(page._codex_group_counts("mounts", "HIDDEN"))
    assert visible["Wolf"] == all_counts["Wolf"] - 1
    assert hidden["Wolf"] == 1
    assert visible["Aries"] == all_counts["Aries"]      # untouched family
    assert set(hidden) == set(all_counts)                  # zero-count chips stay
    assert sum(hidden.values()) == 1
    # Nearby treats the counts as ALL
    assert dict(page._codex_group_counts("mounts", "NEARBY")) == all_counts
    # pets hide through the same companion namespace
    pet = codex.units_by_region("Pets")[0]
    page.s = _FakeSettings(hidden_comps={pet["id"]})
    pets_all = dict(page._codex_group_counts("pets", "ALL"))
    pets_vis = dict(page._codex_group_counts("pets", "VISIBLE"))
    assert pets_vis[pet["type"]] == pets_all[pet["type"]] - 1


def test_group_bar_rebuilds_chip_counts_on_status_change():
    """Switching the Visible/Hidden status filter re-renders the chip counts
    (and the All total) without losing the active family selection."""
    page = _FakeGridPage()
    page._build_codex_group_sub_bar()
    page._collection_sub = "mounts"
    # non-shop Wolf mount (shop-sold ones join the 'Shop' family, above)
    wolf = next(it for it in _sub_view_items(page, "mounts")
                if it.get("group") == "Wolf" and not codex.is_shop_item(it))
    page.s = _FakeSettings(hidden_comps={wolf["id"]})

    all_counts = dict(page._codex_group_counts("mounts", "ALL"))
    page._sync_codex_group_bar("Pets", "Collection", "ALL")
    assert page._group_sub_btns["All"].text() == f"All ({sum(all_counts.values())})"
    assert page._group_sub_btns["Wolf"].text() == f"Wolf ({all_counts['Wolf']})"

    page._sync_codex_group_bar("Pets", "Collection", "HIDDEN")
    assert page._group_sub_btns["Wolf"].text() == "Wolf (1)"
    assert page._group_sub_btns["All"].text() == "All (1)"

    # selecting a family survives the status switch
    page._codex_group_filter = "Wolf"
    page._sync_codex_group_bar("Pets", "Collection", "VISIBLE")
    assert page._codex_group_filter == "Wolf"
    assert page._group_sub_btns["Wolf"].isChecked()
    assert page._group_sub_btns["Wolf"].text() \
        == f"Wolf ({all_counts['Wolf'] - 1})"


def test_group_chip_toggles_off_when_reclicked():
    """Clicking an already-active family chip unselects it (back to All),
    so a filter can be cleared without clicking the All chip itself."""
    page = _FakeGridPage()
    page._build_codex_group_sub_bar()
    page._collection_sub = "mounts"
    page._sync_codex_group_bar("Pets", "Collection", "ALL")
    page._refresh_codex_grid = lambda **kw: None   # just record the filter
    wolf = page._group_sub_btns["Wolf"]

    wolf.click()                                    # select the family
    assert page._codex_group_filter == "Wolf"
    assert wolf.isChecked()
    assert not page._group_sub_btns["All"].isChecked()

    wolf.click()                                    # click it again: toggle off
    assert page._codex_group_filter == "All"
    assert page._group_sub_btns["All"].isChecked()
    assert not wolf.isChecked()

    # switching straight to another family still works
    page._group_sub_btns["Aries"].click()
    assert page._codex_group_filter == "Aries"
    page._group_sub_btns["All"].click()
    assert page._codex_group_filter == "All"


def _fake_status_widgets(page):
    """Minimal shared status chips (All/Nearby/Visible/Hidden), keyed like
    the real control bar (labels carry a statusKey property, not the key)."""
    page._status_btns = QtWidgets.QButtonGroup(page)
    page._status_btns.setExclusive(True)
    page._status_widgets = {}
    for lbl in ("All", "Nearby", "Visible", "Hidden"):
        btn = QtWidgets.QPushButton(lbl)
        btn.setCheckable(True)
        btn.setProperty("statusKey", lbl)
        page._status_btns.addButton(btn)
        page._status_widgets[lbl] = btn
    return page


def test_status_counts_reconcile_with_hidden_set():
    """(all, visible, hidden) totals reconcile: all == visible + hidden, and
    hiding a card moves it from visible to hidden across sub-views."""
    page = _FakeGridPage()
    total, visible, hidden = page._codex_status_counts("mounts")
    assert total == visible + hidden
    assert hidden == 0
    wolf = next(it for it in _sub_view_items(page, "mounts")
                if it.get("group") == "Wolf")
    page.s = _FakeSettings(hidden_comps={wolf["id"]})
    total2, vis2, hid2 = page._codex_status_counts("mounts")
    assert total2 == total
    assert vis2 == visible - 1
    assert hid2 == 1
    # 'all' merges the three sub-views
    merged = page._codex_status_counts("all")
    singles = [page._codex_status_counts(t) for t in ("pets", "mounts", "gliders")]
    assert merged[0] == sum(s[0] for s in singles)
    assert merged[1] == sum(s[1] for s in singles)


def test_status_chips_show_visible_hidden_counts():
    """On the Collection card-grid views the shared status chips read
    'All (total)' / 'Visible (n)' / 'Hidden (m)' (Nearby stays plain); the
    filter key still resolves through the statusKey property despite the
    count labels, and other tabs restore the plain labels."""
    page = _fake_status_widgets(_FakeGridPage())
    page._collection_sub = "mounts"
    page._build_codex_group_sub_bar()

    page._update_codex_status_chips("Pets", "Collection")
    total, visible, hidden = page._codex_status_counts("mounts")
    assert page._status_widgets["All"].text() == f"All ({total})"
    assert page._status_widgets["Visible"].text() == f"Visible ({visible})"
    assert page._status_widgets["Hidden"].text() == f"Hidden ({hidden})"
    assert page._status_widgets["Nearby"].text() == "Nearby"

    # the count-styled labels never become the filter key
    page._status_widgets["Hidden"].setChecked(True)
    _q, status = page._codex_filter_state()
    assert status == "HIDDEN"
    page._status_widgets["All"].setChecked(True)
    _q, status = page._codex_filter_state()
    assert status == "ALL"

    # hiding a card moves one unit from Visible to Hidden on the chips
    wolf = next(it for it in _sub_view_items(page, "mounts")
                if it.get("group") == "Wolf")
    page.s = _FakeSettings(hidden_comps={wolf["id"]})
    page._update_codex_status_chips("Pets", "Collection")
    assert page._status_widgets["Visible"].text() == f"Visible ({visible - 1})"
    assert page._status_widgets["Hidden"].text() == f"Hidden ({hidden + 1})"

    # Chests/Orbs lists restore the plain labels
    page._chest_orb_kind = "chests"
    page._update_codex_status_chips("Pets", "Collection")
    assert page._status_widgets["All"].text() == "All"
    assert page._status_widgets["Visible"].text() == "Visible"
    page._chest_orb_kind = None


def test_status_chips_show_counts_on_mobs_and_others_tabs():
    """The shared status chips also carry All/Visible/Hidden totals on the
    open-world zone tabs and the Others tab (counts match the region's
    rendered cards), while the Dungeons tab — where the status block is
    replaced by zone filters — restores the plain labels."""
    page = _fake_status_widgets(_FakeGridPage())
    page._cur_rid = "Z1"
    page._cur_tab = "Skover Island"

    # zone/Mobs tab: counts cover the region's cards exactly
    page._update_codex_status_chips("Z1", "Skover Island")
    total, visible, hidden = page._codex_tab_status_counts("Z1")
    assert total == len(codex.units_by_region("Z1"))
    assert page._status_widgets["All"].text() == f"All ({total})"
    assert page._status_widgets["Visible"].text() == f"Visible ({visible})"
    assert page._status_widgets["Hidden"].text() == f"Hidden ({hidden})"
    assert page._status_widgets["Nearby"].text() == "Nearby"
    assert total == visible + hidden

    # hiding a mob moves one card from Visible to Hidden on the chips
    mob = codex.units_by_region("Z1")[0]
    page.s = _FakeSettings()
    page.s.get_entity_hidden_units = lambda profile: {mob["id"]}
    page._update_codex_status_chips("Z1", "Skover Island")
    assert page._status_widgets["Visible"].text() == f"Visible ({visible - 1})"
    assert page._status_widgets["Hidden"].text() == f"Hidden ({hidden + 1})"

    # Others tab counts its own rows
    page._update_codex_status_chips("Z0", "Other")
    ot, ov, oh = page._codex_tab_status_counts("Z0")
    assert page._status_widgets["All"].text() == f"All ({ot})"
    assert page._status_widgets["Hidden"].text() == f"Hidden ({oh})"
    assert ot == ov + oh

    # Dungeons swaps in the zone filters -> plain labels restored
    page._update_codex_status_chips("Bosses", "Dungeons")
    assert page._status_widgets["All"].text() == "All"
    assert page._status_widgets["Visible"].text() == "Visible"
    assert page._status_widgets["Hidden"].text() == "Hidden"

def test_unit_icon_reads_the_cards_own_art_key():
    """A codex card names its atlas sprite in `icon`; for the `TODO_*`
    placeholder cards that is the ONLY usable key (the id names the card,
    not the art). Without this the Drops From rows drew the raw `TODO_` id
    and hit no atlas entry, so a weapon vendor's row showed a placeholder
    box instead of their face."""
    from farever_companion.data import codex
    assert codex.unit_icon("TODO_WanderingMerchant") == "WanderingMerchant"
    assert codex.unit_icon("TODO_StableMaster") == "StableMaster"
    # an id with no card, or a card with no icon, falls back to the id
    assert codex.unit_icon("DemonHunterMira") == "DemonHunterMira"
    assert codex.unit_icon("") == ""
    assert codex.unit_icon(None) == ""


# ======================================================================
# test_codex_npc_list  — the Other tab's 'NPC' filter
# ======================================================================

from farever_companion.geo import pois as geo_pois  # noqa: E402
from farever_companion.ui.pages.codex.npc_list import (  # noqa: E402
    NpcListView, NpcMixin, npc_rows)


class _NpcPage(NpcMixin, CodexMapUiMixin):
    """Page with the real NPC track/plot handlers plus the map stand-ins.

    `settings` is the real `Settings` in the persistence test; the rail only
    touches `s` through `hasattr` guards, so the stub is enough everywhere else.
    """

    def __init__(self, tracker=None, settings=None):
        self.overlay_mgr = _Ov(tracker or _Tracker())
        self.s = settings if settings is not None else _Settings()
        self.model = None
        self._codex_map_widget = _FakeMapWidget()
        self._map_info_lbl = _Label()
        self._last_codex_item = None
        self._zone_pins_active = False


def test_npc_rows_are_every_placed_npc_not_just_the_shops():
    """The list is EVERY placed NPC: one row per poi_locs placement of the
    npc / vendor / petshop families. The plain `npc` rows are the point — the
    compiler used to drop them, so nothing rendered the trainers and quest
    NPCs at all."""
    rows = npc_rows()
    index = geo_pois.load_npc_pois()
    assert rows and len(rows) == len(index)
    assert {r["id"] for r in rows} == {p.id for p in index}
    roles = {r["role"] for r in rows}
    assert roles <= {"npc", "vendor", "petshop", "mountshop"}
    assert roles >= {"npc", "vendor", "petshop"}
    assert [r for r in rows if r["role"] == "npc"], \
        "the plain world NPCs must be listed, not only the shop families"
    # placements, not characters: one character id per zone, so a character
    # standing in many zones is many rows, and none owns a codex card
    assert len({r["name"] for r in rows}) < len(rows)
    assert any(codex.find_unit_region(r["id"]) is None for r in rows)
    for r in rows:
        assert r["zone_tag"] in ("Z1", "Z2", "Z3", "Other")


def test_npc_rows_are_zone_ordered_z1_then_z2_then_z3():
    """Rows arrive zone-blocked in the world's own order so the zone headers
    read Z1 … Z2 … Z3 … (anything untagged last)."""
    order = {"Z1": 0, "Z2": 1, "Z3": 2, "Other": 3}
    rows = npc_rows()
    seq = [order[r["zone_tag"]] for r in rows]
    assert seq == sorted(seq)
    assert {"Z1", "Z2", "Z3"} <= {r["zone_tag"] for r in rows}


def test_npc_list_can_reach_every_placement_and_lists_them_zone_ordered():
    """The directory lists every placement, in zone -> place -> name order.

    The family rail is ONE at a time, so "every placement is still reachable"
    means walking all five family buttons with every zone on and the dev rows
    shown - the union of what they list is the whole index. These rows have no
    other surface anywhere in the app, so "a placement is simply gone" must never
    become true without a red test.
    """
    order = {"Z1": 0, "Z2": 1, "Z3": 2, "Other": 3}
    rows = npc_rows()
    view = NpcListView(_NpcPage())
    assert view.show_debug is False
    # the shipped default is Haydn Seek: the plain NPC family is not on
    assert view.family == "haydn"

    seen = set()
    for family in ("vendor", "petshop", "mountshop", "npc", "haydn"):
        view.show_family(family)
        assert view.show_debug is False
        here = view.shown_rows()
        assert here, family
        if family == "npc":
            assert not any(r["name"] == "Haydn Seek" for r in here)
        seq = [order[r["zone_tag"]] for r in here]
        assert seq == sorted(seq), family
        seen |= {r["id"] for r in here}
    # ...plus the debug listing, which owns the dev-only rows outright
    view.toggle_debug()
    here = view.shown_rows()
    assert len(here) == 14, len(here)
    assert all("(debug)" in r["name"] for r in here)
    seen |= {r["id"] for r in here}
    assert seen == {r["id"] for r in rows}
    assert {"Z1", "Z2", "Z3"} <= {r["zone_tag"] for r in rows}
def test_the_default_npc_view_lists_haydn_and_hides_the_dev_rows():
    """The shipped default is Haydn Seek — all ten placements, every zone on,
    the dev-only rows hidden, and nothing else.

    Haydn leads because his ten spots are the reason this list gets opened at
    all; the shop families are one click away rather than on by themselves.
    """
    view = NpcListView(_NpcPage())
    assert view.family == "haydn"
    shown = {(r["name"], r["zone"]) for r in view.shown_rows()}
    assert shown
    assert len(shown) == 10, len(shown)
    for r in npc_rows():
        expect = r["name"] == "Haydn Seek" and "(debug)" not in r["name"]
        assert ((r["name"], r["zone"]) in shown) is expect, r["name"]


def test_opening_the_npc_list_plots_haydns_pins_on_the_map():
    """The opening family arrives plotted, like its button had been clicked:
    Haydn's ten pins land on the codex map with the build, not after it."""
    page = _NpcPage()
    view = NpcListView(page)
    assert view.family == "haydn"
    assert len(page._codex_map_widget.pins) == 10, \
        page._codex_map_widget.pins
    assert page._codex_map_widget.selected == "Haydn Seek", \
        page._codex_map_widget.selected
def test_the_table_sits_at_the_top_of_its_pane_not_floating_in_the_middle():
    """The rows belong at the top of the pane, right under the column headers.

    The RAIL is what decides how tall the pane is (five families + three zones +
    the view toggle is ~360px), so the table's column is usually far taller than
    the rows in it - the mount shops are two. Without a trailing stretch the
    layout has nowhere to put that surplus and Qt centers the table in the
    column, so a short family opened with a blank band above its first row, sized
    by the rail. Found on the real page: with the mount shops selected the table
    sat 135px down inside a 357px pane, and the two-row table read as an empty
    list with one row's worth of rows floating under the middle.
    """
    view = NpcListView(_NpcPage())
    view.rail_option("role", "mountshop").click()
    view.show()
    try:
        view.resize(700, 360)          # the pane the rail's own height gives it
        QtCore.QCoreApplication.processEvents()
        assert view.row_count == 2
        assert view._table.y() <= 1, \
            f"the table floats {view._table.y()}px below the top of its pane"
        assert view._table.height() < view.height(), \
            "the fixture is only meaningful while the pane is taller than the rows"
    finally:
        view.hide()
        view.deleteLater()
        QtCore.QCoreApplication.processEvents()


def test_npc_rows_draw_their_own_marker_and_accent_not_one_shared_npc():
    """Every role reads its own art off the shipped atlas, in its own colour.

    The roles used to share one `npc` person and one gold, then one `shop` sprite
    for all three shop counters, then whatever the minimap sheet had spare (`bell`
    for the pet counter, the Overlays page's `crosshair` for the mount tamer).
    They read the NPCs' OWN sprites now, and both sheets come with the app, so a
    frozen build draws every one of them with no loose art on disk:

    - the MINIMAP sheet for the NPC-ish roles: the plain person (`npc`) and
      Haydn's `npc_bubble`, the two sprites the game's own map draws for them;
    - the UNITS sheet for the three shop counters, where the NPCs' art lives:
      `wanderingmerchant` (the Guild Merchant), `demonhunterzoey` (Zoey, who
      keeps the pet stands in all three zones) and `stablemaster` (the mount
      stands' keeper).

    The MOUNT TAMER still has no sprite of his OWN: `mounttamer`, `tamer` and
    `perina` appear nowhere in the atlas - not among its 1632 unit entries, not
    anywhere else. What the mount shop reads instead is the game's ONLY
    mount-keeper unit, which the unit table files as a Human named "Guild
    Merchant": `StableMaster`. The day a tamer sprite lands the probe list below
    goes red and says to use it - as it did for the collection sheet's creature
    that used to stand in here.

    The three shop COLOURS are not this list's own either: they are
    `theme.KIND_COLOR`'s, the same table the minimap's kiosk rings read
    (`minimap_render.poi_pixmap`), so the directory and the map agree by
    construction instead of by two lists kept in step by hand.
    """
    from farever_companion.data import atlas
    from farever_companion.data import cdb
    from farever_companion.data import icons
    from farever_companion.ui import theme
    from farever_companion.ui.pages.codex.npc_list import (
        role_art, role_glyph, role_sheet, row_accent)

    plain_npc = {"role": "npc", "name": "Rita Von Cheese"}
    haydn = {"role": "npc", "name": "Haydn Seek"}
    vendor = {"role": "vendor", "name": "Guild Merchant"}
    petshop = {"role": "petshop", "name": "Zoey, Demon Huntress"}
    mountshop = {"role": "mountshop", "name": "Perina Wann"}
    sample = [plain_npc, vendor, petshop, mountshop, haydn]

    # four roles, four colours - plus Haydn's own
    accents = [row_accent(r) for r in sample]
    assert len(set(accents)) == len(accents) == len(sample), accents

    assert role_art(plain_npc) == ("minimap", "npc")
    assert role_art(vendor) == ("units", "wanderingmerchant")
    assert role_art(petshop) == ("units", "demonhunterzoey")
    assert role_art(haydn) == ("minimap", "npc_bubble")
    # the mount shop's sprite is the game's own mount keeper, not a gap and not
    # a creature: `mounttamer`/`tamer`/`perina` is still nowhere in the atlas, so
    # the day one lands this probe list goes RED and says to use it.
    for probe in ("mounttamer", "mounttamer_npc_1", "tamer", "perina",
                  "perinawann"):
        assert atlas.find_entry(None, probe) is None, \
            f"the atlas has {probe} now: use it for the mount shop"
    assert role_art(mountshop) == ("units", "stablemaster")
    # ... and the unit table really does call that unit the mount keeper
    stable = [m for m in cdb.lines("units")
              if m.get("id") == "StableMaster"]
    assert len(stable) == 1, stable
    assert stable[0].get("type") == "Human"

    # the art the three counters read is really on the units sheet
    for name in ("wanderingmerchant", "demonhunterzoey", "stablemaster"):
        assert atlas.find_entry("units", name) is not None, name

    # the shop family is three different pictures, not three copies of one
    shops = [vendor, petshop, mountshop]
    assert len({role_glyph(r) for r in shops}) == 3
    assert len({row_accent(r) for r in shops}) == 3, \
        "the shop family must not be one gold"

    # the shop colours are the kind table's, so the map's kiosks and these rows
    # are the same three colours rather than two palettes in sync by accident
    shop_colours = {theme.KIND_COLOR[k]
                    for k in ("vendor", "petshop", "mountshop")}
    assert len(shop_colours) == 3, theme.KIND_COLOR
    for role in ("vendor", "petshop", "mountshop"):
        assert row_accent({"role": role, "name": "x"}) == theme.KIND_COLOR[role]
    assert row_accent(plain_npc) not in shop_colours

    # every sprite resolves on the sheet its role names, and a marker really
    # draws: five roles over FIVE places in the atlas, one each
    cells = {}
    for r in sample:
        entry = atlas.find_entry(role_sheet(r), role_glyph(r))
        assert entry is not None, (role_sheet(r), role_glyph(r))
        cells[role_glyph(r)] = (entry["file"], entry["x"], entry["y"])
        pm = icons.marker(role_glyph(r), 26, accent=row_accent(r),
                          sheet=role_sheet(r))
        assert not pm.isNull(), (r["role"], role_glyph(r))
    assert len(set(cells.values())) == 5, cells


def test_every_family_button_draws_the_sprite_its_rows_do():
    """The rail's family buttons carry the same art their rows draw.

    The rail was text-only, so the one thing that tells the roles apart (the
    sprite) was invisible until you scrolled to the rows. Each family button has
    its sprite now, at the rail's own size: the Guild Merchant, the pet-shop
    keeper and the mount keeper off the units sheet, the plain person and Haydn's
    bubble off the minimap sheet - five buttons, five different sprites. The zone
    buttons are filters rather than places and stay text-only, and the PTS debug
    button takes the plain NPC sprite its rows draw.

    A family button is the FAMILY's sprite, not its rows': the rail answers "what
    kind of place is this", so the plain-NPC button draws the plain person even
    though ten of its rows draw Hilda Lambert's own face - that the buttons stay
    five distinct pictures is the point.
    """
    from farever_companion.data import icons
    from farever_companion.ui.pages.codex.npc_list import role_glyph, role_sheet

    view = NpcListView(_NpcPage())
    keys = {}
    for family in ("vendor", "petshop", "mountshop", "npc", "haydn"):
        btn = view.rail_option("role", family)
        assert not btn.icon().isNull(), family
        pm = btn.icon().pixmap(16, 16)
        assert (pm.width(), pm.height()) == (16, 16), family
        keys[family] = pm.cacheKey()
    assert len(set(keys.values())) == 5, \
        "two family buttons draw the same atlas sprite"

    assert view._family_art("vendor") == ("units", "wanderingmerchant")
    assert view._family_art("petshop") == ("units", "demonhunterzoey")
    assert view._family_art("mountshop") == ("units", "stablemaster")
    assert view._family_art("npc") == ("minimap", "npc")
    assert view._family_art("haydn") == ("minimap", "npc_bubble")
    # ... and a button draws exactly the sprite its rows draw, minus the ring. The
    # row is a REAL placement, id and all, so this covers the row-level resolution
    # as well as the role default: both have to land on the same atlas cell.
    row = {"id": "DemonHuntZoey_NPC_Azuram", "role": "petshop",
           "name": "Zoey, Demon Huntress"}
    assert view.rail_option("role", "petshop").icon().pixmap(16, 16).toImage() \
        == icons.marker(role_glyph(row), 16, sheet=role_sheet(row)).toImage()
    # the mount shop's own placement follows the same rule
    mount_row = {"id": "MountTamer_NPC_1", "role": "mountshop",
                 "name": "Perina Wann"}
    assert view.rail_option("role", "mountshop").icon().pixmap(16, 16).toImage() \
        == icons.marker(role_glyph(mount_row), 16,
                        sheet=role_sheet(mount_row)).toImage()

    assert view.rail_option("view", "debug").icon().pixmap(16, 16).toImage() \
        == view.rail_option("role", "npc").icon().pixmap(16, 16).toImage(), \
        "the PTS debug button draws the plain NPC sprite its rows draw"
    for tag in ("Z1", "Z2"):
        assert view.rail_option("zone", tag).icon().isNull(), \
            "the zone buttons are filters, not places: they stay text-only"
def test_every_placement_draws_the_character_the_unit_table_gives_it():
    """The whole shipped directory: 85 placements, 38 characters, and which of
    them the atlas can draw.

    A row is a PLACEMENT, so it draws the character standing there rather than
    its family's placeholder: the head of the `poi_locs` id when that names a
    unit (`WanderingMerchant_Npc_Azuram` -> the `WanderingMerchant` unit), and
    otherwise the row's own NAME looked up in the game's unit table
    (`Hilda Lambert` -> the `HildaLambert` unit, her ids being the generic
    `Codex_NPC_Hilda_*`). Both routes are keyed on the unit TABLE, so a generic
    head cannot resolve against whatever the atlas happens to call it.

    Twelve of the 38 characters have art; the other 26 - the plain world NPCs,
    Miss Arte, the prisoners the sheet files as `Critters`, the debug merchants -
    have NONE anywhere in the atlas, so they draw the family's plain person. Both
    lists are written out: a sprite landing for a name in the gap is a RED test,
    the same way `StableMaster` already covers the mount shop.
    """
    from farever_companion.ui.pages.codex.npc_list import (
        npc_rows, placement_unit, role_art)

    # the characters the game's own units give a face, and the sprite each draws
    drawn = {
        "Guild Merchant": ("units", "WanderingMerchant"),
        "Mira, Demon Huntress": ("units", "DemonHunterMira"),
        "Zoey, Demon Huntress": ("units", "DemonHunterZoey"),
        "Hilda Lambert": ("units", "HildaLambert"),
        "Job Welldon": ("units", "ProfessionTrainer"),
        "Tyra Firma": ("units", "TODO_BaseNPC_01"),
        "Kobold Prisoner": ("units", "Kobold_Prisoner"),
        "Apix Prisoner": ("units", "Bee_Prisoner"),
        "Royal Guard Prisoner": ("units", "Bee_Prisoner1"),
        "Perina Wann": ("units", "stablemaster"),
        "Haydn Seek": ("minimap", "npc_bubble"),
        # the PTS debug merchant is the vendor family's plain counter
        "Major Update Preview Merchant (debug)": ("units", "wanderingmerchant"),
    }
    # ... and the 26 the atlas never drew: one plain person each
    gap = {
        "Adrian", "Al Scarpone", "Beelly the Bee", "Beerutus", "Chapel Groan",
        "Chef Baker", "Christian Loubouquetin", "Gemini Trinket", "H. Catchum",
        "India Nachos", "Kobold Docker Prisoner", "Lamb Ada", "Lee Van Glyph",
        "Lora Craft", "Major Update Preview Helper (debug)", "Miss Arte",
        "Mortis Goat", "Nepside Prisoner", "Nepside Whale Prisoner", "Ratou",
        "Rita Von Cheese", "Ruby Garland", "Scout Pilgrim", "Shirley Templar",
        "Sister Abigail", "Tay Mirh",
    }

    rows = npc_rows()
    assert rows, "the shipped directory lists nothing"
    by_name = {}
    for r in rows:
        by_name.setdefault(r["name"], set()).add(role_art(r))
    assert set(by_name) == set(drawn) | gap, sorted(set(by_name) - set(drawn) - gap)
    for name, art in drawn.items():
        assert by_name[name] == {art}, (name, by_name[name])
    # every other character draws the plain person (the mount shop is NOT in the
    # gap: it reads the unit table's StableMaster)
    for name in gap:
        assert by_name[name] == {("minimap", "npc")}, (name, by_name[name])
    assert placement_unit({"id": "MountTamer_NPC_1"}) is None, \
        "the mount tamer is the one family with no unit of his own"

    # the spelling the sheet and the unit table disagree on, pinned: without the
    # alias both Demon Huntresses fall through to the vendor's Guild Merchant
    assert placement_unit({"id": "DemonHuntMira_NPC_Azuram"}) == \
        "DemonHunterMira"
    assert placement_unit({"id": "DemonHuntZoey_NPC_Azuram"}) == \
        "DemonHunterZoey"
    # the id route also has to read every casing the sheet writes (Npc/NPC)
    assert placement_unit({"id": "WanderingMerchant_Npc_Azuram"}) == \
        "WanderingMerchant"
    assert placement_unit({"id": "WanderingMerchant_NPC_Primevalley_1"}) == \
        "WanderingMerchant"
    # a name the unit table uses for TWO characters resolves no one: the wandering
    # merchant and the stable master are both "Guild Merchant", so only the id
    # route may pick between them
    assert placement_unit({"id": "", "name": "Guild Merchant"}) is None

    # and every sprite a row draws is really an atlas entry, on its named sheet
    from farever_companion.data import atlas
    for r in rows:
        sheet, sprite = role_art(r)
        assert atlas.find_entry(sheet, sprite) is not None, (r["id"], sheet, sprite)


def test_the_table_marks_every_row_the_atlas_cannot_draw():
    """Each placement the atlas never drew wears '◌ no art', and only those do.

    The mark comes off the SAME route the row's sprite takes (`role_art`), so the
    cell and the icon cannot disagree: a row wears the mark exactly when what it
    draws is the atlas's plain-person placeholder. That is what puts the gap -
    26 of the 38 characters - in front of the user instead of only in the
    directory test above.
    """
    from farever_companion.ui.pages.codex.npc_list import (
        atlas_cannot_draw, role_art)

    plain = ("minimap", "npc")
    rows = npc_rows()
    gapped = [r for r in rows if atlas_cannot_draw(r)]
    assert gapped and len(gapped) < len(rows), \
        "the shipped atlas still has its gap"
    # the predicate is exactly "the sprite drawn is the plain person", on every
    # row in the whole index - and the gap is the 26 characters, 34 placements
    for r in rows:
        assert atlas_cannot_draw(r) is (role_art(r) == plain), (r["name"], r["id"])
    assert len({r["name"] for r in gapped}) == 26
    assert len({r["name"] for r in rows if not atlas_cannot_draw(r)}) == 12
    assert "Perina Wann" not in {r["name"] for r in gapped}, \
        "the mount shop draws the unit table's stablemaster, not a gap"

    view = NpcListView(_NpcPage())
    for r in view.shown_rows():
        assert view.art_mark(r) == ("◌ no art" if atlas_cannot_draw(r) else ""), \
            r["name"]

    # ... and the CELL carries it, on a family that has both kinds of row
    view.show_family("npc")
    listing = view.shown_rows()
    assert any(atlas_cannot_draw(r) for r in listing)
    assert any(not atlas_cannot_draw(r) for r in listing)
    for i, r in enumerate(listing):
        shown = view._table.item(i, 5).text()
        assert ("◌ no art" in shown) is atlas_cannot_draw(r), r["name"]


def test_the_rail_lists_the_atlas_gap_across_every_role_and_zone():
    """The 'No atlas sprite' view is the whole gap in one place.

    The gap is neither a family nor a place, so the listing ignores both rails -
    otherwise finding "what can the atlas not draw" would mean clicking through
    every family and zone by hand. Every gap row is a plain NPC by construction:
    the three shop families all draw a real character sprite as their
    placeholder, so only the `npc` family can fall back to the plain person. It
    still honours the dev-rows toggle (a different axis: shipped vs. PTS-only).
    Off again, the table comes back to the family and zones it was on, because
    the view never touched them.
    """
    from farever_companion.ui.pages.codex.npc_list import atlas_cannot_draw

    view = NpcListView(_NpcPage())
    assert view.noart_only is False
    assert view._noart_hint.isHidden()

    # a narrow family/zone view, to prove the gap listing ignores both
    view.rail_option("role", "mountshop").click()
    view.rail_option("zone", "Z3").click()
    rails = {r["id"] for r in view.shown_rows()}
    assert rails

    gap_all = {r["id"] for r in npc_rows() if atlas_cannot_draw(r)}
    gap_ship = {r["id"] for r in npc_rows()
                if atlas_cannot_draw(r) and "(debug)" not in r["name"]}
    assert gap_all > gap_ship, "the gap includes the PTS-only rows too"

    opt = view.rail_option("view", "noart")
    assert opt is not None and opt.text().startswith("No atlas sprite")
    opt.click()
    assert view.noart_only is True and opt.isChecked()
    assert not view._noart_hint.isHidden()

    listing = view.shown_rows()
    assert {r["id"] for r in listing} == gap_ship
    assert {r["role"] for r in listing} == {"npc"}, \
        "only the plain-NPC family has a plain-person placeholder"
    assert len({r["zone_tag"] for r in listing}) >= 2, "more than one zone"
    assert not ({r["id"] for r in listing} <= rails), \
        "the listing is not just the narrow view it was opened from"

    # dev rows off still means off, for this listing too
    view.rail_option("view", "debug").click()
    assert {r["id"] for r in view.shown_rows()} == gap_all
    view.rail_option("view", "debug").click()

    opt.click()
    assert view.noart_only is False and view._noart_hint.isHidden()
    assert {r["id"] for r in view.shown_rows()} == rails


def test_the_atlas_gap_view_is_a_look_not_a_saved_filter(monkeypatch, tmp_path):
    """It is not persisted and it plots nothing: the next visit opens on the
    family the settings carry, and the click never touches the map."""
    monkeypatch.setenv("FAREVER_MODDATA_DIR", str(tmp_path))
    from farever_companion.config.model import Settings

    settings = Settings()
    page = _NpcPage(settings=settings)
    view = NpcListView(page)
    view.rail_option("role", "mountshop").click()
    pins = list(page._codex_map_widget.pins)
    view.rail_option("view", "noart").click()
    assert view.noart_only is True
    assert page._codex_map_widget.pins == pins, "a filter must not move the map"
    assert settings.codex_npc_role == "mountshop", \
        "the view state is not a stored filter"

    again = NpcListView(_NpcPage(settings=settings))
    assert again.noart_only is False
    assert again.family == "mountshop"


def test_a_gap_row_that_is_tracked_wears_both_marks():
    """The cell is where the two facts meet: the atlas gap and the tracking
    marker share it, and `track_mark` still reports only the tracking token -
    the contract the tracker reads."""
    from farever_companion.ui.pages.codex.npc_list import atlas_cannot_draw

    probe = NpcListView(_NpcPage())
    probe.show_family("npc")
    row = next(r for r in probe.shown_rows() if atlas_cannot_draw(r))
    key = NpcMixin._npc_track_key(probe.ui, row)

    view = NpcListView(_NpcPage(_Tracker(tracked=[("pos", key)])))
    view.show_family("npc")
    hit = next(r for r in view.shown_rows() if r["id"] == row["id"])
    assert view.art_mark(hit) == "◌ no art"
    assert view.track_mark(hit) == "◈ TRACKING"
    text = view._table.item(view.shown_rows().index(hit), 5).text()
    assert "◌ no art" in text and "◈ TRACKING" in text, text


def test_npc_rows_show_their_role_place_and_zone_and_keep_no_tooltip():
    """One row per placement: its marker, name, role, place and zone. The place
    and zone have their own columns now, which is what replaces the zone
    headers - and no tooltip, the flat-list convention."""
    from farever_companion.ui.pages.codex.npc_list import row_accent
    view = NpcListView(_NpcPage())
    labels = {"npc": "NPC", "vendor": "Vendor",
              "petshop": "Pet Shop", "mountshop": "Mount Shop"}
    assert view._table.toolTip() == ""
    assert view.shown_rows()
    for i, r in enumerate(view.shown_rows()):
        assert not view._table.item(i, 0).icon().isNull(), r["name"]
        assert view._table.item(i, 1).text() == r["name"]
        assert view._table.item(i, 2).text() == labels[r["role"]]
        # the accent reaches the table, not just the helper
        assert view._table.item(i, 2).foreground().color().name() == \
            row_accent(r), r["name"]
        assert view._table.item(i, 3).text() == r["place"]
        assert view._table.item(i, 4).text() == r["zone_tag"]


def test_the_mount_tamers_are_mount_shops_not_plain_vendors():
    """Perina Wann sells the mounts and gliders, and the poi_locs sheet files
    her two stalls under the plain `vendor` sub_kind - which is why the mount
    shop listed ZERO placements and stayed invisible on the rail.

    The game's own ids say what they are (`MountTamer_NPC_1/2`), so the index
    corrects the role - in `load_pois()`, the one place it is built, so EVERY
    reader agrees: the minimap would otherwise draw the two mount kiosks as
    ordinary vendors (it has no mount kiosk at all), while the NPC directory
    below calls them mount shops.

    This pins both halves: the raw sheet still says `vendor` (so the override is
    still needed - read straight out of the compiled `poi_locs`), and the index
    every reader sees says `mountshop` (so it still lands). A sheet that starts
    saying `mountshop` itself makes this red, instead of leaving a duplicate
    override behind.
    """
    from farever_companion.data import cdb

    sheet = {str(m.get("id")): m.get("sub_kind")
             for m in cdb.lines("poi_locs")
             if str(m.get("id", "")).startswith("MountTamer_")}
    assert sheet == {"MountTamer_NPC_1": "vendor",
                     "MountTamer_NPC_2": "vendor"}, \
        "the sheet no longer files the mount tamers as plain vendors: drop _MOUNT_VENDOR_IDS and this test"

    ids = set(sheet)
    assert {p.sub_kind for p in geo_pois.load_pois() if p.id in ids} == \
        {"mountshop"}, "the minimap/kiosk reader must see the mount shop too"
    assert {geo_pois.by_id()[i].sub_kind for i in ids} == {"mountshop"}
    index = {p.id: p for p in geo_pois.load_npc_pois()}
    assert {index[i].sub_kind for i in ids} == {"mountshop"}

    tamers = [r for r in npc_rows() if r["id"] in ids]
    assert {r["role"] for r in tamers} == {"mountshop"}
    assert {r["name"] for r in tamers} == {"Perina Wann"}
    assert {r["zone_tag"] for r in tamers} == {"Z1", "Z2"}


def test_every_rail_option_is_a_button_not_a_drawn_checkbox():
    """The rail is a column of toggle BUTTONS, and the family buttons are one at
    a time.

    It used to draw a 13x13 square per option, which read as a checkbox while
    being neither a `QCheckBox` (no hover, no focus, no keyboard, no checked
    state Qt styles) nor a button. Every option is a checkable `QPushButton`
    now, and this drives the real widgets: a family click moves the light to the
    family it selected, lists it and plots it, while the debug toggle still flips
    the dev rows.

    Haydn Seek's entry is the last family BUTTON rather than a section of its
    own: `Pin all Haydn` was a momentary button sitting beside a table it did not
    filter, and the family click is that action now.
    """
    page = _NpcPage()
    view = NpcListView(page)
    assert view.findChildren(QtWidgets.QCheckBox) == [], \
        "the rail's squares were hand-styled; nothing in it is a QCheckBox"
    assert view.rail_option("view", "fold") is None, \
        "'Fold repeats' did nothing but the debug rows, and is gone"
    assert view.rail_option("view", "haydn") is None, \
        "'Only Haydn' is the Haydn family button now, not a mode of its own"

    # `PTS debug npcs` is named for what it turns ON, like every other button
    # here: lit means the dev-only placements are in the list. It read `Hide
    # debug PTS npcs` and was lit while HIDING them.
    debug = view.rail_option("view", "debug")
    assert isinstance(debug, QtWidgets.QPushButton)
    assert debug.text().startswith("PTS debug npcs")
    assert debug.isCheckable() and not debug.isChecked(), \
        "the dev-only placements start hidden, so the button starts unlit"
    listed = {r["id"] for r in view.shown_rows()}
    assert listed == {r["id"] for r in npc_rows()
                      if r["name"] == "Haydn Seek"
                      and "(debug)" not in r["name"]}
    # the debug toggle belongs to one role: walk there first, and re-read
    # the listing there (it was Haydn's above)
    view.rail_option("role", "vendor").click()
    listed = {r["id"] for r in view.shown_rows()}
    assert listed == {r["id"] for r in npc_rows()
                      if r["role"] == "vendor"
                      and "(debug)" not in r["name"]}
    debug.click()
    assert debug.isChecked()
    assert {r["id"] for r in view.shown_rows()} == {
        r["id"] for r in npc_rows() if "(debug)" in r["name"]}
    debug.click()
    assert not debug.isChecked()
    assert {r["id"] for r in view.shown_rows()} == listed

    vendor = view.rail_option("role", "vendor")
    petshop = view.rail_option("role", "petshop")
    assert isinstance(vendor, QtWidgets.QPushButton)
    assert vendor.isCheckable() and vendor.isChecked()
    assert vendor.text().startswith("Vendor")
    petshop.click()                      # the real button, the real slot
    assert petshop.isChecked()
    assert not vendor.isChecked(), "the family buttons are one at a time"
    assert view.shown_rows()
    assert all(r["role"] == "petshop" for r in view.shown_rows())
    assert page._codex_map_widget.pins, \
        "the click plots the family it selected"
    vendor.click()
    assert vendor.isChecked() and not petshop.isChecked()
    assert any(r["role"] == "vendor" for r in view.shown_rows())

    # Haydn Seek is the last family button, and it lists his placements
    haydn = view.rail_option("role", "haydn")
    assert isinstance(haydn, QtWidgets.QPushButton)
    assert haydn.text().startswith("Haydn Seek")
    assert not haydn.isChecked()
    haydn.click()
    assert haydn.isChecked() and not vendor.isChecked()
    assert view.shown_rows() and all(
        r["name"] == "Haydn Seek" for r in view.shown_rows())

    # the plain NPC family lists them and leaves the map alone - and it is every
    # OTHER world NPC: Haydn Seek has a family button of his own, so he is not
    # also an NPC row (nor counted in that button's number)
    npc = view.rail_option("role", "npc")
    npc.click()
    assert npc.isChecked()
    assert view.shown_rows()
    assert all(r["role"] == "npc" for r in view.shown_rows())
    assert not any(r["name"] == "Haydn Seek" for r in view.shown_rows())
    others = len([r for r in npc_rows()
                  if r["role"] == "npc" and r["name"] != "Haydn Seek"])
    haydn = len([r for r in npc_rows() if r["name"] == "Haydn Seek"])
    assert npc.text() == f"NPC  {others}"
    assert view.rail_option("role", "haydn").text() == f"Haydn Seek  {haydn}"
    assert page._codex_map_widget.pins == [], \
        "one click on the NPC family must not bury the map in every NPC"
def test_the_haydn_family_button_lists_and_pins_every_placement_at_once():
    """The Haydn family is the rail's last entry and behaves like a role: one
    click lists his placements and plots every one of them at once.

    Each pin is labeled with the PLACE it stands in - ten pins all reading
    "Haydn Seek" would be ten identical labels stacked on each other. Tracking
    ten of them would be ten needles and ten Entity HUD rows, which is not what
    "where is Haydn" means.
    """
    page = _NpcPage()
    view = NpcListView(page)
    spots = [r for r in npc_rows() if r["name"] == "Haydn Seek"]
    assert len(spots) > 1
    btn = view.rail_option("role", "haydn")
    assert btn is not None
    assert btn.text() == f"Haydn Seek  {len(spots)}"

    btn.click()
    assert btn.isChecked()
    assert {r["id"] for r in view.shown_rows()} == {r["id"] for r in spots}
    pins = page._codex_map_widget.pins
    assert len(pins) == len(spots)
    assert {(p["x"], p["y"]) for p in pins} == \
        {(float(r["x"]), float(r["y"])) for r in spots}
    assert len({p["name"] for p in pins}) == len(pins)
    assert all(p["show_label"] for p in pins)
    assert str(len(pins)) in page._map_info_lbl.text
def test_the_npc_rail_selects_one_family_and_plots_it():
    """The rail is the point of the directory: the two questions people arrive
    with - where is a shop, where is Haydn - are one click each, and the click
    answers them twice over: the table lists that family and the map plots it.

    The plain NPC family is the exception: it lists (the trainers and guards are
    reachable) but plots nothing, because one click there would put every quest
    NPC in the game on the map at once.
    """
    page = _NpcPage()
    view = NpcListView(page)
    rows = npc_rows()

    haydn = view.rail_option("role", "haydn")
    vendor = view.rail_option("role", "vendor")
    petshop = view.rail_option("role", "petshop")
    assert haydn.isChecked() and not vendor.isChecked()
    # opening plots the default family before any click does
    assert len(page._codex_map_widget.pins) == 10
    assert page._codex_map_widget.selected == "Haydn Seek"
    petshop.click()
    assert petshop.isChecked()
    assert not vendor.isChecked(), "exactly one family is selected at a time"
    assert view.family == "petshop"
    assert view.shown_rows()
    assert all(r["role"] == "petshop" for r in view.shown_rows())
    # the click plots the WHOLE family, not just the rows the zone rail leaves
    want = [r for r in rows if r["role"] == "petshop"]
    assert len(page._codex_map_widget.pins) == len(want)
    assert str(len(want)) in page._map_info_lbl.text

    # clicking the lit family again keeps it selected: there is no "none" state
    petshop.click()
    assert petshop.isChecked() and view.family == "petshop"

    # the dev rows are a listing of their own: from any family, the toggle
    # shows all 14 across every role and zone, and off restores the family
    assert view.row_count == 3  # the petshops, dev rows out
    view.toggle_debug()
    assert view.show_debug is True
    assert view.row_count == 14, view.row_count
    assert all("(debug)" in r["name"] for r in view.shown_rows())
    view.toggle_debug()
    assert view.show_debug is False
    assert view.row_count == 3
    assert view.family == "petshop", "the family survives the debug detour"

    # zones stay multi-select, and the last one that lists rows cannot go off
    view.rail_option("role", "npc").click()
    assert not any(r["name"] == "Haydn Seek" for r in view.shown_rows()), \
        "the NPC family is every world NPC except Haydn Seek"
    for tag in sorted({r["zone_tag"] for r in rows}):
        view.toggle_zone(tag)
    assert view.row_count, "the last zone with rows cannot be switched off"
    assert len({r["zone_tag"] for r in view.shown_rows()}) == 1, \
        "exactly the one zone that still lists rows stays on"
def test_picking_a_role_leaves_the_diagnostic_listings():
    """A role click answers "where is X" right now: with the debug rows and
    the atlas gap both driving the table, picking a family turns both views
    off, so the click lists that family instead of lighting up behind the
    listings. The zones are untouched, and the views are one click away."""
    view = NpcListView(_NpcPage())
    view.rail_option("view", "debug").click()
    view.rail_option("view", "noart").click()
    assert view.show_debug is True and view.noart_only is True

    view.rail_option("role", "vendor").click()
    assert view.family == "vendor"
    assert view.show_debug is False and view.noart_only is False
    assert not view.rail_option("view", "debug").isChecked()
    assert not view.rail_option("view", "noart").isChecked()
    assert view.rail_option("role", "vendor").isChecked()
    assert view.shown_rows(), "the picked family lists, not the old views"
    assert all(r["role"] == "vendor" for r in view.shown_rows())
    assert not any("(debug)" in r["name"] for r in view.shown_rows())
def test_the_npc_rail_remembers_its_filters_through_the_settings(
        monkeypatch, tmp_path):
    """The rail persists its filters the way the rest of the Codex does.

    This view is rebuilt every time the NPC chip is activated, so the state has
    to live in the settings. A second view over the same settings object, and a
    settings file reloaded from disk, must both come back with the rail the last
    visit left behind: the mount shops selected, a zone off, the dev rows shown.

    The family persists as a key of its own (`codex_npc_role`) and the zones as
    the OFF set (`codex_npc_zones_off`), which is what makes a zone tag a game
    patch adds arrive ON - see the next test.
    """
    monkeypatch.setenv("FAREVER_MODDATA_DIR", str(tmp_path))
    from farever_companion.config.model import Settings

    settings = Settings()
    first = NpcListView(_NpcPage(settings=settings))
    first.rail_option("role", "mountshop").click()
    first.rail_option("zone", "Z3").click()
    first.rail_option("view", "debug").click()
    left = {r["id"] for r in first.shown_rows()}
    assert left, "the filtered view still lists rows"

    # the settings really carry it: the family key plus the zones' OFF set
    assert settings.codex_npc_role == "mountshop"
    assert settings.codex_npc_zones_off == ["Z3"]
    assert settings.codex_npc_show_debug is True

    # ... and a second view over them opens where the first one left off
    again = NpcListView(_NpcPage(settings=settings))
    assert again.family == "mountshop"
    assert {r["id"] for r in again.shown_rows()} == left
    assert again.show_debug is True
    assert again.rail_option("role", "mountshop").isChecked()
    assert not again.rail_option("role", "vendor").isChecked()
    assert not again.rail_option("zone", "Z3").isChecked()

    # ... and so does a fresh load of the file it wrote
    reloaded = Settings.load()
    assert reloaded.codex_npc_role == "mountshop"
    assert reloaded.codex_npc_zones_off == ["Z3"]
    assert reloaded.codex_npc_show_debug is True


def test_the_retired_npc_view_flags_are_stripped_from_the_settings(
        monkeypatch, tmp_path):
    """The rail names an option for what it turns ON, and two old flags are gone.

    `Only Haydn` is the Haydn family button now, and `Hide debug PTS npcs` is
    `PTS debug npcs` - the opposite polarity. A settings file written before
    either must not keep them: `haydn_only` would read as a control that no
    longer exists, and a leftover `hide_debug` would sit in the list next to the
    new flag while meaning the reverse of it.
    """
    monkeypatch.setenv("FAREVER_MODDATA_DIR", str(tmp_path))
    from farever_companion.config.model import Settings

    Settings(codex_npc_options=["hide_debug", "haydn_only"]).save()
    reloaded = Settings.load()
    assert reloaded.codex_npc_options == []
    assert reloaded.codex_npc_show_debug is False
    # the new flag round-trips on its own
    Settings(codex_npc_options=["show_debug"]).save()
    assert Settings.load().codex_npc_show_debug is True
def test_a_saved_zone_the_game_dropped_never_hides_a_zone_it_still_has(
        monkeypatch, tmp_path):
    """The OFF-set shape is a correctness choice, not a style one.

    A zone tag comes out of the GAME DATA, and this list is the only surface
    those rows have anywhere. An ON list would open the tab with whatever a
    patch adds already filtered out, so the file records what was switched OFF
    instead: an empty list means everything is on, a name the game no longer has
    touches nothing, and a hand-edited file that switches every zone off cannot
    open onto a blank table (the rail refuses to create that state, so restoring
    into one is refused too). A saved FAMILY key the game no longer has falls
    back to one that lists something, for the same reason.
    """
    monkeypatch.setenv("FAREVER_MODDATA_DIR", str(tmp_path))
    from farever_companion.config.model import Settings

    rows = npc_rows()
    debug = "(debug)"

    # nothing switched off - a first run lists the default family, dev rows out
    view = NpcListView(_NpcPage(settings=Settings()))
    assert view.family == "haydn"
    assert view.row_count == len([r for r in rows
                                  if r["name"] == "Haydn Seek"
                                  and debug not in r["name"]])

    # a stale name in the file (a zone the game dropped) hides nothing extra
    stale = Settings()
    stale.codex_npc_role = "vendor"
    stale.codex_npc_zones_off = ["Z9_Gone", "Z1"]
    view = NpcListView(_NpcPage(settings=stale))
    assert {r["id"] for r in view.shown_rows()} == {
        r["id"] for r in rows if r["role"] == "vendor"
        and r["zone_tag"] in ("Z2", "Z3") and debug not in r["name"]}

    # a family key the game no longer has falls back to one that lists rows
    gone = Settings()
    gone.codex_npc_role = "Z9_gone"
    view = NpcListView(_NpcPage(settings=gone))
    assert view.family == "haydn" and view.row_count

    # every zone switched off (hand-edited) is not a state this list opens in
    broken = Settings()
    broken.codex_npc_zones_off = sorted({r["zone_tag"] for r in rows})
    view = NpcListView(_NpcPage(settings=broken))
    assert view.row_count, "an all-off file must not open onto an empty list"
def test_clicking_a_row_tracks_and_plots_a_labeled_pin():
    """Clicking a row tracks that placement (the generic `pos` waypoint the
    Entity HUD uses) and plots the labeled pin on the codex map."""
    tracker = _ToggleTracker()
    page = _NpcPage(tracker)
    view = NpcListView(page)
    row = view.shown_rows()[0]
    view._on_cell_clicked(0, 0)
    key = NpcMixin._npc_track_key(page, row)
    assert tracker.is_tracked("pos", key)
    assert len(page._codex_map_widget.pins) == 1
    assert page._codex_map_widget.pins[0]["name"] == row["name"]
    assert row["name"] in page._map_info_lbl.text


def test_clicking_a_tracked_row_again_clears_the_pin():
    """Second click untracks and clears the pin - the row leaves nothing."""
    tracker = _ToggleTracker()
    page = _NpcPage(tracker)
    view = NpcListView(page)
    row = view.shown_rows()[0]
    view._on_cell_clicked(0, 0)
    assert page._codex_map_widget.pins
    view._on_cell_clicked(0, 0)
    assert not tracker.is_tracked("pos", NpcMixin._npc_track_key(page, row))
    assert page._codex_map_widget.pins == []


def test_only_the_tracked_row_shows_the_tracking_marker():
    """The '◈ TRACKING' cell appears on the tracked placement alone.

    Read off the rows the rail actually lists (the shipped default family), so
    the marker is checked against the table a user is looking at rather than
    against the raw index.
    """
    first = NpcListView(_NpcPage())
    listed = first.shown_rows()
    assert len(listed) > 1, "the default family still lists several placements"
    row = listed[0]
    key = NpcMixin._npc_track_key(first.ui, row)
    page = _NpcPage(_Tracker(tracked=[("pos", key)]))
    view = NpcListView(page)
    shown = view.shown_rows()
    hit = next(r for r in shown if r["id"] == row["id"])
    miss = next(r for r in shown if r["id"] != row["id"])
    assert view.track_mark(hit) == "◈ TRACKING"
    assert view.track_mark(miss) == ""


class _OthersTab:
    """Stand-in for the Codex tab combo (the view-mode code reads/sets it)."""

    def __init__(self, text="Other"):
        self._text = text

    def currentText(self):
        return self._text

    def setCurrentText(self, text):
        self._text = text


class _OthersChipPage(CodexMapUiMixin, CodexGridMixin):
    """Minimal page: the Others sub-bar group plus the view-mode pipeline +
    the card-jump entry points (whose deferred click is a no-op here)."""

    def __init__(self, tab="Other"):
        self._npc_list_mode = False
        self._dungeon_list_mode = False
        self._soulstones_mode = False
        self._chest_orb_kind = None
        self._collection_sub = "pets"
        self.refreshes = 0
        self._codex_tabs = _OthersTab(tab)
        self._others_btn_group = QtWidgets.QButtonGroup()
        self._others_sub_btns = {}
        for label in ("All", "Shop", "Unreleased", "Misc", "NPC"):
            btn = QtWidgets.QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(label == "All")
            self._others_btn_group.addButton(btn)
            self._others_sub_btns[label] = btn

    def _refresh_codex_grid(self, reset_scroll=False):
        self.refreshes += 1


def test_npc_chip_swaps_the_other_grid_to_the_npc_list():
    """'NPC' is the one Other chip that swaps the grid to a LIST; a card chip
    swaps the card grid back, and leaving the view re-checks All."""
    page = _OthersChipPage()
    assert not page._codex_npc_view_active()

    page._others_sub_btns["NPC"].setChecked(True)
    page._on_others_sub_toggled(True)
    assert page._npc_list_mode and page._codex_npc_view_active()
    assert page.refreshes == 1

    page._others_sub_btns["Shop"].setChecked(True)
    page._on_others_sub_toggled(True)
    assert not page._npc_list_mode
    assert page.refreshes == 2

    page._others_sub_btns["NPC"].setChecked(True)
    page._on_others_sub_toggled(True)
    assert page._npc_list_mode
    page._leave_npc_view()
    assert not page._npc_list_mode
    assert page._others_btn_group.checkedButton() is page._others_sub_btns["All"]


def test_npc_chip_owns_no_z0_card():
    """The NPC sub-view resolves no card, so the Z0 card filter rejects
    everything for it (while the card chips keep their own answer)."""
    page = _OthersChipPage()
    assert page._codex_others_sub_ok({"id": "TODO_StableMaster"}, "npc") is False
    assert page._codex_others_sub_ok({"id": "TODO_StableMaster"}, "all") is True


def test_status_chips_go_plain_on_the_npc_view():
    """The NPC list renders no cards, so the shared status chips carry no
    counts while it is up — they would be a lie."""
    page = _fake_status_widgets(_FakeGridPage())
    page._npc_list_mode = True
    page._update_codex_status_chips("Z0", "Other")
    assert page._status_widgets["All"].text() == "All"
    assert page._status_widgets["Visible"].text() == "Visible"
    assert page._status_widgets["Hidden"].text() == "Hidden"


def test_opening_a_card_leaves_a_stale_npc_view_first():
    """Jump-to-card drops the NPC list before it switches tabs, so the jump
    can never land behind a grid swapped to the NPC list."""
    page = _OthersChipPage()
    page._others_sub_btns["NPC"].setChecked(True)
    page._on_others_sub_toggled(True)
    assert page._npc_list_mode
    CodexMapUiMixin._codex_open_card(page, "Z1", "TODO_StableMaster", "Stable")
    assert not page._npc_list_mode


# ======================================================================
# test_codex_map_markers — the map canvas's pin sprites
# ======================================================================

def test_the_vendor_pin_only_tries_sprite_names_the_atlas_really_has():
    """The codex map's vendor pin used to try `shop` -> `currency` -> `vendor`,
    and the atlas has never had the last two: the chain had no fallback at all.

    It could not have recovered either, which is the part that made it silent -
    each attempt after the first was guarded by `pixmap.isNull()`, and
    `icons.marker` never returns None or a null pixmap (a missing asset degrades
    to a bare accent dot by design), so a renamed atlas sheet would have turned
    every vendor pin into a gold dot with nothing anywhere saying so.
    """
    from farever_companion.data import atlas, icons
    from farever_companion.ui import theme
    from farever_companion.ui.pages.codex import map as codex_map

    for name in codex_map._VENDOR_SPRITES:
        assert atlas.find_entry("minimap", name) is not None, name
        assert icons.atlas_sprite_resolvable("minimap", name), name

    # the names the old chain tried are still not sprites
    for phantom in ("currency", "vendor"):
        assert not icons.atlas_sprite_resolvable("minimap", phantom), phantom

    # ... and that is exactly what the degraded dot looks like, so the pin must
    # not be it
    dot = icons.marker("currency", 22, accent=theme.GOLD).toImage()
    vendor = codex_map._first_resolvable_marker(codex_map._VENDOR_SPRITES, 22,
                                                theme.GOLD)
    assert vendor is not None and not vendor.isNull()
    assert bytes(vendor.toImage().constBits()) != bytes(dot.constBits()), \
        "the vendor pin must be the shop sprite, not the degraded accent dot"


def test_the_pin_marker_walk_skips_a_name_the_atlas_does_not_have():
    """The walk is the fix, so it is driven with the old chain's names: it must
    skip the phantom ones, land on the real sprite, and say None - not hand
    back a dot it believes is a sprite - when nothing resolves."""
    from farever_companion.data import icons
    from farever_companion.ui import theme
    from farever_companion.ui.pages.codex import map as codex_map

    pm = codex_map._first_resolvable_marker(("currency", "vendor", "npc"), 22,
                                            theme.GOLD)
    assert pm is not None and not pm.isNull()
    npc = icons.marker("npc", 22, accent=theme.GOLD).toImage()
    assert bytes(pm.toImage().constBits()) == bytes(npc.constBits())

    assert codex_map._first_resolvable_marker(("currency", "nope"), 22,
                                              theme.GOLD) is None
