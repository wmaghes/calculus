"""Renders dashboard/research/<TICKER>/financials.html and market.html for
every company, plus a dashboard/research/index.html hub, from
data/research_data.json.
"""

import json
import os
import shutil

import config

HEAD = """<!doctype html>
<html lang="en">
<head>
<script>try{if(localStorage.getItem('siteTheme')==='light')document.documentElement.setAttribute('data-theme','light');}catch(e){}</script>
<meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink); font-family: "IBM Plex Sans", system-ui, sans-serif; padding-inline: 16px; padding-block: 28px 64px; }
  .wrap { max-width: 860px; margin: 0 auto; }
  h1, h2 { font-family: "Fraunces", Georgia, serif; text-wrap: balance; margin: 0; }
  .mono { font-family: "IBM Plex Mono", ui-monospace, monospace; font-variant-numeric: tabular-nums; }
  a { color: var(--accent); }
  nav.crumbs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; font-family: "IBM Plex Mono", monospace; font-size: 12px; }
  nav.crumbs a { text-decoration: none; border: 1px solid var(--border); border-radius: 999px; padding: 6px 12px; color: var(--ink); background: var(--surface); }
  nav.crumbs a.current { background: var(--accent-soft); color: var(--accent); border-color: transparent; font-weight: 600; }
  header.hero { padding-bottom: 18px; margin-bottom: 24px; border-bottom: 1px solid var(--border); }
  .eyebrow { font-family: "IBM Plex Mono", monospace; font-size: 11.5px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-faint); }
  h1.title { font-size: clamp(26px, 4.2vw, 36px); font-weight: 600; line-height: 1.05; margin-top: 4px; }
  .period { font-family: "IBM Plex Mono", monospace; font-size: 13px; color: var(--ink-muted); margin-top: 6px; }
  .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 20px 0; }
  .stat { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
  .stat .label { font-family: "IBM Plex Mono", monospace; font-size: 11px; color: var(--ink-faint); text-transform: uppercase; letter-spacing: 0.05em; }
  .stat .value { font-family: "IBM Plex Mono", monospace; font-size: 20px; font-weight: 600; margin-top: 4px; }
  .stat .sub { font-size: 11.5px; color: var(--ink-muted); margin-top: 2px; }
  .stat .value.pos { color: var(--pos); } .stat .value.neg { color: var(--neg); }
  .note { background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; font-size: 13.5px; line-height: 1.55; color: var(--ink-muted); margin: 18px 0; }
  .note strong { color: var(--ink); }
  .range-bar { margin: 10px 0 4px; }
  .range-track { position: relative; height: 6px; border-radius: 4px; background: var(--surface-2); }
  .range-fill { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--accent); border-radius: 2px; }
  .range-labels { display: flex; justify-content: space-between; font-family: "IBM Plex Mono", monospace; font-size: 11px; color: var(--ink-faint); margin-top: 4px; }
  footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--border); font-size: 11.5px; color: var(--ink-faint); font-family: "IBM Plex Mono", monospace; line-height: 1.7; }
  @media (max-width: 480px) { .stat-grid { grid-template-columns: 1fr 1fr; } }
</style>
<link rel="stylesheet" href="{theme_href}">
</head>
<body>
"""

FOOT = "</body>\n</html>\n"


def head(title, theme_href):
    return HEAD.replace("{title}", title).replace("{theme_href}", theme_href)


def site_nav(base, active):
    return (
        f'<div id="siteNav"></div>'
        f'<script>window.SITE_NAV = {{ base: "{base}", active: "{active}" }};</script>'
        f'<script src="{base}assets/nav.js"></script>'
    )


def fmt(value, suffix=""):
    if value is None:
        return "n/a"
    return f"{value}{suffix}"


def pct(value, decimals=1):
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def crumbs(ticker, current):
    def link(label, href, key):
        cls = ' class="current"' if key == current else ""
        return f'<a href="{href}"{cls}>{label}</a>'
    return (
        '<nav class="crumbs">'
        + link("&larr; All companies", "../index.html", "index")
        + link(f"{ticker} Financials", "financials.html", "financials")
        + link(f"{ticker} Market Data", "market.html", "market")
        + "</nav>"
    )


