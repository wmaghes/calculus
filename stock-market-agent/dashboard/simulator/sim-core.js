/* ---------- Stock Market Simulator: shared core ----------
 * Loaded by every mode page (individual/ib/banker/advisor/derivatives/
 * shortseller.html) after engine.js and before that page's own mode-<key>.js
 * and tiny inline boot script. Holds everything that isn't specific to a
 * single profession mode: state/profile/engine plumbing, trading primitives
 * used by 2+ modes, the market panel (every mode needs live prices), the
 * company-profile modal, and the bootSimPage() helper that replaces the old
 * single-page boot()/runTick()/setMode() now that each page renders and
 * ticks exactly one mode instead of picking one of six.
 */

/* ---------- shared utilities ---------- */

const LEGACY_STORE_KEY = "simState.v2";
const LEGACY_ENGINE_KEY = "simEngine.v1";
const PROFILES_REGISTRY_KEY = "simProfiles.v1";
const LAST_CODE_KEY = "simLastCode.v1";
const STARTING_CASH_INDIVIDUAL = 100000;
const STARTING_CASH_CLIENT = 250000;
const SUPER_UNIVERSE_SIZE = 24;
const TICK_INTERVAL_MS = 1000;

function freshDerivativesState() {
  return { cash: STARTING_CASH_INDIVIDUAL, startCash: STARTING_CASH_INDIVIDUAL, options: [], optionHistory: [], futures: [], futureHistory: [], nextOptionId: 1, nextFutureId: 1 };
}
function freshShortSellerState() {
  return { cash: STARTING_CASH_INDIVIDUAL, startCash: STARTING_CASH_INDIVIDUAL, holdings: {}, shorts: {}, history: [] };
}
function freshWorldState() {
  return {
    individual: { cash: STARTING_CASH_INDIVIDUAL, startCash: STARTING_CASH_INDIVIDUAL, holdings: {}, history: [] },
    banker: { clients: {}, nextId: 1 },
    advisor: { plans: {}, nextId: 1 },
    derivatives: freshDerivativesState(),
    shortseller: freshShortSellerState(),
  };
}

/* ---------- player-code profiles ---------- */
// There is no backend here -- this whole site is static files. A "profile"
// is just a localStorage namespace keyed by a code the player picks for
// themselves, so the same browser can resume (or wipe) that save any time.
// It does NOT transfer progress to a different browser or computer.

function codeStoreKey(code) { return "simState.v2::" + code; }
function codeEngineKey(code) { return "simEngine.v1::" + code; }
function normalizeCode(raw) { return String(raw || "").trim().replace(/\s+/g, " ").toUpperCase().slice(0, 30); }
function isValidCode(code) { return code.length >= 3 && /^[A-Z0-9 _-]+$/.test(code); }

function getProfilesRegistry() {
  try { return JSON.parse(localStorage.getItem(PROFILES_REGISTRY_KEY) || "{}"); } catch (e) { return {}; }
}
function touchProfile(code, extra) {
  try {
    const reg = getProfilesRegistry();
    const now = Date.now();
    reg[code] = Object.assign({ createdAt: now }, reg[code] || {}, { lastActiveAt: now }, extra || {});
    localStorage.setItem(PROFILES_REGISTRY_KEY, JSON.stringify(reg));
    localStorage.setItem(LAST_CODE_KEY, code);
  } catch (e) {}
}
function profileHasSave(code) {
  try { return localStorage.getItem(codeStoreKey(code)) !== null; } catch (e) { return false; }
}
function deleteProfileSave(code) {
  try { localStorage.removeItem(codeStoreKey(code)); localStorage.removeItem(codeEngineKey(code)); } catch (e) {}
}
function claimLegacySave(code) {
  try {
    const s = localStorage.getItem(LEGACY_STORE_KEY);
    const e = localStorage.getItem(LEGACY_ENGINE_KEY);
    if (s) localStorage.setItem(codeStoreKey(code), s);
    if (e) localStorage.setItem(codeEngineKey(code), e);
    localStorage.removeItem(LEGACY_STORE_KEY);
    localStorage.removeItem(LEGACY_ENGINE_KEY);
  } catch (e) {}
  touchProfile(code, { migratedFromLegacy: true });
}

