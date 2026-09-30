"""Company universe and output paths for the research analyst agent.

Reuses the same watchlist as the market scanner (../config.py
NEXT_GEN_WATCHLIST plus the scanner's growth/stability/short names) so the
two tools stay consistent, grouped here by research category instead of
scanner category.
"""

import os

BASE_DIR = os.path.dirname(__file__)
AGENT_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
RESEARCH_DIR = os.path.join(AGENT_DIR, "dashboard", "research")

# ticker -> full company name, used for page titles and SEC CIK lookup.
COMPANIES = {
    # Growth
    "NVDA": "NVIDIA Corporation",
    "META": "Meta Platforms, Inc.",
    "SHOP": "Shopify Inc.",
    "PLTR": "Palantir Technologies Inc.",
    "DELL": "Dell Technologies Inc.",
    "AVGO": "Broadcom Inc.",
    "SNDK": "SanDisk Corporation",
    "AAOI": "Applied Optoelectronics, Inc.",
    # Stability
    "MCD": "McDonald's Corporation",
    "PG": "The Procter & Gamble Company",
    "IBM": "International Business Machines Corporation",
    "XOM": "Exxon Mobil Corporation",
    "KO": "The Coca-Cola Company",
    "JNJ": "Johnson & Johnson",
    "WMT": "Walmart Inc.",
    "PEP": "PepsiCo, Inc.",
    # Next-gen growth
    "RKLB": "Rocket Lab Corporation",
    "IONQ": "IonQ, Inc.",
    "TEM": "Tempus AI, Inc.",
    "IREN": "IREN Limited",
    "QBTS": "D-Wave Quantum Inc.",
    "RGTI": "Rigetti Computing, Inc.",
    "CRSP": "CRISPR Therapeutics AG",
    "RXRX": "Recursion Pharmaceuticals, Inc.",
    # Short candidates
    "OSIS": "OSI Systems, Inc.",
    "INDI": "indie Semiconductor, Inc.",
    "UA": "Under Armour, Inc.",
    "KSS": "Kohl's Corporation",
    "SMCI": "Super Micro Computer, Inc.",
    "TMDX": "TransMedics Group, Inc.",
    "LULU": "lululemon athletica inc.",
    "CPB": "The Campbell's Company",
}

# SEC requires a descriptive User-Agent identifying the requester.
SEC_USER_AGENT = "stock-market-agent research tool contact@example.com"
SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# XBRL us-gaap tags pulled from the latest 10-K for the financials page.
FACT_TAGS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "CostOfRevenue",
    "GrossProfit",
    "OperatingIncomeLoss",
    "NetIncomeLoss",
    "Assets",
    "Liabilities",
    "StockholdersEquity",
    "CashAndCashEquivalentsAtCarryingValue",
    "LongTermDebtNoncurrent",
    "ResearchAndDevelopmentExpense",
]
