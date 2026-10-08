"""Shoot every app page to a PNG, so a UI change can be reviewed by EYE.

    python build_tools/dev/shoot_pages.py                 # every page, sub-tab, overlay
    python build_tools/dev/shoot_pages.py --demo          # ... with demo scene seeded (see demo_seed.py)
    python build_tools/dev/shoot_pages.py --only gear,settings:DPS
    python build_tools/dev/shoot_pages.py --list          # the catalogue, no Qt
    python build_tools/dev/shoot_pages.py --show          # real desktop windows

Why this exists: the suite can only ever check what a test can READ. A label's
text, a widget's height, which widget is visible — all readable, and all of them
can be right while the page looks wrong (a clipped row, a label over a
neighbour, the wrong font, a card that never paints). Those need a picture and
an eye. `tests/` gives you the dump; this gives you the picture.

It drives the REAL `ControlPanel` — the same class, mixins and QSS the app
builds, with `theme.apply()` so the bundled fonts are loaded rather than a dev
box fallback — then walks it and grabs each surface:

* every `NAV` page (the catalogue comes from `nav_registry`, so a new page is a
  new shot and a deleted one leaves nothing behind);
* the Items page's modes and, inside Enchants, each strip tab;
* each Settings sub-tab;
* each HUD overlay window.

Each surface is grabbed WHILE it is the current one — navigate, settle, grab, in
one step. Collecting first and grabbing afterwards is the bug this tool shipped
with for its first run: the panel is a single live object, so a second pass
photographs whatever the walk left on screen and 37 "pages" came back as 10
pictures. Hence the duplicate report at the end: two shots that are pixel for
pixel the same are usually a walk that stopped navigating.

Three things it never does, on purpose:

* it never touches the game — the panel is built with `model=None`, so nothing
  attaches and nothing is read;
* it never writes the user's live moddata — `FAREVER_MODDATA_DIR` is pointed at
  a fresh temp dir before the app is imported, the same redirection the suite
  makes (settings/collection saves land there and are thrown away);
* it never writes outside `--out`, which defaults to
  `ai/workspace/shots/<date_time>/` — the one scratch location this repo allows
  (a stray folder at the repo root is a reported hygiene finding).

Headless by default (`QT_QPA_PLATFORM=offscreen`), which is what makes it
runnable from a test-ish shell and repeatable; `--show` swaps in the real
platform for a shot of how it actually looks on the desktop.

A shot that comes back blank makes the exit status non-zero — a file on disk is
not evidence that anything was drawn.

Two runs are NOT byte-identical, by design: the panel's own live bits move (a
16x6px status indicator in the left rail, the Log page's text, a run timer), so
compare two runs by eye rather than by hash. The HUD windows, which have no such
chrome, do come back byte for byte the same.
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import hashlib
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRATCH = ROOT / "ai" / "workspace" / "shots"
DEFAULT_SIZE = (1600, 1000)

#: Run as a SCRIPT (`python build_tools/dev/shoot_pages.py`), sys.path[0] is
#: this folder, not the repo root — the package is importable only once the root
#: is on the path. `devicons.py` never needs this because the app loads it by
#: file path from inside the package's own process.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# --- the catalogue, before any Qt is imported -----------------------------

def page_keys() -> list[str]:
    """The `NAV` page keys, in sidebar order."""
    from farever_companion.ui.nav_registry import NAV
    return [key for key, _icon, _label in NAV]


def overlay_keys() -> list[str]:
    """The HUD overlay keys the manager can build (runtime string imports)."""
    from farever_companion.ui.overlay_manager import _OVERLAY_SOURCES
    return list(_OVERLAY_SOURCES)


def catalogue() -> list[str]:
    """What `--only` accepts without Qt: pages and overlays. Sub-tabs are
    discovered from the built panel (they live on the page objects)."""
    return page_keys() + overlay_keys()


# --- Qt side ---------------------------------------------------------------

def _redirect_moddata() -> str:
    """Point the app at a throwaway moddata dir. MUST run before the app's
    config is imported: a shot that saves settings is how the user's own file
    gets overwritten (2026-09-17), so the redirect goes in first."""
    d = tempfile.mkdtemp(prefix="farever_shots_")
    os.environ["FAREVER_MODDATA_DIR"] = os.path.join(d, "dev-moddata")
    return os.environ["FAREVER_MODDATA_DIR"]


def _settle(app, rounds: int = 25, ms: int = 10) -> None:
    """Let layouts, fonts and deferred paints land before the grab (250ms).

    `processEvents()` alone is not enough for a first paint: the panel lays out
    on a deferred pass, builds a page's content on `singleShot(0)` timers and
    pre-warms the next one at 150ms, so grabbing too early photographs a page
    that is still assembling — which showed up as a page matching its own
    default sub-tab in one run and not the next."""
    from PySide6 import QtCore
    for _ in range(rounds):
        app.processEvents()
        QtCore.QThread.msleep(ms)
    app.processEvents()


def _grab(app, name: str, widget, out: pathlib.Path) -> dict:
    """Save one shot and judge it: a uniform image is a failed render."""
    from PySide6 import QtGui
    _settle(app, rounds=10)
    pix: QtGui.QPixmap = widget.grab()
    path = out / f"{name}.png"
    if pix.isNull() or not pix.save(str(path)):
        return {"name": name, "path": path, "ok": False, "digest": "",
                "why": "grab was empty or the PNG did not write"}
    img = pix.toImage()
    step = max(1, min(img.width(), img.height()) // 200)     # sample, not every px
    seen: set[str] = set()
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            seen.add(img.pixelColor(x, y).name())
            if len(seen) > 64:                               # plenty: it drew
                break
        if len(seen) > 64:
            break
    ok = len(seen) > 1
    return {"name": name, "path": path, "ok": ok, "w": img.width(),
            "h": img.height(), "bytes": path.stat().st_size,
            "colours": len(seen),
            "digest": hashlib.md5(bytes(img.bits())).hexdigest()[:10],
            "why": "" if ok else "the whole image is one colour — nothing drew"}


class _Shooter:
    """Builds the real panel once, then walks it and grabs as it goes."""

    def __init__(self, app, size: tuple[int, int], want_overlays: bool,
                 only: list[str], demo: bool = False):
        from PySide6 import QtGui

        from farever_companion.config import Settings
        from farever_companion.ui import theme
        from farever_companion.ui.control_panel import ControlPanel

        self.app = app
        self.only = only
        theme.apply(app)                      # the real sheet AND the real fonts
        self.font = QtGui.QFontInfo(app.font()).family()
        self.panel = ControlPanel(Settings())  # model=None: nothing attaches
        self.panel.resize(*size)
        self.want_overlays = want_overlays
        self.demo = demo
        self.notes: list[str] = []

    # --- naming and filtering --------------------------------------------
    def _wanted(self, name: str) -> bool:
        """A bare page name also takes its children (`gear` -> `gear-*`)."""
        if not self.only:
            return True
        return any(name == k or name.startswith(k + "-") for k in self.only)

    def _goto(self, target: str) -> None:
        self.panel._select_nav(target)
        _settle(self.app)

    # --- the walk ---------------------------------------------------------
    def shoot(self, out: pathlib.Path) -> list[dict]:
        """Navigate and grab in ONE pass, so each shot is the surface it is
        named after. (A collect-then-grab split photographs the last page 37
        times — see the module docstring.)"""
        shots: list[dict] = []

        def take(name: str, widget=None) -> None:
            """Grab NOW — the widget is live state, and it will not be the
            current one by the time the walk ends."""
            if self._wanted(name):
                if self.demo:
                    from build_tools.dev import demo_seed as _demo
                    _demo.keep_alive()
                shots.append(_grab(self.app, name, widget or self.panel, out))

        for key in page_keys():
            self._goto(key)
            take(key)
            if key == "gear":
                self._walk_items(take)
            elif key == "settings":
                self._walk_settings(take)
        if self.want_overlays:
            self._walk_overlays(take)
        return shots

    def _walk_items(self, take) -> None:
        """The Items page's own tabs, and the Enchants strip's tabs inside it."""
        tabs = getattr(self.panel, "_items_tabs", None)
        for mode in ([t for t in tabs._btns] if tabs is not None else []):
            self._goto(f"gear:{mode}")
            take(f"gear-{mode.lower()}")
            if mode != "Enchants":
                continue
            strip = getattr(self.panel, "_ench_tabs", None)
            for tab in ([t for t in strip._btns] if strip is not None else []):
                strip._btns[tab].click()
                _settle(self.app, rounds=6)
                take(f"gear-enchants-{tab.lower()}")

    def _walk_settings(self, take) -> None:
        for tab in list(getattr(self.panel, "_TAB_ORDER", []) or []):
            self._goto(f"settings:{tab}")
            take(f"settings-{tab.lower()}")

    def _walk_overlays(self, take) -> None:
        """Each HUD window, grabbed while it is up. A HUD that cannot build
        with no game attached is a note, not a failure: several are driven by
        live model data and have nothing to draw without it."""
        mgr = getattr(self.panel, "overlay_mgr", None)
        for key in overlay_keys():
            try:
                mgr.request(key, True)
                _settle(self.app, rounds=8)
                ov = mgr.get(key)
            except Exception as exc:                   # a HUD that cannot build
                self.notes.append(f"overlay {key}: {type(exc).__name__}: {exc}")
                continue
            if ov is None:
                self.notes.append(f"overlay {key}: no window came back")
                continue
            try:
                # HUDs tick on slow timers that may not have fired yet in
                # the settle window — drive one tick explicitly (the app's
                # own per-frame entry, except the minimap whose timers live
                # on its canvas), so the shot is the surface it is named
                # after rather than a first-paint empty.
                tick = getattr(ov, "_tick", None)
                if callable(tick):
                    tick()
                canvas = getattr(ov, "canvas", None)
                refresh = getattr(canvas, "refresh", None)
                if callable(refresh):
                    refresh()
                _settle(self.app, rounds=4)
            except Exception as exc:
                self.notes.append(f"overlay {key} (refresh): {exc}")
            take(f"overlay-{key}", ov)
            try:
                mgr.request(key, False)
                _settle(self.app, rounds=3)
            except Exception as exc:
                self.notes.append(f"overlay {key} (close): {exc}")


# --- the gallery -----------------------------------------------------------

def _data_uri(path: pathlib.Path) -> str:
    """The PNG inlined. The gallery has to be ONE file: the app's preview tab
    serves the html alone, so a relative `<img src="codex.png">` renders blank
    — a review page you cannot actually look at."""
    return ("data:image/png;base64," +
            base64.b64encode(path.read_bytes()).decode("ascii"))


def _gallery(shots: list[dict], out: pathlib.Path, size: tuple[int, int],
             head: str, dupes: list[list[str]]) -> pathlib.Path:
    """An HTML page with every shot inline, so review is scroll-and-look."""
    rows = "\n".join(
        f'<figure><a href="{s["path"].name}" target="_blank">'
        f'<img src="{_data_uri(s["path"])}" width="760"></a>'
        f'<figcaption><b>{s["name"]}</b> — {s.get("w", "?")}x{s.get("h", "?")}'
        f'{" ⚠ " + s["why"] if s.get("why") else ""}</figcaption></figure>'
        for s in shots)
    dup_note = ""
    if dupes:
        dup_note = ("<div class='meta' style='color:#eac331'>identical shots: "
                    + "; ".join(", ".join(g) for g in dupes)
                    + " — if that is a surprise, the walk stopped navigating</div>")
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>FareverMod — page shots</title>
<style>
  body {{ background:#0e0f13; color:#dee3e8; font:14px/1.5 'Segoe UI',sans-serif;
         margin:0; padding:24px 28px 60px; }}
  h1 {{ font-size:20px; letter-spacing:2px; text-transform:uppercase;
        margin:0 0 2px; }}
  .meta {{ color:#87929a; font-size:12px; margin-bottom:18px; }}
  figure {{ background:#1b2024; border:1px solid #3e484f; border-radius:8px;
            margin:0 0 22px; padding:14px 16px; }}
  img {{ border:1px solid #3e484f; border-radius:4px; max-width:100%; }}
  figcaption {{ color:#bdc8d1; font-size:12px; margin-top:8px; }}
  a {{ color:#38bdf8; text-decoration:none; }}
</style></head>
<body>
  <h1>FareverMod — page shots</h1>
  <div class="meta">{len(shots)} surfaces · {size[0]}x{size[1]} per window ·
  generated {_dt.datetime.now():%Y-%m-%d %H:%M} at <code>{head}</code> by
  <code>build_tools/dev/shoot_pages.py</code> · every shot is embedded, so this
  file stands alone; the folder also has the original PNGs</div>
{dup_note}
{rows}
</body></html>
"""
    path = out / "gallery.html"
    path.write_text(html, encoding="utf-8")
    return path