// Shows a gate every page load (so this reads as a real "log in" step), but
// offers a one-click "continue as" when this browser already remembers a
// code with a save. Resolves once ACTIVE_CODE is set.
function runProfileGate() {
  return new Promise((resolve) => {
    const modal = document.getElementById("profileGateModal");
    const input = document.getElementById("profileCodeInput");
    const goBtn = document.getElementById("profileGoBtn");
    const restartBtn = document.getElementById("profileRestartBtn");
    const msgEl = document.getElementById("profileGateMsg");
    const continueRow = document.getElementById("continueAsRow");
    const legacyRow = document.getElementById("legacyClaimRow");

    function showMsg(m) { msgEl.textContent = m; msgEl.style.display = "block"; }
    function activate(code) {
      ACTIVE_CODE = code;
      touchProfile(code);
      modal.style.display = "none";
      resolve(code);
    }
    function updateRestartVisibility() {
      const code = normalizeCode(input.value);
      restartBtn.style.display = isValidCode(code) && profileHasSave(code) ? "inline-flex" : "none";
    }

    let lastCode = null;
    try { lastCode = localStorage.getItem(LAST_CODE_KEY); } catch (e) {}
    if (lastCode) input.value = lastCode;
    if (lastCode && profileHasSave(lastCode)) {
      continueRow.style.display = "block";
      continueRow.innerHTML = `<button class="action buy" id="continueAsBtn">Continue as ${escapeHtml(lastCode)}</button>`;
      document.getElementById("continueAsBtn").addEventListener("click", () => activate(lastCode));
    }

    let hasLegacy = false;
    try { hasLegacy = localStorage.getItem(LEGACY_STORE_KEY) !== null; } catch (e) {}
    if (hasLegacy) {
      legacyRow.style.display = "block";
      legacyRow.innerHTML = `Found a saved game from before player codes existed. Type a code above, then <button class="action ghost" id="claimLegacyBtn" style="margin-left:4px;padding:4px 10px;font-size:11.5px">claim it with that code</button> instead of starting fresh.`;
      document.getElementById("claimLegacyBtn").addEventListener("click", () => {
        const code = normalizeCode(input.value);
        if (!isValidCode(code)) return showMsg("Enter a code first: 3-30 letters, numbers, spaces or dashes.");
        claimLegacySave(code);
        activate(code);
      });
    }

    goBtn.addEventListener("click", () => {
      const code = normalizeCode(input.value);
      if (!isValidCode(code)) return showMsg("Enter a code: 3-30 letters, numbers, spaces or dashes.");
      activate(code);
    });
    input.addEventListener("input", updateRestartVisibility);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") goBtn.click(); });
    restartBtn.addEventListener("click", () => {
      const code = normalizeCode(input.value);
      if (!isValidCode(code)) return;
      if (!confirm(`Erase ALL saved progress for code "${code}" and start over? This cannot be undone.`)) return;
      deleteProfileSave(code);
      activate(code);
    });

    modal.style.display = "flex";
    input.focus();
  });
}

function renderProfileBar() {
  const el = document.getElementById("profileBar");
  if (!el || !ACTIVE_CODE) return;
  el.innerHTML = `<span class="mono" style="font-size:12px;color:var(--ink-faint)">Playing as <strong style="color:var(--ink)">${escapeHtml(ACTIVE_CODE)}</strong></span> ` +
    `<button class="action ghost" id="switchProfileBtn" style="margin-left:8px;padding:4px 10px;font-size:11px">Switch / log out</button>` +
    `<button class="action ghost" id="restartProfileBtn" style="margin-left:6px;padding:4px 10px;font-size:11px">Restart this code</button>`;
  document.getElementById("switchProfileBtn").addEventListener("click", () => {
    saveState(STATE); saveEngineState();
    try { localStorage.removeItem(LAST_CODE_KEY); } catch (e) {}
    location.reload();
  });
  document.getElementById("restartProfileBtn").addEventListener("click", () => {
    if (!confirm(`Erase ALL saved progress for code "${ACTIVE_CODE}" and start over? This cannot be undone.`)) return;
    deleteProfileSave(ACTIVE_CODE);
    location.reload();
  });
}

