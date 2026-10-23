// Pane router: one visible section, hash-synced, no page scroll.
const links = [...document.querySelectorAll('nav.side a[data-pane]')];
document.querySelectorAll('a[data-pane]:not(nav.side a)').forEach(a =>
  a.addEventListener('click', () => show(a.dataset.pane)));
const panes = [...document.querySelectorAll('.pane')];
const main = document.getElementById('main');
function show(name, push) {
  if (!document.getElementById('pane-' + name)) name = 'overview';
  panes.forEach(p => p.classList.toggle('on', p.id === 'pane-' + name));
  links.forEach(a => {
    const on = a.dataset.pane === name;
    a.classList.toggle('on', on);
    if (on) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
  if (push !== false && location.hash !== '#' + name) history.replaceState(null, '', '#' + name);
  main.scrollTop = 0;
  document.getElementById('sidebar').classList.remove('open');
}
// Nav clicks route instantly; the hash change would do it a tick later anyway.
links.forEach(a => a.addEventListener('click', () => show(a.dataset.pane)));
window.addEventListener('hashchange', () => show(location.hash.slice(1) || 'overview', false));
show(location.hash.slice(1) || 'overview', false);
// Theme toggle, persisted.
const t = document.getElementById('themeBtn');
function paintThemeBtn() {
  const dark = document.documentElement.dataset.theme === 'dark';
  t.textContent = dark ? '☾' : '☀';
  t.setAttribute('aria-label', dark ? 'Switch to light theme' : 'Switch to dark theme');
}
const saved = localStorage.getItem('fm-theme');
if (saved) document.documentElement.dataset.theme = saved;
paintThemeBtn();
t.onclick = () => {
  const el = document.documentElement;
  el.dataset.theme = el.dataset.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('fm-theme', el.dataset.theme);
  paintThemeBtn();
};
document.getElementById('menuBtn').onclick = e => {
  const open = document.getElementById('sidebar').classList.toggle('open');
  e.currentTarget.setAttribute('aria-expanded', open ? 'true' : 'false');
};
// Skip link: focus main without touching the hash (unknown hashes fall back to Overview).
document.querySelector('.skip').addEventListener('click', e => {
  e.preventDefault();
  main.focus();
});
// Screenshot pickers: each pane's list drives that pane's own viewer.
const allPicks = [];
document.querySelectorAll('.picker').forEach(picker => {
  const picks = [...picker.querySelectorAll('.picklist .pick')];
  const shotFig = picker.querySelector('.shot.viewer');
  const shotView = picker.querySelector('.shotview');
  const shotDesc = picker.querySelector('.shotdesc');
  picks.forEach(p => p.setAttribute('aria-controls', shotFig.id));
  function selectShot(el, focus) {
    picks.forEach(p => {
      const on = p === el;
      p.setAttribute('aria-selected', on ? 'true' : 'false');
      p.tabIndex = on ? 0 : -1;
    });
    shotView.src = el.getAttribute('href');
    shotView.alt = el.dataset.alt;
    shotView.width = el.dataset.w;
    shotView.height = el.dataset.h;
    shotView.setAttribute('aria-labelledby', el.id);
    if (el.dataset.desc) {
      shotDesc.innerHTML = el.dataset.desc;
      shotDesc.style.display = 'block';
    } else {
      shotDesc.style.display = 'none';
    }
    shotFig.hidden = false;
    if (focus) el.focus();
  }
  picks.forEach((el, i) => {
    el.addEventListener('click', e => { e.preventDefault(); selectShot(el); });
    el.addEventListener('keydown', e => {
      const step = (e.key === 'ArrowDown' || e.key === 'ArrowRight') ? 1
                 : (e.key === 'ArrowUp' || e.key === 'ArrowLeft') ? -1 : 0;
      if (!step) return;
      e.preventDefault();
      selectShot(picks[(i + step + picks.length) % picks.length], true);
    });
  });
  selectShot(picks[0], false);
  allPicks.push(...picks);
});
// Overview carousel: prev/next cycles the app-page shots (data reused from the
// picker entries, so the two never drift apart).
(function () {
  const fig = document.getElementById('ov-shot');
  if (!fig) return;
  const img = fig.querySelector('img');
  const cap = document.getElementById('ov-cap');
  // Carousel order follows the app's own sidebar (nav_registry.NAV), not the
  // Screenshots picker's listing: Overlays → Settings → Codex → Codex · Collection →
  // DPS Analysis → Player Inspect → Gear → Craft → Server Ping.
  const OV_ORDER = ['pick-page-overlays','pick-page-settings-rift','pick-page-codex',
                    'pick-page-codex-collection','pick-page-combat','pick-page-party',
                    'pick-page-gear','pick-page-craft','pick-page-server'];
  const byId = Object.fromEntries(allPicks.filter(p => p.id && p.id.startsWith('pick-page-'))
                                .map(p => [p.id, p]));
  const pagePicks = OV_ORDER.map(id => byId[id]).filter(Boolean);
  let i = 0;
  function render() {
    const p = pagePicks[i];
    img.src = p.getAttribute('href');
    img.alt = p.dataset.alt;
    img.width = p.dataset.w;
    img.height = p.dataset.h;
    img.setAttribute('aria-labelledby', p.id);
    // caption derives from the pick's own visible text — no data-* duplication
    const label = p.querySelector('span').textContent.trim();
    const sp = label.indexOf(' ');
    const icon = sp < 0 ? '' : label.slice(0, sp);
    const title = sp < 0 ? label : label.slice(sp + 1);
    cap.innerHTML = (icon ? icon + ' ' : '') + '<b>' + title + '</b> ' + p.querySelector('small').textContent;
  }
  function step(d) { i = (i + d + pagePicks.length) % pagePicks.length; render(); }
  document.getElementById('ov-prev').onclick = () => step(-1);
  document.getElementById('ov-next').onclick = () => step(1);
})();
// Release tiles and the combined Releases pane share one fetch per window.
(function () {
  const KEY = 'fm-rel7';
  const isVer = t => /^v?\d+\.\d+/i.test(t || '');
  const put = (id, value, url) => {
    const el = document.getElementById(id);
    if (value) el.textContent = value;
    if (url) el.closest('a').href = url;
  };
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const inline = s => s.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https:\/\/[^)\s]+\))/g).map(part => {
    let m;
    if ((m = /^\*\*(.+)\*\*$/.exec(part))) return '<b>' + esc(m[1]) + '</b>';
    if ((m = /^`(.+)`$/.exec(part))) return '<code>' + esc(m[1]) + '</code>';
    if ((m = /^\[([^\]]+)\]\((https:\/\/[^)\s]+)\)$/.exec(part))) {
      try { const u = new URL(m[2]); if (u.protocol === 'https:') return '<a href="' + esc(u.href) + '" rel="noopener">' + esc(m[1]) + '</a>'; } catch (e) {}
    }
    return esc(part);
  }).join('');
  const md = src => {
    let html = '', inList = false;
    for (const raw of String(src || '').split(/\r?\n/)) {
      const line = raw.trim();
      if (/^[-*] /.test(line)) { if (!inList) { html += '<ul>'; inList = true; } html += '<li>' + inline(line.slice(2)) + '</li>'; continue; }
      if (inList) { html += '</ul>'; inList = false; }
      if (!line) continue;
      if (/^#{1,4} /.test(line)) { html += '<h3>' + inline(line.replace(/^#+ /, '')) + '</h3>'; continue; }
      html += '<p>' + inline(line) + '</p>';
    }
    return html + (inList ? '</ul>' : '');
  };
  const date = s => s ? new Date(s).toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' }) : '';
  function render(list) {
    const box = document.getElementById('releaseList');
    if (!box || !list || !list.length) return;
    const latest = list.find(r => !r.prerelease) || list[0];
    box.replaceChildren();
    const current = document.createElement('details');
    current.className = 'rel release-current';
    current.name = 'releases';
    current.open = true;
    const head = document.createElement('summary'); head.className = 'release-head';
    const title = document.createElement('h2'); title.textContent = latest.tag_name;
    const time = document.createElement('time'); time.textContent = date(latest.published_at);
    head.append(title, time); current.append(head);
    const body = document.createElement('div'); body.className = 'release-body'; body.innerHTML = md(latest.body);
    current.append(body);
    box.append(current);
    const older = list.filter(r => r !== latest);
    if (!older.length) return;
    const section = document.createElement('section'); section.className = 'release-older';
    const heading = document.createElement('h2'); heading.textContent = 'Earlier releases'; section.append(heading);
    older.forEach(r => {
      const d = document.createElement('details'); d.className = 'rel'; d.name = 'releases';
      const summary = document.createElement('summary');
      const tag = document.createElement('span'); tag.className = 'tag'; tag.textContent = r.tag_name;
      const when = document.createElement('time'); when.textContent = date(r.published_at);
      summary.append(tag);
      if (r.prerelease) { const chip = document.createElement('span'); chip.className = 'chip'; chip.textContent = 'pre-release'; summary.append(chip); }
      summary.append(when); d.append(summary);
      const notes = document.createElement('div'); notes.className = 'release-body'; notes.innerHTML = md(r.body);
      d.append(notes);
      section.append(d);
    });
    box.append(section);
  }
  const apply = data => {
    put('verLatest', data.latest, data.latestUrl); put('verPre', data.pre, data.preUrl);
    render(data.releases);
  };
  try { const cached = JSON.parse(sessionStorage.getItem(KEY)); if (cached) { apply(cached); return; } } catch (e) {}
  fetch('https://api.github.com/repos/Kohan-Mucan/FareverMod/releases?per_page=10')
    .then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(list => {
      const stable = list.find(r => !r.prerelease && isVer(r.tag_name));
      const pre = list.find(r => /pre-release/i.test(r.tag_name) || r.prerelease);
      const data = {
        latest: (list.find(r => !r.prerelease && isVer(r.tag_name)) || {}).tag_name,
        latestUrl: stable && stable.html_url,
        pre: pre && (isVer(pre.name) ? pre.name.match(/v?\d+(?:\.\d+)+/i)[0].replace(/^(v?0\.3)\.72$/i, '$1.7.2') : (list.find(r => r.prerelease && isVer(r.tag_name)) || {}).tag_name),
        preUrl: pre && pre.html_url,
        releases: list.slice(0, 10)
      };
      apply(data);
      try { sessionStorage.setItem(KEY, JSON.stringify(data)); } catch (e) {}
    })
    .catch(() => {}); // release links and notes remain available on GitHub
})();
