"""Demo seeding for the page-shooter ONLY (`shoot_pages.py --demo`).

Builds a clearly-labeled demo scene — fake heroes with "Demo" names, a boss
and trash, real combat events through the REAL `DpsTracker` pipeline — and
attaches it to the shooter's `ControlPanel` so every page photographs with
content instead of empty states.

Nothing here ships: the app never imports this module (it lives in
`build_tools/dev/`, outside the package), and no app code is touched. The
never-fabricate rule is intact — the app with no game still draws nothing;
only this dev script hands the panel a fake model, exactly like the tests do
with `tests/dps_fakes.py`.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tests.dps_fakes as F
from farever_companion.data import units as udata
from farever_companion.core.damage_events import DamageEvent
from farever_companion.core.dps_tracker import DpsTracker

# Demo identities: obviously not real players, real hero classes.
DEMO_HEROES = [
    (F.PA, "DemoYou", "ent.hero.Warrior"),
    (F.TEAM, "DemoMage", "ent.hero.Mage"),
    (0x2223, "DemoRogue", "ent.hero.Rogue"),
]

# Real skill ids (seen in tests) so the breakdown shows real names.
DEMO_SKILLS = [
    "Sword_Base_Attack", "Book_Fireball_Skill1", "Bow_Base_Attack",
    "Axe_Base_Attack", "Meteor", "Judgment",
]


class DemoModel(F._FakeModel):
    """Fake model with pure-python scene answers for the HUDs.

    The live queries (nearest_*, chests, heading…) normally read game
    memory; here they answer from the demo units above, so the entity /
    minimap / dungeon HUDs photograph with rows instead of empty states.
    Anything without demo data answers empty, exactly like a quiet zone."""

    chests: list = []
    units_ok = False
    # The demo is a heroic dungeon run: opens the dungeon-HUD instance gate
    # (game_state.in_instance) and stamps boards the way a real run does.
    is_dungeon = True

    class _DemoHl:
        """Memory stub: every read misses, so health() returns None cleanly."""
        class proc:
            @staticmethod
            def try_read(addr, n):
                return None

        @staticmethod
        def ptr(addr):
            return None

    hl = _DemoHl()

    def _by_dist(self, xyz, want_hero: bool, n: int, max_dist: float):
        # Live queries return (entity, dist) tuples (see LiveModel._ranked).
        out = []
        for u in self._units:
            if bool(getattr(u, "is_hero", False)) != want_hero:
                continue
            try:
                d = u.dist2d(xyz[0], xyz[1])
            except Exception:
                continue
            if max_dist and d > max_dist:
                continue
            out.append((u, d))
        out.sort(key=lambda t: t[1])
        return out[:n] if n else out

    def nearest_enemies(self, xyz, n: int, max_dist: float = 0.0, **kw):
        # Mirror the live codex filter: engine objects (training dummy)
        # never read as enemies.
        rows = [(u, d) for u, d in self._by_dist(xyz, False, 0, 0.0)
                if udata.is_codex_unit(getattr(u, "unit_id", None))]
        return rows[:n] if n else rows

    def nearest_group_members(self, xyz, n: int, max_dist: float = 0.0, **kw):
        return self._by_dist(xyz, True, n, max_dist)

    def nearest_companions(self, xyz, n: int, max_dist: float = 0.0, **kw):
        return []

    def gatherables(self, player_zone=None, max_dist: float = 0.0, **kw):
        return []

    def live_chests(self, player_zone=None, max_dist: float = 0.0, **kw):
        return []

    def live_orbs(self, *a, **kw):
        return []

    def live_chest_orbs(self, *a, **kw):
        return []

    def obelisks(self, player_zone=None, max_dist: float = 0.0, **kw):
        return []

    def nearest_chests_merged(self, *a, **kw):
        return []

    def loot_drops(self, *a, **kw):
        return []

    def food_stations(self, *a, **kw):
        return []

    def world_orb_fx(self, *a, **kw):
        return []

    def hero_class_of(self, hero_addr):
        for u in self._units:
            if getattr(u, "addr", None) == hero_addr:
                return getattr(u, "cls", None)
        return None

    def hero_display_name(self, hero):
        name = self.player_name(getattr(hero, "addr", 0))
        if name:
            return name
        cls_name = getattr(hero, "cls", None) or ""
        if cls_name.startswith("ent.hero."):
            return cls_name.replace("ent.hero.", "")
        return getattr(hero, "unit_id", None) or "Hero"

    def are_in_same_group(self, addr):
        return True

    def player_xyz(self):
        # NOT (0,0,0): the minimap reads a literal 0.0 x as "no player"
        # and paints "Waiting for player" instead of the radar. (1,1) sits
        # beside the demo party, so distances stay a few meters.
        return (1.0, 1.0, 0.0)

    def player_heading(self):
        return 0.0

    def camera_yaw(self):
        return 0.0

    def player_class(self):
        return "ent.hero.Warrior"

    def dungeon_mode(self):
        return "heroic"

    def encounter_state(self):
        return None

    def party_health_state(self, *a, **kw):
        return {}

    def view_matrix(self):
        return None

    def foe_target_line(self, el):
        # Demo: the boss is on the local hero.
        return "\u25ce DemoYou (You)"


def build_demo_model() -> tuple:
    """A fake model + tracker with a finished-looking fight in the session."""
    heroes = [F._hero(addr, cls=cls) for addr, _, cls in DEMO_HEROES]
    boss = F._foe(F.BOSS, uid="Nepsilon", hp=8000.0, is_boss=True)
    # Real codex trash ids (is_codex_unit-verified): the HUD's live filter
    # keeps these, and drops engine objects like the training dummy.
    trash = F._foe(F.FOE, uid="Kobold_Prisoner", hp=500.0)
    trash2 = F._foe(0x3334, uid="HunterShepherd", hp=650.0)
    trash2.x, trash2.y = 9.0, 3.0
    dummy = F.training_dummy(0x7777)
    names = {addr: name for addr, name, _ in DEMO_HEROES}
    model = DemoModel(names=names, units=[*heroes, boss, trash, trash2, dummy])
    tr = DpsTracker(model)
    model.dps = tr

    # A finished-looking ~90s parse: three heroes rotating skills onto the
    # boss, plus boss bite-back so the Taken channel is non-zero. keep_alive
    # tops it up with fresh hits during the walk so HUDs stay live.
    global _BUILT, _LAST_VOLLEY
    now = time.time()
    n = 0
    for sec in range(90, 0, -3):
        addr, _, _ = DEMO_HEROES[n % 3]
        skill = DEMO_SKILLS[n % len(DEMO_SKILLS)]
        model.damage.push(DamageEvent(
            amount=400.0 + (n * 37) % 900, skill=skill,
            source_addr=addr, target_addr=F.BOSS, t=now - sec))
        if n % 5 == 0:
            model.damage.push(DamageEvent(
                amount=150.0 + (n * 13) % 200, skill="Mob_Bite",
                source_addr=F.BOSS, target_addr=addr, t=now - sec + 1))
        n += 1
        tr.update()
    # A few whacks on the training dummy so the dummy HUD has a session.
    for i in range(6):
        model.damage.push(DamageEvent(
            amount=500.0 + i * 50, skill="Sword_Base_Attack",
            source_addr=F.PA, target_addr=0x7777, t=time.time() - (6 - i)))
    tr.update()
    n = _volley(model, tr, time.time(), n, count=8)
    _BUILT = (model, tr, n)
    _LAST_VOLLEY = time.time()
    return model, tr


def seed_pb_rows() -> None:
    """Demo speedrun history into the shooter's throwaway moddata."""
    from farever_companion.config import write_speedrun_history
    base = time.time()
    rows = [
        {"char": "DemoYou", "dungeon": "Abandoned Mines", "boss": "Gorgon Overseer",
         "full_ms": 312_400, "boss_ms": 95_200, "mode": "heroic", "at": base - 86400},
        {"char": "DemoYou", "dungeon": "Abandoned Mines", "boss": "Gorgon Overseer",
         "full_ms": 298_100, "boss_ms": 88_700, "mode": "heroic", "at": base - 43200},
        {"char": "DemoMage", "dungeon": "Ruins of Gorgon's Hollow", "boss": "Hollow Matron",
         "full_ms": 421_000, "boss_ms": 132_500, "mode": "veteran", "at": base - 3600},
    ]
    write_speedrun_history(rows)


