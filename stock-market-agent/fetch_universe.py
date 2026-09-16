"""Builds the scan universe: S&P 500 + Nasdaq-100 constituents, plus the
next-gen growth watchlist. Requires outbound internet access to Wikipedia.
"""

import json
import os

import pandas as pd

import config


def fetch_sp500() -> list[str]:
    tables = pd.read_html(config.SP500_WIKI_URL)
    df = tables[0]
    return sorted(df["Symbol"].str.replace(".", "-", regex=False).tolist())


def fetch_nasdaq100() -> list[str]:
    tables = pd.read_html(config.NASDAQ100_WIKI_URL)
    for table in tables:
        if "Ticker" in table.columns:
            return sorted(table["Ticker"].str.replace(".", "-", regex=False).tolist())
        if "Symbol" in table.columns:
            return sorted(table["Symbol"].str.replace(".", "-", regex=False).tolist())
    raise ValueError("Could not find a ticker column in Nasdaq-100 tables")


def build_universe() -> list[str]:
    tickers = set(fetch_sp500()) | set(fetch_nasdaq100()) | set(config.NEXT_GEN_WATCHLIST)
    return sorted(tickers)


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    universe = build_universe()
    out_path = os.path.join(config.DATA_DIR, "universe.json")
    with open(out_path, "w") as f:
        json.dump(universe, f, indent=2)
    print(f"Wrote {len(universe)} tickers to {out_path}")


if __name__ == "__main__":
    main()
