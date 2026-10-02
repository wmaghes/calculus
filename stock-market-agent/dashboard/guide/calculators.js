/* ---------- Career Guide calculators ----------
 * One small interactive calculator per role that has one (9 of the 13
 * roles), migrated unchanged from the original single-page
 * dashboard/guide/index.html. Each entry describes its input fields and
 * a run(values) function that returns the output HTML; role-page.js
 * renders the field markup and wires the button from this config, keyed
 * by each role's careers.json `calculatorId`.
 */
function fmtUSD(n, decimals) {
  decimals = decimals === undefined ? 0 : decimals;
  const neg = n < 0;
  const out = "$" + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  return (neg ? "-" : "") + out;
}
function pnlSpan(text, isGood) {
  return `<span class="${isGood ? "pos" : "neg"}">${text}</span>`;
}

const CALCULATORS = {
  cg: {
    title: "Try it &mdash; compound growth calculator",
    fields: [
      { id: "cg-initial", label: "Initial amount ($)", type: "number", value: 10000 },
      { id: "cg-monthly", label: "Monthly contribution ($)", type: "number", value: 500 },
      { id: "cg-return", label: "Annual return (%)", type: "number", value: 7, step: 0.5 },
      { id: "cg-years", label: "Years", type: "number", value: 20 },
    ],
    run(v) {
      const initial = Number(v["cg-initial"]) || 0;
      const monthly = Number(v["cg-monthly"]) || 0;
      const annualReturn = (Number(v["cg-return"]) || 0) / 100;
      const years = Math.max(0, Number(v["cg-years"]) || 0);
      const r = annualReturn / 12, n = years * 12;
      const fvLump = initial * Math.pow(1 + r, n);
      const fvAnnuity = r === 0 ? monthly * n : monthly * ((Math.pow(1 + r, n) - 1) / r);
      const fv = fvLump + fvAnnuity;
      const contributed = initial + monthly * n;
      const growth = fv - contributed;
      return `Future value: <b>${fmtUSD(fv)}</b><br>Total contributed: ${fmtUSD(contributed)}<br>Investment growth: ${pnlSpan(fmtUSD(growth), growth >= 0)}`;
    },
  },
  ps: {
    title: "Try it &mdash; position sizing calculator",
    fields: [
      { id: "ps-account", label: "Account size ($)", type: "number", value: 25000 },
      { id: "ps-risk", label: "Risk per trade (%)", type: "number", value: 1, step: 0.25 },
      { id: "ps-entry", label: "Entry price ($)", type: "number", value: 50, step: 0.01 },
      { id: "ps-stop", label: "Stop-loss price ($)", type: "number", value: 47, step: 0.01 },
    ],
    run(v) {
      const account = Number(v["ps-account"]) || 0;
      const riskPct = Number(v["ps-risk"]) || 0;
      const entry = Number(v["ps-entry"]) || 0;
      const stop = Number(v["ps-stop"]) || 0;
      const perShareRisk = Math.abs(entry - stop);
      if (perShareRisk <= 0) return "Entry and stop-loss prices must differ.";
      const riskAmount = account * (riskPct / 100);
      const shares = Math.floor(riskAmount / perShareRisk);
      const positionValue = shares * entry;
      const pctAccount = account > 0 ? (positionValue / account) * 100 : 0;
      return `Max shares: <b>${shares.toLocaleString()}</b><br>Position value: ${fmtUSD(positionValue)} (${pctAccount.toFixed(1)}% of account)<br>Dollars at risk if stopped out: ${fmtUSD(riskAmount)}`;
    },
  },
  pe: {
    title: "Try it &mdash; IRR / MOIC calculator",
    fields: [
      { id: "pe-entry", label: "Entry equity check ($M)", type: "number", value: 100 },
      { id: "pe-exit", label: "Exit equity value ($M)", type: "number", value: 280 },
      { id: "pe-years", label: "Hold period (years)", type: "number", value: 5 },
    ],
    run(v) {
      const entry = Number(v["pe-entry"]) || 0;
      const exit = Number(v["pe-exit"]) || 0;
      const years = Math.max(0.1, Number(v["pe-years"]) || 0.1);
      if (entry <= 0) return "Entry equity must be greater than zero.";
      const moic = exit / entry;
      const irr = Math.pow(moic, 1 / years) - 1;
      return `MOIC: <b>${moic.toFixed(2)}x</b><br>Approx. IRR: ${pnlSpan((irr * 100).toFixed(1) + "%", irr >= 0)} over ${years} years`;
    },
  },
  vc: {
    title: "Try it &mdash; ownership dilution calculator",
    fields: [
      { id: "vc-own", label: "Your current ownership (%)", type: "number", value: 20, step: 0.5 },
      { id: "vc-pre", label: "Pre-money valuation ($M)", type: "number", value: 40 },
      { id: "vc-raise", label: "New round raised ($M)", type: "number", value: 10 },
    ],
    run(v) {
      const ownership = Number(v["vc-own"]) || 0;
      const pre = Number(v["vc-pre"]) || 0;
      const raise = Math.max(0, Number(v["vc-raise"]) || 0);
      const post = pre + raise;
      if (post <= 0) return "Pre-money plus raise must be greater than zero.";
      const dilutionFactor = pre / post;
      const newOwnership = ownership * dilutionFactor;
      const lost = ownership - newOwnership;
      return `Post-money valuation: <b>${fmtUSD(post * 1e6)}</b><br>New ownership: <b>${newOwnership.toFixed(2)}%</b><br>Diluted by: ${pnlSpan(lost.toFixed(2) + " points", false)}`;
    },
  },
  hf: {
    title: "Try it &mdash; Sharpe ratio calculator",
    fields: [
      { id: "hf-return", label: "Portfolio annual return (%)", type: "number", value: 14, step: 0.5 },
      { id: "hf-rf", label: "Risk-free rate (%)", type: "number", value: 4.5, step: 0.1 },
      { id: "hf-vol", label: "Annual volatility (%)", type: "number", value: 18, step: 0.5 },
    ],
    run(v) {
      const ret = Number(v["hf-return"]) || 0;
      const rf = Number(v["hf-rf"]) || 0;
      const vol = Number(v["hf-vol"]) || 0;
      if (vol <= 0) return "Volatility must be greater than zero.";
      const sharpe = (ret - rf) / vol;
      let read = "poor";
      if (sharpe >= 2) read = "excellent";
      else if (sharpe >= 1) read = "good";
      else if (sharpe >= 0) read = "sub-par";
      return `Sharpe ratio: <b>${sharpe.toFixed(2)}</b><br>Rule-of-thumb read: ${pnlSpan(read, sharpe >= 1)} risk-adjusted return`;
    },
  },
  cfo: {
    title: "Try it &mdash; buyback EPS impact calculator",
    fields: [
      { id: "cfo-ni", label: "Net income ($M)", type: "number", value: 500 },
      { id: "cfo-shares", label: "Shares outstanding (M)", type: "number", value: 200 },
      { id: "cfo-buyback", label: "Buyback amount ($M)", type: "number", value: 50 },
      { id: "cfo-price", label: "Buyback price ($/share)", type: "number", value: 25 },
    ],
    run(v) {
      const ni = Number(v["cfo-ni"]) || 0;
      const shares = Number(v["cfo-shares"]) || 0;
      const buyback = Math.max(0, Number(v["cfo-buyback"]) || 0);
      const price = Number(v["cfo-price"]) || 0;
      if (shares <= 0 || price <= 0) return "Shares outstanding and buyback price must be greater than zero.";
      const repurchasedM = buyback / price;
      const newSharesM = Math.max(0.0001, shares - repurchasedM);
      const oldEPS = ni / shares;
      const newEPS = ni / newSharesM;
      const pctChange = ((newEPS - oldEPS) / Math.abs(oldEPS)) * 100;
      return `Shares repurchased: <b>${repurchasedM.toFixed(1)}M</b><br>EPS: ${oldEPS.toFixed(2)} &rarr; <b>${newEPS.toFixed(2)}</b><br>EPS impact: ${pnlSpan((pctChange >= 0 ? "+" : "") + pctChange.toFixed(1) + "%", pctChange >= 0)} (no profit growth needed)`;
    },
  },
  mm: {
    title: "Try it &mdash; spread economics calculator",
    fields: [
      { id: "mm-bid", label: "Bid price ($)", type: "number", value: 49.98, step: 0.01 },
      { id: "mm-ask", label: "Ask price ($)", type: "number", value: 50.02, step: 0.01 },
      { id: "mm-shares", label: "Shares traded / day", type: "number", value: 2000000 },
      { id: "mm-capture", label: "Spread captured (%)", type: "number", value: 50, step: 5 },
    ],
    run(v) {
      const bid = Number(v["mm-bid"]) || 0;
      const ask = Number(v["mm-ask"]) || 0;
      const shares = Number(v["mm-shares"]) || 0;
      const capture = Number(v["mm-capture"]) || 0;
      const spread = ask - bid;
      if (spread <= 0) return "Ask must be higher than bid.";
      const dailyRevenue = shares * spread * (capture / 100);
      return `Spread: <b>${fmtUSD(spread, 4)}</b> per share<br>Estimated daily revenue: <b>${fmtUSD(dailyRevenue)}</b><br>(at ${capture}% of spread captured across ${shares.toLocaleString()} shares/day)`;
    },
  },
  eq: {
    title: "Try it &mdash; comps valuation calculator",
    fields: [
      { id: "eq-ebitda", label: "Company EBITDA ($M)", type: "number", value: 400 },
      { id: "eq-multiple", label: "Peer avg. EV/EBITDA (x)", type: "number", value: 9, step: 0.1 },
      { id: "eq-debt", label: "Net debt ($M)", type: "number", value: 600 },
      { id: "eq-shares", label: "Shares outstanding (M)", type: "number", value: 150 },
    ],
    run(v) {
      const ebitda = Number(v["eq-ebitda"]) || 0;
      const multiple = Number(v["eq-multiple"]) || 0;
      const debt = Number(v["eq-debt"]) || 0;
      const shares = Number(v["eq-shares"]) || 0;
      if (shares <= 0) return "Shares outstanding must be greater than zero.";
      const ev = ebitda * multiple;
      const equityValue = ev - debt;
      const price = equityValue / shares;
      return `Implied enterprise value: <b>${fmtUSD(ev * 1e6)}</b><br>Implied equity value: <b>${fmtUSD(equityValue * 1e6)}</b><br>Implied price/share: <b>${fmtUSD(price, 2)}</b>`;
    },
  },
  risk: {
    title: "Try it &mdash; 1-day Value-at-Risk calculator",
    fields: [
      { id: "risk-value", label: "Portfolio value ($)", type: "number", value: 10000000 },
      { id: "risk-vol", label: "Daily volatility (%)", type: "number", value: 1.5, step: 0.1 },
      { id: "risk-conf", label: "Confidence", type: "select", options: [{ value: "1.65", label: "95%" }, { value: "2.33", label: "99%" }] },
    ],
    run(v) {
      const value = Number(v["risk-value"]) || 0;
      const vol = Number(v["risk-vol"]) || 0;
      const z = Number(v["risk-conf"]) || 1.65;
      const varAmount = value * (vol / 100) * z;
      return `1-day Value-at-Risk: <b>${fmtUSD(varAmount)}</b><br>Interpretation: on a typical day, losses shouldn't exceed this &mdash; but the confidence level means it still will, some of the time.`;
    },
  },
};

