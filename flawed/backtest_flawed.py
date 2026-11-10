"""INTENTIONALLY FLAWED customer example. Educational audit target only."""
from __future__ import annotations

import math
import pandas as pd

SIMULATION_DEFECTS = {"lookahead", "same_close", "costs", "stop", "warmup", "data"}
REPORT_DEFECTS = {"returns", "calendar"}
DEFECTS = SIMULATION_DEFECTS | REPORT_DEFECTS


def run(bars: pd.DataFrame, defects: set[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Toggle simulation and reporting defects for the audit demonstration."""
    bad = set(DEFECTS if defects is None else defects)
    df = bars.copy().reset_index(drop=True)
    if "data" not in bad:
        df = df.sort_values("date").drop_duplicates("date", keep="first").reset_index(drop=True)
    fast = df.close.ewm(span=10, adjust=False, min_periods=(1 if "warmup" in bad else 10)).mean()
    slow = df.close.ewm(span=30, adjust=False, min_periods=(1 if "warmup" in bad else 30)).mean()
    cross = (fast > slow) & (fast.shift(1) <= slow.shift(1))
    cross_down = (fast < slow) & (fast.shift(1) >= slow.shift(1))
    if "lookahead" in bad:
        # BUG: shift(-1) imports tomorrow's crossing into today's decision.
        signal = cross | cross.shift(-1, fill_value=False)
    else:
        signal = cross
    cash, qty, entry, stop = 10_000.0, 0.0, None, None
    curve, trades, pending = [], [], None
    for i, row in df.iterrows():
        close, opn, low = float(row.close), float(row.open), float(row.low)
        if pending == "buy" and qty == 0:
            px = opn * (1.0005 if "costs" not in bad else 1)
            qty = cash / (px * (1.001 if "costs" not in bad else 1))
            fee = qty * px * (.001 if "costs" not in bad else 0)
            cash -= qty * px + fee
            entry, stop, entry_date, pending = px, px * .94, row.date, None
        elif pending == "sell" and qty > 0:
            px = opn * (.9995 if "costs" not in bad else 1)
            fee = qty * px * (.001 if "costs" not in bad else 0)
            cash += qty * px - fee
            trades.append({"entry_date": entry_date, "exit_date": row.date, "entry_price": entry,
                           "exit_price": px, "quantity": qty, "exit_reason": "cross"})
            qty, entry, stop, pending = 0.0, None, None, None
        if qty > 0 and entry is not None and str(entry_date) != str(row.date):
            # BUG: checks close only, missing intrabar low and gap-through fill.
            if (close <= stop if "stop" in bad else low <= stop or opn <= stop):
                px = close if "stop" in bad else min(stop, opn)
                if "costs" not in bad:
                    px *= .9995
                fee = 0 if "costs" in bad else qty * px * .001
                cash += qty * px - fee
                trades.append({"entry_date": entry_date, "exit_date": row.date, "entry_price": entry,
                               "exit_price": px, "quantity": qty, "exit_reason": "stop"})
                qty, entry, stop = 0.0, None, None
        if qty == 0 and bool(signal.iloc[i]) and i + 1 < len(df):
            if "same_close" in bad:
                # BUG: a close-derived signal is executed on that same close.
                px = close
                if "costs" not in bad:
                    px *= 1.0005
                qty = cash / (px * (1.001 if "costs" not in bad else 1))
                fee = qty * px * (.001 if "costs" not in bad else 0)
                cash -= qty * px + fee
                entry, stop, entry_date = px, px * .94, row.date
            else:
                pending = "buy"
        elif qty > 0 and bool(cross_down.iloc[i]) and i + 1 < len(df):
            if "same_close" in bad:
                px = close * (.9995 if "costs" not in bad else 1)
                fee = qty * px * (.001 if "costs" not in bad else 0)
                cash += qty * px - fee
                trades.append({"entry_date": entry_date, "exit_date": row.date, "entry_price": entry,
                               "exit_price": px, "quantity": qty, "exit_reason": "cross"})
                qty, entry, stop = 0.0, None, None
            else:
                pending = "sell"
        curve.append({"date": row.date, "equity": cash + qty * close})
    eq = pd.DataFrame(curve)
    v = eq.equity.astype(float)
    daily = v.pct_change().dropna()
    if "returns" in bad:
        total = float(daily.sum())
    else:
        total = float(v.iloc[-1] / 10_000 - 1)
    period = 252 if "calendar" in bad else 365
    years = max(len(v) / period, 1 / period)
    annual = float((1 + total) ** (1 / years) - 1) if total > -1 else -1.0
    dd = v / v.cummax() - 1
    vol = daily.std(ddof=1)
    sharpe = float(daily.mean() / vol * math.sqrt(period)) if len(daily) > 1 and vol else 0.0
    eq.attrs["metrics"] = {"total_return": total, "annualized_return": annual, "max_drawdown": float(dd.min()),
                           "sharpe": sharpe, "trade_count": len(trades), "final_equity": float(v.iloc[-1])}
    # BUG: duplicate candles and missing calendar dates are accepted without audit.
    return eq, pd.DataFrame(trades)
