#!/usr/bin/env python3
"""
Dhan Engine - Tradebook Parser, FIFO Matcher, Analytics & DhanHQ API Client
Processes Dhan tradebook CSVs and direct API data to audit algo performance.
"""

import csv
import io
import re
import math
from datetime import datetime, timedelta
import requests

def clean_key(k):
    """Normalize dictionary keys to lowercase alphanumeric."""
    return re.sub(r'[^a-z0-9]', '', str(k).strip().lower())

def infer_underlying(symbol):
    """Detect underlying asset and option type from trading symbol."""
    sym = symbol.upper()
    if 'BANKNIFTY' in sym or 'BANK NIFTY' in sym:
        underlying = 'BANKNIFTY'
    elif 'FINNIFTY' in sym or 'FIN NIFTY' in sym:
        underlying = 'FINNIFTY'
    elif 'MIDCPNIFTY' in sym or 'MIDCAP' in sym:
        underlying = 'MIDCPNIFTY'
    elif 'NIFTY' in sym:
        underlying = 'NIFTY'
    elif 'SENSEX' in sym:
        underlying = 'SENSEX'
    elif 'BANKEX' in sym:
        underlying = 'BANKEX'
    else:
        underlying = sym.split()[0] if ' ' in sym else sym[:8]

    opt_type = 'CE' if 'CE' in sym else ('PE' if 'PE' in sym else 'FUT')
    return underlying, opt_type


def extract_expiry_date(symbol):
    """
    Extracts the real contract expiry date from a trading symbol string.
    Handles formats produced by _normalize_symbol():
      - NIFTY 2026-10-19 23100 PE  (primary canonical form)
      - NIFTY 19 OCT 22500 PUT     (Dhan history customSymbol)
      - NIFTY26O1923100PE          (Stratzy compact notation)
    Returns a datetime.date or None.
    """
    if not symbol:
        return None
    sym_u = symbol.upper()

    # 1. YYYY-MM-DD embedded in symbol
    m = re.search(r'(202\d|203\d)-(\d{2})-(\d{2})', sym_u)
    if m:
        try:
            return datetime.strptime(m.group(0), '%Y-%m-%d').date()
        except Exception:
            pass

    # 2. DD Mon YYYY  (e.g. "19 OCT 2026" or "19-OCT-2026")
    m = re.search(
        r'(\d{1,2})\s*[-/]?\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)'
        r'\s*[-/]?\s*(202\d|203\d)', sym_u
    )
    if m:
        try:
            return datetime.strptime(
                f'{m.group(1)} {m.group(2)} {m.group(3)}', '%d %b %Y'
            ).date()
        except Exception:
            pass

    # 3. DD Mon  (without year — assume current year, e.g. "19 OCT")
    m = re.search(
        r'(\d{1,2})\s*[-/]?\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b',
        sym_u
    )
    if m:
        yr = datetime.now().year
        try:
            return datetime.strptime(
                f'{m.group(1)} {m.group(2)} {yr}', '%d %b %Y'
            ).date()
        except Exception:
            pass

    return None

def calculate_charges(buy_val, sell_val, is_option=True):
    """
    Calculate statutory Dhan and exchange regulatory charges for NSE F&O.
    Brokerage: Rs 20 per order or 0.03% (whichever lower)
    STT: 0.1% on Option sell value (since Oct 2024), 0.0125% for futures
    Exchange charges: 0.0505% on option turnover
    GST: 18% on (Brokerage + Exchange)
    Stamp duty: 0.003% on buy value
    SEBI fee: 0.0001% on turnover
    """
    turnover = buy_val + sell_val
    brokerage = 20.0 + 20.0  # entry + exit orders
    stt = (sell_val * 0.001) if is_option else (sell_val * 0.000125)
    exchange_charges = turnover * 0.000505
    gst = (brokerage + exchange_charges) * 0.18
    stamp_duty = buy_val * 0.00003
    sebi_charges = turnover * 0.000001
    
    total = brokerage + stt + exchange_charges + gst + stamp_duty + sebi_charges
    return round(total, 2)

def parse_date_time(date_str, time_str):
    """Parse date and time strings with multiple format fallbacks."""
    date_str = str(date_str or '').strip()
    time_str = str(time_str or '').strip()
    
    # Clean up any trailing Z or fractional seconds
    time_str = re.sub(r'\.\d+', '', time_str)
    
    combined = f"{date_str} {time_str}".strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%y %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(combined, fmt)
        except Exception:
            pass
    for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(date_str, fmt)
        except Exception:
            pass
    return datetime.now()

