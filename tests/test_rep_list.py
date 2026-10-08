"""The reputation ladder and its Codex Others "Reputation" list.

Two halves: the DATA (factions, XP rules and per-rank rewards, all read off
the sheets — no hand-recorded numbers) and the VIEW (the Others sub-bar's Rep
chip swapping the card grid for the ladder list, the NPC chip's pattern).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6 import QtWidgets  # noqa: E402

from farever_companion import paths  # noqa: E402
from farever_companion.data import reputation as rep  # noqa: E402
from farever_companion.data import soulwell as swd  # noqa: E402


def _data_present() -> bool:
    try:
        return paths.item_drops_path().exists()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _data_present(),
    reason="requires bundled data (assets/data/item_drops.json)")


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _flush(app=None, n: int = 6) -> None:
    app = app or QtWidgets.QApplication.instance()
    for _ in range(n):
        app.processEvents()


# --- the data -------------------------------------------------------------
def test_the_ladder_has_two_factions_with_ten_ranks_each():
    """The sheets grant ranks to two factions — the Riftstalkers and the
    Pilgrims — with achievements at 1, 5 and 10, so the ladder is 1..10."""
    factions = {f.faction_id: f for f in rep.factions()}
    assert set(factions) == {"Riftstalkers", "Pilgrims"}
    for faction in factions.values():
        assert faction.levels == tuple(range(1, 11))
        assert set(faction.achievements) == {1, 5, 10}
    assert factions["Riftstalkers"].title == "Riftstalkers Sisterhood"
    assert factions["Pilgrims"].title == "Pilgrims of Merilam"


def test_one_rank_costs_3000_xp_and_rifts_pay_400():
    """The sheet's single threshold prices every rank; a rift pays 400."""
    assert rep.xp_per_rank() == 3000
    assert rep.cumulative_xp(1) == 3000
    assert rep.cumulative_xp(10) == 30000
    gains = dict(rep.xp_gains())
    assert gains["Rift completed"] == 400
    # the soulwell gifts pay through the soulwell module, not a copy here
    assert gains["Soulwell Rare gift"] == swd.reputation_gain("rare") == 10
    assert gains["Soulwell Epic gift"] == swd.reputation_gain("epic") == 20


def test_the_riftstalkers_ranks_pay_what_the_sheets_state():
    """Every Riftstalkers rung with a sheet-recorded reward: the rank-2 ore
    drops, the rank-3 standing heal, the rank-5 soulwell minutes, the rank-7
    vitality — plus the 1/5/10 achievements."""
    by_level: dict[int, list] = {}
    for rw in rep.rewards("Riftstalkers"):
        by_level.setdefault(rw.level, []).append(rw)
    # rank 2 is both the gated drop row and the faction sheet's own
    # unlock text for it — two sheets stating the same rung
    assert {r.title for r in by_level[2]} == \
        {"DemonicSoul drops from Riftstalkers_ChaosOre",
         "You can now gather [DemonicSoul] by mining chaos-blessed "
         "deposits"}
    ore = next(r.detail for r in by_level[2]
               if r.title == "DemonicSoul drops from Riftstalkers_ChaosOre")
    assert "25%" in ore and "1–5" in ore
    assert {r.title for r in by_level[3]} == \
        {"Nightlings' Favor",
         "Killing a demon inside a Rift heals 10% of your [MaxHealth] "
         "and increases your [MoveSpeedFactor] by +30% for 5s"}
    favor = next(r.detail for r in by_level[3]
                 if r.title == "Nightlings' Favor")
    assert "Heals 10% max Health" in favor, favor
    assert "in rifts" in favor and "vs Demon" in favor, favor
    assert "Chaos Predator (5s)" in favor, favor
    assert "Move Speed increased by 30%" in favor, favor
    assert any("15 min" in r.detail for r in by_level[5]), by_level[5]
    assert {r.title for r in by_level[7]} == \
        {"Chaos Vitality",
         "Each Soulwell offering grants +1% Vitality for its full duration"}
    for level in (1, 5, 10):
        # the title is the achievement's own name — no "Achievement: " prefix
        # (noise repeated on every row); the detail says what it is
        assert any(not r.title.startswith("Achievement: ")
                   and "achievement points" in r.detail
                   for r in by_level[level]), (level, by_level[level])


def test_rewards_come_back_lowest_rank_first():
    """The view draws them in order, so the data arrives in order."""
    levels = [rw.level for rw in rep.rewards("Riftstalkers")]
    assert levels == sorted(levels)


def test_the_faction_sheet_grants_each_rank_its_unlock_text():
    """`faction.json`'s `reputation.rewards[i]` is rank `i + 1`'s unlock —
    the mounts, gliders, quartermaster stock and flask ranks the other
    sheets never state.

    The mapping is anchored, not guessed: index 4 is the rank-5 duration
    bonus and index 6 the rank-7 vitality, the ranks the station rewards
    already state. Eight entries each, ranks 1..8; ranks 9..10 carry no
    faction line, and the reward-less Herald yields nothing."""
    rift = rep._faction_rewards("Riftstalkers")
    pilg = rep._faction_rewards("Pilgrims")
    assert [r.level for r in rift] == list(range(1, 9)), [r.level for r in rift]
    assert [r.level for r in pilg] == list(range(1, 9)), [r.level for r in pilg]
    # ... and the merged ladder carries them, which is what the view draws
    assert "quartermaster" in " ".join(
        r.title for r in rep.rewards("Riftstalkers"))
    by_level = {r.level: r.title for r in rift}
    assert "member" in by_level[1] and "Soulwell" in by_level[1]
    assert "mount" in by_level[4], by_level[4]
    assert "15 minutes" in by_level[5], by_level[5]
    assert "glider" in by_level[6], by_level[6]
    assert "Vitality" in by_level[7], by_level[7]
    assert "TPRiftStone" in by_level[8], by_level[8]
    pilg_by_level = {r.level: r.title for r in pilg}
    assert "mount" in pilg_by_level[4]
    assert "SecretOrb" in pilg_by_level[5]
    assert "SparkCube" in pilg_by_level[7]
    assert rep.rewards("Herald") == []


