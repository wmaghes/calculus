# VANTAGE — Career Prep Implementation Plan

Companion to `docs/AUDIT.md`. Milestones are ordered so each one ships
something usable on its own and later milestones build on earlier ones'
data/schema rather than redoing it. Per the request's working style, this
plan stops after Step 1 — nothing below is built yet.

## Open questions (need an answer before the milestone that depends on them)

1. **Classroom/club mode vs. the no-backend principle (blocks Milestone 7).**
   The spec asks for a join-code + group leaderboard, flagged for later.
   This project has deliberately had zero backend/server/accounts since
   inception (`README.md`, "Security & scope"). A group leaderboard needs
   *some* shared state across browsers, which `localStorage` structurally
   cannot provide. Options: (a) keep it entirely flagged-off and unbuilt
   until a backend decision is made — ship only the feature flag and a
   "coming soon" state; (b) scope "classroom mode" down to something that
   works without a server, e.g. an exportable/importable progress file a
   teacher collects manually; (c) accept introducing a minimal backend
   (changes the threat model per `README.md`'s own caveat, and is a much
   bigger decision than this spec's other asks). Recommend (a) for now and
   revisit explicitly — want to confirm before Milestone 7.
2. **Content tone/authorship for career-track data (affects Milestone 1).**
   The 13 existing role write-ups are intentionally punchy and informal (see
   `dashboard/guide/index.html`'s existing prose). New structured fields
   (entry path, progression ladder, "typical day") should match that voice.
   Confirm that's still the target tone before a large content pass.
3. **Scope of career tracks: 13 existing roles vs. the spec's 7 named
   tracks.** The spec names IB, PE, S&T, equity research, asset management,
   VC, corporate finance, wealth management — a subset/rename of the
   existing 13 (which also includes Individual Investor, Quant, Market
   Maker, CFO, Risk/Compliance, Hedge Fund PM). Recommend keeping all 13
   and tagging the 7 named ones as the "primary" career-prep tracks (full
   interview-prep + recruiting-roadmap content), with the other 6 getting
   the lighter market-linkage/scenario treatment only — confirm before
   Milestone 1.
4. **Real-money compensation and recruiting-timeline figures need sourcing.**
   Spec section E (recruiting timeline) and the "how they're paid" content
   both involve numbers that go stale and vary by firm/year. Confirm
   whether to cite specific firms/sources inline or keep everything
   deliberately generic + hedged ("many programs run roughly...") with
   verification tracked in `docs/CONTENT_TODO.md` — recommend the latter,
   consistent with how `data.json`/`research_data.json` already handle
   uncertain figures (explicit "not yet researched" rather than a guess).

## Milestone 0 — Test harness + content-verification scaffolding

No test runner, linter, or `docs/CONTENT_TODO.md` exists today (see Audit
§1, §6.8-6.9). Before adding game logic:
- Add a minimal JS test setup for the vanilla-JS codebase (no framework in
  use anywhere else, so prefer something equally dependency-light — e.g.
  Node's built-in `node:test` + `node:assert` run via a plain npm script,
  no bundler) covering pure logic functions that don't touch the DOM
  (`scoring.py`'s functions already have none; `engine.js`'s `stepPrice`/
  `deriveRealParams`/`createExtraDiversifiedTickers` are good first targets).
- Add `pytest` for the Python pipeline (`scoring.py`, the `research-analyst/`
  scripts) — currently zero coverage there too.
- Create `docs/CONTENT_TODO.md` with its header/format established, empty
  of entries until Milestone 1 starts adding sourced content.
- No user-visible change. Commit message makes that explicit.

## Milestone 1 — Career tracks as structured, data-driven content (spec A)

- Design a `dashboard/guide/data/careers.json` (or per-role files under a
  `careers/` folder — decide based on how large a single file gets)
  schema: `{ id, title, oneLiner, dayToDay, variations[], pay, skills[],
  marketDependencies[] (indicator ids this role cares about, feeding
  Milestone 2), entryPath: { typicalMajors[], internshipPath, recruitingTrackId
  (feeding Milestone 5) }, progressionLadder[], isPrimaryTrack (per Open
  Question 3), existingSimulatorMode (nullable) }`.
- Migrate the 13 existing roles' prose into this schema *without losing or
  rewriting existing content* — this is a structural move, not a rewrite
  (per the spec's "match existing code style... do not rewrite working
  systems without explaining why").
- Change `dashboard/guide/index.html` to render role cards from this JSON
  instead of hand-authored HTML, keeping the existing accordion/tutor/
  calculator UI intact (calculators stay inline JS per role, since they're
  genuinely interactive, not prose).
- Add the Milestone 0 test coverage for the new content loader (valid
  schema, no missing required fields, all 13 roles present).
- Any new factual claim introduced here (not already in the existing prose)
  gets logged in `docs/CONTENT_TODO.md`.

## Milestone 2 — Market-to-career linkage engine (spec B)

- Define a small `marketEvents.json`/`indicators.json` content file: each
  indicator (rate changes, credit spreads, equity vol, earnings season,
  commodity/FX moves — the five examples the spec gives, extensible later)
  with `{ id, label, cause, mechanism, careerImpacts: [{careerId, impact}] }`,
  2-4 hedged sentences each, cross-referenced by the `marketDependencies[]`
  field added to careers in Milestone 1.
- Surface this as a new "What this means for your career" panel, likely
  on the Career Guide (per-role, filtered to that role's dependencies) and
  optionally as a widget on the Scanner page keyed to whichever indicator a
  ticker's current `metric_label` represents (e.g. a "beta"-labeled Stability
  pick could surface the rate-change linkage).
- This is static, authored content (not live-computed from `data.json`
  values) for the first pass — a "today's 10Y yield moved X, here's what
  that means" *live* version is a reasonable future enhancement but adds a
  new data source and is explicitly out of scope unless asked for.
- All linkage text sourced/hedged per the Quality rules; log anything
  needing verification in `docs/CONTENT_TODO.md`.

## Milestone 3 — Interview prep module (spec D)

- New question-bank content file(s): accounting/valuation fundamentals,
  market questions, stock pitch + brainteasers (trading roles), behavioral/
  "why this career" — tagged by `careerId` (primary tracks per Open
  Question 3 get full coverage first).
- New page or Guide sub-section with: difficulty levels, answer
  explanations, a simple spaced-repetition scheduler for missed questions
  (client-side only, stored in the existing per-player-code `localStorage`
  pattern — no new persistence mechanism needed), and per-skill progress
  tracking feeding into Milestone 6.
- Test coverage: the spaced-repetition scheduling logic is pure and
  DOM-free, so it's a good Milestone-0-harness candidate.

## Milestone 4 — Role-play scenarios (spec C)

- Define scenario content per the four examples given (Banker comp-picking,
  PE associate screen, Trader risk reaction, Analyst estimate update) as
  structured steps with decision points, each with an explanation shown
  after the choice.
- Score on reasoning quality via a rubric (e.g. which considerations a
  chosen rationale references), not P&L — this is a genuinely new scoring
  model distinct from the Simulator's existing cash/mark-to-market P/L, so
  it should be its own module rather than bolted onto `engine.js`.
- Decide (ask first if ambiguous per the spec's own "Working style" rule)
  whether scenarios live inside the existing Simulator page (reusing its
  live-ticking market data) or as a new Guide sub-section (reusing career
  content) — leaning Simulator, since "live market data reacting to a
  decision" is the Simulator's whole premise, but this changes the
  Simulator's existing six-mode structure and deserves explicit sign-off.

## Milestone 5 — Recruiting roadmap (spec E)

- Static timeline content per primary career track x class year (coffee
  chats → networking → applications → superday → offers), explicitly
  labeled approximate with a "verify with your school/target firms" note
  per the spec's own instruction.
- A trackable checklist UI, persisted the same way interview-prep progress
  is (per-player-code `localStorage`).
- All timing claims logged in `docs/CONTENT_TODO.md` for human verification
  before this milestone is considered content-complete.

## Milestone 6 — Progress and credibility (spec F)

- Per-track skill levels/badges computed from real signals already
  produced by Milestones 3-5 (interview-prep accuracy, scenario reasoning
  scores, recruiting-checklist completion) — not from Simulator trading
  returns, per the spec's explicit "not just returns."
- A shareable summary view (e.g. a printable/exportable page, consistent
  with the project having no backend to host a persistent public profile
  URL on — this needs the same no-backend constraint check as Open
  Question 1, likely resolved the same way: client-side export rather than
  a hosted link).
- A "weekly market recap through a career lens" digest generated from the
  Scanner's own `data.json` plus Milestone 2's linkage content — static
  generation (similar to how `generate_dashboard.py` already produces
  `data.json`) rather than a live/scheduled feature, since there's no
  server to run anything on a schedule client-side.

## Milestone 7 — Monetization-ready structure (spec G)

- A single `featureFlags.json` (or inline `const FEATURE_FLAGS` object,
  matching the project's existing "small static config object" idiom seen
  in `config.py`) marking tracks/scenarios/interview modules free or
  premium — no pricing or payment code, purely a gate that can hide/show
  content.
- Classroom/club mode and sponsor-track slots built per however Open
  Question 1 is resolved; shipped flagged-off by default regardless.

## Cross-cutting, every milestone

- Match existing code style (vanilla JS, no new dependencies unless truly
  needed, inline SVG icons, the existing `.card`/`role-card` CSS component
  patterns from `theme.css`) and the existing honesty conventions (hedge
  uncertain claims, disable rather than fake a feature that can't be
  confirmed — same principle already used for tutor voice-matching).
- Run the new test suite (Milestone 0) and any lint added before calling a
  milestone done, per the spec's quality rules.
- Commit per milestone with a clear message; summarize what changed, what
  was tested, and what's uncertain after each one, per "Working style."
- Keep the disclaimer ("educational, not investment advice") visible on any
  new page, consistent with the three existing tools.

## Suggested order and rationale

Milestone 0 → 1 → 2 → (3 and 5 can run in parallel, both are
content-plus-simple-UI and don't depend on each other) → 4 → 6 → 7. Scenario
scoring (4) is ordered after interview prep (3) because a reasoning-quality
rubric is easier to design once the question-bank/explanation pattern from
Milestone 3 already exists and has been validated with real content.
