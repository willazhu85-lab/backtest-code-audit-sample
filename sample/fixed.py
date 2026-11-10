"""A compact long-only daily-bar engine with explicit execution assumptions."""
from __future__ import annotations

from dataclasses import dataclass
import math
import pandas as pd


@dataclass(frozen=True)
class Config:
    fast: int = 10
    slow: int = 30
    stop_pct: float = 0.06
    fee: float = 0.001
    slippage: float = 0.0005
    initial_cash: float = 10_000.0


def indicators(bars: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    out = bars.copy()
    out["fast"] = out.close.ewm(span=cfg.fast, adjust=False, min_periods=cfg.fast).mean()
    out["slow"] = out.close.ewm(span=cfg.slow, adjust=False, min_periods=cfg.slow).mean()
    prior_fast, prior_slow = out.fast.shift(1), out.slow.shift(1)
    out["entry"] = (out.fast > out.slow) & (prior_fast <= prior_slow)
    out["exit"] = (out.fast < out.slow) & (prior_fast >= prior_slow)
    out["ready"] = out.fast.notna() & out.slow.notna() & prior_fast.notna() & prior_slow.notna()
    return out


def backtest(bars: pd.DataFrame, cfg: Config = Config()) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Signal at close, execute pending orders at next open; stop uses low and gap open."""
    df = indicators(bars, cfg).reset_index(drop=True)
    cash, qty, stop = cfg.initial_cash, 0.0, None
    pending = None
    trades: list[dict] = []
    curve: list[dict] = []
    active: dict | None = None
    for i, row in df.iterrows():
        date = str(row.date)
        if pending == "buy" and qty == 0:
            px = float(row.open) * (1 + cfg.slippage)
            qty = cash / (px * (1 + cfg.fee))
            fee = qty * px * cfg.fee
            cash -= qty * px + fee
            stop = px * (1 - cfg.stop_pct)
            active = {"entry_date": date, "entry_price": px, "quantity": qty, "entry_fee": fee}
            pending = None
        elif pending == "sell" and qty > 0:
            px = float(row.open) * (1 - cfg.slippage)
            fee = qty * px * cfg.fee
            cash += qty * px - fee
            trades.append({**active, "exit_date": date, "exit_price": px, "exit_fee": fee, "exit_reason": "crossunder"})
            qty, stop, active, pending = 0.0, None, None, None
        # Stop is active only after the entry bar. An opening gap fills at open.
        if qty > 0 and active and active["entry_date"] != date:
            if float(row.open) <= stop or float(row.low) <= stop:
                px = min(float(row.open), stop) * (1 - cfg.slippage)
                fee = qty * px * cfg.fee
                cash += qty * px - fee
                trades.append({**active, "exit_date": date, "exit_price": px, "exit_fee": fee, "exit_reason": "stop"})
                qty, stop, active, pending = 0.0, None, None, None
        if bool(row.ready):
            if qty == 0 and bool(row.entry) and i + 1 < len(df):
                pending = "buy"
            elif qty > 0 and bool(row.exit) and i + 1 < len(df):
                pending = "sell"
        curve.append({"date": date, "equity": cash + qty * float(row.close), "cash": cash, "quantity": qty})
    return pd.DataFrame(curve), pd.DataFrame(trades)


def metrics(equity: pd.DataFrame, trades: pd.DataFrame, initial_cash: float = 10_000.0) -> dict[str, float | int]:
    v = equity.equity.astype(float)
    daily = v.pct_change().dropna()
    total = float(v.iloc[-1] / initial_cash - 1)
    dates = pd.to_datetime(equity.date)
    elapsed_days = max(int((dates.iloc[-1] - dates.iloc[0]).days), 1)
    annual = float((v.iloc[-1] / initial_cash) ** (365 / elapsed_days) - 1) if v.iloc[-1] > 0 else -1.0
    dd = v / v.cummax() - 1
    vol = daily.std(ddof=1)
    sharpe = float(daily.mean() / vol * math.sqrt(365)) if len(daily) > 1 and vol else 0.0
    return {"total_return": total, "annualized_return": annual, "max_drawdown": float(dd.min()),
            "sharpe": sharpe, "trade_count": int(len(trades)), "final_equity": float(v.iloc[-1])}