function loadState() {
  let s = null;
  try { s = JSON.parse(localStorage.getItem(codeStoreKey(ACTIVE_CODE)) || "null"); } catch (e) { s = null; }
  if (!s) s = {};
  if (s.marketMode !== "real" && s.marketMode !== "super") s.marketMode = "real";
  if (!s.speedKey) s.speedKey = "position";
  if (typeof s.running !== "boolean") s.running = true;
  if (!s.worlds) s.worlds = {};
  if (!s.worlds.real) s.worlds.real = freshWorldState();
  if (!s.worlds.super) s.worlds.super = freshWorldState();
  for (const w of [s.worlds.real, s.worlds.super]) {
    if (!w.derivatives) w.derivatives = freshDerivativesState();
    if (!w.shortseller) w.shortseller = freshShortSellerState();
    if (typeof w.derivatives.nextOptionId !== "number") w.derivatives.nextOptionId = (w.derivatives.options || []).length + 1;
    if (typeof w.derivatives.nextFutureId !== "number") w.derivatives.nextFutureId = (w.derivatives.futures || []).length + 1;
  }
  // Real Companies mode is locked to a single real-time speed (see market
  // panel) so it can never look like a fast-forwarded prediction tool for
  // real securities.
  if (s.marketMode === "real") s.speedKey = "realtime";
  return s;
}
function saveState(s) {
  try { localStorage.setItem(codeStoreKey(ACTIVE_CODE), JSON.stringify(s)); } catch (e) { /* storage unavailable; state stays in-memory only */ }
  touchProfile(ACTIVE_CODE);
}
function worldState() { return STATE.worlds[STATE.marketMode]; }

let ACTIVE_CODE = null;
let STATE = null;
let UNIVERSE = {};      // ticker -> {ticker, name, price, category, sector}
let RESEARCH = {};      // ticker -> research/data.json company record (real mode only)
let SCANNER_DATA = null;
let ENGINE_REAL = null;
let ENGINE_SUPER = null;
let CURRENT_MODE = null;   // this page's single mode key, set by bootSimPage()
let CURRENT_RENDER = null; // this page's single render function, set by bootSimPage()
let tickCounter = 0;

function activeWorld() { return STATE.marketMode === "super" ? ENGINE_SUPER : ENGINE_REAL; }

function loadEngineState() {
  try { return JSON.parse(localStorage.getItem(codeEngineKey(ACTIVE_CODE)) || "null"); } catch (e) { return null; }
}
function saveEngineState() {
  try { localStorage.setItem(codeEngineKey(ACTIVE_CODE), JSON.stringify({ real: ENGINE_REAL, super: ENGINE_SUPER })); } catch (e) {}
}
function isEditingForm() {
  const ae = document.activeElement;
  return !!ae && (ae.tagName === "INPUT" || ae.tagName === "SELECT");
}

function fmtMoney(n, opts) {
  opts = opts || {};
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const neg = n < 0;
  const abs = Math.abs(n);
  let out;
  if (opts.compact && abs >= 1e9) out = "$" + (abs / 1e9).toFixed(2) + "B";
  else if (opts.compact && abs >= 1e6) out = "$" + (abs / 1e6).toFixed(2) + "M";
  else out = "$" + abs.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return (neg ? "-" : "") + out;
}
function fmtPct(n, digits) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  digits = digits === undefined ? 1 : digits;
  return (n >= 0 ? "+" : "") + n.toFixed(digits) + "%";
}
function pnlClass(n) { return n > 0 ? "pos" : (n < 0 ? "neg" : ""); }

// Client/plan names are free text the user types; they get rendered back
// into innerHTML in several places, so escape before interpolating to
// prevent a stored self-XSS (e.g. a client named `<img src=x onerror=...>`).
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/* ---------- engine <-> universe bridge ---------- */

function refreshUniverseFromEngine() {
  const world = activeWorld();
  const u = {};
  for (const t of Object.values(world.tickers)) {
    u[t.ticker] = { ticker: t.ticker, name: t.name, price: t.price, category: t.category, sector: t.sector };
  }
  UNIVERSE = u;
}

async function loadResearch() {
  try {
    const res = await fetch("../research/data.json");
    const data = await res.json();
    return data.companies || {};
  } catch (e) {
    return {};
  }
}

function universeOptions(selectedTicker) {
  const groups = {};
  for (const t of Object.values(UNIVERSE)) {
    const key = t.sector || t.category;
    (groups[key] = groups[key] || []).push(t);
  }
  const catLabel = { growth: "Growth", stability: "Stability", nextgen: "Next-Gen", shorts: "Shorts / High-risk" };
  let html = "";
  for (const [key, items] of Object.entries(groups)) {
    html += `<optgroup label="${catLabel[key] || key}">`;
    for (const t of items.sort((a, b) => a.ticker.localeCompare(b.ticker))) {
      html += `<option value="${t.ticker}" ${t.ticker === selectedTicker ? "selected" : ""}>${t.ticker} — ${t.name}</option>`;
    }
    html += `</optgroup>`;
  }
  return html;
}

/* ---------- trading engine (shared by individual / banker clients / advisor plans / short-seller long side) ---------- */

