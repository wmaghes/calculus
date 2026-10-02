/*
 * Shared renderer for the 5 Scanner desk pages. Each page sets
 * window.SCANNER_CATEGORY to one of growth/stability/nextgen/shorts/funds
 * before loading this script, then this script fetches ../data.json and
 * renders just that one category's rows plus its own filter bar.
 */
const ICONS = {
  trendUp: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3,17 9,11 13,15 21,7"/><polyline points="14,7 21,7 21,14"/></svg>',
  trendDown: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3,7 9,13 13,9 21,17"/><polyline points="14,17 21,17 21,10"/></svg>',
  shield: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 L19 5 V11 C19 16 15.5 19.5 12 21 C8.5 19.5 5 16 5 11 V5 Z"/></svg>',
  sparkle: '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2 L13.5 9.5 L21 11 L13.5 12.5 L12 20 L10.5 12.5 L3 11 L10.5 9.5 Z"/></svg>',
  basket: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5"/></svg>',
};

const CATEGORY_META = {
  growth:    { title: "Biggest Growth", color: "var(--growth)", soft: "var(--growth-soft)", icon: ICONS.trendUp,
               sub: "Large/mid-cap names posting the fastest revenue growth or price momentum right now. Ranked by conviction tier, not a blended score — see disclaimer above." },
  stability: { title: "Stability", color: "var(--stability)", soft: "var(--stability-soft)", icon: ICONS.shield,
               sub: "Low-beta, dividend-consistent names built to hold up when growth stocks wobble. Score blends low beta (60%) and dividend yield (40%)." },
  nextgen:   { title: "Next-Gen Growth", color: "var(--nextgen)", soft: "var(--nextgen-soft)", icon: ICONS.sparkle,
               sub: "Smaller, thematic bets — quantum computing, AI infrastructure, gene editing, space — with outsized upside and outsized risk. Ranked by conviction tier." },
  shorts:    { title: "Short Candidates", color: "var(--short)", soft: "var(--short-soft)", icon: ICONS.trendDown,
               sub: "Highest short interest and clearest negative catalysts (guidance cuts, structural decline). Score is a normalized blend of short-%-of-float plus momentum/valuation flags." },
  funds:     { title: "Funds & Company Size", color: "var(--funds)", soft: "var(--funds-soft)", icon: ICONS.basket,
               sub: "A deliberately small, mixed set — broad-market and bond ETFs, mutual funds, and individual small/mid-cap stocks — sorted from lowest to highest risk so the diversification effect is visible at a glance. The “Risk” dots below use the same 1–5 scale as conviction elsewhere, just relabeled: more dots means more volatility, not more upside." },
};

function fmtPrice(p) {
  if (p === null || p === undefined) return null;
  return "$" + Number(p).toFixed(2);
}

function renderRow(item, catKey) {
  const meta = CATEGORY_META[catKey];
  const priceStr = fmtPrice(item.price);
  const chgVal = item.momentum ?? null;
  let chgHtml = "";
  if (typeof chgVal === "number") {
    const cls = chgVal >= 0 ? "pos" : "neg";
    chgHtml = `<span class="price-chg ${cls}">${chgVal >= 0 ? "+" : ""}${chgVal.toFixed(1)}%</span>`;
  }

  const metaBits = [];
  if (priceStr) metaBits.push(priceStr);
  if (item.mktCap) metaBits.push(item.mktCap);
  if (item.metric_label) {
    const isRatio = /beta/i.test(item.metric_label);
    const val = typeof item.metric === "number" ? (Number.isInteger(item.metric) ? item.metric : item.metric.toFixed(isRatio ? 2 : 1)) : item.metric;
    metaBits.push(`${item.metric_label}: <span class="metric-val">${val}${typeof item.metric === "number" && !isRatio ? "%" : ""}</span>`);
  }
  if (item.divYield) metaBits.push(`Yield: <span class="metric-val">${item.divYield}%</span>`);
  if (item.streak) metaBits.push(`Streak: <span class="metric-val">${item.streak}</span>`);
  if (item.theme) metaBits.push(item.theme);
  if (item.flag) metaBits.push(`<span class="metric-val">${item.flag}</span>`);
  if (item.expenseRatio != null) metaBits.push(`Expense ratio: <span class="metric-val">${item.expenseRatio}%</span>`);
  if (item.assetType === "etf") metaBits.push(`<span class="metric-val">ETF</span>`);
  if (item.assetType === "mutual_fund") metaBits.push(`<span class="metric-val">Mutual Fund</span>`);
  if (item.capTier) metaBits.push(`<span class="metric-val">${item.capTier[0].toUpperCase()}${item.capTier.slice(1)}-Cap</span>`);
  if (item.sector) metaBits.push(item.sector + (item.industry ? ` / ${item.industry}` : ""));
  if (item.fortune100) metaBits.push(`<span class="f100-badge">FORTUNE 100${item.fortune100Rank ? " #" + item.fortune100Rank : ""}</span>`);

  let gaugeHtml = "";
  if (typeof item.score === "number") {
    gaugeHtml = `
      <div class="gauge">
        <div class="score-num">${item.score.toFixed(0)}<span style="color:var(--ink-faint);font-weight:400"> /100</span></div>
        <div class="bar-track"><div class="bar-fill" style="width:${item.score}%; background:${meta.color}"></div></div>
      </div>`;
  } else if (typeof item.conviction === "number") {
    let dots = "";
    for (let i = 1; i <= 5; i++) {
      dots += `<div class="dot ${i <= item.conviction ? "on" : ""}" style="--dotcolor:${meta.color}"></div>`;
    }
    gaugeHtml = `
      <div class="gauge">
        <span class="rating-pill" style="background:${meta.soft}; color:${meta.color}">${item.rating || "conviction"}</span>
        <div class="dots">${dots}</div>
      </div>`;
  }

  return `
    <div class="row">
      <div class="id">
        <a class="ticker" href="../research/${item.ticker}/market.html">${item.ticker}</a>
        <div class="company">${item.name || ""}</div>
      </div>
      <div class="mid">
        <p class="blurb">${item.blurb || ""}</p>
        <div class="metaline">${metaBits.map(b => `<span>${b}</span>`).join("")}${chgHtml ? `<span>${chgHtml}</span>` : ""}</div>
      </div>
      ${gaugeHtml}
    </div>`;
}

