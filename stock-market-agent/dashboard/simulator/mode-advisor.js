/* ---------- mode: Financial Advisor ---------- */

const RISK_TIERS = {
  Conservative: { assumedReturn: 0.05, allocation: { stability: 60, growth: 10, nextgen: 0, cash: 30 } },
  Balanced:     { assumedReturn: 0.07, allocation: { stability: 40, growth: 30, nextgen: 10, cash: 20 } },
  Growth:       { assumedReturn: 0.09, allocation: { stability: 20, growth: 45, nextgen: 25, cash: 10 } },
  Aggressive:   { assumedReturn: 0.11, allocation: { stability: 5,  growth: 45, nextgen: 45, cash: 5 } },
};

function projectedFutureValue(lumpSum, monthly, years, annualReturn) {
  const r = annualReturn / 12;
  const n = years * 12;
  const fvLump = lumpSum * Math.pow(1 + r, n);
  const fvAnnuity = r === 0 ? monthly * n : monthly * ((Math.pow(1 + r, n) - 1) / r);
  return fvLump + fvAnnuity;
}

function fundPlan(plan) {
  // one-time deployment of the lump sum, split across tickers in each allocation bucket, whole shares only
  const byCat = { growth: [], stability: [], nextgen: [] };
  for (const t of Object.values(UNIVERSE)) if (byCat[t.category]) byCat[t.category].push(t);
  for (const [cat, pct] of Object.entries(plan.allocation)) {
    if (cat === "cash" || pct <= 0) continue;
    const names = byCat[cat] || [];
    if (names.length === 0) continue;
    const budget = plan.lumpSum * (pct / 100);
    const perName = budget / names.length;
    for (const t of names) {
      if (t.price == null || t.price <= 0) continue;
      const qty = Math.floor(perName / t.price);
      if (qty > 0) tradeBuy(plan, t.ticker, qty);
    }
  }
  plan.funded = true;
}
function investContribution(plan) {
  const amount = plan.monthly;
  if (amount <= 0) return;
  plan.cash += amount;
  const byCat = { growth: [], stability: [], nextgen: [] };
  for (const t of Object.values(UNIVERSE)) if (byCat[t.category]) byCat[t.category].push(t);
  for (const [cat, pct] of Object.entries(plan.allocation)) {
    if (cat === "cash" || pct <= 0) continue;
    const names = byCat[cat] || [];
    if (names.length === 0) continue;
    const budget = amount * (pct / 100);
    const perName = budget / names.length;
    for (const t of names) {
      if (t.price == null || t.price <= 0 || perName > plan.cash) continue;
      const qty = Math.floor(perName / t.price);
      if (qty > 0) tradeBuy(plan, t.ticker, qty);
    }
  }
  plan.monthsContributed = (plan.monthsContributed || 0) + 1;
}

function renderAdvisor() {
  const el = document.getElementById("mode-advisor");
  const plans = Object.entries(worldState().advisor.plans);
  const selectedId = el.dataset.selected || (plans[0] ? plans[0][0] : null);
  el.dataset.selected = selectedId || "";

  let rows = "";
  for (const [id, plan] of plans) {
    const fv = projectedFutureValue(plan.lumpSum, plan.monthly, plan.years, RISK_TIERS[plan.risk].assumedReturn);
    const actual = plan.funded ? portfolioTotalValue(plan) : null;
    rows += `<tr>
      <td class="name-cell">${escapeHtml(plan.name)}</td><td>${escapeHtml(plan.risk)}</td><td>${fmtMoney(plan.target)}</td><td>${plan.years}y</td>
      <td>${fmtMoney(fv, { compact: true })}</td><td>${actual != null ? fmtMoney(actual, { compact: true }) : "not funded"}</td>
    </tr>`;
  }

  const planOpts = plans.map(([id, p]) => `<option value="${id}" ${id === selectedId ? "selected" : ""}>${escapeHtml(p.name)}</option>`).join("");
  const selected = plans.find(([id]) => id === selectedId);

  el.innerHTML = `
    <p class="mode-intro">You build goal-based plans for clients: a target dollar amount, a time horizon and a risk tolerance map to a suggested asset mix. Fund a plan to actually simulate it against the active universe and compare to the projection.</p>
    <div class="card">
      <h3>Plans</h3>
      ${plans.length ? `<table class="data"><thead><tr><th>Client / Goal</th><th>Risk</th><th>Target</th><th>Horizon</th><th>Projected FV</th><th>Actual Sim Value</th></tr></thead><tbody>${rows}</tbody></table>` : `<p class="empty-note">No plans yet — create one below.</p>`}
    </div>
    <div class="card">
      <h3>New Plan</h3>
      <div class="field-row">
        <div class="field"><label>Client / goal name</label><input type="text" id="adv-name" placeholder="e.g. Retirement — the Smiths" maxlength="60"></div>
        <div class="field"><label>Target ($)</label><input type="number" id="adv-target" min="1000" step="1000" value="250000"></div>
        <div class="field"><label>Horizon (years)</label><input type="number" id="adv-years" min="1" max="50" value="15"></div>
        <div class="field"><label>Risk tolerance</label><select id="adv-risk">
          <option>Conservative</option><option selected>Balanced</option><option>Growth</option><option>Aggressive</option>
        </select></div>
        <div class="field"><label>Starting lump sum ($)</label><input type="number" id="adv-lump" min="0" step="500" value="10000"></div>
        <div class="field"><label>Monthly contribution ($)</label><input type="number" id="adv-monthly" min="0" step="50" value="500"></div>
        <button class="action primary" id="adv-add">Create Plan</button>
      </div>
    </div>
    ${selected ? renderAdvisorPlanDetail(selected[0], selected[1], planOpts) : ""}`;

  document.getElementById("adv-add").addEventListener("click", () => {
    const name = document.getElementById("adv-name").value.trim();
    if (!name) return;
    const risk = document.getElementById("adv-risk").value;
    const ws = worldState();
    const id = "p" + (ws.advisor.nextId++);
    const plan = {
      name, risk,
      target: Math.max(1000, Number(document.getElementById("adv-target").value) || 0),
      years: Math.max(1, Number(document.getElementById("adv-years").value) || 1),
      lumpSum: Math.max(0, Number(document.getElementById("adv-lump").value) || 0),
      monthly: Math.max(0, Number(document.getElementById("adv-monthly").value) || 0),
      allocation: { ...RISK_TIERS[risk].allocation },
      cash: Math.max(0, Number(document.getElementById("adv-lump").value) || 0),
      startCash: Math.max(0, Number(document.getElementById("adv-lump").value) || 0),
      holdings: {}, history: [], funded: false, monthsContributed: 0,
    };
    ws.advisor.plans[id] = plan;
    el.dataset.selected = id;
    saveState(STATE); renderAdvisor();
  });

  wireAdvisorPlanDetail();
}

