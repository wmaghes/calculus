/*
 * Market Engine: advances simulated ticker prices through time using a
 * geometric Brownian motion model (the standard textbook random-walk model
 * for a stock price), at a speed the user controls.
 *
 * Two starting universes:
 *   - "real"  world seeds each of the 32 watchlist tickers at their real
 *     Market Scanner snapshot price, with drift/volatility DERIVED from
 *     that same snapshot's own metrics (beta, growth, momentum). This is
 *     NOT a replay of actual historical prices -- this sandbox has no
 *     historical time-series data to replay. It is a disclosed model,
 *     calibrated from real numbers, run forward.
 *   - "super" world procedurally generates entirely fictional companies
 *     (fake tickers, names, sectors, financials) for fast, consequence-free
 *     experimentation at any speed.
 */
const MarketEngine = (function () {
  const MS_PER_YEAR = 365.25 * 24 * 3600 * 1000;

  const SPEED_PRESETS = [
    { key: "daytrader", label: "Day Trader \u2014 1 year per 10 min", realMsPerYear: 10 * 60 * 1000 },
    { key: "swing", label: "Swing Trader \u2014 1 year per hour", realMsPerYear: 60 * 60 * 1000 },
    { key: "position", label: "Position Trader \u2014 1 year per day", realMsPerYear: 24 * 60 * 60 * 1000 },
    { key: "investor", label: "Long-Term Investor \u2014 1 year per week", realMsPerYear: 7 * 24 * 60 * 60 * 1000 },
    { key: "realtime", label: "Real-Time \u2014 1 year per year", realMsPerYear: MS_PER_YEAR },
  ];

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function gaussianRandom() {
    let u = 0, v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  // One GBM step. Valid for any dtYears (including a large catch-up jump
  // after time away) since GBM's distribution over an interval depends only
  // on the interval length, not on how finely it's sub-divided.
  function stepPrice(price, driftAnnual, volAnnual, dtYears) {
    if (dtYears <= 0) return price;
    const z = gaussianRandom();
    const next = price * Math.exp((driftAnnual - 0.5 * volAnnual * volAnnual) * dtYears + volAnnual * Math.sqrt(dtYears) * z);
    return Math.max(0.01, next);
  }

  // Turn one Market Scanner snapshot row into a (drift, volatility) pair.
  // Beta-style metrics scale volatility directly; growth/momentum metrics
  // become the drift (clamped to a sane annual range); short-interest names
  // get a bearish bias. Everything is a heuristic disclosed in the UI.
  function deriveRealParams(item, cat) {
    let drift = 0.08, vol = 0.30;
    const label = (item.metric_label || "").toLowerCase();
    if (label.includes("beta") && typeof item.metric === "number") {
      vol = clamp(0.28 * Math.max(0.2, item.metric), 0.10, 0.85);
      drift = clamp(0.03 + 0.02 * item.metric, -0.05, 0.12);
    } else if (label.includes("growth") && typeof item.metric === "number") {
      drift = clamp(item.metric / 100, -0.30, 0.55);
      vol = clamp(0.25 + Math.abs(drift) * 0.45, 0.22, 0.85);
    } else if (label.includes("short")) {
      drift = -0.12; vol = 0.55;
    } else if (typeof item.metric === "number") {
      drift = clamp(item.metric / 100, -0.20, 0.40);
      vol = 0.35;
    }
    if (cat === "nextgen") vol = Math.min(0.95, vol + 0.15);
    return { drift, vol };
  }

  function createRealWorld(scannerData) {
    const tickers = {};
    for (const [cat, arr] of Object.entries(scannerData.categories || {})) {
      for (const item of arr) {
        if (tickers[item.ticker] || item.price == null) continue;
        const { drift, vol } = deriveRealParams(item, cat);
        tickers[item.ticker] = {
          ticker: item.ticker, name: item.name, category: cat,
          price: item.price, seedPrice: item.price, drift, vol,
          history: [{ t: 0, p: item.price }],
        };
      }
    }
    return { mode: "real", tickers, simMs: 0, lastRealMs: Date.now(), createdAt: Date.now() };
  }

  const SECTORS = ["Technology", "Biotech", "Energy", "Consumer Retail", "Industrials", "Financials", "Real Estate", "Telecom"];
  const NAME_A = ["Nova", "Zenith", "Quantum", "Vertex", "Helio", "Axiom", "Cobalt", "Meridian", "Lumen", "Atlas", "Trident", "Orbital", "Ferrous", "Cascade", "Nimbus", "Halcyon", "Ridgeline", "Solace"];
  const NAME_B = ["Dynamics", "Holdings", "Systems", "Labs", "Industries", "Networks", "Materials", "Robotics", "Biosciences", "Energy", "Capital", "Ventures", "Works", "Technologies"];
  const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

  const SECTOR_SPECIALTY = {
    Technology: ["cloud infrastructure monitoring", "enterprise cybersecurity", "AI-powered customer support software", "edge computing hardware", "developer productivity tools"],
    Biotech: ["gene-editing therapeutics", "oncology drug development", "at-home diagnostic testing", "mRNA vaccine platforms", "rare disease treatments"],
    Energy: ["grid-scale battery storage", "offshore wind turbine components", "carbon capture systems", "next-generation solar panels", "hydrogen fuel infrastructure"],
    "Consumer Retail": ["direct-to-consumer athletic wear", "subscription meal kits", "budget home furnishings", "specialty pet products", "off-price fashion retail"],
    Industrials: ["industrial robotics arms", "precision-machined aerospace parts", "warehouse automation systems", "modular construction components", "advanced materials manufacturing"],
    Financials: ["small-business lending", "embedded payments infrastructure", "digital wealth management", "trade finance technology", "specialty insurance underwriting"],
    "Real Estate": ["logistics warehouse REITs", "data center real estate", "affordable housing development", "self-storage facilities", "senior living communities"],
    Telecom: ["rural broadband infrastructure", "satellite internet connectivity", "5G network equipment", "fiber-optic backbone networks", "IoT connectivity platforms"],
  };
  const HQ_CITIES = ["Austin, TX", "Denver, CO", "Raleigh, NC", "Seattle, WA", "Boston, MA", "San Diego, CA", "Atlanta, GA", "Minneapolis, MN", "Phoenix, AZ", "Columbus, OH", "Nashville, TN", "Salt Lake City, UT"];
  const FIRST_NAMES = ["Maria", "James", "Wei", "Priya", "Daniel", "Sofia", "Marcus", "Elena", "Omar", "Grace", "Nathan", "Amara"];
  const LAST_NAMES = ["Chen", "Patel", "Rodriguez", "Kowalski", "Nakamura", "Okafor", "Petrov", "Larsen", "Silva", "Kim", "Fischer", "Diallo"];

  function randomChoice(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
  function randomRange(lo, hi) { return lo + Math.random() * (hi - lo); }
  function randomInt(lo, hi) { return Math.floor(randomRange(lo, hi + 1)); }

  function randomTicker(used) {
    let t;
    do {
      const len = Math.random() < 0.5 ? 3 : 4;
      t = "";
      for (let i = 0; i < len; i++) t += LETTERS[Math.floor(Math.random() * LETTERS.length)];
    } while (used.has(t));
    used.add(t);
    return t;
  }

  // A fictional business profile so a fake ticker reads like a company, not
  // just a random number generator with a name attached.
  function generateProfile(ticker, name, sector, revenue) {
    const specialty = randomChoice(SECTOR_SPECIALTY[sector] || SECTOR_SPECIALTY.Technology);
    const hq = randomChoice(HQ_CITIES);
    const founded = randomInt(1998, 2021);
    const ceo = `${randomChoice(FIRST_NAMES)} ${randomChoice(LAST_NAMES)}`;
    const employees = Math.max(40, Math.round((revenue / 1e6) * randomRange(1.5, 4)));
    return {
      specialty, hq, founded, ceo, employees,
      tagline: `Specializing in ${specialty}.`,
      description: `${name} (${ticker}) is a ${sector}-sector company specializing in ${specialty}, headquartered in ${hq} and founded in ${founded}. Led by CEO ${ceo}, the company employs approximately ${employees.toLocaleString()} people.`,
    };
  }

  // A short trailing four-quarter financial backstory, generated once at
  // creation so a fake company has "history" instead of appearing from
  // nowhere. Purely a static narrative -- it does not evolve with sim time.
  function generateQuarterlyHistory(revenue, netMarginPct) {
    const quarters = [];
    let val = (revenue / 4) * randomRange(0.80, 0.92);
    for (let i = 0; i < 4; i++) {
      val = val * (1 + randomRange(-0.03, 0.09));
      quarters.push({ revenue: val, netIncome: val * (netMarginPct / 100) });
    }
    return quarters; // oldest to newest
  }

  const NEWS_TEMPLATES = {
    strong: [
      "{ticker} shares surge after a blowout quarter beats analyst expectations.",
      "{name} posts its strongest bookings quarter to date, sending {ticker} sharply higher.",
      "Investors cheer as {ticker} raises full-year guidance on accelerating demand.",
    ],
    beat: [
      "{ticker} climbs on better-than-expected quarterly results.",
      "{name} tops estimates; {ticker} moves higher in reaction.",
      "Solid execution lifts {ticker} as {name} beats consensus.",
    ],
    steady: [
      "{name} reports a quarter largely in line with expectations; {ticker} little changed.",
      "{ticker} holds steady as {name}'s results match analyst forecasts.",
      "No major surprises from {name} this quarter; {ticker} trades flat.",
    ],
    miss: [
      "{ticker} slides after {name} misses quarterly expectations.",
      "{name} cuts guidance, sending {ticker} lower.",
      "Soft demand weighs on {name}; {ticker} falls on the news.",
    ],
    steep: [
      "{ticker} tumbles as {name} warns of a sharper-than-expected slowdown.",
      "Shares of {name} ({ticker}) plunge amid mounting investor concerns.",
      "{ticker} sinks after {name} discloses a major setback in its {sector} business.",
    ],
  };
  function newsBucket(pctChange) {
    if (pctChange > 15) return "strong";
    if (pctChange > 5) return "beat";
    if (pctChange >= -5) return "steady";
    if (pctChange >= -15) return "miss";
    return "steep";
  }
  function makeNewsItem(t, pctChange, simMs) {
    const bucket = newsBucket(pctChange);
    const template = randomChoice(NEWS_TEMPLATES[bucket]);
    const headline = template.replace(/\{ticker\}/g, t.ticker).replace(/\{name\}/g, t.name).replace(/\{sector\}/g, t.sector);
    return { t: simMs, headline, pctChange };
  }

  // A fixed, small set of fake funds -- one per "flavor" -- so Super
  // Simulator mode teaches the same diversification-lowers-volatility
  // lesson as Real Companies mode, where it falls out naturally from each
  // real fund's own beta. Volatility/drift ranges are deliberately modeled
  // after real-world analogues (a broad index ETF, a tech-tilted one, a
  // small-cap index, a dividend/quality screen, a bond fund, and the
  // mutual-fund equivalents of an index fund, an active growth fund, and a
  // bond-tilted balanced fund) rather than randomized like individual
  // fake companies.
  const FUND_NAME_WORDS = ["Horizon", "Summit", "Beacon", "Cornerstone", "Meridian", "Anchor", "Keystone", "Pinnacle", "Vantage", "Granite"];
  const FUND_FLAVORS = [
    { kind: "etf", label: "Broad Market Index ETF", vol: [0.18, 0.26], drift: [0.06, 0.09],
      holdings: (s) => `Tracks a broad, diversified basket of ${s} companies across every sector in this simulation, weighted by size.` },
    { kind: "etf", label: "Growth Index ETF", vol: [0.28, 0.38], drift: [0.07, 0.11],
      holdings: (s) => `Concentrates on this simulation's fastest-growing ${s} companies, so it swings harder than a broad-market fund.` },
    { kind: "etf", label: "Small-Cap Index ETF", vol: [0.30, 0.40], drift: [0.05, 0.09],
      holdings: () => `Holds a wide basket of this simulation's smaller companies; diversified, but small companies as a group are still more volatile than large ones.` },
    { kind: "etf", label: "Dividend Growth ETF", vol: [0.14, 0.20], drift: [0.05, 0.08],
      holdings: (s) => `Screens for established, steadily-profitable ${s} companies in this simulation with a history of raising their dividend.` },
    { kind: "etf", label: "Core Bond ETF", vol: [0.06, 0.11], drift: [0.02, 0.045],
      holdings: () => `Holds simulated investment-grade bonds instead of stocks, so it mostly reacts to interest-rate assumptions rather than this simulation's stock-market swings.` },
    { kind: "mutual_fund", label: "Index Mutual Fund", vol: [0.18, 0.26], drift: [0.06, 0.09],
      holdings: (s) => `The mutual-fund twin of a broad index ETF: owns a wide basket of ${s} companies and moves almost exactly in line with this simulation's overall market.` },
    { kind: "mutual_fund", label: "Actively Managed Growth Fund", vol: [0.24, 0.32], drift: [0.07, 0.10],
      holdings: (s) => `A fictional manager actively picks a changing set of ${s} growth companies rather than tracking an index.` },
    { kind: "mutual_fund", label: "Balanced Income Fund", vol: [0.12, 0.18], drift: [0.04, 0.065],
      holdings: () => `Splits assets between simulated bonds and steady dividend payers, trading upside for a much gentler ride than a pure stock fund.` },
  ];
  function randomFundTicker(used, kind) {
    let t;
    do {
      if (kind === "etf") {
        t = ""; for (let i = 0; i < 3; i++) t += LETTERS[Math.floor(Math.random() * LETTERS.length)];
      } else {
        t = ""; for (let i = 0; i < 4; i++) t += LETTERS[Math.floor(Math.random() * LETTERS.length)];
        t += "X";
      }
    } while (used.has(t));
    used.add(t);
    return t;
  }

  // A fixed, small set of explicit small-cap and mid-cap individual
  // companies, sized (via price * shares) to actually land in their
  // intended market-cap band, with volatility skewed to match real-world
  // cap-size risk: smaller companies carry more idiosyncratic risk than
  // the mega/large-cap names that dominate the main random universe.
  const CAP_SPECS = [
    { tier: "small", n: 4, mktCap: [0.3e9, 2e9], vol: [0.45, 0.80] },
    { tier: "mid", n: 4, mktCap: [2e9, 10e9], vol: [0.28, 0.50] },
  ];

  function createExtraDiversifiedTickers(used) {
    const extra = {};

    for (const flavor of FUND_FLAVORS) {
      const ticker = randomFundTicker(used, flavor.kind);
      const flavorSector = randomChoice(SECTORS);
      const name = `${randomChoice(FUND_NAME_WORDS)} ${flavor.label}`;
      const vol = randomRange(flavor.vol[0], flavor.vol[1]);
      const drift = randomRange(flavor.drift[0], flavor.drift[1]);
      const price = flavor.kind === "etf" ? Math.round(randomRange(40, 450) * 100) / 100 : Math.round(randomRange(10, 120) * 100) / 100;
      extra[ticker] = {
        ticker, name, category: "funds", sector: "Diversified", assetType: flavor.kind,
        price, seedPrice: price, drift, vol,
        shares: null, netIncome: null, revenue: null, netMarginPct: null,
        profile: { description: flavor.holdings(flavorSector) },
        history: [{ t: 0, p: price }],
      };
    }

    for (const spec of CAP_SPECS) {
      for (let i = 0; i < spec.n; i++) {
        const ticker = randomTicker(used);
        const name = `${randomChoice(NAME_A)} ${randomChoice(NAME_B)}`;
        const sector = randomChoice(SECTORS);
        const mktCap = randomRange(spec.mktCap[0], spec.mktCap[1]);
        const price = Math.round(randomRange(5, 120) * 100) / 100;
        const shares = Math.round(mktCap / price);
        const drift = randomRange(-0.15, 0.35);
        const vol = randomRange(spec.vol[0], spec.vol[1]);
        const netMarginPct = randomRange(-15, 25);
        const revenue = mktCap / randomRange(2, 10);
        const netIncome = revenue * (netMarginPct / 100);
        const profile = generateProfile(ticker, name, sector, revenue);
        const quarterlyHistory = generateQuarterlyHistory(revenue, netMarginPct);
        extra[ticker] = {
          ticker, name, category: "funds", sector, assetType: "stock", capTier: spec.tier,
          price, seedPrice: price, drift, vol,
          shares, netIncome, revenue, netMarginPct,
          profile, quarterlyHistory,
          news: [{ t: 0, headline: `${name} (${ticker}) begins trading today.`, pctChange: 0 }],
          lastNewsSimMs: 0, lastNewsPrice: price,
          history: [{ t: 0, p: price }],
        };
      }
    }
    return extra;
  }

  function createSuperWorld(count) {
    count = count || 24;
    const tickers = {};
    const used = new Set();
    for (let i = 0; i < count; i++) {
      const ticker = randomTicker(used);
      const name = `${randomChoice(NAME_A)} ${randomChoice(NAME_B)}`;
      const sector = randomChoice(SECTORS);
      const price = Math.round(randomRange(5, 400) * 100) / 100;
      const drift = randomRange(-0.20, 0.45);
      const vol = randomRange(0.18, 0.85);
      const shares = Math.round(randomRange(10e6, 1.5e9));
      const netMarginPct = randomRange(-20, 32);
      const revenue = (price * shares) / randomRange(2, 14);
      const netIncome = revenue * (netMarginPct / 100);
      let category = "growth";
      if (vol < 0.30) category = "stability";
      else if (vol > 0.65 || drift > 0.30) category = "nextgen";
      const mktCap = price * shares;
      const capTier = mktCap >= 200e9 ? "mega" : mktCap >= 10e9 ? "large" : mktCap >= 2e9 ? "mid" : "small";
      const profile = generateProfile(ticker, name, sector, revenue);
      const quarterlyHistory = generateQuarterlyHistory(revenue, netMarginPct);
      tickers[ticker] = {
        ticker, name, category, sector, assetType: "stock", capTier,
        price, seedPrice: price, drift, vol,
        shares, netIncome, revenue, netMarginPct,
        profile, quarterlyHistory,
        news: [{ t: 0, headline: `${name} (${ticker}) begins trading today.`, pctChange: 0 }],
        lastNewsSimMs: 0, lastNewsPrice: price,
        history: [{ t: 0, p: price }],
      };
    }
    Object.assign(tickers, createExtraDiversifiedTickers(used));
    return { mode: "super", tickers, simMs: 0, lastRealMs: Date.now(), createdAt: Date.now() };
  }

  const MAX_HISTORY = 300;
  const MAX_CATCHUP_YEARS = 5; // cap a single jump (e.g. after the tab was closed for days at a fast speed) so GBM doesn't extrapolate into nonsense
  const QUARTER_MS = MS_PER_YEAR / 4;
  const MAX_NEWS = 12;

  function tick(world, speedRealMsPerYear, nowMs) {
    nowMs = nowMs || Date.now();
    const elapsedRealMs = Math.max(0, nowMs - world.lastRealMs);
    if (elapsedRealMs <= 0) { world.lastRealMs = nowMs; return world; }
    const dtYears = Math.min(elapsedRealMs / speedRealMsPerYear, MAX_CATCHUP_YEARS);
    world.simMs += dtYears * MS_PER_YEAR;
    for (const t of Object.values(world.tickers)) {
      t.price = stepPrice(t.price, t.drift, t.vol, dtYears);
      t.history.push({ t: world.simMs, p: t.price });
      if (t.history.length > MAX_HISTORY) t.history.splice(0, t.history.length - MAX_HISTORY);

      if (world.mode === "super" && t.news && world.simMs - t.lastNewsSimMs >= QUARTER_MS) {
        const pctChange = ((t.price - t.lastNewsPrice) / t.lastNewsPrice) * 100;
        t.news.unshift(makeNewsItem(t, pctChange, world.simMs));
        if (t.news.length > MAX_NEWS) t.news.length = MAX_NEWS;
        t.lastNewsSimMs = world.simMs;
        t.lastNewsPrice = t.price;
      }
    }
    world.lastRealMs = nowMs;
    return world;
  }

  // Equal-weighted index of every ticker in the world, based to 100 at the
  // start of its history.
  function indexSeries(world) {
    const list = Object.values(world.tickers);
    if (list.length === 0) return [];
    const base = list.reduce((s, t) => s + (t.history[0] ? t.history[0].p : t.price), 0) / list.length;
    const maxLen = Math.max(...list.map((t) => t.history.length));
    const points = [];
    for (let i = 0; i < maxLen; i++) {
      let sum = 0, n = 0, simT = null;
      for (const t of list) {
        const h = t.history[Math.min(i, t.history.length - 1)];
        if (h) { sum += h.p; n++; simT = h.t; }
      }
      if (n > 0) points.push({ t: simT, v: (sum / n / base) * 100 });
    }
    return points;
  }

  return {
    MS_PER_YEAR, SPEED_PRESETS, clamp, stepPrice, deriveRealParams,
    createRealWorld, createSuperWorld, tick, indexSeries,
  };
})();
