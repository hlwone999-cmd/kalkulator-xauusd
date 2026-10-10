/* Akun Trading MT4/MT5 — trading.js
   Hanya untuk trading.html. TIDAK menyentuh script.js kalkulator. */
"use strict";
const $ = id => document.getElementById(id);
const apiBase = new URLSearchParams(location.search).get("api") || "";

async function api(path, opts = {}) {
  let res, data;
  try {
    res = await fetch(apiBase + "/api/trading/" + path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
      body: opts.body ? JSON.stringify(opts.body) : undefined
    });
    data = await res.json();
  } catch (e) {
    throw { code: "BACKEND_OFF", message: "Backend tidak aktif atau tidak terjangkau." };
  }
  if (!res.ok) throw (data && data.error) || { code: "HTTP_" + res.status, message: "Kesalahan tak terduga." };
  return data;
}

/* ---------------- util format ---------------- */
let CURR = "USD";
const money = v => {
  if (v === null || v === undefined || !isFinite(v)) return "–";
  return (v < 0 ? "-" : "") + CURR + Math.abs(v).toLocaleString("id-ID",
    { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};
const num1 = v => (v === null || v === undefined) ? "–" :
  (+v).toLocaleString("id-ID", { maximumFractionDigits: 2 });
const dt = ts => ts ? new Date(ts * 1000).toLocaleString("id-ID",
  { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "–";
const setMsg = (el, text, cls) => { el.textContent = text || ""; el.className = "hint" + (cls ? " " + cls : ""); };

/* ---------------- status koneksi ---------------- */
function setConnectedUI(s) {
  const pill = $("statusPill"), modePill = $("modePill");
  $("emptyState").hidden = !!s.connected;
  $("dashboard").hidden = !s.connected;
  $("disconnectBtn").hidden = !s.connected;
  $("refreshBtn").hidden = !s.connected;
  modePill.hidden = !s.connected;
  if (s.connected) {
    const isDemo = s.mode === "demo";
    pill.textContent = "Terhubung · " + (s.label || s.platform.toUpperCase());
    pill.className = "pill " + (isDemo ? "" : "live");
    modePill.textContent = isDemo ? "MODE DEMONSTRASI — data contoh" : "LIVE (read-only)";
    modePill.className = "pill" + (isDemo ? "" : " live");
    CURR = (s.account && s.account.currency) || "USD";
    $("aiLogin").textContent = (s.account && s.account.login) || "–";
    $("aiBroker").textContent = (s.account && s.account.broker) || "–";
    $("aiServer").textContent = (s.account && s.account.server) || "–";
    $("aiCurrency").textContent = CURR;
    $("aiLeverage").textContent = s.account && s.account.leverage ? "1:" + s.account.leverage : "–";
    $("aiName").textContent = (s.account && s.account.name) || "–";
    $("accInfo").hidden = false;
  } else {
    pill.textContent = "Belum terhubung";
    pill.className = "pill off";
    $("accInfo").hidden = true;
  }
}

/* ---------------- form koneksi ---------------- */
function platformRows() {
  const p = $("platform").value;
  $("rowLogin").hidden = p === "demo";
  $("rowPassword").hidden = p === "demo";
  $("rowServer").hidden = p === "demo";
  $("rowBridge").hidden = p !== "mt4";
}

async function saveAccount() {
  const p = $("platform").value;
  const body = { platform: p, label: "" };
  if (p !== "demo") {
    body.login = $("login").value.trim();
    body.password = $("password").value;
    body.server = $("server").value.trim();
    if (p === "mt4") {
      body.bridge_host = $("bridgeHost").value.trim();
      body.bridge_port = $("bridgePort").value.trim();
    }
  } else {
    body.login = $("login").value.trim() || ("demo-" + Math.random().toString(36).slice(2, 6));
  }
  const r = await api("accounts", { method: "POST", body });
  await loadAccounts();
  return r.account;
}

async function connectForm() {
  const msg = $("connMsg");
  try {
    setMsg(msg, "Menyambungkan…");
    const p = $("platform").value;
    // pakai akun tersimpan bila form cocok; kalau tidak, simpan dulu
    const acc = await saveAccount();
    const r = await api("connect", { method: "POST", body: { account_id: acc.id } });
    setMsg(msg, p === "demo" ? "Terhubung ke data demonstrasi." : "Terhubung.", "ok");
    await afterConnect(r);
  } catch (e) {
    setMsg(msg, e.message || "Gagal terhubung.", "bad");
    await loadAccounts();
  }
}

async function afterConnect(r) {
  const s = await api("status");
  setConnectedUI(s);
  await loadDashboard(currentPeriod);
}

async function disconnect() {
  try { await api("disconnect", { method: "POST" }); } catch (e) { }
  const s = await api("status");
  setConnectedUI(s);
  setMsg($("connMsg"), "Koneksi diputus.");
}

/* ---------------- daftar akun ---------------- */
async function loadAccounts() {
  const d = await api("accounts");
  const box = $("accList");
  box.innerHTML = "";
  if (!d.accounts.length) {
    box.innerHTML = '<p class="hint">Belum ada akun tersimpan.</p>';
    return;
  }
  for (const a of d.accounts) {
    const el = document.createElement("div");
    el.className = "accitem" + (a.id === d.active ? " active" : "");
    const tag = a.platform === "demo" ? "DEMO" : a.platform.toUpperCase();
    el.innerHTML = `<div class="meta"><b>${escapeHtml(a.label || a.login)}</b>
      <span>${tag} · ${escapeHtml(a.login || "–")}${a.server ? " · " + escapeHtml(a.server) : ""}</span></div>`;
    const bPilih = document.createElement("button");
    bPilih.className = "btn"; bPilih.type = "button"; bPilih.textContent = "Pakai";
    bPilih.onclick = () => connectById(a.id);
    const bHapus = document.createElement("button");
    bHapus.className = "btn"; bHapus.type = "button"; bHapus.textContent = "Hapus";
    bHapus.onclick = () => removeAccount(a.id);
    el.append(bPilih, bHapus);
    box.appendChild(el);
  }
}

async function connectById(id) {
  setMsg($("connMsg"), "Menyambungkan akun…");
  try {
    await api("connect", { method: "POST", body: { account_id: id } });
    await afterConnect();
    setMsg($("connMsg"), "Terhubung.", "ok");
  } catch (e) { setMsg($("connMsg"), e.message, "bad"); }
}

async function removeAccount(id) {
  if (!confirm("Hapus akun tersimpan ini?")) return;
  await api("accounts/" + id, { method: "DELETE" });
  await loadAccounts();
  const s = await api("status");
  setConnectedUI(s);
}

/* ---------------- dashboard ---------------- */
let currentPeriod = "all";
let currentMode = null;

async function loadDashboard(period) {
  currentPeriod = period;
  document.querySelectorAll("#periods button").forEach(b =>
    b.classList.toggle("active", b.dataset.p === period));
  $("customRange").hidden = period !== "custom";
  const q = periodQ();
  const [sum, hist, curve] = await Promise.all([
    api("summary" + q), api("history" + q + "&limit=100"), api("curve" + q)
  ]);
  currentMode = sum.mode;
  renderSummary(sum, hist.total);
  renderCurve(curve.points || []);
  renderHistory(hist);
}

function periodQ() {
  if (currentPeriod === "custom") {
    const f = $("fromDate").value, t = $("toDate").value;
    const from = f ? Math.floor(new Date(f + "T00:00:00Z").getTime() / 1000) : 0;
    const to = t ? Math.floor(new Date(t + "T23:59:59Z").getTime() / 1000) : 0;
    return `?period=custom&from=${from}&to=${to}`;
  }
  return "?period=" + currentPeriod;
}

function renderSummary(s, totalHist) {
  CURR = s.balance !== null ? CURR : CURR;
  $("dashLabel").textContent = (s.mode === "demo" ? "[DEMO] " : "") + "Ringkasan akun";
  $("mBalance").textContent = money(s.balance);
  $("mEquity").textContent = money(s.equity);
  const fl = $("mFloating");
  fl.textContent = money(s.floating);
  fl.style.color = s.floating > 0 ? "var(--good)" : s.floating < 0 ? "var(--red)" : "";
  const pf = s.profit_factor === "inf" ? "∞" : num1(s.profit_factor);
  const items = [
    ["Total P/L (bersih)", money(s.net_profit), s.net_profit],
    ["Total deposit", s.total_deposit === null ? "tidak tersedia" : money(s.total_deposit), null],
    ["Total withdrawal", s.total_withdrawal === null ? "tidak tersedia" : money(s.total_withdrawal), null],
    ["Jumlah trade", num1(s.total_deals), null],
    ["Win rate", s.win_rate === null ? "–" : num1(s.win_rate) + "%", null],
    ["Menang / Kalah / Impas", `${s.wins} / ${s.losses} / ${s.breakeven}`, null],
    ["Average win", money(s.avg_win), s.avg_win],
    ["Average loss", money(s.avg_loss ? -s.avg_loss : s.avg_loss), s.avg_loss],
    ["Profit factor", pf, null],
    ["Max drawdown", s.max_drawdown_pct === null ? "–" : num1(s.max_drawdown_pct) + "% (" + money(-(s.max_drawdown_abs || 0)) + ")", null],
    ["Trade terbaik", money(s.best_trade), s.best_trade],
    ["Trade terburuk", money(s.worst_trade), s.worst_trade],
  ];
  $("metricsGrid").innerHTML = items.map(([l, v, sign]) =>
    `<div><b class="${v === "tidak tersedia" ? "" : sign > 0 ? "pos" : sign < 0 ? "neg" : ""}">${v}</b><span>${l}</span></div>`
  ).join("");
  $("statsNotes").textContent = (s.notes || []).join(" ");
}

/* ---------------- grafik kurva balance ---------------- */
function renderCurve(points) {
  const c = $("curveChart");
  if (!c.dataset.h) c.dataset.h = c.getAttribute("height");
  const dpr = Math.min(window.devicePixelRatio || 1, 3);
  const w = Math.min(c.clientWidth || 600, 1600), h = +c.dataset.h;
  c.width = w * dpr; c.height = h * dpr; c.style.height = h + "px";
  const x = c.getContext("2d");
  x.setTransform(dpr, 0, 0, dpr, 0, 0);
  x.clearRect(0, 0, w, h);
  x.font = "11px 'Instrument Sans',sans-serif";
  if (!points.length) {
    x.fillStyle = cssv("--muted"); x.textAlign = "center";
    x.fillText("Tidak ada data pada periode ini.", w / 2, h / 2);
    return;
  }
  const L = 62, R = 10, T = 10, B = 22;
  const vals = points.map(p => p.balance);
  let lo = Math.min(0, ...vals), hi = Math.max(1, ...vals);
  const pad = (hi - lo) * .08 || 1; lo -= pad; hi += pad;
  const X = i => L + (w - L - R) * i / Math.max(1, points.length - 1);
  const Y = v => T + (h - T - B) * (1 - (v - lo) / (hi - lo));
  // grid + label sumbu Y
  x.strokeStyle = cssv("--line"); x.fillStyle = cssv("--muted");
  for (let i = 0; i <= 4; i++) {
    const v = lo + (hi - lo) * i / 4, y = Y(v);
    x.beginPath(); x.moveTo(L, y); x.lineTo(w - R, y); x.stroke();
    x.textAlign = "right"; x.fillText(shortMoney(v), L - 5, y + 4);
  }
  // area + garis
  const grad = x.createLinearGradient(0, T, 0, h - B);
  grad.addColorStop(0, cssv("--goldsoft"));
  grad.addColorStop(1, "rgba(0,0,0,0)");
  x.beginPath();
  points.forEach((p, i) => i ? x.lineTo(X(i), Y(p.balance)) : x.moveTo(X(0), Y(p.balance)));
  x.lineTo(X(points.length - 1), h - B); x.lineTo(X(0), h - B); x.closePath();
  x.fillStyle = grad; x.fill();
  x.beginPath();
  points.forEach((p, i) => i ? x.lineTo(X(i), Y(p.balance)) : x.moveTo(X(0), Y(p.balance)));
  x.strokeStyle = cssv("--gold"); x.lineWidth = 2.2; x.stroke();
  // label sumbu X (awal / tengah / akhir)
  x.fillStyle = cssv("--muted"); x.textAlign = "center";
  const lbl = [0, Math.floor((points.length - 1) / 2), points.length - 1];
  [[0, "left"], [1, "center"], [2, "right"]].forEach(([k, al]) => {
    const i = lbl[k]; if (i < 0) return;
    x.textAlign = al === "left" ? "left" : al === "right" ? "right" : "center";
    const px = al === "left" ? L : al === "right" ? w - R : (L + w - R) / 2;
    x.fillText(new Date(points[i].t * 1000).toLocaleDateString("id-ID", { day: "2-digit", month: "short" }), px, h - 6);
  });
}

function shortMoney(v) {
  const a = Math.abs(v);
  const s = v < 0 ? "-" : "";
  return a >= 1e9 ? s + (a / 1e9).toFixed(1).replace(".", ",") + "M"
    : a >= 1e6 ? s + (a / 1e6).toFixed(1).replace(".", ",") + "jt"
      : a >= 1e3 ? s + Math.round(a / 1e3) + "rb" : s + Math.round(a);
}

function cssv(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }

/* ---------------- tabel riwayat ---------------- */
function renderHistory(h) {
  $("histCount").textContent = `menampilkan ${Math.min(h.deals.length, 100)} dari ${h.total} transaksi`;
  const tb = $("histBody");
  if (!h.deals.length) {
    tb.innerHTML = '<tr><td colspan="5" style="text-align:left;color:var(--muted)">Tidak ada transaksi pada periode ini.</td></tr>';
    return;
  }
  tb.innerHTML = h.deals.map(d => {
    const net = d.profit + (d.swap || 0) + (d.commission || 0);
    const cls = net > 0 ? "win" : net < 0 ? "loss" : "be";
    return `<tr><td>${dt(d.close_time)}</td><td>${escapeHtml(d.symbol || "-")}</td>
      <td class="dir">${d.type === "buy" ? "Buy" : "Sell"}</td>
      <td>${num1(d.volume)} lot</td><td class="${cls}">${money(net)}</td></tr>`;
  }).join("");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------------- inisialisasi ---------------- */
$("platform").addEventListener("change", platformRows);
$("connectBtn").addEventListener("click", () => connectForm().catch(e => setMsg($("connMsg"), e.message, "bad")));
$("disconnectBtn").addEventListener("click", disconnect);
$("saveBtn").addEventListener("click", () => saveAccount().then(() => setMsg($("connMsg"), "Akun tersimpan.", "ok")).catch(e => setMsg($("connMsg"), e.message, "bad")));
$("demoBtn").addEventListener("click", async () => {
  $("platform").value = "demo"; platformRows();
  $("connMsg").textContent = "";
  await connectForm();
});
$("refreshBtn").addEventListener("click", () => loadDashboard(currentPeriod).catch(showDashErr));
document.querySelectorAll("#periods button").forEach(b =>
  b.addEventListener("click", () => loadDashboard(b.dataset.p).catch(showDashErr)));
$("applyRange").addEventListener("click", () => loadDashboard("custom").catch(showDashErr));
window.addEventListener("resize", () => { if (!$("dashboard").hidden) loadDashboard(currentPeriod).catch(() => { }); });

function showDashErr(e) { setMsg($("connMsg"), e.message || "Gagal memuat data.", "bad"); }

(async function init() {
  platformRows();
  try {
    await api("health");
  } catch (e) {
    $("backendBanner").hidden = false;
    return;
  }
  try {
    const s = await api("status");
    setConnectedUI(s);
    if (s.connected) await loadDashboard(currentPeriod);
    await loadAccounts();
  } catch (e) {
    setMsg($("connMsg"), e.message, "bad");
  }
})();
