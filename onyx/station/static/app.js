const POLL_MS = 3000;
const CHART_REFRESH_MS = 30000;
const SYMBOL_SHORT = { GOLD: "XAU", NASDAQ: "NQ", BITCOIN: "BTC" };  // news profiles
const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone;
let lastAlertId = null;   // null until the first poll, so old alerts are not replayed
let seenNews = null;
let newsFilter = "";
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
const signed = (x, d = 0) => (x == null ? "–" : (x > 0 ? "+" : "") + Number(x).toFixed(d));
const nyTime = (iso, opts = { hour: "2-digit", minute: "2-digit" }) =>
  new Date(iso).toLocaleString([], { timeZone: "America/New_York", hour12: false, ...opts });
// Full date and time in the viewer's own time zone, e.g. "Sat, 26 Sep 2026 · 14:57".
const localDateTime = (iso) => {
  const d = new Date(iso);
  return d.toLocaleDateString([], { weekday: "short", day: "2-digit", month: "short", year: "numeric" }) +
    " · " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
};
// Relevance = strongest impact on any asset (0..3): grey when none, then yellow → red.
function relevanceDot(impact) {
  const r = Math.max(...Object.keys(SYMBOL_SHORT).map((k) => Math.abs(impact[k] || 0)));
  const color = r ? `hsl(${55 - (55 * Math.min(r, 3)) / 3} 90% 55%)` : "var(--rel-none)";
  return `<i class="rel" style="background:${color}" title="Relevance ${r}/3"></i>`;
}

function bar(score) {
  const w = Math.min(Math.abs(score), 100) / 2;
  const left = score >= 0 ? 50 : 50 - w;
  return `<div class="bar"><i style="left:${left}%;width:${w}%;background:var(--${score >= 0 ? "bull" : "bear"})"></i></div>`;
}

// ---- left panel -----------------------------------------------------------

function renderMacro() {
  const cards = Object.values(state.macro).map((m) => `<div class="macro-card">
      <div><b>${esc(m.name)}</b> <span class="muted">${esc(m.ticker)}</span><br>
        <span>${price(m.price.last)}</span> <span class="${signCls(m.price.change_pct)}">${signed(m.price.change_pct, 2)}%</span></div>
      <div style="text-align:right"><div class="dir ${m.score >= 0 ? "bear" : "bull"}">${m.direction === "RISING" ? "▲ RISING" : "▼ FALLING"}</div>
        <span class="muted">${Object.entries(m.timeframes).map(([tf, s]) => `${tf} ${signed(s)}`).join(" · ")}</span></div>
    </div>`).join("");
  $("macro").innerHTML = cards || `<div class="empty">Loading dollar index and 10-year yield…</div>`;
}

function liveRecord(r) {
  if (!r || !r.days) return `<span class="muted">Live record: starts after the first New York open</span>`;
  const dots = r.recent.map((d) => `<span class="dot ${d.hit ? "bull" : "bear"}" title="${esc(d.date)}: ${d.bias} ${d.hit ? "right" : "wrong"}"></span>`).join("");
  return `<span class="record" title="Overall bias at the New York open vs that day's close">Live record ${r.hits}/${r.days} (${r.hit_rate}%) ${dots}</span>`;
}

