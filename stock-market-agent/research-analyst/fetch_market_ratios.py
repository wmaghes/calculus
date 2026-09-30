"""Pulls current price and valuation ratios per ticker via yfinance (free,
no API key). Writes data/ratios_<TICKER>.json.
"""

import json
import os
import time

import yfinance as yf

import config


def fetch_one(ticker: str) -> dict:
    info = yf.Ticker(ticker).info or {}
    return dict(
        ticker=ticker,
        price=info.get("currentPrice") or info.get("regularMarketPrice"),
        market_cap=info.get("marketCap"),
        trailing_pe=info.get("trailingPE"),
        forward_pe=info.get("forwardPE"),
        price_to_book=info.get("priceToBook"),
        price_to_sales=info.get("priceToSalesTrailing12Months"),
        peg_ratio=info.get("pegRatio"),
        dividend_yield=info.get("dividendYield"),
        beta=info.get("beta"),
        fifty_two_week_low=info.get("fiftyTwoWeekLow"),
        fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
        eps_trailing=info.get("trailingEps"),
        eps_forward=info.get("forwardEps"),
        return_on_equity=info.get("returnOnEquity"),
        profit_margin=info.get("profitMargins"),
        debt_to_equity=info.get("debtToEquity"),
    )


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    for ticker in config.COMPANIES:
        try:
            ratios = fetch_one(ticker)
        except Exception as exc:
            print(f"[warn] ratios for {ticker}: {exc}")
            continue
        out_path = os.path.join(config.DATA_DIR, f"ratios_{ticker}.json")
        with open(out_path, "w") as f:
            json.dump(ratios, f, indent=2)
        print(f"wrote {out_path}")
        time.sleep(0.2)


if __name__ == "__main__":
    main()
