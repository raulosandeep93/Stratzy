#!/usr/bin/env python3
"""
Stratzy Algo Scanner - Backend API
Fetches and aggregates data from Stratzy's API for all algo strategies.
"""

import os
import json
import time
import threading
import requests
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import dhan_engine

app = Flask(__name__, static_folder='frontend', static_url_path='')
CORS(app)

BASE_URL = "https://stratzy.in"

# Default categories to scan when none are specified
DEFAULT_CATEGORIES = ['Option Buying', 'Credit Spread', 'Short Strangle', 'Short Straddle']

# Categories to always exclude
EXCLUDED_CATEGORIES = {'Investing', 'Swing', 'Intraday Cash', 'Index Strategies',
                        'futures buying', 'Ratio Spread', 'Iron Condor', 'Batman Spread'}
EXCLUDED_CATEGORIES_LOWER = {c.strip().lower() for c in EXCLUDED_CATEGORIES}

SESSION_COOKIE_FILE = os.path.join(os.path.dirname(__file__), ".session_cookie")

store = {
    "session_cookie": None,
    "algos": [],
    "scan_results": [],
    "last_scan": None,
    "scan_status": "idle",
    "scan_progress": 0,
    "scan_total": 0,
    "scan_log": [],
    "dhan": {
        "clientId": None,
        "accessToken": None,
        "connected": False,
        "profile": None,
    },
    "dhan_trades": [],
    "dhan_analytics": None,
}

# Auto-restore session cookie from disk if present
if os.path.exists(SESSION_COOKIE_FILE):
    try:
        with open(SESSION_COOKIE_FILE, "r") as f:
            _sc = f.read().strip()
            if _sc:
                store["session_cookie"] = _sc
    except Exception:
        pass

def get_headers():
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "referer": "https://stratzy.in/algo-trading-strategies?filterBy=all",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
    }
    if store["session_cookie"]:
        headers["cookie"] = store["session_cookie"]
    return headers


