/* ---------- mode: Individual Investor ---------- */

function renderIndividual() {
  const el = document.getElementById("mode-individual");
  const p = worldState().individual;
  const total = portfolioTotalValue(p);
  const holdVal = portfolioHoldingsValue(p);
  const pl = total - p.startCash;
  const plPct = (pl / p.startCash) * 100;

  el.innerHTML = `
    <p class="mode-intro">You're a retail investor with a single account. Buy and sell shares from the active universe and watch your own P&amp;L.</p>
    <div class="stat-grid">
      <div class="stat"><div class="label">Cash</div><div class="value">${fmtMoney(p.cash)}</div></div>
      <div class="stat"><div class="label">Holdings Value</div><div class="value">${fmtMoney(holdVal)}</div></div>
      <div class="stat"><div class="label">Total Value</div><div class="value">${fmtMoney(total)}</div></div>
      <div class="stat"><div class="label">Total P/L</div><div class="value ${pnlClass(pl)}">${fmtMoney(pl)} (${fmtPct(plPct)})</div></div>
    </div>
    <div class="card">
      <h3>Trade</h3>
      <div class="field-row">
        <div class="field"><label>Ticker</label><select id="ind-ticker">${universeOptions()}</select></div>
        <div class="field"><label>Shares</label><input type="number" id="ind-qty" min="1" value="1"></div>
        <div class="field"><label>&nbsp;</label><span class="live-price" id="ind-price"></span></div>
        <button class="action buy" id="ind-buy">Buy</button>
        <button class="action sell" id="ind-sell">Sell</button>
      </div>
      <div id="ind-msg" class="empty-note"></div>
    </div>
    <div class="card"><h3>Holdings</h3>${renderHoldingsTable(p)}</div>
    <div class="card">
      <h3>Trade History</h3>${renderHistory(p)}
      <div style="margin-top:12px"><button class="action ghost" id="ind-reset">Reset to ${fmtMoney(STARTING_CASH_INDIVIDUAL)}</button></div>
    </div>`;

  const tickerSel = document.getElementById("ind-ticker");
  const updatePrice = () => {
    const t = UNIVERSE[tickerSel.value];
    document.getElementById("ind-price").textContent = t && t.price != null ? "Last: " + fmtMoney(t.price) : "No price data";
  };
  tickerSel.addEventListener("change", updatePrice);
  updatePrice();

  document.getElementById("ind-buy").addEventListener("click", () => {
    const r = tradeBuy(p, tickerSel.value, document.getElementById("ind-qty").value);
    document.getElementById("ind-msg").textContent = r.ok ? "" : r.msg;
    if (r.ok) { saveState(STATE); renderIndividual(); }
  });
  document.getElementById("ind-sell").addEventListener("click", () => {
    const r = tradeSell(p, tickerSel.value, document.getElementById("ind-qty").value);
    document.getElementById("ind-msg").textContent = r.ok ? "" : r.msg;
    if (r.ok) { saveState(STATE); renderIndividual(); }
  });
  document.getElementById("ind-reset").addEventListener("click", () => {
    if (!confirm("Reset your individual portfolio back to " + fmtMoney(STARTING_CASH_INDIVIDUAL) + " cash? This clears all holdings and history.")) return;
    worldState().individual = { cash: STARTING_CASH_INDIVIDUAL, startCash: STARTING_CASH_INDIVIDUAL, holdings: {}, history: [] };
    saveState(STATE); renderIndividual();
  });
}
