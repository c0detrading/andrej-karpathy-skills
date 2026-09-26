const POLL_MS = 3000;
const SYMBOL_SHORT = { GOLD: "XAU", NASDAQ: "NQ", BITCOIN: "BTC" };
const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone;
let lastAlertId = null;   // null until the first poll, so old alerts are not replayed
let seenNews = null;
let newsFilter = "";
let state = null;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cls = (bias) => (bias === "BULLISH" ? "bull" : "bear");
const signCls = (x) => (x > 0 ? "bull" : x < 0 ? "bear" : "muted");
const fmt = (x, d = 2) => (x == null ? "–" : Number(x).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d }));
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

function renderSymbols() {
  const html = Object.entries(state.symbols).map(([key, s]) => {
    const tfs = state.timeframes.filter((tf) => s.timeframes[tf]);
    const tiles = state.timeframes.map((tf) => {
      const f = s.timeframes[tf];
      if (!f) return `<div class="tile"><div class="tf">${tf}</div><div class="b muted">–</div></div>`;
      return `<div class="tile ${cls(f.bias)}" title="Last bar ${esc(localDateTime(f.bar_time))}">
        <div class="tf">${tf}</div><div class="b ${cls(f.bias)}">${f.bias === "BULLISH" ? "▲ BULL" : "▼ BEAR"}</div>
        <div class="s">${signed(f.score)}</div>${bar(f.score)}</div>`;
    }).join("");
    const rows = tfs.map((tf) => {
      const f = s.timeframes[tf], v = f.values, vt = f.votes;
      const dots = [20, 50, 100, 200].map((n) => `<span class="dot ${vt["close>ema" + n] > 0 ? "bull" : "bear"}" title="close ${vt["close>ema" + n] > 0 ? "above" : "below"} EMA${n} (${fmt(v["ema" + n])})"></span>`).join("");
      const stack = ["ema20>ema50", "ema50>ema100", "ema100>ema200"].map((k) => `<span class="dot ${vt[k] > 0 ? "bull" : "bear"}" title="${k.replace(">", " > ")}"></span>`).join("");
      return `<tr><td>${tf}</td><td>${dots}</td><td>${stack}</td>
        <td class="${signCls(v.rsi - 50)}">${fmt(v.rsi, 1)}</td>
        <td class="${signCls(v.pct_b - 0.5)}">${fmt(v.pct_b, 2)}</td>
        <td class="${signCls(v.macd_hist)}">${fmt(v.macd_hist, 2)}</td>
        <td>${fmt(v.adx, 0)} <span class="${signCls(v.plus_di - v.minus_di)}">${v.plus_di > v.minus_di ? "+DI" : "−DI"}</span></td>
        <td class="${signCls(f.score)}"><b>${signed(f.score)}</b></td></tr>`;
    }).join("");
    const drivers = s.drivers.length
      ? `<ul class="drivers">${s.drivers.map((d) => `<li><span class="pts ${signCls(d.points)}">${signed(d.points, 1)}</span><span>${esc(d.title)} <span class="muted">· ${esc(d.source)}</span></span></li>`).join("")}</ul>`
      : `<div class="empty">No market-moving headlines in the last few hours.</div>`;
    const p = s.price;
    return `<div class="symbol">
      <div class="sym-head">
        <div><span class="sym-name">${esc(s.name)}</span><span class="sym-ticker">${esc(s.ticker)}</span></div>
        <div><span class="price">${fmt(p.last)}</span><span class="change ${signCls(p.change_pct)}">${signed(p.change_pct, 2)}%</span></div>
      </div>
      <div class="overall">
        <div class="pill ${cls(s.bias)}">${s.bias === "BULLISH" ? "▲" : "▼"} ${s.bias}</div>
        <div class="breakdown">Daily bias score <b class="${signCls(s.score)}">${signed(s.score)}</b><br>
          technical <b>${signed(s.technical)}</b> · news <b>${signed(s.news)}</b></div>
      </div>
      <div class="tiles">${tiles}</div>
      <div class="table-wrap"><table class="details">
        <thead><tr><th>TF</th><th title="Close vs EMA 20/50/100/200">Close vs EMA</th><th title="EMA20>50, 50>100, 100>200">EMA stack</th><th>RSI 14</th><th>BB %B</th><th>MACD hist</th><th>ADX / DMI</th><th>Score</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      <h2 style="margin-top:12px">News drivers</h2>${drivers}
    </div>`;
  }).join("");
  $("symbols").innerHTML = html || `<div class="empty">Loading market data…</div>`;
}

function renderCalendar() {
  const now = Date.now();
  const items = state.calendar.filter((e) => new Date(e.time) > now - 12 * 3600e3).slice(0, 12);
  $("calendar").innerHTML = items.length ? items.map((e) => {
    const t = new Date(e.time), past = t < now;
    const mins = Math.round((t - now) / 60e3);
    const when = localDateTime(e.time) + (!past && mins < 90 ? ` (in ${mins} min)` : "");
    const detail = [e.forecast && `F ${esc(e.forecast)}`, e.previous && `P ${esc(e.previous)}`].filter(Boolean).join(" · ");
    return `<li class="${past ? "past" : ""}"><span>${esc(when)}</span>
      <span><span class="imp ${esc(e.impact)}">${esc(e.impact.toUpperCase())}</span> ${esc(e.country)} ${esc(e.title)}</span>
      <span class="muted">${detail}</span></li>`;
  }).join("") : `<li class="empty">No upcoming USD events this week.</li>`;

  const risk = state.event_risk;
  $("event-risk").hidden = !risk;
  if (risk) $("event-risk").textContent = `⚠ Event risk: ${risk.country} ${risk.title} at ${localDateTime(risk.time)}. Bias can swing sharply around the release.`;
}

function renderNews() {
  const items = state.news.filter((n) =>
    !newsFilter || (newsFilter === "scored" ? n.impact.tags.length : n.source === newsFilter)).slice(0, 80);
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
    `<li><span class="t">${esc(localDateTime(a.time))}</span><b>${esc(a.title)}</b> <span class="muted">${esc(a.body)}</span></li>`
  ).join("") : `<li class="empty">Bias flips, market-moving headlines and upcoming high-impact events will appear here.</li>`;
}

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
    fresh.forEach((a) => new Notification(a.title, { body: a.body, tag: `ts-${a.id}` }));
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
    renderSymbols(); renderCalendar(); renderNews(); renderAlerts(); fireAlerts();
    const errs = Object.keys(state.errors);
    $("status").className = "status " + (errs.length ? "err" : "ok");
    $("status").textContent = errs.length ? `${errs.length} source error(s)` : "live";
    $("status").title = errs.map((k) => `${k}: ${state.errors[k]}`).join("\n");
  } catch (e) {
    $("status").className = "status err";
    $("status").textContent = "server offline";
  }
}

$("alerts-btn").addEventListener("click", async () => {
  if ("Notification" in window) await Notification.requestPermission();
  renderAlertsButton(); beep();
});
$("filters").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  newsFilter = b.dataset.src;
  document.querySelectorAll("#filters button").forEach((x) => x.classList.toggle("on", x === b));
  if (state) renderNews();
});
setInterval(() => {
  const now = new Date();
  $("clock").textContent = `Local ${now.toLocaleTimeString([], { hour12: false })} · New York ${nyTime(now.toISOString())}`;
}, 1000);
$("tz-note").textContent = `Times shown in your local time (${TZ}).`;

renderAlertsButton();
poll();
setInterval(poll, POLL_MS);
