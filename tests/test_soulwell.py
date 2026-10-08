"""The Soulwell offering tunables are the game's own, not ours.

`data/soulwell.py` reads the constant sheet's `Soulwell` rows and the
counter sheet's `Luck_*` rows through cdb, so buff timers follow
whatever the shipped sheets say. These tests pin the accessor against
the real baked data: which rows it needs (a shim that predates the
sheet sync must fail here, not silently serve empty tunables), how the
durations and luck math combine, and the rare/epic choice a sacrifice
makes.

All of it is file data: the two facts that are NOT in any sheet — which gifts a
station holds right now, and whether a luck buff is up with time left — are
runtime state, and nothing in the app reads them any more (the Soulwell tab is a
mock-up). So there is no live half left to test.
"""
from __future__ import annotations

import pytest

from farever_companion.data import cdb, raw_data, soulwell


def test_the_shim_carries_the_soulwell_sheets():
    """The build contract: the baked raw_data actually holds the
    Soulwell rows and the luck counters. `test_compiler.py` proves a
    rebuild reproduces the committed shims, but a committed shim can
    itself be stale — this is the assertion that catches that."""
    constants = cdb.by_id("constant")
    assert "Soulwell" in constants, "constant.json lost its Soulwell row"
    assert "Soulwell_Statuses" in constants, (
        "constant.json lost its Soulwell_Statuses row")
    counters = cdb.lines("counter")
    assert counters, "counter.json is not baked into raw_data"
    assert any(row.get("luckParams") for row in counters), (
        "counter.json lost its luckParams rows")


def test_offering_tunables_are_the_sheet_six_values():
    """The constant sheet's Soulwell group, as the game authors it:
    buff minutes by rarity, reputation per offering, and the
    reputation-level duration bonus."""
    tunables = soulwell.soulwell_tunables()
    assert tunables == {
        "Status_Duration_Base": 0,
        "Status_Duration_Rare": 12,
        "Status_Duration_Epic": 24,
        "Reputation_Gain_Rare": 10,
        "Reputation_Gain_Epic": 20,
        "Reputation_Duration_Bonus": 15,
    }


def test_buff_durations_and_rep_follow_rarity():
    """A Rare gift runs half an Epic one and gives half the
    reputation; the base duration is the un-bonused floor."""
    assert soulwell.buff_duration_minutes("rare") == 12
    assert soulwell.buff_duration_minutes("epic") == 24
    assert soulwell.buff_duration_minutes("epic") == (
        2 * soulwell.buff_duration_minutes("rare"))
    assert soulwell.reputation_gain("rare") == 10
    assert soulwell.reputation_gain("epic") == 20
    with pytest.raises(ValueError):
        soulwell.buff_duration_minutes("legendary")
    with pytest.raises(ValueError):
        soulwell.reputation_gain("common")


def test_buff_ids_are_the_five_luck_statuses():
    """An offering grants exactly one of the five luck buffs (which
    one is the server's choice — the app lists the possibilities)."""
    buffs = soulwell.soulwell_buff_ids()
    assert set(buffs) == {
        "Luck_LegendaryWeapon_Status", "Luck_Mount_Status",
        "Luck_Glider_Status", "Luck_RareMaterial_Status",
        "Luck_PrismaticGear_Status",
    }
    assert len(buffs) == len(set(buffs)) == 5


def test_every_buff_has_a_luck_counter():
    """Each buff status is ticked by exactly one counter row, and the
    counter names the buff back — the pairing the buff timer uses to
    find the chance math for a given buff."""
    for buff in soulwell.soulwell_buff_ids():
        counter = soulwell.luck_counter_for_status(buff)
        assert counter, f"no luck counter grants {buff}"
        assert soulwell.luck_counters()[counter]["status"] == buff
    assert soulwell.luck_counter_for_status("Not_A_Buff_Status") is None
    assert soulwell.luck_counter_for_status(None) is None


def test_luck_chance_is_base_plus_increment_capped():
    """Chance at N stacks = base + N*increment, capped at max — the
    sheet's own numbers, so a game re-tune moves the test with it."""
    for counter_id, params in soulwell.luck_counters().items():
        base = float(params["base"])
        increment = float(params.get("increment", 0))
        cap = float(params["max"])
        assert soulwell.luck_chance(counter_id, 0) == pytest.approx(base)
        assert soulwell.luck_chance(counter_id, 1) == pytest.approx(
            min(base + increment, cap))
        assert soulwell.luck_chance(counter_id, 10_000) == pytest.approx(cap)
    # a flat counter (no increment) ignores the stack count entirely
    flat = [c for c, p in soulwell.luck_counters().items()
            if not p.get("increment")]
    assert flat, "the sheet lost its flat luck counter"
    for counter_id in flat:
        assert soulwell.luck_chance(counter_id, 7) == pytest.approx(
            soulwell.luck_chance(counter_id, 0))
    assert soulwell.luck_chance("Not_A_Counter", 3) is None


def test_luck_scope_names_the_counters_item_type():
    """Scoped counters tick on one item type (Mount luck on mounts,
    rare-material luck on Rare crafting components); global counters
    (legendary-weapon luck) are unscoped."""
    scoped = {
        counter: soulwell.luck_scope(counter)
        for counter in soulwell.luck_counters()
    }
    assert scoped["Luck_Mount"] == ("Mount", None)
    assert scoped["Luck_Glider"] == ("GearGlider", None)
    assert scoped["Luck_RareMaterial"] == ("CraftingComponent", "Rare")
    assert scoped["Luck_LegendaryWeapon"] == (None, None)


