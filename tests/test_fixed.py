import pandas as pd
import pytest

from sample.fixed import Config, backtest, indicators, metrics


def frame(closes, opens=None, lows=None):
    opens = opens or closes
    lows = lows or [min(c, o) for c, o in zip(closes, opens)]
    return pd.DataFrame({"date":pd.date_range("2024-01-01", periods=len(closes)).strftime("%Y-%m-%d"),
                         "open":opens, "high":[max(c,o)*1.01 for c,o in zip(closes,opens)],
                         "low":lows, "close":closes, "volume":[1]*len(closes)})


def test_close_signal_fills_next_open_not_same_close():
    bars = frame([3, 2, 1, 2, 4, 5], [3, 2, 1, 2, 10, 10])
    cfg = Config(fast=2, slow=3, fee=0, slippage=0)
    equity, _ = backtest(bars, cfg)
    # The crossover is confirmed on day 4; the large next open is the entry.
    assert equity.quantity.iloc[4] == 0
    assert equity.quantity.iloc[5] == 1000


def test_future_bars_cannot_change_past_signal_values():
    cfg = Config(fast=2, slow=3)
    original = frame([3, 2, 1, 2, 4, 5])
    extended = frame([3, 2, 1, 2, 4, 5, 100, 1])
    a, b = indicators(original, cfg), indicators(extended, cfg)
    expected = [False, False, False, False, True, False]
    assert a.entry.tolist() == expected
    assert b.entry.iloc[:len(a)].tolist() == expected


def test_warmup_bars_are_not_tradeable():
    out = indicators(frame([10, 9, 8, 7, 6]), Config(fast=2, slow=4))
    assert not out.ready.iloc[:4].any()
    assert out.ready.iloc[4]
    eq, trades = backtest(frame([10, 9, 8, 7, 6]), Config(fast=2, slow=4))
    assert not (eq.quantity.iloc[:4] != 0).any()
    assert len(trades) == 0


def test_stop_uses_intraday_low_even_when_close_recovers():
    bars = frame([3, 2, 1, 2, 4, 10, 10], lows=[3,2,1,2,4,10,8])
    cfg = Config(fast=2, slow=3, stop_pct=.1, fee=0, slippage=0)
    _, trades = backtest(bars, cfg)
    stopped = trades[trades.exit_reason == "stop"]
    assert len(stopped) == 1
    assert stopped.iloc[0].exit_price == 9


def test_gap_through_stop_fills_at_open_not_stop():
    bars = frame([3, 2, 1, 2, 4, 10, 10], opens=[3,2,1,2,4,10,8], lows=[3,2,1,2,4,10,7])
    cfg = Config(fast=2, slow=3, stop_pct=.1, fee=0, slippage=0)
    _, trades = backtest(bars, cfg)
    stopped = trades[trades.exit_reason == "stop"]
    assert len(stopped) == 1
    assert stopped.iloc[0].exit_price == 8


def test_fee_reduces_equity_after_entry():
    bars = frame([3, 2, 1, 2, 4, 5])
    cfg = Config(fast=2, slow=3, fee=.01, slippage=0)
    equity, _ = backtest(bars, cfg)
    assert equity.equity.iloc[5] == pytest.approx(9_900.990099, rel=1e-8)


def test_adverse_entry_slippage_reduces_equity_by_hand_calculated_amount():
    bars = frame([3, 2, 1, 2, 4, 5])
    cfg = Config(fast=2, slow=3, fee=0, slippage=.01)
    equity, _ = backtest(bars, cfg)
    # Signal follows close 4; next open is 5, slipped entry is 5.05.
    assert equity.equity.iloc[5] == pytest.approx(10_000 * 5 / 5.05, rel=1e-10)


def test_metrics_compound_simple_returns_and_use_calendar_days():
    equity = pd.DataFrame({"date":["2023-01-01", "2023-07-02", "2024-01-01"], "equity":[10_000, 11_000, 9_900]})
    m = metrics(equity, pd.DataFrame())
    assert m["total_return"] == pytest.approx(-0.01)
    assert m["annualized_return"] == pytest.approx(-0.01)
