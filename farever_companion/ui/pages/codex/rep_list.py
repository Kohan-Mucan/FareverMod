"""The reputation ladder list: every faction's ranks with what each one pays.

This list has one job the card grid cannot do: ranks are not items, so they
have no codex cards at all — like the placed NPCs (`npc_list.NpcListView`),
they list from the sheets instead of filtering the grid. One SHARED ladder:
the rank/XP rungs are identical for every faction (one threshold prices
them all), so ranks 1..10 with the cumulative XP draw ONCE down the left
and each faction pays out in its own column beside them: achievements,
standing skills, gated drops, station rewards and the faction sheet's own
per-rank unlock text, as `data/reputation.py` states them.

An "Earning it" box up top carries the XP rules (per-rank cost, rift and
soulwell gains), so the whole ladder — cost, income and payout — is one
surface. Read-only like every codex list: no buttons, no tracking, nothing
to press.
"""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ... import theme
from ....data import reputation as rep


def _rank_rows(faction_id: str) -> dict[int, list[tuple[str, str]]]:
    """{rank: [(reward title, reward detail)]} for one faction, over its
    full ladder (1..10).

    No XP text here: the gutter is shared across factions and priced by
    the one global threshold, so the ladder formats it once rather than
    each faction formatting the same string to be thrown away. Ranks with
    no sheet-recorded reward still list — with an empty reward list,
    which the table renders as an em dash, so "no reward" reads as a
    stated fact instead of a missing row.
    """
    by_level: dict[int, list[tuple[str, str]]] = {}
    for rw in rep.rewards(faction_id):
        by_level.setdefault(rw.level, []).append((rw.title, rw.detail or ""))
    faction = next((f for f in rep.factions()
                    if f.faction_id == faction_id), None)
    top = max(faction.levels) if faction and faction.levels else 10
    return {level: by_level.get(level, [])
            for level in range(1, top + 1)}


# fixed columns, like the NPC list: rank + XP never move, rewards stretch
_COL_RANK = 52
_COL_XP = 110


