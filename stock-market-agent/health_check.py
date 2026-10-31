"""Daily health & compliance check for the Market Scanner dashboard.

Two kinds of findings, deliberately kept separate:

- PIPELINE BREAKS: objective data/structure problems (bad JSON, wrong entry
  counts, duplicate tickers, missing static fields, mojibake, a stale
  `generated` date, failing test suites). These are safe for an agent to
  auto-repair (usually by reverting dashboard/data.json to the last good
  git commit, fixing the environment, and re-running tests) because the
  daily refresh routine already validates all of this before it ever
  commits -- so a failure here means something corrupted the working tree
  *after* a good commit, not a bad data value that needs judgment.

- COMPLIANCE FLAGS: a missing "not investment advice" disclaimer on a page,
  or blurb/holdingsNote copy using absolute-certainty language ("guaranteed",
  "can't lose", etc). These need a human's judgment on the exact wording,
  so this script only reports them -- it never edits disclaimer or blurb
  text on its own.

Run directly: `python3 health_check.py`. Exit code 0 means no pipeline
breaks (compliance flags may still be present and are printed either way);
exit code 1 means at least one pipeline break was found.
"""

import json
import os
import re
import subprocess
import sys
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "dashboard", "data.json")

EXPECTED_COUNTS = {"growth": 25, "stability": 25, "nextgen": 25, "shorts": 25, "funds": 16}
STATIC_FIELDS_COMMON = ["sector", "industry", "fortune100", "fortune100Rank", "capTier"]
STATIC_FIELDS_EXTRA = {
    "stability": ["streak"],
    "nextgen": ["theme"],
    "funds": ["assetType"],  # expenseRatio only applies to etf/mutual_fund entries, checked separately
}
MOJIBAKE_RE = re.compile(r"Ã.|â€.")
STALE_WARN_DAYS = 2
STALE_BREAK_DAYS = 5

# Pages that must carry a disclaimer. Checked for either phrase, case-insensitive.
DISCLAIMER_PAGES = [
    "dashboard/index.html",
    "dashboard/research/index.html",
    "dashboard/guide/index.html",
    "dashboard/scanner/growth.html",
    "dashboard/scanner/stability.html",
    "dashboard/scanner/nextgen.html",
    "dashboard/scanner/shorts.html",
    "dashboard/scanner/funds.html",
]
DISCLAIMER_PHRASES = ["not investment advice", "not financial advice"]

# Absolute-certainty language that has no place in investment-research copy.
RISKY_PHRASES = [
    "guaranteed", "can't lose", "cannot lose", "sure thing", "risk-free", "risk free",
    "no risk", "certain to rise", "certain to fall", "will definitely", "100% certain",
    "can't miss", "cannot miss", "surefire", "sure bet",
]

breaks = []
warnings = []
compliance = []


def check_data_json():
    if not os.path.exists(DATA_PATH):
        breaks.append("dashboard/data.json does not exist")
        return None
    with open(DATA_PATH, encoding="utf-8") as f:
        raw = f.read()
    if MOJIBAKE_RE.search(raw):
        breaks.append("Mojibake (double-encoded UTF-8) found in dashboard/data.json")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        breaks.append(f"dashboard/data.json is not valid JSON: {e}")
        return None

    generated = data.get("generated")
    if not generated:
        breaks.append("dashboard/data.json has no 'generated' date field")
    else:
        try:
            gen_date = date.fromisoformat(generated)
            age_days = (date.today() - gen_date).days
            if age_days >= STALE_BREAK_DAYS:
                breaks.append(
                    f"dashboard/data.json is {age_days} days stale (generated={generated}) "
                    "-- the daily refresh routine appears to have stopped running"
                )
            elif age_days >= STALE_WARN_DAYS:
                warnings.append(
                    f"dashboard/data.json is {age_days} days old (generated={generated}); "
                    "presenting this as current data is a compliance-adjacent staleness risk "
                    "if it keeps growing"
                )
        except ValueError:
            breaks.append(f"dashboard/data.json 'generated' field is not a valid date: {generated!r}")

    categories = data.get("categories", {})
    for cat, expected_n in EXPECTED_COUNTS.items():
        entries = categories.get(cat)
        if entries is None:
            breaks.append(f"category '{cat}' is missing from dashboard/data.json")
            continue
        if len(entries) != expected_n:
            breaks.append(f"category '{cat}' has {len(entries)} entries, expected {expected_n}")

        tickers = [e.get("ticker") for e in entries]
        dupes = {t for t in tickers if tickers.count(t) > 1}
        if dupes:
            breaks.append(f"category '{cat}' has duplicate tickers: {sorted(dupes)}")

        required = STATIC_FIELDS_COMMON + STATIC_FIELDS_EXTRA.get(cat, [])
        for e in entries:
            missing = [f for f in required if f not in e]
            if cat == "funds" and e.get("assetType") in ("etf", "mutual_fund") and "expenseRatio" not in e:
                missing.append("expenseRatio")
            if missing:
                breaks.append(f"category '{cat}' ticker {e.get('ticker')!r} missing fields: {missing}")

    return data


def check_risky_language(data):
    if not data:
        return
    for cat, entries in data.get("categories", {}).items():
        for e in entries:
            for field in ("blurb", "holdingsNote"):
                text = e.get(field)
                if not text:
                    continue
                lower = text.lower()
                for phrase in RISKY_PHRASES:
                    if phrase in lower:
                        compliance.append(
                            f"{cat}/{e.get('ticker')}: {field} contains absolute-certainty "
                            f"language ({phrase!r}): \"{text}\""
                        )


def check_disclaimers():
    for rel_path in DISCLAIMER_PAGES:
        full_path = os.path.join(BASE_DIR, rel_path)
        if not os.path.exists(full_path):
            warnings.append(f"expected page missing, could not check disclaimer: {rel_path}")
            continue
        with open(full_path, encoding="utf-8") as f:
            content = f.read().lower()
        if not any(phrase in content for phrase in DISCLAIMER_PHRASES):
            compliance.append(f"{rel_path}: no 'not investment/financial advice' disclaimer found")


def run_tests():
    node_result = subprocess.run(
        ["node", "--test"], cwd=BASE_DIR, capture_output=True, text=True, timeout=120
    )
    if node_result.returncode != 0:
        breaks.append(
            "node --test failed (exit "
            f"{node_result.returncode}): {node_result.stdout[-800:]}{node_result.stderr[-800:]}"
        )

    pytest_result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        cwd=BASE_DIR, capture_output=True, text=True, timeout=120,
    )
    if pytest_result.returncode != 0:
        breaks.append(
            "pytest failed (exit "
            f"{pytest_result.returncode}): {pytest_result.stdout[-800:]}{pytest_result.stderr[-800:]}"
        )


def main():
    data = check_data_json()
    check_risky_language(data)
    check_disclaimers()
    run_tests()

    print("=== PIPELINE BREAKS ===")
    print("None" if not breaks else "")
    for b in breaks:
        print(f" - {b}")

    print("\n=== WARNINGS ===")
    print("None" if not warnings else "")
    for w in warnings:
        print(f" - {w}")

    print("\n=== COMPLIANCE FLAGS (report only, do not auto-fix) ===")
    print("None" if not compliance else "")
    for c in compliance:
        print(f" - {c}")

    print(f"\nSummary: {len(breaks)} break(s), {len(warnings)} warning(s), {len(compliance)} compliance flag(s).")
    return 1 if breaks else 0


if __name__ == "__main__":
    sys.exit(main())
