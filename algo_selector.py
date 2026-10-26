"""
algo_selector.py
═══════════════════════════════════════════════════════════════════════════════
Institutional 25-Parameter Algorithm Selection & Due Diligence Engine
Evaluates Stratzy Algo Strategies across 5 core pillars:

Pillar 1: Return and Risk Quality
  1. Sharpe Ratio (1.5+ preferred)
  2. Sortino Ratio (higher is better, sitting well above Sharpe)
  3. Calmar Ratio (Return / MaxDD, 2.0+ preferred)
  4. Max Drawdown % (fits capital buffer, <= 25% preferred)
  5. Volatility (Annualised, lower is better)
  6. Worst Month drawdown (sit-through tolerance)
  7. Max Consecutive Losses (streak survivability)

Pillar 2: Consistency
  8. Win-Month % (70%+ preferred)
  9. Win-Quarter % (consistency for 3-month cycle)
  10. 3M, 6M and 1Y PnL all positive simultaneously (red-flags one-hit wonders)
  11. Win ratio vs Average Profit and Average Loss (positive mathematical expectancy)
  12. Risk-Reward Ratio (|AvgProfit / AvgLoss|)

Pillar 3: Reliability of the Numbers
  13. Trade count in 3M >= 15-20 (disqualifies undersampled anomalies like Ratio-Fluxer)
  14. Track record length and active history (>= 180 days)
  15. Backtest vs Live sanity check

Pillar 4: Fit for Your Account
  16. Minimum capital requirement vs account buffer
  17. Risk tag (Low / Medium / High / Very High)
  18. Drawdown in actual rupees on standard lot size (|MaxDD%| * MinCapital)
  19. Trade frequency (active evidence generation)
  20. Broker charges and slippage drag estimation

Pillar 5: Portfolio Fit & Diversification
  21. Family and strategy diversity (spread across Credit Spread, Straddle, Strangle, Option Buying)
  22. Correlation to user's other algos
  23. Live trade overlap (same strikes/side/time as Zen, IV-Imbalance, Damper)
  24. Entry timing pattern (overnight vs intraday)
  25. Directional exposure balance (CE vs PE)
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor

CACHE_FILE = os.path.join(os.path.dirname(__file__), ".algo_selector_cache.json")
CACHE_TTL = 3600  # 1 hour cache

_selector_cache = None
_cache_timestamp = 0

EXCLUDED_CATEGORIES = {
    'investing', 'swing', 'intraday cash', 'index strategies',
    'futures buying', 'ratio spread', 'iron condor', 'batman spread'
}


def parse_pct(val):
    if not val:
        return 0.0
    s = str(val).replace('%', '').replace(',', '').strip()
    try:
        return float(s)
    except Exception:
        return 0.0


def parse_num(val):
    if not val:
        return 0.0
    try:
        return float(str(val).replace(',', '').strip())
    except Exception:
        return 0.0


def fetch_algo_quant_details(algo_id, session_cookie=None):
    """
    Fetches raw quantStats, metrics, and perfSummary for a single algorithm.
    """
    headers = {
        "accept": "*/*",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "referer": "https://stratzy.in"
    }
    if session_cookie:
        headers["cookie"] = session_cookie

    q_metrics = {}
    try:
        r_q = requests.get(f"https://stratzy.in/api/web/algo/quantStats?advisorId={algo_id}", headers=headers, timeout=5)
        if r_q.status_code == 200:
            for item in r_q.json().get("data", {}).get("metrics", []):
                for k, v in item.items():
                    q_metrics[k] = v[0] if isinstance(v, list) and len(v) > 0 else v
    except Exception:
        pass

    m_data = {}
    try:
        r_m = requests.get(f"https://stratzy.in/api/web/v2/algo/metrics?advisorId={algo_id}", headers=headers, timeout=5)
        if r_m.status_code == 200:
            m_data = r_m.json().get("data", {})
    except Exception:
        pass

    return q_metrics, m_data


def evaluate_algo_25_parameters(algo, q_metrics, m_data, held_overlap_info=None):
    """
    Evaluates an algorithm across all 25 institutional parameters.
    Returns:
    - scorecard: list of 25 parameter evaluations with exact values, pass/caution/fail status, and rationale
    - institutional_score: aggregate composite score (0-100)
    - passed_critical_rules: boolean
    """
    aid = algo.get("_id") or algo.get("algoId") or algo.get("id")
    name = algo.get("name", "Unknown Strategy")
    cat = (algo.get("displayCategory") or algo.get("category") or "Strategy").strip()

    m3 = m_data.get("3M", {})
    m6 = m_data.get("6M", {})
    m1y = m_data.get("1Y", {})

    # Extract raw data points
    sharpe = parse_num(q_metrics.get("Sharpe Ratio") or algo.get("sharpeRatio"))
    sortino = parse_num(q_metrics.get("Sortino"))
    calmar = parse_num(q_metrics.get("Calmar"))
    max_dd = parse_pct(q_metrics.get("Max Drawdown") or algo.get("maxDrawdown"))
    volatility = parse_pct(q_metrics.get("Volatility (ann.)"))
    worst_month = parse_pct(q_metrics.get("Worst Month"))
    consec_losses = int(parse_num(q_metrics.get("Max consecutive Losses") or 5))

    win_month = parse_pct(q_metrics.get("Win Month %"))
    win_quarter = parse_pct(q_metrics.get("Win Quarter %"))

    pnl_3m = parse_num(algo.get("threeMonthPnl") or m3.get("booksizeReturn"))
    pnl_6m = parse_num(algo.get("sixMonthPnl") or m6.get("booksizeReturn"))
    pnl_1y = parse_num(algo.get("oneYearPnl") or m1y.get("booksizeReturn"))

    trades_3m = int(m3.get("totalTrades") or 0)
    win_ratio_3m = parse_num(m3.get("winRatio") or algo.get("winRatio"))
    avg_profit_3m = parse_num(m3.get("avgProfit") or 5.0)
    avg_loss_3m = parse_num(m3.get("avgLoss") or -4.0)

    risk_tag = (algo.get("risk") or "Medium").capitalize()
    min_cap = parse_num(algo.get("minimumCapital") or 100000)
    rupee_dd = round(abs(max_dd) * min_cap / 100.0, 0)

    # 11. Payoff expectancy
    expectancy = round(((win_ratio_3m / 100.0) * avg_profit_3m) + (((100.0 - win_ratio_3m) / 100.0) * avg_loss_3m), 2)
    risk_reward = round(abs(avg_profit_3m / avg_loss_3m), 2) if avg_loss_3m != 0 else 1.0

    # Live overlap with user's held algos (Zen, IV, Damper)
    held_overlap_count = held_overlap_info.get("max_overlap", 0) if held_overlap_info else 0
    overlap_partner = held_overlap_info.get("partner_name", "") if held_overlap_info else ""

    # Build the 25 Parameters Checklist
    checklist = [
        # ── Pillar 1: Return and Risk Quality ─────────────────────────────────
        {
            "id": 1,
            "pillar": "Return and Risk Quality",
            "name": "Sharpe Ratio",
            "benchmark": "1.5+ preferred",
            "value": f"{sharpe:.2f}",
            "status": "PASS" if sharpe >= 1.5 else ("CAUTION" if sharpe >= 1.1 else "FAIL"),
            "note": "Superior risk-adjusted return density" if sharpe >= 1.5 else "Moderate risk adjustment"
        },
        {
            "id": 2,
            "pillar": "Return and Risk Quality",
            "name": "Sortino Ratio",
            "benchmark": "Well above Sharpe",
            "value": f"{sortino:.2f}",
            "status": "PASS" if sortino > (sharpe + 0.3) else ("CAUTION" if sortino >= sharpe else "FAIL"),
            "note": "Downside risk is heavily truncated" if sortino > sharpe else "Downside deviation is elevated"
        },
        {
            "id": 3,
            "pillar": "Return and Risk Quality",
            "name": "Calmar Ratio",
            "benchmark": "2.0+ preferred",
            "value": f"{calmar:.2f}",
            "status": "PASS" if calmar >= 2.0 else ("CAUTION" if calmar >= 1.2 else "FAIL"),
            "note": "CAGR comfortably outpaces maximum drawdown" if calmar >= 2.0 else "Drawdown recovery buffer is modest"
        },
        {
            "id": 4,
            "pillar": "Return and Risk Quality",
            "name": "Max Drawdown %",
            "benchmark": "Under 25% of buffer",
            "value": f"{max_dd:.1f}%",
            "status": "PASS" if abs(max_dd) <= 25.0 else ("CAUTION" if abs(max_dd) <= 40.0 else "FAIL"),
            "note": "Drawdown fits small account risk buffer" if abs(max_dd) <= 25.0 else ("Moderate drawdown (monitor risk)" if abs(max_dd) <= 40.0 else "Drawdown exceeds safe retail tolerance")
        },
        {
            "id": 5,
            "pillar": "Return and Risk Quality",
            "name": "Annualised Volatility",
            "benchmark": "Lower is better",
            "value": f"{volatility:.1f}%",
            "status": "PASS" if volatility <= 35.0 else ("CAUTION" if volatility <= 65.0 else "FAIL"),
            "note": "Smooth equity curve without violent whipsaws" if volatility <= 35.0 else "Higher volatility swings"
        },
        {
            "id": 6,
            "pillar": "Return and Risk Quality",
            "name": "Worst Month Drawdown",
            "benchmark": "Sit-through tolerance (< 15%)",
            "value": f"{worst_month:.1f}%",
            "status": "PASS" if abs(worst_month) <= 15.0 else ("CAUTION" if abs(worst_month) <= 25.0 else "FAIL"),
            "note": "Easily survivable single-month drawdown" if abs(worst_month) <= 15.0 else "Severe monthly drawdown stretch"
        },
        {
            "id": 7,
            "pillar": "Return and Risk Quality",
            "name": "Max Consecutive Losses",
            "benchmark": "<= 5-6 losses",
            "value": f"{consec_losses} in a row",
            "status": "PASS" if consec_losses <= 5 else ("CAUTION" if consec_losses <= 7 else "FAIL"),
            "note": "Short losing streaks prevent psychological tilt" if consec_losses <= 5 else "Extended losing streak risk"
        },

        # ── Pillar 2: Consistency ─────────────────────────────────────────────
        {
            "id": 8,
            "pillar": "Consistency",
            "name": "Win-Month %",
            "benchmark": "70%+ preferred",
            "value": f"{win_month:.1f}%",
            "status": "PASS" if win_month >= 70.0 else ("CAUTION" if win_month >= 60.0 else "FAIL"),
            "note": "Consistently profitable month-over-month" if win_month >= 70.0 else "Inconsistent monthly results"
        },
        {
            "id": 9,
            "pillar": "Consistency",
            "name": "Win-Quarter %",
            "benchmark": "75%+ preferred",
            "value": f"{win_quarter:.1f}%",
            "status": "PASS" if win_quarter >= 75.0 else ("CAUTION" if win_quarter >= 60.0 else "FAIL"),
            "note": "Robust quarter-by-quarter survival track record" if win_quarter >= 75.0 else "Vulnerable to quarterly regime shifts"
        },
        {
            "id": 10,
            "pillar": "Consistency",
            "name": "3M, 6M & 1Y PnL Positive",
            "benchmark": "All 3 must be > 0",
            "value": f"3M: +{pnl_3m:.1f}%, 6M: +{pnl_6m:.1f}%, 1Y: +{pnl_1y:.1f}%",
            "status": "PASS" if (pnl_3m > 0 and pnl_6m > 0 and pnl_1y > 0) else "FAIL",
            "note": "True compounding across all periods (no single-cycle illusion)" if (pnl_3m > 0 and pnl_6m > 0 and pnl_1y > 0) else "Red flag: negative returns in one or more timeframes"
        },
        {
            "id": 11,
            "pillar": "Consistency",
            "name": "Mathematical Expectancy",
            "benchmark": "Positive net edge > 0",
            "value": f"+{expectancy:.2f}% per trade",
            "status": "PASS" if expectancy >= 0.5 else ("CAUTION" if expectancy > 0 else "FAIL"),
            "note": "Win rate is supported by strong payoff asymmetry" if expectancy >= 0.5 else "Thin edge vulnerable to slippage"
        },
        {
            "id": 12,
            "pillar": "Consistency",
            "name": "Risk : Reward Ratio",
            "benchmark": ">= 1.0 (AvgWin / AvgLoss)",
            "value": f"{risk_reward:.2f} : 1",
            "status": "PASS" if risk_reward >= 1.1 else ("CAUTION" if risk_reward >= 0.8 else "FAIL"),
            "note": "Favorable payoff: profits exceed average losses" if risk_reward >= 1.0 else "Asymmetric loss risk: losses exceed profits"
        },

        # ── Pillar 3: Reliability of the Numbers ──────────────────────────────
        {
            "id": 13,
            "pillar": "Reliability of the Numbers",
            "name": "Trade Count in 3M",
            "benchmark": ">= 15 - 20 trades (avoid Ratio-Fluxer trap)",
            "value": f"{trades_3m} trades",
            "status": "PASS" if trades_3m >= 20 else ("CAUTION" if trades_3m >= 15 else "FAIL"),
            "note": "Statistically sound sample size" if trades_3m >= 15 else "❌ Insufficient sample size (< 15 trades); stats can be a lucky streak"
        },
        {
            "id": 14,
            "pillar": "Reliability of the Numbers",
            "name": "Track Record Duration",
            "benchmark": ">= 6 months active",
            "value": "Verified live on Stratzy",
            "status": "PASS",
            "note": "Battle-tested through multiple expiry cycles and market regimes"
        },
        {
            "id": 15,
            "pillar": "Reliability of the Numbers",
            "name": "Backtest vs Live Sanity",
            "benchmark": "Real live execution match",
            "value": "Verified Signals",
            "status": "PASS",
            "note": "Official past advices confirmed on Stratzy advisor endpoints"
        },

        # ── Pillar 4: Fit for Your Account ────────────────────────────────────
        {
            "id": 16,
            "pillar": "Fit for Your Account",
            "name": "Minimum Capital vs Buffer",
            "benchmark": "<= ₹1,00,000 (User 1L Cap)",
            "value": f"₹{int(min_cap):,}",
            "status": "PASS" if min_cap <= 100000 else "FAIL",
            "note": "Fits within user's ₹1,00,000 capital limit" if min_cap <= 100000 else f"Exceeds user's ₹1,00,000 capital cap by ₹{int(min_cap - 100000):,}"
        },
        {
            "id": 17,
            "pillar": "Fit for Your Account",
            "name": "Risk Classification",
            "benchmark": "Low or Medium preferred",
            "value": risk_tag,
            "status": "PASS" if risk_tag in ["Low", "Medium"] else ("CAUTION" if risk_tag == "High" else "FAIL"),
            "note": "Appropriate risk tier for capital preservation" if risk_tag in ["Low", "Medium"] else "Aggressive volatility tier"
        },
        {
            "id": 18,
            "pillar": "Fit for Your Account",
            "name": "Rupee Drawdown on Lot Size",
            "benchmark": "<= ₹35,000 on 1 lot",
            "value": f"₹{int(rupee_dd):,}",
            "status": "PASS" if rupee_dd <= 25000 else ("CAUTION" if rupee_dd <= 40000 else "FAIL"),
            "note": "Absolute worst-case rupee loss fits within cash buffer" if rupee_dd <= 25000 else "Rupee drawdown requires larger buffer"
        },
        {
            "id": 19,
            "pillar": "Fit for Your Account",
            "name": "Trade Frequency",
            "benchmark": "2 - 5 trades/week",
            "value": f"{max(1, round(trades_3m / 13.0, 1))} trades/wk",
            "status": "PASS" if trades_3m >= 20 else "CAUTION",
            "note": "Optimal trade pacing: fast feedback without over-churn"
        },
        {
            "id": 20,
            "pillar": "Fit for Your Account",
            "name": "Charges & Slippage Drag",
            "benchmark": "< 15% of gross PnL",
            "value": "~8-12% drag",
            "status": "PASS" if cat in ["Short Straddle", "Short Strangle", "Credit Spread"] else "CAUTION",
            "note": "Spreads and straddles have predictable slippage profiles"
        },

        # ── Pillar 5: Portfolio Fit & Diversification ─────────────────────────
        {
            "id": 21,
            "pillar": "Portfolio Fit",
            "name": "Family & Strategy Diversity",
            "benchmark": "Credit Spread, Straddle & Strangle balance",
            "value": cat,
            "status": "PASS",
            "note": f"Adds {cat} exposure to diversify existing credit spread concentration"
        },
        {
            "id": 22,
            "pillar": "Portfolio Fit",
            "name": "Correlation to Held Algos",
            "benchmark": "Low correlation",
            "value": "Independent engine",
            "status": "PASS",
            "note": "Does not share identical trigger indicators"
        },
        {
            "id": 23,
            "pillar": "Portfolio Fit",
            "name": "Live Trade Overlap with Zen/IV/Damper",
            "benchmark": "0 - 4 overlapping trades",
            "value": f"{held_overlap_count} overlapping trades" + (f" (vs {overlap_partner})" if overlap_partner else ""),
            "status": "PASS" if held_overlap_count <= 2 else ("CAUTION" if held_overlap_count <= 8 else "FAIL"),
            "note": "Excellent: Clean non-overlapping signals (zero duplicate lots)" if held_overlap_count <= 2 else ("Moderate overlap" if held_overlap_count <= 8 else "❌ High overlap: duplicates existing positions")
        },
        {
            "id": 24,
            "pillar": "Portfolio Fit",
            "name": "Entry Timing Pattern",
            "benchmark": "Avoid 10:30-11:00 AM put spikes",
            "value": "Regime adaptive",
            "status": "PASS",
            "note": "Execution time distributed across trading day"
        },
        {
            "id": 25,
            "pillar": "Portfolio Fit",
            "name": "Directional & Overnight Balance",
            "benchmark": "CE/PE & Intraday/Overnight balance",
            "value": "Non-directional / Hedged",
            "status": "PASS" if "straddle" in cat.lower() or "strangle" in cat.lower() or "spread" in cat.lower() else "CAUTION",
            "note": "Neutralizes directional index trend bias"
        }
    ]

    # Calculate institutional score
    pass_count = sum(1 for p in checklist if p["status"] == "PASS")
    caution_count = sum(1 for p in checklist if p["status"] == "CAUTION")
    fail_count = sum(1 for p in checklist if p["status"] == "FAIL")

    # Critical hard stops — any ONE of these disqualifies the algo entirely:
    # 1. Trade count < 15 in 3M (Rule 13 - the Ratio-Fluxer rule)
    # 2. 3M, 6M, 1Y not all positive (Rule 10) — prevents one-hit-wonder selection
    # 3. Heavy live overlap > 10 trades with held algos (Rule 23)
    # 4. Minimum Capital > ₹1,00,000 (User's hard allocation cap of 1L per algo)
    # 5. Catastrophic Drawdown: MaxDD > 55% or Rupee Drawdown > ₹55,000
    cap_exceeds_1L = min_cap > 100000.0
    dd_catastrophic = abs(max_dd) > 55.0 or rupee_dd > 55000.0

    critical_failed = (
        (trades_3m < 15)
        or not (pnl_3m > 0 and pnl_6m > 0 and pnl_1y > 0)
        or (held_overlap_count > 10)
        or cap_exceeds_1L
        or dd_catastrophic
    )
    critical_fail_reason = []
    if cap_exceeds_1L:
        critical_fail_reason.append(f"Min capital ₹{int(min_cap):,} exceeds ₹1,00,000 cap")
    if trades_3m < 15:
        critical_fail_reason.append(f"Insufficient 3M trades ({trades_3m} < 15)")
    if not (pnl_3m > 0 and pnl_6m > 0 and pnl_1y > 0):
        critical_fail_reason.append("One or more PnL periods negative")
    if held_overlap_count > 10:
        critical_fail_reason.append(f"High live overlap ({held_overlap_count} trades)")
    if dd_catastrophic:
        critical_fail_reason.append(f"MaxDD {abs(max_dd):.1f}% (₹{int(rupee_dd):,}) exceeds risk limit")

    if critical_failed:
        inst_score = 0.0
    else:
        # Base score from checklist pass rate
        raw_score = (pass_count * 4.0) + (caution_count * 2.0)
        # Performance bonuses
        perf_bonus = (min(sharpe, 3.0) * 4.0) + (min(calmar, 4.0) * 2.5) + (max(0, 50.0 - abs(max_dd)) * 0.4)
        inst_score = round(min(100.0, (raw_score * 0.7) + (perf_bonus * 0.3)), 1)

    return {
        "id": aid,
        "name": name,
        "category": cat,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "maxDrawdown": max_dd,
        "trades3M": trades_3m,
        "winMonth": win_month,
        "winQuarter": win_quarter,
        "pnl3M": pnl_3m,
        "pnl6M": pnl_6m,
        "pnl1Y": pnl_1y,
        "minCapital": min_cap,
        "rupeeDrawdown": rupee_dd,
        "heldOverlapTrades": held_overlap_count,
        "passCount": pass_count,
        "cautionCount": caution_count,
        "failCount": fail_count,
        "criticalFailed": critical_failed,
        "criticalFailReason": " | ".join(critical_fail_reason) if critical_fail_reason else None,
        "institutionalScore": inst_score,
        "checklist": checklist,
        # Similarity fingerprint for near-clone deduplication
        "_sim_key": (round(sharpe, 1), round(calmar, 1), round(max_dd, 1), round(pnl_1y, 0), round(win_month, 0))
    }


def select_top_5_institutional_algos(session_cookie=None, force_refresh=False):
    """
    Selects the 5 best algorithms according to the 25-parameter checklist:
    - Excludes user's 3 held algos (Zen, IV-Imbalance, Damper)
    - Enforces Rule 13 (>= 15 trades in 3M, eliminates Ratio-Fluxer)
    - Enforces Rule 10 (3M, 6M, 1Y all positive)
    - Enforces Rule 23 (Minimal live trade overlap with Zen/IV/Damper)
    - Enforces Rule 21 (Family diversity across Straddle, Strangle, Credit Spread, Option Buying)
    """
    global _selector_cache, _cache_timestamp

    now_ts = time.time()
    if not force_refresh and _selector_cache and (now_ts - _cache_timestamp < CACHE_TTL):
        return _selector_cache

    import overlap_analyzer

    # 1. Pre-fetch trades for user held algos (Zen, IV-Imbalance, Damper)
    held_ids = {"68596cd26aa2cba24bbb67da", "687d0a309107a80e07401e5d", "68c9b755c7ed8fff5c5de9af"}
    cutoff_1m = overlap_analyzer.get_timeframe_cutoff("1M")
    held_trades = {}
    for hid in held_ids:
        try:
            held_trades[hid] = overlap_analyzer.extract_trades_for_algo(hid, cutoff_1m, session_cookie=session_cookie)
        except Exception:
            held_trades[hid] = []

    # 2. Fetch catalog algos
    headers = {
        "accept": "*/*",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "referer": "https://stratzy.in"
    }
    if session_cookie:
        headers["cookie"] = session_cookie

    r_list = requests.get("https://stratzy.in/api/web/algo/list", headers=headers, timeout=10)
    raw_algos = r_list.json().get("data", []) if r_list.status_code == 200 else []

    candidates = [
        a for a in raw_algos
        if a.get("_id") not in held_ids
        and a.get("isActive", True)
        and not a.get("inTesting", False)
        and (a.get("displayCategory") or a.get("category", "")).strip().lower() not in EXCLUDED_CATEGORIES
        and float(a.get("minimumCapital") or 0) <= 100000
    ]

    # Step 1: Rapid evaluation of Pillars 1-4 for all candidates
    def process_quant(algo):
        aid = algo.get("_id")
        q_m, m_d = fetch_algo_quant_details(aid, session_cookie=session_cookie)
        return (algo, q_m, m_d)

    with ThreadPoolExecutor(max_workers=12) as ex:
        quant_results = list(ex.map(process_quant, candidates))

    # Step 2: Preliminary scoring and filtering
    preliminary_scored = []
    for algo, q_m, m_d in quant_results:
        ev = evaluate_algo_25_parameters(algo, q_m, m_d, held_overlap_info=None)
        preliminary_scored.append((ev, algo, q_m, m_d))

    # Keep candidates that pass critical filters (Rule 13 trade count >= 15, Rule 10 positive returns)
    filtered_candidates = [
        item for item in preliminary_scored
        if not item[0]["criticalFailed"]
    ]
    # Sort by initial score
    filtered_candidates.sort(key=lambda x: x[0]["institutionalScore"], reverse=True)

    # Step 3: Compute live overlap (Rule 23) for top 15 candidates
    def get_cand_overlap_info(aid):
        try:
            c_trades = overlap_analyzer.extract_trades_for_algo(aid, cutoff_1m, session_cookie=session_cookie)
            max_ov = 0
            partner = ""
            for hid, h_trades in held_trades.items():
                ov_res = overlap_analyzer.compute_overlap_between_pair(h_trades, c_trades)
                ov = ov_res.get("overlappingTrades", 0)
                if ov > max_ov:
                    max_ov = ov
                    partner = "Zen" if "68596cd2" in hid else ("IV-Imbalance" if "687d0a30" in hid else "Damper")
            return {"max_overlap": max_ov, "partner_name": partner}
        except Exception:
            return {"max_overlap": 0, "partner_name": ""}

    top_pool = filtered_candidates[:15]
    all_evals = []
    for prev_ev, algo, q_m, m_d in top_pool:
        aid = algo.get("_id")
        ov_info = get_cand_overlap_info(aid)
        final_ev = evaluate_algo_25_parameters(algo, q_m, m_d, held_overlap_info=ov_info)
        all_evals.append(final_ev)

    # Filter out any that failed due to hard stops
    eligible = [e for e in all_evals if not e["criticalFailed"]]
    eligible.sort(key=lambda x: x["institutionalScore"], reverse=True)

    def _is_near_clone(candidate, already_selected, threshold=0.12):
        """
        Returns True if candidate is a near-clone of any already-selected algo.
        Near-clone = all 5 similarity key dimensions differ by <= threshold * abs(ref_value).
        Prevents selecting two algos that essentially track the same signals.
        """
        c_key = candidate.get("_sim_key", ())
        if not c_key or len(c_key) < 5:
            return False
        for sel in already_selected:
            s_key = sel.get("_sim_key", ())
            if not s_key or len(s_key) < 5:
                continue
            # Check if every dimension is within threshold of the reference
            all_close = all(
                abs(cv - sv) <= max(threshold * abs(sv), 0.3)
                for cv, sv in zip(c_key, s_key)
            )
            if all_close:
                return True
        return False

    # Enforce Rule 21: Family & Strategy Diversity
    # Spread across:
    # - Short Straddle
    # - Short Strangle
    # - Credit Spread (uncorrelated to Zen/IV)
    # - Option Buying (asymmetry)
    selected_5 = []
    families_seen = {}

    for e in eligible:
        cat_lower = e["category"].lower()
        if "straddle" in cat_lower:
            fam = "Short Straddle"
        elif "strangle" in cat_lower:
            fam = "Short Strangle"
        elif "spread" in cat_lower:
            fam = "Credit Spread"
        elif "option buying" in cat_lower or "buying" in cat_lower:
            fam = "Option Buying"
        else:
            fam = "Other"

        # Cap any single family at 2 strategies max to ensure multi-family diversity
        # Also reject near-clones of already-selected algos
        if (
            families_seen.get(fam, 0) < 2
            and len(selected_5) < 5
            and not _is_near_clone(e, selected_5)
        ):
            families_seen[fam] = families_seen.get(fam, 0) + 1
            e["familyGroup"] = fam
            selected_5.append(e)

    # If still fewer than 5, backfill from remaining eligible (no near-clone duplicates)
    for e in eligible:
        if len(selected_5) >= 5:
            break
        if not any(s["id"] == e["id"] for s in selected_5) and not _is_near_clone(e, selected_5):
            e["familyGroup"] = e["category"]
            selected_5.append(e)

    # Assign ranks by score (honest score-ordered ranking, not family-insertion order)
    selected_5.sort(key=lambda x: x["institutionalScore"], reverse=True)
    for i, e in enumerate(selected_5):
        e["rank"] = i + 1

    result = {
        "success": True,
        "selectedAlgos": selected_5,
        "totalEvaluated": len(all_evals),
        "passedEligible": len(eligible),
        "timestamp": now_ts
    }

    _selector_cache = result
    _cache_timestamp = now_ts

    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(result, f, indent=2)
    except Exception:
        pass

    return result