@app.route("/api/login", methods=["POST"])
def login():
    body = request.get_json()
    cookie = body.get("cookie", "").strip()
    if not cookie:
        return jsonify({"success": False, "message": "Cookie is required"}), 400
    try:
        resp = requests.get(
            f"{BASE_URL}/api/mobile/profile",
            headers={**get_headers(), "cookie": cookie},
            timeout=10,
        )
        if resp.status_code in [200, 304]:
            data = resp.json()
            if data.get("success"):
                store["session_cookie"] = cookie
                try:
                    with open(SESSION_COOKIE_FILE, "w") as f:
                        f.write(cookie)
                except Exception:
                    pass
                name = data.get("data", {}).get("name") or data.get("data", {}).get("email") or "User"
                return jsonify({"success": True, "name": name})
        return jsonify({"success": False, "message": "Invalid session. Please paste a fresh cookie."}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/logout", methods=["POST"])
def logout():
    store["session_cookie"] = None
    store["algos"] = []
    store["scan_results"] = []
    store["scan_status"] = "idle"
    if os.path.exists(SESSION_COOKIE_FILE):
        try:
            os.remove(SESSION_COOKIE_FILE)
        except Exception:
            pass
    return jsonify({"success": True})


@app.route("/api/auth/status", methods=["GET"])
def auth_status():
    if store["session_cookie"]:
        return jsonify({"authenticated": True})
    return jsonify({"authenticated": False})


@app.route("/api/algos", methods=["GET"])
def get_algos():
    if not store["session_cookie"]:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    try:
        resp = requests.get(f"{BASE_URL}/api/web/algo/list", headers=get_headers(), timeout=15)
        data = resp.json()
        if data.get("success"):
            algos = data.get("data", [])
            active = [
                a for a in algos
                if a.get("isActive", True)
                and not a.get("inTesting", False)
                and (a.get("displayCategory") or a.get("category", "")).strip().lower() not in EXCLUDED_CATEGORIES_LOWER
            ]
            store["algos"] = active
            return jsonify({"success": True, "count": len(active), "algos": active})
        return jsonify({"success": False, "message": "Failed to fetch algos"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


def fetch_algo_detail(algo_id, algo_name):
    result = {"algoId": algo_id, "name": algo_name}
    headers = get_headers()

    try:
        r = requests.get(f"{BASE_URL}/api/web/algo/performanceSummary?algoId={algo_id}", headers=headers, timeout=12)
        if r.status_code in [200, 304]:
            ps = r.json().get("data", {})
            metrics_map = {m["label"]: m["value"] for m in ps.get("metrics", [])}
            result["performanceSummary"] = metrics_map
        time.sleep(0.15)

        r = requests.get(f"{BASE_URL}/api/web/v2/algo/metrics?advisorId={algo_id}", headers=headers, timeout=12)
        if r.status_code in [200, 304]:
            md = r.json().get("data", {})
            result["metrics"] = {
                period: {k: v for k, v in period_data.items() if k != "booksizes"}
                for period, period_data in md.items()
            }
            for period, period_data in md.items():
                booksizes = period_data.get("booksizes", {})
                if booksizes:
                    vals = list(booksizes.values())
                    if len(vals) >= 2:
                        change = ((vals[-1] - vals[0]) / vals[0]) * 100
                        result["metrics"][period]["booksizeReturn"] = round(change, 2)
        time.sleep(0.15)

        r = requests.get(f"{BASE_URL}/api/web/algo/quantStats?advisorId={algo_id}", headers=headers, timeout=12)
        if r.status_code in [200, 304]:
            qs = r.json().get("data", {})
            quant_map = {}
            for m in qs.get("metrics", []):
                for k, v in m.items():
                    quant_map[k] = v[0] if isinstance(v, list) and v else v
            result["quantStats"] = quant_map
            result["benchmarkName"] = qs.get("benchmarkName", "NIFTY 50")
        time.sleep(0.15)

    except Exception as e:
        result["error"] = str(e)

    return result


def run_scan(algo_ids, algo_map):
    store["scan_status"] = "running"
    store["scan_results"] = []
    store["scan_progress"] = 0
    store["scan_total"] = len(algo_ids)
    store["scan_log"] = []
    store["last_scan"] = datetime.now().isoformat()

    results = []
    for i, algo_id in enumerate(algo_ids):
        if store["scan_status"] == "cancelled":
            break
        algo_name = algo_map.get(algo_id, {}).get("name", algo_id)
        store["scan_log"].append(f"Scanning [{i+1}/{len(algo_ids)}]: {algo_name}")
        base_info = algo_map.get(algo_id, {})
        detail = fetch_algo_detail(algo_id, algo_name)
        merged = {**base_info, **detail}
        try:
            import algo_selector
            ev = algo_selector.evaluate_algo_25_parameters(
                merged,
                detail.get("quantStats", {}),
                detail.get("metrics", {})
            )
            merged["institutionalScore"] = ev.get("institutionalScore", 0)
            merged["checklist"] = ev.get("checklist", [])
            merged["passCount"] = ev.get("passCount", 0)
            merged["cautionCount"] = ev.get("cautionCount", 0)
            merged["failCount"] = ev.get("failCount", 0)
            merged["criticalFailed"] = ev.get("criticalFailed", False)
            merged["algoScore"] = ev.get("institutionalScore", 0)
        except Exception as e:
            pass
        results.append(merged)
        store["scan_progress"] = i + 1
        store["scan_results"] = results

    store["scan_status"] = "done"
    store["scan_log"].append(f"Scan complete. {len(results)} algos scanned.")


@app.route("/api/scan/start", methods=["POST"])
def start_scan():
    if not store["session_cookie"]:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    if store["scan_status"] == "running":
        return jsonify({"success": False, "message": "Scan already in progress"}), 409

    body = request.get_json() or {}
    categories = body.get("categories", [])
    # If no filter specified, fall back to the default preferred categories
    if not categories:
        categories = DEFAULT_CATEGORIES

    algos = store.get("algos", [])
    if not algos:
        try:
            resp = requests.get(f"{BASE_URL}/api/web/algo/list", headers=get_headers(), timeout=15)
            data = resp.json()
            if data.get("success"):
                algos = [
                    a for a in data["data"]
                    if a.get("isActive", True)
                    and not a.get("inTesting", False)
                    and (a.get("displayCategory") or a.get("category", "")).strip().lower() not in EXCLUDED_CATEGORIES_LOWER
                ]
                store["algos"] = algos
        except Exception as e:
            return jsonify({"success": False, "message": f"Failed to fetch algo list: {e}"}), 500

    cat_set = {c.strip().lower() for c in categories}
    filtered = [
        a for a in algos
        if (a.get("displayCategory") or a.get("category", "")).strip().lower() in cat_set
    ]

    algo_ids = [a.get("_id") or a.get("algoId") for a in filtered if (a.get("_id") or a.get("algoId"))]
    algo_map = {(a.get("_id") or a.get("algoId")): a for a in filtered if (a.get("_id") or a.get("algoId"))}

    if not algo_ids:
        return jsonify({"success": False, "message": "No matching algos found for selected categories"}), 400

    t = threading.Thread(target=run_scan, args=(algo_ids, algo_map), daemon=True)
    t.start()

    return jsonify({"success": True, "message": f"Scan started for {len(algo_ids)} algos", "total": len(algo_ids)})


@app.route("/api/scan/cancel", methods=["POST"])
def cancel_scan():
    store["scan_status"] = "cancelled"
    return jsonify({"success": True})


@app.route("/api/scan/status", methods=["GET"])
def scan_status():
    return jsonify({
        "status": store["scan_status"],
        "progress": store["scan_progress"],
        "total": store["scan_total"],
        "lastScan": store["last_scan"],
        "log": store["scan_log"][-10:],
    })


@app.route("/api/scan/results", methods=["GET"])
def scan_results():
    return jsonify({
        "success": True,
        "count": len(store["scan_results"]),
        "results": store["scan_results"],
        "lastScan": store["last_scan"],
    })


@app.route("/api/categories", methods=["GET"])
def get_categories():
    algos = store.get("algos", [])
    cats = {}
    for a in algos:
        cat = a.get("displayCategory") or a.get("category") or "Unknown"
        cats[cat] = cats.get(cat, 0) + 1
    return jsonify({"categories": cats})


@app.route("/api/algo/overlap", methods=["GET", "POST"])
def algo_overlap():
    """
    Computes trade overlap between 3 selected algos or portfolio algos
    purely based on official Stratzy signals and past advices at runtime.
    """
    import overlap_analyzer
    import importlib
    importlib.reload(overlap_analyzer)

    timeframe = request.args.get("timeframe")
    algo_a = request.args.get("algoA") or request.args.get("a")
    algo_b = request.args.get("algoB") or request.args.get("b")
    algo_c = request.args.get("algoC") or request.args.get("c")

    candidate_suggested = None
    if request.is_json:
        body = request.get_json() or {}
        timeframe = timeframe or body.get("timeframe")
        algo_a = algo_a or body.get("algoA") or body.get("a")
        algo_b = algo_b or body.get("algoB") or body.get("b")
        algo_c = algo_c or body.get("algoC") or body.get("c")
        candidate_suggested = body.get("suggestedAlgos")

    if not timeframe:
        timeframe = "1M"

    cookie = store.get("session_cookie")
    if not candidate_suggested and store.get("scan_results"):
        candidate_suggested = store["scan_results"]

    try:
        if algo_a and algo_b and algo_c:
            data = overlap_analyzer.analyze_3_strategy_overlap(
                algo_a, algo_b, algo_c,
                timeframe=timeframe,
                session_cookie=cookie
            )
            return jsonify(data)
        else:
            data = overlap_analyzer.analyze_portfolio_overlap(
                timeframe=timeframe,
                session_cookie=cookie,
                candidate_suggested=candidate_suggested
            )
            return jsonify(data)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/algo/catalog-options", methods=["GET"])
def get_algo_catalog_options():
    """
    Returns all active algorithms matching Credit Spread, Short Straddle,
    Short Strangle, and Option Buying categories for dropdown selection.
    """
    import overlap_analyzer
    import importlib
    importlib.reload(overlap_analyzer)
    cookie = store.get("session_cookie")
    try:
        catalog = overlap_analyzer.get_dropdown_catalog(session_cookie=cookie)
        return jsonify({"success": True, "data": catalog})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/algo/top-picks", methods=["GET"])
def algo_top_picks():
    """
    Returns the top 5 suggested algorithms evaluated against the institutional
    25-parameter due diligence checklist.
    """
    import algo_selector
    import importlib
    importlib.reload(algo_selector)

    force = request.args.get("refresh", "").lower() in ["true", "1"]
    cookie = store.get("session_cookie")
    try:
        data = algo_selector.select_top_5_institutional_algos(session_cookie=cookie, force_refresh=force)
        return jsonify(data)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/algo/<algo_id>", methods=["GET"])
def get_algo_detail(algo_id):
    if not store["session_cookie"]:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    detail = fetch_algo_detail(algo_id, algo_id)
    return jsonify({"success": True, "data": detail})


# ══════════════════════════════════════════════════════════════════════════════
# DHAN INTEGRATION & AUDIT ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/dhan/connect", methods=["POST"])
def dhan_connect():
    body = request.get_json() or {}
    client_id = body.get("clientId", "").strip() or store["dhan"].get("clientId", "")
    access_token = body.get("accessToken", "").strip() or store["dhan"].get("accessToken", "")
    from_date = body.get("fromDate", "").strip() or None
    to_date = body.get("toDate", "").strip() or None

    if not client_id or not access_token:
        return jsonify({"success": False, "message": "Client ID and Access Token are required"}), 400

    result = dhan_engine.fetch_dhan_api_data(client_id, access_token, from_date=from_date, to_date=to_date, session_cookie=store.get("session_cookie"))
    if result.get("success"):
        store["dhan"]["clientId"] = client_id
        store["dhan"]["accessToken"] = access_token
        store["dhan"]["connected"] = True
        store["dhan_analytics"] = result.get("analytics")
        store["dhan_trades"] = result.get("analytics", {}).get("trades", [])
        return jsonify({
            "success": True,
            "message": "Connected to DhanHQ successfully",
            "fundLimit": result.get("fundLimit"),
            "analytics": result.get("analytics"),
            "fromDate": result.get("fromDate"),
            "toDate": result.get("toDate"),
            "rawTradesCount": result.get("rawTradesCount", 0)
        })
    else:
        return jsonify({"success": False, "message": result.get("message", "Failed to connect to Dhan")}), 401


@app.route("/api/dhan/parse-csv", methods=["POST"])
def dhan_parse_csv():
    # Check if multipart file was sent
    if 'file' in request.files:
        f = request.files['file']
        file_bytes = f.read()
        filename = f.filename or ""
        if not file_bytes:
            return jsonify({"success": False, "message": "Uploaded file is empty"}), 400
        try:
            analytics = dhan_engine.parse_dhan_file(file_bytes, filename=filename, session_cookie=store.get("session_cookie"))
            store["dhan_analytics"] = analytics
            store["dhan_trades"] = analytics.get("trades", [])
            return jsonify({
                "success": True,
                "message": f"Successfully parsed {analytics.get('totalTrades', 0)} closed trades from {filename}",
                "analytics": analytics
            })
        except Exception as e:
            return jsonify({"success": False, "message": f"Failed to parse file: {str(e)}"}), 500
    else:
        body = request.get_json() or {}
        csv_text = body.get("csvText", "")
        if not csv_text or not csv_text.strip():
            return jsonify({"success": False, "message": "No CSV or Excel content provided"}), 400
        try:
            analytics = dhan_engine.parse_dhan_file(csv_text, filename="upload.csv", session_cookie=store.get("session_cookie"))
            store["dhan_analytics"] = analytics
            store["dhan_trades"] = analytics.get("trades", [])
            return jsonify({
                "success": True,
                "message": f"Successfully parsed {analytics.get('totalTrades', 0)} closed trades",
                "analytics": analytics
            })
        except Exception as e:
            return jsonify({"success": False, "message": f"Failed to parse CSV: {str(e)}"}), 500


@app.route("/api/stratzy/invested-algos", methods=["GET"])
def get_stratzy_invested_algos():
    """Returns the user's active/invested algos directly from Stratzy."""
    try:
        import stratzy_reconciler
        import importlib
        importlib.reload(stratzy_reconciler)
        cookie = store.get("session_cookie")
        algos = stratzy_reconciler.fetch_user_invested_algos(session_cookie=cookie)
        return jsonify({"success": True, "algos": algos})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/dhan/reconcile", methods=["POST"])
def dhan_reconcile():
    """Reconciles loaded Dhan trades with Stratzy published signals."""
    trades = store.get("dhan_trades", [])
    if not trades:
        return jsonify({"success": False, "message": "No Dhan trades loaded to reconcile"}), 400
    try:
        import importlib
        import stratzy_reconciler
        import dhan_engine
        importlib.reload(stratzy_reconciler)
        importlib.reload(dhan_engine)

        cookie = store.get("session_cookie")
        matched_trades, stats = stratzy_reconciler.reconcile_trades(trades, session_cookie=cookie)
        analytics = dhan_engine.compute_dhan_analytics(matched_trades, session_cookie=cookie)
        store["dhan_analytics"] = analytics
        store["dhan_trades"] = analytics.get("trades", [])
        return jsonify({
            "success": True,
            "message": f"Successfully matched {stats.get('matched', 0)} of {stats.get('total', 0)} trades ({stats.get('matchPct', 0)}%) with your Stratzy invested Algos",
            "stats": stats,
            "analytics": analytics
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500



@app.route("/api/dhan/demo-trades", methods=["GET"])
def dhan_demo_trades():
    demo = dhan_engine.generate_demo_trades()
    store["dhan_analytics"] = demo
    store["dhan_trades"] = demo.get("trades", [])
    return jsonify({
        "success": True,
        "message": "Loaded 1-month demo trades across 3 Stratzy algos",
        "analytics": demo
    })


@app.route("/api/dhan/analytics", methods=["GET"])
def dhan_get_analytics():
    return jsonify({
        "success": True,
        "connected": store["dhan"]["connected"],
        "clientId": store["dhan"]["clientId"],
        "analytics": store["dhan_analytics"]
    })


@app.route("/api/dhan/clear", methods=["POST"])
def dhan_clear():
    store["dhan"]["connected"] = False
    store["dhan_analytics"] = None
    store["dhan_trades"] = []
    return jsonify({"success": True})


@app.route("/api/dhan/debug", methods=["GET"])
def dhan_debug():
    """Raw debug endpoint - shows what Dhan API actually returns."""
    client_id = store["dhan"].get("clientId") or request.args.get("clientId", "")
    access_token = store["dhan"].get("accessToken") or request.args.get("accessToken", "")
    if not client_id or not access_token:
        return jsonify({"error": "Not connected. Connect first via /api/dhan/connect"}), 400

    headers = {
        "access-token": access_token.strip(),
        "client-id": client_id.strip(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    from datetime import timedelta
    import traceback

    result = {}

    # Today's trade book
    try:
        r = requests.get("https://api.dhan.co/v2/trades", headers=headers, timeout=10)
        result["today_tradebook"] = {
            "status": r.status_code,
            "data": r.json()
        }
    except Exception as e:
        result["today_tradebook"] = {"error": str(e)}

    # Trade history last 30 days page 0
    try:
        to_d = datetime.now().strftime("%Y-%m-%d")
        fr_d = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        r = requests.get(f"https://api.dhan.co/v2/trades/{fr_d}/{to_d}/0", headers=headers, timeout=15)
        result["trade_history_30d"] = {
            "status": r.status_code,
            "url": f"https://api.dhan.co/v2/trades/{fr_d}/{to_d}/0",
            "data": r.json()
        }
    except Exception as e:
        result["trade_history_30d"] = {"error": str(e)}

    # Positions
    try:
        r = requests.get("https://api.dhan.co/v2/positions", headers=headers, timeout=10)
        result["positions"] = {
            "status": r.status_code,
            "data": r.json()
        }
    except Exception as e:
        result["positions"] = {"error": str(e)}

    # Orders
    try:
        r = requests.get("https://api.dhan.co/v2/orders", headers=headers, timeout=10)
        result["orders"] = {
            "status": r.status_code,
            "count": len(r.json().get("data", [])) if r.status_code == 200 else 0,
            "sample": r.json().get("data", [])[:2]
        }
    except Exception as e:
        result["orders"] = {"error": str(e)}

    return jsonify(result)




@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("frontend", path)


if __name__ == "__main__":
    print("Stratzy Algo Scanner running at http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=False)
