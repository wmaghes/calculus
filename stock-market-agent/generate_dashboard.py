"""Combines scores.json + news.json into dashboard/data.json, the single
file the static dashboard/index.html fetches and renders.
"""

import datetime
import json
import os

import config


def latest_headline(news_per_ticker: dict, ticker: str) -> dict | None:
    items = news_per_ticker.get(ticker) or []
    return items[0] if items else None


def main():
    with open(os.path.join(config.DATA_DIR, "scores.json")) as f:
        scores = json.load(f)
    news_path = os.path.join(config.DATA_DIR, "news.json")
    news = dict(per_ticker={}, market=[])
    if os.path.exists(news_path):
        with open(news_path) as f:
            news = json.load(f)

    def enrich(rows):
        out = []
        for r in rows:
            headline = latest_headline(news["per_ticker"], r["ticker"])
            out.append(dict(r, headline=headline))
        return out

    dashboard_data = dict(
        generated=datetime.datetime.utcnow().isoformat() + "Z",
        categories=dict(
            growth=enrich(scores["growth"]),
            stability=enrich(scores["stability"]),
            nextgen=enrich(scores["nextgen"]),
            shorts=enrich(scores["shorts"]),
        ),
        market_news=news.get("market", [])[:10],
    )

    os.makedirs(config.DASHBOARD_DIR, exist_ok=True)
    out_path = os.path.join(config.DASHBOARD_DIR, "data.json")
    with open(out_path, "w") as f:
        json.dump(dashboard_data, f, indent=2)
    print(f"Wrote dashboard data to {out_path}")


if __name__ == "__main__":
    main()
