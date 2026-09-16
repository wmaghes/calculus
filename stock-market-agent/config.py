"""Universe definition and scoring thresholds for the stock scanner."""

import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "dashboard")

SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NASDAQ100_WIKI_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"

# Thematic tickers for "next generation growth" (AI infra, quantum computing,
# gene editing, space, robotics). Kept as an explicit watchlist because these
# themes cut across index membership and market cap, and mixing them into a
# blind index scan would bury them under mega-caps.
NEXT_GEN_WATCHLIST = [
    "IONQ", "RGTI", "QBTS", "IREN", "RXRX", "RKLB", "TEM", "CRSP",
    "ACHR", "JOBY", "SMR", "OKLO", "CRWV", "SOUN", "PATH", "ISRG",
]

# RSS endpoints used for the news/PR layer (no API key required).
YAHOO_TICKER_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
GOOGLE_NEWS_TICKER_RSS = "https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
PR_NEWSWIRE_RSS = "https://www.prnewswire.com/rss/financial-services-latest-news/financial-services-latest-news-list.rss"
SEC_EDGAR_FULLTEXT_RSS = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=8-K&dateb=&owner=include&count=40&search_text="

TOP_N_PER_CATEGORY = 15

# Scoring weights
GROWTH_WEIGHTS = dict(revenue_growth=0.45, earnings_growth=0.35, momentum_6m=0.20)
STABILITY_WEIGHTS = dict(low_beta=0.35, low_volatility=0.30, dividend_yield=0.15, dividend_streak=0.20)
NEXTGEN_WEIGHTS = dict(revenue_growth=0.55, momentum_6m=0.20, thematic_bonus=0.25)
SHORT_WEIGHTS = dict(short_pct_float=0.45, negative_momentum=0.25, high_peg=0.15, earnings_miss=0.15)
