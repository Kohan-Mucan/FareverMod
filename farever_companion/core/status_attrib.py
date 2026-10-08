"""Shared-party-buff status damage: attribution modes + evidence logging.

A skill like Wingsabers' ``DS_Bladeleaf_Skill2`` (Swarmstrike Accord) is
cast once and applies its ``..._Status`` id to every party member in range.
The bridge then stamps each buffed player's boosted chunks with that status
skill and credits them to the STATUS OWNER (the buff's caster), because the
chunk's ``dealer`` is the skill object and the C++ non-hero dealer branch
(``bridge_core.h`` around the ``OFF_BASESKILL_OWNER`` fallback) names the
skill's hero owner rather than the carrier. The caster's row reads ~30k
when that is really the whole party's bonus and they did ~2k of it.

Only party-wide buffs appear under the local hero arrays, so the gate on
"sid is a live buff on the carriers" also isolates Accord-style buffs from
bleeds/DoTs (those live on enemy status arrays and never show here).

Three modes, chosen by the FAREVER_STATUS_ATTRIB env var:
  * ``log``  — today's behavior, but EVERY derived-status event is written
              to ``status_attrib.jsonl`` next to the DPS logs, with both
              candidate answers beside it (the attributed caster and the
              live carriers). This is the baseline evidence.
  * ``split``— re-credit each derived-status event from the attributed
              caster onto one skill row per live carrier, split evenly,
              and mark those rows "(est.)".
  * ``est``  — keep the event on the attributed caster, but mark the row
              "(est.)" so it cannot be read as a direct number.

The intent: run the same session in ``log``/``split``/``est``, compare the
rows, then delete whichever mode does not hold up.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

_LOGGED_MODES = ("log", "split", "est")
_ENV = "FAREVER_STATUS_ATTRIB"


def status_kind_carriers(proc, hl, heroes) -> dict[str, list[tuple[str, bool]]]:
    """Walk every hero's live statuses once -> `{status_kind: [(name, is_me)]}`.

    Covers the event path per drain rather than per event because the walk
    is one hero-statuses array read per hero and a batched fight's chunks
    all credit the same instant. Unreadable / no proc / no statuses means
    an empty map -- the caller falls back to today's attribution.
    """
    from . import inspect as hero_inspect
    snap = {}
    for addr, (name, is_me, *_rest) in list(heroes.items()):
        try:
            for b in hero_inspect.hero_buffs(proc, hl, addr):
                kind = b.get("kind")
                if not kind or kind == "?":
                    continue
                # One entry per PLAYER, not per Status object: a hero can hold
                # several live instances of one kind (every re-cast of a party
                # buff leaves its own), and a split that counted them would
                # hand one player several shares.
                members = snap.setdefault(kind, [])
                if any(m[0] == name for m in members):
                    continue
                members.append((name, is_me, b.get("_addr")))
        except Exception:
            continue
    return snap


def mode() -> str:
    raw = os.environ.get(_ENV, "log").strip().lower()
    return raw if raw in _LOGGED_MODES else "log"


def log_event(*, sid, attributed, carriers, amount, capture_mode,
              is_me_attributed, target, fight_segment) -> None:
    try:
        from ..config import dps_dir
        path = Path(dps_dir()) / "status_attrib.jsonl"
        line = json.dumps({
            "t": time.time(),
            "mode": mode(),
            "sid": sid,
            "capture": capture_mode,
            "attributed": attributed,
            "is_me": bool(is_me_attributed),
            "carriers": [
                {"player": c[0], "is_me": bool(c[1]), "status_addr": c[2] if len(c) > 2 else None}
                if isinstance(c, (tuple, list)) else {"player": c}
                for c in carriers
            ],
            "amount": amount,
            "target": target,
            "segment": fight_segment,
            "split_per_carrier": (amount / len(carriers) if carriers else None),
        }, separators=(",", ":"), default=str)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
