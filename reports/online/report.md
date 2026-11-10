# Backtest code audit (online)

Demonstration only. Historical results are not predictive. Data source: Binance public BTCUSDT 1d klines from 2021-01-01; 2140 input rows, 2140 unique dates (2021-01-01 to 2026-11-10).

## Headline comparison

| Version | Total return | Max drawdown | Sharpe | Trades |
|---|---:|---:|---:|---:|
| Flawed equity, correctly measured | 770.33% | -44.82% | 1.148 | 33 |
| Corrected | 442.26% | -40.00% | 0.986 | 32 |
| Flawed example's self-reported metrics | 259.83% | -44.82% | 0.954 | 33 |

The first two rows use the same correct `sample.fixed.metrics` function. The third row is the flawed script's own report for its unchanged flawed equity curve; the gap illustrates reporting defects, not a change in simulated performance.

## Simulation-defect ablations

Each row reruns the intentionally flawed engine with exactly that simulation defect disabled. All metrics use the correct `sample.fixed.metrics` function; effects interact, so changes are not additive. The `data` correction removes duplicate dates; the missing day is reported and deliberately not fabricated.

| Simulation defect corrected alone | Return | Max drawdown | Sharpe | Trades |
|---|---:|---:|---:|---:|
| `costs` | 688.30% | -45.97% | 1.103 | 33 |
| `data` | 770.33% | -44.82% | 1.148 | 33 |
| `lookahead` | 361.40% | -47.27% | 0.877 | 33 |
| `same_close` | 770.56% | -44.82% | 1.148 | 33 |
| `stop` | 948.13% | -37.31% | 1.240 | 33 |
| `warmup` | 691.47% | -44.82% | 1.139 | 32 |

## Reporting-defect comparison

This keeps the flawed equity curve and trade list fixed and compares its self-reported statistics to the correct metrics function. `returns` sums daily simple returns instead of compounding; `calendar` annualizes daily data with 252 instead of 365 periods. These defects change reported numbers only, never the equity curve.

| Same flawed equity curve | Total return | Annualized return | Sharpe |
|---|---:|---:|---:|
| Correct metrics (`sample.fixed.metrics`) | 770.33% | 44.66% | 1.148 |
| Flawed reporting algorithm | 259.83% | 16.27% | 0.954 |
## Data audit

- No data quality issues detected.

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
