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
# The first 32 (through XOM) have full SEC-grounded financials/ratios already
# researched; the rest were added later to widen sector/industry coverage to
# 100 names and currently carry live market data only (see research_data.json
# -- financials: null means "not yet researched", not "nothing to find").
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
    # Added for sector/industry diversity + Fortune 100 coverage (market data only so far)
    "AAPL": "Apple Inc.",
    "ABT": "Abbott Laboratories",
    "ADBE": "Adobe Inc.",
    "ADM": "Archer-Daniels-Midland",
    "AFL": "Aflac",
    "AFRM": "Affirm",
    "AI": "C3.ai",
    "AMC": "AMC Entertainment Holdings",
    "AMZN": "Amazon.com",
    "ASTS": "AST SpaceMobile",
    "BA": "The Boeing Company",
    "BEAM": "Beam Therapeutics",
    "BYND": "Beyond Meat",
    "CAT": "Caterpillar Inc.",
    "CHPT": "ChargePoint",
    "CL": "Colgate-Palmolive",
    "COST": "Costco Wholesale",
    "CRWD": "CrowdStrike",
    "CVNA": "Carvana",
    "CVX": "Chevron",
    "DE": "Deere & Company",
    "DJT": "Trump Media & Technology Group",
    "DUK": "Duke Energy",
    "ENVX": "Enovix",
    "FSLR": "First Solar",
    "FUBO": "fuboTV",
    "GE": "GE Aerospace",
    "GIS": "General Mills",
    "GME": "GameStop",
    "GOOGL": "Alphabet Inc.",
    "HON": "Honeywell",
    "HTZ": "Hertz Global Holdings",
    "JOBY": "Joby Aviation",
    "JPM": "JPMorgan Chase & Co.",
    "KMB": "Kimberly-Clark",
    "LCID": "Lucid Group",
    "LLY": "Eli Lilly and Company",
    "LUNR": "Intuitive Machines",
    "MA": "Mastercard Inc.",
    "MMM": "3M",
    "MRK": "Merck",
    "MSFT": "Microsoft Corporation",
    "NEE": "NextEra Energy",
    "NET": "Cloudflare",
    "NTLA": "Intellia Therapeutics",
    "O": "Realty Income",
    "PSKY": "Paramount Skydance Corporation",
    "PATH": "UiPath",
    "PLUG": "Plug Power",
    "PTON": "Peloton Interactive",
    "QS": "QuantumScape",
    "RIOT": "Riot Platforms",
    "RIVN": "Rivian Automotive",
    "SERV": "Serve Robotics",
    "SIRI": "Sirius XM Holdings",
    "SO": "Southern Company",
    "SOFI": "SoFi Technologies",
    "SOUN": "SoundHound AI",
    "T": "AT&T",
    "TGT": "Target",
    "TSLA": "Tesla, Inc.",
    "UNH": "UnitedHealth Group",
    "UPS": "United Parcel Service",
    "UPST": "Upstart Holdings",
    "V": "Visa Inc.",
    "VZ": "Verizon",
    "W": "Wayfair",
    "WBD": "Warner Bros. Discovery",
    # Funds & company-size comparison set (ETFs, mutual funds, small/mid-cap stocks)
    "SPY": "SPDR S&P 500 ETF Trust",
    "QQQ": "Invesco QQQ Trust",
    "IWM": "iShares Russell 2000 ETF",
    "VIG": "Vanguard Dividend Appreciation ETF",
    "AGG": "iShares Core U.S. Aggregate Bond ETF",
    "VFIAX": "Vanguard 500 Index Fund Admiral Shares",
    "FCNTX": "Fidelity Contrafund",
    "VWINX": "Vanguard Wellesley Income Fund",
    "CALM": "Cal-Maine Foods",
    "HAFC": "Hanmi Financial",
    "CHE": "Chemed Corp",
    "SAIA": "Saia Inc",
    "WING": "Wingstop",
    "UMH": "UMH Properties",
    "CEVA": "CEVA Inc",
    "REI": "Ring Energy",
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
