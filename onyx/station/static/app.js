const CHART_REFRESH_MS = 30000;
const SYMBOL_SHORT = { GOLD: "XAU", NASDAQ: "NQ", BITCOIN: "BTC" };  // news profiles
const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone;
let lastAlertId = null;   // null until the first poll, so old alerts are not replayed
let unseenAlerts = 0;     // alerts that arrived while the Alerts tab was closed
let seenNews = null;
let newsFilter = "";
let newsLimit = 25;       // headlines shown; "Show more" adds 25
let state = null;
const chartTf = {};       // asset -> selected chart timeframe
const charts = {};        // asset -> { el, data, tf, fetchedAt }

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cls = (bias) => (bias === "BULLISH" ? "bull" : "bear");
const signCls = (x) => (x > 0 ? "bull" : x < 0 ? "bear" : "muted");
const fmt = (x, d = 2) => (x == null ? "–" : Number(x).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d }));
const decimals = (x) => (x != null && Math.abs(x) < 10 ? 4 : 2);
const price = (x) => fmt(x, decimals(x));
const signed = (x, d = 0) => {
  if (x == null) return "–";
  const r = Number(x).toFixed(d);
  return Number(r) === 0 ? Number(0).toFixed(d) : (Number(r) > 0 ? "+" : "") + r;  // never "-0"
};
const pct = (x, d = 3) => (x == null ? "–" : signed(x, d) + "%");
const nyTime = (iso, opts = { hour: "2-digit", minute: "2-digit" }) =>
  new Date(iso).toLocaleString([], { timeZone: "America/New_York", hour12: false, ...opts });
// Full date and time in the viewer's own time zone, e.g. "Sat, 26 Sep 2026 · 14:57".
const localDateTime = (iso) => {
  const d = new Date(iso);
  return d.toLocaleDateString([], { weekday: "short", day: "2-digit", month: "short", year: "numeric" }) +
    " · " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
};
const setHTML = (el, html) => { if (el._html !== html) { el.innerHTML = html; el._html = html; } };
// Remembered per browser; storage can be unavailable (private windows), so never rely on it.
const store = {
  get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* not saved, that's fine */ } },
};

// Relevance = strongest impact on any asset (0..3): grey when none, then yellow → red.
function relevanceDot(impact) {
  const r = Math.max(...Object.keys(SYMBOL_SHORT).map((k) => Math.abs(impact[k] || 0)));
  const color = r ? `hsl(${55 - (55 * Math.min(r, 3)) / 3} 75% 55%)` : "var(--rel-none)";
  return `<i class="rel" style="background:${color}" title="Relevance ${r}/3 (grey none, yellow low, red high)"></i>`;
}

// ---- views and tabs ---------------------------------------------------------

function showView() {
  const view = location.hash === "#finder" ? "finder" : "markets";
  $("view-markets").hidden = view !== "markets";
  $("view-finder").hidden = view !== "finder";
  document.querySelectorAll("#views a").forEach((a) => a.classList.toggle("on", a.dataset.view === view));
  if (view === "markets") Object.keys(charts).forEach(drawChart);  // charts drawn while hidden have no width
}

function showTab(name) {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
  document.querySelectorAll("[data-pane]").forEach((p) => { p.hidden = p.dataset.pane !== name; });
  if (name === "alerts") unseenAlerts = 0;
  renderAlertsTab();
  store.set("onyx-tab", name);
}

function renderAlertsTab() {
  document.querySelector('#tabs [data-tab="alerts"]').textContent = unseenAlerts ? `Alerts · ${unseenAlerts}` : "Alerts";
}

// ---- markets: macro and assets ---------------------------------------------

function renderMacro() {
  const items = Object.values(state.macro).map((m) => {
    const rising = m.direction === "RISING";
    return `<span title="${esc(m.ticker)} · ${Object.entries(m.timeframes).map(([tf, s]) => `${tf} ${signed(s)}`).join(" · ")}">
      ${esc(m.name)} <b>${price(m.price.last)}</b> <span class="${signCls(m.price.change_pct)}">${signed(m.price.change_pct, 2)}%</span>
      · <span class="${rising ? "bear" : "bull"}">${rising ? "rising" : "falling"}</span></span>`;
  }).join("");
  setHTML($("macro"), items
    ? `<span title="A rising dollar and rising yields weigh on gold and risk assets">Macro</span>` + items
    : `<span>Loading dollar index and 10-year yield…</span>`);
}