function portfolioHoldingsValue(portfolio) {
  let v = 0;
  for (const [ticker, pos] of Object.entries(portfolio.holdings)) {
    const price = UNIVERSE[ticker] ? UNIVERSE[ticker].price : null;
    if (price != null) v += price * pos.shares;
  }
  return v;
}
function shortLiabilityValue(portfolio) {
  let v = 0;
  for (const [ticker, pos] of Object.entries(portfolio.shorts || {})) {
    const price = UNIVERSE[ticker] ? UNIVERSE[ticker].price : null;
    if (price != null) v += price * pos.shares;
  }
  return v;
}
function portfolioTotalValue(portfolio) {
  let v = portfolio.cash + portfolioHoldingsValue(portfolio);
  if (portfolio.shorts) v -= shortLiabilityValue(portfolio);
  return v;
}

function tradeBuy(portfolio, ticker, qty) {
  const t = UNIVERSE[ticker];
  if (!t || t.price == null) return { ok: false, msg: "No price available for " + ticker + "." };
  qty = Math.floor(Number(qty));
  if (!qty || qty <= 0) return { ok: false, msg: "Enter a quantity of at least 1 share." };
  const cost = t.price * qty;
  if (cost > portfolio.cash + 1e-6) return { ok: false, msg: `Not enough cash — need ${fmtMoney(cost)}, have ${fmtMoney(portfolio.cash)}.` };
  const pos = portfolio.holdings[ticker] || { shares: 0, avgCost: 0 };
  const newShares = pos.shares + qty;
  pos.avgCost = (pos.avgCost * pos.shares + cost) / newShares;
  pos.shares = newShares;
  portfolio.holdings[ticker] = pos;
  portfolio.cash -= cost;
  portfolio.history.unshift({ ts: Date.now(), ticker, side: "BUY", qty, price: t.price });
  return { ok: true };
}
function tradeSell(portfolio, ticker, qty) {
  const t = UNIVERSE[ticker];
  if (!t || t.price == null) return { ok: false, msg: "No price available for " + ticker + "." };
  qty = Math.floor(Number(qty));
  const pos = portfolio.holdings[ticker];
  if (!qty || qty <= 0) return { ok: false, msg: "Enter a quantity of at least 1 share." };
  if (!pos || qty > pos.shares) return { ok: false, msg: `You only hold ${pos ? pos.shares : 0} shares of ${ticker}.` };
  const proceeds = t.price * qty;
  pos.shares -= qty;
  portfolio.cash += proceeds;
  if (pos.shares === 0) delete portfolio.holdings[ticker];
  portfolio.history.unshift({ ts: Date.now(), ticker, side: "SELL", qty, price: t.price });
  return { ok: true };
}

function renderHoldingsTable(portfolio) {
  const rows = Object.entries(portfolio.holdings);
  if (rows.length === 0) return `<p class="empty-note">No open positions yet.</p>`;
  let html = `<table class="data"><thead><tr>
    <th>Ticker</th><th>Shares</th><th>Avg Cost</th><th>Price</th><th>Mkt Value</th><th>P/L $</th><th>P/L %</th>
  </tr></thead><tbody>`;
  for (const [ticker, pos] of rows.sort((a, b) => a[0].localeCompare(b[0]))) {
    const t = UNIVERSE[ticker];
    const price = t ? t.price : null;
    const mktVal = price != null ? price * pos.shares : null;
    const costBasis = pos.avgCost * pos.shares;
    const pl = mktVal != null ? mktVal - costBasis : null;
    const plPct = costBasis > 0 && pl != null ? (pl / costBasis) * 100 : null;
    html += `<tr>
      <td>${ticker}</td>
      <td>${pos.shares}</td>
      <td>${fmtMoney(pos.avgCost)}</td>
      <td>${price != null ? fmtMoney(price) : "—"}</td>
      <td>${mktVal != null ? fmtMoney(mktVal) : "—"}</td>
      <td class="${pnlClass(pl)}">${pl != null ? fmtMoney(pl) : "—"}</td>
      <td class="${pnlClass(plPct)}">${plPct != null ? fmtPct(plPct) : "—"}</td>
    </tr>`;
  }
  html += `</tbody></table>`;
  return html;
}
function renderHistory(portfolio) {
  if (portfolio.history.length === 0) return `<p class="empty-note">No trades yet.</p>`;
  return `<div class="history-list">` + portfolio.history.slice(0, 40).map(h => {
    const d = new Date(h.ts);
    return `<div><span class="${h.side === "BUY" ? "pos" : "neg"}">${h.side}</span> ${h.qty}× ${h.ticker} @ ${fmtMoney(h.price)} &mdash; ${d.toLocaleString()}</div>`;
  }).join("") + `</div>`;
}

