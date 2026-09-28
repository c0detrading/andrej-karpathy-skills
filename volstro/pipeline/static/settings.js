const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const FIELDS = ["meta_token", "report_time", "currency"];

async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const res = await fetch(path, opts);
  if (res.status === 401) location.href = "/login";
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`);
  return data;
}

function show(settings) {
  for (const k of FIELDS) $(k).value = settings[k];
}

async function save() {
  try {
    show(await api("/api/settings", Object.fromEntries(FIELDS.map((k) => [k, $(k).value]))));
    $("msg").textContent = "Saved";
    return true;
  } catch (err) {
    $("msg").innerHTML = `<span class="error">${esc(err.message)}</span>`;
    return false;
  }
}

$("save").addEventListener("click", save);

$("meta-check").addEventListener("click", async () => {
  if (!(await save())) return;  // check the token as typed
  $("meta-msg").textContent = "Checking…";
  try {
    const r = await api("/api/meta/check", {});
    const ig = r.instagram
      ? `Instagram lookups run from <b>@${esc(r.instagram.username)}</b>.`
      : `<span class="error">No Instagram business account is linked to these Pages, so Instagram numbers can't be fetched.</span>`;
    const pages = r.pages.length ? `Facebook Pages it can read: ${r.pages.map(esc).join(", ")}.` : "It can't read any Facebook Pages.";
    $("meta-msg").innerHTML = `Connected. ${ig} ${pages}`;
  } catch (err) {
    $("meta-msg").innerHTML = `<span class="error">${esc(err.message)}</span>`;
  }
});

$("csv-import").addEventListener("click", async () => {
  const file = $("csv-file").files[0];
  if (!file) return ($("csv-msg").textContent = "Choose a CSV file first.");
  try {
    const r = await api("/api/import", { csv: await file.text() });
    $("csv-msg").innerHTML = `Imported ${r.imported} row${r.imported === 1 ? "" : "s"}.` +
      (r.skipped.length ? `<ul class="error">${r.skipped.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>` : "");
  } catch (err) {
    $("csv-msg").innerHTML = `<span class="error">${esc(err.message)}</span>`;
  }
});

$("stop").addEventListener("click", async () => {
  if (!confirm("Stop the Volstro app? Start it again with the Start Volstro shortcut.")) return;
  await api("/api/shutdown", {});
  document.body.innerHTML = "<main><p>The app has stopped. You can close this tab.</p></main>";
});

api("/api/settings").then(show);
