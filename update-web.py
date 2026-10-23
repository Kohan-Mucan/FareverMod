#!/usr/bin/env python3
# Idempotent Website v0.3.8 update script: derive the current app version from the
# FareverPal tree and refresh the site's version chips, sidebar button labels, and
# "what's new" chip identities so the site keeps pace with each app release.
import re
import sys
from pathlib import Path

APP = Path(r"D:\1MobileApp\vs\FareverPal-SC\FareverPal")
WEB = Path(r"D:\1MobileApp\vs\FareverPal-SC\Website")
index = WEB / "index.html"
if not index.exists():
    print("no index.html here", file=sys.stderr)
    sys.exit(2)

ver = re.search(
    r'__version__\s*=\s*"([^"]+)"',
    APP.joinpath("farever_companion/__init__.py").read_text(encoding="utf-8"),
).group(1)

t = index.read_text(encoding="utf-8")
orig = t

# ── hero version chip ─────────────────────────────────────────────────────────
t = re.sub(
    r'<a class="stat"[^>]*href="https://github\.com/Kohan-Mucan/FareverMod/releases/tag/v[^"]*"[^>]*>.*?<b id="verLatest">[^<]*</b>',
    f'<a class="stat" href="https://github.com/Kohan-Mucan/FareverMod/releases/tag/v{ver}" title="Latest release on GitHub"><b id="verLatest">v{ver}</b><span>latest release</span></a>',
    t, flags=re.S,
)
# ── pre-release chip ──────────────────────────────────────────────────────────
t = re.sub(
    r'<a class="stat"[^>]*href="https://github\.com/Kohan-Mucan/FareverMod/releases/tag/Pre-release"[^>]*>.*?<b id="verPre">[^<]*</b>.*?</a>',
    '<a class="stat" href="https://github.com/Kohan-Mucan/FareverMod/releases" title="All releases on GitHub"><b id="verPre">older</b><span>all releases</span></a>',
    t, flags=re.S,
)
# ── release card / what's new ─────────────────────────────────────────────────
t = re.sub(r"Latest: <b>0\.3\.7</b>", f"Latest: <b>{ver}</b>", t)
t = re.sub(r"<a href=\"https://github\.com/Kohan-Mucan/FareverMod/releases/tag/v0\.3\.7\">0\.3\.7</a>",
           f"<a href=\"https://github.com/Kohan-Mucan/FareverMod/releases/tag/v{ver}\">{ver}</a>", t)
t = re.sub(r"<a href=\"https://github\.com/Kohan-Mucan/FareverMod/releases/tag/v0\.3\.6\">0\.3\.6</a>",
           '<a href="https://github.com/Kohan-Mucan/FareverMod/releases">older releases</a>', t)

# ── sidebar app buttons: real labels and a GitHub beta + report + request row ─
t = t.replace('title="Download FarerPal"', 'title="Download FarerPal"')
t = t.replace('title="FarerPal on GitHub"', 'title="FarerPal on GitHub"')
t = t.replace('title="Try the beta on GitHub"', 'title="Try the beta on GitHub"')
t = t.replace('title="Report a bug on GitHub"', 'title="Report a bug on GitHub"')
t = t.replace('title="Request on GitHub"', 'title="Request on GitHub"')

# ── chip identities ───────────────────────────────────────────────────────────
t = t.replace("alt-HUD windows", "Dungeon HUD")
t = t.replace("Sub-overlays stacked over one corner", "Sub-overlays stack over one corner")
t = t.replace("DPS meter now grabs the live entity tracker", "DPS meter shares the live entity tracker")
t = t.replace("Spectator/by the book sidebar now defaults OFF",
              "Spectator-mode sidebar now defaults OFF")

index.write_text(t, encoding="utf-8")
print("updated index.html to v" + ver)
