"""Update-notification pill and its background check worker.

The app only NOTIFIES: the pill opens the release page in the browser, where the
player downloads. Nothing here touches the running exe.
"""
from __future__ import annotations

from ..core import updater
from .workers import CallWorker, retire
from .. import __version__


def update_pill_text(info, suffix: str = "") -> str:
    """The sidebar pill's label for this release, or "" when it has none.

    Built from the ONE field that can be trusted - a version the updater itself
    validated (`updater.clean_version`) - because the text is drawn verbatim in
    the sidebar. "" means "do not show this at all": a pill reading "Update to v",
    or showing a raw payload string, is the misleading button this guard exists
    to prevent. Every label in the update flow is built here, the retry label
    included.
    """
    ver = updater.clean_version(getattr(info, "version", ""))
    return f"↑  Update to v{ver}{suffix}" if ver else ""


class UpdaterMixin:
    """Mixin providing the update-notification pill and its background check."""

    def _start_update_check(self):
        """Ask the release oracle once, on a worker thread; a newer release
        reaches `_on_update_found` and raises the sidebar pill.

        Idempotent, like the DPS drain: a second call while a check is in
        flight does nothing. Off the Qt thread because `updater.check` waits on
        the network; `ControlPanel` starts it for the packaged exe only.
        """
        if getattr(self, "_update_check_worker", None) is not None:
            return
        self._update_check_worker = CallWorker(lambda _w: updater.check())
        self._update_check_worker.done.connect(self._on_update_checked)
        self._update_check_worker.start()

    def _on_update_checked(self, _tag, info):
        """Worker-thread handoff for the startup check: a bound method so the
        result is delivered on the Qt thread, not the worker's (see
        `game_attach` for the same `CallWorker` idiom).

        The finished worker is retired and the slot cleared, so the guard in
        `_start_update_check` is really "while a check is in flight" and a
        later caller (Settings -> Dev picking a polling mode) starts a fresh
        check instead of a silent no-op. `retire` keeps the QThread referenced
        until its thread has actually finished: dropping the last reference
        inside the worker's own `done` handler is the still-running-QThread
        destruction `workers.retire` exists to prevent.
        """
        retire(self._update_check_worker)
        self._update_check_worker = None
        self._on_update_found(info)

    def _on_update_found(self, info):
        """Raise the sidebar pill for a release, or show NOTHING at all.

        `updater.check` normalizes what the oracle sends, but this is the
        WIDGET's own contract and the last gate before text lands on screen: a
        caller handing over a release with no displayable version (a hand-built
        UpdateInfo, a future code path) leaves the button hidden rather than
        painting "Update to v" over a live sidebar, and no state is recorded for
        it - so `_on_update_clicked` cannot act on a release nobody can name.
        """
        if info is None:
            return
        text = update_pill_text(info)
        if not text:
            return
        self._update_info = info
        self._update_btn.setText(text)
        self._update_btn.setEnabled(True)
        self._update_btn.setVisible(True)
        self.log(f"Update available: v{__version__} → "
                 f"v{updater.clean_version(info.version)}. "
                 "Click the sidebar button to open the release page.")

    def _on_update_clicked(self):
        """Open the release page in the browser: the app notifies, the player
        downloads. `page_url`, never `info.html_url` raw - the payload does not
        get to choose a `javascript:`/`file:` target for a button we drew.
        """
        info = getattr(self, "_update_info", None)
        if info is None:
            return
        import webbrowser
        webbrowser.open(updater.page_url(info.html_url))