function liveRecord(r) {
  if (!r || !r.days) return "Live record starts after the first New York open.";
  const dots = r.recent.map((d) => `<span class="dot ${d.hit ? "bull" : "bear"}" title="${esc(d.date)}: ${d.bias} ${d.hit ? "right" : "wrong"}"></span>`).join("");
  return `<span title="Overall bias at the New York open vs that day's close">Live record ${r.hits}/${r.days} (${r.hit_rate}%) ${dots}</span>`;
}

function accTitle(a) {
  if (!a) return "";
  return `Checked against price ${a.horizon} bars later, last ${a.n} calls: right ${a.hit_rate}% of the time, ` +
    `average move in the bias direction ${pct(a.edge_pct)} (always-long: ${pct(a.baseline_pct)}). ` +
    `Strong signals only (|score| ≥ 20): ${a.strong_hit_rate ?? "–"}% of ${a.strong_n}, edge ${pct(a.strong_edge_pct)}.`;
}

const cards = {};  // asset -> { root, parts }: built once, then only changed sections are rewritten

function card(asset) {
  if (!cards[asset]) {
    const root = document.createElement("article");
    root.className = "asset";
    root.innerHTML = `<div data-p="head" class="asset-head"></div><div data-p="verdict" class="verdict"></div>
      <p data-p="read" class="read"></p><div data-p="tfs" class="tfs"></div><div data-p="chart"></div>
      <details class="more"><summary>Details</summary><div class="more-body">
        <div><h4>Key levels</h4><div data-p="levels" class="levels"></div></div>
        <div><h4>News moving the bias</h4><div data-p="drivers"></div></div>
        <div><h4>Indicators and track record</h4><p data-p="record" class="note"></p><div data-p="table" class="table-wrap"></div></div>
      </div></details>`;
    const parts = {};
    root.querySelectorAll("[data-p]").forEach((e) => { parts[e.dataset.p] = e; });
    parts.chart.replaceWith(chartBox(asset));
    cards[asset] = { root, parts };
  }
  return cards[asset];
}

