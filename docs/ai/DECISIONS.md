# Architectural Decisions — Stratzy Algo Scanner

## DECISION-001 — Zero-Build Vanilla Frontend Architecture

Date:
2026-10-14

Decision:
Build the frontend entirely with Vanilla HTML5, Vanilla CSS3, and ES6+ JavaScript, served directly by Flask as static files from the `frontend/` directory.

Reason:
Eliminates Node.js/npm dependencies, bundling steps, and build errors for local execution. The entire application runs immediately via `bash start.sh` or `python3 server.py`.

Alternatives considered:
React, Vite, Next.js.

Do not:
Do not introduce Webpack, Vite, Tailwind CLI, or a Node build pipeline into this repository.

Source:
[server.py](file:///home/anisha/Desktop/Sandeep/Stratzy/server.py#L17), [start.sh](file:///home/anisha/Desktop/Sandeep/Stratzy/start.sh), [frontend/index.html](file:///home/anisha/Desktop/Sandeep/Stratzy/frontend/index.html)

---

## DECISION-002 — Disk-Based Local JSON Caching with TTL

Date:
2026-10-15

Decision:
Persist upstream Stratzy advice records, quant scores, and catalog results as local JSON files with time-to-live (`CACHE_TTL` 1–2 hours) on disk (`.algo_selector_cache.json`, `.stratzy_advices_cache.json`, `stratzy_signals_cache.json`).

Reason:
Prevents aggressive request volume to `stratzy.in`, reduces latency on dashboard loads, and avoids IP throttling or bans during scans.

Alternatives considered:
In-memory only cache (lost on server restart), SQLite, Redis.

Do not:
Do not make unthrottled or uncached bulk requests to Stratzy endpoints during runtime user interactions.

Source:
[algo_selector.py](file:///home/anisha/Desktop/Sandeep/Stratzy/algo_selector.py#L50-L54), [overlap_analyzer.py](file:///home/anisha/Desktop/Sandeep/Stratzy/overlap_analyzer.py#L23-L25)

---

## DECISION-003 — 25-Parameter Institutional Scoring Framework with Disqualifying Hard Stops

Date:
2026-10-16

Decision:
Implement an institutional 25-parameter due diligence engine across 5 pillars that uses immediate disqualification (hard stops) for non-negotiable risk violations before ranking survivors by composite score (0–100).

Reason:
Simple ranking by CAGR or raw P&L promotes dangerous curve-fitted or undersampled strategies. Hard stops eliminate low sample sizes, negative multi-timeframe P&L, and excessive drawdowns before scoring.

Alternatives considered:
Simple linear weighted scoring of advertised returns.

Do not:
Do not remove or bypass hard stop rules in `algo_selector.py` to artificially elevate disqualified strategies.

Source:
[ALGO_SELECTION_25_PARAMETERS.md](file:///home/anisha/Desktop/Sandeep/Stratzy/ALGO_SELECTION_25_PARAMETERS.md), [algo_selector.py](file:///home/anisha/Desktop/Sandeep/Stratzy/algo_selector.py)

---

## DECISION-004 — ₹1,00,000 Hard Capital Cap Per Strategy

Date:
2026-10-16

Decision:
Enforce a strict maximum capital requirement of ₹1,00,000 (1 Lakh INR) per strategy. Any strategy requiring > ₹1,00,000 is automatically disqualified.

Reason:
Matches the user's allocated retail capital allocation buffer per algo and prevents recommended strategies from over-leveraging the account.

Alternatives considered:
Scalable lot sizing without hard cutoffs.

Do not:
Do not recommend strategies with minimum capital exceeding ₹1,00,000 unless the user explicitly reconfigures this parameter.

Source:
[ALGO_SELECTION_25_PARAMETERS.md](file:///home/anisha/Desktop/Sandeep/Stratzy/ALGO_SELECTION_25_PARAMETERS.md#L49), [algo_selector.py](file:///home/anisha/Desktop/Sandeep/Stratzy/algo_selector.py)

---

## DECISION-005 — FIFO Trade Matching and Complete NSE Statutory Fee Accounting

Date:
2026-10-15

Decision:
Use First-In-First-Out (FIFO) trade execution pairing in `dhan_engine.py` and account for all Indian exchange statutory charges (STT, brokerage, exchange turnover fees, GST, stamp duty, SEBI turnover fees).

Reason:
Gross P&L from broker tradebooks is misleading in options trading due to high turnover charges and STT on sell legs. Accurate auditing requires net realized P&L after all statutory friction.

Alternatives considered:
LIFO matching, gross P&L only without charge breakdown.

Do not:
Do not calculate trader P&L without deducting statutory charges and brokerage.

Source:
[dhan_engine.py](file:///home/anisha/Desktop/Sandeep/Stratzy/dhan_engine.py#L90-L109), [dhan_engine.py](file:///home/anisha/Desktop/Sandeep/Stratzy/dhan_engine.py#L146-L160)

---

## DECISION-006 — ±15-Minute Signal Execution Window for Strategy Attribution

Date:
2026-10-15

Decision:
Match executed Dhan broker trades to official Stratzy published signals using contract identity (underlying, strike, option type, side) within a ±15-minute timestamp window.

Reason:
Direct broker order logs do not always store the Stratzy strategy ID. Time and contract matching enables attribution of executed trades to specific algos (e.g. Zen vs Damper) and measures execution slippage.

Alternatives considered:
Exact timestamp matching (fails due to order execution latency), tag-based matching only (fails on manual/un-tagged executions).

Do not:
Do not shrink the matching window below execution latency or expand it so wide that distinct daily orders collide.

Source:
[stratzy_reconciler.py](file:///home/anisha/Desktop/Sandeep/Stratzy/stratzy_reconciler.py#L11)
