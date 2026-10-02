# VANTAGE — Codebase Audit (Career Prep Readiness)

Scope: `stock-market-agent/` inside the `wmaghes/calculus` repo (the site is
branded **VANTAGE** and lives entirely under this directory; the rest of the
repo is an unrelated calculus textbook). This audit covers Step 1 of the
career-prep request only — no feature code has been written.

## 1. Stack

- **No backend, no build step, no package manager.** Every page is static
  HTML with an inline `<style>` block and inline/linked vanilla JS — zero npm
  packages, zero bundler, zero framework. The only external network call any
  page makes on its own is to Google Fonts; everything else is a relative
  `fetch()` of a checked-in JSON file, the browser's own Web Speech API, or
  (opt-in, Career Guide only) a direct browser call to `api.anthropic.com`
  using a visitor-supplied API key stored in `localStorage`.
- **Data pipeline is a separate, offline Python layer** (`requirements.txt`:
  `yfinance`, `feedparser`, `pandas`, `lxml`, `requests`) that produces the
  JSON the static pages fetch. It does not run in the browser and has no
  relationship to the page JS at runtime.
- **No test suite, no linter config, no CI** anywhere in this directory
  (`find` for `*.test.*`, `test_*.py`, `*spec.js`, `.eslintrc*`,
  `pyproject.toml` all come back empty). This has to be established, not
  extended, for Milestone work.
