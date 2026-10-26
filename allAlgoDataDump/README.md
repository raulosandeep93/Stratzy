# Stratzy Algorithms Data Dump (`allAlgoDataDump`)

This folder contains a standalone utility and exported data files for all **101 Active Stratzy Options Algorithms** (spanning Credit Spread, Short Straddle, Short Strangle, and Option Buying).

It is self-contained and decoupled from the main application, designed specifically for offline verification, reporting, and sharing with other LLMs or data tools.

---

## Generated Files

| File | Description | Best Used For |
| :--- | :--- | :--- |
| **`stratzy_101_algos_summary.json`** (~108 KB) | **Condensed Master + Key Metrics JSON**<br>Contains all 19 master fields, normalized quant metrics (Sharpe, Sortino, Calmar, MaxDD, Volatility, Win Month %, Win Quarter %), 1M/3M/6M/1Y PnLs, trade counts, and monthly historical PnL heatmap for all 101 algos. | **Recommended for sharing with other LLMs** (fits easily within LLM context windows while containing all essential quantitative data). |
| **`stratzy_101_algos_table.csv`** (~20 KB) | **Tabular Spreadsheet Format**<br>Compact table with all 101 algorithms and their 21 core comparative columns. | **Quick scanning**, Excel/Google Sheets, or uploading to Claude / ChatGPT for quick tabular prompts. |
| **`stratzy_101_algos_dump.json`** (~20 MB) | **Complete Deep Raw Dump**<br>Includes the complete unadulterated JSON payload for all 5 child endpoints for every strategy (`quantStats`, `metrics-v2`, `characteristics`, `correlation`, `performanceSummary`). | Deep offline quantitative backtesting and raw API response inspection. |

---

## Master Record Fields Included

Each algorithm record includes all 19 requested master fields directly from Stratzy:
- `_id`: Stratzy advisor / strategy unique ID
- `name`: Strategy name
- `risk`: Risk tag (Low, Medium, High, Very High)
- `minimumCapital`: Minimum capital requirement in INR
- `maximumCapital`: Maximum capital limit in INR
- `oneMonthPnl`: 1M PnL %
- `threeMonthPnl`: 3M PnL %
- `sixMonthPnl`: 6M PnL %
- `oneYearPnl`: 1Y PnL %
- `winRatio`: Win rate percentage
- `avgFrequency`: Average trades per week
- `algoScore`: Stratzy proprietary algorithm score
- `deployCount`: Active subscriber deployments
- `liveSince`: ISO timestamp when algo went live
- `backTestingPeriod`: Length of backtest period (e.g. "8 Years")
- `isActive`: Boolean indicating active status
- `inTesting`: Boolean indicating testing status
- `slotsLeft`: Available deployment capacity
- `lastTradedOn`: Timestamp of last executed signal

---

## Child Endpoints Extracted Per Algo

1. **`quantStats`** (`/api/web/algo/quantStats?advisorId={aid}`):
   - Sharpe Ratio, Sortino, Calmar, Max Drawdown %, Volatility (ann.), Worst Month, Max consecutive Losses, Win Month %, Win Quarter %
   - Distribution of monthly returns, worst drawdowns series, underwater equity curves
2. **`metricsV2`** (`/api/web/v2/algo/metrics?advisorId={aid}`):
   - Detailed breakdown for 1M, 3M, 6M, 1Y, and Max timeframes (Total Trades, Win Ratio, Avg Profit, Avg Loss, Booksize Return)
3. **`characteristics`** (`/api/web/algo/characteristics?algoId={aid}`):
   - Strategy tags, trading logic characteristics, and operational parameters
4. **`correlation`** (`/api/web/algo/correlation?advisorId={aid}`):
   - Cross-asset and benchmark correlation figures
5. **`performanceSummary`** (`/api/web/algo/performanceSummary?algoId={aid}`):
   - High-level summary metrics
6. **`historicalPnlBreakdown`** (Monthly PnL):
   - Extracted from `quantStats.plotMonthlyHeatmap` as a clean dictionary `{ "Jul-23": 24.45, ... }`

---

## How to Re-Fetch or Refresh the Data

Whenever you want to refresh the data with live values from Stratzy:

```bash
# 1. Fetch all 101 active options strategies (takes ~15 seconds):
python3 allAlgoDataDump/fetch_all_algos.py

# 2. Or fetch ALL 403 strategies (including inactive, cash, investing):
python3 allAlgoDataDump/fetch_all_algos.py --all
```

The script automatically detects and utilizes your local `.session_cookie` if available to ensure full access.
