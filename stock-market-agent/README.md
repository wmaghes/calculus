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

## Design system: VANTAGE

The four pages (Scanner, Research, Simulator, Guide) share one visual
identity, branded **VANTAGE**, built as two shared files:

- `dashboard/assets/theme.css` — a dark-first "trading terminal" design
  system (deep near-black surfaces, an electric cyan/violet accent, Space
  Grotesk headings over IBM Plex Sans/Mono body and data text) loaded last
  on every page, so it skins the component classes each page already uses
  (`.card`, `button.action`, `table.data`, etc.) without any page needing
  its own copy of the color tokens. A `[data-theme="light"]` override
  provides an optional light mode.
- `dashboard/assets/nav.js` — injects the persistent top nav bar (logo,
  Scanner/Research/Simulator/Guide links with active-page highlighting, and
  a theme toggle persisted to `localStorage`) into a `<div id="siteNav">`
  placeholder, reading `window.SITE_NAV = { base, active }` set by each
  page so relative links work at any folder depth (the main pages, and the
  per-ticker research pages two levels deep).

Each page keeps its own `<style>` block for page-specific layout (grids,
widgets like the Simulator's calculator forms or the Guide's role cards);
only the shared tokens, nav, and cross-page links moved into the two
assets files. A tiny inline script at the top of every page's `<head>`
applies a saved theme choice before first paint to avoid a flash of the
wrong theme.

Both themes follow a "polished stone" idea — a genuinely veined base, not a
flat fill. The body background is an SVG `feTurbulence` field, desaturated
and reshaped per-channel with `feComponentTransfer`'s `table` function so
only a narrow band of the noise's range becomes visible: in light mode that
band stays near-white and is applied with `background-blend-mode: multiply`
(soft grey veins on a Carrara-white base); in dark mode the same turbulence
source is mapped to a dim cyan band applied with `screen` (smoky pale-blue
veins on obsidian). Both tile at 800px with soft multi-point ambient
gradients layered underneath for color wash. Glass-morphic cards
(`backdrop-filter` blur + an inset highlight line) float over that
texture so the veining stays visible through them. Hero titles (`h1.title`)
use a gradient text fill
(`background-clip: text`) from ink to the accent color. Entrance motion
(`fadeUp`) is deliberately scoped to `.role-card` and `section.category`
only — classes the Simulator's per-tick re-render never touches — so
nothing replays the animation every second. A small inline-SVG icon set
(reused between the Guide's 13 role cards and the Simulator's 4 matching
mode buttons, plus the Scanner's 4 category headers) replaces plain color
dots with real iconography.

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

## Research Analyst Agent

`research-analyst/` is a companion agent that answers questions about a
company's **10-K financials** (revenue, margins, net income, balance sheet)
and its **market data & ratios** (price, P/E, P/B, P/S, dividend yield, beta,
52-week range) for every ticker on the watchlist above, and publishes the
results as a small static site at `dashboard/research/`.

| Script | Purpose |
|---|---|
| `research-analyst/fetch_10k.py` | Pulls the latest 10-K's key XBRL facts (revenue, margins, assets, debt) per company from SEC EDGAR's free `data.sec.gov` company-facts API — no API key, but requires a real internet connection and a descriptive `User-Agent` per SEC's fair-access policy. |
| `research-analyst/fetch_market_ratios.py` | Pulls price, P/E, P/B, P/S, PEG, dividend yield, beta, and 52-week range per ticker via yfinance. |
| `research-analyst/fetch_yahoo_finance.py` | A deeper Yahoo Finance scraper: annual/quarterly income statement, balance sheet and cash flow history, analyst recommendations and price targets, institutional holders, and recent news headlines per ticker (via `yfinance`, no API key). Writes `data/yahoo/<TICKER>.json` plus a combined `data/yahoo_finance.json`. |
| `research-analyst/generate_research_pages.py` | Renders `dashboard/research/<TICKER>/financials.html` and `.../market.html` for every company, plus a `dashboard/research/index.html` hub. |

Each company gets **two separate pages**: a Financials page (sourced from its
10-K) and a Market Data page (live price/ratios, reusing the scanner's own
`dashboard/data.json` where possible so the two tools stay consistent). The
main dashboard links to the research hub, and each research page links back.

Run it (from an environment with normal internet access) with:

```bash
cd research-analyst
python3 fetch_10k.py
python3 fetch_market_ratios.py
python3 fetch_yahoo_finance.py
python3 generate_research_pages.py
```

This sandbox can't reach SEC EDGAR, yfinance, or finance.yahoo.com either
(same egress restriction as the scanner — see below; verified directly, the
proxy returns `connect_rejected` for `finance.yahoo.com` and
`query1.finance.yahoo.com`), so the checked-in `dashboard/research/` pages
were built from a one-time `assemble_data.py` pass using web-search-grounded
10-K and ratio lookups instead. Ask about a company's financials or ratios
in chat and I'll refresh its two pages the same way.

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

## Stock Market Simulator

`dashboard/simulator/index.html` is a paper-trading sandbox that teaches how
investing looks from four different professional seats, running against a
**live, speed-controlled market engine** (`dashboard/simulator/engine.js`)
instead of a static price snapshot.

### Market engine: two universes, any speed

A settings panel at the top of the page controls the market itself, before
you ever pick a profession mode:

- **Real Companies** — the 32-ticker Scanner watchlist, seeded at each
  company's real snapshot price. From there it moves forward using a
  geometric Brownian motion (random-walk) model, with drift/volatility
  *derived* from that same snapshot's own beta, growth and momentum metrics.
  **This is a disclosed model, not a replay of actual historical prices** —
  this sandbox has no historical time-series data to replay, and the UI says
  so directly.
- **Super Simulator** — an entirely fictional universe: procedurally
  generated fake tickers, company names, sectors, prices, and financials
  (net income, shares outstanding), regenerable on demand with a "New Fake
  Universe" button. Zero connection to any real company, so you can
  experiment freely. Each fake company also gets a generated **profile**
  (business description, HQ, founding year, CEO, employee count), a
  trailing four-quarter financial backstory, and a **live news feed** —
  every simulated quarter, a headline is generated reflecting that
  quarter's actual price move (a blowout quarter, a miss, a steep decline),
  so the market has a story attached to it instead of just numbers. Click
  any sparkline card to open its profile; the same click on a Real
  Companies card opens that ticker's real Company Research page instead.
- **Speed control** — five presets spanning the full requested range, from a
  day trader's pace up to real-time: Day Trader (1 simulated year per 10 real
  minutes), Swing Trader (1 year/hour), Position Trader (1 year/day),
  Long-Term Investor (1 year/week), and Real-Time (1 year/year). Pause/Resume
  freezes the clock exactly (no catch-up jump on resume), and a single
  catch-up step (capped at 5 simulated years) handles time that passed while
  the tab was closed.
