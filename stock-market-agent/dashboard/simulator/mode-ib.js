/* ---------- mode: Investment Banker (M&A accretion / dilution) ---------- */

function parseMoneyStr(s) {
  if (typeof s !== "string") return null;
  let str = s.trim();
  const neg = str.startsWith("-") || (str.startsWith("(") && str.endsWith(")"));
  str = str.replace(/^-/, "").replace(/^\(|\)$/g, "").replace(/\$/g, "").replace(/,/g, "").trim();
  const m = str.match(/^([0-9]*\.?[0-9]+)\s*([TBMK]?)/i);
  if (!m) return null;
  const num = parseFloat(m[1]);
  if (Number.isNaN(num)) return null;
  const mult = { T: 1e12, B: 1e9, M: 1e6, K: 1e3, "": 1 }[m[2].toUpperCase()] ?? 1;
  const val = num * mult;
  return neg ? -val : val;
}

function ibUsableTickers() {
  const out = [];
  if (STATE.marketMode === "super") {
    for (const t of Object.values(ENGINE_SUPER.tickers)) {
      if (t.netIncome != null && t.shares && t.price) {
        out.push({ ticker: t.ticker, name: t.name, ni: t.netIncome, mktCap: t.shares * t.price, price: t.price });
      }
    }
  } else {
    for (const [ticker, c] of Object.entries(RESEARCH)) {
      if (!c.financials || !c.market) continue;
      const ni = parseMoneyStr(c.financials.net_income);
      const snapshotMktCap = parseMoneyStr(c.market.mktCap);
      const snapshotPrice = c.market.price;
      const liveTicker = ENGINE_REAL.tickers[ticker];
      if (ni === null || snapshotMktCap === null || !snapshotPrice || !liveTicker) continue;
      const shares = snapshotMktCap / snapshotPrice;
      out.push({ ticker, name: c.name || ticker, ni, mktCap: shares * liveTicker.price, price: liveTicker.price });
    }
  }
  return out.sort((a, b) => a.ticker.localeCompare(b.ticker));
}

function computeDeal(acq, tgt, premiumPct, stockPct, synergies, financeRatePct, taxRatePct) {
  const acqShares = acq.mktCap / acq.price;
  const tgtShares = tgt.mktCap / tgt.price;
  const offerPrice = tgt.price * (1 + premiumPct / 100);
  const equityPurchasePrice = offerPrice * tgtShares;
  const stockPortion = equityPurchasePrice * (stockPct / 100);
  const cashPortion = equityPurchasePrice - stockPortion;
  const newShares = stockPortion / acq.price;
  const afterTaxFinanceCost = cashPortion * (financeRatePct / 100) * (1 - taxRatePct / 100);
  const afterTaxSynergies = synergies * (1 - taxRatePct / 100);
  const proFormaNI = acq.ni + tgt.ni + afterTaxSynergies - afterTaxFinanceCost;
  const proFormaShares = acqShares + newShares;
  const standaloneEPS = acq.ni / acqShares;
  const proFormaEPS = proFormaNI / proFormaShares;
  const accretionPct = ((proFormaEPS - standaloneEPS) / Math.abs(standaloneEPS)) * 100;
  return { acqShares, tgtShares, offerPrice, equityPurchasePrice, stockPortion, cashPortion, newShares, proFormaNI, proFormaShares, standaloneEPS, proFormaEPS, accretionPct };
}

