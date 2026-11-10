"""Offline fixture loading and strict public Binance daily candle download."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

BASE_URL = "https://api.binance.com/api/v3/klines"
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
        "trade_count", "taker_buy_base", "taker_buy_quote", "ignore"]


def load_offline(path: Path) -> pd.DataFrame:
    bars = pd.read_csv(path)
    needed = {"date", "open", "high", "low", "close", "volume"}
    if bars.empty or not needed.issubset(bars.columns):
        raise ValueError(f"CSV must contain rows and columns: {sorted(needed)}")
    return bars


def fetch_binance() -> pd.DataFrame:
    start = int(pd.Timestamp("2021-01-01", tz="UTC").timestamp() * 1000)
    rows = []
    while True:
        query = urlencode({"symbol": "BTCUSDT", "interval": "1d", "startTime": start, "limit": 1000})
        req = Request(f"{BASE_URL}?{query}", headers={"User-Agent": "backtest-audit-sample/1.0"})
        with urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected Binance response: {payload}")
        if not payload:
            break
        rows.extend(payload)
        if len(payload) < 1000:
            break
        start = int(payload[-1][0]) + 86_400_000
    if not rows:
        raise RuntimeError("Binance returned no candles")
    raw = pd.DataFrame(rows, columns=COLS)
    dates = [datetime.fromtimestamp(int(x) / 1000, tz=timezone.utc).strftime("%Y-%m-%d") for x in raw.open_time]
    out = pd.DataFrame({"date": dates, **{c: pd.to_numeric(raw[c]) for c in ["open", "high", "low", "close", "volume"]}})
    return out.sort_values("date").drop_duplicates("date").reset_index(drop=True)
