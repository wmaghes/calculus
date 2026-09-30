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

  function randomChoice(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
  function randomRange(lo, hi) { return lo + Math.random() * (hi - lo); }

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
      tickers[ticker] = {
        ticker, name, category, sector,
        price, seedPrice: price, drift, vol,
        shares, netIncome, revenue,
        history: [{ t: 0, p: price }],
      };
    }
    return { mode: "super", tickers, simMs: 0, lastRealMs: Date.now(), createdAt: Date.now() };
  }

  const MAX_HISTORY = 300;
  const MAX_CATCHUP_YEARS = 5; // cap a single jump (e.g. after the tab was closed for days at a fast speed) so GBM doesn't extrapolate into nonsense

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
