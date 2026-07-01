"""
Technical Indicators & Strategy Backtesting Dashboard
FINM 25000 HW2

Run with:
    streamlit run backtest_app.py
"""

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_loader import load_daily_bars, DEFAULT_TICKERS
from indicators import add_all_indicators
from strategies import STRATEGIES
from backtest import Backtester
from metrics import metrics_table

st.set_page_config(page_title="Strategy Backtester", layout="wide")
st.title("Technical Indicators & Strategy Backtesting")

# --------------------------------------------------------------------------
# Sidebar controls
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("Settings")
    ticker_choice = st.selectbox("Ticker", DEFAULT_TICKERS + ["Custom..."], index=0)
    if ticker_choice == "Custom...":
        symbol = st.text_input("Custom ticker", value="AAPL").strip().upper()
    else:
        symbol = ticker_choice

    years = st.slider("Years of history", min_value=5, max_value=15, value=5)
    initial_capital = st.number_input("Initial capital ($)", value=100_000, step=10_000)
    commission_bps = st.slider("Commission per trade (bps)", 0, 50, 0)
    risk_free_rate = st.number_input("Risk-free rate (annual, for Sharpe/Sortino)", value=0.02, step=0.005, format="%.3f")
    run_clicked = st.button("Run Backtest", use_container_width=True)

state_key = f"{symbol}-{years}-{initial_capital}-{commission_bps}"

# --------------------------------------------------------------------------
# Load data + run backtests
# --------------------------------------------------------------------------
if run_clicked or st.session_state.get("state_key") != state_key:
    with st.spinner(f"Downloading {years}y of daily bars for {symbol}..."):
        try:
            raw = load_daily_bars(symbol, years=years)
            df = add_all_indicators(raw)

            results = {}
            for name, strategy_fn in STRATEGIES.items():
                sig_df = strategy_fn(df)
                bt = Backtester(sig_df, initial_capital=initial_capital, commission_bps=commission_bps)
                bt.run()
                results[name] = {
                    "df": bt.results,
                    "daily_returns": bt.results["Daily_Return"],
                    "portfolio_value": bt.results["Portfolio_Value"],
                    "trades": bt.trades,
                }

            bh = Backtester.buy_and_hold(df, initial_capital=initial_capital)
            results["Buy & Hold"] = {
                "df": bh,
                "daily_returns": bh["Daily_Return"],
                "portfolio_value": bh["Portfolio_Value"],
                "trades": None,
            }

            st.session_state["price_df"] = df
            st.session_state["results"] = results
            st.session_state["symbol"] = symbol
            st.session_state["state_key"] = state_key
        except Exception as e:
            st.session_state["results"] = None
            st.error(f"Failed to run backtest: {e}")

results = st.session_state.get("results")
price_df = st.session_state.get("price_df")

if not results:
    st.info("Configure settings in the sidebar and click **Run Backtest**.")
    st.stop()

symbol = st.session_state["symbol"]

# --------------------------------------------------------------------------
# 1. Price chart with indicators + buy/sell markers
# --------------------------------------------------------------------------
st.subheader(f"{symbol} — Price, Indicators & Signals")
overlay_strategy = st.selectbox("Show buy/sell signals for:", list(STRATEGIES.keys()))
sig_df = results[overlay_strategy]["df"]

fig = make_subplots(
    rows=3, cols=1, shared_xaxes=True, row_heights=[0.55, 0.2, 0.25],
    vertical_spacing=0.03,
    subplot_titles=(f"{symbol} Price + EMA/Bollinger", "RSI (14)", "MACD"),
)

fig.add_trace(go.Candlestick(
    x=sig_df.index, open=sig_df["Open"], high=sig_df["High"],
    low=sig_df["Low"], close=sig_df["Close"], name=symbol,
), row=1, col=1)
fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["EMA_20"], name="EMA 20", line=dict(width=1)), row=1, col=1)
fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["EMA_50"], name="EMA 50", line=dict(width=1)), row=1, col=1)
fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["BB_Upper"], name="BB Upper", line=dict(width=1, dash="dot")), row=1, col=1)
fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["BB_Lower"], name="BB Lower", line=dict(width=1, dash="dot")), row=1, col=1)

buys = sig_df[sig_df["Buy_Marker"]]
sells = sig_df[sig_df["Sell_Marker"]]
fig.add_trace(go.Scatter(x=buys.index, y=buys["Close"], mode="markers", name="Buy",
                          marker=dict(symbol="triangle-up", size=10, color="green")), row=1, col=1)
fig.add_trace(go.Scatter(x=sells.index, y=sells["Close"], mode="markers", name="Sell",
                          marker=dict(symbol="triangle-down", size=10, color="red")), row=1, col=1)

fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["RSI"], name="RSI"), row=2, col=1)
fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["MACD"], name="MACD"), row=3, col=1)
fig.add_trace(go.Scatter(x=sig_df.index, y=sig_df["MACD_Signal"], name="Signal"), row=3, col=1)

fig.update_layout(height=800, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=40, b=10))
st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------------------------------
# 2. Equity curve comparison
# --------------------------------------------------------------------------
st.subheader("Equity Curve: Buy & Hold vs. Strategies")
eq_fig = go.Figure()
for name, r in results.items():
    eq_fig.add_trace(go.Scatter(x=r["portfolio_value"].index, y=r["portfolio_value"], name=name))
eq_fig.update_layout(height=450, yaxis_title="Portfolio Value ($)", margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(eq_fig, use_container_width=True)

# --------------------------------------------------------------------------
# 3. Drawdown comparison
# --------------------------------------------------------------------------
st.subheader("Drawdown Comparison")
dd_fig = go.Figure()
for name, r in results.items():
    dd = r["df"]["Drawdown"] if "Drawdown" in r["df"].columns else (r["portfolio_value"] / r["portfolio_value"].cummax() - 1)
    dd_fig.add_trace(go.Scatter(x=dd.index, y=dd * 100, name=name, fill="tozeroy"))
dd_fig.update_layout(height=400, yaxis_title="Drawdown (%)", margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(dd_fig, use_container_width=True)

# --------------------------------------------------------------------------
# 4. Performance metrics table
# --------------------------------------------------------------------------
st.subheader("Performance Metrics (Risk-Adjusted Comparison)")
table = metrics_table(results, risk_free_rate=risk_free_rate)

display_table = table.copy()
for col in ["Total Return", "CAGR", "Volatility (ann.)", "Max Drawdown", "Win Rate"]:
    display_table[col] = display_table[col].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "—")
for col in ["Sharpe Ratio", "Sortino Ratio"]:
    display_table[col] = display_table[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
display_table["# Trades"] = display_table["# Trades"].apply(lambda x: "—" if pd.isna(x) else int(x))

st.dataframe(display_table, use_container_width=True)

best_by_sharpe = table["Sharpe Ratio"].idxmax()
st.success(f"**Best risk-adjusted performer (by Sharpe Ratio): {best_by_sharpe}** "
           f"(Sharpe = {table.loc[best_by_sharpe, 'Sharpe Ratio']:.2f})")

with st.expander("Show trade logs"):
    for name, r in results.items():
        if r["trades"] is not None and not r["trades"].empty:
            st.markdown(f"**{name}** — {len(r['trades'])} trades")
            st.dataframe(r["trades"], use_container_width=True)