def process_trades_fifo(raw_executions, live_positions=None):
    """
    Takes a list of execution orders and pairs them via FIFO matching
    to produce closed roundtrip trades.

    live_positions: optional list of Dhan /v2/positions records.
      Used to look up the current MTM price for open legs so they are
      not incorrectly settled at ₹0.
    """
    # Sort chronologically
    sorted_execs = sorted(raw_executions, key=lambda x: x.get('dt', datetime.min))
    
    symbol_positions = {}  # symbol -> list of {side, qty, price, dt, order_id, tag}
    closed_trades = []
    trade_counter = 1

    for exc in sorted_execs:
        sym = exc['symbol']
        side = exc['side'].upper()
        qty = exc['qty']
        price = exc['price']
        dt = exc.get('dt') or datetime.now()
        tag = exc.get('tag') or ''

        if sym not in symbol_positions:
            symbol_positions[sym] = []

        open_legs = symbol_positions[sym]

        # Check if opposite legs exist
        remaining_qty = qty
        while remaining_qty > 0 and open_legs:
            first_leg = open_legs[0]
            if first_leg['side'] == side:
                # Same direction, add to queue
                break

            match_qty = min(remaining_qty, first_leg['qty'])
            remaining_qty -= match_qty
            first_leg['qty'] -= match_qty

            # Determine Long or Short
            if first_leg['side'] == 'BUY':
                entry_leg = first_leg
                exit_price = price
                entry_price = first_leg['price']
                direction = 'LONG'
                buy_val = match_qty * entry_price
                sell_val = match_qty * exit_price
                gross_pnl = (exit_price - entry_price) * match_qty
            else:
                entry_leg = first_leg
                exit_price = price
                entry_price = first_leg['price']
                direction = 'SHORT'
                buy_val = match_qty * exit_price
                sell_val = match_qty * entry_price
                gross_pnl = (entry_price - exit_price) * match_qty

            underlying, opt_type = infer_underlying(sym)
            charges = calculate_charges(buy_val, sell_val, is_option=(opt_type in ['CE', 'PE']))
            net_pnl = round(gross_pnl - charges, 2)
            
            # Duration calculation
            duration_minutes = 0
            if dt and entry_leg.get('dt'):
                diff = dt - entry_leg['dt']
                duration_minutes = max(1, int(diff.total_seconds() / 60))

            algo_tag = tag or entry_leg.get('tag') or f"{underlying} {opt_type} Strategy"

            closed_trades.append({
                "id": f"TRD-{trade_counter:04d}",
                "symbol": sym,
                "underlying": underlying,
                "optType": opt_type,
                "algoTag": algo_tag,
                "direction": direction,
                "qty": match_qty,
                "entryTime": entry_leg['dt'].strftime("%Y-%m-%d %H:%M:%S") if entry_leg.get('dt') else "",
                "exitTime": dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "",
                "exitDate": dt.strftime("%Y-%m-%d") if dt else "",
                "entryPrice": round(entry_price, 2),
                "exitPrice": round(exit_price, 2),
                "grossPnl": round(gross_pnl, 2),
                "charges": charges,
                "netPnl": net_pnl,
                "returnPct": round((net_pnl / (entry_price * match_qty)) * 100, 2) if entry_price > 0 else 0.0,
                "durationMin": duration_minutes,
                "isWin": net_pnl > 0,
            })
            trade_counter += 1

            if first_leg['qty'] <= 0:
                open_legs.pop(0)

        # Any leftover quantity becomes an open position
        if remaining_qty > 0:
            open_legs.append({
                "side": side,
                "qty": remaining_qty,
                "price": price,
                "dt": dt,
                "order_id": exc.get('order_id', ''),
                "tag": tag,
            })

    # Build a quick lookup from live positions for MTM prices (symbol -> position record)
    pos_by_sym = {}
    if live_positions:
        for p in live_positions:
            raw_sym = str(p.get('tradingSymbol', ''))
            # Normalise to the same canonical key used in symbol_positions
            # Try to build UNDERLYING YYYY-MM-DD STRIKE OT from position fields
            p_underlying = raw_sym.upper()
            drv_exp = str(p.get('drvExpiryDate', '')).strip()[:10]  # YYYY-MM-DD
            drv_st  = int(float(p.get('drvStrikePrice') or 0))
            drv_ot  = 'CE' if str(p.get('drvOptionType', '')).upper() in ['CALL', 'CE'] else 'PE'
            # Detect underlying
            u = 'BANKNIFTY' if 'BANK' in p_underlying else ('FINNIFTY' if 'FINNIFTY' in p_underlying else 'NIFTY')
            if drv_st > 0 and drv_exp:
                canon = f"{u} {drv_exp} {drv_st} {drv_ot}"
            else:
                canon = raw_sym
            pos_by_sym[canon] = p

    today = datetime.now().date()

    # Settle positions that were held to expiry OR still open
    for sym, open_legs in symbol_positions.items():
        underlying, opt_type = infer_underlying(sym)

        # Determine the real contract expiry date (None if we can't parse it)
        expiry_date = extract_expiry_date(sym)
        contract_has_expired = (expiry_date is not None and expiry_date < today)

        for leg in open_legs:
            if leg['qty'] <= 0:
                continue
            leg_dt   = leg.get('dt') or datetime.now()
            match_qty = leg['qty']
            entry_price = leg['price']

            if opt_type not in ['CE', 'PE']:
                # Futures / Equities — leave genuinely open positions out of closed trades
                continue

            if not contract_has_expired:
                # ── OPEN POSITION: contract still alive ──────────────────────────────
                # Use live MTM price from Dhan positions API if available
                live_pos = pos_by_sym.get(sym)
                if live_pos:
                    # Use buyAvg / sellAvg as a proxy for current market price
                    if leg['side'] == 'BUY':
                        mtm_price = float(live_pos.get('sellAvg') or live_pos.get('buyAvg') or entry_price)
                        # fallback: use costPrice-adjusted unrealized
                        unrealized = float(live_pos.get('unrealizedProfit') or 0)
                        if unrealized != 0 and match_qty > 0:
                            mtm_price = round(entry_price + unrealized / match_qty, 2)
                    else:
                        mtm_price = float(live_pos.get('buyAvg') or live_pos.get('sellAvg') or entry_price)
                        unrealized = float(live_pos.get('unrealizedProfit') or 0)
                        if unrealized != 0 and match_qty > 0:
                            mtm_price = round(entry_price - unrealized / match_qty, 2)
                else:
                    # No live data — mark as open at cost (zero MTM movement shown)
                    mtm_price = entry_price

                if leg['side'] == 'BUY':
                    gross_pnl = (mtm_price - entry_price) * match_qty
                    buy_val   = match_qty * entry_price
                    sell_val  = match_qty * mtm_price
                else:
                    gross_pnl = (entry_price - mtm_price) * match_qty
                    buy_val   = match_qty * mtm_price
                    sell_val  = match_qty * entry_price

                # Use half-charges for open legs (only entry brokerage paid so far)
                charges = round(calculate_charges(buy_val, sell_val, True) / 2, 2)
                net_pnl = round(gross_pnl - charges, 2)
                direction = 'LONG' if leg['side'] == 'BUY' else 'SHORT'

                expiry_label = expiry_date.strftime("%Y-%m-%d") if expiry_date else "unknown expiry"
                closed_trades.append({
                    "id": f"TRD-{trade_counter:04d}",
                    "symbol": sym,
                    "underlying": underlying,
                    "optType": opt_type,
                    "algoTag": leg.get('tag') or f"{underlying} (Open — expires {expiry_label})",
                    "direction": direction,
                    "qty": match_qty,
                    "entryTime": leg_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "exitTime": "",
                    "exitDate": "",
                    "entryPrice": round(entry_price, 2),
                    "exitPrice": round(mtm_price, 2),
                    "grossPnl": round(gross_pnl, 2),
                    "charges": charges,
                    "netPnl": net_pnl,
                    "returnPct": round((net_pnl / (entry_price * match_qty)) * 100, 2) if entry_price > 0 else 0.0,
                    "durationMin": 0,
                    "isWin": net_pnl > 0,
                    "isOpen": True,
                })
                trade_counter += 1

            else:
                # ── TRULY EXPIRED: contract date has passed, settle at ₹0 ───────────
                if leg['side'] == 'BUY':
                    gross_pnl = -(entry_price * match_qty)
                    charges   = calculate_charges(entry_price * match_qty, 0, True)
                    net_pnl   = round(gross_pnl - charges, 2)
                    direction, ret_pct, is_win = 'LONG', -100.0, False
                else:
                    gross_pnl = entry_price * match_qty
                    charges   = calculate_charges(0, entry_price * match_qty, True)
                    net_pnl   = round(gross_pnl - charges, 2)
                    direction, ret_pct, is_win = 'SHORT', 100.0, True

                expiry_label = expiry_date.strftime("%Y-%m-%d") if expiry_date else "unknown"
                closed_trades.append({
                    "id": f"TRD-{trade_counter:04d}",
                    "symbol": sym,
                    "underlying": underlying,
                    "optType": opt_type,
                    "algoTag": leg.get('tag') or f"{underlying} (Expired {expiry_label})",
                    "direction": direction,
                    "qty": match_qty,
                    "entryTime": leg_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "exitTime": (leg_dt + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"),
                    "exitDate": expiry_label,
                    "entryPrice": round(entry_price, 2),
                    "exitPrice": 0.0,
                    "grossPnl": round(gross_pnl, 2),
                    "charges": charges,
                    "netPnl": net_pnl,
                    "returnPct": ret_pct,
                    "durationMin": 360,
                    "isWin": is_win,
                    "isOpen": False,
                })
                trade_counter += 1

    return closed_trades

def compute_dhan_analytics(closed_trades, session_cookie=None):
    """Computes all summary statistics, daily equity curves, and algo groupings."""
    if not closed_trades:
        return {
            "totalTrades": 0,
            "winTrades": 0,
            "lossTrades": 0,
            "breakEvenTrades": 0,
            "winRate": 0,
            "netPnl": 0,
            "grossProfit": 0,
            "grossLoss": 0,
            "totalCharges": 0,
            "profitFactor": 0,
            "avgWin": 0,
            "avgLoss": 0,
            "winLossRatio": 0,
            "maxWin": 0,
            "maxLoss": 0,
            "maxDrawdown": 0,
            "maxDrawdownPct": 0,
            "dailyPnl": [],
            "equityCurve": [],
            "algoBreakdown": [],
            "trades": [],
            "reconciliation": {"matched": 0, "total": 0, "matchPct": 0, "slippageRs": 0}
        }

    # Automatically reconcile with Stratzy signals to attribute true algo names & slippage
    recon_stats = {"matched": 0, "total": len(closed_trades), "matchPct": 0, "slippageRs": 0}
    try:
        from stratzy_reconciler import reconcile_trades
        closed_trades, recon_stats = reconcile_trades(closed_trades, session_cookie=session_cookie)
    except Exception:
        pass

    # Sort trades chronologically
    trades = sorted(closed_trades, key=lambda t: t.get("exitTime", ""))
    
    total_trades = len(trades)
    win_trades = sum(1 for t in trades if t["netPnl"] > 0)
    loss_trades = sum(1 for t in trades if t["netPnl"] < 0)
    be_trades = sum(1 for t in trades if t["netPnl"] == 0)

    gross_profit = round(sum(t["grossPnl"] for t in trades if t["grossPnl"] > 0), 2)
    gross_loss = round(sum(abs(t["grossPnl"]) for t in trades if t["grossPnl"] < 0), 2)
    total_charges = round(sum(t["charges"] for t in trades), 2)
    net_pnl = round(sum(t["netPnl"] for t in trades), 2)

    win_rate = round((win_trades / total_trades) * 100, 1) if total_trades else 0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

    avg_win = round(gross_profit / win_trades, 2) if win_trades else 0
    avg_loss = round(gross_loss / loss_trades, 2) if loss_trades else 0
    win_loss_ratio = round(avg_win / avg_loss, 2) if avg_loss else 0

    max_win = max((t["netPnl"] for t in trades), default=0)
    max_loss = min((t["netPnl"] for t in trades), default=0)

    # Daily aggregation & Equity curve
    daily_map = {}
    running_pnl = 0.0
    equity_curve = [{"trade": 0, "date": "Start", "cumulative": 0.0, "pnl": 0.0}]
    
    peak_pnl = 0.0
    max_dd = 0.0

    for i, t in enumerate(trades):
        running_pnl += t["netPnl"]
        running_pnl = round(running_pnl, 2)
        
        # Max drawdown tracking
        if running_pnl > peak_pnl:
            peak_pnl = running_pnl
        dd = peak_pnl - running_pnl
        if dd > max_dd:
            max_dd = dd

        equity_curve.append({
            "trade": i + 1,
            "id": t["id"],
            "date": t.get("exitDate", "") or t.get("exitTime", "")[:10],
            "pnl": t["netPnl"],
            "cumulative": running_pnl
        })

        date_key = t.get("exitDate", "") or t.get("exitTime", "")[:10] or "Unknown"
        if date_key not in daily_map:
            daily_map[date_key] = {"date": date_key, "netPnl": 0.0, "trades": 0, "wins": 0, "losses": 0}
        daily_map[date_key]["netPnl"] = round(daily_map[date_key]["netPnl"] + t["netPnl"], 2)
        daily_map[date_key]["trades"] += 1
        if t["netPnl"] > 0:
            daily_map[date_key]["wins"] += 1
        elif t["netPnl"] < 0:
            daily_map[date_key]["losses"] += 1

    daily_pnl = sorted(list(daily_map.values()), key=lambda d: d["date"])

    # 3. Restrict algo audit cards strictly to user's invested Stratzy algos
    try:
        from stratzy_reconciler import fetch_user_invested_algos
        invested_algos = fetch_user_invested_algos(session_cookie=session_cookie)
    except Exception:
        invested_algos = [
            {"id": "68596cd26aa2cba24bbb67da", "name": "Zen Credit Spread Overnight", "broker": "DHAN"},
            {"id": "68c9b755c7ed8fff5c5de9af", "name": "Damper Credit Spread", "broker": "DHAN"},
            {"id": "687d0a309107a80e07401e5d", "name": "IV-Imbalance Credit Spread Overnight", "broker": "DHAN"}
        ]

    invested_names = {a["name"] for a in invested_algos}

    algo_groups = {
        a["name"]: {
            "name": a["name"],
            "id": a.get("id", ""),
            "broker": a.get("broker", "DHAN"),
            "stratzyOverallPnl": float(a.get("stratzyOverallPnl", a.get("overallPnL", 0))),
            "stratzyCurrentPnl": float(a.get("stratzyCurrentPnl", 0)),
            "stratzyTrades": int(a.get("stratzyTrades", 0)),
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "netPnl": 0.0,
            "grossProfit": 0.0,
            "grossLoss": 0.0,
            "charges": 0.0,
            "pnls": []
        }
        for a in invested_algos
    }

    for t in trades:
        tag = t.get("algoTag")
        if tag not in algo_groups:
            # Check if trade was matched by reconciler to an invested algo
            sm = t.get("stratzyMatch")
            if sm and sm.get("algoName") in algo_groups:
                tag = sm.get("algoName")
                t["algoTag"] = tag

        if tag in algo_groups:
            g = algo_groups[tag]
            g["trades"] += 1
            g["netPnl"] = round(g["netPnl"] + t["netPnl"], 2)
            g["charges"] = round(g["charges"] + t["charges"], 2)
            if t["netPnl"] > 0:
                g["wins"] += 1
                g["grossProfit"] = round(g["grossProfit"] + t["grossPnl"], 2)
            elif t["netPnl"] < 0:
                g["losses"] += 1
                g["grossLoss"] = round(g["grossLoss"] + abs(t["grossPnl"]), 2)
            g["pnls"].append(t["netPnl"])

    algo_breakdown = []
    for tag, g in algo_groups.items():
        wr = round((g["wins"] / g["trades"]) * 100, 1) if g["trades"] else 0
        pf = round(g["grossProfit"] / g["grossLoss"], 2) if g["grossLoss"] > 0 else (99.0 if g["grossProfit"] > 0 else 0)
        avg_trade = round(g["netPnl"] / g["trades"], 2) if g["trades"] else 0
        
        # Determine verdict
        if g["trades"] == 0:
            verdict = "STANDBY"
            badge_class = "verdict-caution"
            reason = "Active in Stratzy portfolio. No completed executions detected in the selected period."
        elif g["netPnl"] > 0 and wr >= 50 and pf >= 1.5:
            verdict = "RETAIN"
            badge_class = "verdict-retain"
            reason = "High profit factor, healthy win rate, and strong risk-adjusted returns."
        elif g["netPnl"] > 0 or wr >= 45:
            verdict = "CAUTION"
            badge_class = "verdict-caution"
            reason = "Profitable but watch out for transaction charges/slippage drag eating into margins."
        else:
            verdict = "SWAP CANDIDATE"
            badge_class = "verdict-swap"
            reason = "Underperforming over period. Consider rotating capital into Top Picks."

        algo_breakdown.append({
            "name": tag,
            "id": g.get("id", ""),
            "broker": g.get("broker", "DHAN"),
            "stratzyOverallPnl": g["stratzyOverallPnl"],
            "stratzyCurrentPnl": g["stratzyCurrentPnl"],
            "stratzyTrades": g["stratzyTrades"],
            "trades": g["trades"],
            "wins": g["wins"],
            "losses": g["losses"],
            "winRate": wr,
            "netPnl": g["netPnl"],
            "charges": g["charges"],
            "profitFactor": pf,
            "avgTradePnl": avg_trade,
            "verdict": verdict,
            "badgeClass": badge_class,
            "reason": reason
        })

    # Sort algos by net PnL descending
    algo_breakdown = sorted(algo_breakdown, key=lambda a: a["netPnl"], reverse=True)

    return {
        "totalTrades": total_trades,
        "winTrades": win_trades,
        "lossTrades": loss_trades,
        "breakEvenTrades": be_trades,
        "winRate": win_rate,
        "netPnl": net_pnl,
        "grossProfit": gross_profit,
        "grossLoss": gross_loss,
        "totalCharges": total_charges,
        "profitFactor": profit_factor,
        "avgWin": avg_win,
        "avgLoss": avg_loss,
        "winLossRatio": win_loss_ratio,
        "maxWin": max_win,
        "maxLoss": max_loss,
        "maxDrawdown": round(max_dd, 2),
        "dailyPnl": daily_pnl,
        "equityCurve": equity_curve,
        "algoBreakdown": algo_breakdown,
        "trades": trades,
        "reconciliation": recon_stats
    }

def extract_row_data(clean_row):
    """
    Intelligently extracts trade data from a dictionary row,
    matching any Dhan, Zerodha, Groww, or broker column header variation.
    """
    # 1. Symbol
    sym = ""
    for k, v in clean_row.items():
        if any(term in k for term in ['scrip', 'symbol', 'contract', 'instrument', 'security', 'description', 'stock', 'underlying']):
            val = str(v).strip()
            if val and val.lower() != 'nan' and not val.lower().startswith('total') and len(val) > 1:
                sym = val
                break

    # 2. Side (BUY or SELL)
    side = ""
    for k, v in clean_row.items():
        if any(term in k for term in ['buysell', 'tradetype', 'side', 'action', 'transactiontype', 'order', 'bs', 'type']):
            val = str(v).strip().upper()
            if val in ['BUY', 'B', 'LONG'] or val.startswith('BUY'):
                side = 'BUY'
                break
            elif val in ['SELL', 'S', 'SHORT'] or val.startswith('SELL'):
                side = 'SELL'
                break

    if not side:
        # Check any cell in row that is exactly 'BUY' or 'SELL' or 'B' or 'S'
        for v in clean_row.values():
            val = str(v).strip().upper()
            if val in ['BUY', 'B']:
                side = 'BUY'
                break
            elif val in ['SELL', 'S']:
                side = 'SELL'
                break

    # 3. Quantity
    qty = 0.0
    for k, v in clean_row.items():
        if any(term in k for term in ['qty', 'quantity', 'tradedqty', 'filledqty', 'volume', 'shares', 'units']):
            try:
                num = float(re.sub(r'[^\d.]', '', str(v)) or 0)
                if num > 0:
                    qty = num
                    break
            except Exception:
                pass

    # 4. Price
    price = 0.0
    for k, v in clean_row.items():
        if any(term in k for term in ['tradeprice', 'rate', 'price', 'avgprice', 'fillprice', 'avgcost', 'tradeavg']):
            if 'order' in k and any('trade' in ok for ok in clean_row.keys()):
                continue  # Prefer executed trade price over order limit price
            try:
                num = float(re.sub(r'[^\d.]', '', str(v)) or 0)
                if num > 0:
                    price = num
                    break
            except Exception:
                pass

    # 5. Date & Time
    dt = None
    date_str = ""
    time_str = ""
    for k, v in clean_row.items():
        if any(term in k for term in ['tradedatetime', 'orderdatetime', 'executiondatetime', 'datetime', 'timestamp']):
            dt = parse_date_time(str(v), "")
            if dt:
                break
        if not date_str and any(term in k for term in ['tradedate', 'date', 'orderdate', 'transactiondate', 'activitydate']):
            date_str = str(v).strip()
        if not time_str and any(term in k for term in ['tradetime', 'time', 'ordertime', 'executiontime']):
            time_str = str(v).strip()

    if not dt:
        dt = parse_date_time(date_str, time_str)

    # 6. Order Tag / Algo
    tag = ""
    for k, v in clean_row.items():
        if any(term in k for term in ['tag', 'remark', 'algo', 'strategy']):
            val = str(v).strip()
            if val and val.lower() != 'nan':
                tag = val
                break

    # 7. Check if PnL is directly reported (Dhan Global P&L / Tax report format)
    pnl = None
    for k, v in clean_row.items():
        if any(term in k for term in ['realizedpnl', 'realisedpnl', 'netpnl', 'realizedprofit', 'realisedprofit', 'grosspnl', 'pnl', 'profitloss']):
            try:
                pnl = float(re.sub(r'[^\d.-]', '', str(v)) or 0)
                break
            except Exception:
                pass

    return {
        "symbol": sym,
        "side": side,
        "qty": qty,
        "price": price,
        "dt": dt,
        "tag": tag,
        "pnl": pnl,
        "raw": clean_row
    }


def process_extracted_records(all_records, session_cookie=None):
    """Takes normalized extracted records and computes roundtrip FIFO trades."""
    raw_executions = []
    direct_pnl_records = []

    for rec in all_records:
        sym = rec['symbol']
        pnl = rec.get('pnl')
        clean_row = rec.get('raw', {})

        # Check if direct PnL format row (e.g. Dhan Global P&L)
        has_pnl_markers = ('buyqty' in clean_row or 'buyvalue' in clean_row or 'realizedpnl' in clean_row or 'realisedpnl' in clean_row)
        if pnl is not None and has_pnl_markers:
            underlying, opt_type = infer_underlying(sym)
            qty = rec.get('qty') or 1.0
            dt = rec.get('dt') or datetime.now()
            dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            date_str = dt.strftime("%Y-%m-%d")
            direct_pnl_records.append({
                "id": f"P&L-{len(direct_pnl_records)+1:04d}",
                "symbol": sym,
                "underlying": underlying,
                "optType": opt_type,
                "algoTag": rec.get('tag') or f"{underlying} Strategy",
                "direction": "CLOSED",
                "qty": qty,
                "entryTime": dt_str,
                "exitTime": dt_str,
                "exitDate": date_str,
                "entryPrice": rec.get('price') or 0.0,
                "exitPrice": rec.get('price') or 0.0,
                "grossPnl": pnl,
                "charges": 40.0,
                "netPnl": round(pnl - 40.0, 2),
                "returnPct": 0.0,
                "durationMin": 60,
                "isWin": pnl > 0
            })
            continue

        # Standard execution row
        side = rec.get('side', '')
        qty = rec.get('qty', 0.0)
        price = rec.get('price', 0.0)
        dt = rec.get('dt') or datetime.now()
        tag = rec.get('tag', '')

        if sym and side and qty > 0 and price > 0:
            raw_executions.append({
                "symbol": sym,
                "side": side,
                "qty": qty,
                "price": price,
                "dt": dt,
                "tag": tag,
                "order_id": str(clean_row.get('orderid', '') or clean_row.get('orderno', ''))
            })

    if direct_pnl_records and len(direct_pnl_records) >= len(raw_executions):
        return compute_dhan_analytics(direct_pnl_records, session_cookie=session_cookie)

    closed = process_trades_fifo(raw_executions)
    return compute_dhan_analytics(closed, session_cookie=session_cookie)


def parse_dhan_csv(csv_content, session_cookie=None):
    """
    Parses Dhan tradebook CSV or Dhan P&L report CSV content.
    Handles multiple delimiters and any column header casing.
    """
    if isinstance(csv_content, bytes):
        csv_content = csv_content.decode('utf-8-sig', errors='replace')

    sample = csv_content[:2048]
    delimiter = ','
    if '\t' in sample and sample.count('\t') > sample.count(','):
        delimiter = '\t'
    elif ';' in sample and sample.count(';') > sample.count(','):
        delimiter = ';'

    reader = csv.DictReader(io.StringIO(csv_content), delimiter=delimiter)
    all_records = []

    for row in reader:
        clean_row = {clean_key(k): str(v).strip() for k, v in row.items() if k is not None}
        extracted = extract_row_data(clean_row)
        if extracted['symbol']:
            all_records.append(extracted)

    return process_extracted_records(all_records, session_cookie=session_cookie)


def parse_excel_workbook(file_bytes, filename="", session_cookie=None):
    """
    Scans ALL sheets in the Excel workbook to find trades across sheets (F&O, Equity, etc.)
    and handles Dhan's typical 'Summary' + 'F&O' workbook layout.
    """
    import pandas as pd
    bio = io.BytesIO(file_bytes)
    try:
        xl = pd.ExcelFile(bio)
    except Exception:
        bio.seek(0)
        xl = pd.ExcelFile(bio, engine='openpyxl')

    all_records = []

    # Priority for sheet order: F&O, Derivatives, Trades, Trade History, Equity, etc.
    priority_order = []
    for s in xl.sheet_names:
        sl = s.lower()
        if any(p in sl for p in ['f&o', 'fo', 'derivative', 'future', 'trade', 'history', 'equity']):
            priority_order.append(s)
    for s in xl.sheet_names:
        if s not in priority_order:
            priority_order.append(s)

    for sheet_name in priority_order:
        try:
            df_sample = xl.parse(sheet_name, nrows=25, header=None)
            if df_sample.empty:
                continue

            header_idx = 0
            keywords = {'symbol', 'scrip', 'instrument', 'security', 'buysell', 'type', 'qty', 'quantity', 'price', 'rate', 'tradedate', 'date', 'pnl', 'contract', 'trade'}
            for idx, r in df_sample.iterrows():
                row_words = {clean_key(cell) for cell in r.dropna() if str(cell).strip()}
                match_count = sum(1 for kw in keywords if any(kw in rw for rw in row_words))
                if match_count >= 2:
                    header_idx = idx
                    break

            df = xl.parse(sheet_name, skiprows=header_idx)
            df = df.dropna(how='all')
            if df.empty or len(df.columns) < 2:
                continue

            for _, row_series in df.iterrows():
                clean_row = {}
                for k, v in row_series.items():
                    if pd.notna(v) and str(v).strip():
                        clean_row[clean_key(k)] = v

                extracted = extract_row_data(clean_row)
                if extracted['symbol']:
                    all_records.append(extracted)
        except Exception:
            pass

    return process_extracted_records(all_records, session_cookie=session_cookie)


def parse_dhan_file(file_content, filename="", session_cookie=None):
    """
    Unified entry point for Dhan tradebooks: .csv, .tsv, .txt, .xlsx, or .xls
    """
    is_excel = False
    name_lower = (filename or '').lower()
    if name_lower.endswith(('.xlsx', '.xls', '.xlsm', '.xlsb')):
        is_excel = True
    elif isinstance(file_content, bytes):
        if file_content.startswith(b'PK\x03\x04') or file_content.startswith(b'\xd0\xcf\x11\xe0'):
            is_excel = True

    if is_excel:
        raw_bytes = file_content if isinstance(file_content, bytes) else file_content.encode('latin1')
        return parse_excel_workbook(raw_bytes, filename=filename, session_cookie=session_cookie)
    else:
        return parse_dhan_csv(file_content, session_cookie=session_cookie)


def generate_demo_trades():
    """
    Generates a realistic 1-month dataset for 3 active Stratzy algos on Dhan:
    1. Algo 1: Nifty Momentum Buyer (Option Buying) - Highly profitable
    2. Algo 2: BankNifty Weekly Strangle (Option Selling) - Consistent income
    3. Algo 3: FinNifty Zero-Hero Scalper (Option Buying) - Lagging with high slippage
    """
    trades = []
    base_date = datetime.now() - timedelta(days=30)
    
    # 1. Nifty Momentum Option Buyer (22 trades)
    # Win rate ~50%, High Reward:Risk
    nifty_trades_spec = [
        ("NIFTY 24500 CE", True, 75, 115.0, 168.0, 45, 1),
        ("NIFTY 24600 PE", False, 75, 95.0, 68.0, 30, 2),
        ("NIFTY 24700 CE", True, 75, 140.0, 215.0, 80, 3),
        ("NIFTY 24650 CE", True, 75, 88.0, 142.0, 55, 4),
        ("NIFTY 24800 PE", False, 75, 110.0, 82.0, 25, 5),
        ("NIFTY 24850 CE", True, 75, 130.0, 195.0, 90, 8),
        ("NIFTY 24900 PE", False, 75, 125.0, 95.0, 40, 9),
        ("NIFTY 25000 CE", True, 75, 92.0, 155.0, 65, 10),
        ("NIFTY 24950 CE", False, 75, 105.0, 78.0, 20, 11),
        ("NIFTY 25100 CE", True, 75, 115.0, 185.0, 110, 12),
        ("NIFTY 25050 PE", True, 75, 85.0, 138.0, 50, 15),
        ("NIFTY 25150 CE", False, 75, 145.0, 115.0, 35, 16),
        ("NIFTY 25200 CE", True, 75, 98.0, 162.0, 75, 17),
        ("NIFTY 25100 PE", False, 75, 130.0, 98.0, 30, 18),
        ("NIFTY 25250 CE", True, 75, 112.0, 178.0, 85, 19),
        ("NIFTY 25300 PE", False, 75, 90.0, 65.0, 25, 22),
        ("NIFTY 25350 CE", True, 75, 120.0, 190.0, 70, 23),
        ("NIFTY 25200 PE", True, 75, 105.0, 165.0, 60, 24),
        ("NIFTY 25400 CE", False, 75, 135.0, 105.0, 40, 25),
        ("NIFTY 25450 CE", True, 75, 88.0, 145.0, 50, 26),
        ("NIFTY 25350 PE", False, 75, 115.0, 85.0, 30, 29),
        ("NIFTY 25500 CE", True, 75, 125.0, 205.0, 95, 30),
    ]

    trade_id = 1
    for sym, is_win, qty, entry_p, exit_p, duration, day_offset in nifty_trades_spec:
        trade_dt = base_date + timedelta(days=day_offset, hours=9, minutes=30)
        exit_dt = trade_dt + timedelta(minutes=duration)
        gross = (exit_p - entry_p) * qty
        charges = calculate_charges(qty * entry_p, qty * exit_p, True)
        net = round(gross - charges, 2)
        trades.append({
            "id": f"TRD-{trade_id:04d}",
            "symbol": sym,
            "underlying": "NIFTY",
            "optType": "CE" if "CE" in sym else "PE",
            "algoTag": "Nifty Momentum Buyer (Stratzy)",
            "direction": "LONG",
            "qty": qty,
            "entryTime": trade_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "exitTime": exit_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "exitDate": exit_dt.strftime("%Y-%m-%d"),
            "entryPrice": entry_p,
            "exitPrice": exit_p,
            "grossPnl": round(gross, 2),
            "charges": charges,
            "netPnl": net,
            "returnPct": round((net / (entry_p * qty)) * 100, 2),
            "durationMin": duration,
            "isWin": net > 0,
        })
        trade_id += 1

    # 2. BankNifty Weekly Strangle (14 trades) - Option Selling / Theta Decay
    # High win rate ~71%, smaller consistent gains, shorting
    bn_trades_spec = [
        ("BANKNIFTY 51500 CE", True, 30, 185.0, 92.0, 360, 2),
        ("BANKNIFTY 50800 PE", True, 30, 160.0, 75.0, 360, 2),
        ("BANKNIFTY 51800 CE", True, 30, 195.0, 110.0, 360, 4),
        ("BANKNIFTY 51000 PE", False, 30, 150.0, 220.0, 210, 5),
        ("BANKNIFTY 52000 CE", True, 30, 175.0, 85.0, 360, 9),
        ("BANKNIFTY 51200 PE", True, 30, 140.0, 68.0, 360, 9),
        ("BANKNIFTY 52200 CE", True, 30, 180.0, 95.0, 360, 11),
        ("BANKNIFTY 51500 PE", True, 30, 165.0, 80.0, 360, 12),
        ("BANKNIFTY 52500 CE", False, 30, 190.0, 290.0, 180, 16),
        ("BANKNIFTY 51800 PE", True, 30, 170.0, 88.0, 360, 18),
        ("BANKNIFTY 52800 CE", True, 30, 160.0, 72.0, 360, 23),
        ("BANKNIFTY 52000 PE", True, 30, 155.0, 65.0, 360, 24),
        ("BANKNIFTY 53000 CE", True, 30, 185.0, 98.0, 360, 25),
        ("BANKNIFTY 52200 PE", False, 30, 145.0, 240.0, 240, 29),
    ]

    for sym, is_win, qty, entry_p, exit_p, duration, day_offset in bn_trades_spec:
        trade_dt = base_date + timedelta(days=day_offset, hours=9, minutes=20)
        exit_dt = trade_dt + timedelta(minutes=duration)
        gross = (entry_p - exit_p) * qty  # Short selling
        charges = calculate_charges(qty * exit_p, qty * entry_p, True)
        net = round(gross - charges, 2)
        trades.append({
            "id": f"TRD-{trade_id:04d}",
            "symbol": sym,
            "underlying": "BANKNIFTY",
            "optType": "CE" if "CE" in sym else "PE",
            "algoTag": "BankNifty Short Strangle (Stratzy)",
            "direction": "SHORT",
            "qty": qty,
            "entryTime": trade_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "exitTime": exit_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "exitDate": exit_dt.strftime("%Y-%m-%d"),
            "entryPrice": entry_p,
            "exitPrice": exit_p,
            "grossPnl": round(gross, 2),
            "charges": charges,
            "netPnl": net,
            "returnPct": round((net / (entry_p * qty)) * 100, 2),
            "durationMin": duration,
            "isWin": net > 0,
        })
        trade_id += 1

    # 3. FinNifty Zero-Hero Scalper (16 trades) - Underperforming / High Slippage
    # Win rate ~31%, heavy decay and stop-outs
    fn_trades_spec = [
        ("FINNIFTY 23500 CE", False, 65, 45.0, 28.0, 30, 1),
        ("FINNIFTY 23400 PE", False, 65, 52.0, 32.0, 25, 3),
        ("FINNIFTY 23600 CE", True, 65, 38.0, 78.0, 45, 6),
        ("FINNIFTY 23550 PE", False, 65, 48.0, 30.0, 20, 8),
        ("FINNIFTY 23700 CE", False, 65, 40.0, 22.0, 15, 10),
        ("FINNIFTY 23650 PE", False, 65, 55.0, 35.0, 35, 13),
        ("FINNIFTY 23800 CE", True, 65, 35.0, 82.0, 50, 15),
        ("FINNIFTY 23750 PE", False, 65, 60.0, 40.0, 25, 17),
        ("FINNIFTY 23900 CE", False, 65, 42.0, 26.0, 20, 20),
        ("FINNIFTY 23850 PE", True, 65, 50.0, 95.0, 40, 21),
        ("FINNIFTY 24000 CE", False, 65, 38.0, 20.0, 18, 22),
        ("FINNIFTY 23950 PE", False, 65, 58.0, 38.0, 30, 24),
        ("FINNIFTY 24100 CE", True, 65, 32.0, 74.0, 45, 27),
        ("FINNIFTY 24050 PE", False, 65, 62.0, 42.0, 25, 28),
        ("FINNIFTY 24200 CE", False, 65, 45.0, 25.0, 20, 29),
        ("FINNIFTY 24150 PE", True, 65, 48.0, 88.0, 55, 30),
    ]

    for sym, is_win, qty, entry_p, exit_p, duration, day_offset in fn_trades_spec:
        trade_dt = base_date + timedelta(days=day_offset, hours=13, minutes=15)
        exit_dt = trade_dt + timedelta(minutes=duration)
        gross = (exit_p - entry_p) * qty
        charges = calculate_charges(qty * entry_p, qty * exit_p, True)
        net = round(gross - charges, 2)
        trades.append({
            "id": f"TRD-{trade_id:04d}",
            "symbol": sym,
            "underlying": "FINNIFTY",
            "optType": "CE" if "CE" in sym else "PE",
            "algoTag": "FinNifty Zero-Hero (Stratzy)",
            "direction": "LONG",
            "qty": qty,
            "entryTime": trade_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "exitTime": exit_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "exitDate": exit_dt.strftime("%Y-%m-%d"),
            "entryPrice": entry_p,
            "exitPrice": exit_p,
            "grossPnl": round(gross, 2),
            "charges": charges,
            "netPnl": net,
            "returnPct": round((net / (entry_p * qty)) * 100, 2),
            "durationMin": duration,
            "isWin": net > 0,
        })
        trade_id += 1

    return compute_dhan_analytics(trades)

def _dhan_list(response_json):
    """
    Dhan API v2 sometimes returns data as a bare JSON array [],
    and sometimes wrapped as {"data": [...]}. Handle both.
    """
    if isinstance(response_json, list):
        return response_json
    if isinstance(response_json, dict):
        return response_json.get("data", [])
    return []


def _dhan_time(tr):
    """
    Extract the best available timestamp from a Dhan trade record.
    createTime is 'NA' in historical records; fall through to exchangeTime.
    """
    create = str(tr.get("createTime") or "").strip()
    if create and create.upper() != "NA":
        return create
    exchange = str(tr.get("exchangeTime") or "").strip()
    if exchange and exchange.upper() != "NA":
        # Strip the T separator so parse_date_time can handle it
        return exchange.replace("T", " ")
    return ""


def _normalize_symbol(tr):
    """
    Builds a canonical contract symbol across Dhan today tradebook and historical tradebook.
    Dhan history uses customSymbol like 'NIFTY 19 OCT 23000 CALL',
    today's trade book uses tradingSymbol like 'NIFTY-Oct2026-22700-CE'.
    Both contain drvExpiryDate, drvOptionType, drvStrikePrice.
    Matching them to a canonical string ensures positions opened yesterday
    and closed today pair seamlessly into single completed trades.
    """
    raw_s = str(tr.get("tradingSymbol") or tr.get("customSymbol") or "").strip()
    raw_u = raw_s.upper()

    und = "NIFTY" if "NIFTY" in raw_u and "BANK" not in raw_u else ("BANKNIFTY" if "BANK" in raw_u else "FINNIFTY")
    exp = str(tr.get("drvExpiryDate") or "")
    drv_ot = str(tr.get("drvOptionType") or "").upper()
    ot = "CE" if drv_ot in ["CALL", "CE"] or "CE" in raw_u else "PE"
    st = int(float(tr.get("drvStrikePrice") or 0))

    if st == 0 or not exp:
        try:
            from stratzy_reconciler import normalize_sym_info
            u, parsed_st, parsed_ot = normalize_sym_info(raw_s)
            if parsed_st > 0:
                st = parsed_st
            if parsed_ot:
                ot = parsed_ot
        except Exception:
            pass

    if st > 0 and exp:
        return f"{und} {exp} {st} {ot}"
    elif st > 0:
        return f"{und} {st} {ot}"

    return raw_s.replace(" CALL", " CE").replace(" PUT", " PE")


def fetch_dhan_api_data(client_id, access_token, from_date=None, to_date=None, session_cookie=None):
    """
    Connects to DhanHQ API v2 and pulls trade history via the paginated
    /v2/trades/{from-date}/{to-date}/{page} endpoint for the requested date range,
    plus today's trade book and positions as fallback.
    """
    headers = {
        "access-token": access_token.strip(),
        "client-id": client_id.strip(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # 1. Test connection with fundlimit
    try:
        r_fund = requests.get("https://api.dhan.co/v2/fundlimit", headers=headers, timeout=10)
        if r_fund.status_code not in [200, 201]:
            return {"success": False, "message": f"Dhan auth failed: HTTP {r_fund.status_code}. Please verify Client ID and Access Token."}
        raw_fund = r_fund.json()
        fund_data = raw_fund.get("data", raw_fund) if isinstance(raw_fund, dict) else {}
    except Exception as e:
        return {"success": False, "message": f"Connection error: {str(e)}"}

    # 2. Determine and validate date range
    now = datetime.now()
    try:
        if to_date and str(to_date).strip():
            dt_to = datetime.strptime(str(to_date).strip()[:10], "%Y-%m-%d")
        else:
            dt_to = now

        if from_date and str(from_date).strip():
            dt_from = datetime.strptime(str(from_date).strip()[:10], "%Y-%m-%d")
        else:
            dt_from = dt_to - timedelta(days=30)

        if dt_from > dt_to:
            dt_from, dt_to = dt_to, dt_from
    except Exception:
        dt_to = now
        dt_from = now - timedelta(days=30)

    from_date_str = dt_from.strftime("%Y-%m-%d")
    to_date_str = dt_to.strftime("%Y-%m-%d")

    # Dhan v2 allows up to 90 days per query range; split into <= 90 day chunks if needed
    chunks = []
    chunk_start = dt_from
    while chunk_start <= dt_to:
        chunk_end = min(chunk_start + timedelta(days=89), dt_to)
        chunks.append((chunk_start.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        chunk_start = chunk_end + timedelta(days=1)

    trades_data = []
    seen_exec_keys = set()

    for c_from, c_to in chunks:
        page = 0
        max_pages = 50  # Safety cap (~1000 trades per 90-day chunk at 20/page)
        while page < max_pages:
            url = f"https://api.dhan.co/v2/trades/{c_from}/{c_to}/{page}"
            try:
                r_hist = requests.get(url, headers=headers, timeout=15)
                if r_hist.status_code not in [200, 201]:
                    break
                page_data = _dhan_list(r_hist.json())
                if not page_data:
                    break
                for t in page_data:
                    key = (
                        str(t.get("exchangeTradeId") or t.get("orderId") or ""),
                        str(t.get("exchangeTime") or t.get("createTime") or ""),
                        str(t.get("tradedQuantity") or t.get("quantity") or ""),
                        str(t.get("tradedPrice") or t.get("price") or ""),
                        str(t.get("transactionType") or "")
                    )
                    if key != ("", "", "", "", "") and key in seen_exec_keys:
                        continue
                    if key != ("", "", "", "", ""):
                        seen_exec_keys.add(key)
                    trades_data.append(t)
                page += 1
            except Exception:
                break

    # 3. If to_date is today or later, also fetch today's live trade book (intraday trades not yet in history)
    if dt_to.date() >= now.date():
        try:
            r_trades = requests.get("https://api.dhan.co/v2/trades", headers=headers, timeout=10)
            if r_trades.status_code in [200, 201]:
                today_trades = _dhan_list(r_trades.json())
                for t in today_trades:
                    key = (
                        str(t.get("exchangeTradeId") or t.get("orderId") or ""),
                        str(t.get("exchangeTime") or t.get("createTime") or ""),
                        str(t.get("tradedQuantity") or t.get("quantity") or ""),
                        str(t.get("tradedPrice") or t.get("price") or ""),
                        str(t.get("transactionType") or "")
                    )
                    if key == ("", "", "", "", "") or key not in seen_exec_keys:
                        if key != ("", "", "", "", ""):
                            seen_exec_keys.add(key)
                        trades_data.append(t)
        except Exception:
            pass

    # 4. Fetch positions (for realized P&L fallback)
    positions_data = []
    try:
        r_pos = requests.get("https://api.dhan.co/v2/positions", headers=headers, timeout=10)
        if r_pos.status_code in [200, 201]:
            positions_data = _dhan_list(r_pos.json())
    except Exception:
        pass

    raw_execs = []
    for tr in trades_data:
        sym = _normalize_symbol(tr)          # handles CALL/PUT→CE/PE
        side = tr.get("transactionType", "").upper()
        qty = float(tr.get("tradedQuantity") or tr.get("quantity") or 0)
        price = float(tr.get("tradedPrice") or tr.get("price") or 0)
        time_str = _dhan_time(tr)             # skips createTime='NA', uses exchangeTime
        dt = parse_date_time("", time_str)
        tag = tr.get("orderTag") or tr.get("drvAlgoId") or ""
        if sym and side in ("BUY", "SELL") and qty > 0 and price > 0:
            raw_execs.append({
                "symbol": sym,
                "side": side,
                "qty": qty,
                "price": price,
                "dt": dt,
                "tag": tag,
                "order_id": str(tr.get("orderId", ""))
            })

    if raw_execs:
        closed = process_trades_fifo(raw_execs, live_positions=positions_data)
        analytics = compute_dhan_analytics(closed, session_cookie=session_cookie)
    else:
        # Fall back to positions if no trade executions returned
        pos_records = []
        for p in positions_data:
            sym = p.get("tradingSymbol", "")
            pnl = float(p.get("realizedProfit") or 0)
            underlying, opt_type = infer_underlying(sym)
            pos_records.append({
                "id": f"POS-{len(pos_records)+1:04d}",
                "symbol": sym,
                "underlying": underlying,
                "optType": opt_type,
                "algoTag": f"{underlying} Strategy",
                "direction": "CLOSED",
                "qty": float(p.get("buyQty") or p.get("sellQty") or 1),
                "entryTime": datetime.now().strftime("%Y-%m-%d"),
                "exitTime": datetime.now().strftime("%Y-%m-%d"),
                "exitDate": datetime.now().strftime("%Y-%m-%d"),
                "entryPrice": float(p.get("buyAvg") or 0),
                "exitPrice": float(p.get("sellAvg") or 0),
                "grossPnl": pnl,
                "charges": 40.0,
                "netPnl": round(pnl - 40.0, 2),
                "returnPct": 0.0,
                "durationMin": 60,
                "isWin": pnl > 0
            })
        analytics = compute_dhan_analytics(pos_records, session_cookie=session_cookie)

    analytics["fromDate"] = from_date_str
    analytics["toDate"] = to_date_str

    return {
        "success": True,
        "message": "Connected to DhanHQ successfully",
        "fundLimit": fund_data,
        "analytics": analytics,
        "fromDate": from_date_str,
        "toDate": to_date_str,
        "rawPositionsCount": len(positions_data),
        "rawTradesCount": len(trades_data)
    }
