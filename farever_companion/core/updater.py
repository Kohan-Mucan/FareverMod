"""In-app update notifier: reads this repo's latest GitHub Release and links out.

Flow: the desktop app asks GitHub's releases API for the newest release of
`GITHUB_REPO`, compares the tag against our version, and - if newer - raises a
sidebar pill. Clicking the pill opens the release page in the browser, where the
player downloads the new build. No separate release oracle is needed.

The check READS the `/releases` list, not `/releases/latest`, so a pre-release
(a `v0.3.7-beta2` build) still raises the pill: `/latest` skips pre-releases.

Notify-only, by design: the app never downloads or replaces its own exe. The
release payload needs nothing but a version the pill can print and a page to
open, so a missing hash or size cannot suppress the pill.

Everything here degrades cleanly: a missing network, or a payload that is not a
version/page, aborts without touching anything. The pure helpers (version
parsing/compare, URL checks) are unit-tested.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .. import __version__


@dataclass(frozen=True)
class UpdateInfo:
    # Field ORDER and defaults are load-bearing: every caller builds this by
    # keyword, and a hand-built one (a test, a future caller) passes only
    # `version` - so a field added without a default here breaks the
    # construction rather than the display.
    version: str            # "0.1.2"
    notes: str = ""         # release body (markdown)
    html_url: str = ""      # release page the pill opens; left empty when the
                            # payload named no real page, so `page_url` stays the
                            # one place that picks a click target

#: Where to send the browser when no release URL is known (dev runs, or a
#: release payload without html_url).
DOWNLOAD_PAGE = "https://kohan-mucan.github.io/FareverMod/"


#: The repo the updater reads releases from. Public, so the releases API needs no
#: token; a check is one unauthenticated request per launch.
GITHUB_REPO = "Kohan-Mucan/FareverMod"

#: The releases LIST endpoint (newest first, drafts excluded, pre-releases
#: INCLUDED). `/releases/latest` would skip a pre-release, so a `-betaN` tag
#: would never raise the pill. Public and unauthenticated.
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases"


#: The startup update-check modes. The DISPLAY TEXT is the stored token, the
#: same convention `ui/pages/settings/rift.py` uses for `show_rift_timer`: a
#: settings.json stays readable and the reader only has to coerce what it cannot
#: recognise. Order is the order the picker draws.
UPDATE_CHECK_MODES = ("Always", "Packaged only", "Never")

#: What an unset, unreadable or future value means. Conservative on purpose: a
#: SOURCE run does not poll, so no settings file - and no test run - can reach
#: the network by accident.
DEFAULT_UPDATE_CHECK = "Packaged only"


def normalize_update_check(value) -> str:
    """Coerce a stored `check_updates` value to one of `UPDATE_CHECK_MODES`.

    Tolerant because the field USED to be a boolean: `True` meant "poll this
    source run too" (now `Always`) and `False` meant "only where a release can
    be installed" (now `Packaged only`), so a settings.json written before this
    change still loads into the mode it MEANT. Anything unrecognised - a
    hand-edited file, a typo, a mode a later version adds - falls back to
    `DEFAULT_UPDATE_CHECK` rather than guessing.
    """
    if value is True:
        return "Always"
    if value is False:
        return "Packaged only"
    text = str(value or "").strip().lower()
    if text == "always":
        return "Always"
    if text in ("packaged only", "packaged-only", "packaged", "frozen"):
        return "Packaged only"
    if text in ("never", "off"):
        return "Never"
    return DEFAULT_UPDATE_CHECK


def should_check(value, frozen: bool) -> bool:
    """Whether THIS run polls the release oracle at startup.

    `Always` polls even in a source run (how a dev sees the update pill without
    a build); `Packaged only` polls only in a packaged build; `Never` is a real
    opt-out - including in a packaged build, which is the half that had NO switch
    at all before this became a mode. Junk reads as the default, which is what
    keeps an unset setting offline.
    """
    mode = normalize_update_check(value)
    if mode == "Always":
        return True
    if mode == "Never":
        return False
    return bool(frozen)


# --- pure version helpers (unit-tested) ------------------------------------
def parse_version(s: str) -> tuple[int, ...]:
    """"v0.1.2" / "0.1.2-beta" -> (0, 1, 2). Non-numeric junk is dropped; an
    empty/garbage string parses to (0,)."""
    nums = re.findall(r"\d+", s or "")
    return tuple(int(n) for n in nums) or (0,)


def is_newer(latest: str, current: str = __version__) -> bool:
    """True if `latest` is a strictly higher version than `current`."""
    return parse_version(latest) > parse_version(current)


def current_version() -> str:
    return __version__


#: A version the app is willing to PRINT. The sidebar pill draws this string
#: verbatim, so it has to look like a version and nothing else: digits with dots,
#: plus the `-rc1` / `+build` suffix a release tag may carry. Deliberately strict
#: - refusing a weird-but-real tag costs a missing pill, while accepting one
#: costs a button that reads "Update to vlatest" and asks the player to install
#: it.
_VERSION_RE = re.compile(r"^[vV]?\d+(?:\.\d+)*(?:[-+][0-9A-Za-z.\-]+)?$")


def clean_version(raw) -> str:
    """The version to SHOW for a release payload, or "" when it is not one.

    The oracle is a web endpoint, so this is untrusted input, and "" is the
    caller's signal to show nothing at all - the only label that cannot mislead.
    A leading `v` is dropped because every surface that draws a version adds its
    own ("Update to v..."), so keeping the payload's would double it.
    """
    text = str(raw or "").strip()
    if not _VERSION_RE.match(text):
        return ""
    return text[1:] if text[:1] in ("v", "V") else text


def http_url(raw) -> str:
    """The URL to OPEN/FETCH for a payload field, or "" when it is not one.

    http/https, with a host, and nothing else: `webbrowser.open` on a
    `javascript:` or `file:` string is a local-file launch dressed as an update
    button, and a scheme-less "not a url" is a browser error page. Both are
    refused here, once, for every field that can reach a browser or urllib.
    """
    text = str(raw or "").strip()
    if not text:
        return ""
    parts = urllib.parse.urlsplit(text)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return ""
    return text


def page_url(html_url) -> str:
    """Where a click goes: the release page when the payload names a real one,
    else the project's download page. Never "" - the button always has somewhere
    to go.
    """
    return http_url(html_url) or DOWNLOAD_PAGE


# --- frozen-exe helper -----------------------------------------------------
def is_frozen() -> bool:
    """True when running as the packaged one-file exe (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


# --- check -----------------------------------------------------------------
def fetch_latest_release(url: str = RELEASES_API) -> dict:
    """GET `GITHUB_REPO`'s releases (newest first) and map the newest into the
    shape `check` reads ({ok, version, notes, html_url}).

    The LIST endpoint, not `/releases/latest`, on purpose: `/latest` skips
    pre-releases, so a `v0.3.7-beta2` build would never raise the pill. The list
    includes them (drafts are still excluded, and GitHub sorts newest first).

    Blocking (stdlib urllib), so callers run it off the Qt thread. Never raises:
    no network, a non-JSON body or an HTTP error all come back as
    ``{"ok": False, "error": ...}`` - the shape `check` already handles. The
    release JSON is MAPPED here, not validated: `check` stays the gate on the
    version and page, so a malformed field is refused there exactly as it would
    be for any other source. Assets are not inspected: the notifier links to the
    release page, it does not download.
    """
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "FareverMod-Companion"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            rels = json.loads(resp.read().decode("utf-8") or "[]")
    except Exception:
        return {"ok": False, "error": "network"}
    if not isinstance(rels, list):
        return {"ok": False, "error": "payload"}
    rel = next((r for r in rels
                if isinstance(r, dict) and r.get("tag_name")
                and not r.get("draft")), None)
    if rel is None:
        return {"ok": False, "error": "payload"}
    return {
        "ok": True,
        "version": rel.get("tag_name"),
        "notes": rel.get("body") or "",
        "html_url": rel.get("html_url"),
    }


def check(api=None) -> UpdateInfo | None:
    """Ask the release source for the latest version; return UpdateInfo when it
    is NEWER and its version is displayable, else None. `api` is any object with
    a `latest_release()` returning the release dict; omit it to ask GitHub
    (`fetch_latest_release`). Never raises.

    The app only NOTIFIES and links out, so a payload needs nothing but a version
    the pill can print and a page to open. What is dropped at the wire is
    anything PRINTED or OPENED verbatim - `clean_version` refuses a version the UI
    cannot show and `http_url` refuses a `javascript:`/`file:` page.
    """
    try:
        res = api.latest_release() if api is not None else fetch_latest_release()
    except Exception:
        return None
    if not isinstance(res, dict) or not res.get("ok"):
        return None
    # `parse_version` drops non-digits by design, so "latest" and
    # "9.9.9; DROP TABLE" both used to compare as newer and reach the pill;
    # `clean_version` is what keeps a non-version off the sidebar.
    ver = clean_version(res.get("version"))
    if not ver or not is_newer(ver):
        return None
    return UpdateInfo(
        version=ver,
        notes=str(res.get("notes") or ""),
        # Left EMPTY when the payload named no real page, so `page_url` stays
        # the one place that decides where a click goes.
        html_url=http_url(res.get("html_url")),
    )
