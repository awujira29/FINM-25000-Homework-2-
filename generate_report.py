"""
generate_report.py
Runs the full backtest for a chosen ticker and writes the required
Final Report PDF (FINM 25000 HW2).

The PDF contains:
  1. Title + strategy descriptions + entry/exit rules
  2. Performance comparison table (Buy & Hold vs the three strategies)
  3. Equity curve comparison
  4. Drawdown comparison
  5. Price chart with indicators + buy/sell signals (one strategy)
  6. Discussion of results (auto-seeded with the computed numbers; edit as you like)

Run:
    poetry run python generate_report.py --symbol AAPL --years 5
"""

import argparse

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from data_loader import load_daily_bars
from indicators import add_all_indicators
from strategies import STRATEGIES
from backtest import Backtester
from metrics import metrics_table


# --------------------------------------------------------------------------
# Static narrative text (edit the discussion at the bottom after you see
# your own numbers)
# --------------------------------------------------------------------------

STRATEGY_DESCRIPTIONS = """\
STRATEGY DESCRIPTIONS & RULES

Strategy 1 — Trend Following (MACD + ADX)
  Idea: ride established trends; only act when a real trend is present.
  Buy / hold long when:  MACD > Signal line  AND  ADX > 25
  Exit to flat when:     MACD < Signal line
  ADX acts as a filter so MACD crossovers in choppy, trendless markets
  are ignored.

Strategy 2 — Mean Reversion (RSI + Bollinger Bands)
  Idea: fade extremes; buy when price is stretched down, sell when
  stretched up.
  Buy when:   RSI < 30  AND  Close < lower Bollinger Band
  Sell when:  RSI > 70  OR   Close > upper Bollinger Band

Strategy 3 — Custom "Confirmed Trend" (EMA + RSI + OBV)
  Combines three indicator categories: trend, momentum, and volume.
  Buy when:   EMA(20) > EMA(50)  AND  RSI < 70  AND  OBV > OBV's 20-day SMA
  Sell when:  EMA(20) < EMA(50)  OR   RSI > 80
  Only takes the trend trade when it is not already overheated (RSI) and
  when volume flow confirms buying pressure (OBV).

Benchmark — Buy & Hold
  Buy on day one, hold the whole period. The bar every active strategy
  must beat on a risk-adjusted basis.

Backtest assumptions: $100,000 initial capital, long-only, no leverage,
no shorting. Signals are traded on the next day's close to avoid
lookahead bias.
"""


def run_all(symbol: str, years: int, initial_capital: float,
            commission_bps: float, risk_free_rate: float):
    """Load data, run every strategy + buy & hold, return a results dict."""
    raw = load_daily_bars(symbol, years=years)
    df = add_all_indicators(raw)

    results = {}

    # Buy & Hold first so it heads the table.
    bh = Backtester.buy_and_hold(df, initial_capital=initial_capital)
    results["Buy & Hold"] = {
        "df": bh,
        "daily_returns": bh["Daily_Return"],
        "portfolio_value": bh["Portfolio_Value"],
        "trades": None,
    }

    for name, strategy_fn in STRATEGIES.items():
        sig_df = strategy_fn(df)
        bt = Backtester(sig_df, initial_capital=initial_capital,
                        commission_bps=commission_bps)
        bt.run()
        results[name] = {
            "df": bt.results,
            "daily_returns": bt.results["Daily_Return"],
            "portfolio_value": bt.results["Portfolio_Value"],
            "trades": bt.trades,
        }

    table = metrics_table(results, risk_free_rate=risk_free_rate)
    return df, results, table


# --------------------------------------------------------------------------
# PDF page builders
# --------------------------------------------------------------------------

def text_page(pdf, title, body):
    fig = plt.figure(figsize=(8.5, 11))
    fig.text(0.08, 0.94, title, fontsize=16, fontweight="bold", va="top")
    fig.text(0.08, 0.88, body, fontsize=9.5, va="top", family="monospace")
    pdf.savefig(fig)
    plt.close(fig)


def title_page(pdf, symbol, years):
    fig = plt.figure(figsize=(8.5, 11))
    fig.text(0.5, 0.62, "Technical Indicators &\nStrategy Backtesting",
             fontsize=24, fontweight="bold", ha="center", va="center")
    fig.text(0.5, 0.48, f"Ticker: {symbol}   |   {years} years of daily data",
             fontsize=13, ha="center")
    fig.text(0.5, 0.43, "FINM 25000 — Homework 2", fontsize=12, ha="center",
             color="gray")
    pdf.savefig(fig)
    plt.close(fig)


