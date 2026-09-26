const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let settings = null;
let chosen = [];   // asset keys in display order

function catalog() { return { ...settings.presets, ...settings.custom_assets }; }

function renderAssets() {
  const all = catalog();
  const order = [...chosen, ...Object.keys(all).filter((k) => !chosen.includes(k))];
  $("assets").innerHTML = order.map((k) => {
    const a = all[k], custom = k in settings.custom_assets;
    const pos = chosen.indexOf(k);
    return `<label class="asset-row"><input type="checkbox" data-key="${esc(k)}" ${pos >= 0 ? "checked" : ""}>
      <span class="n">${pos >= 0 ? pos + 1 : ""}</span><b>${esc(a.name)}</b> <span class="muted">${esc(a.ticker)}
      · ${a.cme ? "session" : "24/7"} · news: ${esc(a.news || "none")}</span>
      ${custom ? `<button data-remove="${esc(k)}" title="Remove custom asset">✕</button>` : ""}</label>`;
  }).join("");
}

function fillForm() {
  for (const k of ["telegram_token", "telegram_chat_id", "anthropic_api_key", "briefing_time", "oanda_token", "oanda_env"]) $(k).value = settings[k] || "";
  $("claude_scoring").checked = settings.claude_scoring;
  $("use_tuning").checked = settings.use_tuning;
}

const edgeCls = (x) => (x > 0 ? "bull" : x < 0 ? "bear" : "muted");
const edge = (x) => (x == null ? "–" : (x > 0 ? "+" : "") + x.toFixed(3) + "%");

function renderTuning(t) {
  const rows = Object.entries(t).flatMap(([asset, tfs]) => Object.entries(tfs).map(([tf, r]) => {
    const d = r.results.default?.test, c = r.results[r.variant]?.test;
    return `<tr><td>${esc(asset)}</td><td>${esc(tf)}</td><td><b>${esc(r.variant)}</b></td>
      <td class="${edgeCls(d?.edge_pct)}">${edge(d?.edge_pct)}</td><td class="${edgeCls(c?.edge_pct)}">${edge(c?.edge_pct)}</td>
      <td>${c ? c.hit_rate + "%" : "–"}</td><td class="muted">${esc(r.best_on_train)}</td><td class="muted">${r.tuned_at ? new Date(r.tuned_at).toLocaleString() : ""}</td></tr>`;
  }));
  $("tuning").innerHTML = rows.length
    ? `<table class="details"><thead><tr><th>Asset</th><th>TF</th><th>Model in use</th><th>Default edge</th><th>In-use edge</th><th>In-use hit rate</th><th>Best on older data</th><th>Tuned</th></tr></thead><tbody>${rows.join("")}</tbody></table>`
    : `<div class="empty">Not tuned yet: runs automatically once price history has loaded.</div>`;
}

async function load() {
  settings = await (await fetch("/api/settings")).json();
  chosen = [...settings.assets];
  renderAssets(); fillForm();
  renderTuning(await (await fetch("/api/tuning")).json());
}

function say(text, ok = true) { $("msg").textContent = text; $("msg").className = ok ? "bull" : "bear"; }

async function post(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

async function save() {
  const body = {
    assets: chosen,
    custom_assets: settings.custom_assets,
    telegram_token: $("telegram_token").value,
    telegram_chat_id: $("telegram_chat_id").value,
    anthropic_api_key: $("anthropic_api_key").value,
    claude_scoring: $("claude_scoring").checked,
    briefing_time: $("briefing_time").value,
    oanda_token: $("oanda_token").value,
    oanda_env: $("oanda_env").value,
    use_tuning: $("use_tuning").checked,
  };
  settings = { ...settings, ...(await post("/api/settings", body)) };
  chosen = [...settings.assets];
  renderAssets(); fillForm();
}

$("assets").addEventListener("change", (e) => {
  const k = e.target.dataset.key; if (!k) return;
  chosen = e.target.checked ? [...chosen, k] : chosen.filter((x) => x !== k);
  renderAssets();
});
$("assets").addEventListener("click", (e) => {
  const k = e.target.dataset.remove; if (!k) return;
  e.preventDefault();
  delete settings.custom_assets[k];
  chosen = chosen.filter((x) => x !== k);
  renderAssets();
});
$("c-add").addEventListener("click", () => {
  const ticker = $("c-ticker").value.trim().toUpperCase();
  if (!ticker) return say("Enter a Yahoo ticker", false);
  const key = ($("c-name").value || ticker).toUpperCase().replace(/\W/g, "").slice(0, 16);
  settings.custom_assets[key] = { ticker, name: $("c-name").value.trim() || ticker, cme: !$("c-247").checked,
    news: $("c-news").value || null, macro: Number($("c-macro").value) };
  if (!chosen.includes(key)) chosen.push(key);
  renderAssets();
  say(`Added ${ticker}. Click Save settings to apply.`);
});
$("save").addEventListener("click", async () => {
  try { await save(); say("Saved. The station picks up the changes within a few seconds."); }
  catch (e) { say(e.message, false); }
});
$("tg-test").addEventListener("click", async () => {
  try { await save(); await post("/api/telegram/test", {}); say("Test message sent. Check Telegram."); }
  catch (e) { say(e.message, false); }
});

$("retune").addEventListener("click", async () => {
  say("Retuning… this takes a few seconds.");
  try { renderTuning(await post("/api/tune", {})); say("Retuned."); } catch (e) { say(e.message, false); }
});
$("stop").addEventListener("click", async () => {
  if (!confirm("Stop ONYX? Start it again with your desktop shortcut.")) return;
  try { await post("/api/shutdown", {}); say("ONYX stopped. You can close this tab."); } catch (e) { say(e.message, false); }
});

load();
