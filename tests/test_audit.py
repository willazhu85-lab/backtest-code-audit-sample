import pandas as pd

from sample.audit import audit_bars
from sample.data import load_offline
from pathlib import Path


def test_fixture_contains_one_gap_and_duplicate_detectable():
    bars = load_offline(Path(__file__).parents[1] / "data/sample_btcusdt_1d.csv")
    issues = audit_bars(bars)
    assert sum(x["type"] == "missing_date" for x in issues) == 1
    # Both rows in the duplicated date are flagged; there is one duplicated date.
    assert len({x["date"] for x in issues if x["type"] == "duplicate_candle"}) == 1


def test_audit_flags_nonpositive_and_bad_ohlc():
    bars = pd.DataFrame([{"date":"2024-01-01", "open":-1, "high":2, "low":1, "close":3, "volume":1}])
    kinds = {x["type"] for x in audit_bars(bars)}
    assert {"nonpositive_price", "invalid_ohlc"} <= kinds
