"""Turns raw market_data.json into ranked lists for the four dashboard
categories: biggest growth, stability, next-generation growth, short
candidates. All scores are 0-100, computed by min-max normalizing a metric
across whichever tickers actually have that metric populated -- tickers
missing a required metric are simply excluded from that category rather
than guessed at.
"""

import json
import os

import config


def _values(rows: list[dict], key: str) -> list[float]:
    return [r[key] for r in rows if isinstance(r.get(key), (int, float))]


def normalize(value: float, lo: float, hi: float, invert: bool = False) -> float:
    if hi == lo:
        return 50.0
    score = (value - lo) / (hi - lo) * 100.0
    if invert:
        score = 100.0 - score
    return max(0.0, min(100.0, score))


def score_growth(rows: list[dict]) -> list[dict]:
    candidates = [r for r in rows if r.get("market_cap") and (r.get("revenue_growth") or r.get("momentum_6m"))]
    rev_vals = _values(candidates, "revenue_growth")
    earn_vals = _values(candidates, "earnings_growth")
    mom_vals = _values(candidates, "momentum_6m")
    scored = []
    for r in candidates:
        parts, weights = [], []
        if isinstance(r.get("revenue_growth"), (int, float)) and rev_vals:
            parts.append(normalize(r["revenue_growth"], min(rev_vals), max(rev_vals)))
            weights.append(config.GROWTH_WEIGHTS["revenue_growth"])
        if isinstance(r.get("earnings_growth"), (int, float)) and earn_vals:
            parts.append(normalize(r["earnings_growth"], min(earn_vals), max(earn_vals)))
            weights.append(config.GROWTH_WEIGHTS["earnings_growth"])
        if isinstance(r.get("momentum_6m"), (int, float)) and mom_vals:
            parts.append(normalize(r["momentum_6m"], min(mom_vals), max(mom_vals)))
            weights.append(config.GROWTH_WEIGHTS["momentum_6m"])
        if not parts:
            continue
        score = sum(p * w for p, w in zip(parts, weights)) / sum(weights)
        scored.append(dict(r, score=round(score, 1)))
    scored.sort(key=lambda x: -x["score"])
    return scored[: config.TOP_N_PER_CATEGORY]


def score_stability(rows: list[dict]) -> list[dict]:
    candidates = [r for r in rows if isinstance(r.get("beta"), (int, float))]
    beta_vals = _values(candidates, "beta")
    vol_vals = _values(candidates, "volatility_annualized")
    div_vals = _values(candidates, "dividend_yield")
    streak_vals = _values(candidates, "dividend_streak_years")
    scored = []
    for r in candidates:
        parts, weights = [], []
        parts.append(normalize(r["beta"], min(beta_vals), max(beta_vals), invert=True))
        weights.append(config.STABILITY_WEIGHTS["low_beta"])
        if isinstance(r.get("volatility_annualized"), (int, float)) and vol_vals:
            parts.append(normalize(r["volatility_annualized"], min(vol_vals), max(vol_vals), invert=True))
            weights.append(config.STABILITY_WEIGHTS["low_volatility"])
        if isinstance(r.get("dividend_yield"), (int, float)) and div_vals:
            parts.append(normalize(r["dividend_yield"], min(div_vals), max(div_vals)))
            weights.append(config.STABILITY_WEIGHTS["dividend_yield"])
        if isinstance(r.get("dividend_streak_years"), (int, float)) and streak_vals:
            parts.append(normalize(r["dividend_streak_years"], min(streak_vals), max(streak_vals)))
            weights.append(config.STABILITY_WEIGHTS["dividend_streak"])
        score = sum(p * w for p, w in zip(parts, weights)) / sum(weights)
        scored.append(dict(r, score=round(score, 1)))
    scored.sort(key=lambda x: -x["score"])
    return scored[: config.TOP_N_PER_CATEGORY]


def score_nextgen(rows: list[dict]) -> list[dict]:
    watchlist = set(config.NEXT_GEN_WATCHLIST)
    candidates = [
        r for r in rows
        if r["ticker"] in watchlist
        or (r.get("market_cap") and r["market_cap"] < 50_000_000_000 and (r.get("revenue_growth") or 0) > 0.3)
    ]
    rev_vals = _values(candidates, "revenue_growth")
    mom_vals = _values(candidates, "momentum_6m")
    scored = []
    for r in candidates:
        parts, weights = [], []
        if isinstance(r.get("revenue_growth"), (int, float)) and rev_vals:
            parts.append(normalize(r["revenue_growth"], min(rev_vals), max(rev_vals)))
            weights.append(config.NEXTGEN_WEIGHTS["revenue_growth"])
        if isinstance(r.get("momentum_6m"), (int, float)) and mom_vals:
            parts.append(normalize(r["momentum_6m"], min(mom_vals), max(mom_vals)))
            weights.append(config.NEXTGEN_WEIGHTS["momentum_6m"])
        thematic_bonus = 100.0 if r["ticker"] in watchlist else 40.0
        parts.append(thematic_bonus)
        weights.append(config.NEXTGEN_WEIGHTS["thematic_bonus"])
        if not parts:
            continue
        score = sum(p * w for p, w in zip(parts, weights)) / sum(weights)
        scored.append(dict(r, score=round(score, 1)))
    scored.sort(key=lambda x: -x["score"])
    return scored[: config.TOP_N_PER_CATEGORY]


def score_shorts(rows: list[dict]) -> list[dict]:
    candidates = [r for r in rows if isinstance(r.get("short_pct_float"), (int, float))]
    short_vals = _values(candidates, "short_pct_float")
    mom_vals = _values(candidates, "momentum_6m")
    peg_vals = _values(candidates, "peg_ratio")
    scored = []
    for r in candidates:
        parts, weights = [], []
        parts.append(normalize(r["short_pct_float"], min(short_vals), max(short_vals)))
        weights.append(config.SHORT_WEIGHTS["short_pct_float"])
        if isinstance(r.get("momentum_6m"), (int, float)) and mom_vals:
            parts.append(normalize(r["momentum_6m"], min(mom_vals), max(mom_vals), invert=True))
            weights.append(config.SHORT_WEIGHTS["negative_momentum"])
        if isinstance(r.get("peg_ratio"), (int, float)) and peg_vals and r["peg_ratio"] > 0:
            parts.append(normalize(r["peg_ratio"], min(peg_vals), max(peg_vals)))
            weights.append(config.SHORT_WEIGHTS["high_peg"])
        if isinstance(r.get("earnings_growth"), (int, float)) and r["earnings_growth"] < 0:
            parts.append(80.0)
            weights.append(config.SHORT_WEIGHTS["earnings_miss"])
        score = sum(p * w for p, w in zip(parts, weights)) / sum(weights)
        scored.append(dict(r, score=round(score, 1)))
    scored.sort(key=lambda x: -x["score"])
    return scored[: config.TOP_N_PER_CATEGORY]


def main():
    with open(os.path.join(config.DATA_DIR, "market_data.json")) as f:
        market_data = json.load(f)
    rows = list(market_data.values())

    result = dict(
        growth=score_growth(rows),
        stability=score_stability(rows),
        nextgen=score_nextgen(rows),
        shorts=score_shorts(rows),
    )

    out_path = os.path.join(config.DATA_DIR, "scores.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    for category, items in result.items():
        print(f"{category}: {len(items)} ranked tickers")


if __name__ == "__main__":
    main()