// Renders a <div class="calc"> block for the given calculatorId into
// mountEl (appended at the end), and wires its button.
function renderCalculator(mountEl, calculatorId) {
  const cfg = CALCULATORS[calculatorId];
  if (!cfg) return;
  const div = document.createElement("div");
  div.className = "calc";
  const fieldsHtml = cfg.fields.map((f) => {
    if (f.type === "select") {
      const opts = f.options.map((o) => `<option value="${o.value}">${o.label}</option>`).join("");
      return `<div class="calc-field"><label>${f.label}</label><select id="${f.id}">${opts}</select></div>`;
    }
    return `<div class="calc-field"><label>${f.label}</label><input type="number" id="${f.id}" value="${f.value}"${f.step ? ` step="${f.step}"` : ""}></div>`;
  }).join("");
  div.innerHTML = `
    <h4>${cfg.title}</h4>
    <div class="calc-row">${fieldsHtml}<button class="calc-btn" id="${calculatorId}-calc-btn">Calculate</button></div>
    <div class="calc-out" id="${calculatorId}-calc-out"></div>`;
  mountEl.appendChild(div);
  div.querySelector(`#${calculatorId}-calc-btn`).addEventListener("click", () => {
    const values = {};
    cfg.fields.forEach((f) => { values[f.id] = document.getElementById(f.id).value; });
    document.getElementById(`${calculatorId}-calc-out`).innerHTML = cfg.run(values);
  });
}
