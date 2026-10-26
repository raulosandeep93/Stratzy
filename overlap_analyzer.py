"""
overlap_analyzer.py
═══════════════════════════════════════════════════════════════════════════════
Trade Overlap & Portfolio Correlation Analyzer for Stratzy Algo Strategies.

Purely depends on official Stratzy signals & past advices from:
GET https://stratzy.in/api/web/pastAdvices?advisorId={algo_id}&filter=All&chunk_size=100&offset=0

Calculates:
1. Exact contract overlap (same trading day, same strike/contract/symbol)
2. Overlapping active trading sessions / days
3. Portfolio trade concentration between held algos and suggested top picks
4. Flexible timeframe filtering: 1M (30d), 3M (90d), 6M (180d), YTD, All Time
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta

CACHE_FILE = os.path.join(os.path.dirname(__file__), ".stratzy_advices_cache.json")
CACHE_TTL = 7200  # 2 hours

# Memory cache for past advices: { algo_id: { "cached_at": ts, "advices": [...] } }
_advices_cache = {}


def parse_iso_utc_to_ist(ts):
    """Parses ISO timestamp (e.g. 2026-10-14T05:07:31.049Z) and converts UTC to IST."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        ist_dt = dt.astimezone(timezone(timedelta(hours=5, minutes=30)))
        return ist_dt.replace(tzinfo=None)
    except Exception:
        return None


def _load_disk_cache():
    global _advices_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
            now = time.time()
            # keep non-expired
            _advices_cache = {
                aid: item for aid, item in data.items()
                if now - item.get("cached_at", 0) < CACHE_TTL
            }
        except Exception:
            _advices_cache = {}


def _save_disk_cache():
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(_advices_cache, f)
    except Exception:
        pass


def fetch_algo_advices(algo_id, session_cookie=None, force_refresh=False):
    """
    Fetches up to 100 past advices for an algo directly from Stratzy API.
    Caches responses in-memory and on disk with 2h TTL.
    """
    global _advices_cache
    if not _advices_cache:
        _load_disk_cache()

    now_ts = time.time()
    if not force_refresh and algo_id in _advices_cache:
        item = _advices_cache[algo_id]
        if now_ts - item.get("cached_at", 0) < CACHE_TTL:
            return item.get("advices", [])

    headers = {
        "accept": "*/*",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "referer": "https://stratzy.in"
    }
    if session_cookie:
        headers["cookie"] = session_cookie

    url = f"https://stratzy.in/api/web/pastAdvices?advisorId={algo_id}&filter=All&chunk_size=100&offset=0"
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            advices = resp.json().get("pastAdvices", [])
            _advices_cache[algo_id] = {
                "cached_at": now_ts,
                "advices": advices
            }
            _save_disk_cache()
            return advices
    except Exception as e:
        print(f"[overlap_analyzer] Error fetching advices for {algo_id}: {e}")

    return _advices_cache.get(algo_id, {}).get("advices", [])


def get_timeframe_cutoff(timeframe):
    """Returns datetime cutoff for the given timeframe filter."""
    now = datetime.now()
    tf = (timeframe or "1M").upper().strip()
    if tf == "1M":
        return now - timedelta(days=30)
    elif tf == "3M":
        return now - timedelta(days=90)
    elif tf == "6M":
        return now - timedelta(days=180)
    elif tf == "YTD":
        return datetime(now.year, 1, 1)
    elif tf == "ALL":
        return datetime(2020, 1, 1)
    else:
        return now - timedelta(days=30)


def extract_trades_for_algo(algo_id, cutoff, session_cookie=None):
    """
    Extracts normalized trade records for an algo filtered by cutoff date.
    Returns list of dicts: { date: 'YYYY-MM-DD', symbol: '...', side: '...', advId: '...' }
    """
    advices = fetch_algo_advices(algo_id, session_cookie=session_cookie)
    trades = []
    for adv in advices:
        dt = parse_iso_utc_to_ist(adv.get("createdAt"))
        if not dt or dt < cutoff:
            continue
        date_str = dt.strftime("%Y-%m-%d")
        for tr in adv.get("trades", []):
            sym = tr.get("symbol")
            if not sym:
                continue
            trades.append({
                "date": date_str,
                "symbol": sym.strip().upper(),
                "side": tr.get("transactionType", "").upper(),
                "advId": adv.get("_id")
            })
    return trades


