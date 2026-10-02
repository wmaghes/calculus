"""Build the clickable demo.

    python build.py <data.json> <out_dir> [--fonts embedded.css]

Writes <out_dir>/lexreview-demo.html (for publishing as an Artifact, no
document wrapper) and <out_dir>/lexreview-demo-standalone.html (a complete
file to download and open in a browser; fonts embedded when --fonts is given).

Every quotation in second_chair.json must exist verbatim (whitespace-
normalized) in the cited document's stored page text, or the build fails.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_quote(pages: list, quote: str) -> tuple[int, int, int] | None:
    pat = re.compile(r"\s+".join(re.escape(w) for w in quote.split()))
    for page_no, _loc, text, *_ in pages:
        m = pat.search(text)
        if m:
            return page_no, m.start(), m.end()
    return None


def verify_chair(data: dict, chair: dict) -> int:
    by_name = {d["source_name"]: d["doc_id"] for d in data["docs"]}
    bad, n = [], 0
    for side in ("plaintiff", "defendant"):
        for section in ("arguments", "anticipate", "strategy", "gaps"):
            for pt in chair[side][section]:
                if not pt.get("cites"):
                    bad.append(f"{side}/{section}/{pt['title']}: no citation")
                for c in pt["cites"]:
                    n += 1
                    doc = by_name.get(c["doc"])
                    if not doc or not find_quote(data["pages"].get(doc, []), c["quote"]):
                        bad.append(f"{side}/{section}/{pt['title']}: not found in {c['doc']}: {c['quote']!r}")
    if bad:
        raise SystemExit("Second Chair quotes failed verification:\n  " + "\n  ".join(bad))
    return n


def main() -> None:
    args = sys.argv[1:]
    fonts = None
    if "--fonts" in args:
        i = args.index("--fonts")
        fonts = Path(args[i + 1]).read_text()
        del args[i:i + 2]
    data = json.loads(Path(args[0]).read_text())
    out = Path(args[1])
    chair = json.loads((HERE / "second_chair.json").read_text())
    print("verified quotes:", verify_chair(data, chair))
    data["chair"] = chair
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    page = (HERE / "template.html").read_text().replace("__DATA__", payload)
    (out / "lexreview-demo.html").write_text(page)

    # Standalone file: real document wrapper, embedded fonts, no-script notice.
    t = re.sub(r'<link rel="preconnect"[^>]*>\n', "", page)
    if fonts:
        t = re.sub(r'<link rel="stylesheet" href="https://fonts.googleapis.com[^>]*>',
                   lambda m: "<style>\n" + fonts + "\n</style>", t)
    title = re.search(r"<title>.*?</title>\n", t).group(0)
    t = t.replace(title, "", 1)
    noscript = (
        '<noscript><div style="max-width:560px;margin:15vh auto;padding:24px;font:16px/1.5 Georgia,serif;'
        'color:#0d1424;background:#fff;border:1px solid #c9ced8;border-radius:10px">'
        '<p style="margin:0 0 8px;font-size:20px">lexreview demo</p><p style="margin:0">This file is an '
        "interactive app. Your viewer opened it as a preview, which does not run apps. Save the file, then "
        "open it in Chrome, Safari, Edge or Firefox on a computer.</p></div></noscript>\n")
    head = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<meta name="description" content="Interactive demo of lexreview on a fictional, synthetic matter. '
            'Runs entirely in your browser.">\n' + title)
    i = t.index('<div class="shell">')
    (out / "lexreview-demo-standalone.html").write_text(
        head + t[:i] + "</head>\n<body>\n" + noscript + t[i:] + "\n</body>\n</html>\n")
    print("wrote", out / "lexreview-demo.html", "and", out / "lexreview-demo-standalone.html")


if __name__ == "__main__":
    main()
