# VANTAGE — Content Verification TODO

This file tracks every factual claim introduced by the career-prep
initiative that needs human verification before it's treated as fact:
compensation figures, dates/timelines (e.g. recruiting cycles), named
firms/programs, and market relationships ("X tends to move Y"). It does
not cover content that already existed before this initiative (e.g. the
13 Career Guide roles' existing prose) unless a milestone changes or
extends it.

Per `docs/PLAN.md`'s Quality rules: new factual claims should default to
generic, hedged language ("many programs run roughly...") rather than
citing a specific unverified number, consistent with how `data.json` and
`research_data.json` already mark unresearched figures as unknown instead
of guessing. Anything that *is* stated more specifically gets a row here
so it can be checked against a real source (or walked back to hedged
language) before shipping.

Entries are added starting with Milestone 1 (career tracks as structured
content) and onward; this file is empty until then.

## How to add an entry

One row per claim. Keep the claim text short enough to scan; put detail in
the Notes column.

| Claim | Location (file:line or section) | Why it needs verification | Added in | Status | Notes |
|---|---|---|---|---|---|
| Individual Investor: typical majors ("any major"), internship path, and progression ladder | `dashboard/guide/data/careers.json` (`individual`) | New fields not in the original prose; this role has no formal career ladder, so the ladder is illustrative only | Milestone 1 | hedged | No internship/major claim is firm-specific; generic by design |
| Financial Advisor: typical majors, internship path, and progression ladder (Associate &rarr; Advisor &rarr; Senior/Partner &rarr; Practice owner) | `dashboard/guide/data/careers.json` (`advisor`) | New fields; titles and licensing path vary by firm/channel (wirehouse vs. independent RIA) | Milestone 1 | hedged | Mentions Series 7/65 licensing generically, no specific firm |
| Private Banker / Wealth Manager: typical majors, internship path, and progression ladder | `dashboard/guide/data/careers.json` (`private-banker`) | New fields; this is one of the primary career-prep tracks (wealth management), so entry/progression claims should be checked against real bank programs | Milestone 1 | hedged | "Often"/"sometimes" language throughout, no specific bank named |
| Investment Banker: typical majors, internship path, and Analyst&ndash;MD progression ladder | `dashboard/guide/data/careers.json` (`investment-banker`) | New fields; the Analyst/Associate/VP/Director/MD ladder and summer-internship pipeline are industry-standard but pacing/titles vary by bank | Milestone 1 | hedged | Primary career-prep track; no firm names or timelines cited |
| Trader (Sales &amp; Trading): typical majors, internship path, and progression ladder | `dashboard/guide/data/careers.json` (`trader`) | New fields; path differs a lot between sell-side, prop, and independent trading | Milestone 1 | hedged | Primary career-prep track; kept generic across all three trader variants |
| Quantitative Analyst: typical majors, internship path, and progression ladder | `dashboard/guide/data/careers.json` (`quant`) | New fields; highly technical interview process described only in general terms | Milestone 1 | hedged | No specific firm or interview question cited |
| Private Equity: typical majors, internship path ("2-3 years as an IB analyst first"), and Analyst&ndash;Partner ladder | `dashboard/guide/data/careers.json` (`private-equity`) | New fields; the "banking-then-PE" pipeline is common but not universal, and timing varies by fund size | Milestone 1 | hedged | Primary career-prep track |
| Venture Capitalist: typical majors, internship path, and progression ladder | `dashboard/guide/data/careers.json` (`venture-capital`) | New fields; VC entry paths are unusually varied (operating, banking, fellowships); generalization is a simplification | Milestone 1 | hedged | Primary career-prep track |
| Hedge Fund / Portfolio Manager: typical majors, internship path, and Analyst&ndash;PM ladder | `dashboard/guide/data/careers.json` (`hedge-fund`) | New fields; "recruits from IB/equity research" is common at larger multi-strategy funds but not all hedge funds | Milestone 1 | hedged | Primary career-prep track (asset management) |
| CFO: typical majors, internship path, and Financial Analyst&ndash;CFO ladder | `dashboard/guide/data/careers.json` (`cfo`) | New fields; this is a decades-long career path, described only in general stages | Milestone 1 | hedged | Primary career-prep track (corporate finance) |
| Market Maker / Broker-Dealer: typical majors, internship path, and progression ladder | `dashboard/guide/data/careers.json` (`market-maker`) | New fields; path is specific to trading-firm recruiting, described generically | Milestone 1 | hedged | No specific firm named |
| Equity Research Analyst: typical majors, internship path, and Associate&ndash;Director ladder | `dashboard/guide/data/careers.json` (`research-analyst`) | New fields | Milestone 1 | hedged | Primary career-prep track |
| Risk Manager / Compliance Officer: typical majors, internship path, and progression ladder | `dashboard/guide/data/careers.json` (`risk-manager`) | New fields | Milestone 1 | hedged | No specific firm or regulatory program named |
| `isPrimaryTrack` mapping: "corporate finance" -&gt; CFO, "wealth management" -&gt; Private Banker/Wealth Manager | `dashboard/guide/data/careers.json` (all 13 roles' `isPrimaryTrack`) | PLAN.md's Open Question 3 flagged ambiguity between the spec's 7 named tracks and the existing 13 roles; this task's brief allowed marking more than 7 when the mapping is ambiguous | Milestone 1 | hedged | 8 roles marked primary (IB, PE, Trader, Equity Research, Hedge Fund/PM, VC, CFO, Private Banker) -- see commit message / agent report for full rationale |

**Status** values: `needs-source` (default on add), `verified` (source
added inline or here), `hedged` (claim was rewritten to generic/hedged
language instead of sourced, so no further verification needed).