def compute_overlap_between_pair(trades_a, trades_b):
    """
    Computes exact overlap stats between two lists of trades.
    Overlap criteria: Same date and same contract symbol.
    """
    set_a = {(t["date"], t["symbol"]) for t in trades_a}
    set_b = {(t["date"], t["symbol"]) for t in trades_b}

    common_contracts = set_a & set_b
    overlapping_trades = len(common_contracts)

    days_a = {t["date"] for t in trades_a}
    days_b = {t["date"] for t in trades_b}
    common_days = len(days_a & days_b)
    total_active_days = len(days_a | days_b)

    total_a = len(trades_a)
    total_b = len(trades_b)

    pct_a = round((overlapping_trades / total_a * 100), 1) if total_a > 0 else 0.0
    pct_b = round((overlapping_trades / total_b * 100), 1) if total_b > 0 else 0.0

    # Risk level classification
    if overlapping_trades >= 10 or max(pct_a, pct_b) >= 40:
        level = "HIGH"
        risk_label = "🔴 Heavy Overlap (High Duplication)"
    elif overlapping_trades >= 3 or max(pct_a, pct_b) >= 15:
        level = "MODERATE"
        risk_label = "🟡 Moderate Overlap (Partial Overlap)"
    else:
        level = "LOW"
        risk_label = "🟢 Low / Zero Overlap (Great Diversifier)"

    return {
        "overlappingTrades": overlapping_trades,
        "sameDayOverlap": common_days,
        "totalActiveDays": total_active_days,
        "totalTradesA": total_a,
        "totalTradesB": total_b,
        "overlapPctA": pct_a,
        "overlapPctB": pct_b,
        "level": level,
        "riskLabel": risk_label
    }


