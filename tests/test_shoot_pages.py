"""`build_tools/dev/shoot_pages.py` — the by-eye screenshot walk.

A screenshot tool is only useful if a shot is the surface its NAME says. The
first version broke exactly that: it walked the panel collecting widgets and
grabbed them all afterwards, and since a `ControlPanel` is ONE live widget, 37
"pages" came back as 10 pictures — four groups of pixel-identical PNGs, with
whole pages missing and nothing in the output saying so. These tests pin the
promise against stubs, so the walk can be checked without a screen: each grab
must land while its own surface is current, the catalogue must stay derived from
the registries, and two identical shots must be reported rather than passed off
as two pages.

The Qt-free parts (naming, filtering, duplicate grouping, the moddata redirect)
are called directly; the walk runs against a stub panel that records the
navigation in progress at each grab, which is the only thing the real panel
cannot tell us after the fact.
"""
from __future__ import annotations

import os
import pathlib
import tempfile

import pytest

from build_tools.dev import shoot_pages as SP


# --- stubs -----------------------------------------------------------------

class _StubBtn:
    def __init__(self, text: str):
        self.text = text
        self.clicks = 0

    def click(self) -> None:
        self.clicks += 1


class _StubTabs:
    """The shape the walk reads off `C.SegmentedControl` / `C.UnderlineTabs`."""

    def __init__(self, names: list[str]):
        self._btns = {n: _StubBtn(n) for n in names}
        self.current = names[0] if names else ""

    def currentText(self) -> str:                      # noqa: N802 (Qt spelling)
        return self.current


class _StubOverlays:
    def __init__(self):
        self.windows: dict[str, object] = {}
        self.made: dict[str, object] = {}     # every window ever handed out
        self.calls: list[tuple[str, bool]] = []

    def request(self, key: str, on: bool) -> None:
        self.calls.append((key, on))
        if on:
            ov = object()                     # a window of its own
            self.windows[key] = ov
            self.made[key] = ov
        else:
            self.windows.pop(key, None)

    def get(self, key: str):
        return self.windows.get(key)


class _StubPanel:
    """Records navigation, so a grab can be judged against what was current."""

    ITEMS = ["Gear", "Items", "Loadout", "Enchants", "Farm"]
    STRIP = ["Gems", "Augments", "Scrolls", "Soulwell"]
    SETTINGS = ["Layers", "HUD's", "DPS"]

    def __init__(self):
        self.target = ""
        self.events: list[tuple] = []                  # ("nav", t) / ("tab", t)
        self._items_tabs = _StubTabs(self.ITEMS)
        self._ench_tabs = _StubTabs(self.STRIP)
        self._TAB_ORDER = self.SETTINGS
        self.overlay_mgr = _StubOverlays()

    def _select_nav(self, target: str) -> None:
        self.target = target
        self.events.append(("nav", target))

    def click_strip(self, text: str) -> None:
        self._ench_tabs._btns[text].click()
        self._ench_tabs.current = text
        self.events.append(("tab", text))


@pytest.fixture
def walk(monkeypatch, tmp_path):
    """Builder for a shooter whose grabs are recorded instead of written."""
    def build(only: list[str] | None = None, want_overlays: bool = True):
        panel = _StubPanel()
        shooter = object.__new__(SP._Shooter)          # the walk, not the panel
        shooter.app = None
        shooter.panel = panel
        shooter.only = only or []
        shooter.want_overlays = want_overlays
        shooter.notes = []
        grabbed: list[tuple[str, object, str]] = []

        def fake_grab(app, name, widget, out):
            grabbed.append((name, widget, panel.target))
            return {"name": name, "path": out / f"{name}.png", "ok": True,
                    "w": 8, "h": 8, "bytes": 8, "colours": 2,
                    "digest": f"d{len(grabbed)}", "why": ""}

        monkeypatch.setattr(SP, "_grab", fake_grab)
        monkeypatch.setattr(SP, "_settle", lambda *a, **k: None)
        return shooter, panel, grabbed

    return build


# --- the walk --------------------------------------------------------------

def test_each_shot_is_grabbed_while_its_own_surface_is_current(walk, tmp_path):
    """The regression the tool shipped with: a shot named after a surface must
    show THAT surface, which is only true if the grab happens during the visit
    (the panel is one live widget, so a later pass photographs the last one)."""
    shooter, panel, grabbed = walk()
    shots = shooter.shoot(pathlib.Path(tmp_path))
    assert len(shots) == len(grabbed)

    for name, widget, target in grabbed:
        if name.startswith("overlay-"):
            key = name[len("overlay-"):]
            assert widget is panel.overlay_mgr.made.get(key), (
                f"{name} grabbed {widget!r}, not the {key} HUD window")
            continue
        assert widget is panel, f"{name} is a panel surface"
        # one rule, no naming table: the nav that is in progress at grab time
        # is the surface the shot is named after (`settings:HUD's` ->
        # `settings-hud's`), except inside a tabbed page's strip, where the
        # page's own nav stays put and the strip moved instead.
        assert target, f"{name} was grabbed with no page selected"
        assert name == target.replace(":", "-").lower() or \
            name.startswith(target.replace(":", "-").lower() + "-"), (
            f"{name} was grabbed while {target} was current")

    # and the strip shots really did move the strip, one tab at a time
    strip = [n for n, _w, _t in grabbed if n.startswith("gear-enchants-")]
    assert strip == [f"gear-enchants-{t.lower()}" for t in _StubPanel.STRIP], strip
    assert panel._ench_tabs._btns["Soulwell"].clicks == 1


