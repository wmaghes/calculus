/* ---------- mode: Short Selling / Buy-Side Investor ---------- */

const SHORT_INITIAL_MARGIN = 0.5; // flat 50% of notional must be available as buying power to open a short (simplified Reg T)
const SHORT_BORROW_FEE_ANNUAL = 0.04; // flat 4%/yr cost to borrow the shares, accrued continuously in sim time

function openShort(portfolio, ticker, qty) {
  const t = UNIVERSE[ticker];
  if (!t || t.price == null) return { ok: false, msg: "No price available for " + ticker + "." };
  qty = Math.floor(Number(qty));
  if (!qty || qty <= 0) return { ok: false, msg: "Enter a quantity of at least 1 share." };
  const notional = t.price * qty;
  const requiredMargin = notional * SHORT_INITIAL_MARGIN;
  if (requiredMargin > portfolio.cash + 1e-6) return { ok: false, msg: `Not enough buying power — shorting ${qty} ${ticker} needs ${fmtMoney(requiredMargin)} in margin (50% of ${fmtMoney(notional)} notional), have ${fmtMoney(portfolio.cash)}.` };
  const pos = portfolio.shorts[ticker] || { shares: 0, avgPrice: 0, lastAccrualSimMs: null };
  const newShares = pos.shares + qty;
  pos.avgPrice = (pos.avgPrice * pos.shares + t.price * qty) / newShares;
  pos.shares = newShares;
  portfolio.shorts[ticker] = pos;
  portfolio.cash += notional; // proceeds from selling the borrowed shares
  portfolio.history.unshift({ ts: Date.now(), ticker, side: "SHORT", qty, price: t.price });
  return { ok: true };
}
function coverShort(portfolio, ticker, qty) {
  const t = UNIVERSE[ticker];
  if (!t || t.price == null) return { ok: false, msg: "No price available for " + ticker + "." };
  qty = Math.floor(Number(qty));
  const pos = portfolio.shorts[ticker];
  if (!qty || qty <= 0) return { ok: false, msg: "Enter a quantity of at least 1 share." };
  if (!pos || qty > pos.shares) return { ok: false, msg: `You only have ${pos ? pos.shares : 0} shares short of ${ticker}.` };
  const cost = t.price * qty;
  if (cost > portfolio.cash + 1e-6) return { ok: false, msg: `Not enough cash to cover — need ${fmtMoney(cost)}, have ${fmtMoney(portfolio.cash)}.` };
  pos.shares -= qty;
  portfolio.cash -= cost;
  if (pos.shares === 0) delete portfolio.shorts[ticker];
  portfolio.history.unshift({ ts: Date.now(), ticker, side: "COVER", qty, price: t.price });
  return { ok: true };
}
function accrueShortBorrowFees(portfolio, world) {
  for (const pos of Object.values(portfolio.shorts || {})) {
    if (pos.lastAccrualSimMs == null) { pos.lastAccrualSimMs = world.simMs; continue; }
    const dtYears = Math.max(0, world.simMs - pos.lastAccrualSimMs) / MarketEngine.MS_PER_YEAR;
    if (dtYears <= 0) continue;
    const fee = pos.avgPrice * pos.shares * SHORT_BORROW_FEE_ANNUAL * dtYears;
    portfolio.cash -= fee;
    pos.lastAccrualSimMs = world.simMs;
  }
}
function renderShortPositions(portfolio) {
  const rows = Object.entries(portfolio.shorts || {});
  if (rows.length === 0) return `<p class="empty-note">No open short positions.</p>`;
  let html = `<table class="data"><thead><tr>
    <th>Ticker</th><th>Shares Short</th><th>Avg Short Price</th><th>Price</th><th>Liability</th><th>P/L $</th><th>P/L %</th>
  </tr></thead><tbody>`;
  for (const [ticker, pos] of rows.sort((a, b) => a[0].localeCompare(b[0]))) {
    const t = UNIVERSE[ticker];
    const price = t ? t.price : null;
    const liab = price != null ? price * pos.shares : null;
    const proceeds = pos.avgPrice * pos.shares;
    const pl = liab != null ? proceeds - liab : null;
    const plPct = proceeds > 0 && pl != null ? (pl / proceeds) * 100 : null;
    html += `<tr>
      <td>${ticker}</td>
      <td>${pos.shares}</td>
      <td>${fmtMoney(pos.avgPrice)}</td>
      <td>${price != null ? fmtMoney(price) : "—"}</td>
      <td>${liab != null ? fmtMoney(liab) : "—"}</td>
      <td class="${pnlClass(pl)}">${pl != null ? fmtMoney(pl) : "—"}</td>
      <td class="${pnlClass(plPct)}">${plPct != null ? fmtPct(plPct) : "—"}</td>
    </tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function renderShortSeller() {
  const el = document.getElementById("mode-shortseller");
  const world = activeWorld();
  const p = worldState().shortseller;
  accrueShortBorrowFees(p, world);
  const total = portfolioTotalValue(p);
  const longVal = portfolioHoldingsValue(p);
  const shortLiab = shortLiabilityValue(p);
  const pl = total - p.startCash;
  const plPct = (pl / p.startCash) * 100;
  const candidates = Object.values(UNIVERSE).filter((t) => t.category === "shorts").sort((a, b) => a.ticker.localeCompare(b.ticker));

  el.innerHTML = `
    <p class="mode-intro">You run a long/short book: buy names you believe in, and short sell names you expect to fall &mdash; borrowing shares to sell now, aiming to buy them back cheaper later. Shorting requires margin and costs an ongoing borrow fee; losses on a short are theoretically unlimited since a price can rise without limit, so this seat teaches that risk directly.</p>
    <div class="stat-grid">
      <div class="stat"><div class="label">Cash</div><div class="value">${fmtMoney(p.cash)}</div></div>
      <div class="stat"><div class="label">Long Value</div><div class="value">${fmtMoney(longVal)}</div></div>
      <div class="stat"><div class="label">Short Liability</div><div class="value">${fmtMoney(shortLiab)}</div></div>
      <div class="stat"><div class="label">Total P/L</div><div class="value ${pnlClass(pl)}">${fmtMoney(pl)} (${fmtPct(plPct)})</div></div>
    </div>
    <div class="card">
      <h3>Go Long</h3>
      <div class="field-row">
        <div class="field"><label>Ticker</label><select id="ss-long-ticker">${universeOptions()}</select></div>
        <div class="field"><label>Shares</label><input type="number" id="ss-long-qty" min="1" value="1"></div>
        <div class="field"><label>&nbsp;</label><span class="live-price" id="ss-long-price"></span></div>
        <button class="action buy" id="ss-long-buy">Buy</button>
        <button class="action sell" id="ss-long-sell">Sell</button>
      </div>
      <div id="ss-long-msg" class="empty-note"></div>
    </div>
    <div class="card">
      <h3>Short Sell</h3>
      ${candidates.length ? `<div class="note" style="margin-top:0"><strong>Short-interest candidates from the Market Scanner's Shorts desk:</strong> ${candidates.map((c) => c.ticker).join(", ")}.</div>` : ""}
      <div class="field-row">
        <div class="field"><label>Ticker</label><select id="ss-short-ticker">${universeOptions()}</select></div>
        <div class="field"><label>Shares</label><input type="number" id="ss-short-qty" min="1" value="1"></div>
        <div class="field"><label>&nbsp;</label><span class="live-price" id="ss-short-price"></span></div>
        <button class="action sell" id="ss-open-short">Short Sell</button>
        <button class="action buy" id="ss-cover">Buy to Cover</button>
      </div>
      <div id="ss-short-msg" class="empty-note"></div>
    </div>
    <div class="card"><h3>Long Holdings</h3>${renderHoldingsTable(p)}</div>
    <div class="card"><h3>Short Positions</h3>${renderShortPositions(p)}</div>
    <div class="card">
      <h3>Trade History</h3>${renderHistory(p)}
      <div style="margin-top:12px"><button class="action ghost" id="ss-reset">Reset to ${fmtMoney(STARTING_CASH_INDIVIDUAL)}</button></div>
    </div>
    <div class="note"><strong>Simplifications:</strong> initial margin to open a short is a flat 50% of notional, checked against available cash rather than a separate segregated margin account; borrowing costs a flat 4%/year on the short's notional, accrued continuously in sim time and deducted from cash. There's no forced buy-in if a short runs deeply against you &mdash; in a real margin account, a sharp enough adverse move can trigger one.</div>`;

  const longTickerSel = document.getElementById("ss-long-ticker");
  const updateLongPrice = () => {
    const t = UNIVERSE[longTickerSel.value];
    document.getElementById("ss-long-price").textContent = t && t.price != null ? "Last: " + fmtMoney(t.price) : "No price data";
  };
  longTickerSel.addEventListener("change", updateLongPrice);
  updateLongPrice();
  document.getElementById("ss-long-buy").addEventListener("click", () => {
    const r = tradeBuy(p, longTickerSel.value, document.getElementById("ss-long-qty").value);
    document.getElementById("ss-long-msg").textContent = r.ok ? "" : r.msg;
    if (r.ok) { saveState(STATE); renderShortSeller(); }
  });
  document.getElementById("ss-long-sell").addEventListener("click", () => {
    const r = tradeSell(p, longTickerSel.value, document.getElementById("ss-long-qty").value);
    document.getElementById("ss-long-msg").textContent = r.ok ? "" : r.msg;
    if (r.ok) { saveState(STATE); renderShortSeller(); }
  });

  const shortTickerSel = document.getElementById("ss-short-ticker");
  const updateShortPrice = () => {
    const t = UNIVERSE[shortTickerSel.value];
    document.getElementById("ss-short-price").textContent = t && t.price != null ? "Last: " + fmtMoney(t.price) : "No price data";
  };
  shortTickerSel.addEventListener("change", updateShortPrice);
  updateShortPrice();
  document.getElementById("ss-open-short").addEventListener("click", () => {
    const r = openShort(p, shortTickerSel.value, document.getElementById("ss-short-qty").value);
    document.getElementById("ss-short-msg").textContent = r.ok ? "" : r.msg;
    if (r.ok) { saveState(STATE); renderShortSeller(); }
  });
  document.getElementById("ss-cover").addEventListener("click", () => {
    const r = coverShort(p, shortTickerSel.value, document.getElementById("ss-short-qty").value);
    document.getElementById("ss-short-msg").textContent = r.ok ? "" : r.msg;
    if (r.ok) { saveState(STATE); renderShortSeller(); }
  });
  document.getElementById("ss-reset").addEventListener("click", () => {
    if (!confirm("Reset your long/short portfolio back to " + fmtMoney(STARTING_CASH_INDIVIDUAL) + " cash? This clears all holdings, shorts and history.")) return;
    worldState().shortseller = freshShortSellerState();
    saveState(STATE); renderShortSeller();
  });
}