/* ---------- market panel: mode toggle, speed, chart, sparklines ---------- */
/* Shared by every mode page -- each page needs live prices regardless of
 * which profession mode it renders. */

function speedPreset() {
  return MarketEngine.SPEED_PRESETS.find(s => s.key === STATE.speedKey) || MarketEngine.SPEED_PRESETS[2];
}
function simDateLabel(world) {
  return new Date(world.createdAt + world.simMs).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function buildIndexChart(world) {
  const points = MarketEngine.indexSeries(world);
  if (points.length < 2) return `<div class="empty-note">Collecting price history&hellip;</div>`;
  const W = 600, H = 150;
  const values = points.map((p) => p.v);
  const minV = Math.min(...values, 100), maxV = Math.max(...values, 100);
  const padV = (maxV - minV) * 0.12 || 2;
  const yMin = minV - padV, yMax = maxV + padV;
  const n = points.length;
  const xAt = (i) => (n === 1 ? 0 : (i / (n - 1)) * W);
  const yAt = (v) => H - ((v - yMin) / (yMax - yMin)) * H;
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${xAt(i).toFixed(2)},${yAt(p.v).toFixed(2)}`).join(" ");
  const baselineY = yAt(100);
  const last = points[n - 1];
  const up = last.v >= points[0].v;
  const color = up ? "var(--pos)" : "var(--neg)";
  const endX = xAt(n - 1), endY = yAt(last.v);

  return `
    <div class="chart-card" id="indexChartWrap" data-w="${W}" data-h="${H}" data-ymin="${yMin}" data-ymax="${yMax}">
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" id="indexSvg">
        <line x1="0" y1="${baselineY.toFixed(2)}" x2="${W}" y2="${baselineY.toFixed(2)}" stroke="var(--border)" stroke-width="1" stroke-dasharray="3,4" />
        <path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        <circle cx="${endX.toFixed(2)}" cy="${endY.toFixed(2)}" r="4" fill="${color}" stroke="var(--surface)" stroke-width="2" />
        <line id="crosshair" x1="0" y1="0" x2="0" y2="${H}" stroke="var(--ink-faint)" stroke-width="1" style="display:none" />
        <circle id="crosshairDot" r="4" fill="var(--ink)" stroke="var(--surface)" stroke-width="2" style="display:none" />
      </svg>
      <div class="chart-endlabel" style="color:${color}">${last.v.toFixed(1)}<span style="color:var(--ink-faint);font-weight:400"> idx</span></div>
      <div class="chart-tooltip" id="chartTooltip" style="display:none"></div>
    </div>`;
}
function wireIndexChartHover(world) {
  const wrap = document.getElementById("indexChartWrap");
  if (!wrap) return;
  const svg = document.getElementById("indexSvg");
  const tooltip = document.getElementById("chartTooltip");
  const crosshair = document.getElementById("crosshair");
  const crosshairDot = document.getElementById("crosshairDot");
  const points = MarketEngine.indexSeries(world);
  const W = Number(wrap.dataset.w), H = Number(wrap.dataset.h);
  const yMin = Number(wrap.dataset.ymin), yMax = Number(wrap.dataset.ymax);
  const n = points.length;
  if (n < 2) return;
  const xAt = (i) => (n === 1 ? 0 : (i / (n - 1)) * W);
  const yAt = (v) => H - ((v - yMin) / (yMax - yMin)) * H;

  svg.addEventListener("mousemove", (ev) => {
    const rect = svg.getBoundingClientRect();
    const relX = ((ev.clientX - rect.left) / rect.width) * W;
    let idx = Math.round((relX / W) * (n - 1));
    idx = Math.max(0, Math.min(n - 1, idx));
    const p = points[idx];
    const x = xAt(idx), y = yAt(p.v);
    crosshair.setAttribute("x1", x); crosshair.setAttribute("x2", x); crosshair.style.display = "";
    crosshairDot.setAttribute("cx", x); crosshairDot.setAttribute("cy", y); crosshairDot.style.display = "";
    const simYears = p.t / MarketEngine.MS_PER_YEAR;
    tooltip.style.display = "";
    tooltip.style.left = `${(ev.clientX - rect.left) + 12}px`;
    tooltip.style.top = `${(ev.clientY - rect.top) - 8}px`;
    tooltip.textContent = `${p.v.toFixed(1)} idx · +${simYears.toFixed(2)}y elapsed`;
  });
  svg.addEventListener("mouseleave", () => {
    crosshair.style.display = "none"; crosshairDot.style.display = "none"; tooltip.style.display = "none";
  });
}

function buildSparklineGrid(world) {
  const list = Object.values(world.tickers).sort((a, b) => a.ticker.localeCompare(b.ticker));
  let html = `<div class="sparkline-grid">`;
  for (const t of list) {
    const hist = t.history.slice(-40);
    const first = hist[0] ? hist[0].p : t.price;
    const chgPct = ((t.price - first) / first) * 100;
    const up = chgPct >= 0;
    const color = up ? "var(--pos)" : "var(--neg)";
    let sparkSvg = "";
    if (hist.length >= 2) {
      const vals = hist.map((h) => h.p);
      const minV = Math.min(...vals), maxV = Math.max(...vals);
      const range = maxV - minV || 1;
      const W = 100, H = 28;
      const pts = hist.map((h, i) => {
        const x = (i / (hist.length - 1)) * W;
        const y = H - ((h.p - minV) / range) * H;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(" ");
      sparkSvg = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>`;
    }
    html += `
      <div class="spark-card" data-ticker="${t.ticker}" title="${t.ticker}: ${fmtMoney(t.price)} (${fmtPct(chgPct)}) — click for profile">
        <div class="spark-top"><span class="spark-ticker">${t.ticker}</span><span class="spark-chg ${pnlClass(chgPct)}">${fmtPct(chgPct)}</span></div>
        ${sparkSvg}
        <div class="spark-price">${fmtMoney(t.price)}</div>
      </div>`;
  }
  html += `</div>`;
  return html;
}

