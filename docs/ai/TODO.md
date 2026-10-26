# TODO — Stratzy Algo Scanner Backlog

Tasks and technical debt extracted from codebase analysis and project state.

---

## High Priority

- [ ] **Git Version Control Setup**: Initialize a local git repository (`git init`) and commit the project baseline with a `.gitignore` that safely excludes `.session_cookie`, `.token_*`, `.all_cookies_*`, `.clean_jwt`, and `__pycache__`.
- [ ] **Session Expiry Handling in UI**: Display an explicit notification/badge in the dashboard when the Stratzy session cookie returns 401/403 or expires, prompting the user to refresh the cookie.

---

## Medium Priority

- [ ] **Automated Test Suite**: Create unit tests in a `tests/` directory covering:
  - `dhan_engine.py`: FIFO trade matching, contract expiry date parsing, statutory fee calculation formulas.
  - `algo_selector.py`: Hard stop filters (₹1L capital cap, trade count >= 15, positive 3M/6M/1Y PnL).
  - `stratzy_reconciler.py`: Symbol normalization and ±15-minute time window matching.
- [ ] **Standardize Multi-Profile Token Files**: Consolidate or clean up fragmented profile files (`.all_cookies_Profile_1`, `.all_cookies_Profile_7`, `.token_Profile_1`, `.token_Profile_7`) into a unified configuration schema.
- [ ] **Tradebook Table Pagination**: Add client-side pagination or virtual scrolling in `frontend/app.js` for Dhan tradebook reports containing 1,000+ executions.

---

## Low Priority

- [ ] **Configurable Capital Allocation Cap**: Allow users to adjust the ₹1,00,000 capital filter parameter directly from the frontend scanner settings instead of hardcoding in `algo_selector.py`.
- [ ] **In-App Data Dump Trigger**: Expose an endpoint and UI button to run `allAlgoDataDump/fetch_all_algos.py` without requiring terminal access.

---

## Technical Debt

- [ ] **Remove Development `importlib.reload` Calls**: `server.py` currently reloads `overlap_analyzer` and `algo_selector` on every request to `/api/algo/overlap`, `/api/algo/catalog-options`, and `/api/algo/top-picks`. Replace with standard module imports once modules stabilize.
- [ ] **Deduplicate Symbol Normalization**: Consolidate `infer_underlying()` in [dhan_engine.py](file:///home/anisha/Desktop/Sandeep/Stratzy/dhan_engine.py#L18) and `normalize_sym_info()` in [stratzy_reconciler.py](file:///home/anisha/Desktop/Sandeep/Stratzy/stratzy_reconciler.py#L35) into a shared utility function.
