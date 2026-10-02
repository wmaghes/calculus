"""Tests for scoring.py's pure, network-free ranking functions.

Uses small synthetic rows shaped like market_data.json entries -- never live
yfinance data (the sandbox can't reach the network anyway). Run with:
    pytest stock-market-agent/tests/
"""

from __future__ import annotations

import config
import scoring


# --- normalize ---------------------------------------------------------


def test_normalize_midpoint() -> None:
    assert scoring.normalize(5, 0, 10) == 50.0


def test_normalize_endpoints() -> None:
    assert scoring.normalize(0, 0, 10) == 0.0
    assert scoring.normalize(10, 0, 10) == 100.0


def test_normalize_invert() -> None:
    assert scoring.normalize(0, 0, 10, invert=True) == 100.0
    assert scoring.normalize(10, 0, 10, invert=True) == 0.0


def test_normalize_hi_equals_lo_returns_midpoint() -> None:
    assert scoring.normalize(7, 5, 5) == 50.0


def test_normalize_clamps_out_of_range_values() -> None:
    assert scoring.normalize(-100, 0, 10) == 0.0
    assert scoring.normalize(100, 0, 10) == 100.0


# --- score_growth --------------------------------------------------------


def _growth_row(ticker: str, *, market_cap=1e9, revenue_growth=None, earnings_growth=None, momentum_6m=None) -> dict:
    row = {"ticker": ticker, "market_cap": market_cap}
    if revenue_growth is not None:
        row["revenue_growth"] = revenue_growth
    if earnings_growth is not None:
        row["earnings_growth"] = earnings_growth
    if momentum_6m is not None:
        row["momentum_6m"] = momentum_6m
    return row


def test_score_growth_ranks_higher_growth_first() -> None:
    rows = [
        _growth_row("LOW", revenue_growth=0.05, earnings_growth=0.03, momentum_6m=0.01),
        _growth_row("HIGH", revenue_growth=0.50, earnings_growth=0.40, momentum_6m=0.30),
        _growth_row("MID", revenue_growth=0.20, earnings_growth=0.15, momentum_6m=0.10),
    ]
    scored = scoring.score_growth(rows)
    assert [r["ticker"] for r in scored] == ["HIGH", "MID", "LOW"]
    for r in scored:
        assert "score" in r
        assert 0.0 <= r["score"] <= 100.0


def test_score_growth_excludes_rows_missing_market_cap_or_growth_signal() -> None:
    rows = [
        _growth_row("NO_CAP", market_cap=None, revenue_growth=0.5),
        _growth_row("NO_SIGNAL", revenue_growth=None, earnings_growth=None, momentum_6m=None),
        _growth_row("OK", revenue_growth=0.2),
    ]
    scored = scoring.score_growth(rows)
    tickers = [r["ticker"] for r in scored]
    assert tickers == ["OK"]


def test_score_growth_respects_top_n_cap() -> None:
    rows = [_growth_row(f"T{i}", revenue_growth=i / 100.0) for i in range(config.TOP_N_PER_CATEGORY + 10)]
    scored = scoring.score_growth(rows)
    assert len(scored) == config.TOP_N_PER_CATEGORY


# --- score_stability -------------------------------------------------------


def _stability_row(ticker: str, *, beta, volatility_annualized=None, dividend_yield=None, dividend_streak_years=None) -> dict:
    row = {"ticker": ticker, "beta": beta}
    if volatility_annualized is not None:
        row["volatility_annualized"] = volatility_annualized
    if dividend_yield is not None:
        row["dividend_yield"] = dividend_yield
    if dividend_streak_years is not None:
        row["dividend_streak_years"] = dividend_streak_years
    return row


def test_score_stability_prefers_low_beta() -> None:
    rows = [
        _stability_row("VOLATILE", beta=2.5, volatility_annualized=0.6),
        _stability_row("STEADY", beta=0.3, volatility_annualized=0.1, dividend_yield=0.03, dividend_streak_years=20),
    ]
    scored = scoring.score_stability(rows)
    assert scored[0]["ticker"] == "STEADY"
    for r in scored:
        assert 0.0 <= r["score"] <= 100.0


def test_score_stability_requires_numeric_beta() -> None:
    rows = [
        {"ticker": "NO_BETA"},
        _stability_row("HAS_BETA", beta=1.0),
    ]
    scored = scoring.score_stability(rows)
    assert [r["ticker"] for r in scored] == ["HAS_BETA"]


# --- score_nextgen ----------------------------------------------------------


def test_score_nextgen_includes_watchlist_ticker_regardless_of_growth() -> None:
    watchlisted = config.NEXT_GEN_WATCHLIST[0]
    rows = [
        {"ticker": watchlisted, "market_cap": 5e9, "revenue_growth": 0.01},
        {"ticker": "SMALL_HIGH_GROWTH", "market_cap": 1e9, "revenue_growth": 0.5},
        {"ticker": "BORING_LARGE_CAP", "market_cap": 500e9, "revenue_growth": 0.02},
    ]
    scored = scoring.score_nextgen(rows)
    tickers = [r["ticker"] for r in scored]
    assert watchlisted in tickers
    assert "SMALL_HIGH_GROWTH" in tickers
    assert "BORING_LARGE_CAP" not in tickers


def test_score_nextgen_watchlist_gets_thematic_bonus_over_non_watchlist() -> None:
    watchlisted = config.NEXT_GEN_WATCHLIST[0]
    rows = [
        {"ticker": watchlisted, "market_cap": 5e9, "revenue_growth": 0.31, "momentum_6m": 0.1},
        {"ticker": "NON_WATCHLIST", "market_cap": 5e9, "revenue_growth": 0.31, "momentum_6m": 0.1},
    ]
    scored = scoring.score_nextgen(rows)
    by_ticker = {r["ticker"]: r["score"] for r in scored}
    assert by_ticker[watchlisted] > by_ticker["NON_WATCHLIST"]


# --- score_shorts ------------------------------------------------------------


def test_score_shorts_prefers_higher_short_interest() -> None:
    rows = [
        {"ticker": "LOW_SHORT", "short_pct_float": 1.0, "momentum_6m": 0.1},
        {"ticker": "HIGH_SHORT", "short_pct_float": 35.0, "momentum_6m": -0.2, "peg_ratio": 4.0, "earnings_growth": -0.1},
    ]
    scored = scoring.score_shorts(rows)
    assert scored[0]["ticker"] == "HIGH_SHORT"
    for r in scored:
        assert 0.0 <= r["score"] <= 100.0


def test_score_shorts_requires_numeric_short_pct_float() -> None:
    rows = [
        {"ticker": "NO_SHORT_DATA"},
        {"ticker": "HAS_SHORT_DATA", "short_pct_float": 10.0},
    ]
    scored = scoring.score_shorts(rows)
    assert [r["ticker"] for r in scored] == ["HAS_SHORT_DATA"]
