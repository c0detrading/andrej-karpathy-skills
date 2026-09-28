const PLATFORM_SHORT = { instagram: "IG", facebook: "FB", tiktok: "TikTok" };
const PLATFORM_NAME = { instagram: "Instagram", facebook: "Facebook", tiktok: "TikTok" };
const SOURCE = { auto: "Meta", manual: "typed in", csv: "CSV" };
let board = null;       // last /api/board response
let openId = null;      // client shown in the dialog (null = new client)
let numbersFor = null;  // account whose numbers form is open

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const full = (x) => (x == null ? "–" : Number(x).toLocaleString());
const compact = (x) => (x == null ? "–" : Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(x));
const signed = (x) => (x == null ? `<span class="muted">–</span>` :
  `<span class="${x > 0 ? "up" : x < 0 ? "down" : "muted"}">${x > 0 ? "+" : ""}${Number(x).toLocaleString()}</span>`);
const pct = (x) => (x == null ? "–" : `${x.toFixed(2)}%`);
const shortDate = (iso) => (iso ? new Date(iso + "T00:00").toLocaleDateString([], { day: "numeric", month: "short" }) : "–");
const longDate = (iso) => new Date(iso + "T00:00").toLocaleDateString([], { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const money = (v) => {
  const cur = board?.currency ?? "€";
  const n = Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
  return cur.length > 1 ? `${n} ${esc(cur)}` : `${esc(cur)}${n}`;
};
const clientValue = (c) => (c.value ? money(c.value) + (c.monthly ? "/mo" : " one-off") : "");

async function api(path, { method = "GET", body } = {}) {
  const opts = { method };
  if (body !== undefined) Object.assign(opts, { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const res = await fetch(path, opts);
  if (res.status === 401) location.href = "/login";
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`);
  return data;
}

function flag(concerns) {
  if (!concerns.length) return "";
  const high = concerns.some((c) => c.level === "high");
  const n = concerns.length;
  return `<span class="flag ${high ? "high" : "medium"}" title="${esc(concerns.map((c) => c.text).join("\n"))}">` +
    `${high ? "▲" : "●"} ${n} concern${n > 1 ? "s" : ""}</span>`;
}

const level = (l) => `<span class="flag ${l}">${l === "high" ? "▲ High" : "● Medium"}</span>`;

function tiles(items) {
  return items.map(([label, value, sub]) =>
    `<div class="tile"><div class="label">${label}</div><div class="value">${value}</div><div class="sub">${sub || "&nbsp;"}</div></div>`).join("");
}

// ---- pipeline board -------------------------------------------------------

async function loadBoard() {
  board = await api("/api/board");
  renderBoard();
  if (openId != null && $("client-dlg").open) renderClientExtra();
}

function valueSums(clients) {
  const monthly = clients.filter((c) => c.monthly).reduce((s, c) => s + c.value, 0);
  const oneOff = clients.filter((c) => !c.monthly).reduce((s, c) => s + c.value, 0);
  return [monthly && `${money(monthly)}/mo`, oneOff && `${money(oneOff)} one-off`].filter(Boolean).join(" + ");
}

function renderBoard() {
  const { clients, stages, today } = board;
  const current = clients.filter((c) => c.stage === "active");
  const prospects = clients.filter((c) => c.stage !== "active" && c.stage !== "lost");
  const overdue = clients.filter((c) => c.stage !== "lost" && c.next_date && c.next_date < today);
  $("board-tiles").innerHTML = tiles([
    ["Current clients", current.length, valueSums(current)],
    ["Potential clients", prospects.length, valueSums(prospects) && `${valueSums(prospects)} potential`],
    ["Current clients needing attention", current.filter((c) => c.concerns.length).length, `<a href="#report">See the daily report</a>`],
    ["Follow-ups overdue", overdue.length, overdue.slice(0, 3).map((c) => esc(c.name)).join(", ")],
  ]);

  const showLost = $("show-lost").checked;
  $("board").innerHTML = Object.entries(stages).filter(([k]) => k !== "lost" || showLost).map(([stage, label]) => {
    const cards = clients.filter((c) => c.stage === stage);
    const sum = valueSums(cards);
    return `<section class="column ${stage === "active" ? "active-col" : ""}" data-stage="${stage}">
      <div class="col-head"><b>${esc(label)} · ${cards.length}</b><span>${sum}</span></div>
      ${cards.map((c) => card(c, today)).join("") || `<div class="muted" style="font-size:12px;padding:4px">Nothing here yet</div>`}
    </section>`;
  }).join("");
}

function card(c, today) {
  const chips = c.accounts.map((a) => `<span class="chip" title="${esc(a.platform)} @${esc(a.handle)}">` +
    `${PLATFORM_SHORT[a.platform]} ${compact(a.followers)}${a.change_7d ? " " + signed(a.change_7d) : ""}</span>`).join("");
  const next = c.next_step || c.next_date ? `<div class="card-next ${c.next_date && c.next_date < today ? "overdue" : ""}">` +
    `→ ${esc(c.next_step || "Next step")}${c.next_date ? " · " + shortDate(c.next_date) : ""}</div>` : "";
  return `<article class="card" draggable="true" data-id="${c.id}">
    <div class="card-top"><span class="card-name">${esc(c.name)}</span>${flag(c.concerns)}</div>
    ${clientValue(c) ? `<div class="card-value">${clientValue(c)}</div>` : ""}
    ${next}${chips ? `<div class="chips">${chips}</div>` : ""}
  </article>`;
}

$("board").addEventListener("click", (e) => {
  const el = e.target.closest(".card");
  if (el) openClient(Number(el.dataset.id));
});
$("board").addEventListener("dragstart", (e) => {
  const el = e.target.closest(".card");
  if (!el) return;
  e.dataTransfer.setData("text/plain", el.dataset.id);
  el.classList.add("dragging");
});
$("board").addEventListener("dragend", (e) => e.target.closest(".card")?.classList.remove("dragging"));
$("board").addEventListener("dragover", (e) => {
  const col = e.target.closest(".column");
  if (!col) return;
  e.preventDefault();
  document.querySelectorAll(".column.drop").forEach((c) => c !== col && c.classList.remove("drop"));
  col.classList.add("drop");
});
$("board").addEventListener("dragleave", (e) => {
  const col = e.target.closest(".column");
  if (col && !col.contains(e.relatedTarget)) col.classList.remove("drop");
});
$("board").addEventListener("drop", async (e) => {
  const col = e.target.closest(".column");
  if (!col) return;
  e.preventDefault();
  col.classList.remove("drop");
  const id = Number(e.dataTransfer.getData("text/plain"));
  const c = board.clients.find((x) => x.id === id);
  if (!c || c.stage === col.dataset.stage) return;
  c.stage = col.dataset.stage;  // move it right away, then save
  renderBoard();
  try { await api(`/api/clients/${id}`, { method: "PATCH", body: { stage: col.dataset.stage } }); }
  catch (err) { alert(err.message); }
  loadBoard();
});
$("show-lost").addEventListener("change", renderBoard);

// ---- client dialog --------------------------------------------------------

const form = $("client-form");

function openClient(id) {
  openId = id;
  const c = board.clients.find((x) => x.id === id) || { stage: "lead", monthly: 1 };
  $("dlg-title").textContent = id == null ? "New client" : c.name;
  $("stage-select").innerHTML = Object.entries(board.stages).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  $("platform-select").innerHTML = Object.keys(board.platforms).map((p) => `<option value="${p}">${PLATFORM_NAME[p]}</option>`).join("");
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "checkbox") el.checked = Boolean(c[el.name]);
    else el.value = c[el.name] ?? "";
  }
  if (c.value === 0) form.elements.value.value = "";
  $("client-msg").textContent = "";
  $("delete-client").hidden = id == null;
  numbersFor = null;
  renderClientExtra();
  $("client-dlg").showModal();
}

function renderClientExtra() {
  const c = board.clients.find((x) => x.id === openId);
  $("client-extra").hidden = !c;
  if (!c) return;
  $("client-concerns").innerHTML = c.concerns.length
    ? `<h3>Needs attention</h3><ul class="concerns">${c.concerns.map((x) => `<li>${level(x.level)}<span>${esc(x.text)}</span></li>`).join("")}</ul>`
    : "";
  $("accounts").innerHTML = c.accounts.length ? `<thead><tr><th>Account</th><th>Followers</th><th>7 days</th><th>Engagement</th><th>Last post</th><th>Numbers from</th><th></th></tr></thead><tbody>` +
    c.accounts.map((a) => `<tr><td><b>${PLATFORM_SHORT[a.platform]}</b> @${esc(a.handle)}</td>
      <td>${full(a.followers)}</td><td>${signed(a.change_7d)}</td><td>${pct(a.engagement)}</td>
      <td>${shortDate(a.last_post)}</td><td>${a.date ? `${shortDate(a.date)} · ${SOURCE[a.source]}` : "–"}</td>
      <td class="row-actions"><button class="link" data-numbers="${a.id}">Enter numbers</button><button class="link danger" data-remove="${a.id}">Remove</button></td></tr>` +
      (a.error ? `<tr><td class="err" colspan="7">Couldn't fetch: ${esc(a.error)}</td></tr>` : "")).join("") + "</tbody>"
    : `<tr><td class="muted">No social accounts yet.</td></tr>`;
  $("numbers-form").hidden = numbersFor == null;
}

async function saveClient() {
  const data = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    data[el.name] = el.type === "checkbox" ? el.checked : el.value;
  }
  $("client-msg").textContent = "Saving…";
  try {
    if (openId == null) openId = (await api("/api/clients", { method: "POST", body: data })).id;
    else await api(`/api/clients/${openId}`, { method: "PATCH", body: data });
    $("client-msg").textContent = "Saved";
    $("dlg-title").textContent = data.name;
    $("delete-client").hidden = false;
    await loadBoard();
  } catch (err) {
    $("client-msg").innerHTML = `<span class="error">${esc(err.message)}</span>`;
  }
}

$("new-client").addEventListener("click", () => openClient(null));
$("save-client").addEventListener("click", saveClient);
form.addEventListener("submit", (e) => { e.preventDefault(); saveClient(); });
$("dlg-close").addEventListener("click", () => $("client-dlg").close());
$("delete-client").addEventListener("click", async () => {
  const c = board.clients.find((x) => x.id === openId);
  if (!c || !confirm(`Delete ${c.name} and all their numbers? To keep the history, move them to Lost instead.`)) return;
  await api(`/api/clients/${openId}`, { method: "DELETE" });
  $("client-dlg").close();
  loadBoard();
});

$("add-account").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const btn = f.querySelector("button");
  btn.disabled = true;
  btn.textContent = f.elements.platform.value === "tiktok" ? "Adding…" : "Adding and fetching…";
  try {
    await api(`/api/clients/${openId}/accounts`, { method: "POST", body: { platform: f.elements.platform.value, handle: f.elements.handle.value } });
    f.elements.handle.value = "";
    await loadBoard();
  } catch (err) {
    alert(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Add account";
  }
});

$("accounts").addEventListener("click", async (e) => {
  const remove = e.target.dataset.remove, numbers = e.target.dataset.numbers;
  if (remove && confirm("Remove this account and its numbers?")) {
    await api(`/api/accounts/${remove}`, { method: "DELETE" });
    loadBoard();
  }
  if (numbers) {
    const a = board.clients.find((x) => x.id === openId).accounts.find((x) => x.id === Number(numbers));
    numbersFor = a.id;
    const f = $("numbers-form");
    f.reset();
    f.elements.date.value = board.today;
    $("numbers-title").textContent = `Numbers for ${PLATFORM_SHORT[a.platform]} @${a.handle}`;
    f.hidden = false;
    f.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
});
$("numbers-cancel").addEventListener("click", () => { numbersFor = null; $("numbers-form").hidden = true; });
$("numbers-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
  try {
    await api(`/api/accounts/${numbersFor}/numbers`, { method: "POST", body });
    numbersFor = null;
    await loadBoard();
  } catch (err) {
    alert(err.message);
  }
});

// ---- daily report ---------------------------------------------------------

async function loadReport(day) {
  const { dates } = await api("/api/reports");
  $("report-date").innerHTML = dates.map((d) => `<option value="${d}">${longDate(d)}</option>`).join("");
  if (!dates.length) {
    $("report-tiles").innerHTML = "";
    $("report").innerHTML = `<div class="empty">No report yet. One is made every day at the time set in Settings, or click <b>Refresh numbers now</b>.</div>`;
    return;
  }
  day = dates.includes(day) ? day : dates[0];
  $("report-date").value = day;
  renderReport(await api(`/api/reports/${day}`));
}

function renderReport(rep) {
  const t = rep.totals;
  const made = new Date(rep.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  $("report-msg").textContent = `Made at ${made}`;
  $("report-tiles").innerHTML = tiles([
    ["Current clients", t.clients],
    ["Needing attention", t.attention, t.clients ? `of ${t.clients}` : ""],
    ["High concerns", t.high, "▲ act today"],
    ["Medium concerns", t.medium, "● keep an eye on"],
  ]);
  const notice = rep.notice ? `<div class="notice">${esc(rep.notice)} <a href="settings.html">Open Settings</a></div>` : "";
  if (!rep.clients.length) {
    $("report").innerHTML = notice + `<div class="empty">No current clients yet. Move a client to <b>Current client</b> on the pipeline to include them.</div>`;
    return;
  }
  $("report").innerHTML = notice + rep.clients.map((c) => `<section class="panel report-client">
    <div class="head"><h2>${esc(c.name)}</h2>${c.concerns.length ? flag(c.concerns) : `<span class="flag ok">✓ All good</span>`}</div>
    ${c.concerns.length ? `<ul class="concerns">${c.concerns.map((x) => `<li>${level(x.level)}<span>${esc(x.text)}</span></li>`).join("")}</ul>` : ""}
    ${c.accounts.length ? `<div class="table-wrap"><table>
      <thead><tr><th>Account</th><th>Followers</th><th>1 day</th><th>7 days</th><th>30 days</th><th>Engagement</th>
        <th>30-day avg</th><th>Posts (7 days)</th><th>Last post</th><th>Numbers from</th></tr></thead>
      <tbody>${c.accounts.map((a) => `<tr><td><b>${PLATFORM_SHORT[a.platform]}</b> @${esc(a.handle)}</td>
        <td>${full(a.followers)}</td><td>${signed(a.change_1d)}</td><td>${signed(a.change_7d)}</td><td>${signed(a.change_30d)}</td>
        <td>${pct(a.engagement)}</td><td>${pct(a.engagement_avg)}</td><td>${a.posts_7d ?? "–"}</td>
        <td>${shortDate(a.last_post)}</td><td>${a.date ? `${shortDate(a.date)} · ${SOURCE[a.source]}` : "–"}</td></tr>`).join("")}</tbody>
    </table></div>` : `<p class="muted">No social accounts yet. Open the client on the pipeline to add them.</p>`}
  </section>`).join("");
}

$("report-date").addEventListener("change", (e) => loadReport(e.target.value));
$("refresh").addEventListener("click", async (e) => {
  e.target.disabled = true;
  $("report-msg").textContent = "Fetching today's numbers…";
  try {
    const rep = await api("/api/report", { method: "POST", body: {} });
    await loadReport(rep.date);
    loadBoard();
  } catch (err) {
    $("report-msg").innerHTML = `<span class="error">${esc(err.message)}</span>`;
  } finally {
    e.target.disabled = false;
  }
});

// ---- views ----------------------------------------------------------------

function route() {
  const report = location.hash === "#report";
  $("view-pipeline").hidden = report;
  $("view-report").hidden = !report;
  $("nav-pipeline").classList.toggle("on", !report);
  $("nav-report").classList.toggle("on", report);
  if (report) loadReport($("report-date").value);
}

window.addEventListener("hashchange", route);
loadBoard().then(route).catch((err) => { $("board").innerHTML = `<div class="empty error">${esc(err.message)}</div>`; });