def stat(label, value, sub=None, cls=""):
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return f'<div class="stat"><div class="label">{label}</div><div class="value mono {cls}">{value}</div>{sub_html}</div>'


def render_financials(company):
    ticker = company["ticker"]
    fin = company["financials"]
    if not fin:
        body = '<p>No 10-K figures were confidently sourced for this company in this pass.</p>'
    else:
        growth_cls = "pos" if (fin.get("revenue_growth") or 0) >= 0 else "neg"
        stats = [
            stat("Revenue", fmt(fin.get("revenue"))),
            stat("Revenue growth YoY", pct(fin.get("revenue_growth")), cls=growth_cls if fin.get("revenue_growth") is not None else ""),
            stat("Gross margin", fmt(fin.get("gross_margin"), "%") if fin.get("gross_margin") is not None else "n/a"),
            stat("Net income", fmt(fin.get("net_income"))),
            stat("Total assets", fmt(fin.get("total_assets"))),
            stat("Total debt", fmt(fin.get("total_debt"))),
        ]
        note = fin.get("note", "")
        source = fin.get("source_url")
        source_html = f'<a href="{source}">SEC filing</a>' if source else "n/a"
        body = f"""
      <div class="stat-grid">{''.join(stats)}</div>
      <div class="note"><strong>Filing notes.</strong> {note}<br><br><strong>Source:</strong> {source_html}</div>
        """
    return f"""{head(f"{ticker} Financials", "../../assets/theme.css")}
{site_nav("../../", "research")}
<div class="wrap">
  {crumbs(ticker, "financials")}
  <header class="hero">
    <div class="eyebrow">Research Analyst &middot; Financials (10-K)</div>
    <h1 class="title">{company['name']} <span class="mono" style="color:var(--ink-faint)">{ticker}</span></h1>
    <div class="period">Period: {fin.get('period', 'n/a')}</div>
  </header>
  {body}
  <footer>
    Figures are drawn from each company's most recent 10-K / annual report available via web search in this session, not a live XBRL feed.
    See the companion <span class="mono">fetch_10k.py</span> script for the real SEC EDGAR-based pipeline this stands in for.
    Not investment advice.
  </footer>
</div>
{FOOT}"""


def render_market(company):
    ticker = company["ticker"]
    ratios = company["ratios"]
    market = company["market"]
    price = market.get("price")
    stats = []
    if price is not None:
        stats.append(stat("Price", f"${price:,.2f}"))
    if market.get("mktCap"):
        stats.append(stat("Market cap", market["mktCap"]))
    if ratios.get("trailing_pe") is not None:
        stats.append(stat("Trailing P/E", f"{ratios['trailing_pe']:.2f}"))
    if ratios.get("forward_pe") is not None:
        stats.append(stat("Forward P/E", f"{ratios['forward_pe']:.2f}"))
    if ratios.get("price_to_book") is not None:
        stats.append(stat("Price / book", f"{ratios['price_to_book']:.2f}"))
    if ratios.get("price_to_sales") is not None:
        stats.append(stat("Price / sales", f"{ratios['price_to_sales']:.2f}"))
    if market.get("divYield") is not None:
        stats.append(stat("Dividend yield", f"{market['divYield']:.2f}%"))
    if market.get("beta") is not None:
        stats.append(stat("Beta (5yr)", f"{market['beta']:.2f}"))

    range_html = ""
    lo, hi = ratios.get("week52_low"), ratios.get("week52_high")
    if lo is not None and hi is not None and price is not None and hi > lo:
        position = max(0.0, min(100.0, (price - lo) / (hi - lo) * 100))
        range_html = f"""
      <div class="range-bar">
        <div class="label mono" style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--ink-faint);text-transform:uppercase;letter-spacing:.05em;">52-week range</div>
        <div class="range-track"><div class="range-fill" style="left:{position}%"></div></div>
        <div class="range-labels"><span>${lo:,.2f}</span><span>${hi:,.2f}</span></div>
      </div>
        """

    note = ratios.get("note", "")
    note_html = f'<div class="note">{note}</div>' if note else ""

    if not stats and not range_html:
        body = "<p>No market ratios were confidently sourced for this company in this pass.</p>"
    else:
        body = f'<div class="stat-grid">{"".join(stats)}</div>{range_html}{note_html}'

    return f"""{head(f"{ticker} Market Data", "../../assets/theme.css")}
{site_nav("../../", "research")}
<div class="wrap">
  {crumbs(ticker, "market")}
  <header class="hero">
    <div class="eyebrow">Research Analyst &middot; Market Data &amp; Ratios</div>
    <h1 class="title">{company['name']} <span class="mono" style="color:var(--ink-faint)">{ticker}</span></h1>
    <div class="period">Live figures reused from the Market Scanner where available; ratios added from web search.</div>
  </header>
  {body}
  <footer>
    Price, market cap, dividend yield and beta are shared with the Market Scanner's own daily refresh.
    Valuation ratios (P/E, P/B, P/S) and 52-week ranges are a one-time snapshot from this session.
    Not investment advice.
  </footer>
</div>
{FOOT}"""


