# AI Changelog — Stratzy Algo Scanner

AI-oriented development and architectural log.

---

## 2026-10-26

### Added
- Created persistent AI context operating system:
  - [AGENTS.md](file:///home/anisha/Desktop/Sandeep/Stratzy/AGENTS.md) operating manual and session handoff protocol.
  - [docs/ai/PROJECT_CONTEXT.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/PROJECT_CONTEXT.md) high-level architecture and constraints.
  - [docs/ai/CURRENT_STATE.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/CURRENT_STATE.md) handoff state and active findings.
  - [docs/ai/ARCHITECTURE.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/ARCHITECTURE.md) technical design and quant engine specifications.
  - [docs/ai/DECISIONS.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/DECISIONS.md) architectural decision records.
  - [docs/ai/TODO.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/TODO.md) prioritized task list and technical debt.
  - [docs/ai/CHANGELOG.md](file:///home/anisha/Desktop/Sandeep/Stratzy/docs/ai/CHANGELOG.md) development history.
  - Scoped rules in `.agents/rules/` for Python backend, frontend UI, and security.

---

## 2026-10-16

### Added
- **25-Parameter Institutional Framework**: Created [ALGO_SELECTION_25_PARAMETERS.md](file:///home/anisha/Desktop/Sandeep/Stratzy/ALGO_SELECTION_25_PARAMETERS.md) and [algo_selector.py](file:///home/anisha/Desktop/Sandeep/Stratzy/algo_selector.py) to filter and rank Top 5 algorithm picks across 5 risk pillars with hard stop disqualifications.
- **Trade Overlap Analyzer**: Implemented [overlap_analyzer.py](file:///home/anisha/Desktop/Sandeep/Stratzy/overlap_analyzer.py) to calculate exact contract collisions and concurrent trading sessions across 3 strategies using live Stratzy past advice signals.
- **Offline 101 Algos Dump Pipeline**: Created [allAlgoDataDump/](file:///home/anisha/Desktop/Sandeep/Stratzy/allAlgoDataDump/) with `fetch_all_algos.py`, exporting condensed master JSON and CSV files.

### Changed
- Integrated top picks scorecard and pairwise/3-way overlap inspector into `frontend/index.html` and `frontend/app.js`.

---

## 2026-10-15

### Added
- **Dhan Tradebook Parser & FIFO Engine**: Implemented [dhan_engine.py](file:///home/anisha/Desktop/Sandeep/Stratzy/dhan_engine.py) to parse CSV/XLSX/XLS tradebooks, pair execution legs with FIFO matching, and calculate full NSE statutory fees (STT, GST, stamp duty, turnover fees).
- **Stratzy Reconciler**: Implemented [stratzy_reconciler.py](file:///home/anisha/Desktop/Sandeep/Stratzy/stratzy_reconciler.py) to match broker executions with published advisor signals within ±15 minutes for slippage and P&L attribution.
- **Dhan API & Debug Utility**: Added direct DhanHQ REST API client in `dhan_engine.py` and CLI utility `debug_dhan.py`.

---

## 2026-10-14

### Added
- Initial project creation: Flask backend server ([server.py](file:///home/anisha/Desktop/Sandeep/Stratzy/server.py)), static launcher script ([start.sh](file:///home/anisha/Desktop/Sandeep/Stratzy/start.sh)), and dependency list ([requirements.txt](file:///home/anisha/Desktop/Sandeep/Stratzy/requirements.txt)).
- Frontend dashboard SPA ([frontend/index.html](file:///home/anisha/Desktop/Sandeep/Stratzy/frontend/index.html), [frontend/app.js](file:///home/anisha/Desktop/Sandeep/Stratzy/frontend/app.js), [frontend/styles.css](file:///home/anisha/Desktop/Sandeep/Stratzy/frontend/styles.css)) featuring glassmorphic dark UI, multi-category scanning, and watchlist management.