def seed_log(panel) -> None:
    """A few representative Activity Log lines through the real log path."""
    for line in (
        "Demo scene loaded: 3 heroes, Nepsilon + 2 trash in range.",
        "DPS capture: Option 2 (Hot Injector) — combat events flowing.",
        "Located DemoYou (Warrior) — tracking across zones.",
        "Speedrun history: 3 demo runs recorded.",
    ):
        try:
            panel.log(line)
        except Exception:
            break


def seed_server(panel) -> None:
    """Demo ping results + player count through the real paint paths."""
    try:
        panel._on_steam_player_count(18_422)
    except Exception:
        pass
    demo_ms = {"na": 42, "eu": 118, "as": 203, "sa": 176, "cn": 289,
               "na_test": 51, "eu_test": 121}
    from farever_companion.ui.pages.server.net import REGIONS
    for region in REGIONS:
        code = region["code"]
        hosts = region.get("hosts") or [("demo.invalid", 0)]
        h, port = hosts[0][0], hosts[0][1]
        panel._ping_on_result(code, f"{h}:{port}", True,
                              demo_ms.get(code, 99),
                              "127.0.0.1", "Demo", "xx")


def _ensure_server_built(panel) -> None:
    """The server page builds lazily: navigate once so cards + badge exist."""
    try:
        panel._select_nav("server")
    except Exception:
        pass


