"""One-off assembly of research data gathered via WebSearch in this sandbox
(no direct SEC EDGAR / yfinance access here -- see fetch_10k.py and
fetch_market_ratios.py for the real, unrestricted-network pipeline this
replaces). Writes data/research_data.json, consumed by
generate_research_pages.py.

Every entry keeps a `source_note` describing where the figure came from and
a `period` string; anything not confidently found is left as None rather
than guessed, and generate_research_pages.py renders those as "n/a".
"""

import json
import os

import config

# financials: pulled from each company's most recent 10-K (or best full-year
# figure found). Units: revenue/income/assets/debt in USD, margins in %.
FINANCIALS = {
    "NVDA": dict(period="FY2026 (ended Jan 25, 2026)", revenue="$215.9B", revenue_growth=65.0,
                 gross_margin=71.1, net_income="$120.1B", net_income_growth=65.0,
                 total_assets="$206.8B", total_debt="$12.03B",
                 note="Gross margin fell 3.9pp YoY on the Hopper-to-Blackwell transition and a $4.5B H20 inventory charge.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm"),
    "META": dict(period="FY2025 (ended Dec 31, 2025)", revenue="$200.97B", revenue_growth=None,
                 gross_margin=82.0, net_income="$60.46B", net_income_margin=30.08,
                 total_assets="$366.02B", total_debt="$28.83B (FY2024)",
                 note="Total liabilities were $148.78B against $366.02B in total assets.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1326801/000162828026003942/meta-20251231.htm"),
    "SHOP": dict(period="FY2025 (ended Dec 31, 2025)", revenue="$11,556M", revenue_growth=30.0,
                 gross_margin=48.0, net_income="$1,231M", net_income_growth=None,
                 total_assets=None, total_debt=None,
                 note="Net income was down from $2,019M the prior year, mainly on losses in equity/equity-method investments; operating income rose to $1,468M.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1594805/000159480526000007/shop-20251231.htm"),
    "PLTR": dict(period="FY2025 (ended Dec 31, 2025)", revenue="$4.48B", revenue_growth=56.2,
                 gross_margin=None, net_income="$1.63B", net_income_growth=None,
                 total_assets="$8.90B", total_debt=None,
                 note="Total liabilities were $1.41B, giving a very light balance sheet relative to assets.",
                 source_url="https://investors.palantir.com/files/2025%20FY%20PLTR%2010-K.pdf"),
    "DELL": dict(period="FY2026 (ended ~Jan 2026)", revenue="$113.5B", revenue_growth=18.8,
                 gross_margin=None, net_income="$5.94B", net_income_growth=None,
                 total_assets="$101.3B", total_debt="$25.99B (FY2024 figure)",
                 note="AI-optimized server backlog was the main growth driver cited in recent quarters.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1571996/000157199624000036/dell-20240202.htm"),
    "AVGO": dict(period="FY2025 (ended ~Nov 2025)", revenue="$63.89B", revenue_growth=23.9,
                 gross_margin=68.0, net_income="$23.13B", net_income_growth=None,
                 total_assets="$171.1B", total_debt="$67.97B",
                 note="Gross profit of $43.29B, up from $32.51B in FY2024.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1730168/000173016825000121/avgo-20251102.htm"),
    "SNDK": dict(period="FY2025 (partial year, spun off from Western Digital Feb 21, 2025)", revenue="$7.36B", revenue_growth=None,
                 gross_margin=None, net_income="-$1.64B (loss)", net_income_growth=None,
                 total_assets="$12.99B", total_debt=None,
                 note="Newly independent public company as of Feb 2025 (pro rata spinoff of 80.1% of shares); first full fiscal year is still shaking out post-separation.",
                 source_url="https://investor.sandisk.com/"),
    "AAOI": dict(period="FY2025 (ended Dec 31, 2025)", revenue="$455.7M", revenue_growth=98.0,
                 gross_margin=None, net_income="Unprofitable (net loss)", net_income_growth=None,
                 total_assets=None, total_debt=None,
                 note="Revenue nearly doubled on AI-datacenter optics demand, but the company remains unprofitable.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1158114/000143774925005575/aaoi20241231_10k.htm"),
    "MCD": dict(period="FY2025 (ended Dec 31, 2025)", revenue="$26.9B", revenue_growth=4.0,
                 gross_margin=None, net_income="$8.6B", net_income_growth=None,
                 total_assets=None, total_debt="$40.0B",
                 note="Revenue growth was +2% in constant currency; franchise model keeps reported revenue small relative to system-wide sales.",
                 source_url="https://www.sec.gov/Archives/edgar/data/63908/000006390826000035/mcd-20251231.htm"),
    "PG": dict(period="FY2026 (ended ~Jun 2026)", revenue="$87.0B", revenue_growth=3.0,
               gross_margin=50.0, net_income="$16.1B", net_income_growth=None,
               total_assets=None, total_debt="$37.0B",
               note="Total debt of $37.0B against $12.3B cash, a net debt position of roughly $24.7B; operating cash flow was $19.6B.",
               source_url="https://www.sec.gov/Archives/edgar/data/0000080424/000008042426000103/pg-20260630.htm"),
    "IBM": dict(period="FY2025 (ended Dec 31, 2025)", revenue="$67.5B", revenue_growth=None,
                gross_margin=60.6, net_income="$10.6B (continuing ops)", net_income_growth=None,
                total_assets="$151.88B", total_debt="$61.3B",
                note="Total assets rose $14.7B YoY; free cash flow was $14.7B, up $2.0B YoY.",
                source_url="https://www.sec.gov/Archives/edgar/data/51143/000005114326000010/ibm-20251231_d2.htm"),
    "XOM": dict(period="FY2025 (ended Dec 31, 2025)", revenue="$323.91B", revenue_growth=-4.5,
                gross_margin=None, net_income="$28.8B", net_income_growth=None,
                total_assets="$448.98B", total_debt="$43.5B",
                note="Revenue declined from $339.25B in 2024; long-term debt alone was $34.24B.",
                source_url="https://www.sec.gov/Archives/edgar/data/34088/000003408826000045/xom-20251231.htm"),
    "KO": dict(period="FY2025 (ended Dec 31, 2025)", revenue="$47.94B", revenue_growth=None,
               gross_margin=61.6, net_income="$13.11B", net_income_growth=None,
               total_assets="$104.82B", total_debt="$39.15B",
               note="Gross profit of $29.54B on improved production-cost efficiency.",
               source_url="https://www.sec.gov/Archives/edgar/data/21344/000162828026010047/ko-20251231.htm"),
    "JNJ": dict(period="FY2025 (ended Dec 28, 2025)", revenue="$94.2B", revenue_growth=6.0,
                gross_margin=None, net_income=None, net_income_growth=None,
                total_assets="$199.21B", total_debt=None,
                note="Sales growth was led by Innovative Medicine (Oncology: DARZALEX, ERLEADA) and MedTech (Abiomed, Shockwave); total assets up from $180.10B a year earlier.",
                source_url="https://www.sec.gov/Archives/edgar/data/200406/000020040626000016/jnj-20251228.htm"),
    "WMT": dict(period="FY2026 (ended Jan 31, 2026)", revenue="$713.2B", revenue_growth=None,
                gross_margin=None, net_income="$22.27B", net_income_growth=None,
                total_assets="$260.82B (Q2 FY26)", total_debt=None,
                note="Operating income was $29.8B (4.2% margin); total liabilities were $173.98B as of the same quarter.",
                source_url="https://www.sec.gov/Archives/edgar/data/104169/000010416926000055/wmt-20260131.htm"),
    "PEP": dict(period="FY2025 (ended Dec 27, 2025)", revenue="$93.93B", revenue_growth=2.0,
                gross_margin=None, net_income="$8.24B", net_income_growth=None,
                total_assets="$107.40B", total_debt=None,
                note="Total liabilities were $86.85B; the company issued $8.2B in long-term debt while repaying $4.1B during the year.",
                source_url="https://www.sec.gov/Archives/edgar/data/77476/000007747626000007/pep-20251227.htm"),
    "RKLB": dict(period="FY2025 (ended Dec 31, 2025)", revenue="$601.8M", revenue_growth=None,
                 gross_margin=34.4, net_income="Net loss (continuing)", net_income_growth=None,
                 total_assets=None, total_debt=None,
                 note="Still loss-making as it scales Neutron and integrates recent acquisitions (Mynaric, pending Iridium deal).",
                 source_url="https://www.sec.gov/Archives/edgar/data/1819994/000181999426000013/rklb-20251231.htm"),
    "IONQ": dict(period="FY2025 (ended Dec 31, 2025)", revenue="$130.0M", revenue_growth=201.9,
                 gross_margin=None, net_income="-$510.4M (loss)", net_income_growth=None,
                 total_assets="$6.57B", total_debt=None,
                 note="Total assets roughly equal total equity -- a very low-leverage, cash-rich balance sheet typical of a recently-funded growth name.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1824920/000119312526071562/ionq-20251231.htm"),
    "TEM": dict(period="FY2025 (ended Dec 31, 2025)", revenue="~$1.27B (Q4 rev. $367.2M, +83% YoY)", revenue_growth=83.0,
                gross_margin=None, net_income=None, net_income_growth=None,
                total_assets=None, total_debt=None,
                note="Q4 organic growth (ex-Ambry) was 33.5%; full balance-sheet detail wasn't available in this pass.",
                source_url="https://last10k.com/sec-filings/tem/0001193125-26-066961.htm"),
    "IREN": dict(period="FY2026 (ended Jun 30, 2026)", revenue=None, revenue_growth=None,
                 gross_margin=None, net_income=None, net_income_growth=None,
                 total_assets=None, total_debt=None,
                 note="Aggregate market value held by non-affiliates was ~$11.9B as of Dec 31, 2025; detailed income-statement figures weren't available in this pass.",
                 source_url="https://www.sec.gov/Archives/edgar/data/0001878848/000187884826000052/iren-20260630.htm"),
    "QBTS": dict(period="FY2025 (ended Dec 31, 2025)", revenue=None, revenue_growth=179.0,
                 gross_margin=None, net_income=None, net_income_growth=None,
                 total_assets=None, total_debt=None,
                 note="Revenue +179% YoY and gross profit +265% YoY; ended 2025 with over $884M in liquidity, the strongest cash position in company history.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1907982/000190798225000060/qbts-20241231.htm"),
    "RGTI": dict(period="FY2025 (ended Dec 31, 2025)", revenue="$7.1M", revenue_growth=-34.3,
                 gross_margin=None, net_income="-$216.2M (loss)", net_income_growth=None,
                 total_assets=None, total_debt=None,
                 note="Trailing-twelve-month revenue through Jun 2026 was $13.4M, up 68.5% -- growth reaccelerated after a down FY2025.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1838359/000110465926023454/rgti-20251231x10k.htm"),
    "CRSP": dict(period="FY2025 (ended Dec 31, 2025)", revenue="$3.51M (collab/grant revenue)", revenue_growth=None,
                 gross_margin=None, net_income="-$581.6M (loss)", net_income_growth=None,
                 total_assets=None, total_debt=None,
                 note="CASGEVY product revenue ($116M for the year, $54M in Q4) is reported separately from collaboration revenue; cash & marketable securities were $1.98B.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1674416/000119312526048957/crsp-20251231.htm"),
    "RXRX": dict(period="FY2025 (ended Dec 31, 2025)", revenue="$74.68M", revenue_growth=None,
                 gross_margin=None, net_income="-$644.76M (loss)", net_income_growth=None,
                 total_assets=None, total_debt=None,
                 note="Cash and cash equivalents were roughly $785M as of Oct 9, 2025, funding continued AI drug-discovery R&D.",
                 source_url="https://ir.recursion.com/"),
    "OSIS": dict(period="FY2025 (ended ~Jun 2025)", revenue="$1,713.2M", revenue_growth=11.3,
                 gross_margin=34.3, net_income="$149.6M", net_income_growth=None,
                 total_assets=None, total_debt=None,
                 note="Net profit margin 8.7%; debt-to-equity ratio of 0.49 is comparatively low leverage for the group.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1039065/000110465925104478/osis-20250930x10q.htm"),
    "INDI": dict(period="FY2025 (ended Dec 31, 2025)", revenue=None, revenue_growth=None,
                 gross_margin=None, net_income="-$150.7M (loss)", net_income_growth=None,
                 total_assets=None, total_debt=None,
                 note="FY2024 revenue was $216.7M, down 3% from $223.2M in FY2023; still unprofitable.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1841925/000119312526082535/indi-20251231.htm"),
    "UA": dict(period="Trailing 12 months", revenue="$4.97B", revenue_growth=None,
               gross_margin=45.5, net_income="-$495.6M (loss)", net_income_growth=None,
               total_assets=None, total_debt="$1.94B",
               note="Net cash position is roughly -$1.63B ($ -3.82/share); turnaround remains a work in progress.",
               source_url="https://www.sec.gov/Archives/edgar/data/1336917/"),
    "KSS": dict(period="FY2025 (ended Jan 31, 2026)", revenue=None, revenue_growth=-4.0,
                gross_margin=33.1, net_income="$125M", net_income_growth=None,
                total_assets=None, total_debt="$1.44B",
                note="Full-year net sales fell 4.0% and comparable sales fell 3.1%; total debt rose 22.3% YoY.",
                source_url="https://investors.kohls.com/"),
    "SMCI": dict(period="FY2025 (ended Jun 30, 2025)", revenue="$21.97B", revenue_growth=None,
                 gross_margin=11.1, net_income="$1.05B", net_income_growth=None,
                 total_assets=None, total_debt="$4.8B",
                 note="Cash and cash equivalents were $5.2B against $4.8B in bank debt and convertible notes.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1375365/000137536525000027/smci-20250630.htm"),
    "TMDX": dict(period="FY2024 (ended Dec 31, 2024)", revenue="$441.5M", revenue_growth=None,
                 gross_margin=59.0, net_income="$35.5M", net_income_growth=None,
                 total_assets=None, total_debt=None,
                 note="Gross profit of $262.1M on a 59% margin.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1756262/"),
    "LULU": dict(period="FY2024 (ended Feb 2, 2025)", revenue="$10.6B", revenue_growth=10.0,
                 gross_margin=59.2, net_income=None, net_income_growth=None,
                 total_assets=None, total_debt=None,
                 note="Gross profit +12% to $6.3B; operating income +17% to $2.5B. Guidance has since been cut twice for the current fiscal year.",
                 source_url="https://www.sec.gov/Archives/edgar/data/1397187/000139718725000013/lulu-20250202.htm"),
    "CPB": dict(period="FY2025 (ended Aug 3, 2025)", revenue="$10.25B", revenue_growth=6.0,
                gross_margin=None, net_income="$602M", net_income_growth=None,
                total_assets="$14.90B", total_debt="$6.86B",
                note="Growth included an 8-point benefit from the Sovos Brands acquisition and a 2-point benefit from a 53rd week.",
                source_url="https://www.sec.gov/Archives/edgar/data/16732/000001673225000112/cpb-20250803.htm"),
}