- An **index chart** (equal-weighted across the active universe, hover for a
  crosshair + tooltip) and a **sparkline grid** per ticker visualize price
  action live as the engine ticks (see `references/` under the `dataviz`
  skill for the chart methodology this follows).

Each of the two universes ("real" and "super") carries its own fully separate
trading state — switching modes never mixes a fake holding with a real one.

### The four profession modes

- **Individual Investor** — a single account: buy/sell active-universe
  tickers, track cash, holdings and P/L.
- **Private Banker** — manage several named clients at once, each with their
  own risk profile, starting AUM, holdings and P/L, plus a book-of-business
  summary table across all of them.
- **Financial Advisor** — build goal-based plans (target $, time horizon,
  risk tolerance) that map to a suggested asset mix, project a future value
  with a simple compounding estimate, then "fund" the plan to actually invest
  the lump sum and add simulated monthly contributions against live prices.
- **Investment Banker** — a simplified M&A accretion/dilution calculator:
  pick an acquirer and target with usable net income, market cap and price
  data (from either universe), set premium/consideration/synergy/financing
  assumptions, and see pro-forma EPS accretion or dilution against the
  *live* ticking price.

All state (cash, holdings, clients, plans, and the engine's own price
history) is stored in the browser's `localStorage` — nothing is sent
anywhere, and it resets if site data is cleared. None of this is real
trading or real investment advice — it's a teaching tool for how each role
thinks about risk, return and time horizon.

## Career Guide

`dashboard/guide/index.html` is a fourth tab: a plain-language reference on
how thirteen finance careers actually relate to the stock market — Individual
Investor, Financial Advisor, Private Banker/Wealth Manager, Investment
Banker, Trader (sales & trading / prop / day trader), Quantitative Analyst,
Private Equity, Venture Capitalist, Hedge Fund/Portfolio Manager, Chief
Financial Officer (the issuer side), Market Maker/Broker-Dealer, Equity
Research Analyst, and Risk Manager/Compliance Officer. Each entry covers what
the role does day to day, the concepts/tools it relies on, a small
interactive calculator so the math isn't just words (compound growth,
position sizing, IRR/MOIC, ownership dilution, Sharpe ratio, buyback EPS
impact, bid-ask spread economics, comps valuation, Value-at-Risk), and —
where one exists — a deep link straight into the matching Simulator mode (the
Simulator reads a `?mode=` query param on load, e.g.
`simulator/index.html?mode=ib`).

## Not financial advice

This tool surfaces public data and a transparent scoring formula for research
convenience. It is not investment advice; verify anything before acting on it.