def _index_md(shots: list[dict], out: pathlib.Path, font: str,
              size: tuple[int, int], head: str,
              dupes: list[list[str]]) -> pathlib.Path:
    lines = [f"# Page shots — {_dt.datetime.now():%Y-%m-%d %H:%M}", "",
             f"- {len(shots)} surfaces at {size[0]}x{size[1]}",
             f"- font resolved: {font}", f"- commit: {head}",
             "- open `gallery.html` to review by eye",
             "- the panel's live bits (a status indicator in the left rail, the "
             "Log page, a run timer) differ between runs, so review by eye "
             "rather than by hash; the HUD windows are byte-stable", ""]
    if dupes:
        lines += ["## Identical shots", ""]
        lines += [f"- {', '.join(g)}" for g in dupes]
        lines += ["", "Two surfaces can legitimately match (a page and its "
                  "default tab), but a long group usually means the walk "
                  "stopped navigating.", ""]
    lines += ["| shot | size | bytes | colours | digest |", "|---|---|---|---|---|"]
    lines += [f"| `{s['name']}` | {s.get('w')}x{s.get('h')} | {s.get('bytes')} | "
              f"{s.get('colours')} | `{s.get('digest', '')}` |" for s in shots]
    path = out / "INDEX.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _duplicates(shots: list[dict]) -> list[list[str]]:
    """Groups of shots that came back pixel for pixel identical."""
    by_digest: dict[str, list[str]] = {}
    for s in shots:
        if s.get("digest"):
            by_digest.setdefault(s["digest"], []).append(s["name"])
    return [sorted(v) for v in by_digest.values() if len(v) > 1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None,
                    help=f"where the PNGs go (default {SCRATCH}/<date_time>)")
    ap.add_argument("--only", default="",
                    help="comma-separated shot names (see --list); a page name "
                         "also takes its sub-tabs")
    ap.add_argument("--list", action="store_true", help="print the catalogue and exit")
    ap.add_argument("--size", default=f"{DEFAULT_SIZE[0]}x{DEFAULT_SIZE[1]}",
                    help="window size, WxH")
    ap.add_argument("--show", action="store_true",
                    help="use the real desktop platform instead of offscreen")
    ap.add_argument("--no-overlays", action="store_true",
                    help="skip the HUD overlay windows")
    ap.add_argument("--demo", action="store_true",
                    help="seed the shooter-only demo scene (demo_seed.py): fake "
                         "heroes + real tracker events, demo PB rows, log and "
                         "ping values, so pages photograph with content")
    args = ap.parse_args(argv)

    if args.list:
        print("pages:   " + ", ".join(page_keys()))
        print("overlays:" + ", ".join(overlay_keys()))
        print("(sub-tabs — the Items modes, the Enchants strip and the Settings "
              "tabs — are discovered from the built panel)")
        return 0

    only = [k.strip() for k in args.only.split(",") if k.strip()]
    known = set(catalogue())
    unknown = [k for k in only if k not in known
               and not any(k.startswith(p + "-") for p in known)]
    if unknown:
        return _fail(f"unknown shot name(s): {', '.join(unknown)}. "
                     f"Known: {', '.join(sorted(known))}")

    try:
        w, h = (int(v) for v in args.size.lower().split("x", 1))
    except ValueError:
        return _fail(f"--size wants WxH, got {args.size!r}")

    if not args.show:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    moddata = _redirect_moddata()

    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    shooter = _Shooter(app, (w, h), not args.no_overlays, only, demo=args.demo)
    if args.demo:
        from build_tools.dev import demo_seed as _demo
        for note in _demo.seed_all(shooter.panel):
            print(f"note: {note}", file=sys.stderr)
    stamp = _dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    out = pathlib.Path(args.out).resolve() if args.out else SCRATCH / stamp
    out.mkdir(parents=True, exist_ok=True)

    shots = shooter.shoot(out)
    if not shots:
        return _fail("nothing matched — the panel came back with no surfaces")

    for line in shooter.notes:
        print(f"note: {line}", file=sys.stderr)

    dupes = _duplicates(shots)
    head = _git_head()
    gallery = _gallery(shots, out, (w, h), head, dupes)
    index = _index_md(shots, out, shooter.font, (w, h), head, dupes)

    name_w = max(len(s["name"]) for s in shots)
    print(f"font {shooter.font} · commit {head} · "
          f"moddata {moddata} (throwaway)")
    for s in shots:
        state = "ok" if s["ok"] else "BLANK"
        print(f"  {s['name']:<{name_w}}  {s.get('w', '?'):>4}x{s.get('h', '?'):<4} "
              f"{s.get('bytes', 0):>8} B  {state}  {s.get('digest', '')}"
              f"{'  ' + s['why'] if s.get('why') else ''}")
    for g in dupes:
        print(f"identical: {', '.join(g)}", file=sys.stderr)
    print(f"\n{sum(1 for s in shots if s['ok'])}/{len(shots)} shots rendered"
          f" · {len(dupes)} identical group(s)")
    print(f"gallery: {gallery}")
    print(f"index:   {index}")

    bad = [s for s in shots if not s["ok"]]
    return _fail(f"{len(bad)} shot(s) did not render: "
                 f"{', '.join(s['name'] for s in bad)}") if bad else 0


def _fail(msg: str) -> int:
    print(f"shoot_pages: {msg}", file=sys.stderr)
    return 1


def _git_head() -> str:
    """The commit the shots were taken at — the only way to say later which
    revision a picture shows."""
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "(unknown)"
    except Exception:
        return "(unknown)"


if __name__ == "__main__":
    sys.exit(main())
