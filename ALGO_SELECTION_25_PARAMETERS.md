# Institutional 25-Parameter Algorithm Selection & Due Diligence Framework

This document outlines the **25-Parameter Institutional Framework** implemented in Stratzy Algo Engine (`algo_selector.py`) for vetting, scoring, and selecting the **Top 5 Algo Strategies**.

Every strategy scan evaluates these 25 parameters across 5 core pillars. Any strategy failing critical non-negotiable filters is immediately disqualified.

---

## Pillar 1: Return & Risk Quality

| # | Parameter | Institutional Benchmark | Why It Matters |
|---|---|---|---|
| **1** | **Sharpe Ratio** | **1.5+** preferred | Measures excess return per unit of total risk. Filters out low-density strategies. |
| **2** | **Sortino Ratio** | **Well above Sharpe** | Isolates downside volatility from upside volatility. High Sortino indicates clean, one-sided upside. |
| **3** | **Calmar Ratio** | **2.0+** preferred | Compound annual growth divided by maximum drawdown. Ensures fast recovery after equity dips. |
| **4** | **Max Drawdown %** | **<= 25%** of capital buffer | Preserves account capital. Keeps drawdowns within survivable retail buffers. |
| **5** | **Annualised Volatility** | **Lower is better** (<= 35%) | Prevents violent swings and ensures smooth capital compounding. |
| **6** | **Worst Month Drawdown** | **Sit-through tolerance (< 15%)** | Psychological threshold — ensures you will not abandon the algo during its toughest calendar month. |
| **7** | **Max Consecutive Losses** | **<= 5–6 trades** | Losing streak survivability. Limits emotional tilt and capital erosion before reversal. |

---

## Pillar 2: Consistency

| # | Parameter | Institutional Benchmark | Why It Matters |
|---|---|---|---|
| **8** | **Win-Month %** | **70%+** preferred | Month-over-month predictability. Avoids feast-or-famine strategies. |
| **9** | **Win-Quarter %** | **75%+** preferred | Critical for quarterly evaluation cycles (3-month durability). |
| **10** | **3M, 6M & 1Y PnL Positive** | **All 3 must be > 0** | **CRITICAL HARD STOP**: Disqualifies one-hit wonders with negative historical stretches. |
| **11** | **Mathematical Expectancy** | **Net edge > 0.5% / trade** | `(Win Rate × Avg Profit) - (Loss Rate × Avg Loss)`. Ensures mathematical edge after friction. |
| **12** | **Risk-Reward Ratio** | **>= 1.0 (Avg Profit / Avg Loss)** | Ensures average wins outweigh or match average losses so win rate drops do not destroy account. |

---

## Pillar 3: Reliability of the Numbers

| # | Parameter | Institutional Benchmark | Why It Matters |
|---|---|---|---|
| **13** | **Trade Count in 3M** | **>= 15–20 trades** | **CRITICAL HARD STOP**: Disqualifies undersampled anomalies (e.g. Ratio-Fluxer which only took 7 trades). |
| **14** | **Track Record Length** | **>= 180 days active** | Assures the strategy survived multiple expiry cycles and market volatility regimes. |
| **15** | **Backtest vs Live Sanity** | **Verified signals** | Live broker and advisor execution must match advertised backtest performance (checked as with IV). |

---

## Pillar 4: Fit for Your Account

| # | Parameter | Institutional Benchmark | Why It Matters |
|---|---|---|---|
| **16** | **Minimum Capital vs Buffer** | **<= ₹1,00,000 (User 1L Cap)** | **CRITICAL HARD STOP**: Strictly caps investment per strategy at ₹1,00,000; any strategy requiring > ₹1L is disqualified. |
| **17** | **Risk Tag** | **Low or Medium** | Preserves capital safety margins; filters out hyper-aggressive speculative tiers. |
| **18** | **Rupee Drawdown on Lot Size** | **<= ₹25,000 – ₹35,000** | Exact rupee loss at 1 lot (`|MaxDD%| × MinCapital`). Avoids deceptive small percentage claims. |
| **19** | **Trade Frequency** | **2–5 trades / week** | Generates sufficient real-world statistical proof quickly without burning cash in churn. |
| **20** | **Charges & Slippage Drag** | **< 12–15% of gross PnL** | Accounts for STT, brokerage, exchange turnover charges, and execution slippage drag. |

---

## Pillar 5: Portfolio Fit & Diversification

| # | Parameter | Institutional Benchmark | Why It Matters |
|---|---|---|---|
| **21** | **Family & Strategy Diversity** | **Spread across Spread / Straddle / Strangle** | Prevents structural clustering; balances delta, vega, and gamma profiles. |
| **22** | **Correlation to Held Algos** | **Low correlation** | Independent entry logic so all algos do not take simultaneous losses on the same event. |
| **23** | **Live Trade Overlap** | **<= 2–4 overlapping trades** | **CRITICAL HARD STOP**: Avoids identical strikes, sides, and timestamps as Zen, IV-Imbalance, or Damper. |
| **24** | **Entry Timing Pattern** | **Distributed execution** | Avoids known high-risk vulnerability windows (e.g. IV-Imbalance's late-morning put entries). |
| **25** | **Directional & Overnight Balance** | **CE/PE & Intraday/Overnight balance** | Neutralizes directional index skew (CE vs PE) and overnight gap-risk exposure. |

---

## Automated Execution Pipeline

1. **Scan Engine (`server.py`)**: Runs all candidate strategies against `evaluate_algo_25_parameters()`.
2. **Hard Stops Enforced**:
   - Rule 16: Minimum Capital `> ₹1,00,000` ➔ **Instant Disqualification (User 1L Cap)**
   - Rule 13: Sample size `< 15 trades` in 3M ➔ **Instant Disqualification**
   - Rule 10: Any of 3M, 6M, 1Y PnL `<= 0` ➔ **Instant Disqualification**
   - Rule 23: Heavy live overlap `> 10 trades` with active portfolio ➔ **Instant Disqualification**
   - Rule 4 & 18: Catastrophic Drawdown (`> 55%` or Rupee DD `> ₹55,000`) ➔ **Instant Disqualification**
3. **Top 5 Selection (`algo_selector.py`)**: Ranks survivors by composite institutional score (0–100) and ensures family diversity and near-clone deduplication.
4. **Interactive UI (`frontend/app.js` & `index.html`)**: Renders the complete 25-parameter scorecard with pass/caution/fail pill badges and detailed due diligence findings for each suggestion.