def analyze_portfolio_overlap(timeframe="1M", session_cookie=None, candidate_suggested=None):
    """
    Main entry point for Portfolio Overlap Analysis.
    Compares:
    - 3 user-invested algos (Zen, IV-Imbalance, Damper)
    - 5 suggested top pick algos from Stratzy
    """
    import stratzy_reconciler

    # 1. Fetch user's held algos
    invested = stratzy_reconciler.fetch_user_invested_algos(session_cookie)
    held_algos = []
    for a in invested:
        held_algos.append({
            "id": a["id"],
            "name": a["name"],
            "type": "held",
            "category": a.get("category", "Index Strategies")
        })

    # Default fallback to the verified 3 deployed algos if needed
    if not held_algos:
        held_algos = [
            {"id": "68596cd26aa2cba24bbb67da", "name": "Zen Credit Spread Overnight", "type": "held", "category": "Index Strategies"},
            {"id": "687d0a309107a80e07401e5d", "name": "IV-Imbalance Credit Spread Overnight", "type": "held", "category": "Index Strategies"},
            {"id": "68c9b755c7ed8fff5c5de9af", "name": "Damper Credit Spread", "type": "held", "category": "Index Strategies"}
        ]

    held_ids = {h["id"] for h in held_algos}

    # 2. Determine top 5 suggested algos (non-held)
    suggested_algos = []
    if candidate_suggested and isinstance(candidate_suggested, list):
        for s in candidate_suggested:
            sid = s.get("_id") or s.get("id")
            if sid and sid not in held_ids and len(suggested_algos) < 5:
                suggested_algos.append({
                    "id": sid,
                    "name": s.get("name", "Suggested Algo"),
                    "type": "suggested",
                    "category": s.get("displayCategory") or s.get("category", "")
                })

    # If fewer than 5 provided, pull from 25-parameter institutional selection engine
    if len(suggested_algos) < 5:
        try:
            import algo_selector
            top_inst = algo_selector.select_top_5_institutional_algos(session_cookie=session_cookie)
            for a in top_inst.get("selectedAlgos", []):
                aid = a.get("id")
                if aid not in held_ids and not any(s["id"] == aid for s in suggested_algos) and len(suggested_algos) < 5:
                    suggested_algos.append({
                        "id": aid,
                        "name": a.get("name"),
                        "type": "suggested",
                        "category": a.get("category", "Strategy"),
                        "institutionalScore": a.get("institutionalScore"),
                        "sharpe": a.get("sharpe"),
                        "calmar": a.get("calmar"),
                        "maxDrawdown": a.get("maxDrawdown")
                    })
        except Exception as e:
            print(f"[overlap_analyzer] Error getting institutional algos: {e}")

    # Fallback default 5 top suggested algos with confirmed active Stratzy advices
    if len(suggested_algos) < 5:
        default_suggested = [
            {"id": "698075eaf867bf12b20442e5", "name": "Ratio-Fluxer Credit Spread Expiry", "type": "suggested", "category": "Credit Spread"},
            {"id": "6a7d8b6135b2bb8297f674e7", "name": "Takashi Kotegawa Option Buying", "type": "suggested", "category": "Option Buying"},
            {"id": "687d08f09107a80e07401e57", "name": "Curvature Credit Spread Overnight", "type": "suggested", "category": "Credit Spread"},
            {"id": "672ddda758f8d0f97e2d0c25", "name": "Intraday Short Strangle", "type": "suggested", "category": "Short Strangle"},
            {"id": "6a5db852a98a2cc087e856e9", "name": "Synthesized Gate", "type": "suggested", "category": "Option Buying"}
        ]
        existing_sugg_ids = {s["id"] for s in suggested_algos}
        for ds in default_suggested:
            if ds["id"] not in held_ids and ds["id"] not in existing_sugg_ids and len(suggested_algos) < 5:
                suggested_algos.append(ds)

    all_algos = held_algos + suggested_algos
    cutoff = get_timeframe_cutoff(timeframe)

    # 3. Extract trades per algo for this timeframe
    trades_by_algo = {}
    for a in all_algos:
        trades_by_algo[a["id"]] = extract_trades_for_algo(a["id"], cutoff, session_cookie=session_cookie)
        a["totalTrades"] = len(trades_by_algo[a["id"]])

    # 4. Compute full pairwise matrix
    matrix = {}
    overlap_pairs = []

    for i, a1 in enumerate(all_algos):
        aid1 = a1["id"]
        matrix[aid1] = {}
        for j, a2 in enumerate(all_algos):
            aid2 = a2["id"]
            if aid1 == aid2:
                matrix[aid1][aid2] = {
                    "overlappingTrades": len(trades_by_algo[aid1]),
                    "sameDayOverlap": len({t["date"] for t in trades_by_algo[aid1]}),
                    "totalActiveDays": len({t["date"] for t in trades_by_algo[aid1]}),
                    "totalTradesA": len(trades_by_algo[aid1]),
                    "totalTradesB": len(trades_by_algo[aid1]),
                    "overlapPctA": 100.0,
                    "overlapPctB": 100.0,
                    "level": "SELF",
                    "riskLabel": "Identical Strategy"
                }
            else:
                stats = compute_overlap_between_pair(trades_by_algo[aid1], trades_by_algo[aid2])
                matrix[aid1][aid2] = stats
                if i < j:
                    overlap_pairs.append({
                        "algoA": a1,
                        "algoB": a2,
                        **stats
                    })

    # 5. Extract specific held-vs-held key findings for user's portfolio
    held_findings = []
    for i in range(len(held_algos)):
        for j in range(i + 1, len(held_algos)):
            h1, h2 = held_algos[i], held_algos[j]
            st = matrix[h1["id"]][h2["id"]]
            held_findings.append({
                "pairName": f"{h1['name']} & {h2['name']}",
                "algo1": h1["name"],
                "algo2": h2["name"],
                "algo1Id": h1["id"],
                "algo2Id": h2["id"],
                "overlappingTrades": st["overlappingTrades"],
                "sameDayOverlap": st["sameDayOverlap"],
                "totalTradesA": st["totalTradesA"],
                "totalTradesB": st["totalTradesB"],
                "overlapPctA": st["overlapPctA"],
                "overlapPctB": st["overlapPctB"],
                "level": st["level"],
                "riskLabel": st["riskLabel"]
            })

    return {
        "success": True,
        "timeframe": timeframe,
        "cutoffDate": cutoff.strftime("%Y-%m-%d"),
        "heldAlgos": held_algos,
        "suggestedAlgos": suggested_algos,
        "allAlgos": all_algos,
        "heldFindings": held_findings,
        "matrix": matrix,
        "overlapPairs": overlap_pairs
    }


