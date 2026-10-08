# FareverMod

A live companion tool for Farever (Heaps / HashLink). It attaches to the running
game and locates your character from **read-only** memory reads, and shows:

- **Entity / loot overlay** — nearest enemies & chests with the real game icons,
  distance, and the closest source's full predicted drop table by rarity.
- **DPS meter** — live DPS, group rankings, per-skill/crit breakdown from real
  per-hit events (the game's own `DamageDisplay` numbers, with the server-synced
  HUD group meter auto-selected when the client provides it).
- **Minimap** — top-down POI radar (chests, gatherables, enemies, obelisks),
  zoom, right-click to mark collectibles done.
- **Rift predictor** — next hourly rift zone + live countdown card in the
  sidebar, with chime reminders before it opens (Settings · Rift) and the
  predicted rift pinned on the map. Pure clock math, so it works even with
  the game closed.
- **Dungeon Secret Orbs** — Automatic detection of InstanceOrbs and activity orbs
  within dungeons, even those not in the overworld static database.
- **Gear, Items & Farm browser** — every item with its drop sources, farm rows, plus loadout and enchant planning.

Overlays, loot prediction, and the minimap come from **read-only, out-of-process**
memory reads. The DPS meter's combat feed depends on your DPS capture mode in
Settings (default **Option 2: Hot Injector**): **Option 1** loads a drop-in proxy
DLL from the game folder, **Option 2** hot-injects a hook DLL into the running
game, and **Option 3** is a pure memory reader with no DLL at all. The DLL modes
only stream combat events out to the meter — they cannot and do not change drops
or any game state (Farever is online & server-authoritative).

> Memory-reader mode never writes to the game. The DLL-based DPS modes run game-loaded
> code to export combat events, so they carry the normal caveats of any game hook.
> Pick Option 3 in Settings for a strictly DLL-free session.

## How it works (overview)

The whole bet is that an external reader plus a separate Qt window can surface
live info while leaving the game alone.

- **Out-of-process, read-only memory path.** A small Rust extension opens the game
  with a read-only handle (no write / alloc / protect access) and exposes only
  reads and a memory scan. No `WriteProcessMemory`-style write primitive exists
  anywhere in the tree, and a test enforces that.
- **Reflection, not hard-coded addresses.** The game runs on HashLink, which keeps
  class and field names in the runtime. The app reads those to identify objects by
  *name* (your character, enemies, chests, …) rather than relying on brittle fixed
  addresses, so it tends to survive game updates.
- **A stable anchor for the player.** Instead of rescanning a multi-GB heap on
  every zone change, it resolves one long-lived game object and follows it to your
  character each frame — so tracking keeps working across loads and menus with no
  repeated scan.
- **Batched scene reads.** Each frame it pulls the live unit / interactible lists
  in as few reads as possible, then interprets them in Python for the overlays.
- **Loot is predicted entirely offline.** Drop tables come from the game's own data
  files (CastleDB); the tool never reads or influences a live roll — drops are
  server-authoritative, which a client cannot change.
- **DPS** comes from the game's own per-hit damage objects: the floating
  `ui.comp.DamageDisplay` numbers carry amount, skill, crit/kill and the
  authoritative caster; the client's server-synced HUD group meter is probed
  and takes over when live (whole group, not distance-bounded). No HP polling
  is used to make damage numbers - health is only read for the boss bar and
  encounter state, and HP-diff is never used to fabricate a total. The combat
  events reach the meter via the capture mode you pick in Settings: **Option 1:
  Drop-In Proxy** (a proxy DLL in the game folder), **Option 2: Hot Injector**
  (hook DLL injected into the live game, the default), or **Option 3: Memory
  Reader** (pure passive reads, no DLL).

The tool *reads* derived, public-facing information for a fan wiki and personal
use.

## Layout

```
companion/
  native/            Rust memory reader (farever_native, PyO3)
  farever_companion/ the app (core / data / combat / geo / ui)
  tests/             headless logic tests
  CREDITS.md         attribution
```

Data (CDB sheets, icons, names, chest positions) is stored in the `assets/`
directory and consolidated into the app during build.

## Utility Scripts

The `build_tools/` directory holds the dev-only helper scripts (asset and
launcher checks, the compiled-field and unnamed-item audits, the icon/overlay
preview page under `build_tools/dev/`, and the pre-build environment doctor
`build_tools/doctor.bat`). They never ship inside the app.

## Run from source

```bat
:: from companion\  (a .venv with the deps is already set up)
.venv\Scripts\python.exe -m maturin develop --release -m native\Cargo.toml   :: build the Rust extension (farever_native)
.venv\Scripts\python.exe -m farever_companion
```

If `.venv\` is missing, recreate it:

```bat
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If you don't build the Rust extension, the app falls back to `pymem` for basic
reads, but the **player locate** (memory scan) needs `farever_native`.

## Test

```bat
.venv\Scripts\python.exe -m pytest -q
```

## Build the single-file .exe

```bat
build-mod.bat    :: one-shot pipeline: Rust ext -> compile data shims -> PyInstaller -> verify
```

`build-mod.bat` handles the whole pipeline in one go (Rust `farever_native`,
`compiler.py` embedded shims, PyInstaller, `build_tools/verify_assets.py`) and
names the output `dist\FareverMod-<version>-<commit>.exe` from the latest git
commit. The resulting exe (~105 MB, self-contained) is published as a GitHub
**release asset**, not committed to the repo.

## Use

1. Launch Farever and load fully into the world.
2. Run the app — it attaches **automatically** when Farever is running and locates
   your character once you're in-world (no button; the status line shows when it's
   ready and follows you across zones/menus).
3. Open the overlays. Drag them by their title bars; set opacity / click-through
   in the control panel.

## Status

The core overlays (entity/loot, DPS, minimap) and the read-only player locate are
**live-validated**. DPS totals are fed by real combat events (bridge DLL or
DamageDisplay reader depending on capture mode, auto-probing the HUD group
meter); the Top DPS overlay and Combat &
DPS Analysis page show a status line for the active source and stay empty -
never HP-derived - until real events flow. Some newer pieces (e.g. speedrun
difficulty auto-detect) are still being refined.

## Credits

See [`CREDITS.md`](CREDITS.md) for full attribution. In short:

- **Farever** is made by its developers — this is an unofficial community fan
  tool. Please support the game on Steam. Taken down / stripped on request.
- Based on **[Popparoni/FareverPal](https://github.com/Popparoni/FareverPal)**
  — credit for the original codebase and concept.
- Built on the **Heaps** engine + **HashLink** VM (the game's stack); bundled
  fonts (Roboto Condensed) and Lucide icons under their own licenses.