# ratios not already tracked in the market scanner's dashboard/data.json
# (P/E, P/B, P/S, PEG, 52-week range). Price/market cap/beta/dividend yield
# are pulled from that file at generation time instead of duplicated here.
RATIOS = {
    "NVDA": dict(trailing_pe=28.79, forward_pe=25.64, week52_low=164.27, week52_high=236.54),
    "META": dict(trailing_pe=27.38, forward_pe=22.16),
    "SHOP": dict(trailing_pe=95.76, forward_pe=67.82),
    "PLTR": dict(trailing_pe=160.34, forward_pe=98.85, week52_low=106.37, week52_high=207.52),
    "DELL": dict(trailing_pe=33.57, forward_pe=20.44, week52_low=110.22, week52_high=595.51),
    "AVGO": dict(trailing_pe=45.03, price_to_book=17.46, price_to_sales=19.02, week52_low=289.96, week52_high=495.00),
    "SNDK": dict(trailing_pe=24.63, price_to_book=16.74, price_to_sales=13.36, week52_low=112.00, week52_high=2354.0),
    "AAOI": dict(trailing_pe=None, price_to_book=-2.87, price_to_sales=3.32, week52_low=9.71, week52_high=128.96,
                 note="P/E is negative/n.m. -- the company is unprofitable."),
    "MCD": dict(trailing_pe=19.13, price_to_book=6.45, week52_low=234.03, week52_high=341.75),
    "PG": dict(trailing_pe=22.20, price_to_book=6.32, week52_low=137.62, week52_high=179.99),
    "IBM": dict(trailing_pe=21.71, price_to_book=7.24, price_to_sales=3.11, week52_low=214.50, week52_high=324.90),
    "XOM": dict(trailing_pe=21.42, price_to_book=2.53, week52_low=105.30, week52_high=174.09),
    "KO": dict(trailing_pe=26.95, price_to_sales=7.22, week52_low=65.35, week52_high=81.69),
    "JNJ": dict(trailing_pe=31.10, price_to_book=7.4, price_to_sales=6.2, week52_low=179.80, week52_high=281.07),
    "WMT": dict(trailing_pe=38.68, forward_pe=35.58, price_to_book=8.55, week52_low=77.49, week52_high=105.30,
                note="52-week low/high look stale next to the current ~$108 price -- worth a live-quote check."),
    "PEP": dict(trailing_pe=17.00, price_to_book=2.67, price_to_sales=2.08, week52_low=129.55, week52_high=171.48),
    "RKLB": dict(price_to_sales=65.66, week52_low=37.57, week52_high=151.00,
                 note="PS ratio is 208% above its 10-year median (21.31) -- priced for a lot of future growth."),
    "IONQ": dict(price_to_sales=6.75, week52_low=21.36, week52_high=84.64),
    "TEM": dict(week52_low=40.77, week52_high=104.32),
    "IREN": dict(trailing_pe=39.69, week52_low=5.13, week52_high=76.87),
    "QBTS": dict(week52_low=12.75, week52_high=46.75),
    "RGTI": dict(week52_low=6.86, week52_high=58.15),
    "RXRX": dict(week52_low=2.77, week52_high=7.18),
    "OSIS": dict(trailing_pe=30.40, week52_low=164.08, week52_high=306.12),
    "KSS": dict(trailing_pe=6.49, forward_pe=10.06),
    "SMCI": dict(trailing_pe=10.99, week52_low=19.48, week52_high=58.78),
    "TMDX": dict(trailing_pe=21.68, price_to_book=5.51, week52_low=60.11, week52_high=156.00),
    "LULU": dict(trailing_pe=9.72, price_to_book=2.71, week52_low=104.44, week52_high=225.98),
    "CPB": dict(trailing_pe=10.77, week52_low=29.39, week52_high=49.11),
}


