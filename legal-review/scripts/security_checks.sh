#!/usr/bin/env bash
# Supply-chain and static checks. Run from legal-review/.
#   1. install only hash-verified pins
#   2. known-vulnerability scan of the runtime and dev locks
#   3. static security scan of the source
#   4. CycloneDX SBOM of the runtime dependency set
# Also scans for bidirectional-control characters (Trojan Source).
set -euo pipefail
pip-audit -r requirements.lock --require-hashes --disable-pip
pip-audit -r requirements-dev.lock --require-hashes --disable-pip
bandit -q -r src
cyclonedx-py requirements requirements.lock -o sbom.cdx.json --of JSON
python - <<'PY'
import pathlib, re, sys
bidi = re.compile("[\u202a-\u202e\u2066-\u2069\u200e\u200f\u061c]")
bad = [str(p) for d in ("src", "tests", "scripts") for p in pathlib.Path(d).rglob("*")
       if p.is_file() and p.suffix in (".py", ".sh", ".md", ".toml") and bidi.search(p.read_text(errors="strict"))]
if bad:
    sys.exit("bidirectional control characters found in: " + ", ".join(bad))
PY
echo "security checks passed"