def test_the_walk_covers_every_page_and_every_overlay(walk, tmp_path):
    shooter, _panel, grabbed = walk()
    shooter.shoot(pathlib.Path(tmp_path))
    names = [n for n, _w, _t in grabbed]
    for key in SP.page_keys():
        assert key in names, f"NAV page {key} has no shot"
    assert names[-len(SP.overlay_keys()):] == \
        [f"overlay-{k}" for k in SP.overlay_keys()]
    assert len(set(names)) == len(names), "a surface was shot twice"


def test_every_items_mode_and_settings_tab_is_shot(walk, tmp_path):
    shooter, panel, grabbed = walk()
    shooter.shoot(pathlib.Path(tmp_path))
    names = [n for n, _w, _t in grabbed]
    for mode in panel.ITEMS:
        assert f"gear-{mode.lower()}" in names
    for tab in panel.SETTINGS:
        assert f"settings-{tab.lower()}" in names


def test_a_hud_that_cannot_build_is_a_note_not_a_failure(walk, tmp_path):
    """Several HUDs have nothing to draw with no game attached. That must be
    reported, not crash the run — and the other HUDs must still be shot."""
    shooter, panel, grabbed = walk()

    def explode(key, on):
        if key == "dungeon" and on:
            raise RuntimeError("no model")
        return _StubOverlays.request(panel.overlay_mgr, key, on)

    panel.overlay_mgr.request = explode
    shots = shooter.shoot(pathlib.Path(tmp_path))
    assert shots, "the walk gave up instead of skipping the broken HUD"
    assert any("dungeon" in n for n in shooter.notes), shooter.notes
    assert "overlay-dungeon" not in [n for n, _w, _t in grabbed]


# --- names and filtering ---------------------------------------------------

def test_the_catalogue_is_derived_from_the_two_registries():
    """No hand-kept list: the pages come from `NAV` and the overlays from the
    manager's runtime import table, so a new page is a shot with no edit here
    (and a renamed one cannot linger)."""
    from farever_companion.ui.nav_registry import NAV
    from farever_companion.ui.overlay_manager import _OVERLAY_SOURCES
    assert SP.page_keys() == [key for key, _i, _l in NAV]
    assert SP.overlay_keys() == list(_OVERLAY_SOURCES)
    assert SP.catalogue() == SP.page_keys() + SP.overlay_keys()


def test_a_bare_page_name_also_takes_its_sub_tabs(walk, tmp_path):
    shooter, _panel, grabbed = walk(only=["settings"])
    shooter.shoot(pathlib.Path(tmp_path))
    names = [n for n, _w, _t in grabbed]
    assert "settings" in names and "settings-dps" in names
    assert not any(n.startswith("overlay-") for n in names), names
    assert not any(n.startswith("gear") for n in names), names


def test_one_sub_tab_can_be_shot_on_its_own(walk, tmp_path):
    shooter, _panel, grabbed = walk(only=["gear-enchants-soulwell"],
                                    want_overlays=False)
    shooter.shoot(pathlib.Path(tmp_path))
    assert [n for n, _w, _t in grabbed] == ["gear-enchants-soulwell"]


def test_an_unknown_shot_name_fails_before_any_window_is_built(capsys):
    """`--only tpyo` must say so rather than shoot everything (or nothing)."""
    assert SP.main(["--only", "tpyo"]) == 1
    err = capsys.readouterr().err
    assert "tpyo" in err and "codex" in err           # names a real one too


def test_identical_shots_are_reported_as_a_group():
    """The output of the collect-then-grab bug was identical PNGs; the report
    is what turns that from "37 shots" into a visible finding."""
    def shot(name, digest):
        return {"name": name, "digest": digest, "ok": True}
    shots = [shot("codex", "aa"), shot("combat", "aa"), shot("gear", "bb"),
             shot("log", "cc")]
    assert SP._duplicates(shots) == [["codex", "combat"]]
    assert SP._duplicates([shot("codex", "aa"), shot("gear", "bb")]) == []


# --- the safety property ---------------------------------------------------

def test_shots_never_write_the_folder_a_live_run_uses():
    """A shot run must not touch the user's own data. The redirect is set
    BEFORE the app's config is imported and points at a throwaway temp folder —
    the 2026-09-17 hazard was a run that saved over the live settings file."""
    from farever_companion.config import store
    saved = os.environ.get("FAREVER_MODDATA_DIR")
    try:
        os.environ.pop("FAREVER_MODDATA_DIR", None)
        live = store.config_dir()                      # what a dev run writes
        redirected = pathlib.Path(SP._redirect_moddata())
        assert store.config_dir() == redirected, "the override must win"
        assert redirected != live
        assert redirected.is_relative_to(pathlib.Path(tempfile.gettempdir()))
        # a second run gets its own folder: one run never reads another's saves
        assert pathlib.Path(SP._redirect_moddata()) != redirected
    finally:
        if saved is None:
            os.environ.pop("FAREVER_MODDATA_DIR", None)
        else:
            os.environ["FAREVER_MODDATA_DIR"] = saved
