"""Archived-fight deletion — the write side of the Past Fights panel.

The panel itself lives on the Combat & DPS page (`combat_fights_list` owns the
list, `history_index` the scan and the on-demand read); this module is only
what the panel cannot do read-only: delete one archived fight or a batch of
them from disk and from every in-memory copy. The `_KIND_STYLE` badge table
lives here because the panel imports it from the `..combat` hub.
"""
from __future__ import annotations

import re
from pathlib import Path

from PySide6 import QtWidgets

from .. import theme
from ...core.dps_tracker import CombatSession
from ...core.dps_tracker_history import remove_log_file
from .history_index import cached_history_sessions, forget_cached_sessions
from ...core import dps_archive
from ...core.dps_archive import refresh_index


def _archive_base_for(path: Path) -> Path:
    return path.parent.parent


def _clean_session_name(name: str) -> str:
    """Strip the kind-duplicating parenthetical from archived fight names."""
    name = (name or "Fight").strip()
    return re.sub(r"\s*\([^)]*\)\s*$", "", name).strip() or "Fight"


_KIND_STYLE = {
    "boss": (theme.GOLD, "BOSS"),
    "boss_adds": (theme.ORANGE, "ADDS"),
    "trash": (theme.DIM, "TRASH"),
    "dummy": (theme.ACCENT_LIGHT, "TEST DUMMY"),
    "overall": (theme.ACCENT, "OVERALL"),
}


def delete_past_fight(parent_widget: QtWidgets.QWidget, path: str | Path, sess: CombatSession,
                      active_tracker, browse_holder: dict | None = None,
                      after_delete_cb=None) -> bool:
    """Delete one archived fight from its history file + in-memory copies."""
    path = Path(path)
    confirm = QtWidgets.QMessageBox.question(
        parent_widget, "Delete fight?",
        f"Delete '{_clean_session_name(sess.name)}'?\n"
        f"Boss: {(sess.target_name or 'None').replace('👑 ', '')}\n"
        "This cannot be undone.",
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        QtWidgets.QMessageBox.No)
    if confirm != QtWidgets.QMessageBox.Yes:
        return False

    try:
        sessions = dps_archive.read_sessions(path)
    except Exception:
        return False
    kept = [s for s in sessions
            if not (s.start_time == sess.start_time and s.name == sess.name)]
    if len(kept) == len(sessions):
        kept = [s for s in sessions if s.start_time != sess.start_time]

    if not kept:
        remove_log_file(path)
        if active_tracker and getattr(active_tracker, "_history_dir", None):
            try:
                refresh_index(Path(active_tracker._history_dir))
            except Exception:
                pass
    else:
        try:
            dps_archive.write_sessions(path, kept)
            refresh_index(_archive_base_for(path))
        except OSError:
            return False
        forget_cached_sessions(path)

    # Purge in-memory copies
    try:
        if active_tracker and getattr(active_tracker, "history", None):
            active_tracker.history = [
                s for s in active_tracker.history
                if not (s.start_time == sess.start_time and s.name == sess.name)]
            try:
                hd = getattr(active_tracker, "_history_dir", None)
                if (hd is not None and str(path).startswith(str(hd))
                        or active_tracker._resolve_history_file() == path):
                    active_tracker._persist_history()
            except Exception:
                pass
        if browse_holder and getattr(browse_holder, "_browse_sessions", None):
            browse_holder._browse_sessions = [
                s for s in browse_holder._browse_sessions
                if not (s.start_time == sess.start_time and s.name == sess.name)]
            if not browse_holder._browse_sessions:
                browse_holder._browse_sessions = None
                browse_holder._browse_char = ""
                browse_holder._selected_history_idx = 0
    except Exception:
        pass

    if after_delete_cb:
        after_delete_cb()
    return True


def delete_past_fights_batch(parent_widget: QtWidgets.QWidget, items: list[tuple[Path, CombatSession]],
                            active_tracker, browse_holder: dict | None = None,
                            after_delete_cb=None) -> bool:
    """Delete multiple archived fights in a single batch with 1 confirmation dialog."""
    if not items:
        return False

    confirm = QtWidgets.QMessageBox.question(
        parent_widget, "Delete selected fights?",
        f"Delete {len(items)} selected fight(s)?\n"
        "This cannot be undone.",
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        QtWidgets.QMessageBox.No)
    if confirm != QtWidgets.QMessageBox.Yes:
        return False

    # Group items by file path
    by_path: dict[Path, list[CombatSession]] = {}
    for p, sess in items:
        p = Path(p)
        by_path.setdefault(p, []).append(sess)

    for path, sess_list in by_path.items():
        try:
            sessions = dps_archive.read_sessions(path)
        except Exception:
            continue
        delete_sigs = {(s.start_time, s.name) for s in sess_list}
        kept = [s for s in sessions
                if (s.start_time, s.name) not in delete_sigs]
        if not kept:
            remove_log_file(path)
        else:
            try:
                dps_archive.write_sessions(path, kept)
                refresh_index(_archive_base_for(path))
            except OSError:
                continue
            forget_cached_sessions(path)

        # Purge in-memory copies
        try:
            if active_tracker and getattr(active_tracker, "history", None):
                active_tracker.history = [
                    s for s in active_tracker.history
                    if not any(s.start_time == cs.start_time and s.name == cs.name for cs in sess_list)
                ]
                try:
                    hd = getattr(active_tracker, "_history_dir", None)
                    if (hd is not None
                            and any(str(Path(p)).startswith(str(hd))
                                    for p, _ in sess_list)
                            or active_tracker._resolve_history_file() in
                            [Path(p) for p, _ in sess_list]):
                        active_tracker._persist_history()
                except Exception:
                    pass
            if browse_holder and getattr(browse_holder, "_browse_sessions", None):
                browse_holder._browse_sessions = [
                    s for s in browse_holder._browse_sessions
                    if not any(s.start_time == cs.start_time and s.name == cs.name for cs in sess_list)
                ]
                if not browse_holder._browse_sessions:
                    browse_holder._browse_sessions = None
                    browse_holder._browse_char = ""
                    browse_holder._selected_history_idx = 0
        except Exception:
            pass

    if after_delete_cb:
        after_delete_cb()
    return True

