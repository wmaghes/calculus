"""Pulls the latest annual (10-K) figures for each company from SEC EDGAR's
free XBRL company-facts API (no API key required, but requires a real
outbound internet connection with a descriptive User-Agent header per SEC's
fair-access policy). Writes data/facts_<TICKER>.json.
"""

import json
import os
import time

import requests

import config


def load_ticker_to_cik() -> dict:
    resp = requests.get(config.SEC_TICKER_MAP_URL, headers={"User-Agent": config.SEC_USER_AGENT})
    resp.raise_for_status()
    rows = resp.json().values()
    return {row["ticker"].upper(): row["cik_str"] for row in rows}


def latest_annual_value(fact: dict) -> dict | None:
    """Picks the most recent 10-K (form=='10-K', duration ~1 year) value."""
    best = None
    for unit_values in fact.get("units", {}).values():
        for entry in unit_values:
            if entry.get("form") != "10-K":
                continue
            if entry.get("fp") != "FY":
                continue
            if best is None or entry["end"] > best["end"]:
                best = entry
    if best is None:
        return None
    return dict(value=best["val"], fiscal_year=best.get("fy"), period_end=best["end"], unit=best.get("uom", "USD"))


def fetch_company_facts(cik: int) -> dict:
    url = config.SEC_COMPANY_FACTS_URL.format(cik=cik)
    resp = requests.get(url, headers={"User-Agent": config.SEC_USER_AGENT})
    resp.raise_for_status()
    return resp.json()


def extract_facts(company_facts: dict) -> dict:
    gaap = company_facts.get("facts", {}).get("us-gaap", {})
    out = {}
    for tag in config.FACT_TAGS:
        fact = gaap.get(tag)
        if fact:
            value = latest_annual_value(fact)
            if value:
                out[tag] = value
    return out


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    ticker_to_cik = load_ticker_to_cik()

    for ticker in config.COMPANIES:
        cik = ticker_to_cik.get(ticker)
        if cik is None:
            print(f"[warn] no CIK found for {ticker}")
            continue
        try:
            company_facts = fetch_company_facts(cik)
            facts = extract_facts(company_facts)
        except Exception as exc:
            print(f"[warn] 10-K facts for {ticker}: {exc}")
            continue

        out_path = os.path.join(config.DATA_DIR, f"facts_{ticker}.json")
        with open(out_path, "w") as f:
            json.dump(dict(ticker=ticker, cik=cik, facts=facts), f, indent=2)
        print(f"wrote {out_path}")
        time.sleep(0.2)  # stay within SEC's fair-access rate limit


if __name__ == "__main__":
    main()
