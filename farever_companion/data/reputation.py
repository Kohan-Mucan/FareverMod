"""Reputation ranks — the standing ladder, read off the sheets.

Two factions grant ranks (`ach.json` objectives against `ReputationLevel`):
the Riftstalkers and the Pilgrims, each with achievements at ranks 1, 5 and
10. Everything else a rank needs is game-authored too:

* `constant.json` `Reputation_XPThresholds` — the XP one rank costs;
* `constant.json` `Reputation_XPGain` — XP per completed rift;
* `constant.json` `Reputation_Rewards` — which rank unlocks which station
  reward (the soulwell's +minutes at 5, its vitality bonus at 7);
* `faction.json` `reputation.rewards` — the game's own per-rank unlock
  text (mounts, gliders, quartermaster stock, flask ranks), `rewards[i]`
  granting rank `i + 1` (index 4 is the rank-5 duration bonus, index 6
  the rank-7 vitality — which is what fixes the mapping);
* `data.soulwell.reputation_gain` — the XP a soulwell offering grants
  (a Rare gift 10, an Epic 20), reused here rather than re-stated;
* `skill.json` — the rep-gated standing rewards (the Nightlings' Favor heal,
  Chaos Vitality), found by the `hasReputationLevel(Faction, N)` their
  scripts test;
* `lootTable.json` — the rep-gated drops (`conditions.reputation`), e.g.
  Demonic Souls off Chaos Ore from rank 2.

Nothing here reads the game process: a faction's CURRENT rank is runtime
state, and no sheet carries it. What the sheets do carry — the ladder, its
cost, what each rung pays — is what this module returns, and what the Codex
Others "Reputation" list draws.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import re

from . import cdb
from . import skills as _skills
from . import soulwell as _soulwell

#: ach.json objective ref that marks a reputation-rank achievement.
_REP_OBJECTIVE = "ReputationLevel"
#: constant.json rows behind the ladder.
_THRESHOLDS_ID = "Reputation_XPThresholds"
_XP_GAIN_ID = "Reputation_XPGain"
_REWARDS_ID = "Reputation_Rewards"


@dataclass(frozen=True)
class FactionRep:
    """One reputation faction: its id, display title, and ranked rungs."""

    faction_id: str
    title: str
    levels: tuple[int, ...] = ()
    achievements: dict[int, tuple[str, str, int]] = field(default_factory=dict)
    #: ach_id -> (name, points) per rank holding an achievement


@dataclass(frozen=True)
class RankReward:
    """One thing a rank grants: the rank, a title, and the sheet's detail."""

    level: int
    title: str
    detail: str = ""


@lru_cache(maxsize=1)
def _constants() -> dict[str, dict]:
    return cdb.by_id("constant")


def _rep_achievements() -> dict[str, dict[int, tuple[str, str, int]]]:
    """{faction_id: {rank: (ach_id, name, points)}} from the Reputation
    achievements' `ReputationLevel` objectives."""
    out: dict[str, dict[int, tuple[str, str, int]]] = {}
    for row in cdb.lines("ach"):
        for obj in row.get("objectives") or []:
            if obj.get("ref") != _REP_OBJECTIVE:
                continue
            for target in obj.get("targets") or []:
                ref = target.get("ref")
                if not (isinstance(ref, list) and len(ref) == 2 and ref[0] == 5):
                    continue
                faction = str(ref[1])
                level = int((obj.get("value") or {}).get("v", 0) or 0)
                if level > 0:
                    out.setdefault(faction, {})[level] = (
                        str(row.get("id", "")),
                        str(row.get("name", "") or row.get("id", "")),
                        int(row.get("points", 0) or 0),
                    )
    return out


def factions() -> list[FactionRep]:
    """Every faction with reputation ranks, titled by its own achievements.

    The title is the rank-1 achievement's name ("Riftstalkers Sisterhood",
    "Pilgrims of Merilam") — the game's own words for the standing, not an
    app-side label. The ladder runs to the highest achievement rank (10).
    """
    out: list[FactionRep] = []
    for faction_id, achs in sorted(_rep_achievements().items()):
        levels = sorted(achs)
        first = achs.get(min(levels), ("", faction_id, 0))
        title = first[1] or faction_id
        top = max(levels)
        out.append(FactionRep(
            faction_id=faction_id,
            title=title,
            levels=tuple(range(1, top + 1)),
            achievements=dict(achs),
        ))
    return out