function renderAdvisorPlanDetail(id, plan, planOpts) {
  const tier = RISK_TIERS[plan.risk];
  const fv = projectedFutureValue(plan.lumpSum, plan.monthly, plan.years, tier.assumedReturn);
  const allocBits = Object.entries(plan.allocation).filter(([k, v]) => v > 0)
    .map(([k, v]) => `${k[0].toUpperCase() + k.slice(1)} ${v}%`).join(" &middot; ");
  return `
    <div class="card">
      <h3>Plan &mdash; <select id="adv-plan-select">${planOpts}</select></h3>
      <div class="stat-grid">
        <div class="stat"><div class="label">Target</div><div class="value">${fmtMoney(plan.target)}</div></div>
        <div class="stat"><div class="label">Assumed annual return</div><div class="value">${(tier.assumedReturn * 100).toFixed(0)}%</div></div>
        <div class="stat"><div class="label">Projected value @ ${plan.years}y</div><div class="value">${fmtMoney(fv, { compact: true })}</div></div>
        <div class="stat"><div class="label">Actual sim value</div><div class="value">${plan.funded ? fmtMoney(portfolioTotalValue(plan), { compact: true }) : "—"}</div></div>
      </div>
      <div class="note"><strong>Suggested allocation for ${plan.risk}:</strong> ${allocBits}. Projection is a simple compounding estimate (not guaranteed) used only to illustrate how time horizon and risk tolerance change the math.</div>
      <div class="field-row">
        ${!plan.funded ? `<button class="action primary" id="adv-fund">Fund Plan (invest lump sum now)</button>` :
          `<button class="action buy" id="adv-contribute">Add a Month's Contribution (${fmtMoney(plan.monthly)})</button>`}
        <button class="action ghost" id="adv-remove">Remove Plan</button>
      </div>
      <div id="adv-msg" class="empty-note"></div>
      ${plan.funded ? `<div style="margin-top:12px"><h3 style="font-size:14px">Holdings</h3>${renderHoldingsTable(plan)}</div>
      <div style="margin-top:12px"><h3 style="font-size:14px">Trade History</h3>${renderHistory(plan)}</div>` : ""}
    </div>`;
}
function wireAdvisorPlanDetail() {
  const planSelect = document.getElementById("adv-plan-select");
  if (!planSelect) return;
  const el = document.getElementById("mode-advisor");
  planSelect.addEventListener("change", () => { el.dataset.selected = planSelect.value; renderAdvisor(); });

  const id = el.dataset.selected;
  const plan = worldState().advisor.plans[id];
  const fundBtn = document.getElementById("adv-fund");
  if (fundBtn) fundBtn.addEventListener("click", () => {
    fundPlan(plan); saveState(STATE); renderAdvisor();
  });
  const contribBtn = document.getElementById("adv-contribute");
  if (contribBtn) contribBtn.addEventListener("click", () => {
    investContribution(plan); saveState(STATE); renderAdvisor();
  });
  document.getElementById("adv-remove").addEventListener("click", () => {
    if (!confirm(`Remove plan "${plan.name}"?`)) return;
    delete worldState().advisor.plans[id];
    el.dataset.selected = "";
    saveState(STATE); renderAdvisor();
  });
}
