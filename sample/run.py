"""Generate reproducible offline or public-Binance audit reports."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

from flawed.backtest_flawed import REPORT_DEFECTS, SIMULATION_DEFECTS, run as run_flawed
from sample.audit import audit_bars, clean_bars
from sample.data import fetch_binance, load_offline
from sample.fixed import Config, backtest, metrics

ROOT = Path(__file__).resolve().parents[1]


def flawed_run(bars: pd.DataFrame, defects: set[str]):
    return run_flawed(bars, defects)


def correct_stats_for_curve(eq: pd.DataFrame, trades: pd.DataFrame, initial_cash: float) -> dict:
    return metrics(eq, trades, initial_cash)


def fmt(x, percent=False):
    return f"{x:.2%}" if percent else f"{x:.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    mode = "offline" if args.offline else "online"
    output = ROOT / "reports" / mode
    output.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(output / ".mplconfig")
    os.environ["XDG_CACHE_HOME"] = str(output / ".cache")
    raw = load_offline(ROOT / "data/sample_btcusdt_1d.csv") if args.offline else fetch_binance()
    issues = audit_bars(raw)
    bars = clean_bars(raw)
    cfg = Config()
    eq, trades = backtest(bars, cfg)
    fixed_stats = metrics(eq, trades, cfg.initial_cash)
    flawed_eq, flawed_trades = flawed_run(raw, set(SIMULATION_DEFECTS) | set(REPORT_DEFECTS))
    flawed_correct_stats = correct_stats_for_curve(flawed_eq, flawed_trades, cfg.initial_cash)
    flawed_report_stats = flawed_eq.attrs["metrics"]
    ablations = []
    for defect in sorted(SIMULATION_DEFECTS):
        ab_eq, ab_trades = flawed_run(raw, set(REPORT_DEFECTS) | (SIMULATION_DEFECTS - {defect}))
        s = correct_stats_for_curve(ab_eq, ab_trades, cfg.initial_cash)
        ablations.append((defect, s))
    eq.to_csv(output / "equity.csv", index=False)
    trades.to_csv(output / "trades.csv", index=False)
    pd.DataFrame(issues).to_csv(output / "data_issues.csv", index=False)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    dates = pd.to_datetime(eq.date)
    buy_hold = cfg.initial_cash * bars.close.astype(float) / float(bars.close.iloc[0])
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.plot(dates, eq.equity, label="Corrected strategy")
    ax.plot(dates, buy_hold, label="Buy and hold", alpha=.65)
    ax.set(title=f"BTCUSDT daily audit demonstration ({mode})", ylabel="Equity (USDT)")
    ax.grid(alpha=.2); ax.legend(); fig.tight_layout(); fig.savefig(output / "equity.png", dpi=150); plt.close(fig)
    dd = eq.equity / eq.equity.cummax() - 1
    fig, ax = plt.subplots(figsize=(10, 2.8)); ax.fill_between(dates, dd, 0, color="firebrick", alpha=.45)
    ax.set(title="Corrected strategy drawdown", ylabel="Drawdown"); ax.grid(alpha=.2)
    fig.tight_layout(); fig.savefig(output / "drawdown.png", dpi=150); plt.close(fig)
    compare = "| Version | Total return | Max drawdown | Sharpe | Trades |\n|---|---:|---:|---:|---:|\n"
    for label, s in [("Flawed equity, correctly measured", flawed_correct_stats), ("Corrected", fixed_stats),
                     ("Flawed example's self-reported metrics", flawed_report_stats)]:
        compare += f"| {label} | {fmt(s['total_return'], True)} | {fmt(s['max_drawdown'], True)} | {fmt(s['sharpe'])} | {s['trade_count']} |\n"
    ab = "| Simulation defect corrected alone | Return | Max drawdown | Sharpe | Trades |\n|---|---:|---:|---:|---:|\n"
    for defect, s in ablations:
        ab += f"| `{defect}` | {fmt(s['total_return'], True)} | {fmt(s['max_drawdown'], True)} | {fmt(s['sharpe'])} | {s['trade_count']} |\n"
    issue_text = "\n".join(f"- `{x['type']}` at {x['date']}: {x['detail']}" for x in issues) or "- No data quality issues detected."
    report = f"""# Backtest code audit ({mode})

Demonstration only. Historical results are not predictive. Data source: {'bundled altered offline CSV' if args.offline else 'Binance public BTCUSDT 1d klines from 2021-01-01'}; {len(raw)} input rows, {len(bars)} unique dates ({bars.date.iloc[0]} to {bars.date.iloc[-1]}).

## Headline comparison

{compare}
The first two rows use the same correct `sample.fixed.metrics` function. The third row is the flawed script's own report for its unchanged flawed equity curve; the gap illustrates reporting defects, not a change in simulated performance.