function renderMarketPanel() {
  const el = document.getElementById("marketPanel");
  // Real Companies mode is locked to real time only, so it can never be
  // mistaken for a fast-forwarded prediction/backtest of real securities.
  if (STATE.marketMode === "real" && STATE.speedKey !== "realtime") { STATE.speedKey = "realtime"; saveState(STATE); }
  const world = activeWorld();
  const speed = speedPreset();
  const speedField = STATE.marketMode === "real"
    ? `<div class="field"><label>Speed</label><span class="live-price" style="padding:8px 10px;display:inline-block">Real-Time (fixed)</span></div>`
    : `<div class="field"><label>Speed</label><select id="speedSelect">${MarketEngine.SPEED_PRESETS.map((s) => `<option value="${s.key}" ${s.key === STATE.speedKey ? "selected" : ""}>${s.label}</option>`).join("")}</select></div>`;
  const tickerCount = Object.keys(world.tickers).length;

  el.innerHTML = `
    <div class="market-head">
      <div class="mode-toggle" id="marketModeToggle">
        <button data-market="real" class="${STATE.marketMode === "real" ? "active" : ""}">Real Companies</button>
        <button data-market="super" class="${STATE.marketMode === "super" ? "active" : ""}">Super Simulator</button>
      </div>
      <div class="field-row" style="margin:0">
        ${speedField}
        <button class="action ghost" id="pauseBtn">${STATE.running ? "Pause" : "Resume"}</button>
        ${STATE.marketMode === "super" ? `<button class="action ghost" id="newUniverseBtn">New Fake Universe</button>` : ""}
      </div>
    </div>
    <div class="sim-clock">Sim date: <b>${simDateLabel(world)}</b> &middot; ${tickerCount} companies &middot; ${STATE.running ? "running" : "paused"} at <b>${speed.label}</b></div>
    ${buildIndexChart(world)}
    ${buildSparklineGrid(world)}
    <div class="note" style="margin-top:14px">
      <strong>${STATE.marketMode === "real" ? "Real Companies mode:" : "Super Simulator mode:"}</strong>
      ${STATE.marketMode === "real"
        ? "always runs in real time (no fast-forward) and starts from each company's real Market Scanner snapshot price, but every subsequent price move is generated by a disclosed random-walk model calibrated from that same snapshot's own beta/growth/momentum — <strong>not real market data and not a replay of actual history.</strong> Treat it as a teaching tool, never as a live quote or investment signal."
        : "an entirely fictional universe — fake tickers, names and financials — so you can crank the speed and test ideas with zero connection to any real company."}
    </div>`;

  const speedSelect = document.getElementById("speedSelect");
  if (speedSelect) speedSelect.addEventListener("change", (ev) => {
    STATE.speedKey = ev.target.value; saveState(STATE);
  });
  document.getElementById("pauseBtn").addEventListener("click", () => {
    STATE.running = !STATE.running; saveState(STATE); renderMarketPanel();
  });
  for (const btn of document.querySelectorAll("#marketModeToggle button")) {
    btn.addEventListener("click", () => {
      if (btn.dataset.market === STATE.marketMode) return;
      STATE.marketMode = btn.dataset.market;
      if (STATE.marketMode === "real") STATE.speedKey = "realtime";
      saveState(STATE);
      activeWorld().lastRealMs = Date.now();
      refreshUniverseFromEngine();
      renderMarketPanel();
      if (CURRENT_RENDER) CURRENT_RENDER();
    });
  }
  const newUniverseBtn = document.getElementById("newUniverseBtn");
  if (newUniverseBtn) newUniverseBtn.addEventListener("click", () => {
    if (!confirm("Generate a brand-new fake company universe? This resets all Super Simulator portfolios, clients and plans.")) return;
    ENGINE_SUPER = MarketEngine.createSuperWorld(SUPER_UNIVERSE_SIZE);
    STATE.worlds.super = freshWorldState();
    saveState(STATE); saveEngineState();
    refreshUniverseFromEngine();
    renderMarketPanel();
    if (CURRENT_RENDER) CURRENT_RENDER();
  });

  wireIndexChartHover(world);
  for (const card of document.querySelectorAll(".spark-card")) {
    card.addEventListener("click", () => openCompanyModal(card.dataset.ticker));
  }
}