- **Persistence is 100% client-side `localStorage`**, namespaced per
  Simulator "player code." There is no account system and no server-side
  state anywhere, by explicit prior design (see `README.md`, "Security &
  scope").

## 2. Structure

```
stock-market-agent/
  config.py, scoring.py, run.py,              # Scanner data pipeline (Python)
  fetch_universe.py, fetch_market_data.py, fetch_news.py, generate_dashboard.py
  research-analyst/                           # Research page pipeline (Python)
    config.py (COMPANIES: 116 ticker->name)
    fetch_10k.py, fetch_market_ratios.py, fetch_yahoo_finance.py
    assemble_data.py, generate_research_pages.py
    data/research_data.json                   # {generated, companies: {TICKER: {...}}}
  dashboard/                                   # The actual shipped site (static)
    data.json                                  # Scanner's 116-ticker snapshot
    index.html                                 # Scanner (landing + 5 ranked "desks")
    research/<TICKER>/{financials,market}.html # 116 x 2 generated pages + index.html hub
    simulator/{index.html, engine.js}          # 6 "profession mode" paper-trading sim
    guide/index.html                           # Career Guide: 13 roles + 7 security types
    assets/{theme.css, nav.js}                 # Shared design system + top nav injector
```

Four top-level pages, tied together by `window.SITE_NAV` + `nav.js`: Scanner,
Research, Simulator, Guide. This is the entire "game" — there is no other
entry point, menu, or mode outside these four.

## 3. Data models

- **`dashboard/data.json`** — `{ generated, categories: { growth[25],
  stability[25], nextgen[25], shorts[25], funds[16] } }`. Each item:
  `{ ticker, name, price, mktCap, metric_label, metric, conviction, blurb,
  rating, sector, industry, fortune100, fortune100Rank, capTier }`. This is
  hand/web-search-curated (the pipeline scripts above produce the same shape
  from live `yfinance`/Wikipedia/RSS sources, but can't reach the network
  from this sandbox — see `README.md`, "A note on this sandbox"). `scoring.py`
  computes `conviction`/`score` via documented min-max normalization per
  category; nothing here is a "game event," just a daily market snapshot.
- **`research-analyst/data/research_data.json`** — `{ generated, companies:
  { TICKER: { ticker, name, financials: {...|null}, ratios: {...}, market:
  {...synced from data.json...} } } }`, 116 entries, only the original 32
  have real 10-K-sourced `financials`.
- **Simulator state** — entirely in `localStorage`, two keys per player code:
  `simState.v2::<CODE>` (cash/holdings/shorts/options/futures/clients/plans
  across both universes and all six modes) and `simEngine.v1::<CODE>` (the
  market engine's own price history). `simProfiles.v1` is a browser-wide
  registry of codes seen, for the "Continue as" shortcut. No schema file —
  shape is implicit in `engine.js`/`simulator/index.html` JS.
- **Career Guide content** — **not data-driven at all.** All 13 role
  write-ups (what they do, variations, pay, calculator) and all 7 security
  types are hand-authored directly as HTML inside `dashboard/guide/index.html`
  (it is 1,741 lines). The only structured content objects are `ROLE_NARRATION`
  (130 pre-translated two-sentence summaries used for TTS/subtitles across 10
  languages) and `TUTORS` (2 entries: Max/Nova). There is no `careers.json`,
  no per-role schema, no machine-readable "entry path," "progression ladder,"
  or "key skills" field — that information, where it exists at all, is prose
  inside `<p>` tags.

## 4. "Game loop"

There isn't a single game loop; each of the four pages is its own
self-contained tool:

- **Scanner** — load `data.json`, filter/sort, read-only browsing. No player
  action, no persistence, no scoring of the user.
- **Research** — 232 static pages (116 x financials + market), pure reading.
- **Simulator** — the only page with an actual loop: `engine.js` runs a
  `setInterval`-driven GBM price tick (`tick()`, capped at
  `MAX_CATCHUP_YEARS = 5` per jump) against either the 116-ticker "real"
  universe (drift/vol derived from `data.json` metrics, speed locked to
  real-time) or a procedurally generated "super" universe (5 speed presets).
  Six **profession modes** (Individual Investor, Investment Banker, Private
  Banker, Financial Planner, Options & Futures Trader, Short Seller) read/write
  the same per-code `localStorage` state against whichever universe is
  active. Scoring is just cash + mark-to-market P/L — there is no reasoning
  or decision-quality evaluation anywhere.
- **Career Guide** — static accordion reading, plus two interactive layers:
  a tutor system (language-matched TTS narration/subtitles + Q&A, with
  bring-your-own-key real Claude answers or an offline keyword-match
  fallback) and small embedded calculators (compound growth, IRR/MOIC, Sharpe,
  comps, VaR, etc., one per role). No progress tracking, no scoring, no
  persistence of what a user has read or answered.

## 5. What currently connects markets to careers

This is stronger than a blank slate, but it is all **static and narrow**:

- Each of the 13 Career Guide roles has a prose "How they use the market"
  section and, for several roles, a deep link into the matching Simulator
  mode via `simulator/index.html?mode=<id>` (e.g. Investment Banker → the IB
  M&A calculator mode). This is a real, working link between the two tools,
  but it's a static 1:1 role-to-mode map authored once, not something that
  reacts to live data.
- Several roles' calculators consume realistic *shapes* of data (comps
  multiples, IRR/MOIC, Black-Scholes-priced options) but not the Scanner's
  actual live tickers — they take manually typed inputs.
- The Simulator's Short Seller mode explicitly surfaces the Scanner's own
  "Shorts" desk as candidate ideas — the one place a scored category feeds
  directly into a career-mode workflow.
- The AI tutor's system prompt keeps answers "in character" for a role, but
  has no grounding in *today's* market data — it's a generic persona prompt,
  not fed any live indicator, headline, or event.

## 6. What's missing or shallow (prioritized gap list)

### High impact
1. **No market-to-career linkage engine at all.** Nothing in the codebase
   maps a market event or indicator (rate moves, credit spreads, vol,
   earnings season, commodity/FX moves) to "what this means for your
   career." The spec's entire section B does not exist in any form —
   `data.json`'s `blurb` field is a one-off descriptive sentence per ticker,
   not a reusable, career-tagged linkage.
2. **No role-play / scenario mode with decision scoring.** The Simulator
   has professional "seats" (buy/sell/manage), but nothing scores reasoning
   quality or gives a post-decision explanation — it's P&L-only. Spec
   section C (Banker/PE/Trader/Analyst scenarios, scored on reasoning) is
   entirely new work.
3. **No interview-prep module.** Zero quiz, flashcard, spaced-repetition, or
   question-bank content/UI anywhere (`grep` for interview/quiz/flashcard/
   brainteaser/recruiting returns nothing). Spec section D is entirely new.
4. **No recruiting-timeline/roadmap feature.** No checklist, no class-year
   timeline content. Spec section E is entirely new.
5. **Career content is not data-driven.** The 13 roles live as hand-authored
   HTML, not structured JSON/YAML (spec section A's core requirement). Any
   new career-track fields (entry path, progression ladder, key skills,
   dependent indicators) need a real schema and a migration of the existing
   13 roles into it before anything else can be layered on cleanly.

### Medium impact
6. **No progress/credibility layer.** No skill levels, badges, shareable
   profile, or generated digest (spec section F). The player-code save
   exists but tracks only trading state, nothing skill-related.
7. **No feature-flag scaffolding.** Nothing resembling free/premium gating
   or a classroom/club mode exists; `grep` hits for "premium"/"classroom" in
   the codebase are unrelated (options *premium*, M&A deal *premium*). Spec
   section G needs to be built from zero, though the lack of any backend
   means "classroom mode" (join code, group leaderboard) has no natural
   place to live without inventing some shared-state mechanism — this
   conflicts with the project's explicit "no backend, no accounts" design
   principle and needs a decision (see PLAN.md open questions).
8. **No automated tests or lint**, for old or new code. Any new game logic
   or content loader needs a test harness introduced from scratch — there is
   currently no `npm`/`pytest`-style convention to extend.
9. **No content-sourcing/verification ledger.** The spec requires a
   `docs/CONTENT_TODO.md` for every claim needing human verification (comp
   figures, dates, market relationships). No equivalent exists today; the
   closest precedent is `README.md`'s own honest "not yet researched"
   labeling on 68 of 116 companies' financials, which is a good model to
   follow but isn't itself a structured TODO ledger.

### Low impact
10. **`README.md`'s Career Guide section is already slightly stale** — it
    describes the tutor avatars as "a simple HUD-style face... blinking eyes
    and a talking mouth," but the current `charAvatarSVG()` in
    `dashboard/guide/index.html` (line 1312) is an abstract hologram-ring
    design from a later revision. Worth a one-line doc fix alongside
    whichever milestone next touches that file, not urgent on its own.
11. **No sitewide "educational, not advice" disclaimer audit was done as
    part of this pass** — the Scanner, Simulator, and Guide each already
    carry their own disclaimer language per `README.md`'s "Not financial
    advice" section, so this is likely already satisfied, but a direct
    check is cheap and worth folding into Milestone 1 rather than assuming.
12. **No privacy/COPPA/FERPA review has ever been done**, though it's
    likely a non-issue today since the project collects no personal data at
    all (no accounts, no server). Worth a short explicit note in the plan
    rather than silence, since classroom mode (if built) would be the first
    feature where that stops being trivially true.

## 7. Summary

The project is a well-built, zero-backend static site with a genuinely
working data pipeline (Python) feeding four polished static tools (Scanner,
Research, Simulator, Guide). The Career Guide is the closest existing piece
to "career prep" — 13 well-written roles, working calculators, and a
Simulator deep-link per role — but everything from here on (sections A
through G of the request) is additive, net-new work: a structured content
model, a market-event-to-career linkage layer, scored scenarios, interview
prep, a recruiting roadmap, progress tracking, and flagged monetization
scaffolding. None of it conflicts with the existing architecture, but all of
it requires decisions (see `docs/PLAN.md`) about where structured content
lives, how "classroom mode" squares with the no-backend design principle,
and what a test harness looks like for a project that has never had one.