function renderSymbols() {
  const html = Object.entries(state.symbols).map(([key, s]) => {
    chartTf[key] ??= "15m";
    const tfs = state.timeframes.filter((tf) => s.timeframes[tf]);
    const tiles = state.timeframes.map((tf) => {
      const f = s.timeframes[tf];
      if (!f) return `<div class="tile"><div class="tf">${tf}</div><div class="b muted">–</div></div>`;
      const acc = f.accuracy ? `hit ${Math.round(f.accuracy.hit_rate)}%` : "";
      return `<div class="tile ${cls(f.bias)} ${chartTf[key] === tf ? "sel" : ""}" data-asset="${esc(key)}" data-tf="${tf}"
          title="Click to chart ${tf}. Last bar ${esc(localDateTime(f.bar_time))}${f.accuracy ? `. Bias matched direction ${f.accuracy.horizon} bars later ${f.accuracy.hit_rate}% of ${f.accuracy.n} times` : ""}">
        <div class="tf">${tf}</div><div class="b ${cls(f.bias)}">${f.bias === "BULLISH" ? "▲ BULL" : "▼ BEAR"}</div>
        <div class="s">${signed(f.score)}</div>${bar(f.score)}<div class="acc">${acc}</div></div>`;
    }).join("");
    const rows = tfs.map((tf) => {
      const f = s.timeframes[tf], v = f.values, vt = f.votes;
      const dots = [20, 50, 100, 200].map((n) => `<span class="dot ${vt["close>ema" + n] > 0 ? "bull" : "bear"}" title="close ${vt["close>ema" + n] > 0 ? "above" : "below"} EMA${n} (${price(v["ema" + n])})"></span>`).join("");
      const stack = ["ema20>ema50", "ema50>ema100", "ema100>ema200"].map((k) => `<span class="dot ${vt[k] > 0 ? "bull" : "bear"}" title="${k.replace(">", " > ")}"></span>`).join("");
      const acc = f.accuracy;
      return `<tr><td>${tf}</td><td>${dots}</td><td>${stack}</td>
        <td class="${signCls(v.rsi - 50)}">${fmt(v.rsi, 1)}</td>
        <td class="${signCls(v.pct_b - 0.5)}">${fmt(v.pct_b, 2)}</td>
        <td class="${signCls(v.macd_hist)}">${fmt(v.macd_hist, decimals(v.macd_hist))}</td>
        <td>${fmt(v.adx, 0)} <span class="${signCls(v.plus_di - v.minus_di)}">${v.plus_di > v.minus_di ? "+DI" : "−DI"}</span></td>
        <td>${price(v.atr)}</td>
        <td title="${acc ? `${acc.n} samples, ${acc.horizon} bars ahead` : ""}">${acc ? acc.hit_rate + "%" : "–"}</td>
        <td class="${signCls(f.score)}"><b>${signed(f.score)}</b></td></tr>`;
    }).join("");
    const drivers = s.news_profile == null
      ? `<div class="empty">News scoring doesn't cover this asset.</div>`
      : s.drivers.length
        ? `<ul class="drivers">${s.drivers.map((d) => `<li><span class="pts ${signCls(d.points)}">${signed(d.points, 1)}</span><span>${esc(d.title)} <span class="muted">· ${esc(d.source)}</span></span></li>`).join("")}</ul>`
        : `<div class="empty">No market-moving headlines in the last few hours.</div>`;
    const levels = s.levels.map((l) => {
      const where = l.distance_pct < 0 ? "above" : "below";
      return `<span class="lvl ${l.testing ? "testing" : ""}" title="Level is ${Math.abs(l.distance_pct).toFixed(2)}% ${where} price${l.testing ? " · price is testing it" : ""}">
        ${esc(l.name)} <b>${price(l.price)}</b> ${where === "above" ? "↑" : "↓"}${Math.abs(l.distance_pct).toFixed(2)}%${l.testing ? " · testing" : ""}</span>`;
    }).join("");
    const vol = s.volatility;
    const p = s.price;
    return `<div class="symbol">
      <div class="sym-head">
        <div><span class="sym-name">${esc(s.name)}</span><span class="sym-ticker">${esc(s.ticker)}</span></div>
        <div><span class="price">${price(p.last)}</span><span class="change ${signCls(p.change_pct)}">${signed(p.change_pct, 2)}%</span></div>
      </div>
      <div class="overall">
        <div class="pill ${cls(s.bias)}">${s.bias === "BULLISH" ? "▲" : "▼"} ${s.bias}</div>
        <div class="breakdown">Daily bias score <b class="${signCls(s.score)}">${signed(s.score)}</b><br>
          technical <b>${signed(s.technical)}</b> · news <b>${signed(s.news)}</b> · macro <b>${signed(s.macro)}</b><br>
          ${liveRecord(s.live_record)}</div>
      </div>
      <p class="read">${esc(s.read)}${vol ? ` <span class="muted">· Volatility <b>${vol.regime}</b>: today's range is ${vol.range_used_pct}% of the daily ATR (${fmt(vol.atr_pct, 2)}% of price).</span>` : ""}</p>
      <div class="tiles">${tiles}</div>
      <div class="chart-slot" data-asset="${esc(key)}"></div>
      <div class="chips">${levels}</div>
      <details class="more" ${openDetails.has(key) ? "open" : ""} data-asset="${esc(key)}"><summary>Indicators by timeframe</summary>
      <div class="table-wrap"><table class="details">
        <thead><tr><th>TF</th><th title="Close vs EMA 20/50/100/200">Close vs EMA</th><th title="EMA20>50, 50>100, 100>200">EMA stack</th><th>RSI 14</th><th>BB %B</th><th>MACD hist</th><th>ADX / DMI</th><th>ATR</th><th title="How often this timeframe's bias matched the price direction a few bars later">Hit rate</th><th>Score</th></tr></thead>
        <tbody>${rows}</tbody></table></div></details>
      <h2 style="margin-top:12px">News drivers</h2>${drivers}
    </div>`;
  }).join("");
  $("symbols").innerHTML = html || `<div class="empty">Loading market data…</div>`;
  // Charts live outside the re-rendered HTML so hover state survives each poll.
  document.querySelectorAll(".chart-slot").forEach((slot) => slot.replaceWith(chartBox(slot.dataset.asset)));
  Object.keys(state.symbols).forEach(refreshChart);
}

const openDetails = new Set();

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
  const legend = `<div class="chart-legend"><b style="color:var(--text)">${esc(c.tf)} chart</b>
    ${SERIES.map((s) => `<span><i style="background:${s.color}"></i>${s.label}</span>`).join("")}
    <span><i class="band"></i>Bollinger 20, 2</span></div>`;
  if (!d) { c.el.innerHTML = legend + `<div class="empty">Chart loading…</div>`; return; }
  const W = Math.max(c.el.clientWidth || 600, 280), H = 200, padR = 30, padT = 8, padB = 18;
  const n = d.close.length, step = (W - padR) / n;
  const vals = [...d.high, ...d.low, ...d.bb_upper, ...d.bb_lower].filter((v) => v != null);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.05 || 1; lo -= pad; hi += pad;
  const y = (v) => padT + (H - padT - padB) * (1 - (v - lo) / (hi - lo));
  const x = (i) => i * step + step / 2;
  const line = (arr) => arr.map((v, i) => (v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`)).filter(Boolean).join(" ");
  const upper = d.bb_upper.map((v, i) => v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`).filter(Boolean);
  const lower = d.bb_lower.map((v, i) => v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`).filter(Boolean).reverse();
  const bw = Math.max(1, step * 0.6);
  const candles = d.close.map((cl, i) => {
    const o = d.open[i], up = cl >= o, col = up ? "var(--bull)" : "var(--bear)";
    const top = y(Math.max(o, cl)), h = Math.max(1, Math.abs(y(o) - y(cl)));
    return `<line x1="${x(i)}" x2="${x(i)}" y1="${y(d.high[i])}" y2="${y(d.low[i])}" stroke="${col}" stroke-width="1"/>` +
      `<rect x="${x(i) - bw / 2}" y="${top}" width="${bw}" height="${h}" fill="${col}"/>`;
  }).join("");
  const ticks = [0, 1, 2, 3].map((k) => lo + ((hi - lo) * (k + 0.5)) / 4);
  const grid = ticks.map((t) => `<line x1="0" x2="${W - padR}" y1="${y(t)}" y2="${y(t)}" stroke="var(--line)" stroke-width="1"/>
    <text x="2" y="${y(t) - 3}">${price(t)}</text>`).join("");
  // Direct labels at the right edge, nudged apart so they never overlap.
  const ends = SERIES.map((s) => ({ ...s, v: d[s.key][n - 1] })).filter((s) => s.v != null).sort((a, b) => y(a.v) - y(b.v));
  ends.forEach((s, i) => { s.ly = Math.max(y(s.v), i ? ends[i - 1].ly + 11 : 0); });
  const labels = ends.map((s) => `<text x="${W - padR + 4}" y="${s.ly + 3}" style="fill:${s.color}">${s.label.replace("EMA ", "")}</text>`).join("");
  const xlab = `<text x="0" y="${H - 4}">${esc(localDateTime(d.t[0]))}</text><text x="${W - padR}" y="${H - 4}" text-anchor="end">${esc(localDateTime(d.t[n - 1]))}</text>`;
  c.geom = { step, n };
  c.el.innerHTML = legend + `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(asset)} ${esc(c.tf)} candlestick chart">
    ${grid}<polygon points="${[...upper, ...lower].join(" ")}" fill="rgba(125,136,150,.12)"/>
    ${candles}${SERIES.map((s) => `<polyline points="${line(d[s.key])}" fill="none" stroke="${s.color}" stroke-width="2"/>`).join("")}
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

// ---- right panel ----------------------------------------------------------

function renderCalendar() {
  const now = Date.now();
  const items = state.calendar.filter((e) => new Date(e.time) > now - 24 * 3600e3).slice(0, 14);
  $("calendar").innerHTML = items.length ? items.map((e) => {
    const t = new Date(e.time), past = t < now;
    const mins = Math.round((t - now) / 60e3);
    const when = localDateTime(e.time) + (!past && mins < 90 ? ` (in ${mins} min)` : "");
    const detail = [e.forecast && `F ${esc(e.forecast)}`, e.previous && `P ${esc(e.previous)}`].filter(Boolean).join(" · ");
    const moves = e.reaction && Object.entries(e.reaction).filter(([, v]) => v != null);
    const reaction = moves && moves.length
      ? `<span class="reaction">Reaction: ${moves.map(([k, v]) => `${esc(state.asset_names[k] || k)} <b class="${signCls(v)}">${signed(v, 2)}%</b>`).join(" · ")}</span>` : "";
    return `<li class="${past && !reaction ? "past" : ""}"><span>${esc(when)}</span>
      <span><span class="imp ${esc(e.impact)}">${esc(e.impact.toUpperCase())}</span> ${esc(e.country)} ${esc(e.title)}</span>
      <span class="muted">${detail}</span>${reaction}</li>`;
  }).join("") : `<li class="empty">No USD events in the last day or ahead this week.</li>`;

  const risk = state.event_risk;
  $("event-risk").hidden = !risk;
  if (risk) $("event-risk").textContent = `⚠ Event risk: ${risk.country} ${risk.title} at ${localDateTime(risk.time)}. Bias can swing sharply around the release.`;
}

function renderBriefing() {
  const b = state.briefing;
  $("briefing").textContent = b ? b.text : "No briefing yet today. It's sent at the time set in Settings, or click Generate now.";
}

function renderNews() {
  const items = state.news.filter((n) =>
    !newsFilter || (newsFilter === "scored" ? n.impact.tags.length : n.source.startsWith(newsFilter))).slice(0, 80);
  const firstLoad = seenNews === null;
  seenNews ??= new Set();
  $("news").innerHTML = items.length ? items.map((n) => {
    const fresh = !firstLoad && !seenNews.has(n.id);
    const chips = Object.keys(SYMBOL_SHORT).filter((k) => n.impact[k])
      .map((k) => `<span class="chip ${signCls(n.impact[k])}">${SYMBOL_SHORT[k]} ${n.impact[k] > 0 ? "▲" : "▼"}${Math.abs(n.impact[k])}</span>`).join(" ");
    const safeLink = /^https?:\/\//.test(n.link || "") ? n.link : "#";
    return `<li class="${fresh ? "fresh" : ""}">
      <div class="meta">${relevanceDot(n.impact)}<span>${esc(localDateTime(n.published))}</span><span>${esc(n.source)}</span>${chips}
        ${n.impact.tags.length ? `<span class="tag">${esc(n.impact.tags.join(", "))}</span>` : ""}</div>
      <a href="${esc(safeLink)}" target="_blank" rel="noopener noreferrer">${esc(n.title)}</a></li>`;
  }).join("") : `<li class="empty">No headlines yet.</li>`;
  state.news.forEach((n) => seenNews.add(n.id));
}

function renderAlerts() {
  const list = [...state.notifications].reverse().slice(0, 30);
  $("alerts").innerHTML = list.length ? list.map((a) =>
    `<li><span class="t">${esc(localDateTime(a.time))}</span><b>${esc(a.title)}</b> <span class="muted">${esc(a.kind === "briefing" ? "(see Briefing above)" : a.body)}</span></li>`
  ).join("") : `<li class="empty">Bias flips, market-moving headlines, event reactions and briefings will appear here.</li>`;
}

function renderHeader() {
  $("subtitle").textContent = Object.values(state.asset_names).join(" · ");
  const f = state.features;
  $("features").innerHTML = `<span class="feat ${f.telegram ? "on" : ""}" title="Configure in Settings">Telegram ${f.telegram ? "on" : "off"}</span>` +
    `<span class="feat ${f.claude ? "on" : ""}" title="Configure in Settings">Claude news ${f.claude ? "on" : "off"}</span>`;
}

// ---- alerts -----------------------------------------------------------------

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

async function poll() {
  try {
    const res = await fetch("/api/state");
    state = await res.json();
    renderHeader(); renderMacro(); renderSymbols(); renderBriefing(); renderCalendar(); renderNews(); renderAlerts(); fireAlerts();
    const errs = Object.keys(state.errors);
    $("status").className = "status " + (errs.length ? "err" : "ok");
    $("status").textContent = errs.length ? `${errs.length} source error(s)` : "live";
    $("status").title = errs.map((k) => `${k}: ${state.errors[k]}`).join("\n");
  } catch (e) {
    $("status").className = "status err";
    $("status").textContent = "server offline";
  }
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
$("filters").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  newsFilter = b.dataset.src;
  document.querySelectorAll("#filters button").forEach((x) => x.classList.toggle("on", x === b));
  if (state) renderNews();
});
$("symbols").addEventListener("click", (e) => {
  const tile = e.target.closest(".tile[data-tf]"); if (!tile) return;
  chartTf[tile.dataset.asset] = tile.dataset.tf;
  document.querySelectorAll(`.tile[data-asset="${CSS.escape(tile.dataset.asset)}"]`).forEach((t) => t.classList.toggle("sel", t === tile));
  refreshChart(tile.dataset.asset);
});
$("symbols").addEventListener("toggle", (e) => {
  const d = e.target.closest("details.more"); if (!d) return;
  d.open ? openDetails.add(d.dataset.asset) : openDetails.delete(d.dataset.asset);
}, true);
window.addEventListener("resize", () => Object.keys(charts).forEach(drawChart));
setInterval(() => {
  const now = new Date();
  $("clock").textContent = `Local ${now.toLocaleTimeString([], { hour12: false })} · New York ${nyTime(now.toISOString())}`;
}, 1000);
$("tz-note").textContent = `Times shown in your local time (${TZ}).`;

renderAlertsButton();
poll();
setInterval(poll, POLL_MS);