# --- the view ---------------------------------------------------------------
class _OthersTab:
    """Stand-in for the Codex tab combo (the view-mode code reads it)."""

    def __init__(self, text="Other"):
        self._text = text

    def currentText(self):
        return self._text


class _RepChipPage:
    """Minimal page: the Others sub-bar group plus the view-mode pipeline —
    the `_OthersChipPage` pattern from tests/test_codex.py, with Rep."""

    def __init__(self, tab="Other"):
        from farever_companion.ui.pages.codex.grid import CodexGridMixin
        from farever_companion.ui.pages.codex.map_ui import CodexMapUiMixin

        class Host(CodexMapUiMixin, CodexGridMixin):
            pass

        self._host = Host()
        host = self._host
        host._npc_list_mode = False
        host._rep_list_mode = False
        host._dungeon_list_mode = False
        host._soulstones_mode = False
        host._chest_orb_kind = None
        host._collection_sub = "pets"
        host.refreshes = 0
        host._codex_tabs = _OthersTab(tab)
        host._others_btn_group = QtWidgets.QButtonGroup()
        host._others_sub_btns = {}
        for label in ("All", "Shop", "Unreleased", "Misc", "NPC",
                        "Reputation"):
            btn = QtWidgets.QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(label == "All")
            host._others_btn_group.addButton(btn)
            host._others_sub_btns[label] = btn
        host._refresh_codex_grid = self._count_refresh

    def _count_refresh(self, reset_scroll=False):
        self._host.refreshes += 1

    def __getattr__(self, name):
        return getattr(self._host, name)


def test_the_others_sub_bar_has_a_rep_chip():
    """The Rep button sits beside NPC on the Others sub-bar."""
    from farever_companion.ui.pages.codex.page import CodexPageBase
    from farever_companion.ui.pages.codex.grid import CodexGridMixin

    class Host(CodexPageBase, CodexGridMixin, QtWidgets.QWidget):
        def _page_container(self, title=None):
            page = QtWidgets.QWidget()
            return page, QtWidgets.QVBoxLayout(page)

    host = Host()
    try:
        bar = host._build_codex_others_sub_bar()
        assert set(host._others_sub_btns) == \
            {"All", "Shop", "Unreleased", "Misc", "NPC", "Reputation"}
        assert host._others_sub_btns["Reputation"].isCheckable()
        bar.deleteLater()
    finally:
        host.deleteLater()


def test_the_rep_chip_swaps_the_other_grid_to_the_ladder_list():
    """Rep swaps the grid to the ladder list; a card chip swaps it back,
    and leaving the view re-checks All — the NPC chip's contract."""
    page = _RepChipPage()
    assert not getattr(page, "_rep_list_mode", False)

    page._others_sub_btns["Reputation"].setChecked(True)
    page._on_others_sub_toggled(True)
    assert page._rep_list_mode and not page._npc_list_mode
    assert page.refreshes == 1

    page._others_sub_btns["Shop"].setChecked(True)
    page._on_others_sub_toggled(True)
    assert not page._rep_list_mode
    assert page.refreshes == 2

    page._others_sub_btns["Reputation"].setChecked(True)
    page._on_others_sub_toggled(True)
    assert page._rep_list_mode
    page._leave_npc_view()
    assert not page._rep_list_mode
    assert page._others_btn_group.checkedButton() is page._others_sub_btns["All"]


def test_the_rep_list_shows_every_rank_with_its_rewards():
    """One shared ladder draws: both faction titles, the earning rules,
    each rank with its cumulative XP once, and every rank's rewards in
    its faction's column — ten shared rank rows, plus the faction
    sheet's own unlock text."""
    from farever_companion.ui.pages.codex.rep_list import RepListView

    page = _RepChipPage()
    view = RepListView(page)
    try:
        texts = " ".join(lb.text()
                         for lb in view.findChildren(QtWidgets.QLabel))
        assert "Riftstalkers Sisterhood" in texts
        assert "Pilgrims of Merilam" in texts
        assert "EARNING REPUTATION" in texts
        assert "3,000 XP" in texts
        assert "Nightlings' Favor" in texts
        assert "Chaos Vitality" in texts
        assert "quartermaster" in texts
        assert "15 minutes" in texts
        assert view.row_count == 10, view.row_count
        # one rank gutter, not one per faction: a single Lv + XP each
        ranks = [lb.text() for lb in view.findChildren(QtWidgets.QLabel)
                 if lb.text().startswith("Lv ")]
        assert sorted(ranks, key=lambda t: int(t[3:])) == \
            [f"Lv {n}" for n in range(1, 11)], ranks
    finally:
        view.deleteLater()
