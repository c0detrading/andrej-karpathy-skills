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
  for (const k of ["telegram_token", "telegram_chat_id", "anthropic_api_key", "briefing_time"]) $(k).value = settings[k] || "";
  $("claude_scoring").checked = settings.claude_scoring;
}

async function load() {
  settings = await (await fetch("/api/settings")).json();
  chosen = [...settings.assets];
  renderAssets(); fillForm();
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

load();
