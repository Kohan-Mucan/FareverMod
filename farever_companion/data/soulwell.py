"""Soulwell offering tunables — the "Sacrifice Corrupted Gift" station.

The Soulwell is the offering station: sacrificing one of the 24
AugmentDemon gift items grants one of five luck buffs (which one is
chosen server-side, so the app can only list the possibilities).
Every tunable a buff timer needs is game-authored, in two sheets:

* constant.json's `Soulwell` row — a group of named values: the buff
  durations (rare/epic minutes), the reputation an offering gains,
  and the reputation-level duration bonus.
* constant.json's `Soulwell_Statuses` row — the five buff status ids
  an offering can grant.
* counter.json's `Luck_*` rows — each buff's luck math while it is
  up: base chance, per-stack increment, cap, and the item type (and
  minimum rarity) the counter ticks on.

The offering POOL is the item catalog: the 24 'Corrupted Gift' items of
type `AugmentDemon`, the only type the station accepts (see `_GIFT_TYPE`).
NOTHING here derives that list any more. The tab is a mock-up that names the rule
rather than listing the gifts, the Items pages work off the `DemonGearUpgrade*`
ids themselves, and the join that turned a held gift id into a name and a rarity
went with the live reader (retired to `ai/workspace/buffy/retired/`). The rule is
still checked against the sheet — by `tests/test_soulwell.py`, the file that
pins the game's own tunables — instead of being re-derived here for nobody.

The five buffs themselves come back from `luck_buffs()` — the buff ids joined
to their counters and a human label — which is the whole of what the tab needs
to draw them. Nothing here reads the game process: the station's CURRENT
offering and a live buff timer are runtime state, and they are not in any sheet.

Everything reads through cdb, so the compiled shim serves the frozen
build and the loose sheets cover a checkout whose shim predates them.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from . import cdb

#: The constant row carrying the offering's tunables (a `group` of
#: named int values).
_SOULWELL_ID = "Soulwell"
#: The constant row listing the buffs an offering can grant.
_SOULWELL_STATUSES_ID = "Soulwell_Statuses"


@lru_cache(maxsize=1)
def _constants() -> dict[str, dict]:
    return cdb.by_id("constant")


def soulwell_tunables() -> dict[str, int | float]:
    """The Soulwell group's named values, as the sheet states them:

    `Status_Duration_Base` / `Status_Duration_Rare` /
    `Status_Duration_Epic` (minutes), `Reputation_Gain_Rare` /
    `Reputation_Gain_Epic` (reputation points per offering), and
    `Reputation_Duration_Bonus` (extra minutes at Riftstalkers
    reputation level 5).
    """
    row = _constants().get(_SOULWELL_ID) or {}
    out: dict[str, int | float] = {}
    for entry in (row.get("v") or {}).get("group") or []:
        val = entry.get("v") or {}
        for kind in ("int", "float"):
            if kind in val:
                out[str(entry.get("id", ""))] = val[kind]
                break
    return out


def soulwell_buff_ids() -> list[str]:
    """The five buff status ids an offering can grant, in sheet order
    (Luck_LegendaryWeapon_Status, Luck_Mount_Status,
    Luck_Glider_Status, Luck_RareMaterial_Status,
    Luck_PrismaticGear_Status)."""
    row = _constants().get(_SOULWELL_STATUSES_ID) or {}
    other = (row.get("v") or {}).get("other") or {}
    return [s["ref"] for s in other.get("skills") or [] if s.get("ref")]


def buff_duration_minutes(rarity: str) -> int:
    """How long an offering's buff lasts, in minutes: 12 for a Rare
    gift, 24 for an Epic one — before the reputation-level bonus,
    which the game adds at runtime (see
    `reputation_duration_bonus`)."""
    key = {"rare": "Status_Duration_Rare",
           "epic": "Status_Duration_Epic"}.get(str(rarity).lower())
    if key is None:
        raise ValueError(f"rarity must be 'rare' or 'epic', got {rarity!r}")
    return int(soulwell_tunables().get(key, 0))


def reputation_gain(rarity: str) -> int:
    """Reputation points one offering gives: 10 (Rare) / 20 (Epic)."""
    key = {"rare": "Reputation_Gain_Rare",
           "epic": "Reputation_Gain_Epic"}.get(str(rarity).lower())
    if key is None:
        raise ValueError(f"rarity must be 'rare' or 'epic', got {rarity!r}")
    return int(soulwell_tunables().get(key, 0))


def reputation_duration_bonus() -> int:
    """Extra buff minutes the game grants at Riftstalkers reputation
    level 5 (the sheet's Reputation_Duration_Bonus)."""
    return int(soulwell_tunables().get("Reputation_Duration_Bonus", 0))


#: Whether an offering ADDS its gift's minutes to what the buff already carried
#: instead of replacing them — which is what makes five gifts (one per slot) five
#: times the minutes plus ONE reputation bonus rather than a single gift's worth.
#:
#: No sheet states this. The sheet gives a base of 0 and the per-rarity minutes,
#: and the SERVER does the adding — the offer RPC carries only
#: `(station, player)` (see `ai/workspace/soulwell_offer/CONCLUSION.md`) — so what
#: the app has is the live log: a Rare offering landed 1620s (12 min + 15), an
#: Epic one 2340s (24 + 15), one offering raised a live 1627s Mount buff to 2368s
#: (the 12 minutes added, not a reset), and five gifts at once landed 4500s
#: (5 x 12 + 15). See `ai/workspace/soulwell_offer/offers.jsonl`.
# HAND-FACT: _DURATION_ADDS_PER_GIFT
_DURATION_ADDS_PER_GIFT = True


def offering_seconds(rarity: str, gifts: int = 1) -> int:
    """Seconds the granted buff carries after `gifts` offerings of `rarity`.

    The rarity's minutes for each gift, plus the reputation bonus ONCE, because
    that is what the game granted: 1620s for one Rare gift, 4500s for five. Set
    `_DURATION_ADDS_PER_GIFT` to False and a run is worth a single gift's minutes
    instead — the shape this function would take if the game ever replaces the
    duration rather than extending it.

    `gifts` below 1 counts as 1 (an offering happened); the caller's ceiling is
    the station's own stacks — five blocks of five. Past the five the live log
    recorded, the rule extends as stated: each gift's minutes, bonus once.
    """
    per_gift = buff_duration_minutes(rarity) * 60
    total = per_gift * max(1, int(gifts)) if _DURATION_ADDS_PER_GIFT else per_gift
    return total + reputation_duration_bonus() * 60


@lru_cache(maxsize=1)
def luck_counters() -> dict[str, dict]:
    """counter.json's luck rows by counter id — only the rows that
    carry `luckParams` (the five `Luck_*` counters). Each value is
    that params block: the buff `status` it ticks, the `base`
    chance, the per-stack `increment`, the `max` cap, and, where the
    counter is scoped to one item type, `itemType` and `minRarity`."""
    out: dict[str, dict] = {}
    for row in cdb.lines("counter"):
        params = row.get("luckParams")
        if params and row.get("id"):
            out[str(row["id"])] = params
    return out


def luck_counter_for_status(status_id: str | None) -> str | None:
    """The luck counter whose buff status is `status_id`
    ('Luck_Mount_Status' -> 'Luck_Mount'), or None when no counter
    grants that buff."""
    if not status_id:
        return None
    for counter_id, params in luck_counters().items():
        if params.get("status") == status_id:
            return counter_id
    return None


def luck_scope(counter_id: str) -> tuple[str | None, str | None]:
    """The item type (and minimum rarity) a counter ticks on, where
    the counter is scoped: ('Mount', None), ('CraftingComponent',
    'Rare'), or (None, None) for the global counters."""
    params = luck_counters().get(counter_id) or {}
    item_type = params.get("itemType")
    min_rarity = params.get("minRarity")
    return (str(item_type) if item_type else None,
            str(min_rarity) if min_rarity else None)


def luck_chance(counter_id: str, stacks: int = 0) -> float | None:
    """The luck chance at `stacks` stacks: `base` + `increment` per
    stack, capped at `max`. Flat counters (increment 0) ignore the
    stack count. None when the counter id is unknown."""
    params = luck_counters().get(counter_id)
    if not params:
        return None
    chance = (float(params.get("base", 0))
              + float(params.get("increment", 0)) * stacks)
    return min(chance, float(params.get("max", chance)))


# The station's two acceptance rules, both out of the same bytecode function
# (`SoulwellInventory.getNoMoveItemReason`, f@34869 in hlboot.dat) and both
# stated to the player on the Soulwell tab:
#
# * the TYPE gate — anything that is not `st.Item.isType(item, 'AugmentDemon')`
#   comes back `EReason.WrongItem`, so the offering pool is EXACTLY the items
#   carrying `_GIFT_TYPE`, nothing more;
# * the DUPLICATE gate — it then walks the inventory's own `items` and returns
#   `EReason.Soulwell_SameItem` when an existing stack's item id equals the
#   offered one: one offering per gift, and the same gift cannot go in twice.
#
# No sheet row carries either rule, so they are recorded HERE rather than only
# in the scan notes (`ai/workspace/soulwell_offer/CONCLUSION.md`). Which of the
# five buffs a valid offering grants is not a client rule at all — the offer RPC
# carries exactly `(station, player)` and the server picks off
# `Soulwell_Statuses` — which is why the tab lists the possibilities instead of
# predicting one, and why the 24 gifts' individual stat conversions are not
# shown: the type is what is checked, not which conversion you picked.
# HAND-FACT: _GIFT_TYPE
#: The one item type the station accepts (see the rules above).
_GIFT_TYPE = "AugmentDemon"


# --- the five buffs an offering can grant -----------------------------------
def _counter_label(counter_id: str | None, status_id: str) -> str:
    """'Luck_LegendaryWeapon' -> 'Legendary Weapon'. The counter id is the
    game's own short name for the buff, so it is the label, not a guess."""
    base = (counter_id or status_id).removeprefix("Luck_").removesuffix("_Status")
    out = ""
    for ch in base:
        if ch.isupper() and out and not out.endswith(" "):
            out += " "
        out += ch
    return out or status_id


@dataclass(frozen=True)
class LuckBuff:
    """One of the five buffs an offering can grant, as the sheet names it.

    No live state: which buff is up and how long is left is runtime state the
    game never writes to a file. All a file can say is which five exist, what the
    game calls them and which luck counter each one ticks.
    """

    status_id: str
    label: str
    counter_id: str | None


def luck_buffs() -> list[LuckBuff]:
    """The five buffs an offering can grant, in sheet order, with the game's own
    label for each (`Luck_LegendaryWeapon` -> 'Legendary Weapon').

    No chance here: the sheet's luck math is read by the one table that shows it
    (`luck_chance`, from `ui/pages/items/soulwell.py`, the Items page's SOULWELL
    tab), so there is one place the number comes from and one place it is
    printed.
    """
    out: list[LuckBuff] = []
    for sid in soulwell_buff_ids():
        counter = luck_counter_for_status(sid)
        out.append(LuckBuff(status_id=sid, label=_counter_label(counter, sid),
                            counter_id=counter))
    return out