/* ---------- company profile modal ---------- */

function fmtQuarterLabel(i, total) {
  const fromNow = total - i;
  return fromNow === 1 ? "Most recent quarter" : `${fromNow} quarters ago`;
}

function openCompanyModal(ticker) {
  const world = activeWorld();
  const t = world.tickers[ticker];
  if (!t) return;
  const modal = document.getElementById("companyModal");

  if (world.mode === "real") {
    window.open(`../research/${ticker}/financials.html`, "_blank");
    return;
  }

  const p = t.profile;

  if (t.assetType === "etf" || t.assetType === "mutual_fund") {
    const kindLabel = t.assetType === "etf" ? "Exchange-Traded Fund" : "Mutual Fund";
    const riskPct = Math.round(t.vol * 100);
    modal.innerHTML = `
      <div class="modal-card">
        <button class="modal-close" id="modalCloseBtn">&times;</button>
        <div class="modal-tag">${kindLabel} &middot; Super Simulator (fictional)</div>
        <h3>${t.name} <span class="mono" style="color:var(--ink-faint)">${t.ticker}</span></h3>
        <p class="desc">${p.description}</p>
        <div class="modal-section-title">Snapshot</div>
        <div class="profile-grid">
          <div class="profile-item"><div class="label">Price</div><div class="value">${fmtMoney(t.price)}</div></div>
          <div class="profile-item"><div class="label">Simulated volatility</div><div class="value">~${riskPct}%/yr</div></div>
        </div>
        <div class="note"><strong>Why this isn't a "company":</strong> a fund holds many underlying positions instead of running one business, so it has no revenue, earnings, or headquarters of its own to show here &mdash; its price simply reflects the combined, diversified movement of what it holds. That's also why its simulated volatility is set lower than an individual fake company's.</div>
      </div>`;
    modal.style.display = "flex";
    document.getElementById("modalCloseBtn").addEventListener("click", closeCompanyModal);
    return;
  }

  const quartersRows = (t.quarterlyHistory || []).map((q, i, arr) => `
    <tr>
      <td>${fmtQuarterLabel(i, arr.length)}</td>
      <td>${fmtMoney(q.revenue, { compact: true })}</td>
      <td class="${pnlClass(q.netIncome)}">${fmtMoney(q.netIncome, { compact: true })}</td>
    </tr>`).join("");
  const newsRows = (t.news || []).map((n) => `
    <div class="news-item">
      <div class="news-date">+${(n.t / MarketEngine.MS_PER_YEAR).toFixed(2)}y into the sim</div>
      ${n.headline}
    </div>`).join("");
  const capTierLabel = t.capTier ? `${t.capTier[0].toUpperCase()}${t.capTier.slice(1)}-cap &middot; ` : "";

  modal.innerHTML = `
    <div class="modal-card">
      <button class="modal-close" id="modalCloseBtn">&times;</button>
      <div class="modal-tag">${capTierLabel}${t.sector} &middot; Super Simulator (fictional)</div>
      <h3>${t.name} <span class="mono" style="color:var(--ink-faint)">${t.ticker}</span></h3>
      <p class="desc">${p.description}</p>
      <div class="modal-section-title">Snapshot</div>
      <div class="profile-grid">
        <div class="profile-item"><div class="label">Price</div><div class="value">${fmtMoney(t.price)}</div></div>
        <div class="profile-item"><div class="label">Market cap</div><div class="value">${fmtMoney(t.price * t.shares, { compact: true })}</div></div>
        <div class="profile-item"><div class="label">Annual revenue</div><div class="value">${fmtMoney(t.revenue, { compact: true })}</div></div>
        <div class="profile-item"><div class="label">Net margin</div><div class="value">${t.netMarginPct.toFixed(1)}%</div></div>
        <div class="profile-item"><div class="label">Founded</div><div class="value">${p.founded}</div></div>
        <div class="profile-item"><div class="label">Employees</div><div class="value">${p.employees.toLocaleString()}</div></div>
        <div class="profile-item"><div class="label">Headquarters</div><div class="value">${p.hq}</div></div>
        <div class="profile-item"><div class="label">CEO</div><div class="value">${p.ceo}</div></div>
      </div>
      <div class="modal-section-title">Trailing quarters (backstory)</div>
      <table class="quarters"><thead><tr><th>Quarter</th><th>Revenue</th><th>Net income</th></tr></thead><tbody>${quartersRows}</tbody></table>
      <div class="modal-section-title">News</div>
      ${newsRows || '<p class="empty-note">No news yet &mdash; check back after a sim-quarter or two passes.</p>'}
    </div>`;
  modal.style.display = "flex";
  document.getElementById("modalCloseBtn").addEventListener("click", closeCompanyModal);
}
document.getElementById("companyModal").addEventListener("click", (ev) => {
  if (ev.target.id === "companyModal") closeCompanyModal();
});
function closeCompanyModal() {
  const modal = document.getElementById("companyModal");
  modal.style.display = "none";
  modal.innerHTML = "";
}
document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") closeCompanyModal(); });