def normalize_category_for_catalog(algo):
    """
    Normalizes algorithm category into one of the 4 requested families:
    Credit Spread, Short Straddle, Short Strangle, Option Buying.
    """
    cat = (algo.get("displayCategory") or algo.get("category") or "").strip()
    name = (algo.get("name") or "").strip()
    c_lower = cat.lower()
    n_lower = name.lower()

    if "credit spread" in c_lower or "credit spread" in n_lower:
        return "Credit Spread"
    if "straddle" in c_lower or "straddle" in n_lower:
        return "Short Straddle"
    if "strangle" in c_lower or "strangle" in n_lower:
        return "Short Strangle"
    if "option buying" in c_lower or "option buying" in n_lower:
        return "Option Buying"
    return None


def get_dropdown_catalog(session_cookie=None):
    """
    Returns all active algorithms in Stratzy matching:
    Credit Spread, Short Straddle, Short Strangle, Option Buying.
    Includes user held algorithms and tags them.
    """
    import stratzy_reconciler
    held_invested = stratzy_reconciler.fetch_user_invested_algos(session_cookie)
    held_ids = {h["id"] for h in held_invested}

    # Load from algo_list.json
    algo_file = os.path.join(os.path.dirname(__file__), "algo_list.json")
    raw_algos = []
    if os.path.exists(algo_file):
        try:
            with open(algo_file, "r") as f:
                d = json.load(f)
                raw_algos = d.get("data", []) if isinstance(d, dict) else d
        except Exception:
            pass

    if not raw_algos:
        headers = {
            "accept": "*/*",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "referer": "https://stratzy.in"
        }
        if session_cookie:
            headers["cookie"] = session_cookie
        try:
            r = requests.get("https://stratzy.in/api/web/algo/list", headers=headers, timeout=10)
            if r.status_code == 200:
                raw_algos = r.json().get("data", [])
        except Exception:
            pass

    catalog = []
    seen_ids = set()

    for a in raw_algos:
        aid = a.get("_id") or a.get("id")
        if not aid or aid in seen_ids:
            continue
        if not a.get("isActive", True) or a.get("inTesting", False):
            continue

        norm_cat = normalize_category_for_catalog(a)
        is_held = aid in held_ids

        # If user holds it, always include even if Stratzy categorizes under 'Index Strategies'
        if not norm_cat and is_held:
            norm_cat = "Credit Spread"

        if norm_cat:
            seen_ids.add(aid)
            catalog.append({
                "id": aid,
                "name": a.get("name", "Unknown Strategy"),
                "category": norm_cat,
                "originalCategory": a.get("displayCategory") or a.get("category", ""),
                "isHeld": is_held,
                "risk": a.get("risk", "Medium"),
                "minimumCapital": a.get("minimumCapital", 0)
            })

    # Sort catalog: Held algos first, then Category order, then Alphabetical Name
    cat_order = {"Credit Spread": 1, "Short Straddle": 2, "Short Strangle": 3, "Option Buying": 4}
    catalog.sort(key=lambda x: (not x["isHeld"], cat_order.get(x["category"], 99), x["name"]))
    return catalog


