"""Combat-page view helpers, kept out of the page mixins themselves.

Four modules, re-exported here so the page reaches them through one import:

- timeline_plotter.py  the burst graph (`_CombatTimelinePlotter`)
- player_card.py       `_PlayerCardWidget` + the metric summary cards
- past_fights.py       archived-fight deletion + the `_KIND_STYLE` badges
- compare_view.py      the Compare matrix, the performance-gap math and the
                       A-vs-B damage-by-type table (`refresh_rail_compare`,
                       `_ranked_skill_total`, `_CmpTypeTable`)

`combat_page.py` imports from this hub; nothing here imports a page, and
nothing outside `ui/` may - these are widgets, not data.
"""

from .timeline_plotter import _CombatTimelinePlotter, COMPARE_COLORS
from .player_card import (
    _ranked_skill_total,
    _cp_card_alive,
    _StatCardWidget,
    _StatStrip,
    _DamageTypeBar,
    _PdMdLabel,
    _PlayerCardWidget,
)
from .history_index import (
    history_days,
    scan_history_dir,
    load_history_sessions,
    cached_history_sessions,
    forget_cached_sessions,
    summary_line,
    party_chip,
    build_chip,
)
from .past_fights import (
    _clean_session_name,
    _KIND_STYLE,
    delete_past_fight,
    delete_past_fights_batch,
)
from .compare_view import _CmpTypeTable, refresh_rail_compare

__all__ = [
    "_CombatTimelinePlotter",
    "COMPARE_COLORS",
    "_ranked_skill_total",
    "_cp_card_alive",
    "_StatCardWidget",
    "_StatStrip",
    "_DamageTypeBar",
    "_PdMdLabel",
    "_PlayerCardWidget",
    "history_days",
    "scan_history_dir",
    "load_history_sessions",
    "cached_history_sessions",
    "forget_cached_sessions",
    "summary_line",
    "party_chip",
    "build_chip",
    "_clean_session_name",
    "_KIND_STYLE",
    "delete_past_fight",
    "delete_past_fights_batch",
    "_CmpTypeTable",
    "refresh_rail_compare",
]
