/* Renders one Career Guide role page from dashboard/guide/data/careers.json.
 * Each roles/<id>.html sets window.GUIDE_ROLE = "<id>" before loading this
 * file (same pattern as the Scanner's window.SCANNER_CATEGORY). */

const ROLE_ORDER = ["individual", "advisor", "private-banker", "investment-banker", "trader", "quant",
  "private-equity", "venture-capital", "hedge-fund", "cfo", "market-maker", "research-analyst", "risk-manager"];

const MARKET_DEP_LABELS = {
  "rates": "Interest rates",
  "credit-spreads": "Credit spreads",
  "equity-vol": "Equity volatility",
  "earnings-season": "Earnings season",
  "commodity-fx": "Commodities & FX",
};

function stripHtml(html) {
  const div = document.createElement("div");
  div.innerHTML = html;
  return div.textContent || "";
}

function buildKnowledgeBase(role) {
  const kb = [{ lead: "In short:", text: stripHtml(role.oneLiner), generic: true }];
  kb.push({ lead: "Here's how I use the market in this job:", text: stripHtml(role.dayToDay.howTheyUseMarket) });
  kb.push({ lead: "Day to day, here's what it actually looks like:", text: stripHtml(role.dayToDay.inPractice) });
  kb.push({ lead: "As for how I'm paid:", text: stripHtml(role.pay) });
  role.variations.forEach((v) => kb.push({ lead: "One version of this role:", text: stripHtml(v) }));
  if (role.skills.length) kb.push({ lead: "The tools and concepts I lean on:", text: role.skills.map(stripHtml).join(", ") + "." });
  if (role.tryItHtml) kb.push({ lead: "If you want to try this yourself:", text: stripHtml(role.tryItHtml) });
  (role.expertiseQA || []).forEach((e) => kb.push({ lead: stripHtml(e.lead), text: stripHtml(e.text) }));
  return kb;
}

function renderNav(activeId) {
  const nav = document.getElementById("roleNav");
  const links = ROLE_ORDER.map((id) => {
    const el = CAREERS_BY_ID[id];
    const cls = id === activeId ? "active" : "";
    return `<a href="${id}.html" class="${cls}"><span class="dot"></span>${el.title}</a>`;
  }).join("");
  nav.innerHTML = `<a href="../index.html" class="back">&larr; Guide</a>${links}`;
}

function renderRole(role) {
  // role.title / role.tag may contain HTML entities (e.g. "Sales &amp;
  // Trading") migrated verbatim from the original markup -- decode them
  // for document.title (plain text) and render the rest via innerHTML so
  // the entities display correctly rather than literally.
  document.title = stripHtml(role.title) + " — Career Guide";
  document.getElementById("rpIcon").innerHTML = role.icon;
  document.getElementById("rpTitle").innerHTML = role.title;
  document.getElementById("rpTag").innerHTML = role.tag;
  document.getElementById("rpOneliner").innerHTML = role.oneLiner;

  const content = document.getElementById("roleContent");

  const variationsHtml = role.variations.map((v) => `<div class="variant">${v}</div>`).join("");
  const skillsHtml = role.skills.map((s) => `<span class="chip">${s}</span>`).join("");
  const depsHtml = role.marketDependencies.map((d) => `<span class="chip dep-chip">${MARKET_DEP_LABELS[d] || d}</span>`).join("");
  const majorsHtml = role.entryPath.typicalMajors.map((m) => `<span class="chip">${m}</span>`).join("");
  const ladderHtml = role.progressionLadder.map((rung, i) =>
    (i > 0 ? `<span class="arrow">&rarr;</span>` : "") + `<span class="rung">${rung}</span>`
  ).join("");

  content.innerHTML = `
    <h3>How they use the market</h3>
    <p>${role.dayToDay.howTheyUseMarket}</p>
    <h3>In practice</h3>
    <p>${role.dayToDay.inPractice}</p>
    <h3>Variations on this role</h3>
    <div class="variant-list">${variationsHtml}</div>
    <h3>How they're paid</h3>
    <p>${role.pay}</p>
    <h3>Key tools &amp; concepts</h3>
    <div class="chip-row">${skillsHtml}</div>
    <h3>What this role tends to track</h3>
    <div class="chip-row">${depsHtml}</div>
    <p class="hedge-note">Illustrative tagging for a future "what this means for your career" market-linkage feature &mdash; not yet live analysis of any specific indicator.</p>
    <h3>Breaking in</h3>
    <div class="chip-row">${majorsHtml}</div>
    <p style="margin-top:8px">${role.entryPath.internshipPath}</p>
    <p class="hedge-note">General, illustrative guidance, not a guarantee &mdash; verify specifics with your school's career office or target firms. Logged in docs/CONTENT_TODO.md.</p>
    <h3>Typical progression</h3>
    <div class="ladder-list">${ladderHtml}</div>
    <p class="hedge-note">Titles and pacing vary a lot by firm and group &mdash; shown as a general illustration, not a guarantee. Logged in docs/CONTENT_TODO.md.</p>
  `;

  if (role.calculatorId) renderCalculator(content, role.calculatorId);
  if (role.tryItHtml) {
    const tryIt = document.createElement("div");
    tryIt.className = "try-it";
    tryIt.innerHTML = role.tryItHtml;
    content.appendChild(tryIt);
  }

  // Mentor panel mounts above the content card.
  const mentorMount = document.getElementById("mentorMount");
  const kb = buildKnowledgeBase(role);
  const colorIdx = ROLE_ORDER.indexOf(role.id);
  renderMentorPanel(mentorMount, role.id, role.title, kb, colorIdx);
  initMentorVoices();
}

let CAREERS_BY_ID = {};

async function bootRolePage() {
  const roleId = window.GUIDE_ROLE;
  try {
    const res = await fetch("../data/careers.json");
    const data = await res.json();
    CAREERS_BY_ID = {};
    data.roles.forEach((r) => { CAREERS_BY_ID[r.id] = r; });
  } catch (e) {
    document.getElementById("roleContent").innerHTML = `<p style="color:var(--neg)">Could not load careers.json &mdash; ${e.message}</p>`;
    return;
  }
  const role = CAREERS_BY_ID[roleId];
  if (!role) {
    document.getElementById("roleContent").innerHTML = `<p style="color:var(--neg)">Unknown role: ${roleId}</p>`;
    return;
  }
  renderNav(roleId);
  renderRole(role);
}

bootRolePage();
