"""Static POI index: id -> world position, type, and metadata.

Reads from `assets/data/poi_locs.json`. Handles obelisks, dungeons,
respawn points, and other fixed map markers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

@dataclass(frozen=True)
class POI:
    id: str
    kind: str      # "poi"
    sub_kind: str  # "dungeon", "obelisk", "respawn", "rift", "soulstone"
    x: float
    y: float
    z: float
    name: str | None = None
    zone: str | None = None
    target_activity: str | None = None
    spawn_unit: str | None = None   # soulstone: summoned boss unit id
    cost_item: str | None = None    # soulstone: item consumed to summon
    cost_count: int | None = None   # soulstone: amount consumed

    def dist2d(self, x: float, y: float) -> float:
        return math.hypot(self.x - x, self.y - y)

# Kinds whose POI rows include per-instance scenery, not just the world
# marker. The 2026-09-11 game-data regen reclassified every interior prop
# (DungeonExit_*, POI_Dungeon_*_CheckpointZone_*, BeeHive_HoneyStackPlatform*,
# Rift_Gate_*, Rift_Bonus_Chest_*, Monolith_*, …) as `dungeon`/`rift`, taking
# those kinds from 14 rows (12 dungeon + 2 rift entrances) to 243. The extras
# carry instance-local coordinates that overlap the overworld map, so plotting
# them plastered the minimap with dungeon/rift icons. A real entrance is the
# row that names the activity it opens (or at least a display name).
_ENTRANCE_KINDS = ("dungeon", "rift")


def _is_world_poi(m: dict) -> bool:
    """False for a dungeon/rift scenery row that is not a real entrance."""
    if m.get("sub_kind") not in _ENTRANCE_KINDS:
        return True
    return bool(m.get("target_activity") or m.get("name"))


@lru_cache(maxsize=1)
def load_pois() -> list[POI]:
    """All world POIs from compiled raw data with valid world positions.

    Dungeon/rift rows are reduced to their entrance markers (see
    `_is_world_poi`); obelisks, respawn points, vendors and soulstones are
    returned as-is - except the mount tamers, whose role the sheet gets wrong
    (`_MOUNT_VENDOR_IDS`). That one is corrected HERE, not in a reader, because
    every surface that shows a shop takes its kind from this index: the minimap
    drew the two mount kiosks as ordinary vendors (it has no mount kiosk at all
    otherwise) while the Codex NPC directory already called them mount shops.
    """
    from ..data import cdb
    out = []
    for m in cdb.lines("poi_locs"):
        wp = m.get("world_pos")
        if not wp or "x" not in wp or "y" not in wp:
            continue
        if not _is_world_poi(m):
            continue
        sub_kind = m.get("sub_kind", "")
        if m.get("id") in _MOUNT_VENDOR_IDS and sub_kind != "mountshop":
            sub_kind = "mountshop"
        out.append(POI(
            id=m.get("id", ""),
            kind=m.get("kind", "poi"),
            sub_kind=sub_kind,
            x=float(wp["x"]),
            y=float(wp["y"]),
            z=float(m.get("z", 0.0)),
            name=m.get("name"),
            zone=m.get("zone"),
            target_activity=m.get("target_activity"),
            spawn_unit=m.get("spawn_unit"),
            cost_item=m.get("cost_item"),
            cost_count=m.get("cost_count")
        ))
    return out

# Placed-NPC kinds in the world index. `npc` is the plain world NPC (Haydn
# Seek, Hilda Lambert, the profession trainers, the prison guards); the shop
# families the minimap already plots are NPCs too, so one list holds all of
# them instead of making the reader check three kinds side by side.
_NPC_KINDS = ("npc", "vendor", "petshop", "mountshop")

# HAND-FACT: _MOUNT_VENDOR_IDS
# The poi_locs sheet files the two mount tamers under the plain `vendor`
# sub_kind, so `mountshop` came out with ZERO placements and the mount/glider
# shops were listed as ordinary shopkeepers that sold no mounts. It is the
# game's own ids that say what they are - `MountTamer_NPC_1` (Perina Wann,
# Navelin) and `MountTamer_NPC_2` (Perina Wann, Orange Highland) - and the
# sheet patch that would make this list unnecessary is not in this repo. The
# correction is applied in `load_pois()`, the one place the role is built, so
# every reader (the minimap kiosks, the Codex NPC directory, `by_id()`) sees the
# same kind. A sheet that starts saying `mountshop` itself is a red test, not a
# silent double override.
_MOUNT_VENDOR_IDS = ("MountTamer_NPC_1", "MountTamer_NPC_2")


@lru_cache(maxsize=1)
def load_npc_pois() -> list[POI]:
    """Every PLACED NPC in the world index, straight from `poi_locs`.

    Placements, not characters: Hilda Lambert stands in nine zones, so she is
    nine rows with nine ids — the game names each spot separately
    (`Codex_NPC_Hilda_Eksod`, `Codex_NPC_Hilda_Azuram`, …) — the same
    character standing in two zones is two rows. The `sub_kind` IS the role
    (npc / vendor / petshop / mountshop).

    These rows have no codex card of their own (`units_by_region` has never
    heard of `MountTamer_NPC_2`), which is why the NPC list reads this index
    rather than the card grid.

    The role correction lives one level down, in `load_pois()` - every shop
    surface reads the role from this index, so fixing it there is what makes
    the minimap's kiosks and this list agree.
    """
    return [p for p in load_pois() if p.sub_kind in _NPC_KINDS]


@lru_cache(maxsize=1)
def by_id() -> dict[str, POI]:
    return {p.id: p for p in load_pois()}
