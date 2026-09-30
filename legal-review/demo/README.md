# Clickable demo (synthetic data, runs in the browser)

`export.py` runs the real app on the synthetic corpus and writes `data.json`
(pages, coverage, entities, timeline, and the SYNTHETIC fixture legal leads).
`template.html` is the single-page demo; replace `__DATA__` with the JSON
(escape `</` as `<\/`) to build it. The demo is keyword-search only, uses the
extractive (no-model) Q&A mode, and does not include the server's security
controls (encryption, MFA, audit log, sandboxed parsing).