def load_researched_extensions():
    """Loads data/researched_financials.json, a second batch of real 10-K
    financials/ratios gathered via WebSearch for the companies added to the
    watchlist after the original 32 (see config.py's COMPANIES comment).
    Returns (financials, ratios) dicts to merge on top of FINANCIALS/RATIOS
    above; missing file means nothing to merge (not an error).
    """
    path = os.path.join(config.DATA_DIR, "researched_financials.json")
    if not os.path.exists(path):
        return {}, {}
    with open(path) as f:
        extra = json.load(f)
    financials = {t: v["financials"] for t, v in extra.items() if v.get("financials")}
    ratios = {t: v["ratios"] for t, v in extra.items() if v.get("ratios")}
    return financials, ratios


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)

    with open(os.path.join(config.AGENT_DIR, "dashboard", "data.json")) as f:
        scanner_data = json.load(f)
    scanner_by_ticker = {}
    for items in scanner_data["categories"].values():
        for item in items:
            scanner_by_ticker[item["ticker"]] = item

    extra_financials, extra_ratios = load_researched_extensions()
    all_financials = {**FINANCIALS, **extra_financials}
    all_ratios = {**RATIOS, **extra_ratios}

    combined = {}
    for ticker, name in config.COMPANIES.items():
        combined[ticker] = dict(
            ticker=ticker,
            name=name,
            financials=all_financials.get(ticker, {}),
            ratios=all_ratios.get(ticker, {}),
            market=scanner_by_ticker.get(ticker, {}),
        )

    out_path = os.path.join(config.DATA_DIR, "research_data.json")
    with open(out_path, "w") as f:
        json.dump(dict(generated="2026-10-10", companies=combined), f, indent=2)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
