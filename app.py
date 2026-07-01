"""
Mini Market Data Terminal - UI
FINM 25000 HW1

Run with:
    streamlit run app.py
"""

import time
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

import connector

st.set_page_config(page_title="Mini Market Data Terminal", layout="wide")
st.title("Mini Market Data Terminal")


def bars_to_df(bars):
    df = pd.DataFrame(bars)
    if df.empty:
        return df
    df["t"] = pd.to_datetime(df["t"], utc=True)
    df["t"] = df["t"].dt.tz_convert("America/New_York")
    df = df.set_index("t")
    df = df.rename(columns={
        "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"
    })
    return df


def plot_candles(df, symbol):
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        name=symbol,
    )])
    fig.update_layout(
        title=f"{symbol} — Historical Bars",
        xaxis_rangeslider_visible=False,
        height=450,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    fig.update_xaxes(
        rangebreaks=[
            dict(bounds=["sat", "mon"]),              # hide weekends
            dict(bounds=[16, 9.5], pattern="hour"),   # hide 4pm–9:30am overnight
        ]
    )
    return fig


with st.sidebar:
    st.header("Settings")
    symbol = st.text_input("Ticker", value="AAPL").strip().upper()
    timeframe = st.selectbox("Bar size", ["1Min", "5Min"], index=1)
    days = st.slider("Days of history", min_value=5, max_value=60, value=30)
    refresh_secs = st.slider("Quote refresh (sec)", min_value=1, max_value=10, value=2)
    load_clicked = st.button("Load / Reload Historical Data", use_container_width=True)
    st.divider()
    streaming = st.toggle("Live quotes ON", value=False)

hist_key = f"{symbol}-{timeframe}-{days}"
if load_clicked or st.session_state.get("hist_key") != hist_key:
    with st.spinner(f"Downloading {days}d of {timeframe} bars for {symbol}..."):
        try:
            bars = connector.get_bars(symbol, timeframe=timeframe, days=days)
            st.session_state["hist_df"] = bars_to_df(bars)
            st.session_state["hist_key"] = hist_key
        except Exception as e:
            st.session_state["hist_df"] = None
            st.error(f"Failed to load historical data: {e}")

st.subheader("Historical Data")
hist_df = st.session_state.get("hist_df")
if hist_df is not None and not hist_df.empty:
    st.plotly_chart(plot_candles(hist_df, symbol), use_container_width=True)
    with st.expander("Show raw OHLCV table"):
        st.dataframe(hist_df.tail(50), use_container_width=True)
else:
    st.info("Click 'Load / Reload Historical Data' in the sidebar to fetch bars.")

st.divider()

st.subheader("Real-Time Quote")

col1, col2, col3 = st.columns(3)
bid_box = col1.empty()
ask_box = col2.empty()
last_box = col3.empty()
status_box = st.empty()


def render_quote(bid, ask, last):
    bid_box.metric("Bid", f"${bid:,.2f}" if bid is not None else "—")
    ask_box.metric("Ask", f"${ask:,.2f}" if ask is not None else "—")
    last_box.metric("Last Trade", f"${last:,.2f}" if last is not None else "—")


def fetch_quote_and_trade(sym):
    quote = connector.get_latest_quote(sym)
    trade = connector.get_latest_trade(sym)
    return quote["bid"], quote["ask"], trade["price"]


if not streaming:
    try:
        bid, ask, last = fetch_quote_and_trade(symbol)
        render_quote(bid, ask, last)
        status_box.caption("Live quotes are OFF. Toggle the switch in the sidebar to start streaming.")
    except Exception as e:
        render_quote(None, None, None)
        status_box.error(f"Could not fetch quote: {e}")
else:
    status_box.caption(f"🔴 Live — refreshing every {refresh_secs}s. Toggle off to stop.")
    error_count = 0
    while True:
        try:
            bid, ask, last = fetch_quote_and_trade(symbol)
            render_quote(bid, ask, last)
            error_count = 0
        except Exception as e:
            error_count += 1
            status_box.error(f"Quote fetch failed ({error_count}): {e}")
            if error_count >= 5:
                status_box.error("Too many consecutive errors — stopping. Toggle 'Live quotes' off/on to retry.")
                break
        time.sleep(refresh_secs)
