#!/usr/bin/env python3
"""
allAlgoDataDump/fetch_all_algos.py
═══════════════════════════════════════════════════════════════════════════════
Utility to fetch comprehensive master data and deep quant metrics for all active
Stratzy Options Algorithms (Credit Spread, Short Straddle, Short Strangle, Option Buying).

Usage:
  python3 allAlgoDataDump/fetch_all_algos.py
  python3 allAlgoDataDump/fetch_all_algos.py --all   # (Fetches all 403 algos including inactive/cash)

Outputs created in allAlgoDataDump/:
  1. stratzy_101_algos_dump.json    -> Complete raw dump with nested endpoint details
  2. stratzy_101_algos_summary.json -> Condensed summary for easy LLM prompt injection
  3. stratzy_101_algos_table.csv    -> Tabular CSV for spreadsheet or tabular LLM analysis
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import csv
import time
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

COOKIE_FILE = os.path.join(PROJECT_ROOT, ".session_cookie")
OUTPUT_DUMP_FILE = os.path.join(BASE_DIR, "stratzy_101_algos_dump.json")
OUTPUT_SUMMARY_FILE = os.path.join(BASE_DIR, "stratzy_101_algos_summary.json")
OUTPUT_CSV_FILE = os.path.join(BASE_DIR, "stratzy_101_algos_table.csv")

MASTER_FIELDS = [
    "_id", "name", "category", "displayCategory", "risk",
    "minimumCapital", "maximumCapital",
    "oneMonthPnl", "threeMonthPnl", "sixMonthPnl", "oneYearPnl",
    "winRatio", "avgFrequency", "algoScore", "deployCount",
    "liveSince", "backTestingPeriod", "isActive", "inTesting",
    "slotsLeft", "lastTradedOn"
]

EXCLUDED_CATEGORIES = {
    'investing', 'swing', 'intraday cash', 'index strategies',
    'futures buying', 'ratio spread', 'iron condor', 'batman spread'
}


def get_headers():
    headers = {
        "accept": "*/*",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "referer": "https://stratzy.in"
    }
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r") as f:
                cookie = f.read().strip()
                if cookie:
                    headers["cookie"] = cookie
        except Exception:
            pass
    return headers


def safe_get_json(url, headers, timeout=8):
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200:
            js = r.json()
            return js.get("data")
    except Exception:
        pass
    return None


def fetch_algo_full_data(algo_record, headers):
    aid = algo_record.get("_id")
    name = algo_record.get("name", "Unknown")

    # 1. Master Record extraction
    master = {k: algo_record.get(k) for k in MASTER_FIELDS}

    # 2. Fetch all child endpoints
    # - quantStats (metrics, drawdown curves, monthly heatmap)
    # - metrics-v2 (1M, 3M, 6M, 1Y, Max)
    # - characteristics (tags, strategy characteristics)
    # - correlation (matrix against benchmarks and assets)
    # - performanceSummary (high-level performance numbers)
    quant_stats = safe_get_json(f"https://stratzy.in/api/web/algo/quantStats?advisorId={aid}", headers)
    metrics_v2 = safe_get_json(f"https://stratzy.in/api/web/v2/algo/metrics?advisorId={aid}", headers)
    characteristics = safe_get_json(f"https://stratzy.in/api/web/algo/characteristics?algoId={aid}", headers)
    correlation = safe_get_json(f"https://stratzy.in/api/web/algo/correlation?advisorId={aid}", headers)
    perf_summary = safe_get_json(f"https://stratzy.in/api/web/algo/performanceSummary?algoId={aid}", headers)

    # 3. Extract historical monthly PnL breakdown from quantStats.plotMonthlyHeatmap
    historical_pnl_monthly = None
    if isinstance(quant_stats, dict) and "plotMonthlyHeatmap" in quant_stats:
        historical_pnl_monthly = quant_stats.get("plotMonthlyHeatmap")

    # 4. Normalized Quant Metrics flat dict
    flat_metrics = {}
    if isinstance(quant_stats, dict) and "metrics" in quant_stats:
        for item in quant_stats.get("metrics", []):
            if isinstance(item, dict):
                for k, v in item.items():
                    flat_metrics[k] = v[0] if isinstance(v, list) and len(v) > 0 else v

    return {
        "master": master,
        "normalizedMetrics": flat_metrics,
        "historicalPnlBreakdown": historical_pnl_monthly,
        "endpoints": {
            "quantStats": quant_stats,
            "metricsV2": metrics_v2,
            "characteristics": characteristics,
            "correlation": correlation,
            "performanceSummary": perf_summary
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Stratzy Algos Data Dump Utility")
    parser.add_argument("--all", action="store_true", help="Dump all 403 algos (including inactive/cash/investing)")
    args = parser.parse_args()

    headers = get_headers()
    print("=" * 75)
    print("  Stratzy Algorithm Data Dump Utility")
    print("=" * 75)
    print("Fetching master catalog from https://stratzy.in/api/web/algo/list ...")

    try:
        r = requests.get("https://stratzy.in/api/web/algo/list", headers=headers, timeout=12)
        if r.status_code != 200:
            print(f"Error fetching catalog: HTTP {r.status_code}")
            sys.exit(1)
        raw_algos = r.json().get("data", [])
    except Exception as e:
        print(f"Failed to connect to Stratzy API: {e}")
        sys.exit(1)

    print(f"Found {len(raw_algos)} total strategies on Stratzy.")

    if args.all:
        target_algos = raw_algos
        print(f"Targeting ALL {len(target_algos)} strategies (--all specified).")
    else:
        # Filter for active options trading algos (Credit Spread, Short Straddle, Short Strangle, Option Buying)
        target_algos = [
            a for a in raw_algos
            if a.get("isActive", True)
            and not a.get("inTesting", False)
            and (a.get("displayCategory") or a.get("category", "")).strip().lower() not in EXCLUDED_CATEGORIES
        ]
        print(f"Filtered for {len(target_algos)} active Options strategies (Credit Spread, Straddle, Strangle, Buying).")

    print(f"\nFetching endpoints (quantStats, metrics-v2, characteristics, correlation, performanceSummary)...")
    start_time = time.time()

    full_dump = []
    completed = 0
    total = len(target_algos)

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_algo = {
            executor.submit(fetch_algo_full_data, a, headers): a
            for a in target_algos
        }
        for future in as_completed(future_to_algo):
            algo_res = future.result()
            full_dump.append(algo_res)
            completed += 1
            if completed % 10 == 0 or completed == total:
                print(f"  [{completed}/{total}] Fetched {algo_res['master']['name']} ({algo_res['master'].get('displayCategory') or algo_res['master'].get('category')})")

    elapsed = round(time.time() - start_time, 1)
    print(f"\nCompleted fetching all {len(full_dump)} strategies in {elapsed}s.")

    # Sort stably by master name
    full_dump.sort(key=lambda x: (x["master"].get("displayCategory") or "", x["master"].get("name") or ""))

    # 1. Save Complete JSON Dump
    dump_payload = {
        "metadata": {
            "title": "Stratzy Active Options Algorithms Complete Dump",
            "extractedAt": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "totalCount": len(full_dump),
            "categories": list(set((x["master"].get("displayCategory") or x["master"].get("category", "")).strip() for x in full_dump)),
            "endpointsExtracted": ["quantStats", "metricsV2", "characteristics", "correlation", "performanceSummary", "historicalPnlBreakdown"]
        },
        "algorithms": full_dump
    }

    with open(OUTPUT_DUMP_FILE, "w", encoding="utf-8") as f:
        json.dump(dump_payload, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved full dump: {OUTPUT_DUMP_FILE} ({round(os.path.getsize(OUTPUT_DUMP_FILE)/1024, 1)} KB)")

    # 2. Save Condensed Summary JSON (ideal for LLM prompt context window limits)
    summary_list = []
    for item in full_dump:
        m = item["master"]
        nm = item["normalizedMetrics"]
        mv2 = item["endpoints"].get("metricsV2") or {}
        m3 = mv2.get("3M", {})
        m6 = mv2.get("6M", {})
        m1y = mv2.get("1Y", {})

        summary_list.append({
            "_id": m["_id"],
            "name": m["name"],
            "category": m.get("displayCategory") or m.get("category"),
            "risk": m.get("risk"),
            "minCapital": m.get("minimumCapital"),
            "maxCapital": m.get("maximumCapital"),
            "sharpeRatio": nm.get("Sharpe Ratio"),
            "sortino": nm.get("Sortino"),
            "calmar": nm.get("Calmar"),
            "maxDrawdown": nm.get("Max Drawdown"),
            "volatilityAnn": nm.get("Volatility (ann.)"),
            "winMonthPct": nm.get("Win Month %"),
            "winQuarterPct": nm.get("Win Quarter %"),
            "trades3M": m3.get("totalTrades"),
            "pnl1M": m.get("oneMonthPnl"),
            "pnl3M": m.get("threeMonthPnl") or m3.get("booksizeReturn"),
            "pnl6M": m.get("sixMonthPnl") or m6.get("booksizeReturn"),
            "pnl1Y": m.get("oneYearPnl") or m1y.get("booksizeReturn"),
            "winRatio": m.get("winRatio"),
            "avgFrequency": m.get("avgFrequency"),
            "algoScore": m.get("algoScore"),
            "liveSince": m.get("liveSince"),
            "monthlyPnlHeatmap": item.get("historicalPnlBreakdown")
        })

    with open(OUTPUT_SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": dump_payload["metadata"],
            "summary": summary_list
        }, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved summary JSON: {OUTPUT_SUMMARY_FILE} ({round(os.path.getsize(OUTPUT_SUMMARY_FILE)/1024, 1)} KB)")

    # 3. Save Tabular CSV
    csv_headers = [
        "_id", "name", "category", "risk", "minCapital",
        "sharpeRatio", "sortino", "calmar", "maxDrawdown", "volatilityAnn",
        "winMonthPct", "winQuarterPct", "trades3M", "pnl1M", "pnl3M", "pnl6M", "pnl1Y",
        "winRatio", "avgFrequency", "algoScore", "liveSince"
    ]
    with open(OUTPUT_CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers, extrasaction="ignore")
        writer.writeheader()
        for row in summary_list:
            writer.writerow(row)
    print(f"✓ Saved CSV table: {OUTPUT_CSV_FILE} ({round(os.path.getsize(OUTPUT_CSV_FILE)/1024, 1)} KB)")

    print("\n" + "=" * 75)
    print("  Data dump finished successfully! All files are in allAlgoDataDump/")
    print("=" * 75)


if __name__ == "__main__":
    main()
