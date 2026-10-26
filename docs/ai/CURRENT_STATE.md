# Current State — Stratzy Algo Scanner & Strategy Intelligence Dashboard

## Last Updated
2026-10-26

## Current Project Status
Fully functional local application. The Flask server, 25-parameter quant selection engine, dynamic trade overlap analyzer, and Dhan broker reconciler/auditor are fully implemented and running locally via `bash start.sh` or `python3 server.py`.

## Recently Completed
- Implemented the 25-parameter institutional selection engine in [algo_selector.py](file:///home/anisha/Desktop/Sandeep/Stratzy/algo_selector.py) with hard stops (₹1L max cap, min 15 trades in 3M, positive 3M/6M/1Y PnL).
- Built real-time trade overlap analyzer in [overlap_analyzer.py](file:///home/anisha/Desktop/Sandeep/Stratzy/overlap_analyzer.py) supporting pairwise and 3-way simultaneous collision checks.
- Developed the Dhan tradebook FIFO parser and regulatory fee auditor in [dhan_engine.py](file:///home/anisha/Desktop/Sandeep/Stratzy/dhan_engine.py).
- Created offline 101 options strategies dump pipeline in [allAlgoDataDump/](file:///home/anisha/Desktop/Sandeep/Stratzy/allAlgoDataDump/).

## Currently in Progress
- Establishing AI context and operating system (`AGENTS.md`, `docs/ai/`, `.agents/rules/`).

## Known Issues
- Repository is not initialized with Git (`.git` directory is not present in workspace).
- Stratzy web session cookies and DhanHQ JWT access tokens expire periodically and must be manually replaced.
- No automated unit test runner (`pytest`) currently configured; verification relies on `python3 -m py_compile` and manual testing.

## Current Blockers
None.

## Recently Modified Areas
- Root-level Python modules: [server.py](file:///home/anisha/Desktop/Sandeep/Stratzy/server.py), [algo_selector.py](file:///home/anisha/Desktop/Sandeep/Stratzy/algo_selector.py), [overlap_analyzer.py](file:///home/anisha/Desktop/Sandeep/Stratzy/overlap_analyzer.py), [dhan_engine.py](file:///home/anisha/Desktop/Sandeep/Stratzy/dhan_engine.py), [stratzy_reconciler.py](file:///home/anisha/Desktop/Sandeep/Stratzy/stratzy_reconciler.py)
- Frontend: [frontend/index.html](file:///home/anisha/Desktop/Sandeep/Stratzy/frontend/index.html), [frontend/app.js](file:///home/anisha/Desktop/Sandeep/Stratzy/frontend/app.js), [frontend/styles.css](file:///home/anisha/Desktop/Sandeep/Stratzy/frontend/styles.css)
- Offline data dump: [allAlgoDataDump/](file:///home/anisha/Desktop/Sandeep/Stratzy/allAlgoDataDump/)

## Next Recommended Actions
1. Initialize git version control (`git init`) and commit baseline codebase with an appropriate `.gitignore` to protect `.session_cookie` and token dotfiles.
2. Add a lightweight test suite (e.g. `tests/test_dhan_engine.py`, `tests/test_algo_selector.py`) to automate validation of FIFO matching and institutional scoring filters.
3. Add a visual status indicator in the UI when the Stratzy session cookie expires or returns 401.

## Important Discoveries
- The user's active portfolio in [.user_invested_algos.json](file:///home/anisha/Desktop/Sandeep/Stratzy/.user_invested_algos.json) holds 3 specific algorithms:
  - `Zen Credit Spread Overnight` (id: `68596cd26aa2cba24bbb67da`)
  - `IV-Imbalance Credit Spread Overnight` (id: `687d0a309107a80e07401e5d`)
  - `Damper Credit Spread` (id: `68c9b755c7ed8fff5c5de9af`)
- Stratzy API returns UTC timestamps; they must always be converted to IST (`+05:30`) for trading day alignment.

## Do Not Redo
- Do NOT convert the frontend to React, Next.js, or Vite; vanilla JS/HTML/CSS is intentionally chosen for zero-build local execution.
- Do NOT replace local JSON caching with PostgreSQL or Redis; file-based caching meets performance and simplicity goals.
