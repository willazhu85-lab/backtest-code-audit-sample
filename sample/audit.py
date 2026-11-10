"""Small auditable checks for daily OHLCV data."""
from __future__ import annotations

import pandas as pd


def audit_bars(bars: pd.DataFrame) -> list[dict[str, str]]:
    """Return one record per detected data issue; never silently repairs data."""
    issues: list[dict[str, str]] = []
    required = {"date", "open", "high", "low", "close", "volume"}
    missing = sorted(required - set(bars.columns))
    if missing:
        return [{"type": "missing_columns", "date": "", "detail": ", ".join(missing)}]
    dates = pd.to_datetime(bars.date, errors="coerce", utc=True)
    for idx in bars.index[dates.isna()]:
        issues.append({"type": "invalid_date", "date": str(bars.loc[idx, "date"]), "detail": "date cannot be parsed"})
    valid_dates = dates.dropna()
    duplicates = valid_dates[valid_dates.duplicated(keep=False)]
    for idx in duplicates.index:
        issues.append({"type": "duplicate_candle", "date": str(bars.loc[idx, "date"]), "detail": "more than one row for date"})
    unique = pd.Series(valid_dates.unique()).sort_values().reset_index(drop=True)
    for left, right in zip(unique.iloc[:-1], unique.iloc[1:]):
        delta = right - left
        if delta > pd.Timedelta(days=1):
            days_missing = int(delta / pd.Timedelta(days=1)) - 1
            issues.append({"type": "missing_date", "date": (left + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                           "detail": f"{days_missing} calendar day(s) missing before {right.strftime('%Y-%m-%d')}"})
    values = bars[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    for idx, row in values.iterrows():
        date = str(bars.loc[idx, "date"])
        if (row <= 0).any() or pd.to_numeric(bars.loc[idx, "volume"], errors="coerce") < 0:
            issues.append({"type": "nonpositive_price", "date": date, "detail": "prices must be positive and volume nonnegative"})
        if not (row.low <= min(row.open, row.close) <= max(row.open, row.close) <= row.high):
            issues.append({"type": "invalid_ohlc", "date": date, "detail": "expected low <= open/close <= high"})
    return issues


def clean_bars(bars: pd.DataFrame) -> pd.DataFrame:
    """Stable de-duplication for demonstration; date gaps remain visible in audit."""
    out = bars.copy()
    out["date"] = pd.to_datetime(out.date, errors="raise").dt.strftime("%Y-%m-%d")
    return out.sort_values("date").drop_duplicates("date", keep="first").reset_index(drop=True)