_BUILT: tuple = ()
_LAST_VOLLEY = 0.0


def _volley(model, tr, now: float, n0: int, count: int = 8) -> int:
    """A few fresh hits, right now: keeps the live session in COMBAT."""
    n = n0
    for i in range(count):
        addr, _, _ = DEMO_HEROES[n % 3]
        skill = DEMO_SKILLS[n % len(DEMO_SKILLS)]
        model.damage.push(DamageEvent(
            amount=400.0 + (n * 37) % 900, skill=skill,
            source_addr=addr, target_addr=F.BOSS, t=now - (count - i) * 0.4))
        n += 1
    tr.update()
    return n


def keep_alive() -> None:
    """Fresh hits when the last volley aged out (boss-gone idle is ~6s).

    The shooter calls this before every grab: HUDs render the LIVE session,
    so a walk that outlasts the final seeded hit would photograph zeros."""
    global _BUILT, _LAST_VOLLEY
    if not _BUILT:
        return
    model, tr, n = _BUILT
    if time.time() - _LAST_VOLLEY < 4.0:
        return
    _BUILT = (model, tr, _volley(model, tr, time.time(), n))
    _LAST_VOLLEY = time.time()


def seed_all(panel) -> list[str]:
    """Attach the demo scene to the shooter's panel. Returns notes."""
    notes = []
    model, tr = build_demo_model()
    # Outside pass (FAREVER_DEMO_OUTSIDE=1): park the scene in the overworld
    # so the Entity HUD gathers instead of clearing (it empties inside
    # instances by design), and switch the showcase layers on — fresh
    # Settings default show_enemies/minimap_enemies to False, which
    # photographs empty boards. Throwaway moddata only; never the app.
    if os.environ.get("FAREVER_DEMO_OUTSIDE"):
        model.is_dungeon = False
    # ControlPanel.model is a read-only property onto the attach controller;
    # the fake model goes there (pages read panel.model / model.dps).
    try:
        panel.attach_ctl.model = model
    except Exception as exc:
        notes.append(f"attach model: {type(exc).__name__}: {exc}")
        panel._fallback_dps_tracker = tr
    # Push the fake model into the overlay manager, exactly like a real
    # attach does, so HUD windows built during the walk bind its tracker.
    try:
        panel._on_model_changed(model)
    except Exception as exc:
        notes.append(f"model changed: {type(exc).__name__}: {exc}")
    try:
        seed_pb_rows()
        panel._pb_refresh()
    except Exception as exc:
        notes.append(f"pb seed: {type(exc).__name__}: {exc}")
    for layer in ("show_enemies", "minimap_enemies"):
        try:
            setattr(panel.s, layer, True)
        except Exception as exc:
            notes.append(f"showcase layer {layer}: {type(exc).__name__}: {exc}")
    seed_log(panel)
    _ensure_server_built(panel)
    seed_server(panel)
    try:
        panel._select_nav("overlays")
    except Exception:
        pass
    return notes