function renderIB() {
  const el = document.getElementById("mode-ib");
  const usable = ibUsableTickers();
  if (usable.length < 2) {
    el.innerHTML = `<p class="mode-intro">Not enough companies with complete net income, market cap and price data loaded to run a deal model.</p>`;
    return;
  }
  const opts = usable.map(c => `<option value="${c.ticker}">${c.ticker} — ${c.name}</option>`).join("");
  el.innerHTML = `
    <p class="mode-intro">You're evaluating a merger. Pick an acquirer and a target from companies with usable net income, market cap and price data, set deal terms, and see the simplified pro-forma EPS accretion/(dilution) &mdash; the first-pass math a banker runs before anything gets to a fairness opinion.</p>
    <div class="card">
      <h3>Deal Terms</h3>
      <div class="field-row">
        <div class="field"><label>Acquirer</label><select id="ib-acq">${opts}</select></div>
        <div class="field"><label>Target</label><select id="ib-tgt">${opts}</select></div>
      </div>
      <div class="field-row">
        <div class="field"><label>Premium over target price (%)</label><input type="number" id="ib-premium" value="25" step="1"></div>
        <div class="field"><label>Stock consideration (%)</label><input type="number" id="ib-stock" value="50" min="0" max="100" step="5"></div>
        <div class="field"><label>Annual pre-tax synergies ($)</label><input type="number" id="ib-synergies" value="0" step="1000000"></div>
        <div class="field"><label>Financing rate on cash (%)</label><input type="number" id="ib-rate" value="5" step="0.5"></div>
        <div class="field"><label>Tax rate (%)</label><input type="number" id="ib-tax" value="21" step="1"></div>
        <button class="action primary" id="ib-compute">Run Deal Model</button>
      </div>
      <div id="ib-msg" class="empty-note"></div>
    </div>
    <div id="ib-results"></div>
    <div class="note"><strong>Simplifications:</strong> this ignores purchase-accounting adjustments (goodwill, intangible amortization), real deal fees, actual diluted share counts and control premium negotiation dynamics. Shares outstanding are estimated as market cap &divide; price. It's meant to teach the shape of an accretion/dilution model, not to replace one built on real filings.</div>`;

  document.getElementById("ib-compute").addEventListener("click", () => {
    const acqTicker = document.getElementById("ib-acq").value;
    const tgtTicker = document.getElementById("ib-tgt").value;
    const msgEl = document.getElementById("ib-msg");
    if (acqTicker === tgtTicker) { msgEl.textContent = "Acquirer and target must be different companies."; document.getElementById("ib-results").innerHTML = ""; return; }
    const acq = usable.find(c => c.ticker === acqTicker);
    const tgt = usable.find(c => c.ticker === tgtTicker);
    const premium = Number(document.getElementById("ib-premium").value) || 0;
    const stockPct = Math.min(100, Math.max(0, Number(document.getElementById("ib-stock").value) || 0));
    const synergies = Number(document.getElementById("ib-synergies").value) || 0;
    const rate = Number(document.getElementById("ib-rate").value) || 0;
    const tax = Number(document.getElementById("ib-tax").value) || 0;
    const d = computeDeal(acq, tgt, premium, stockPct, synergies, rate, tax);
    msgEl.textContent = "";
    document.getElementById("ib-results").innerHTML = `
      <div class="card">
        <h3>${acq.ticker} acquires ${tgt.ticker}</h3>
        <div class="stat-grid">
          <div class="stat"><div class="label">Offer price / share</div><div class="value">${fmtMoney(d.offerPrice)}</div></div>
          <div class="stat"><div class="label">Equity purchase price</div><div class="value">${fmtMoney(d.equityPurchasePrice, { compact: true })}</div></div>
          <div class="stat"><div class="label">Cash paid</div><div class="value">${fmtMoney(d.cashPortion, { compact: true })}</div></div>
          <div class="stat"><div class="label">New shares issued</div><div class="value">${(d.newShares / 1e6).toFixed(1)}M</div></div>
          <div class="stat"><div class="label">Standalone ${acq.ticker} EPS</div><div class="value">${fmtMoney(d.standaloneEPS)}</div></div>
          <div class="stat"><div class="label">Pro forma EPS</div><div class="value">${fmtMoney(d.proFormaEPS)}</div></div>
          <div class="stat"><div class="label">Accretion / (Dilution)</div><div class="value ${pnlClass(d.accretionPct)}">${fmtPct(d.accretionPct, 1)}</div></div>
        </div>
        <p style="font-size:13.5px;color:var(--ink-muted);margin-top:10px">In plain terms: the deal is <strong class="${pnlClass(d.accretionPct)}">${d.accretionPct >= 0 ? "accretive" : "dilutive"}</strong> to ${acq.ticker}'s EPS by ${Math.abs(d.accretionPct).toFixed(1)}% in year one under these assumptions &mdash; ${d.accretionPct >= 0 ? "the combined company earns more per share than the acquirer would have alone" : "the combined company earns less per share than the acquirer would have alone, even after synergies"}.</p>
      </div>`;
  });
}