## Simulation-defect ablations

Each row reruns the intentionally flawed engine with exactly that simulation defect disabled. All metrics use the correct `sample.fixed.metrics` function; effects interact, so changes are not additive. The `data` correction removes duplicate dates; the missing day is reported and deliberately not fabricated.

{ab}
## Reporting-defect comparison

This keeps the flawed equity curve and trade list fixed and compares its self-reported statistics to the correct metrics function. `returns` sums daily simple returns instead of compounding; `calendar` annualizes daily data with 252 instead of 365 periods. These defects change reported numbers only, never the equity curve.

| Same flawed equity curve | Total return | Annualized return | Sharpe |
|---|---:|---:|---:|
| Correct metrics (`sample.fixed.metrics`) | {fmt(flawed_correct_stats['total_return'], True)} | {fmt(flawed_correct_stats['annualized_return'], True)} | {fmt(flawed_correct_stats['sharpe'])} |
| Flawed reporting algorithm | {fmt(flawed_report_stats['total_return'], True)} | {fmt(flawed_report_stats['annualized_return'], True)} | {fmt(flawed_report_stats['sharpe'])} |
## Data audit

{issue_text}

## Findings and remediation

| Defect class | Location | Why it is wrong and effect | Correction |
|---|---|---|---|
| Simulation | `flawed/backtest_flawed.py:20-22` | `shift(-1)` reveals tomorrow's crossover and can enter early; the `lookahead` ablation quantifies the change. | Use only information available at the current close; queue an order for next open. |
| Simulation | `flawed/backtest_flawed.py:53-64` | Same-close fills on close-derived signals are unattainable. On BTC's 24/7 daily bars, next open is usually close to the prior close, so this sample shows little impact; stock daily bars can have large overnight gaps and the effect can be much larger. A hand-built test demonstrates the timing defect. | Queue the close signal and fill at the following bar's open. |
| Simulation | `flawed/backtest_flawed.py:30-38` | Commissions and adverse slippage are omitted, overstating fills/equity; see the `costs` ablation. | Charge entry and exit commission plus adverse slippage. |
| Simulation | `flawed/backtest_flawed.py:42-51` | Close-only stop logic misses intraday low touches and prices that gap through the stop. | Check low; if open is through stop fill at open, otherwise at stop, with sell slippage. |
| Simulation | `flawed/backtest_flawed.py:16-17` | `min_periods=1` admits signals before the 30-bar indicator window is ready. | Require both moving averages and their prior values to be available. |
| Reporting | `flawed/backtest_flawed.py:79-88` | Summing daily returns ignores compounding; 252 annualization periods misstates a 7-day crypto series. Neither changes the equity curve. Their metric distortion is isolated above. | Use equity ratio for cumulative return and 365 daily periods; CAGR uses elapsed calendar days. |
| Simulation (data) | Input `data/sample_btcusdt_1d.csv`; checks in `sample/audit.py` | A missing day and repeated candle can distort indicators and metrics. This small sample demonstrates a data-quality defect, not a claim of broad universe survivorship testing. | Audit before use; de-duplicate with a documented rule and never invent missing OHLC bars. A real survivorship audit requires delisted instruments and point-in-time universe membership. |

See `equity.png`, `drawdown.png`, `equity.csv`, `trades.csv`, and `data_issues.csv`. Simulation defects affect equity; reporting defects affect metrics only. The results are diagnostic demonstrations, not investment performance estimates.
"""
    (output / "report.md").write_text(report, encoding="utf-8")
    print(f"Mode: {mode}; input_rows: {len(raw)}; unique_dates: {len(bars)}; issues: {len(issues)}")
    print(f"Period: {bars.date.iloc[0]} to {bars.date.iloc[-1]}")
    print(f"Report: {output / 'report.md'}")
    print(f"Fixed total_return={fixed_stats['total_return']:.6f} max_drawdown={fixed_stats['max_drawdown']:.6f} sharpe={fixed_stats['sharpe']:.6f} trades={fixed_stats['trade_count']}")
    print(f"Flawed curve, correct metrics total_return={flawed_correct_stats['total_return']:.6f} max_drawdown={flawed_correct_stats['max_drawdown']:.6f} sharpe={flawed_correct_stats['sharpe']:.6f} trades={flawed_correct_stats['trade_count']}")
    print(f"Flawed self-reported total_return={flawed_report_stats['total_return']:.6f} max_drawdown={flawed_report_stats['max_drawdown']:.6f} sharpe={flawed_report_stats['sharpe']:.6f} trades={flawed_report_stats['trade_count']}")
    print("Data issue types:", ", ".join(sorted(set(x["type"] for x in issues))) or "none")


if __name__ == "__main__":
    main()