def render_index(companies):
    rows = []
    for ticker, company in sorted(companies.items()):
        rows.append(f"""
        <div class="row">
          <div class="id"><div class="ticker mono">{ticker}</div><div class="name">{company['name']}</div></div>
          <div class="links">
            <a href="{ticker}/financials.html">Financials</a>
            <a href="{ticker}/market.html">Market Data</a>
          </div>
        </div>""")
    return f"""{head("Research Analyst", "../assets/theme.css")}
<style>
  .rows {{ display: flex; flex-direction: column; border-top: 1px solid var(--border); }}
  .row {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 4px; border-bottom: 1px solid var(--border); flex-wrap: wrap; }}
  .row .ticker {{ font-weight: 600; font-size: 15px; }}
  .row .name {{ font-size: 12px; color: var(--ink-faint); }}
  .row .links {{ display: flex; gap: 8px; font-family: "IBM Plex Mono", monospace; font-size: 12.5px; }}
  .row .links a {{ text-decoration: none; border: 1px solid var(--border); border-radius: 999px; padding: 5px 11px; background: var(--surface); }}
</style>
{site_nav("../", "research")}
<div class="wrap">
  <header class="hero">
    <div class="eyebrow">Research Analyst Agent</div>
    <h1 class="title">Company Research</h1>
    <div class="period">10-K financials and market ratios for every company on the Market Scanner watchlist, {len(companies)} companies.</div>
  </header>
  <div class="rows">{''.join(rows)}</div>
  <footer>
    Ask about any company's 10-K financials or valuation ratios in chat and this site updates.
    Not investment advice.
  </footer>
</div>
{FOOT}"""


def main():
    with open(os.path.join(config.DATA_DIR, "research_data.json")) as f:
        data = json.load(f)
    companies = data["companies"]

    for ticker, company in companies.items():
        out_dir = os.path.join(config.RESEARCH_DIR, ticker)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "financials.html"), "w") as f:
            f.write(render_financials(company))
        with open(os.path.join(out_dir, "market.html"), "w") as f:
            f.write(render_market(company))

    os.makedirs(config.RESEARCH_DIR, exist_ok=True)
    with open(os.path.join(config.RESEARCH_DIR, "index.html"), "w") as f:
        f.write(render_index(companies))

    # Also copy the raw JSON so the Simulator's Investment Banker mode can
    # fetch net income / market cap client-side without a backend.
    shutil.copy(
        os.path.join(config.DATA_DIR, "research_data.json"),
        os.path.join(config.RESEARCH_DIR, "data.json"),
    )

    print(f"wrote {len(companies)} companies x 2 pages + index to {config.RESEARCH_DIR}")


if __name__ == "__main__":
    main()
