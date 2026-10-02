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
| _(none yet)_ | | | | | |

**Status** values: `needs-source` (default on add), `verified` (source
added inline or here), `hedged` (claim was rewritten to generic/hedged
language instead of sourced, so no further verification needed).
