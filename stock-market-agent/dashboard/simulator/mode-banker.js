/* ---------- mode: Private Banker ---------- */

function bankerClientList() { return Object.entries(worldState().banker.clients); }

function renderBanker() {
  const el = document.getElementById("mode-banker");
  const clients = bankerClientList();
  const selectedId = el.dataset.selected || (clients[0] ? clients[0][0] : null);
  el.dataset.selected = selectedId || "";

  let summaryRows = "";
  for (const [id, c] of clients) {
    const total = portfolioTotalValue(c);
    const pl = total - c.startCash;
    const plPct = (pl / c.startCash) * 100;
    summaryRows += `<tr>
      <td class="name-cell">${escapeHtml(c.name)}</td><td>${escapeHtml(c.risk)}</td><td>${fmtMoney(c.cash)}</td>
      <td>${fmtMoney(total)}</td><td class="${pnlClass(pl)}">${fmtMoney(pl)}</td><td class="${pnlClass(plPct)}">${fmtPct(plPct)}</td>
    </tr>`;
  }

  const clientOpts = clients.map(([id, c]) => `<option value="${id}" ${id === selectedId ? "selected" : ""}>${escapeHtml(c.name)}</option>`).join("");
  const selected = clients.find(([id]) => id === selectedId);

  el.innerHTML = `
    <p class="mode-intro">You manage several client books at once. Add clients with their own risk profile and starting AUM, then trade inside each one separately.</p>
    <div class="card">
      <h3>Book of Business</h3>
      ${clients.length ? `<table class="data"><thead><tr><th>Client</th><th>Risk Profile</th><th>Cash</th><th>Total AUM</th><th>P/L $</th><th>P/L %</th></tr></thead><tbody>${summaryRows}</tbody></table>` : `<p class="empty-note">No clients yet — add one below.</p>`}
    </div>
    <div class="card">
      <h3>Add Client</h3>
      <div class="field-row">
        <div class="field"><label>Client name</label><input type="text" id="pb-name" placeholder="e.g. Jane Doe" maxlength="60"></div>
        <div class="field"><label>Risk profile</label><select id="pb-risk">
          <option>Conservative</option><option selected>Balanced</option><option>Growth</option><option>Aggressive</option>
        </select></div>
        <div class="field"><label>Starting AUM</label><input type="number" id="pb-aum" min="1000" step="1000" value="${STARTING_CASH_CLIENT}"></div>
        <button class="action primary" id="pb-add">Add Client</button>
      </div>
    </div>
    ${selected ? `
    <div class="card">
      <h3>Trade &mdash; <span id="pb-client-select-wrap"><select id="pb-client-select">${clientOpts}</select></span></h3>
      <div class="field-row">
        <div class="field"><label>Ticker</label><select id="pb-ticker">${universeOptions()}</select></div>
        <div class="field"><label>Shares</label><input type="number" id="pb-qty" min="1" value="1"></div>
        <div class="field"><label>&nbsp;</label><span class="live-price" id="pb-price"></span></div>
        <button class="action buy" id="pb-buy">Buy</button>
        <button class="action sell" id="pb-sell">Sell</button>
        <button class="action ghost" id="pb-remove">Remove Client</button>
      </div>
      <div id="pb-msg" class="empty-note"></div>
    </div>
    <div class="card"><h3>Holdings &mdash; ${escapeHtml(selected[1].name)}</h3>${renderHoldingsTable(selected[1])}</div>
    <div class="card"><h3>Trade History &mdash; ${escapeHtml(selected[1].name)}</h3>${renderHistory(selected[1])}</div>
    ` : ""}`;

  document.getElementById("pb-add").addEventListener("click", () => {
    const name = document.getElementById("pb-name").value.trim();
    const risk = document.getElementById("pb-risk").value;
    const aum = Math.max(1000, Number(document.getElementById("pb-aum").value) || STARTING_CASH_CLIENT);
    if (!name) return;
    const ws = worldState();
    const id = "c" + (ws.banker.nextId++);
    ws.banker.clients[id] = { name, risk, cash: aum, startCash: aum, holdings: {}, history: [] };
    el.dataset.selected = id;
    saveState(STATE); renderBanker();
  });

  if (selected) {
    const [selId, selPortfolio] = selected;
    const clientSelect = document.getElementById("pb-client-select");
    clientSelect.addEventListener("change", () => { el.dataset.selected = clientSelect.value; renderBanker(); });

    const tickerSel = document.getElementById("pb-ticker");
    const updatePrice = () => {
      const t = UNIVERSE[tickerSel.value];
      document.getElementById("pb-price").textContent = t && t.price != null ? "Last: " + fmtMoney(t.price) : "No price data";
    };
    tickerSel.addEventListener("change", updatePrice);
    updatePrice();

    document.getElementById("pb-buy").addEventListener("click", () => {
      const r = tradeBuy(selPortfolio, tickerSel.value, document.getElementById("pb-qty").value);
      document.getElementById("pb-msg").textContent = r.ok ? "" : r.msg;
      if (r.ok) { saveState(STATE); renderBanker(); }
    });
    document.getElementById("pb-sell").addEventListener("click", () => {
      const r = tradeSell(selPortfolio, tickerSel.value, document.getElementById("pb-qty").value);
      document.getElementById("pb-msg").textContent = r.ok ? "" : r.msg;
      if (r.ok) { saveState(STATE); renderBanker(); }
    });
    document.getElementById("pb-remove").addEventListener("click", () => {
      if (!confirm(`Remove client "${selPortfolio.name}"? This deletes their holdings and history.`)) return;
      delete worldState().banker.clients[selId];
      el.dataset.selected = "";
      saveState(STATE); renderBanker();
    });
  }
}
