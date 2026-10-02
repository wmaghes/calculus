// Milestone 0: test harness for engine.js's pure, DOM-free logic.
// Run with `node --test` (no framework, no bundler -- see package.json).
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const MarketEngine = require("./engine.js");

const { stepPrice, deriveRealParams, createExtraDiversifiedTickers } = MarketEngine;

test("stepPrice", async (t) => {
  await t.test("dtYears=0 returns the input price unchanged", () => {
    assert.equal(stepPrice(100, 0.08, 0.3, 0), 100);
  });

  await t.test("negative dtYears also short-circuits to the input price", () => {
    assert.equal(stepPrice(42, 0.08, 0.3, -1), 42);
  });

  await t.test("returns a finite, positive number for typical inputs", () => {
    for (let i = 0; i < 100; i++) {
      const next = stepPrice(100, 0.08, 0.3, 1 / 365);
      assert.ok(Number.isFinite(next), `expected finite, got ${next}`);
      assert.ok(next > 0, `expected positive, got ${next}`);
    }
  });

  await t.test("respects the 0.01 floor even for a catastrophic drop", () => {
    // A huge dtYears with high volatility makes the -0.5*vol^2*dtYears decay
    // term dominate over the sqrt(dtYears)*z stochastic term for any
    // realistic z, driving the price toward zero regardless of randomness.
    for (let i = 0; i < 20; i++) {
      const next = stepPrice(100, 0.05, 1.0, 1e6);
      assert.equal(next, 0.01);
    }
  });

  await t.test("never returns a value below the 0.01 floor across many draws", () => {
    for (let i = 0; i < 500; i++) {
      const next = stepPrice(50, -0.5, 0.9, 5);
      assert.ok(next >= 0.01, `expected >= 0.01, got ${next}`);
    }
  });
});

test("deriveRealParams", async (t) => {
  await t.test("beta branch produces finite drift/vol scaled by beta", () => {
    const { drift, vol } = deriveRealParams({ metric_label: "Beta", metric: 1.5 }, "stability");
    assert.ok(Number.isFinite(drift));
    assert.ok(Number.isFinite(vol));
    assert.ok(vol >= 0.1 && vol <= 0.85);
  });

  await t.test("growth branch produces finite drift/vol scaled by growth metric", () => {
    const { drift, vol } = deriveRealParams({ metric_label: "Revenue Growth", metric: 25 }, "growth");
    assert.ok(Number.isFinite(drift));
    assert.ok(Number.isFinite(vol));
    assert.equal(drift, 0.25);
    assert.ok(vol >= 0.22 && vol <= 0.85);
  });

  await t.test("short branch produces a fixed bearish drift/vol", () => {
    const { drift, vol } = deriveRealParams({ metric_label: "Short % of Float", metric: 10 }, "shorts");
    assert.equal(drift, -0.12);
    assert.equal(vol, 0.55);
  });

  await t.test("unlabeled numeric metric falls back to the generic branch", () => {
    const { drift, vol } = deriveRealParams({ metric_label: "", metric: 20 }, "growth");
    assert.equal(drift, 0.2);
    assert.equal(vol, 0.35);
  });

  await t.test("missing metric/label falls back to sane defaults", () => {
    const { drift, vol } = deriveRealParams({}, "growth");
    assert.equal(drift, 0.08);
    assert.equal(vol, 0.3);
  });

  await t.test("nextgen category bumps volatility, capped at 0.95", () => {
    const base = deriveRealParams({ metric_label: "Revenue Growth", metric: 90 }, "growth");
    const bumped = deriveRealParams({ metric_label: "Revenue Growth", metric: 90 }, "nextgen");
    assert.ok(bumped.vol >= base.vol);
    assert.ok(bumped.vol <= 0.95);
  });

  await t.test("never produces NaN/Infinity across a spread of inputs", () => {
    const cases = [
      { metric_label: "Beta", metric: 0 },
      { metric_label: "Beta", metric: -3 },
      { metric_label: "growth rate", metric: -200 },
      { metric_label: "shortinterest", metric: 999 },
      { metric_label: "momentum", metric: 50 },
      {},
    ];
    for (const item of cases) {
      for (const cat of ["growth", "stability", "nextgen", "shorts"]) {
        const { drift, vol } = deriveRealParams(item, cat);
        assert.ok(Number.isFinite(drift), `drift not finite for ${JSON.stringify(item)}/${cat}`);
        assert.ok(Number.isFinite(vol), `vol not finite for ${JSON.stringify(item)}/${cat}`);
      }
    }
  });
});

test("createExtraDiversifiedTickers", async (t) => {
  await t.test("produces the fixed set of 8 funds + 8 individual small/mid-cap companies", () => {
    const used = new Set();
    const extra = createExtraDiversifiedTickers(used);
    const keys = Object.keys(extra);
    assert.equal(keys.length, 16, "expected 8 fund flavors + 4 small-cap + 4 mid-cap");
    assert.equal(used.size, 16, "every generated ticker should be recorded as used");
  });

  await t.test("every entry is well-formed, category 'funds', with finite price/drift/vol", () => {
    const extra = createExtraDiversifiedTickers(new Set());
    for (const [ticker, item] of Object.entries(extra)) {
      assert.equal(item.ticker, ticker);
      assert.equal(item.category, "funds");
      assert.ok(Number.isFinite(item.price) && item.price > 0, `${ticker} price`);
      assert.ok(Number.isFinite(item.drift), `${ticker} drift`);
      assert.ok(Number.isFinite(item.vol) && item.vol > 0, `${ticker} vol`);
      assert.ok(Array.isArray(item.history) && item.history.length === 1);
    }
  });

  await t.test("includes exactly 8 ETF/mutual-fund entries and 8 individual stocks (4 small, 4 mid)", () => {
    const extra = createExtraDiversifiedTickers(new Set());
    const items = Object.values(extra);
    const funds = items.filter((i) => i.assetType === "etf" || i.assetType === "mutual_fund");
    const stocks = items.filter((i) => i.assetType === "stock");
    assert.equal(funds.length, 8);
    assert.equal(stocks.length, 8);
    assert.equal(stocks.filter((i) => i.capTier === "small").length, 4);
    assert.equal(stocks.filter((i) => i.capTier === "mid").length, 4);
  });

  await t.test("respects a pre-populated 'used' set without throwing or colliding", () => {
    const used = new Set(["ABC", "AAAX"]);
    const extra = createExtraDiversifiedTickers(used);
    assert.equal(Object.keys(extra).length, 16);
    assert.ok(!("ABC" in extra));
    assert.ok(!("AAAX" in extra));
  });
});
