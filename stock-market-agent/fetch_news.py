"""Pulls recent news/PR headlines per ticker from free RSS feeds
(Yahoo Finance, Google News) plus a general market-wide PR feed.
Writes data/news.json keyed by ticker -> list of {title, link, published}.
"""

import json
import os

import feedparser

import config


def fetch_ticker_news(ticker: str, limit: int = 5) -> list[dict]:
    items = []
    for url in (
        config.YAHOO_TICKER_RSS.format(ticker=ticker),
        config.GOOGLE_NEWS_TICKER_RSS.format(ticker=ticker),
    ):
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit]:
            items.append(dict(
                title=entry.get("title"),
                link=entry.get("link"),
                published=entry.get("published"),
                source=feed.feed.get("title", url),
            ))
    return items[:limit]


def fetch_market_news(limit: int = 20) -> list[dict]:
    feed = feedparser.parse(config.PR_NEWSWIRE_RSS)
    return [
        dict(title=e.get("title"), link=e.get("link"), published=e.get("published"))
        for e in feed.entries[:limit]
    ]


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    universe_path = os.path.join(config.DATA_DIR, "universe.json")
    with open(universe_path) as f:
        universe = json.load(f)

    news = {}
    for ticker in universe:
        try:
            news[ticker] = fetch_ticker_news(ticker)
        except Exception as exc:
            print(f"[warn] news for {ticker}: {exc}")
            news[ticker] = []

    out_path = os.path.join(config.DATA_DIR, "news.json")
    with open(out_path, "w") as f:
        json.dump(dict(per_ticker=news, market=fetch_market_news()), f, indent=2)
    print(f"Wrote news for {len(news)} tickers to {out_path}")


if __name__ == "__main__":
    main()