def table_page(pdf, table):
    fig, ax = plt.subplots(figsize=(11, 8.5))  # landscape
    ax.axis("off")
    ax.set_title("Performance Comparison", fontsize=16, fontweight="bold",
                 pad=20)

    pct_cols = ["Total Return", "CAGR", "Volatility (ann.)",
                "Max Drawdown", "Win Rate"]
    ratio_cols = ["Sharpe Ratio", "Sortino Ratio"]

    disp = table.copy()
    for col in pct_cols:
        if col in disp.columns:
            disp[col] = disp[col].apply(
                lambda x: f"{x:.2%}" if x == x else "—")  # x==x skips NaN
    for col in ratio_cols:
        if col in disp.columns:
            disp[col] = disp[col].apply(
                lambda x: f"{x:.2f}" if x == x else "—")
    if "# Trades" in disp.columns:
        disp["# Trades"] = disp["# Trades"].apply(
            lambda x: "—" if x != x else str(int(x)))

    tbl = ax.table(cellText=disp.values,
                   rowLabels=disp.index,
                   colLabels=disp.columns,
                   loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(0.8, 1.6)
    pdf.savefig(fig)
    plt.close(fig)


def equity_curve_page(pdf, results):
    fig, ax = plt.subplots(figsize=(11, 8.5))
    for name, r in results.items():
        ax.plot(r["portfolio_value"].index, r["portfolio_value"], label=name)
    ax.set_title("Equity Curve: Buy & Hold vs. Strategies",
                 fontsize=16, fontweight="bold")
    ax.set_ylabel("Portfolio Value ($)")
    ax.legend()
    ax.grid(alpha=0.3)
    pdf.savefig(fig)
    plt.close(fig)


def drawdown_page(pdf, results):
    fig, ax = plt.subplots(figsize=(11, 8.5))
    for name, r in results.items():
        dd = r["df"]["Drawdown"] * 100
        ax.plot(dd.index, dd, label=name)
    ax.set_title("Drawdown Comparison", fontsize=16, fontweight="bold")
    ax.set_ylabel("Drawdown (%)")
    ax.legend()
    ax.grid(alpha=0.3)
    pdf.savefig(fig)
    plt.close(fig)


def price_signals_page(pdf, results, symbol, strategy_name):
    r = results[strategy_name]
    d = r["df"]
    fig, ax = plt.subplots(figsize=(11, 8.5))
    ax.plot(d.index, d["Close"], color="black", linewidth=0.8, label="Close")
    if "EMA_20" in d:
        ax.plot(d.index, d["EMA_20"], linewidth=0.8, label="EMA 20", alpha=0.8)
    if "EMA_50" in d:
        ax.plot(d.index, d["EMA_50"], linewidth=0.8, label="EMA 50", alpha=0.8)

    if "Buy_Marker" in d:
        buys = d[d["Buy_Marker"]]
        ax.scatter(buys.index, buys["Close"], marker="^", color="green",
                   s=60, label="Buy", zorder=5)
    if "Sell_Marker" in d:
        sells = d[d["Sell_Marker"]]
        ax.scatter(sells.index, sells["Close"], marker="v", color="red",
                   s=60, label="Sell", zorder=5)

    ax.set_title(f"{symbol} — Price & Signals ({strategy_name})",
                 fontsize=16, fontweight="bold")
    ax.set_ylabel("Price ($)")
    ax.legend()
    ax.grid(alpha=0.3)
    pdf.savefig(fig)
    plt.close(fig)


def build_discussion(table):
    """Auto-seed a discussion paragraph from the computed metrics."""
    best_sharpe = table["Sharpe Ratio"].idxmax()
    best_return = table["Total Return"].idxmax()
    smallest_dd = table["Max Drawdown"].idxmax()  # closest to 0 = smallest

    lines = ["DISCUSSION OF RESULTS", ""]
    lines.append(
        f"On a risk-adjusted basis, {best_sharpe} had the highest Sharpe "
        f"ratio ({table.loc[best_sharpe, 'Sharpe Ratio']:.2f})."
    )
    lines.append(
        f"The highest total return came from {best_return} "
        f"({table.loc[best_return, 'Total Return']:.2%})."
    )
    lines.append(
        f"{smallest_dd} experienced the smallest maximum drawdown "
        f"({table.loc[smallest_dd, 'Max Drawdown']:.2%})."
    )
    lines.append("")
    lines.append(
        "Which strategy performs best depends on what you optimize for:\n"
        "raw return, risk-adjusted return (Sharpe/Sortino), or capital\n"
        "preservation (drawdown). A strategy can beat Buy & Hold on Sharpe\n"
        "while trailing it on total return if it sidesteps the worst\n"
        "drawdowns by moving to cash."
    )
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="AAPL")
    p.add_argument("--years", type=int, default=5)
    p.add_argument("--capital", type=float, default=100_000)
    p.add_argument("--commission_bps", type=float, default=0)
    p.add_argument("--risk_free_rate", type=float, default=0.02)
    p.add_argument("--out", default="report.pdf")
    args = p.parse_args()

    print(f"Running backtest for {args.symbol} ({args.years}y)...")
    df, results, table = run_all(
        args.symbol, args.years, args.capital,
        args.commission_bps, args.risk_free_rate,
    )

    print(f"Writing {args.out}...")
    with PdfPages(args.out) as pdf:
        title_page(pdf, args.symbol, args.years)
        text_page(pdf, "Strategies", STRATEGY_DESCRIPTIONS)
        table_page(pdf, table)
        equity_curve_page(pdf, results)
        drawdown_page(pdf, results)
        # Show signals for the custom strategy (has EMA markers); pick any.
        strat_to_plot = next(k for k in results if k != "Buy & Hold")
        price_signals_page(pdf, results, args.symbol, strat_to_plot)
        text_page(pdf, "Discussion", build_discussion(table))

    print("Done. Open", args.out)


if __name__ == "__main__":
    main()