const CAT_KEY = window.SCANNER_CATEGORY;
let DATA = null;
const FILTER = { text: "", sector: "", capTier: "", f100Only: false, themes: new Set() };

function itemMatchesFilter(item) {
  if (FILTER.f100Only && !item.fortune100) return false;
  if (FILTER.sector && item.sector !== FILTER.sector) return false;
  if (FILTER.capTier && item.capTier !== FILTER.capTier) return false;
  if (FILTER.themes.size > 0 && !FILTER.themes.has(item.theme)) return false;
  if (FILTER.text) {
    const haystack = [item.ticker, item.name, item.sector, item.industry, item.theme]
      .filter(Boolean).join(" ").toLowerCase();
    if (!haystack.includes(FILTER.text)) return false;
  }
  return true;
}

function renderAll() {
  const meta = CATEGORY_META[CAT_KEY];
  const all = (DATA.categories[CAT_KEY] || []);
  const filtered = all.filter(itemMatchesFilter);
  const rows = filtered.length
    ? filtered.map(item => renderRow(item, CAT_KEY)).join("")
    : `<p class="empty-cat">No companies in this desk match the current filters.</p>`;
  const countLabel = filtered.length === all.length ? `${all.length} names` : `${filtered.length} of ${all.length} names`;

  document.getElementById("category").innerHTML = `
    <div class="cat-head">
      <span class="count">${countLabel}</span>
    </div>
    <p class="cat-sub">${meta.sub}</p>
    <div class="rows">${rows}</div>`;

  const anyFilterActive = FILTER.text || FILTER.sector || FILTER.capTier || FILTER.f100Only || FILTER.themes.size > 0;
  document.getElementById("filterSummary").textContent = anyFilterActive
    ? `Showing ${filtered.length} of ${all.length} names in this desk`
    : "";
}

function wireFilterBar() {
  const searchInput = document.getElementById("searchInput");
  const sectorSelect = document.getElementById("sectorSelect");
  const capTierSelect = document.getElementById("capTierSelect");
  const f100Toggle = document.getElementById("f100Toggle");
  const clearBtn = document.getElementById("clearFiltersBtn");
  const themeChipsEl = document.getElementById("themeChips");

  const items = DATA.categories[CAT_KEY] || [];
  const sectors = Array.from(new Set(items.map(i => i.sector).filter(Boolean))).sort();
  sectorSelect.innerHTML = `<option value="">All sectors</option>` + sectors.map(s => `<option value="${s}">${s}</option>`).join("");

  const themes = Array.from(new Set(items.map(i => i.theme).filter(Boolean))).sort();
  themeChipsEl.innerHTML = themes.map(t => `<button type="button" class="theme-chip" data-theme="${t}">${t}</button>`).join("");
  themeChipsEl.hidden = themes.length === 0;

  const f100Count = items.filter(i => i.fortune100).length;
  const f100CountEl = document.getElementById("f100CountLabel");
  if (f100CountEl) f100CountEl.textContent = f100Count;

  searchInput.addEventListener("input", () => {
    FILTER.text = searchInput.value.trim().toLowerCase();
    renderAll();
  });
  sectorSelect.addEventListener("change", () => {
    FILTER.sector = sectorSelect.value;
    renderAll();
  });
  capTierSelect.addEventListener("change", () => {
    FILTER.capTier = capTierSelect.value;
    renderAll();
  });
  f100Toggle.addEventListener("click", () => {
    FILTER.f100Only = !FILTER.f100Only;
    f100Toggle.classList.toggle("active", FILTER.f100Only);
    renderAll();
  });
  themeChipsEl.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".theme-chip");
    if (!btn) return;
    const t = btn.dataset.theme;
    if (FILTER.themes.has(t)) FILTER.themes.delete(t); else FILTER.themes.add(t);
    btn.classList.toggle("active", FILTER.themes.has(t));
    renderAll();
  });
  clearBtn.addEventListener("click", () => {
    FILTER.text = ""; FILTER.sector = ""; FILTER.capTier = ""; FILTER.f100Only = false; FILTER.themes.clear();
    searchInput.value = ""; sectorSelect.value = ""; capTierSelect.value = "";
    f100Toggle.classList.remove("active");
    themeChipsEl.querySelectorAll(".theme-chip").forEach(b => b.classList.remove("active"));
    renderAll();
  });
}

async function boot() {
  const meta = CATEGORY_META[CAT_KEY];
  document.getElementById("deskIcon").innerHTML = meta.icon;
  document.getElementById("deskIcon").style.color = meta.color;
  document.getElementById("deskTitle").textContent = meta.title;

  try {
    const res = await fetch("../data.json");
    DATA = await res.json();
  } catch (e) {
    document.getElementById("category").innerHTML =
      `<p style="color:var(--neg)">Could not load data.json — ${e.message}</p>`;
    return;
  }

  document.getElementById("genTime").textContent = DATA.generated || "—";
  const count = (DATA.categories[CAT_KEY] || []).length;
  document.getElementById("deskCount").textContent = count;

  wireFilterBar();
  renderAll();
}

boot();