function renderSymbols() {
  const box = $("symbols");
  const keys = Object.keys(state.symbols);
  if (!keys.length) { box.innerHTML = `<div class="empty">Loading market data…</div>`; return; }
  box.querySelector(".empty")?.remove();
  Object.keys(cards).filter((k) => !keys.includes(k)).forEach((k) => { cards[k].root.remove(); delete cards[k]; delete charts[k]; });
  keys.forEach((key, i) => {
    const s = state.symbols[key], { root, parts } = card(key);
    if (box.children[i] !== root) box.insertBefore(root, box.children[i] || null);
    chartTf[key] ??= "15m";
    const p = s.price;
    setHTML(parts.head, `<h3>${esc(s.name)}<span class="sub">${esc(s.ticker)} · ${esc(s.source)}</span></h3>
      <div><span class="px">${price(p.last)}</span><span class="chg ${signCls(p.change_pct)}">${signed(p.change_pct, 2)}%</span></div>`);
    const weak = s.strength === "weak";
    const word = weak ? `No clear bias <span class="muted">· leans ${s.bias === "BULLISH" ? "bullish" : "bearish"}</span>`
      : s.bias === "BULLISH" ? "Bullish" : "Bearish";
    setHTML(parts.verdict, `<span class="bias ${weak ? "weak" : cls(s.bias)}" title="${weak ? "Score is within ±20: too weak to call" : ""}">${word}</span>
      <span class="score ${signCls(s.score)}" title="Daily bias score, −100 to +100">${signed(s.score)}</span>
      <span class="muted">technical ${signed(s.technical)} · news ${signed(s.news)} · macro ${signed(s.macro)}</span>`);
    const vol = s.volatility;
    setHTML(parts.read, `${esc(s.read)}${vol ? ` Volatility ${vol.regime}: today's range is ${vol.range_used_pct}% of the daily ATR.` : ""}`);
    setHTML(parts.tfs, state.timeframes.map((tf) => {
      const f = s.timeframes[tf];
      if (!f) return `<button class="tf weak" disabled><span class="l">${tf}</span><span class="v">–</span></button>`;
      const w = f.strength === "weak";
      const title = `${tf}: ${w ? "weak, " : ""}${f.bias.toLowerCase()} (${signed(f.score)}). Click to chart. Model: ${f.model_label}.` +
        `${f.counted ? "" : " Shown for information, not counted in the daily bias."} ${accTitle(f.accuracy)}`;
      return `<button class="tf ${w ? "weak" : ""} ${f.counted ? "" : "info"}" data-asset="${esc(key)}" data-tf="${tf}" title="${esc(title)}">
        <span class="l">${tf}</span><span class="v ${w ? "" : cls(f.bias)}">${signed(f.score)}</span></button>`;
    }).join(""));
    parts.tfs.querySelectorAll(".tf").forEach((t) => t.classList.toggle("sel", t.dataset.tf === chartTf[key]));
    setHTML(parts.levels, s.levels.length ? s.levels.map((l) => {
      const where = l.distance_pct < 0 ? "above" : "below";
      return `<div class="${l.testing ? "testing" : ""}" title="${Math.abs(l.distance_pct).toFixed(2)}% ${where} price${l.testing ? " · price is testing it" : ""}">
        <span>${esc(l.name)}${l.testing ? " · testing" : ""}</span>
        <span>${price(l.price)} <span class="muted">${where === "above" ? "↑" : "↓"}${Math.abs(l.distance_pct).toFixed(2)}%</span></span></div>`;
    }).join("") : `<div class="empty">No levels yet.</div>`);
    setHTML(parts.drivers, s.news_profile == null
      ? `<div class="empty">News scoring doesn't cover this asset.</div>`
      : s.drivers.length
        ? `<ul class="drivers">${s.drivers.map((d) => `<li><span class="pts ${signCls(d.points)}">${signed(d.points, 1)}</span><span>${esc(d.title)} <span class="muted">· ${esc(d.source)}${d.related ? ` · +${d.related} related headlines counted as one event` : ""}</span></span></li>`).join("")}</ul>`
        : `<div class="empty">No market-moving headlines in the last few hours.</div>`);
    setHTML(parts.record, liveRecord(s.live_record));
    const rows = state.timeframes.filter((tf) => s.timeframes[tf]).map((tf) => {
      const f = s.timeframes[tf], v = f.values, vt = f.votes, a = f.accuracy;
      const dots = [20, 50, 100, 200].map((n) => `<span class="dot ${vt["close>ema" + n] > 0 ? "bull" : "bear"}" title="close ${vt["close>ema" + n] > 0 ? "above" : "below"} EMA${n} (${price(v["ema" + n])})"></span>`).join("");
      const stack = ["ema20>ema50", "ema50>ema100", "ema100>ema200"].map((k) => `<span class="dot ${vt[k] > 0 ? "bull" : "bear"}" title="${k.replace(">", " > ")}"></span>`).join("");
      return `<tr><td>${tf}</td><td>${dots}</td><td>${stack}</td>
        <td class="${signCls(v.rsi - 50)}">${fmt(v.rsi, 1)}</td>
        <td class="${signCls(v.pct_b - 0.5)}">${fmt(v.pct_b, 2)}</td>
        <td class="${signCls(v.macd_hist)}">${fmt(v.macd_hist, decimals(v.macd_hist))}</td>
        <td>${fmt(v.adx, 0)} <span class="${signCls(v.plus_di - v.minus_di)}">${v.plus_di > v.minus_di ? "+DI" : "−DI"}</span></td>
        <td>${price(v.atr)}</td>
        <td title="${esc(f.model_label)}">${esc(f.model)}</td>
        <td title="${esc(accTitle(a))}">${a ? a.hit_rate + "%" : "–"}</td>
        <td class="${signCls(a?.edge_pct)}">${pct(a?.edge_pct)}</td>
        <td>${a?.strong_hit_rate != null ? a.strong_hit_rate + "%" : "–"} <span class="muted">(${a?.strong_n ?? 0})</span></td>
        <td class="${signCls(f.score)}"><b>${signed(f.score)}</b></td></tr>`;
    }).join("");
    setHTML(parts.table, `<table class="details">
      <thead><tr><th>TF</th><th title="Close vs EMA 20/50/100/200">Close vs EMA</th><th title="EMA20>50, 50>100, 100>200">EMA stack</th><th>RSI 14</th><th>BB %B</th><th>MACD hist</th><th>ADX / DMI</th><th>ATR</th>
      <th title="Model in use (tuned walk-forward, see Settings)">Model</th><th title="How often the bias matched the price direction a few bars later">Hit rate</th>
      <th title="Average % move in the bias direction per call">Edge</th><th title="Hit rate when |score| ≥ 20 (number of calls)">Strong hit</th><th>Score</th></tr></thead>
      <tbody>${rows}</tbody></table>`);
    refreshChart(key);
  });
}

// ---- charts ---------------------------------------------------------------

const SERIES = [
  { key: "ema20", label: "EMA 20", color: "var(--ema20)" },
  { key: "ema50", label: "EMA 50", color: "var(--ema50)" },
  { key: "ema200", label: "EMA 200", color: "var(--ema200)" },
];

function chartBox(asset) {
  if (!charts[asset]) {
    const el = document.createElement("div");
    el.className = "chart-box";
    charts[asset] = { el, data: null, tf: null, fetchedAt: 0 };
    el.addEventListener("mousemove", (e) => chartHover(asset, e));
    el.addEventListener("mouseleave", () => { $("chart-tip").hidden = true; const x = el.querySelector(".xhair"); if (x) x.setAttribute("visibility", "hidden"); });
  }
  return charts[asset].el;
}

async function refreshChart(asset) {
  const c = charts[asset], tf = chartTf[asset];
  if (!c || (c.tf === tf && Date.now() - c.fetchedAt < CHART_REFRESH_MS)) return;
  c.tf = tf; c.fetchedAt = Date.now();
  try {
    const res = await fetch(`/api/chart?asset=${encodeURIComponent(asset)}&tf=${encodeURIComponent(tf)}`);
    c.data = res.ok ? await res.json() : null;
  } catch { c.data = null; }
  drawChart(asset);
}

function drawChart(asset) {
  const c = charts[asset], d = c.data;
  const legend = `<div class="chart-legend"><span>${esc(c.tf)}</span>
    ${SERIES.map((s) => `<span><i style="background:${s.color}"></i>${s.label}</span>`).join("")}
    <span><i style="background:var(--band);height:8px"></i>Bollinger 20, 2</span></div>`;
  if (!d) { c.el.innerHTML = legend + `<div class="empty">Chart loading…</div>`; return; }
  const W = Math.max(c.el.clientWidth || 600, 280), H = 180, padR = 30, padT = 8, padB = 18;
  const n = d.close.length, step = (W - padR) / n;
  const vals = [...d.high, ...d.low, ...d.bb_upper, ...d.bb_lower].filter((v) => v != null);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.05 || 1; lo -= pad; hi += pad;
  const y = (v) => padT + (H - padT - padB) * (1 - (v - lo) / (hi - lo));
  const x = (i) => i * step + step / 2;
  const line = (arr) => arr.map((v, i) => (v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`)).filter(Boolean).join(" ");
  const upper = d.bb_upper.map((v, i) => v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`).filter(Boolean);
  const lower = d.bb_lower.map((v, i) => v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`).filter(Boolean).reverse();
  const bw = Math.max(1, step * 0.55);
  const candles = d.close.map((cl, i) => {
    const o = d.open[i], up = cl >= o, col = up ? "var(--bull)" : "var(--bear)";
    const top = y(Math.max(o, cl)), h = Math.max(1, Math.abs(y(o) - y(cl)));
    return `<line x1="${x(i)}" x2="${x(i)}" y1="${y(d.high[i])}" y2="${y(d.low[i])}" stroke="${col}" stroke-width="1" opacity=".6"/>` +
      `<rect x="${x(i) - bw / 2}" y="${top}" width="${bw}" height="${h}" fill="${col}" opacity=".85"/>`;
  }).join("");
  const ticks = [0, 1, 2, 3].map((k) => lo + ((hi - lo) * (k + 0.5)) / 4);
  const grid = ticks.map((t) => `<line x1="0" x2="${W - padR}" y1="${y(t)}" y2="${y(t)}" stroke="var(--line-soft)" stroke-width="1"/>
    <text x="2" y="${y(t) - 3}">${price(t)}</text>`).join("");
  // Direct labels at the right edge, nudged apart so they never overlap.
  const ends = SERIES.map((s) => ({ ...s, v: d[s.key][n - 1] })).filter((s) => s.v != null).sort((a, b) => y(a.v) - y(b.v));
  ends.forEach((s, i) => { s.ly = Math.max(y(s.v), i ? ends[i - 1].ly + 11 : 0); });
  const labels = ends.map((s) => `<text x="${W - padR + 4}" y="${s.ly + 3}" style="fill:${s.color}">${s.label.replace("EMA ", "")}</text>`).join("");
  const xlab = `<text x="0" y="${H - 4}">${esc(localDateTime(d.t[0]))}</text><text x="${W - padR}" y="${H - 4}" text-anchor="end">${esc(localDateTime(d.t[n - 1]))}</text>`;
  c.geom = { step, n };
  c.el.innerHTML = legend + `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(asset)} ${esc(c.tf)} candlestick chart">
    ${grid}<polygon points="${[...upper, ...lower].join(" ")}" fill="var(--band)"/>
    ${candles}${SERIES.map((s) => `<polyline points="${line(d[s.key])}" fill="none" stroke="${s.color}" stroke-width="1.5"/>`).join("")}
    <g>${labels}</g>${xlab}
    <line class="xhair" x1="0" x2="0" y1="${padT}" y2="${H - padB}" stroke="var(--muted)" stroke-dasharray="3 3" visibility="hidden"/>
    <rect x="0" y="0" width="${W - padR}" height="${H}" fill="transparent"/></svg>`;
}

function chartHover(asset, e) {
  const c = charts[asset], d = c.data, svg = c.el.querySelector("svg");
  if (!d || !svg || !c.geom) return;
  const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
  const px = ((e.clientX - r.left) / r.width) * vb.width;
  const i = Math.floor(px / c.geom.step);
  const tip = $("chart-tip");
  if (i < 0 || i >= c.geom.n) { tip.hidden = true; return; }
  const xh = svg.querySelector(".xhair");
  xh.setAttribute("x1", i * c.geom.step + c.geom.step / 2); xh.setAttribute("x2", i * c.geom.step + c.geom.step / 2);
  xh.setAttribute("visibility", "visible");
  const row = (k, v, color) => `<div><span class="k" ${color ? `style="color:${color}"` : ""}>${k}</span> ${price(v)}</div>`;
  tip.innerHTML = `<div><b>${esc(localDateTime(d.t[i]))}</b></div>
    ${row("O", d.open[i])}${row("H", d.high[i])}${row("L", d.low[i])}${row("C", d.close[i])}
    ${SERIES.map((s) => row(s.label, d[s.key][i], s.color)).join("")}`;
  tip.hidden = false;
  tip.style.left = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8) + "px";
  tip.style.top = e.clientY + 14 + "px";
}

// ---- stock finder -------------------------------------------------------------

function renderFinder() {
  const f = state.finder, r = f.result;
  const status = [];
  if (!f.enabled) status.push(`Add your name and email for SEC in <a href="settings.html">Settings</a> to turn on the stock finder.`);
  if (f.running) status.push(`Scanning ${f.total ? `${f.done} of ${f.total}` : "…"} (the first scan takes several minutes)`);
  else if (r) status.push(`${r.passed} of ${r.scanned} companies pass · scanned ${esc(localDateTime(r.time))}` + (r.failed ? ` · ${r.failed} couldn't be read` : ""));
  if (f.error) status.push(`<span class="bear">Last scan failed: ${esc(f.error)}</span>`);
  status.push("A screen on SEC filings and delayed Yahoo prices, not financial advice. Hover a row for the rules it passed.");
  setHTML($("finder-status"), status.join(" · "));
  $("scan-btn").disabled = !f.enabled || f.running;
  const picks = r ? r.picks : [];
  setHTML($("finder"), picks.length ? `<table class="details finder"><thead><tr><th>#</th><th>Company</th><th>Score</th><th>Price</th><th>P/E</th>
      <th>Revenue YoY</th><th>EPS YoY</th><th>Net margin</th><th>RSI</th><th>vs 200-day</th><th>Off 52w high</th></tr></thead><tbody>
    ${picks.map((p, i) => `<tr title="${esc(p.why.join("\n"))}"><td class="rank">${i + 1}</td>
      <td><b>${esc(p.ticker)}</b><div class="co">${esc(p.name)} · ${esc(p.sector)}</div></td>
      <td><b>${p.score == null ? "–" : fmt(p.score * 100, 0)}</b></td><td>${price(p.price)}</td><td>${fmt(p.pe, 1)}</td>
      <td class="${signCls(p.revenue_growth_yoy)}">${pct(p.revenue_growth_yoy, 1)}</td>
      <td class="${signCls(p.eps_growth_yoy)}">${pct(p.eps_growth_yoy, 1)}</td>
      <td>${fmt(p.net_margin, 1)}%</td><td>${fmt(p.rsi14, 0)}</td>
      <td>${pct(p.pct_vs_ema200, 1)}</td><td class="muted">${pct(p.pct_from_high, 1)}</td></tr>`).join("")}</tbody></table>`
    : r && !f.running ? `<div class="empty">No S&amp;P 500 company passes every rule today.</div>` : "");
}

// ---- feed: news, calendar, alerts, briefing --------------------------------------

function renderCalendar() {
  const now = Date.now();
  const items = state.calendar.filter((e) => new Date(e.time) > now - 24 * 3600e3).slice(0, 14);
  setHTML($("calendar"), items.length ? items.map((e) => {
    const t = new Date(e.time), past = t < now;
    const mins = Math.round((t - now) / 60e3);
    const when = localDateTime(e.time) + (!past && mins < 90 ? ` · in ${mins} min` : "");
    const detail = [e.forecast && `forecast ${esc(e.forecast)}`, e.previous && `previous ${esc(e.previous)}`].filter(Boolean).join(" · ");
    const moves = e.reaction && Object.entries(e.reaction).filter(([, v]) => v != null);
    const reaction = moves && moves.length
      ? `<span class="reaction">Reaction: ${moves.map(([k, v]) => `${esc(state.asset_names[k] || k)} <b class="${signCls(v)}">${signed(v, 2)}%</b>`).join(" · ")}</span>` : "";
    return `<li class="${past && !reaction ? "past" : ""}"><div class="meta"><i class="imp ${esc(e.impact)}" title="${esc(e.impact)} impact"></i>${esc(when)}</div>
      <div>${esc(e.country)} ${esc(e.title)}</div>${detail ? `<div class="fp">${detail}</div>` : ""}${reaction}</li>`;
  }).join("") : `<li class="empty">No USD events in the last day or ahead this week.</li>`);

  const risk = state.event_risk;
  $("event-risk").hidden = !risk;
  if (risk) $("event-risk").textContent = `Event risk: ${risk.country} ${risk.title} at ${localDateTime(risk.time)}. Bias can swing sharply around the release.`;
}

function renderBriefing() {
  const b = state.briefing;
  $("briefing").textContent = b ? b.text : "No briefing yet today. It's sent at the time set in Settings, or click Generate now.";
}

function renderNews() {
  const items = state.news.filter((n) =>
    !newsFilter || (newsFilter === "scored" ? n.impact.tags.length : n.source.startsWith(newsFilter)));
  const shown = items.slice(0, newsLimit);
  const firstLoad = seenNews === null;
  seenNews ??= new Set();
  setHTML($("news"), shown.length ? shown.map((n) => {
    const fresh = !firstLoad && !seenNews.has(n.id);
    const chips = Object.keys(SYMBOL_SHORT).filter((k) => n.impact[k])
      .map((k) => `<span class="chip ${signCls(n.impact[k])}" title="${esc(n.impact.tags.join(", "))}">${SYMBOL_SHORT[k]} ${n.impact[k] > 0 ? "▲" : "▼"}${Math.abs(n.impact[k])}</span>`).join(" ");
    const safeLink = /^https?:\/\//.test(n.link || "") ? n.link : "#";
    return `<li class="${fresh ? "fresh" : ""}">
      <div class="meta">${relevanceDot(n.impact)}<span>${esc(localDateTime(n.published))}</span><span>${esc(n.source)}</span>${chips}</div>
      <a href="${esc(safeLink)}" target="_blank" rel="noopener noreferrer">${esc(n.title)}</a></li>`;
  }).join("") + (items.length > shown.length ? `<li class="empty"><button class="quiet" id="news-more">Show more</button></li>` : "")
    : `<li class="empty">No headlines yet.</li>`);
  state.news.forEach((n) => seenNews.add(n.id));
}

function renderAlerts() {
  const list = [...state.notifications].reverse().slice(0, 30);
  setHTML($("alerts"), list.length ? list.map((a) =>
    `<li><span class="t">${esc(localDateTime(a.time))}</span><b>${esc(a.title)}</b> <span class="muted">${esc(a.kind === "briefing" ? "(see the Briefing tab)" : a.body)}</span></li>`
  ).join("") : `<li class="empty">Bias flips, market-moving headlines, event reactions, stock finder picks and briefings will appear here.</li>`);
}

// ---- notifications ------------------------------------------------------------

function beep() {
  try {
    const ctx = new AudioContext(), osc = ctx.createOscillator(), gain = ctx.createGain();
    osc.frequency.value = 880; gain.gain.value = 0.08;
    osc.connect(gain).connect(ctx.destination); osc.start(); osc.stop(ctx.currentTime + 0.25);
  } catch { /* audio blocked until the user interacts with the page */ }
}

function fireAlerts() {
  const maxId = Math.max(0, ...state.notifications.map((a) => a.id));
  if (lastAlertId === null) { lastAlertId = maxId; return; }
  const fresh = state.notifications.filter((a) => a.id > lastAlertId);
  lastAlertId = maxId;
  if (!fresh.length) return;
  if (document.querySelector('[data-pane="alerts"]').hidden) { unseenAlerts += fresh.length; renderAlertsTab(); }
  beep();
  if ("Notification" in window && Notification.permission === "granted") {
    fresh.forEach((a) => new Notification(a.title, { body: a.body.slice(0, 300), tag: `ts-${a.id}` }));
  }
}

function renderAlertsButton() {
  const btn = $("alerts-btn");
  if (!("Notification" in window)) { btn.textContent = "Alerts: sound only"; btn.disabled = true; return; }
  const p = Notification.permission;
  btn.textContent = p === "granted" ? "Alerts on" : p === "denied" ? "Alerts blocked" : "Enable alerts";
  btn.classList.toggle("on", p === "granted");
}

// ---- wiring ---------------------------------------------------------------------

function render() {
  renderMacro(); renderSymbols(); renderFinder(); renderBriefing(); renderCalendar(); renderNews(); renderAlerts(); fireAlerts();
  const errs = Object.keys(state.errors);
  $("status").className = "status " + (errs.length ? "err" : "ok");
  $("status").textContent = errs.length ? `${errs.length} source error${errs.length > 1 ? "s" : ""}` : "Live";
  $("status").title = errs.map((k) => `${k}: ${state.errors[k]}`).join("\n");
}

// The server pushes new state after every update (about every 10 s); EventSource reconnects by itself.
function connect() {
  const es = new EventSource("/api/stream");
  es.onmessage = (e) => { state = JSON.parse(e.data); render(); };
  es.onerror = async () => {
    $("status").className = "status err";
    $("status").textContent = "Reconnecting…";
    try { if ((await fetch("/api/state")).status === 401) location.href = "/login"; } catch { /* server down */ }
  };
}

const postJSON = (url, body = {}) => fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

$("alerts-btn").addEventListener("click", async () => {
  if ("Notification" in window) await Notification.requestPermission();
  renderAlertsButton(); beep();
});
$("brief-btn").addEventListener("click", async () => {
  const res = await postJSON("/api/briefing");
  if (res.ok) $("briefing").textContent = (await res.json()).text;
});
$("scan-btn").addEventListener("click", () => { $("scan-btn").disabled = true; postJSON("/api/finder/scan"); });
$("tabs").addEventListener("click", (e) => { const b = e.target.closest("button[data-tab]"); if (b) showTab(b.dataset.tab); });
$("filters").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  newsFilter = b.dataset.src;
  newsLimit = 25;
  document.querySelectorAll("#filters button").forEach((x) => x.classList.toggle("on", x === b));
  if (state) renderNews();
});
$("news").addEventListener("click", (e) => {
  if (e.target.id !== "news-more") return;
  newsLimit += 25;
  renderNews();
});
$("symbols").addEventListener("click", (e) => {
  const tile = e.target.closest(".tf[data-tf]"); if (!tile) return;
  chartTf[tile.dataset.asset] = tile.dataset.tf;
  document.querySelectorAll(`.tf[data-asset="${CSS.escape(tile.dataset.asset)}"]`).forEach((t) => t.classList.toggle("sel", t === tile));
  refreshChart(tile.dataset.asset);
});
window.addEventListener("hashchange", showView);
window.addEventListener("resize", () => Object.keys(charts).forEach(drawChart));
setInterval(() => {
  const now = new Date();
  $("clock").textContent = `${now.toLocaleTimeString([], { hour12: false })} · New York ${nyTime(now.toISOString())}`;
}, 1000);
$("tz-note").textContent = `Times are in your local time (${TZ}).`;

showView();
showTab(document.querySelector(`#tabs [data-tab="${store.get("onyx-tab")}"]`) ? store.get("onyx-tab") : "news");
renderAlertsButton();
connect();
