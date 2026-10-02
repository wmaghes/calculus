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

### Company universe: 116 names across 10 sectors, plus funds

The watchlist spans 116 tickers across 10 of the 11 GICS sectors, 29 current
Fortune 100 companies (by revenue), and 13 next-gen growth niches (quantum
computing, space, gene editing, AI, cybersecurity, EV & battery tech,
fintech, clean energy, robotics, AI infrastructure, AI healthcare, AI drug
discovery). The Market Scanner has a search/filter bar (free-text search,
sector dropdown, a company-size dropdown, a Fortune 100 toggle, and theme
chips) so the full universe stays navigable instead of just a long scroll.

Of the 116, 100 are individual stocks split across four scored/ranked desks
(Growth, Stability, Next-Gen Growth, Short Candidates — 25 each). The
original **32** of those have full SEC-10-K-sourced financials and valuation
ratios (the Financials tab shows real revenue/margin/balance-sheet figures).
The other **68** — added later purely for sector/industry diversity and
Fortune 100 coverage — currently have live market-snapshot data only (price,
market cap, sector/industry, a key metric, Fortune 100 rank); their
Financials page says so honestly ("No 10-K figures were confidently sourced
for this company in this pass") rather than fabricating numbers. Running
`fetch_10k.py` and `fetch_market_ratios.py` for those 68 (from an environment
with real internet access) would fill them in using the exact same pipeline
as the original 32 — `config.COMPANIES` already lists all 116 tickers.

### Funds & Company Size desk: seeing the risk difference

A 5th desk, **Funds & Company Size**, holds a deliberately small set of 16
names — 5 ETFs, 3 mutual funds, 4 mid-cap stocks, and 4 small-cap stocks —
sorted from lowest to highest risk instead of by conviction or score, so the
effect of diversification and company size on volatility is visible at a
glance: a bond ETF (AGG) sits at "Very Low Risk," a balanced fund and a
dividend-quality ETF at "Low," broad-market index funds at "Moderate," a
tech-heavy/small-cap index ETF alongside individual mid-cap stocks at
"High," and individual small-cap stocks at "Very High." The "Risk" dots
reuse the same 1–5 UI as the conviction-tier dots elsewhere, just relabeled.

This works identically in both Simulator modes:
- **Real Companies mode** needs no special-casing at all — each fund's real
  beta (e.g. AGG's ~0.23 vs. QQQ's ~1.26) flows straight into the existing
  `deriveRealParams()` beta heuristic in `engine.js`, which already produces
  a lower-volatility GBM process for a lower-beta instrument.
- **Super Simulator mode** procedurally generates its own fixed set of 8
  fake funds (one per real-world "flavor": broad index, growth-tilted,
  small-cap index, dividend/quality, bond, plus the mutual-fund equivalents
  of an index fund, an active growth fund, and a balanced fund) with
  volatility ranges modeled after their real analogues, plus 8 explicit
  small-cap and mid-cap fake companies sized (via `price * shares`) to
  actually land in their intended market-cap band with correspondingly
  higher volatility — see `createExtraDiversifiedTickers()` in `engine.js`.

Every stock-type item (across all 116) also carries a `capTier` field
(`mega` ≥ $200B, `large` $10B–$200B, `mid` $2B–$10B, `small` $300M–$2B,
derived from market cap), so the Scanner's company-size filter works across
the whole universe, not just the dedicated 16.

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
investing looks from six different professional seats, running against a
**live, speed-controlled market engine** (`dashboard/simulator/engine.js`)
instead of a static price snapshot.

A one-time disclaimer gate (shown once per browser, acknowledged via a
button, never dismissible by clicking outside it) makes explicit that this
is a simulation, not real trading, before anyone touches the market panel.

### Player codes: a game save, not a real account

The Simulator is a game you can walk away from and resume. On every visit it
first asks for a **player code** — any code the player picks themselves (3-30
letters/numbers/spaces/dashes, not case-sensitive) — before anything else
loads:

- **New code** → a brand-new save starts under it immediately (starting cash
  in every mode, no holdings, no history).
- **Same code again, any time later** → the browser remembers the last code
  used and offers a one-click "Continue as `<CODE>`" button; typing the code
  back in manually works identically even without that shortcut.
- **"Restart this code instead"** (shown on the gate once a code with an
  existing save is typed, and again as a button in-page next to "Switch /
  log out") wipes that one code's save back to a fresh start, after a
  confirmation — the code itself is kept, only its progress is erased.

This is **not a real account system** — there is no server or database
anywhere in this project, by design (see "Make it downloadable outside of
Claude" below). A player code is just a `localStorage` namespace: every
mode's state (cash, holdings, shorts, options, futures, clients, plans, and
the market engine's own price history) is stored under
`simState.v2::<CODE>` / `simEngine.v1::<CODE>` in that one browser. The same
code resumes the same game **in that same browser, on that same computer,
indefinitely** — closing the tab, shutting down, or coming back next week all
work — but it has no way to reach a different browser or a different
computer, and clearing that browser's site data erases every code's save
permanently. A registry of codes seen on this browser is kept in
`simProfiles.v1` purely so the "Continue as" shortcut and a future
my-profiles list have something to read; the one-time migration path for
anyone updating from the pre-player-code version of this project (back when
all state was one unkeyed global save) is a "claim it with a code" prompt
that appears on the gate only when that old, un-keyed save is still present.

### Market engine: two universes, one of them real-time only

A settings panel at the top of the page controls the market itself, before
you ever pick a profession mode:

- **Real Companies** — the 116-ticker Scanner watchlist, seeded at each
  company's real snapshot price. From there it moves forward using a
  geometric Brownian motion (random-walk) model, with drift/volatility
  *derived* from that same snapshot's own beta, growth and momentum metrics.
  **This is a disclosed model, not a replay of actual historical prices** —
  this sandbox has no historical time-series data to replay, and the UI says
  so directly. **Real Companies mode is locked to a single Real-Time speed**
  (no fast-forward option, no speed selector shown at all) so it can never
  look like a prediction tool or a backtest running against real securities;
  the lock is enforced both when switching into the mode and on page load.
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
- **Speed control (Super Simulator only)** — five presets spanning the full
  requested range, from a day trader's pace up to real-time: Day Trader (1
  simulated year per 10 real minutes), Swing Trader (1 year/hour), Position
  Trader (1 year/day), Long-Term Investor (1 year/week), and Real-Time (1
  year/year). Pause/Resume freezes the clock exactly (no catch-up jump on
  resume), and a single catch-up step (capped at 5 simulated years) handles
  time that passed while the tab was closed.
- An **index chart** (equal-weighted across the active universe, hover for a
  crosshair + tooltip) and a **sparkline grid** per ticker visualize price
  action live as the engine ticks (see `references/` under the `dataviz`
  skill for the chart methodology this follows).

Each of the two universes ("real" and "super") carries its own fully separate
trading state — switching modes never mixes a fake holding with a real one.

### The six profession modes

- **Individual Investor** — a single account: buy/sell active-universe
  tickers, track cash, holdings and P/L.
- **Investment Banker** — a simplified M&A accretion/dilution calculator:
  pick an acquirer and target with usable net income, market cap and price
  data (from either universe), set premium/consideration/synergy/financing
  assumptions, and see pro-forma EPS accretion or dilution against the
  *live* ticking price.
- **Private Banker** — manage several named clients at once, each with their
  own risk profile, starting AUM, holdings and P/L, plus a book-of-business
  summary table across all of them.
- **Financial Planner** — build goal-based plans (target $, time horizon,
  risk tolerance) that map to a suggested asset mix, project a future value
  with a simple compounding estimate, then "fund" the plan to actually invest
  the lump sum and add simulated monthly contributions against live prices.
- **Options & Futures Trader** — buy calls/puts priced with a real
  Black-Scholes model (using each ticker's own simulated annualized
  volatility and a flat 4% risk-free rate; 1 contract = 100 shares, four
  expiry choices from 1 month to 1 year, auto-settled at expiry), and open
  leveraged futures positions (flat 10% initial margin, continuously
  marked to market, auto-liquidated if losses erode the position to 50% of
  posted margin — a simplified margin call).
- **Short Selling / Buy-Side Investor** — run a long/short equity book:
  regular buy/sell on the long side, plus borrow-and-sell-now short
  positions (flat 50% initial margin, a flat 4%/year borrow fee accrued
  continuously in sim time) on the short side, with the Market Scanner's
  own "Shorts" category surfaced as candidate ideas.

All state (cash, holdings, shorts, options, futures, clients, plans, and the
engine's own price history) is stored in the browser's `localStorage`, keyed
to the player code chosen at startup (see above) — nothing is sent anywhere,
and it resets if site data is cleared. None of this is real trading or real
investment, legal or tax advice — it's a teaching tool for how each role
thinks about risk, return, leverage and time horizon.

## Career Guide

`dashboard/guide/index.html` is a fourth tab, in two parts. Every entry in
both parts is a collapsed-by-default `<details>` accordion (click to open;
an "Expand all" / "Collapse all" toggle and a table-of-contents sit above
each part, and the two parts' accordions are independent of each other).

The first part is a plain-language reference on how thirteen finance careers
actually relate to the stock market — Individual Investor, Financial
Advisor, Private Banker/Wealth Manager, Investment Banker, Trader (sales &
trading / prop / day trader), Quantitative Analyst, Private Equity, Venture
Capitalist, Hedge Fund/Portfolio Manager, Chief Financial Officer (the
issuer side), Market Maker/Broker-Dealer, Equity Research Analyst, and Risk
Manager/Compliance Officer. Each entry covers what the role does day to day,
how the role varies in practice (e.g. fee-only vs. commission advisor,
sell-side vs. buy-side trader), how people in it are actually paid, the
concepts/tools it relies on, a small interactive calculator so the math
isn't just words (compound growth, position sizing, IRR/MOIC, ownership
dilution, Sharpe ratio, buyback EPS impact, bid-ask spread economics, comps
valuation, Value-at-Risk), and — where one exists — a deep link straight
into the matching Simulator mode (the Simulator reads a `?mode=` query param
on load, e.g. `simulator/index.html?mode=ib`).

The second part, **Types of Securities**, explains every instrument type
traded anywhere on the site in plain language: Common Stock (including the
mega/large/mid/small-cap risk gradient), ETFs, Mutual Funds, Bonds, Options,
Futures, and Short Selling — each cross-linked to where it shows up live
(the Funds & Company Size Scanner desk, or the matching Simulator mode).

## Security & scope

This is a static site: no backend, no server-side code, no database, no
accounts, and no payments. The only outbound network call the live pages
make is to Google Fonts; everything else is a relative `fetch()` to a JSON
file checked into this repo. All simulator/trading/plan state lives in the
visitor's own browser `localStorage` and is never transmitted anywhere, so
there is no shared state between visitors and nothing server-side to
compromise.

That said, it's worth being concrete about what was actually checked rather
than asserting "it's safe":

- **Secrets**: the repo was grep-audited for API keys, tokens, and
  passwords — none exist. The only credential-adjacent string is
  `SEC_USER_AGENT`, a descriptive contact string SEC's fair-access policy
  asks for, not a secret.
- **XSS**: the only free-text user inputs anywhere on the site are the
  Simulator's Private Banker client name and Financial Advisor plan name
  fields, both of which get rendered back into the page in several places
  (tables, headings, `<option>` labels). These are escaped through a shared
  `escapeHtml()` helper before interpolation — verified with an actual
  `<img src=x onerror=...>` payload in a Playwright test confirming it
  renders as inert text rather than executing. Every other piece of dynamic
  content on the site (company names, tickers, financials) comes from this
  repo's own generated JSON, not visitor input.
- **No `eval`/`Function` constructor, no shell-outs**: grep-audited across
  both the JS and the Python research scripts; none exist.
- **Dependency surface**: zero npm packages, zero CDN JS libraries — every
  script is hand-written vanilla JS checked into this repo. The only
  external resource is the Google Fonts stylesheet link.
- **Runaway-math guardrail**: the Simulator's market engine caps a single
  "catch up" time jump at 5 simulated years (`MAX_CATCHUP_YEARS` in
  `engine.js`), so a tab left open for a long real-world stretch at a fast
  game speed can't extrapolate the random-walk model into nonsense
  (near-zero or astronomical prices) — see that file's comments for why.

If you ever extend this past a static site (add a real backend, accounts,
or payments), that changes the threat model entirely and would need its own
review — none of the above claims extend to code you add beyond what's in
this repo today.

## Not financial advice

This tool surfaces public data and a transparent scoring formula for research
convenience. It is not investment advice; verify anything before acting on it.
