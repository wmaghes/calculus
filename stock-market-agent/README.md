# Stock Market Scanner Agent

Scans the market and the web for prices, growth/fundamentals, and news/PR,
then scores every ticker into four dashboards:

- **Biggest Growth** — fastest revenue/earnings growth and momentum, large & mid cap.
- **Stability** — low beta, dividend-consistent, low-volatility names.
- **Next-Gen Growth** — thematic, earlier-stage bets (AI infra, quantum computing,
  gene editing, space, robotics) with outsized upside and outsized risk.
- **Short Candidates** — highest short interest and clearest negative catalysts
  (guidance cuts, structural decline).

Output is a static dashboard at `dashboard/index.html` + `dashboard/data.json`.
Open `dashboard/index.html` directly in a browser (it fetches `./data.json`),
or host the `dashboard/` folder anywhere static (GitHub Pages, S3, etc.).

## How it works

| Script | Purpose |
|---|---|
| `fetch_universe.py` | Builds the scan universe: S&P 500 + Nasdaq-100 constituents (scraped from Wikipedia) plus a curated next-gen growth watchlist (`config.NEXT_GEN_WATCHLIST`). |
| `fetch_market_data.py` | Pulls price, market cap, beta, P/E, PEG, dividend yield/streak, revenue/earnings growth, 6-month momentum, volatility, and short-%-of-float per ticker via [yfinance](https://github.com/ranaroussi/yfinance) — free, no API key. |
| `fetch_news.py` | Pulls recent headlines per ticker from Yahoo Finance and Google News RSS (free, no API key), plus a general market PR feed. |
| `scoring.py` | Turns raw metrics into 0–100 scores per category. See **Scoring methodology** below. |
| `generate_dashboard.py` | Merges scores + latest headline into `dashboard/data.json`. |
| `run.py` | Runs the full pipeline end to end. |

Run it all with:

```bash
pip install -r requirements.txt
python run.py
```

Then open `dashboard/index.html`.

## Scheduling

`run.py` is a plain script with no long-running process, so schedule it however
you already run periodic jobs, e.g. a daily cron entry:

```cron
0 7 * * 1-5 cd /path/to/stock-market-agent && /usr/bin/python3 run.py
```

or a scheduled GitHub Actions workflow that runs `run.py` and commits/publishes
the refreshed `dashboard/` folder (e.g. to GitHub Pages).

## Scoring methodology

- **Growth and Next-Gen Growth are ranked by an explicit conviction tier (1–5),
  not a single blended score.** Their best-available metric differs by stock
  (revenue growth %, price momentum %, analyst upside %, funding secured) —
  those units aren't comparable, so averaging them into one number would be
  false precision. `scoring.py` normalizes what it *can* compare (revenue
  growth, momentum) within the group and adds a thematic-fit bonus for
  Next-Gen, but the final tier is the honest signal, not a spurious decimal.
- **Stability and Short Candidates get a real normalized 0–100 score**, because
  every ticker in those groups is measured on the same units (beta, dividend
  yield/streak for Stability; short-%-of-float, momentum, PEG for Short
  Candidates).
- Any ticker missing a metric required for a category is excluded from that
  category rather than backfilled with a guess.

## A note on this sandbox

This repository was developed inside a sandboxed session whose network egress
is restricted to a short allowlist (npm, PyPI, GitHub, the Anthropic API) —
`yfinance`, Wikipedia, and RSS feeds are **not** reachable from there. The
`dashboard/data.json` checked into this repo is therefore a manually-curated
snapshot built from web-search-grounded lookups on ~30 well-known names,
documented in the dashboard's own header. The scripts above (`fetch_universe.py`
onward) are the real, unrestricted-network implementation — run them from any
normal machine, CI runner, or server to get a full live S&P 500 + Nasdaq-100
scan.

## Not financial advice

This tool surfaces public data and a transparent scoring formula for research
convenience. It is not investment advice; verify anything before acting on it.
