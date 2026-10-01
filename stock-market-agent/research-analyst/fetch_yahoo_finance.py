"""Scrapes Yahoo Finance for deep per-company research data: income
statement / balance sheet / cash flow history, analyst recommendations,
institutional holders, and recent news headlines -- well beyond the handful
of valuation ratios `fetch_market_ratios.py` pulls.

Requires real internet access (this sandbox's egress is restricted and
cannot reach finance.yahoo.com -- see the "A note on this sandbox" section
of the README). Run this from a normal machine, CI runner, or server:

    pip install -r requirements.txt
    python research-analyst/fetch_yahoo_finance.py

Writes one JSON file per ticker to data/yahoo/<TICKER>.json plus a combined
data/yahoo_finance.json, both ready for generate_research_pages.py or any
other downstream consumer to read.
"""

import json
import os
import time

import yfinance as yf

import config

OUT_DIR = os.path.join(config.DATA_DIR, "yahoo")


def _df_to_records(df):
    """Convert a yfinance DataFrame (columns are report dates) into a list
    of {period, ...line items} dicts, newest period first, JSON-safe."""
    if df is None or df.empty:
        return []
    records = []
    for col in df.columns:
        period = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
        row = {"period": period}
        for idx, val in df[col].items():
            if val is None:
                continue
            try:
                if val != val:  # NaN
                    continue
                row[str(idx)] = float(val)
            except (TypeError, ValueError):
                continue
        records.append(row)
    return records


def _recommendations(tk):
    try:
        df = tk.recommendations
    except Exception:
        return []
    if df is None or df.empty:
        return []
    records = []
    for _, row in df.tail(8).iterrows():
        records.append({k: (int(v) if hasattr(v, "item") else v) for k, v in row.items()})
    return records


def _holders(tk):
    out = {}
    for attr, key in (("institutional_holders", "institutional"), ("major_holders", "major")):
        try:
            df = getattr(tk, attr)
        except Exception:
            df = None
        if df is None or (hasattr(df, "empty") and df.empty):
            out[key] = []
            continue
        out[key] = json.loads(df.to_json(orient="records")) if hasattr(df, "to_json") else []
    return out


def _news(tk):
    try:
        items = tk.news or []
    except Exception:
        return []
    out = []
    for item in items[:10]:
        content = item.get("content", item)  # yfinance has reshaped this payload across versions
        out.append({
            "title": content.get("title"),
            "publisher": (content.get("provider") or {}).get("displayName") if isinstance(content.get("provider"), dict) else content.get("publisher"),
            "link": (content.get("canonicalUrl") or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else content.get("link"),
            "published": content.get("pubDate") or content.get("providerPublishTime"),
        })
    return out


def fetch_one(ticker: str) -> dict:
    tk = yf.Ticker(ticker)
    info = tk.info or {}

    return {
        "ticker": ticker,
        "fetched_fields": {
            "shortName": info.get("shortName"),
            "longBusinessSummary": info.get("longBusinessSummary"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "fullTimeEmployees": info.get("fullTimeEmployees"),
            "city": info.get("city"),
            "state": info.get("state"),
            "country": info.get("country"),
            "website": info.get("website"),
        },
        "price": {
            "current": info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_day_avg": info.get("fiftyDayAverage"),
            "two_hundred_day_avg": info.get("twoHundredDayAverage"),
        },
        "valuation": {
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "peg_ratio": info.get("pegRatio"),
            "enterprise_value": info.get("enterpriseValue"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            "ev_to_revenue": info.get("enterpriseToRevenue"),
        },
        "fundamentals": {
            "revenue_ttm": info.get("totalRevenue"),
            "gross_margin": info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "profit_margin": info.get("profitMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "return_on_assets": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "free_cashflow": info.get("freeCashflow"),
            "eps_trailing": info.get("trailingEps"),
            "eps_forward": info.get("forwardEps"),
            "earnings_growth": info.get("earningsGrowth"),
            "revenue_growth": info.get("revenueGrowth"),
        },
        "dividend": {
            "yield": info.get("dividendYield"),
            "rate": info.get("dividendRate"),
            "payout_ratio": info.get("payoutRatio"),
            "ex_dividend_date": info.get("exDividendDate"),
        },
        "risk": {
            "beta": info.get("beta"),
            "short_percent_of_float": info.get("shortPercentOfFloat"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "shares_short": info.get("sharesShort"),
        },
        "analyst": {
            "recommendation_key": info.get("recommendationKey"),
            "recommendation_mean": info.get("recommendationMean"),
            "number_of_analyst_opinions": info.get("numberOfAnalystOpinions"),
            "target_mean_price": info.get("targetMeanPrice"),
            "target_high_price": info.get("targetHighPrice"),
            "target_low_price": info.get("targetLowPrice"),
            "recommendations_history": _recommendations(tk),
        },
        "financial_statements": {
            "income_statement_annual": _df_to_records(tk.financials),
            "income_statement_quarterly": _df_to_records(tk.quarterly_financials),
            "balance_sheet_annual": _df_to_records(tk.balance_sheet),
            "balance_sheet_quarterly": _df_to_records(tk.quarterly_balance_sheet),
            "cashflow_annual": _df_to_records(tk.cashflow),
            "cashflow_quarterly": _df_to_records(tk.quarterly_cashflow),
        },
        "holders": _holders(tk),
        "news": _news(tk),
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    combined = {}
    for ticker in config.COMPANIES:
        try:
            data = fetch_one(ticker)
        except Exception as exc:
            print(f"[warn] yahoo finance scrape for {ticker} failed: {exc}")
            continue
        combined[ticker] = data
        with open(os.path.join(OUT_DIR, f"{ticker}.json"), "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"scraped {ticker}")
        time.sleep(0.5)  # be polite -- this is an unofficial, unauthenticated endpoint

    with open(os.path.join(config.DATA_DIR, "yahoo_finance.json"), "w") as f:
        json.dump(combined, f, indent=2, default=str)
    print(f"wrote {len(combined)} companies to {os.path.join(config.DATA_DIR, 'yahoo_finance.json')}")


if __name__ == "__main__":
    main()
