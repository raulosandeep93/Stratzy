# Project Context — Stratzy Algo Scanner & Strategy Intelligence Dashboard

## 1. Project Overview

- **Name**: Stratzy Algo Scanner & Dhan Strategy Intelligence Dashboard
- **Purpose**: A local web application to scan, quant-evaluate, and rank 400+ algorithmic options trading strategies from Stratzy using an institutional 25-parameter risk framework, analyze live trade overlap and portfolio correlation across strategies, and audit/reconcile Dhan broker tradebooks against official Stratzy advice signals.
- **Target Users**: Retail options traders and quants deploying capital on Stratzy strategies via Dhan broker accounts.
- **Platform**: Web application running locally on Linux/macOS/Windows, served on `http://localhost:5050`.

---

## 2. Technology Stack

- **Backend Language & Framework**: Python 3, Flask 3.0.3, Flask-CORS 4.0.1
- **HTTP Client**: Requests 2.32.3
- **Data Processing**: Pandas, Openpyxl, Xlrd (for parsing Dhan Excel/CSV tradebooks)
- **Frontend Architecture**: Vanilla HTML5, Vanilla CSS3 (custom dark glassmorphism system), Vanilla JavaScript (ES6+ modular script, single-page app architecture)
- **External APIs**:
  - Stratzy Web & Mobile API (`https://stratzy.in/api/...`)
  - DhanHQ REST API v2 (`https://api.dhan.co/v2/...`)
- **Data Storage**: Local JSON file storage and TTL memory caches (no external database server required)

---

## 3. High-Level Architecture

The application has a lightweight two-tier architecture:

```
[ Browser UI: Vanilla JS/CSS/HTML ]
             │ (HTTP / JSON)
             ▼
[ Flask App: server.py on port 5050 ]
  ├── algo_selector.py     (25-Parameter Due Diligence Engine & Top 5 Picks)
  ├── overlap_analyzer.py  (Past Advice Scraper & Trade Overlap Matrix)
  ├── dhan_engine.py       (Tradebook Parser, FIFO Matcher & Fee Calculator)
  └── stratzy_reconciler.py (Broker Execution vs Signal Attribution ±15m)
             │
  ├── Local Cache Files    (.session_cookie, *.json caches)
  └── Upstream APIs        (Stratzy Web API, DhanHQ v2 API)
```

---

## 4. Important Directories & Files

```text
/
├── server.py                        Flask backend API & static file server (port 5050)
├── algo_selector.py                 25-parameter institutional strategy scoring & ranking engine
├── overlap_analyzer.py              Trade overlap & contract collision engine across algos
├── dhan_engine.py                   Dhan tradebook parsing (CSV/XLSX), FIFO matching, NSE charges
├── stratzy_reconciler.py            Reconciliation of executed broker trades with Stratzy signals
├── start.sh                         One-click startup bash script (kills port 5050, launches app)
├── requirements.txt                 Python dependency manifest
├── ALGO_SELECTION_25_PARAMETERS.md  Specification for the 25-parameter institutional scoring rules
├── frontend/
│   ├── index.html                   Single-page dashboard layout (Scanner, Results, Watchlist, Dhan)
│   ├── app.js                       Frontend logic, API communication, and dynamic rendering
│   └── styles.css                   Complete custom design system, glassmorphic dark theme
└── allAlgoDataDump/                 Standalone data extraction utility
    ├── fetch_all_algos.py           Script to extract all active Stratzy options strategies
    ├── stratzy_101_algos_summary.json Condensed quant master for LLMs / analysis
    └── README.md                    Documentation on data dump schema and usage
```

---

## 5. Important Commands

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start backend server and open browser (recommended)
bash start.sh

# Or start server manually
python3 server.py

# Verify Python syntax across all core modules
python3 -m py_compile server.py algo_selector.py overlap_analyzer.py dhan_engine.py stratzy_reconciler.py

# Run standalone 101 algorithms data fetch utility
python3 allAlgoDataDump/fetch_all_algos.py

# Debug DhanHQ API connection directly
python3 debug_dhan.py <CLIENT_ID> <ACCESS_TOKEN>
```

---

## 6. Important Constraints

1. **₹1,00,000 Capital Cap**: Strategy evaluation strictly caps deployment capital at ₹1,00,000. Strategies requiring > ₹1L minimum capital are instantly disqualified (Rule 16 in `algo_selector.py`).
2. **Stratzy Session Cookie Lifespan**: Upstream Stratzy API calls require an authenticated session cookie (`.session_cookie`). If the cookie expires, upstream requests fail with 401/403.
3. **Timezone Conversion (UTC to IST)**: Stratzy signals and API responses often serialize timestamps in UTC ISO format, while Indian markets and Dhan trades are in IST. `parse_iso_utc_to_ist` standardizes this.
4. **Rate Limiting & Caching**: Upstream Stratzy and Dhan endpoints are subject to rate limiting. Caching (`CACHE_TTL` in `algo_selector.py` and `overlap_analyzer.py`) must be respected to prevent blocking.
5. **No Frontend Build Pipeline**: Frontend has no Babel, Webpack, Vite, or Tailwind. Edits to `frontend/index.html`, `frontend/app.js`, and `frontend/styles.css` are immediately live upon browser refresh.

---

## 7. Current Development Philosophy

- **Zero-Build Overhead**: Keep development friction zero. The Python server directly serves static frontend assets.
- **Deterministic Quant Evaluation**: Quant metrics (Sharpe, Sortino, Calmar, Win-Quarter %, Overlap) are calculated deterministically using clear formulas rather than heuristic approximations.
- **Non-destructive Data Handling**: Trade reconciliations and cache files are non-destructive and fail gracefully when upstream endpoints are unreachable.