def analyze_3_strategy_overlap(algo_a_id, algo_b_id, algo_c_id, timeframe="1M", session_cookie=None):
    """
    Computes exact trade overlap between 3 selected algorithms for the given timeframe.
    All calculations are performed dynamically at runtime using live Stratzy advice signals.
    """
    cutoff = get_timeframe_cutoff(timeframe)

    # 1. Fetch catalog to get strategy details
    catalog = get_dropdown_catalog(session_cookie)
    cat_map = {c["id"]: c for c in catalog}

    meta_a = dict(cat_map.get(algo_a_id, {"id": algo_a_id, "name": "Strategy A", "category": "Strategy"}))
    meta_b = dict(cat_map.get(algo_b_id, {"id": algo_b_id, "name": "Strategy B", "category": "Strategy"}))
    meta_c = dict(cat_map.get(algo_c_id, {"id": algo_c_id, "name": "Strategy C", "category": "Strategy"}))

    # 2. Extract trades at runtime from official Stratzy advice signals
    trades_a = extract_trades_for_algo(algo_a_id, cutoff, session_cookie=session_cookie)
    trades_b = extract_trades_for_algo(algo_b_id, cutoff, session_cookie=session_cookie)
    trades_c = extract_trades_for_algo(algo_c_id, cutoff, session_cookie=session_cookie)

    meta_a["totalTrades"] = len(trades_a)
    meta_b["totalTrades"] = len(trades_b)
    meta_c["totalTrades"] = len(trades_c)

    days_a = {t["date"] for t in trades_a}
    days_b = {t["date"] for t in trades_b}
    days_c = {t["date"] for t in trades_c}

    # 3. Pairwise overlaps
    st_ab = compute_overlap_between_pair(trades_a, trades_b) if algo_a_id != algo_b_id else {
        "overlappingTrades": len(trades_a), "sameDayOverlap": len(days_a), "totalActiveDays": len(days_a),
        "totalTradesA": len(trades_a), "totalTradesB": len(trades_a), "overlapPctA": 100.0, "overlapPctB": 100.0,
        "level": "SELF", "riskLabel": "Identical Strategy"
    }

    st_ac = compute_overlap_between_pair(trades_a, trades_c) if algo_a_id != algo_c_id else {
        "overlappingTrades": len(trades_a), "sameDayOverlap": len(days_a), "totalActiveDays": len(days_a),
        "totalTradesA": len(trades_a), "totalTradesB": len(trades_a), "overlapPctA": 100.0, "overlapPctB": 100.0,
        "level": "SELF", "riskLabel": "Identical Strategy"
    }

    st_bc = compute_overlap_between_pair(trades_b, trades_c) if algo_b_id != algo_c_id else {
        "overlappingTrades": len(trades_b), "sameDayOverlap": len(days_b), "totalActiveDays": len(days_b),
        "totalTradesA": len(trades_b), "totalTradesB": len(trades_b), "overlapPctA": 100.0, "overlapPctB": 100.0,
        "level": "SELF", "riskLabel": "Identical Strategy"
    }

    # 4. Simultaneous 3-way overlap
    set_a = {(t["date"], t["symbol"]) for t in trades_a}
    set_b = {(t["date"], t["symbol"]) for t in trades_b}
    set_c = {(t["date"], t["symbol"]) for t in trades_c}
    common_3way = set_a & set_b & set_c
    common_days_3way = len(days_a & days_b & days_c)

    # 5. Build 3x3 Matrix
    matrix = {
        algo_a_id: {
            algo_a_id: {"overlappingTrades": len(trades_a), "level": "SELF", "riskLabel": "Identical Strategy", "sameDayOverlap": len(days_a)},
            algo_b_id: st_ab,
            algo_c_id: st_ac,
        },
        algo_b_id: {
            algo_a_id: st_ab,
            algo_b_id: {"overlappingTrades": len(trades_b), "level": "SELF", "riskLabel": "Identical Strategy", "sameDayOverlap": len(days_b)},
            algo_c_id: st_bc,
        },
        algo_c_id: {
            algo_a_id: st_ac,
            algo_b_id: st_bc,
            algo_c_id: {"overlappingTrades": len(trades_c), "level": "SELF", "riskLabel": "Identical Strategy", "sameDayOverlap": len(days_c)},
        }
    }

    return {
        "success": True,
        "timeframe": timeframe,
        "cutoffDate": cutoff.strftime("%Y-%m-%d"),
        "strategies": [meta_a, meta_b, meta_c],
        "strategyA": meta_a,
        "strategyB": meta_b,
        "strategyC": meta_c,
        "matrix": matrix,
        "pairAB": st_ab,
        "pairAC": st_ac,
        "pairBC": st_bc,
        "threeWayOverlap": {
            "overlappingTrades": len(common_3way),
            "sameDayOverlap": common_days_3way,
            "contracts": [f"{d}: {s}" for d, s in sorted(common_3way)]
        }
    }

