from __future__ import annotations
from functools import lru_cache
from .raw_data import DATA


@lru_cache(maxsize=1)
def load_dungeons() -> list[dict]:
    """Returns the list of dungeons, sorted by level then name, Rifts last.

    The compiled `raw_data['dungeons']` ships every row the app needs, both
    RIFTS included under their own ids: the dungeon scan states each rift's
    identity on its own sheet row - title, boss, level, the shared 'Rifts'
    entrance, its mob list and `is_rift` - and the compiler ships those rows as
    they stand, so there is nothing to recover here.
    """
    ds = list(DATA.get("dungeons", []))
    # Sort by: is_rift (False < True), then level, then name
    return sorted(ds, key=lambda d: (
        d.get("entrance_zone") == "Rifts" or bool(d.get("is_rift")),
        d.get("level", 99),
        d.get("name", "").lower()
    ))

@lru_cache(maxsize=1)
def by_id() -> dict[str, dict]:
    return {d["id"]: d for d in load_dungeons()}

@lru_cache(maxsize=1)
def by_entrance_zone() -> dict[str, dict]:
    """{entrance_zone: dungeon}, skipping the rows that declare none.

    The payload carries zone-less rows — a POI that only marks where a dungeon
    starts (`Z1_POI_Dungeon_ManfishGeyser`) — and indexing `d["entrance_zone"]`
    on one of those raised a KeyError for every caller, which reads as "no
    dungeon is here" for a zone that simply has no row. A row with no entrance
    zone is not an entrance.
    """
    return {d["entrance_zone"]: d for d in load_dungeons()
            if d.get("entrance_zone")}

def is_listable(d: dict) -> bool:
    """Does this row name anything the app can show as a dungeon?

    The payload carries rows that are only a PLACE the extraction saw, with no
    dungeon attached: `Z1_POI_Dungeon_ManfishGeyser` has no `name`, no
    `boss_id`/`boss_name`, no `entrance_zone` and no `dungeon_loc` - only a
    `level`. The Codex dungeon list renders the boss line as
    `boss_name or icon or "?"`, so such a row showed up as a bare `?` with
    `Lv 10`, unnameable and untrackable.

    Nothing else needs this test: every other consumer already skips a row
    without a name or a `boss_id` on its own (see `codex.bosses`,
    `sources._dungeon_roll_sources`). It is stated here so the rule lives with
    the data it describes instead of inside one widget.
    """
    return bool(d.get("boss_name") or d.get("boss_id") or d.get("name"))


@lru_cache(maxsize=1)
def dungeon_unit_ids() -> set[str]:
    """Returns a set of all unit IDs (bosses and mobs) that appear in dungeons."""
    ids = set()
    for d in load_dungeons():
        bid = d.get("boss_id")
        if bid: ids.add(bid)
        for mid in d.get("mobs", []): ids.add(mid)
    return ids

@lru_cache(maxsize=1)
def unit_to_dungeon_map() -> dict[str, dict]:
    """Returns a mapping of unit ID -> dungeon dict for all dungeon bosses and mobs."""
    mapping = {}
    for d in load_dungeons():
        bid = d.get("boss_id")
        if bid:
            mapping[bid] = d
        for mid in d.get("mobs", []):
            mapping[mid] = d
    return mapping

def zone_tag_from_zone_id(zone_id: str) -> str | None:
    """'Z1_Enripit_Falls' -> 'Z1' (Crimson -> Z3), or None."""
    if not zone_id:
        return None
    if "Crimson" in zone_id:
        return "Z3"
    for prefix in ("Z1_", "Z2_", "Z3_"):
        if zone_id.startswith(prefix):
            return prefix[:2]
    return None


def zone_tag(d: dict) -> str | None:
    """Zone filter tag for a dungeon ('Z1'/'Z2'/'Z3'), or None.

    Crimson entrances map to Z3 — the codex treats Crimson Island as Z3 even
    though its metadata entrance zones are Z2_CrimsonIsland_*. For every other
    dungeon `entrance_zone` IS the zone it sits in.

    A RIFT is the exception: both rifts share the one 'Rifts' entrance, which
    says nothing about where their bosses stand (Z1 Enripit Falls / Z2 Krisomal
    North — the two overworld rift gates, and nothing in the game data binds
    either gate to a rift), so the row states its own `zone`. That value is
    curated in `Dungeons_Scanner/dungeons_config.json` and carried onto the row
    by the capture, so this reads the sheet instead of keeping a table here.
    """
    return zone_tag_from_zone_id(d.get("zone") or d.get("entrance_zone") or "")


def get_dungeon_info(activity_id_or_name: str | None) -> dict | None:
    if not activity_id_or_name:
        return None
    
    # 1. Try by ID (exact)
    d_map = by_id()
    if activity_id_or_name in d_map:
        return d_map[activity_id_or_name]
        
    # 2. Try by entrance zone
    e_map = by_entrance_zone()
    if activity_id_or_name in e_map:
        return e_map[activity_id_or_name]
        
    # 3. Try by Name or In-game Name (fuzzy)
    low_val = activity_id_or_name.lower()
    
    # Handle "Rift " prefix (try both with and without)
    search_vals = [low_val]
    if low_val.startswith("rift "):
        search_vals.append(low_val[5:].strip())
    
    for d in load_dungeons():
        d_name = d.get("name", "").lower()
        d_ig = d.get("ingame_name", "").lower()
        
        for v in search_vals:
            # Pre-process for common typos/quirks in poi_locs.json names
            v_clean = v.replace("abbandoned", "abandoned").replace("mines", " mines")
            v_clean = v_clean.replace("barraks", "barracks").replace("goulp", "gulp")
            v_clean = v_clean.replace("manfish", "manfish ").strip()

            if d_name == v or d_ig == v or d_name == v_clean or d_ig == v_clean:
                return d
            
    return None


def declared_boss_id(zone: str | None) -> str | None:
    """The boss unit id the game itself names for this instance, else None.

    The zone the player is standing in is resolved to a dungeon row, and that
    row's ``boss_id`` is the instance declaring who its boss is. This is the
    only INDEPENDENT boss signal the tracker has: everything else it can see
    (a unit's class, the runtime boss flag, a distance) describes a unit that is
    present, not the one this instance is actually about.

    Rifts return None on purpose. Both rifts share one entrance zone, so the
    lookup can only ever name one of the two and the answer would be wrong half
    the time - worse than saying nothing, because a rift boss is recognised
    perfectly well by its own unit id (see `units._is_rift_boss`). A zone with
    no dungeon row, a row with no boss id, and the shared Rifts entrance all
    return None, which reads downstream as "this instance declares no boss".

    Restored 2026-10-03 after a concurrent edit dropped the function while
    `core/model.py` and `core/dps_tracker_tick.py` still called it (an
    AttributeError on the zone read, not only in tests).
    """
    if not zone:
        return None
    info = get_dungeon_info(zone)
    if not info:
        return None
    if info.get("entrance_zone") == "Rifts":
        return None
    return (info.get("boss_id") or None)