def xp_per_rank() -> int:
    """The XP one reputation rank costs — the sheet's single threshold."""
    row = _constants().get(_THRESHOLDS_ID) or {}
    floats = (row.get("v") or {}).get("floats") or []
    if floats:
        return int(float(floats[0].get("v", 0) or 0))
    return 0


def cumulative_xp(level: int) -> int:
    """Total XP rank `level` has cost from unranked (rank N = N × threshold)."""
    return max(0, int(level)) * xp_per_rank()


def xp_gains() -> list[tuple[str, int]]:
    """How XP is earned: rifts from the sheet, soulwell gifts from the
    soulwell module (one source for both tabs, so the two can never disagree).
    """
    out: list[tuple[str, int]] = []
    row = _constants().get(_XP_GAIN_ID) or {}
    for entry in (row.get("v") or {}).get("group") or []:
        val = entry.get("v") or {}
        for kind in ("int", "float"):
            if kind in val:
                label = str(entry.get("id", "")).replace("RiftCompleted",
                                                         "Rift completed")
                out.append((label, int(val[kind])))
                break
    out.append(("Soulwell Rare gift", _soulwell.reputation_gain("rare")))
    out.append(("Soulwell Epic gift", _soulwell.reputation_gain("epic")))
    return out


def _rewards_row(faction_id: str) -> dict:
    """The faction's entry in `Reputation_Rewards`, or {} when the sheet
    grants it no station rewards."""
    row = _constants().get(_REWARDS_ID) or {}
    for entry in (row.get("v") or {}).get("group") or []:
        if entry.get("id") == faction_id:
            return entry.get("v") or {}
    return {}


def _station_rewards(faction_id: str) -> list[RankReward]:
    """Rank-gated station rewards from `Reputation_Rewards`.

    Each entry names the reward after `ReputationLevel_` and carries the rank
    as its value — parallel entries, so the value is the required rank, the
    way the soulwell module already reads the duration bonus (rep 5).
    """
    out: list[RankReward] = []
    for entry in _rewards_row(faction_id).get("group") or []:
        rid = str(entry.get("id", ""))
        val = entry.get("v") or {}
        level = int(val.get("int", 0) or 0)
        if level <= 0:
            continue
        short = rid.removeprefix("ReputationLevel_")
        if short == "Soulwell_DurationBonus":
            mins = _soulwell.reputation_duration_bonus()
            out.append(RankReward(level, "Soulwell offerings last longer",
                                  f"+{mins} min on every buff"))
        elif short == "Soulwell_OfferingFull_VitalityBonus":
            sk = _skills.skill_row("RiftstalkersReputation_SoulwellVitality") or {}
            texts = sk.get("texts") or {}
            out.append(RankReward(
                level,
                str(texts.get("name", "Chaos Vitality")),
                str(texts.get("desc", "Vitality per offering"))))
        else:
            out.append(RankReward(level, short, ""))
    return out


def _script_rep_level(script: str, faction_id: str) -> int:
    """The rank `hasReputationLevel(Faction.<id>, N)` tests in a skill script,
    or 0 when the script gates nothing for this faction."""
    m = re.search(r"hasReputationLevel\(Faction\." + re.escape(faction_id)
                  + r"\s*,\s*(\d+)\)", script or "")
    return int(m.group(1)) if m else 0


def _script_conditions(script: str) -> list[str]:
    """Where/when a gated skill fires, from the calls its script makes:
    `isInRift()` (in rifts), `isTargetFaction(..., Faction.<X>)` (vs that
    faction). The rank itself is the caller's row, not repeated here."""
    conds: list[str] = []
    if re.search(r"isInRift\(\)", script or ""):
        conds.append("in rifts")
    for fac in re.findall(r"isTargetFaction\([^,]+,\s*Faction\.([A-Za-z0-9_]+)\)",
                           script or ""):
        conds.append(f"vs {fac}")
    return conds


def _heal_summary(row: dict) -> str:
    """What a Heal step restores, from its MaxHealth scaling ratio
    (0.1 -> "heals 10% max Health"). Empty when the row heals nothing that
    way — the sheet's own desc then stands alone."""
    for step in row.get("steps") or []:
        for fx in step.get("effects") or []:
            for sc in fx.get("scaling") or []:
                if sc.get("atb") == "MaxHealth" and sc.get("ratio"):
                    return (f"heals {float(sc['ratio']) * 100:.0f}% "
                            f"max Health")
    return ""


