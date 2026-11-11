(function () {
  'use strict';
  var D = JSON.parse(document.getElementById('gb-data').textContent);
  var TZ = 'America/Toronto', ESPN = 'https://site.api.espn.com/apis/site/v2/sports/';
  var LG = { nfl: ['NFL', 'football/nfl', 'nfl'], cfb: ['College football (FBS)', 'football/college-football', 'college-football'], nba: ['NBA', 'basketball/nba', 'nba'], nhl: ['NHL', 'hockey/nhl', 'nhl'] };
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function fmt(d, o) { return new Intl.DateTimeFormat('en-US', Object.assign({ timeZone: TZ }, o)).format(d); }
  function ymd(d) { return new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(d); }
  function timeET(iso) { return fmt(new Date(iso), { hour: 'numeric', minute: '2-digit' }); }
  function chip(t, k) { return '<span class="chip ' + k + '">' + esc(t) + '</span>'; }
  function mins(iso) { return (Date.now() - new Date(iso).getTime()) / 60000; }
  function ageText(m) { return m < 1 ? 'just now' : m < 90 ? Math.round(m) + ' min old' : m < 2880 ? (m / 60).toFixed(1) + ' h old' : Math.round(m / 1440) + ' days old'; }

  // ---------- freshness: recomputed on every view ----------
  function ages() {
    document.querySelectorAll('[data-age]').forEach(function (el) {
      var m = mins(el.dataset.age), max = +el.dataset.max;
      el.innerHTML = esc(el.dataset.prefix || '') + ageText(m) + ' ' + chip(m <= max ? 'fresh' : 'stale', m <= max ? 'good' : 'bad');
    });
  }
  ages(); setInterval(ages, 60000);

  // ---------- schedules (live from ESPN, snapshot fallback) ----------
  function days() {
    var out = [], t = new Date();
    for (var i = 0; i < 8; i++) {
      var d = new Date(t.getTime() + i * 86400000), k = ymd(d);
      out.push({ key: k, dow: fmt(d, { weekday: 'short' }), label: fmt(d, { weekday: 'short', month: 'short', day: 'numeric' }) });
      if (out[i].dow === 'Sun') break;
    }
    return out;
  }
  var DAYS = days(), TODAY = DAYS[0].key, SUNDAY = DAYS[DAYS.length - 1].dow === 'Sun' ? DAYS[DAYS.length - 1].key : null;
  function norm(lg, e) {
    var c = e.competitions[0], h = c.competitors.find(function (x) { return x.homeAway === 'home'; }), a = c.competitors.find(function (x) { return x.homeAway === 'away'; });
    var o = (c.odds || [])[0] || {}, ml = o.moneyline || {};
    var nm = function (t) { return [t.location, t.displayName, t.shortDisplayName, t.abbreviation].join(' '); };
    return { lg: lg, id: e.id, t: e.date, a: a.team.shortDisplayName || a.team.displayName, h: h.team.shortDisplayName || h.team.displayName, an: nm(a.team), hn: nm(h.team),
      line: o.details || '', ou: o.overUnder == null ? '' : o.overUnder, mla: (ml.away && ml.away.close && ml.away.close.odds) || '', mlh: (ml.home && ml.home.close && ml.home.close.odds) || '',
      state: e.status.type.state, det: e.status.type.shortDetail, sa: a.score, sh: h.score, live: true };
  }
  function snapRows(lg) {
    return D.sched.filter(function (r) { return r.lg === lg; }).map(function (r) {
      return Object.assign({ an: r.a + ' ' + r.aa, hn: r.h + ' ' + r.ha, state: new Date(r.t) > new Date() ? 'pre' : 'unknown', det: '', live: false }, r);
    });
  }
  var EV = [], liveLeagues = [], failed = [], view = 'today';
  function load() {
    var jobs = Object.keys(LG).map(function (lg) {
      var q = lg === 'cfb' ? '?groups=80&limit=300&dates=' : '?dates=';
      return Promise.all(DAYS.map(function (d) {
        return fetch(ESPN + LG[lg][1] + '/scoreboard' + q + d.key.replace(/-/g, '')).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
      })).then(function (js) {
        var seen = {}, rows = [];
        js.forEach(function (j) { (j.events || []).forEach(function (e) { if (!seen[e.id]) { seen[e.id] = 1; rows.push(norm(lg, e)); } }); });
        liveLeagues.push(lg); return rows;
      }).catch(function () { failed.push(lg); return snapRows(lg); });
    });
    return Promise.all(jobs).then(function (all) {
      EV = [].concat.apply([], all).sort(function (x, y) { return x.t < y.t ? -1 : x.t > y.t ? 1 : 0; });
      var now = new Date().toISOString();
      if (liveLeagues.length) {
        $('live-src').innerHTML = 'live' + (failed.length ? ' (' + failed.map(function (x) { return x.toUpperCase(); }).join(', ') + ' from snapshot)' : '');
        $('live-ts').textContent = fmt(new Date(), { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' ET';
        $('live-age').dataset.age = now;
        $('sched-note').textContent = 'Eastern time · live, loaded ' + timeET(now) + ' ET';
      } else {
        $('live-src').innerHTML = 'snapshot ' + chip('live load failed', 'bad');
        $('sched-note').innerHTML = 'Eastern time · saved snapshot ' + chip('stale', 'bad');
      }
      ages(); renderSched(); evaluate();
    });
  }
  function words(s) { return String(s).toLowerCase().replace(/[^a-z0-9 ]/g, ' ').split(/\s+/).filter(Boolean); }
  function teamHit(team, names) {
    var w = words(names), t = words(team).filter(function (x) { return x.length >= 4 && x !== 'state'; });
    if (!t.length) t = words(team);
    return t.some(function (x) { return w.indexOf(x) >= 0; });
  }
  function findEvent(g) {
    var t0 = new Date(g.start).getTime();
    for (var i = 0; i < EV.length; i++) {
      var e = EV[i];
      if (e.lg !== g.sport || Math.abs(new Date(e.t).getTime() - t0) > 600000) continue;
      var s0 = g.sides[0].team, s1 = g.sides[1].team;
      if (teamHit(s0, e.an) && teamHit(s1, e.hn)) return { e: e, side: [s0, s1] };
      if (teamHit(s1, e.an) && teamHit(s0, e.hn)) return { e: e, side: [s1, s0] };
    }
    return null;
  }
  function implied(a) { a = String(a).toUpperCase(); if (a === 'EVEN') return 0.5; var n = parseFloat(a); if (!isFinite(n) || !n) return null; return n < 0 ? -n / (-n + 100) : 100 / (n + 100); }
  function tracked(e) { return D.games.some(function (g) { var m = findEvent(g); return m && m.e.id === e.id; }); }
  function rowsFor(list) {
    var h = '';
    Object.keys(LG).forEach(function (lg) {
      var L = list.filter(function (e) { return e.lg === lg; });
      if (!L.length) return;
      h += '<div class="lg">' + LG[lg][0].toUpperCase() + ' · ' + L.length + (L[0].live ? '' : ' ' + chip('snapshot', 'warn')) + '</div><div class="tw"><table><thead><tr><th class="n">Start (ET)</th><th>Matchup</th><th class="n">Line</th><th class="n">Total</th><th class="n hide-s">Moneyline (away / home)</th><th>Status</th></tr></thead><tbody>';
      L.forEach(function (e) {
        var st = e.state === 'pre' ? '' : e.state === 'in' ? chip('LIVE', 'good') + ' ' + esc(e.sa + '–' + e.sh + ' ' + (e.det || '')) : e.state === 'post' ? 'Final ' + esc(e.sa + '–' + e.sh) : chip('check live', 'warn');
        h += '<tr><td class="n">' + timeET(e.t) + '</td><td><a href="https://www.espn.com/' + LG[lg][2] + '/game/_/gameId/' + e.id + '" target="_blank" rel="noopener">' + esc(e.a) + ' at ' + esc(e.h) + '</a>' + (tracked(e) ? ' <span class="tag pk">tracked</span>' : '') +
          '</td><td class="n">' + (esc(e.line) || '<span class="muted">not posted</span>') + '</td><td class="n">' + esc(e.ou) + '</td><td class="n hide-s">' + (e.mla ? esc(e.mla + ' / ' + e.mlh) : '') + '</td><td>' + st + '</td></tr>';
      });
      h += '</tbody></table></div>';
    });
    return h;
  }
  function renderSched() {
    var by = {}; EV.forEach(function (e) { var k = ymd(new Date(e.t)); (by[k] = by[k] || []).push(e); });
    var tabs = [['today', 'Today · ' + DAYS[0].label + ' (' + (by[TODAY] || []).length + ')']];
    if (SUNDAY && SUNDAY !== TODAY) tabs.push(['sunday', 'Next Sunday · ' + DAYS[DAYS.length - 1].label + ' (' + (by[SUNDAY] || []).length + ')']);
    tabs.push(['week', 'All through Sunday (' + EV.filter(function (e) { return ymd(new Date(e.t)) >= TODAY; }).length + ')']);
    $('sched-tabs').innerHTML = tabs.map(function (t) { return '<button type="button" data-v="' + t[0] + '"' + (view === t[0] ? ' class="on"' : '') + '>' + esc(t[1]) + '</button>'; }).join('');
    var h = '';
    if (view === 'week') {
      DAYS.forEach(function (d) {
        if (!(by[d.key] || []).length) return;
        h += '<div class="day">' + esc(d.label) + (d.key === TODAY ? ' ' + chip('TODAY', 'good') : '') + (d.key === SUNDAY ? ' ' + chip('SUNDAY SLATE', 't-established') : '') + '</div>' + rowsFor(by[d.key]);
      });
    } else {
      var k = view === 'sunday' ? SUNDAY : TODAY;
      h = (by[k] || []).length ? rowsFor(by[k]) : '<p class="muted">No games on this day.</p>';
    }
    $('sched-body').innerHTML = h || '<p class="muted">No games found.</p>';
  }
  $('sched-tabs').addEventListener('click', function (e) { var b = e.target.closest('button'); if (b) { view = b.dataset.v; renderSched(); } });

  // ---------- upcoming games: the board's BET / WAIT, re-checked for freshness and kickoff on every view ----------
  function evaluate() {
    var C = D.cfg, bets = [], stale = [], open = 0;
    D.games.forEach(function (g) {
      var tr = document.querySelector('tr[data-game="' + g.id + '"]'); if (!tr) return;
      var m = findEvent(g), started = new Date(g.start) <= new Date(), ref = g.bet ? g.sides.filter(function (s) { return s.team === g.bet.side; })[0] || g.sides[0] : g.sides[0];
      var liveP = null, liveTxt = '<span class="muted">unavailable</span>';
      if (m) {
        var e = m.e, isAway = m.side[0] === ref.team, pa = implied(e.mla), ph = implied(e.mlh);
        if (e.state && e.state !== 'pre' && e.state !== 'unknown') started = true;
        if (pa && ph) liveP = 100 * (isAway ? pa : ph) / (pa + ph);
        liveTxt = (esc(e.line) || 'no line') + (liveP ? ' · ' + esc(ref.team) + ' ' + esc(isAway ? e.mla : e.mlh) + ' (' + liveP.toFixed(1) + '%)' : '') + '<br><span class="muted">' + (e.live ? 'ESPN · ' + timeET(new Date().toISOString()) : 'snapshot ' + timeET(D.sched_ts)) + '</span>' + (e.live ? '' : ' ' + chip('stale', 'bad'));
      }
      tr.querySelector('[data-live]').innerHTML = liveTxt;
      if (!started) open++;
      if (g.bet) {
        var fresh = mins(g.bet.ts) <= C.max_age, conflict = liveP != null && Math.abs(liveP - ref.pm) > C.agree, v = tr.querySelector('[data-verdict]');
        var head = started ? chip('STARTED', 'neutral') : fresh && !conflict ? chip('BET ' + g.bet.side + ' ' + g.bet.price + '¢', 'good') : chip('BET ' + g.bet.side, 'warn') + '<br>' + chip(!fresh ? 'price stale · unverified' : 'conflicting odds · unverified', 'bad');
        v.innerHTML = head;
        if (!started) (fresh && !conflict ? bets : stale).push(g);
      } else if (started) {
        tr.querySelector('[data-verdict]').innerHTML = chip('STARTED', 'neutral');
      }
      if (started) tr.querySelectorAll('a.pick').forEach(function (a) { a.style.opacity = .4; a.title = 'Game has started: calls are rejected'; });
    });
    var box = $('cand'), big, txt;
    if (bets.length) {
      var p = bets[0]; big = 'BET (paper)';
      txt = esc(p.bet.side) + ' at ' + p.bet.price + '¢ · board edge +' + Number(p.bet.edge).toFixed(1) + '¢' + (bets.length > 1 ? ' · ' + (bets.length - 1) + ' more below' : '');
      box.className = 'cand go';
    } else {
      big = 'NO QUALIFYING BET / WAIT'; box.className = 'cand';
      txt = !open ? 'No tracked game is still upcoming.' : stale.length ? 'The board had a BET on ' + esc(stale[0].bet.side) + ', but its price is over ' + C.max_age + ' min old or conflicts with the live line (unverified).'
        : 'The board has no BET on any of ' + open + ' upcoming game' + (open === 1 ? '' : 's') + ': none has an edge of ' + C.hurdle + '¢ or more backed by a source with ' + C.trusted_min + '+ graded picks.';
    }
    $('cand-h').textContent = big; $('cand-t').innerHTML = txt; $('sp-big').textContent = big; $('sp-why').innerHTML = txt;
    $('sp-big').className = 'big ' + (bets.length ? 'go' : 'wait');
  }
  evaluate();
  load().catch(function () { renderSched(); });

  // ---------- bettor table (lazy data from ledger.json) ----------
  var B = null, LED = null, openRow = {}, showAll = false;
  var q = $('bq'), fs = $('bsport'), ft = $('btier'), more = $('bmore');
  function tierRank(g) { return g >= D.cfg.trusted_min ? 0 : g >= D.cfg.verdict_min ? 1 : 2; }
  function rankCmp(x, y) { return tierRank(x.g) - tierRank(y.g) || (y.roi == null ? -9 : y.roi) - (x.roi == null ? -9 : x.roi) || y.g - x.g; }
  function need() {
    if (B) return Promise.resolve();
    return fetch('data/sports/ledger.json').then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (j) {
      LED = j; var obj = function (a) { var o = {}; j.K.forEach(function (k, i) { o[k] = a[i]; }); return o; };
      B = j.F.map(function (f, i) { var o = obj(f[3]), sp = {}; Object.keys(f[4]).forEach(function (s) { sp[s] = obj(f[4][s]); }); if (!Object.keys(sp).length) o.sp.forEach(function (s) { sp[s] = o; });
        return { i: i, name: f[0], kind: f[1], x: f[2] || null, o: o, sports: sp }; }).filter(function (b) { return b.o.g > 0; });
    });
  }
  function pc(x) { return x == null ? '–' : (x < 0 ? '−' : '') + Math.abs(x * 100).toFixed(0) + '%'; }
  function cl(x) { return x > 0 ? 'pos' : x < 0 ? 'neg' : ''; }
  var VB = { follow: ['FOLLOW', 'good'], fade: ['FADE', 'bad'], neutral: ['NEUTRAL', 'neutral'], small: ['small sample', 'warn'] };
  function picksHtml(b) {
    if (!LED) return '<span class="muted">Loading picks…</span>';
    var s = fs.value, rows = LED.P.filter(function (p) { return p[0] === b.i && (!s || LED.G[p[1]][1] === s); });
    var h = '<div class="tw"><table><thead><tr><th>Made</th><th>Game</th><th>Side</th><th class="n">Price</th><th>Crowd</th><th class="n">Result</th><th class="n">P&amp;L</th><th>Post</th></tr></thead><tbody>';
    rows.forEach(function (p) {
      var g = LED.G[p[1]];
      h += '<tr><td>' + esc(p[2]) + '</td><td>' + esc(g[0]) + ' <span class="tag">' + g[1].toUpperCase() + '</span></td><td>' + esc(p[3]) + '</td><td class="n">' + p[4] + '¢</td><td>' + esc(p[8] || '') + '</td><td class="n ' + (p[5] === 'W' ? 'pos' : p[5] === 'L' ? 'neg' : '') + '">' + (p[5] || 'pending') +
        '</td><td class="n ' + cl(p[6]) + '">' + (p[6] == null ? '–' : (p[6] < 0 ? '−$' : '+$') + Math.abs(p[6]).toFixed(2)) + '</td><td>' + (/^https:\/\/x\.com\//.test(p[7]) ? '<a href="' + esc(p[7]) + '" target="_blank" rel="noopener">X post</a>' : '') + '</td></tr>';
    });
    return h + '</tbody></table></div>';
  }
  function renderB() {
    var s = fs.value, t = ft.value, k = q.value.trim().toLowerCase(), L = [];
    B.forEach(function (b) { var o = s ? b.sports[s] : b.o; if (!o || !o.g) return; if (t && o.v !== t) return; if (k && b.name.toLowerCase().indexOf(k) < 0) return; L.push([b, o]); });
    L.sort(function (x, y) { return rankCmp(x[1], y[1]); });
    var lim = showAll || k ? L.length : 15, h = '';
    L.slice(0, lim).forEach(function (r, j) {
      var b = r[0], o = r[1], safe = b.x && /^https:\/\/x\.com\//.test(b.x), tag = { kyle: 'you', kyle_seed: 'seeded', sc: 'agent' }[b.kind], v = VB[o.v] || VB.small;
      h += '<tr data-i="' + b.i + '"><td class="n">' + (j + 1) + '</td><td>' + (safe ? '<a href="' + esc(b.x) + '" target="_blank" rel="noopener">' + esc(b.name) + '</a>' : esc(b.name) + (tag ? ' <span class="tag">' + tag + '</span>' : '')) +
        '</td><td class="n">' + o.g + '</td><td class="n">' + o.w + '-' + o.l + (o.p ? '-' + o.p : '') + '</td><td class="n">' + pc(o.wp) + '</td><td class="n ' + cl(o.roi) + '">' + pc(o.roi) +
        '</td><td class="n hide-s ' + cl(o.clv) + '">' + (o.clv == null ? '–' : (o.clv > 0 ? '+' : '') + o.clv.toFixed(2) + '¢') + '</td><td class="n">' + (o.aw || o.al ? o.aw + '-' + o.al : '–') +
        '</td><td class="n hide-s">' + (o.froi == null ? '–' : o.fw + '-' + o.fl + ' <span class="' + cl(o.froi) + '">' + pc(o.froi) + '</span>') + '</td><td>' + chip(v[0], v[1]) +
        '</td><td class="hide-s">' + o.sp.join(' ').toUpperCase() + '</td><td class="n hide-s">' + (o.last || '').slice(5) + '</td></tr>';
      if (openRow[b.i]) h += '<tr class="det"><td></td><td colspan="11">' + picksHtml(b) + '</td></tr>';
    });
    document.querySelector('#btable tbody').innerHTML = h || '<tr><td colspan="12" class="muted">Nobody matches these filters.</td></tr>';
    $('bcount').textContent = 'Showing ' + Math.min(lim, L.length) + ' of ' + L.length + (s ? ' in ' + s.toUpperCase() : '') + '. Tap a row for picks.';
    more.textContent = showAll ? 'Show top 15' : 'Show all';
  }
  function fail() { $('bcount').innerHTML = chip('could not load ledger.json', 'bad') + ' Open the page over http(s), not from a file.'; }
  [q, fs, ft].forEach(function (el) { el.addEventListener(el === q ? 'input' : 'change', function () { need().then(renderB).catch(fail); }); });
  more.addEventListener('click', function () { showAll = !showAll; need().then(renderB).catch(fail); });
  $('btable').addEventListener('click', function (e) {
    var tr = e.target.closest('tbody tr'); if (!tr || tr.classList.contains('det') || e.target.closest('a')) return;
    var rank = +tr.children[0].textContent;
    need().then(function () {
      var i = tr.dataset.i != null ? +tr.dataset.i : null;
      if (i == null) { var L = B.filter(function (b) { return b.o.g; }).sort(function (x, y) { return rankCmp(x.o, y.o); }); i = (L[rank - 1] || {}).i; }
      openRow[i] = !openRow[i]; renderB();
    }).catch(fail);
  });

  // ---------- paper calls by email (unchanged behaviour) ----------
  var sel = {}, LIMIT = 1900, TO = 'robinson@mail.grokbot.com', bar = $('pickbar'), box = $('pickbtns');
  function today() { return ymd(new Date()); }
  function url(items, part, parts) {
    var subj = 'PICKS ' + today() + ' (' + items.length + ')' + (parts > 1 ? ' ' + part + ' of ' + parts : ''), body = ['Paper picks (no real money)', ''];
    items.forEach(function (it, i) { body.push((i + 1) + '. ' + it.r); body.push(it.m); body.push(''); });
    return 'mailto:' + TO + '?subject=' + encodeURIComponent(subj) + '&body=' + encodeURIComponent(body.join('\r\n'));
  }
  function chunks(items) {
    var out = [], cur = [];
    items.forEach(function (it) { var t = cur.concat([it]); if (cur.length && url(t, 9, 9).length > LIMIT) { out.push(cur); cur = [it]; } else cur = t; });
    if (cur.length) out.push(cur); return out;
  }
  function renderPicks() {
    var items = Object.keys(sel).map(function (k) { return sel[k]; });
    document.querySelectorAll('a.pick').forEach(function (a) { var s = sel[a.dataset.g]; a.classList.toggle('sel', !!(s && s.k === a.dataset.k)); });
    box.innerHTML = ''; if (!items.length) { bar.hidden = true; return; } bar.hidden = false;
    var cs = chunks(items);
    cs.forEach(function (c, i) { var a = document.createElement('a'); a.className = 'sendall'; a.href = url(c, i + 1, cs.length); a.textContent = cs.length > 1 ? 'Email picks ' + (i + 1) + ' of ' + cs.length + ' (' + c.length + ')' : 'Email all picks (' + items.length + ')'; box.appendChild(a); });
  }
  document.querySelectorAll('a.pick[data-g]').forEach(function (a) {
    a.addEventListener('click', function (e) { e.preventDefault(); var g = a.dataset.g; if (sel[g] && sel[g].k === a.dataset.k) delete sel[g]; else sel[g] = { k: a.dataset.k, r: a.dataset.r, m: a.dataset.m }; renderPicks(); });
  });
  $('pickclear').addEventListener('click', function () { sel = {}; renderPicks(); });
})();
