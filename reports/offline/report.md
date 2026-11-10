# Backtest code audit (offline)

Demonstration only. Historical results are not predictive. Data source: bundled altered offline CSV; 300 input rows, 299 unique dates (2025-12-01 to 2026-09-26).

## Headline comparison

| Version | Total return | Max drawdown | Sharpe | Trades |
|---|---:|---:|---:|---:|
| Flawed equity, correctly measured | 21.98% | -16.82% | 1.002 | 7 |
| Corrected | 8.72% | -18.46% | 0.537 | 6 |
| Flawed example's self-reported metrics | 23.04% | -16.82% | 0.833 | 7 |

The first two rows use the same correct `sample.fixed.metrics` function. The third row is the flawed script's own report for its unchanged flawed equity curve; the gap illustrates reporting defects, not a change in simulated performance.

## Simulation-defect ablations

Each row reruns the intentionally flawed engine with exactly that simulation defect disabled. All metrics use the correct `sample.fixed.metrics` function; effects interact, so changes are not additive. The `data` correction removes duplicate dates; the missing day is reported and deliberately not fabricated.

| Simulation defect corrected alone | Return | Max drawdown | Sharpe | Trades |
|---|---:|---:|---:|---:|
| `costs` | 19.27% | -17.82% | 0.909 | 7 |
| `data` | 21.98% | -16.82% | 1.002 | 7 |
| `lookahead` | 3.13% | -19.44% | 0.273 | 7 |
| `same_close` | 21.98% | -16.82% | 1.002 | 7 |
| `stop` | 23.04% | -16.10% | 1.041 | 7 |
| `warmup` | 23.08% | -16.73% | 1.094 | 6 |

## Reporting-defect comparison

This keeps the flawed equity curve and trade list fixed and compares its self-reported statistics to the correct metrics function. `returns` sums daily simple returns instead of compounding; `calendar` annualizes daily data with 252 instead of 365 periods. These defects change reported numbers only, never the equity curve.

| Same flawed equity curve | Total return | Annualized return | Sharpe |
|---|---:|---:|---:|
| Correct metrics (`sample.fixed.metrics`) | 21.98% | 27.45% | 1.002 |
| Flawed reporting algorithm | 23.04% | 19.03% | 0.833 |
## Data audit

- `duplicate_candle` at 2026-04-30: more than one row for date
- `duplicate_candle` at 2026-04-30: more than one row for date
- `missing_date` at 2026-03-11: 1 calendar day(s) missing before 2026-03-12

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