class RepListView(QtWidgets.QFrame):
    """Every reputation faction's full rank ladder, with rewards per rank.

    One table for all factions: a single RANK + TOTAL XP gutter on the
    left (the ladder is the same for every faction, so repeating it per
    faction was two identical columns saying nothing twice) and one
    reward column per faction beside it.
    """

    def __init__(self, ui, parent=None):
        super().__init__(parent)
        self.ui = ui
        self.row_count = 0
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        root.addWidget(self._build_earning_box())
        root.addWidget(self._build_ladder(rep.factions()))
        root.addStretch(1)

    # ---- earning box -----------------------------------------------------
    def _build_earning_box(self) -> QtWidgets.QFrame:
        box = QtWidgets.QFrame()
        box.setObjectName("RepEarning")
        box.setStyleSheet(
            f"QFrame#RepEarning {{ background:{theme.PANEL_LOW}; "
            f"border:1px solid {theme.BORDER}; border-radius:6px; }}")
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(3)
        head = QtWidgets.QLabel("EARNING REPUTATION")
        head.setStyleSheet(
            f"font-size:10.5px; font-weight:800; color:{theme.DIM}; "
            f"letter-spacing:1px; background:transparent; border:none;")
        lay.addWidget(head)
        lines = [f"Each rank costs {rep.xp_per_rank():,} XP"]
        lines += [f"{label}: +{xp} XP" for label, xp in rep.xp_gains()]
        body = QtWidgets.QLabel(" · ".join(lines))
        body.setWordWrap(True)
        body.setStyleSheet(
            f"font-size:12px; color:{theme.TEXT}; "
            f"background:transparent; border:none;")
        lay.addWidget(body)
        return box

    # ---- the shared ladder --------------------------------------------------
    def _build_ladder(self, factions) -> QtWidgets.QFrame:
        """One card for every faction: the rank/XP gutter once, then one
        reward column per faction.

        Levels are the UNION across factions (1..10 for both today), so a
        faction with a shorter ladder simply shows dashes past its top.
        """
        factions = list(factions)
        card = QtWidgets.QFrame()
        card.setObjectName("RepLadder")
        card.setStyleSheet(
            f"QFrame#RepLadder {{ background:{theme.PANEL}; "
            f"border:1px solid {theme.BORDER}; border-radius:6px; }}")
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)
        # header row: small caps, aligned to the columns below — the rank
        # gutter first, then each faction's name over its own column
        hdr = QtWidgets.QHBoxLayout()
        hdr.setContentsMargins(8, 2, 8, 2)
        hdr.setSpacing(12)
        for text, width in (("RANK", _COL_RANK), ("TOTAL XP", _COL_XP)):
            lab = QtWidgets.QLabel(text)
            lab.setFixedWidth(width)
            lab.setStyleSheet(
                f"font-size:10px; font-weight:800; color:{theme.DIM}; "
                f"letter-spacing:1px; background:transparent; border:none;")
            hdr.addWidget(lab)
        for faction in factions:
            name = QtWidgets.QLabel(faction.title.upper())
            name.setObjectName(f"RepFactionTitle_{faction.faction_id}")
            name.setStyleSheet(
                f"font-size:10px; font-weight:800; color:{theme.GOLD}; "
                f"letter-spacing:1px; background:transparent; border:none;")
            hdr.addWidget(name, 1)
        lay.addLayout(hdr)
        cells = {f.faction_id: _rank_rows(f.faction_id) for f in factions}
        levels = sorted({lv for per in cells.values() for lv in per})
        for level in levels:
            lay.addWidget(self._build_rank_row(
                level, f"{rep.cumulative_xp(level):,} XP",
                [cells[f.faction_id].get(level, []) for f in factions]))
            self.row_count += 1
        return card

    def _build_rank_row(self, level: int, xp: str,
                        per_faction: list[list[tuple[str, str]]]
                        ) -> QtWidgets.QFrame:
        """One table row: rank + total XP in the fixed gutter, then each
        faction's rewards stacked in its own stretch column — each reward
        its title with its detail under it, instead of one long joined
        sentence. Alternate rows carry the low-panel tint so the eye can
        follow a row across."""
        row = QtWidgets.QFrame()
        row.setObjectName("RepRankRow")
        if level % 2 == 0:
            row.setStyleSheet(
                f"QFrame#RepRankRow {{ background:{theme.PANEL_LOW}; "
                f"border-radius:4px; }}")
        h = QtWidgets.QHBoxLayout(row)
        h.setContentsMargins(8, 5, 8, 5)
        h.setSpacing(12)
        lv = QtWidgets.QLabel(f"Lv {level}")
        lv.setFixedWidth(_COL_RANK)
        lv.setAlignment(QtCore.Qt.AlignTop)
        lv.setStyleSheet(
            f"font-size:12px; font-weight:800; color:{theme.ACCENT_LIGHT}; "
            f"background:transparent; border:none;")
        h.addWidget(lv)
        xp_lbl = QtWidgets.QLabel(xp)
        xp_lbl.setFixedWidth(_COL_XP)
        xp_lbl.setAlignment(QtCore.Qt.AlignTop)
        xp_lbl.setStyleSheet(
            f"font-size:11px; color:{theme.MUTED}; font-family:monospace; "
            f"background:transparent; border:none;")
        h.addWidget(xp_lbl)
        for rewards in per_faction:
            h.addLayout(self._rewards_cell(rewards), 1)
        return row

    @staticmethod
    def _rewards_cell(rewards: list[tuple[str, str]]) -> QtWidgets.QVBoxLayout:
        """One faction's cell in a rank row: its rewards stacked, or an em
        dash when the sheets record none — "no reward" as a stated fact
        instead of a missing cell."""
        body = QtWidgets.QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(4)
        if not rewards:
            dash = QtWidgets.QLabel("—")
            dash.setStyleSheet(
                f"font-size:11.5px; color:{theme.DIM}; "
                f"background:transparent; border:none;")
            body.addWidget(dash)
        for title, detail in rewards:
            title_lbl = QtWidgets.QLabel(title)
            title_lbl.setWordWrap(True)
            title_lbl.setStyleSheet(
                f"font-size:11.5px; font-weight:600; color:{theme.TEXT}; "
                f"background:transparent; border:none;")
            body.addWidget(title_lbl)
            if detail:
                detail_lbl = QtWidgets.QLabel(detail)
                detail_lbl.setWordWrap(True)
                detail_lbl.setStyleSheet(
                    f"font-size:11px; color:{theme.DIM}; "
                    f"background:transparent; border:none;")
                body.addWidget(detail_lbl)
        return body
