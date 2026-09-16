"""Pulls prices and fundamentals for the scan universe via yfinance
(free, no API key). Writes data/market_data.json keyed by ticker.
"""

import json
import os
import time

import yfinance as yf

import config


def fetch_one(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.info or {}
    hist = t.history(period="1y", interval="1d")

    momentum_6m = None
    volatility = None
    if not hist.empty and len(hist) > 5:
        closes = hist["Close"]
        if len(closes) >= 126:
            momentum_6m = float(closes.iloc[-1] / closes.iloc[-126] - 1) * 100
        returns = closes.pct_change().dropna()
        if not returns.empty:
            volatility = float(returns.std()) * (252 ** 0.5) * 100  # annualized %

    dividends = t.dividends
    dividend_streak_years = 0
    if not dividends.empty:
        years_with_dividends = sorted(set(dividends.index.year))
        streak = 0
        for y in reversed(years_with_dividends):
            if streak == 0 or y == years_with_dividends[len(years_with_dividends) - streak - 1]:
                streak += 1
            else:
                break
        dividend_streak_years = streak

    return dict(
        ticker=ticker,
        name=info.get("shortName") or info.get("longName") or ticker,
        price=info.get("currentPrice") or info.get("regularMarketPrice"),
        market_cap=info.get("marketCap"),
        sector=info.get("sector"),
        beta=info.get("beta"),
        trailing_pe=info.get("trailingPE"),
        peg_ratio=info.get("pegRatio"),
        dividend_yield=info.get("dividendYield"),
        dividend_streak_years=dividend_streak_years,
        revenue_growth=info.get("revenueGrowth"),
        earnings_growth=info.get("earningsGrowth"),
        short_pct_float=info.get("shortPercentOfFloat"),
        momentum_6m=momentum_6m,
        volatility_annualized=volatility,
    )


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    universe_path = os.path.join(config.DATA_DIR, "universe.json")
    with open(universe_path) as f:
        universe = json.load(f)

    results = {}
    for i, ticker in enumerate(universe):
        try:
            results[ticker] = fetch_one(ticker)
        except Exception as exc:  # yfinance/network hiccups on individual tickers
            print(f"[warn] {ticker}: {exc}")
        if i % 20 == 0:
            print(f"...{i}/{len(universe)}")
        time.sleep(0.3)  # be polite to the free endpoint

    out_path = os.path.join(config.DATA_DIR, "market_data.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Wrote market data for {len(results)} tickers to {out_path}")


if __name__ == "__main__":
    main()
