#FINM-25000-Homework-1


A small trading terminal built on Alpaca's Market Data API. It pulls historical OHLCV bars, polls live bid/ask quotes, and displays everything in a Streamlit UI. Built for FINM-25000 Homework 1.

![Mini Market Data Terminal](screenshots/terminal.png)

## Setup

This project uses [Poetry](https://python-poetry.org/) for dependency management.

1. Clone the repo and install dependencies:

```
git clone https://github.com/awujira29/FINM-25000-Homework-1
cd FINM-25000-Homework-1
poetry install
```

2. Get your Alpaca paper keys. Log in at https://app.alpaca.markets, switch to a Paper account in the top-left, and generate an API key from the Home dashboard. Copy both the Key ID and the Secret (the secret is shown only once).

3. Create a `.env` file in the project root from the template:

```
cp .env.example .env
```

Then fill in your values:

```
ALPACA_API_KEY=your_key_id_here
ALPACA_SECRET_KEY=your_secret_key_here
```

Each teammate uses their own keys. The `.env` file is gitignored and should never be committed.

## Running it

```
poetry run streamlit run app.py
```

## HW2: Technical Indicators & Strategy Backtesting

Built on top of the HW1 connector, this adds a full backtesting platform:

| File | Purpose |
|---|---|
| `data_loader.py` | Pulls 5+ years of daily OHLCV bars for a chosen ticker from Alpaca |
| `indicators.py` | 8 indicators: SMA, EMA, MACD, ADX (trend) · RSI (momentum) · Bollinger Bands, ATR (volatility) · OBV (volume) |
| `strategies.py` | Strategy 1 (Trend Following: MACD+ADX), Strategy 2 (Mean Reversion: RSI+Bollinger), Strategy 3 (Custom: EMA cross + RSI filter + OBV volume confirmation) |
| `backtest.py` | Long-only, no-leverage `Backtester` engine. $100k initial capital, lookahead-safe (signals lag one day), optional commission, trade log, buy & hold benchmark |
| `metrics.py` | Total Return, CAGR, annualized Volatility, Sharpe, Sortino, Max Drawdown, Win Rate |
| `backtest_app.py` | Streamlit dashboard: price/indicator chart with buy/sell markers, equity curve comparison, drawdown comparison, metrics table |
| `test_backtesting.py` | Unit tests against synthetic OHLCV data (no Alpaca credentials needed) |

Run the dashboard:

```
poetry run streamlit run backtest_app.py
```

Run the tests:

```
poetry run pytest test_backtesting.py -v
```

**Design notes**
- No lookahead bias: a strategy's signal for day T is only acted on starting day T+1 inside `Backtester.run()`.
- Long-only / no leverage: position is always 0 or 1 (fully in cash or fully invested); no shorting, no margin.
- The custom strategy deliberately spans three indicator categories (trend, momentum, volume) rather than stacking two indicators from the same category.
- The dashboard surfaces the best strategy by **Sharpe Ratio** (risk-adjusted), not raw return.

## Screenshots

![Real-time quotes](screenshots/quotes.png)

![Historical candlestick chart](screenshots/chart.png)

![Raw OHLCV table](screenshots/ohlcv-table.png)
