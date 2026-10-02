/* ---------- mode: Options & Futures Trader ---------- */

const RISK_FREE_RATE = 0.04;
const OPTION_MULTIPLIER = 100; // 1 contract = 100 shares
const FUTURES_MARGIN_RATE = 0.10; // 10% initial margin = 10x notional leverage
const FUTURES_MAINT_RATIO = 0.5; // maintenance margin = 50% of initial margin posted
const OPTION_EXPIRIES = [
  { key: "1m", label: "1 month", years: 1 / 12 },
  { key: "3m", label: "3 months", years: 0.25 },
  { key: "6m", label: "6 months", years: 0.5 },
  { key: "1y", label: "1 year", years: 1 },
];

function erf(x) {
  const sign = x < 0 ? -1 : 1;
  x = Math.abs(x);
  const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741, a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
  const t = 1 / (1 + p * x);
  const y = 1 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
  return sign * y;
}
function normCdf(x) { return 0.5 * (1 + erf(x / Math.SQRT2)); }
function blackScholesPrice(S, K, T, vol, type) {
  if (T <= 1e-6 || vol <= 0) return type === "call" ? Math.max(S - K, 0) : Math.max(K - S, 0);
  const r = RISK_FREE_RATE;
  const d1 = (Math.log(S / K) + (r + 0.5 * vol * vol) * T) / (vol * Math.sqrt(T));
  const d2 = d1 - vol * Math.sqrt(T);
  if (type === "call") return S * normCdf(d1) - K * Math.exp(-r * T) * normCdf(d2);
  return K * Math.exp(-r * T) * normCdf(-d2) - S * normCdf(-d1);
}