def _standing_skills(faction_id: str) -> list[RankReward]:
    """Rank-gated standing skills: skill rows whose scripts test this
    faction's rank. Title is the row's own `texts.name`; the detail is the
    row's desc PLUS what the game files say it does — the heal from its
    steps, the conditions from its script, and any buff it also grants
    (`addStatusDuration(..., Skill.<id>, <secs>)`) — so the rank shows the
    whole reward, not just its name.
    """
    out: list[RankReward] = []
    # Verbatim rows (the shim's `skill_rows`, via data/skills.py): the trimmed
    # `skill` mirror drops `script`, which is the only field carrying the rank
    # gate — the same read the weapon-skills section relies on.
    ids = [r.get("id") for r in cdb.lines("skill")] or list(cdb.by_id("skill"))
    for sid in ids:
        if not sid:
            continue
        row = _skills.skill_row(sid) or {}
        level = _script_rep_level(str(row.get("script") or ""), faction_id)
        if level <= 0:
            continue
        texts = row.get("texts") or {}
        script = str(row.get("script") or "")
        buffs: list[str] = []
        for b in re.findall(r"addStatusDuration\(\w+,\s*Skill\.([A-Za-z0-9_]+)\s*,\s*(\d+)\)",
                            script):
            brow = _skills.skill_row(b[0]) or {}
            btexts = brow.get("texts") or {}
            # the resolver's reading first ([MoveSpeedFactor] -> Move Speed),
            # the raw desc when it has nothing to say
            bdesc = (_skills.skill_description(b[0])
                     or str(btexts.get("desc", "")) or "").rstrip(".")
            buffs.append(f"{btexts.get('name', b[0])} ({b[1]}s)"
                         + (f": {bdesc}" if bdesc else ""))
        parts = [str(texts.get("desc", "")).rstrip(".")]
        heal = _heal_summary(row)
        conds = _script_conditions(script)
        mid = ", ".join(([heal] if heal else []) + conds)
        if mid:
            parts.append(mid[0].upper() + mid[1:])
        if buffs:
            parts.append("Also grants: " + "; ".join(buffs))
        detail = ". ".join(p for p in parts if p) + "."
        out.append(RankReward(level, str(texts.get("name", sid)), detail))
    return out


def _gated_drops(faction_id: str) -> list[RankReward]:
    """Rank-gated drops: loot tables whose conditions name this faction."""
    out: list[RankReward] = []
    for row in cdb.lines("lootTable"):
        for loot in row.get("loot") or []:
            cond = ((loot.get("conditions") or {}).get("reputation") or {})
            if cond.get("faction") != faction_id:
                continue
            level = int(cond.get("level", 0) or 0)
            proba = float(loot.get("proba", 0) or 0)
            lo = loot.get("itemMin", loot.get("itemMax", ""))
            hi = loot.get("itemMax", "")
            span = f"{lo}–{hi}" if lo != hi else f"{hi}"
            out.append(RankReward(
                level,
                f"{loot.get('item', '?')} drops from {row.get('id', '?')}",
                f"{proba * 100:.0f}% · {span} per drop"))
    return out


def _faction_rewards(faction_id: str) -> list[RankReward]:
    """The game's own per-rank unlock text from `faction.json`.

    `reputation.rewards[i]` grants rank `i + 1`: the sheet carries eight
    entries and the rank-5/7 anchors (duration bonus, vitality) land on
    the ranks the station rewards already state, so the mapping is
    checked, not guessed. Unknown factions (and the reward-less Herald)
    yield nothing — the ladder simply shows no faction line there.
    """
    row = cdb.by_id("faction").get(faction_id) or {}
    descs = (row.get("reputation") or {}).get("rewards") or []
    out: list[RankReward] = []
    for i, desc in enumerate(descs):
        if str(desc):
            out.append(RankReward(level=i + 1, title=str(desc)))
    return out


def rewards(faction_id: str) -> list[RankReward]:
    """Everything rank `N` grants for one faction, lowest rank first.

    Achievements (name + points) ride with the station rewards, standing
    skills and gated drops, so a rank is one complete row: what the game
    gives, as the sheets state it.
    """
    achs = _rep_achievements().get(faction_id) or {}
    out: list[RankReward] = []
    for level, (ach_id, name, points) in achs.items():
        # No "Achievement: " prefix on the title: every line on this ladder
        # is a rank reward and the detail already says what it is, so the
        # prefix was noise repeated on every row.
        out.append(RankReward(level, name or ach_id,
                              f"{points} achievement points"))
    out.extend(_standing_skills(faction_id))
    out.extend(_gated_drops(faction_id))
    out.extend(_station_rewards(faction_id))
    out.extend(_faction_rewards(faction_id))
    return sorted(out, key=lambda r: (r.level, r.title))
