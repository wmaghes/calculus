# Clickable demo (synthetic data, runs in the browser)

`export.py` runs the real app on the synthetic corpus and writes `data.json`
(pages, coverage, entities, timeline, and the SYNTHETIC fixture legal leads).
`build.py` merges it with `second_chair.json`, verifies every Second Chair
quotation word for word against the stored page text (the build fails on any
miss), and writes two files:

```bash
python build.py <data.json> <out_dir> [--fonts embedded.css]
# lexreview-demo.html             published as a claude.ai Artifact
# lexreview-demo-standalone.html  download and open in a browser (fonts embedded)
```

Sections: Overview (coverage ledger, discovery-by-topic chart), Second Chair,
Search, Ask a question, Timeline, People & organizations, Legal research
leads, Audit log.

**Second Chair** argues the side you pick (plaintiff or defendant) from your
stated position. Prepared analyses (arguments, anticipated arguments,
strategy, weaknesses) ship in `second_chair.json`. On the Artifact link it can
also draft live through the viewer's own Claude account (`sample`
capability); every quotation it returns is re-verified in the page, points
without a verified quotation are dropped, references to case law or statutes
and links are removed, and passages from documents flagged for AI-instruction
text are never sent. Offline (the downloaded file) it answers questions by
pointing to verified passages. This live mode is for the synthetic demo only:
the production app uses a local model (see the repository README).

The demo is keyword-search only and does not include the server's security
controls (encryption, MFA, audit log, sandboxed parsing).