function optionMarkValue(opt, world) {
  const t = UNIVERSE[opt.ticker];
  if (!t || t.price == null) return 0;
  const T = Math.max(0, (opt.expirySimMs - world.simMs)) / MarketEngine.MS_PER_YEAR;
  const wt = world.tickers[opt.ticker];
  const vol = (wt && wt.vol) || 0.3;
  const perShare = blackScholesPrice(t.price, opt.strike, T, vol, opt.type);
  return perShare * OPTION_MULTIPLIER * opt.qty;
}
function buyOption(portfolio, world, ticker, type, strike, expiryYears, qty) {
  const t = UNIVERSE[ticker];
  const wt = world.tickers[ticker];
  if (!t || t.price == null || !wt) return { ok: false, msg: "No price/volatility data available for " + ticker + "." };
  qty = Math.floor(Number(qty));
  if (!qty || qty <= 0) return { ok: false, msg: "Enter a quantity of at least 1 contract." };
  strike = Number(strike);
  if (!strike || strike <= 0) return { ok: false, msg: "Enter a valid strike price." };
  const perShare = blackScholesPrice(t.price, strike, expiryYears, wt.vol, type);
  const premium = perShare * OPTION_MULTIPLIER * qty;
  if (premium <= 0) return { ok: false, msg: "This contract is worth essentially nothing (too far out of the money, or too little time left) — pick different terms." };
  if (premium > portfolio.cash + 1e-6) return { ok: false, msg: `Not enough cash — premium is ${fmtMoney(premium)}, have ${fmtMoney(portfolio.cash)}.` };
  portfolio.cash -= premium;
  const id = "opt" + (portfolio.nextOptionId++);
  portfolio.options.push({ id, ticker, type, strike, expirySimMs: world.simMs + expiryYears * MarketEngine.MS_PER_YEAR, qty, premiumPaid: premium });
  portfolio.optionHistory.unshift({ ts: Date.now(), kind: "BUY", ticker, type, strike, qty, premium, pl: null });
  return { ok: true };
}
function closeOption(portfolio, world, id) {
  const idx = portfolio.options.findIndex((o) => o.id === id);
  if (idx < 0) return;
  const opt = portfolio.options[idx];
  const value = optionMarkValue(opt, world);
  portfolio.cash += value;
  portfolio.options.splice(idx, 1);
  portfolio.optionHistory.unshift({ ts: Date.now(), kind: "SELL TO CLOSE", ticker: opt.ticker, type: opt.type, strike: opt.strike, qty: opt.qty, premium: value, pl: value - opt.premiumPaid });
}
function settleExpiredOptions(portfolio, world) {
  const stillOpen = [];
  for (const opt of portfolio.options) {
    if (world.simMs >= opt.expirySimMs) {
      const t = UNIVERSE[opt.ticker];
      const S = t ? t.price : opt.strike;
      const payoutPerShare = opt.type === "call" ? Math.max(S - opt.strike, 0) : Math.max(opt.strike - S, 0);
      const payout = payoutPerShare * OPTION_MULTIPLIER * opt.qty;
      portfolio.cash += payout;
      portfolio.optionHistory.unshift({ ts: Date.now(), kind: "EXPIRED", ticker: opt.ticker, type: opt.type, strike: opt.strike, qty: opt.qty, premium: payout, pl: payout - opt.premiumPaid });
    } else {
      stillOpen.push(opt);
    }
  }
  portfolio.options = stillOpen;
}
function renderOptionPositions(portfolio, world) {
  if (portfolio.options.length === 0) return `<p class="empty-note">No open options positions.</p>`;
  let html = `<table class="data"><thead><tr>
    <th>Ticker</th><th>Type</th><th>Strike</th><th>Expiry</th><th>Contracts</th><th>Premium Paid</th><th>Mark Value</th><th>P/L $</th><th></th>
  </tr></thead><tbody>`;
  for (const opt of portfolio.options) {
    const mark = optionMarkValue(opt, world);
    const pl = mark - opt.premiumPaid;
    const expiryDate = new Date(world.createdAt + opt.expirySimMs).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
    html += `<tr>
      <td>${opt.ticker}</td><td>${opt.type === "call" ? "Call" : "Put"}</td><td>${fmtMoney(opt.strike)}</td>
      <td>${expiryDate}</td><td>${opt.qty}</td><td>${fmtMoney(opt.premiumPaid)}</td>
      <td>${fmtMoney(mark)}</td><td class="${pnlClass(pl)}">${fmtMoney(pl)}</td>
      <td><button class="action ghost opt-close" data-id="${opt.id}" style="padding:4px 10px;font-size:11px">Close</button></td>
    </tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function futureUnrealizedPnl(fut, world) {
  const t = UNIVERSE[fut.ticker];
  if (!t || t.price == null) return 0;
  const dir = fut.side === "long" ? 1 : -1;
  return (t.price - fut.entryPrice) * fut.qty * dir;
}
function openFuture(portfolio, ticker, side, qty) {
  const t = UNIVERSE[ticker];
  if (!t || t.price == null) return { ok: false, msg: "No price available for " + ticker + "." };
  qty = Math.floor(Number(qty));
  if (!qty || qty <= 0) return { ok: false, msg: "Enter a quantity of at least 1 contract." };
  const notional = t.price * qty;
  const margin = notional * FUTURES_MARGIN_RATE;
  if (margin > portfolio.cash + 1e-6) return { ok: false, msg: `Not enough cash for margin — need ${fmtMoney(margin)} (10% of ${fmtMoney(notional)} notional), have ${fmtMoney(portfolio.cash)}.` };
  portfolio.cash -= margin;
  const id = "fut" + (portfolio.nextFutureId++);
  portfolio.futures.push({ id, ticker, side, qty, entryPrice: t.price, marginPosted: margin });
  portfolio.futureHistory.unshift({ ts: Date.now(), kind: "OPEN " + side.toUpperCase(), ticker, qty, price: t.price, pl: null });
  return { ok: true };
}
function closeFuture(portfolio, world, id, auto) {
  const idx = portfolio.futures.findIndex((f) => f.id === id);
  if (idx < 0) return;
  const fut = portfolio.futures[idx];
  const pnl = futureUnrealizedPnl(fut, world);
  const settle = Math.max(0, fut.marginPosted + pnl); // clamp so a sandbox-only slippage edge case can't push cash negative
  portfolio.cash += settle;
  portfolio.futures.splice(idx, 1);
  const t = UNIVERSE[fut.ticker];
  portfolio.futureHistory.unshift({ ts: Date.now(), kind: auto ? "MARGIN CALL — LIQUIDATED" : "CLOSE", ticker: fut.ticker, qty: fut.qty, price: t ? t.price : fut.entryPrice, pl: pnl });
}
function checkFuturesMarginCalls(portfolio, world) {
  const toClose = [];
  for (const fut of portfolio.futures) {
    const pnl = futureUnrealizedPnl(fut, world);
    if (fut.marginPosted + pnl <= fut.marginPosted * FUTURES_MAINT_RATIO) toClose.push(fut.id);
  }
  for (const id of toClose) closeFuture(portfolio, world, id, true);
}
function renderFuturePositions(portfolio, world) {
  if (portfolio.futures.length === 0) return `<p class="empty-note">No open futures positions.</p>`;
  let html = `<table class="data"><thead><tr>
    <th>Ticker</th><th>Side</th><th>Contracts</th><th>Entry</th><th>Price</th><th>Margin</th><th>P/L $</th><th></th>
  </tr></thead><tbody>`;
  for (const fut of portfolio.futures) {
    const t = UNIVERSE[fut.ticker];
    const pnl = futureUnrealizedPnl(fut, world);
    const equity = fut.marginPosted + pnl;
    const warnStyle = equity <= fut.marginPosted * (FUTURES_MAINT_RATIO * 1.25) ? ' style="color:var(--neg)"' : "";
    html += `<tr${warnStyle}>
      <td>${fut.ticker}</td><td>${fut.side === "long" ? "Long" : "Short"}</td><td>${fut.qty}</td>
      <td>${fmtMoney(fut.entryPrice)}</td><td>${t ? fmtMoney(t.price) : "—"}</td>
      <td>${fmtMoney(fut.marginPosted)}</td><td class="${pnlClass(pnl)}">${fmtMoney(pnl)}</td>
      <td><button class="action ghost fut-close" data-id="${fut.id}" style="padding:4px 10px;font-size:11px">Close</button></td>
    </tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function renderDerivatives() {
  const el = document.getElementById("mode-derivatives");
  const world = activeWorld();
  const p = worldState().derivatives;
  settleExpiredOptions(p, world);
  checkFuturesMarginCalls(p, world);

  let optionsMTM = 0;
  for (const o of p.options) optionsMTM += optionMarkValue(o, world);
  let futuresEquity = 0;
  for (const f of p.futures) futuresEquity += f.marginPosted + futureUnrealizedPnl(f, world);
  const total = p.cash + optionsMTM + futuresEquity;
  const pl = total - p.startCash;
  const plPct = (pl / p.startCash) * 100;

  const tickerList = Object.values(UNIVERSE).sort((a, b) => a.ticker.localeCompare(b.ticker));
  const tickerOpts = tickerList.map((t) => `<option value="${t.ticker}">${t.ticker} — ${t.name}</option>`).join("");
  const expiryOpts = OPTION_EXPIRIES.map((e) => `<option value="${e.key}">${e.label}</option>`).join("");
  const firstTicker = tickerList[0];
  const defaultStrike = firstTicker && firstTicker.price != null ? Math.round(firstTicker.price) : "";

  const histRows = [
    ...p.optionHistory.map((h) => ({ ...h, kindGroup: "opt" })),
    ...p.futureHistory.map((h) => ({ ...h, kindGroup: "fut" })),
  ].sort((a, b) => b.ts - a.ts).slice(0, 40);

  el.innerHTML = `
    <p class="mode-intro">You trade derivatives instead of shares: options (the right, not the obligation, to buy/sell at a fixed strike before expiry) and futures (a leveraged bet on a price, marked to market continuously). Both let you control far more exposure than your cash alone &mdash; and both can lose money faster than owning the stock outright.</p>
    <div class="stat-grid">
      <div class="stat"><div class="label">Cash</div><div class="value">${fmtMoney(p.cash)}</div></div>
      <div class="stat"><div class="label">Options Mark Value</div><div class="value">${fmtMoney(optionsMTM)}</div></div>
      <div class="stat"><div class="label">Futures Equity</div><div class="value">${fmtMoney(futuresEquity)}</div></div>
      <div class="stat"><div class="label">Total P/L</div><div class="value ${pnlClass(pl)}">${fmtMoney(pl)} (${fmtPct(plPct)})</div></div>
    </div>

    <div class="card">
      <h3>Buy an Option</h3>
      <div class="field-row">
        <div class="field"><label>Ticker</label><select id="opt-ticker">${tickerOpts}</select></div>
        <div class="field"><label>Type</label><select id="opt-type"><option value="call">Call</option><option value="put">Put</option></select></div>
        <div class="field"><label>Strike</label><input type="number" id="opt-strike" step="0.5" value="${defaultStrike}"></div>
        <div class="field"><label>Expiry</label><select id="opt-expiry">${expiryOpts}</select></div>
        <div class="field"><label>Contracts (&times;100 sh)</label><input type="number" id="opt-qty" min="1" value="1"></div>
      </div>
      <div class="field-row">
        <div class="field"><label>&nbsp;</label><span class="live-price" id="opt-premium"></span></div>
        <button class="action buy" id="opt-buy">Buy to Open</button>
      </div>
      <div id="opt-msg" class="empty-note"></div>
    </div>
    <div class="card"><h3>Open Options Positions</h3>${renderOptionPositions(p, world)}</div>

    <div class="card">
      <h3>Open a Futures Position</h3>
      <div class="field-row">
        <div class="field"><label>Ticker</label><select id="fut-ticker">${tickerOpts}</select></div>
        <div class="field"><label>Side</label><select id="fut-side"><option value="long">Long</option><option value="short">Short</option></select></div>
        <div class="field"><label>Contracts (1 sh each)</label><input type="number" id="fut-qty" min="1" value="10"></div>
        <div class="field"><label>&nbsp;</label><span class="live-price" id="fut-margin"></span></div>
        <button class="action primary" id="fut-open">Open Position</button>
      </div>
      <div id="fut-msg" class="empty-note"></div>
    </div>
    <div class="card"><h3>Open Futures Positions</h3>${renderFuturePositions(p, world)}</div>

    <div class="card">
      <h3>Trade History</h3>
      ${histRows.length === 0 ? `<p class="empty-note">No trades yet.</p>` : `<div class="history-list">${histRows.map((h) => {
        const d = new Date(h.ts);
        const plSpan = h.pl != null ? ` <span class="${pnlClass(h.pl)}">(${fmtMoney(h.pl)})</span>` : "";
        if (h.kindGroup === "opt") return `<div><span class="${h.kind.includes("BUY") ? "" : pnlClass(h.pl)}">${h.kind}</span> ${h.qty}× ${h.ticker} ${h.type} $${h.strike} @ ${fmtMoney(h.premium)}${plSpan} &mdash; ${d.toLocaleString()}</div>`;
        return `<div><span class="${h.kind.includes("OPEN") ? "" : pnlClass(h.pl)}">${h.kind}</span> ${h.qty}× ${h.ticker} @ ${fmtMoney(h.price)}${plSpan} &mdash; ${d.toLocaleString()}</div>`;
      }).join("")}</div>`}
      <div style="margin-top:12px"><button class="action ghost" id="deriv-reset">Reset to ${fmtMoney(STARTING_CASH_INDIVIDUAL)}</button></div>
    </div>
    <div class="note"><strong>Simplifications:</strong> this seat only supports buying options (long calls/puts), not writing/selling them. Premiums use the Black-Scholes model, priced off each company's own simulated annualized volatility and a flat 4% risk-free rate, rather than a live options chain with a bid/ask spread; 1 contract = 100 shares. Futures use a flat 10% initial margin (10&times; leverage) with a simplified maintenance check that auto-liquidates a position once losses erode it to 50% of the margin you posted &mdash; a real margin call gives you a chance to post more cash first.</div>`;

  const optTicker = document.getElementById("opt-ticker");
  const optType = document.getElementById("opt-type");
  const optStrike = document.getElementById("opt-strike");
  const optExpiry = document.getElementById("opt-expiry");
  const optQty = document.getElementById("opt-qty");
  const updateOptPreview = () => {
    const t = UNIVERSE[optTicker.value];
    const wt = world.tickers[optTicker.value];
    if (!t || t.price == null || !wt) { document.getElementById("opt-premium").textContent = "No price data"; return; }
    const exp = OPTION_EXPIRIES.find((e) => e.key === optExpiry.value) || OPTION_EXPIRIES[1];
    const strike = Number(optStrike.value) || t.price;
    const perShare = blackScholesPrice(t.price, strike, exp.years, wt.vol, optType.value);
    document.getElementById("opt-premium").textContent = `Est. premium: ${fmtMoney(perShare * OPTION_MULTIPLIER * (Number(optQty.value) || 1))} (spot ${fmtMoney(t.price)}, vol ${(wt.vol * 100).toFixed(0)}%)`;
  };
  optTicker.addEventListener("change", () => {
    const t = UNIVERSE[optTicker.value];
    if (t && t.price != null) optStrike.value = Math.round(t.price);
    updateOptPreview();
  });
  optType.addEventListener("change", updateOptPreview);
  optExpiry.addEventListener("change", updateOptPreview);
  optStrike.addEventListener("input", updateOptPreview);
  optQty.addEventListener("input", updateOptPreview);
  updateOptPreview();

  document.getElementById("opt-buy").addEventListener("click", () => {
    const exp = OPTION_EXPIRIES.find((e) => e.key === optExpiry.value) || OPTION_EXPIRIES[1];
    const r = buyOption(p, world, optTicker.value, optType.value, optStrike.value, exp.years, optQty.value);
    document.getElementById("opt-msg").textContent = r.ok ? "" : r.msg;
    if (r.ok) { saveState(STATE); renderDerivatives(); }
  });
  for (const btn of document.querySelectorAll(".opt-close")) {
    btn.addEventListener("click", () => { closeOption(p, world, btn.dataset.id); saveState(STATE); renderDerivatives(); });
  }

  const futTicker = document.getElementById("fut-ticker");
  const futQty = document.getElementById("fut-qty");
  const updateFutMargin = () => {
    const t = UNIVERSE[futTicker.value];
    if (!t || t.price == null) { document.getElementById("fut-margin").textContent = "No price data"; return; }
    const notional = t.price * (Number(futQty.value) || 0);
    document.getElementById("fut-margin").textContent = `Notional ${fmtMoney(notional)} · margin required ${fmtMoney(notional * FUTURES_MARGIN_RATE)}`;
  };
  futTicker.addEventListener("change", updateFutMargin);
  futQty.addEventListener("input", updateFutMargin);
  updateFutMargin();
  document.getElementById("fut-open").addEventListener("click", () => {
    const side = document.getElementById("fut-side").value;
    const r = openFuture(p, futTicker.value, side, futQty.value);
    document.getElementById("fut-msg").textContent = r.ok ? "" : r.msg;
    if (r.ok) { saveState(STATE); renderDerivatives(); }
  });
  for (const btn of document.querySelectorAll(".fut-close")) {
    btn.addEventListener("click", () => { closeFuture(p, world, btn.dataset.id, false); saveState(STATE); renderDerivatives(); });
  }

  document.getElementById("deriv-reset").addEventListener("click", () => {
    if (!confirm("Reset your derivatives portfolio back to " + fmtMoney(STARTING_CASH_INDIVIDUAL) + " cash? This clears all options, futures and history.")) return;
    worldState().derivatives = freshDerivativesState();
    saveState(STATE); renderDerivatives();
  });
}