def test_reputation_duration_bonus_is_readable():
    """The extra minutes the game adds at Riftstalkers reputation
    level 5 — the timer shows it on top of the rarity duration."""
    assert soulwell.reputation_duration_bonus() == 15


def test_the_station_takes_one_type_and_one_offering_per_gift():
    """The station's acceptance law, checked against the item sheet it rests on
    (`# HAND-FACT: _GIFT_TYPE` — the rules sit above the constant).

    Both halves come out of one bytecode function,
    `SoulwellInventory.getNoMoveItemReason`: a non-`AugmentDemon` item comes back
    `EReason.WrongItem`, and an id already sitting in the station comes back
    `EReason.Soulwell_SameItem` (one offering per gift). The second half is a
    rule, not data, so what can be pinned is the half the type gate decides: the
    station's menu is EXACTLY the `AugmentDemon` rows the sheet ships — 24 gifts,
    twelve conversions with a Rare and an Epic half each. This is the assertion
    that goes red when the type is re-authored or the constant is retyped.

    The derivation lives HERE, not in the app: nothing consumes the pool any more
    (the tab names the rule instead of listing the gifts, and the reader that
    joined a held gift id to a name and a rarity is retired), so the pool stays
    what it always was under the rule — a sheet contract.
    """
    assert soulwell._GIFT_TYPE == "AugmentDemon"
    from farever_companion.data.items import catalog

    typed = [it for it in catalog.items()
             if str(it.get("type") or "").lower() == "augmentdemon"]
    assert typed, "the item sheet no longer ships a single AugmentDemon item"
    assert len(typed) == 24, "the sheet's gift family changed size"
    assert {str(it.get("rarity")) for it in typed} == {"Rare", "Epic"}
    # every one of them converts one stat into another, and the 24 come in 12
    # pairs, each carrying both rarities — the shape the rule implies
    halves: dict[tuple[str, str], set[str]] = {}
    for it in typed:
        stats = it.get("stats") or []
        adds = [s for s in stats if int(s.get("v") or 0) > 0]
        drains = [s for s in stats if int(s.get("v") or 0) < 0]
        assert adds and drains, f"{it.get('id')} is not a conversion pair"
        pair = (str(drains[0].get("n")), str(adds[0].get("n")))
        halves.setdefault(pair, set()).add(str(it.get("rarity")))
    assert len(halves) == 12, f"the sheet's conversions changed: {sorted(halves)}"
    assert all(len(r) == 2 for r in halves.values()), (
        f"a conversion lost a rarity half: {[p for p, r in halves.items() if len(r) != 2]}")


def test_luck_buffs_are_the_five_sheet_buffs_with_the_games_labels():
    """`luck_buffs()` is the whole of what the tab needs to draw the five slots:
    the sheet's five status ids, joined to their counters and a label the player
    recognises ('Luck_LegendaryWeapon' -> 'Legendary Weapon'), in sheet order.

    It carries NO live state — which buff is up and how long is left are runtime
    facts no sheet holds — so a `LuckBuff` is exactly the three sheet-derived
    fields, and a field added for a timer would be a field nothing can fill.
    """
    buffs = soulwell.luck_buffs()
    assert [b.status_id for b in buffs] == soulwell.soulwell_buff_ids()
    assert [b.label for b in buffs] == [
        "Legendary Weapon", "Mount", "Glider", "Rare Material",
        "Prismatic Gear"]
    assert [b.counter_id for b in buffs] == [
        "Luck_LegendaryWeapon", "Luck_Mount", "Luck_Glider",
        "Luck_RareMaterial", "Luck_PrismaticGear"]
    assert [f for f in soulwell.LuckBuff.__dataclass_fields__] == [
        "status_id", "label", "counter_id"]
    assert soulwell._counter_label(None, "Luck_Mount_Status") == "Mount"


def test_offering_seconds_matches_the_durations_the_game_granted():
    """`# HAND-FACT: _DURATION_ADDS_PER_GIFT` — the rule no sheet states: an
    offering ADDS its gift's minutes, so five gifts are five times the minutes
    plus ONE reputation bonus.

    Pinned to the live log (`ai/workspace/soulwell_offer/offers.jsonl`), which is
    the only evidence there is for the adding: a Rare offering landed 1620s
    (12 + 15), an Epic one 2340s (24 + 15), a live Mount buff rose from 1627s to
    2368s by one offering, and five gifts at once landed 4500s (5 x 12 + 15).
    If the game ever replaces instead of extending, this is the test that goes
    red and the constant that flips.
    """
    assert soulwell._DURATION_ADDS_PER_GIFT is True
    assert soulwell.offering_seconds("rare", 1) == 1620        # the log's value
    assert soulwell.offering_seconds("epic", 1) == 2340        # the log's value
    assert soulwell.offering_seconds("rare", 5) == 4500        # the log's value
    assert soulwell.offering_seconds("epic", 5) == 8100        # 5 x 24 + 15
    # the bonus lands ONCE, so the growth is the gift's minutes per step
    rare_step = soulwell.offering_seconds("rare", 2) - soulwell.offering_seconds("rare", 1)
    assert rare_step == soulwell.buff_duration_minutes("rare") * 60
    epic_step = soulwell.offering_seconds("epic", 3) - soulwell.offering_seconds("epic", 2)
    assert epic_step == soulwell.buff_duration_minutes("epic") * 60
    # one live offering is the +15-minute bonus over the sheet's own minute count
    assert soulwell.offering_seconds("rare", 1) == (
        soulwell.buff_duration_minutes("rare") * 60
        + soulwell.reputation_duration_bonus() * 60)
    # below one gift still counts as the one offering that happened
    assert soulwell.offering_seconds("rare", 0) == soulwell.offering_seconds("rare", 1)
