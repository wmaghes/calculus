"""Orchestrates a full scan: universe -> market data -> news -> scores ->
dashboard. Intended to be run on a schedule (cron, GitHub Actions, etc.)
from an environment with normal outbound internet access.
"""

import fetch_market_data
import fetch_news
import fetch_universe
import generate_dashboard
import scoring


def main():
    fetch_universe.main()
    fetch_market_data.main()
    fetch_news.main()
    scoring.main()
    generate_dashboard.main()


if __name__ == "__main__":
    main()