/* ---------- tick loop + boot ---------- */

function runTick() {
  const world = activeWorld();
  const speed = speedPreset();
  const now = Date.now();
  if (STATE.running) {
    MarketEngine.tick(world, speed.realMsPerYear, now);
  } else {
    world.lastRealMs = now;
  }
  refreshUniverseFromEngine();
  if (!isEditingForm()) {
    renderMarketPanel();
    if (CURRENT_RENDER) CURRENT_RENDER();
  }
  tickCounter++;
  if (tickCounter % 5 === 0) saveEngineState();
}

function showDisclaimerGateIfNeeded() {
  let ack = false;
  try { ack = localStorage.getItem("simDisclaimerAck.v1") === "1"; } catch (e) {}
  if (ack) return;
  const modal = document.getElementById("disclaimerModal");
  modal.style.display = "flex";
  document.getElementById("disclaimerAckBtn").addEventListener("click", () => {
    try { localStorage.setItem("simDisclaimerAck.v1", "1"); } catch (e) {}
    modal.style.display = "none";
  });
}

// Replaces the old single-page boot(): each mode page has exactly one mode
// section (always visible, no CSS toggling), so this takes that page's mode
// key + render function directly instead of walking a MODES array. Still
// resolves ?mode=<key> for the Guide's existing deep-links (now a no-op
// redirect handled by index.html before this ever runs on the wrong page)
// and keeps simMode.v1 updated as "last mode played" for convenience.
async function bootSimPage(modeKey, renderFn) {
  await runProfileGate();
  renderProfileBar();
  STATE = loadState();

  try {
    SCANNER_DATA = await (await fetch("../data.json")).json();
  } catch (e) {
    document.querySelector(".wrap").insertAdjacentHTML("beforeend", `<p style="color:var(--neg)">Could not load ../data.json — ${e.message}</p>`);
    return;
  }
  RESEARCH = await loadResearch();

  const saved = loadEngineState();
  ENGINE_REAL = (saved && saved.real) || MarketEngine.createRealWorld(SCANNER_DATA);
  ENGINE_SUPER = (saved && saved.super) || MarketEngine.createSuperWorld(SUPER_UNIVERSE_SIZE);
  saveState(STATE);
  saveEngineState();

  CURRENT_MODE = modeKey;
  CURRENT_RENDER = renderFn;
  try { localStorage.setItem("simMode.v1", modeKey); } catch (e) {}

  refreshUniverseFromEngine();
  renderFn();
  renderMarketPanel();

  setInterval(runTick, TICK_INTERVAL_MS);
  window.addEventListener("beforeunload", saveEngineState);
  document.addEventListener("visibilitychange", () => { if (document.hidden) saveEngineState(); });
  showDisclaimerGateIfNeeded();
}
