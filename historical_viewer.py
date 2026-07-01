import matplotlib as plt
import pandas as pd
import mplfinance as mpf
import datetime
import connector

def bars_to_dataframe(bars):
    df = pd.DataFrame(bars)
    df["t"] = pd.to_datetime(df["t"])
    df = df.set_index("t")
    df_new = df.rename(columns={"o": "Open", "h": "High", "l": "Low",
                            "c": "Close", "v": "Volume"})
    
    return df_new

def plot_bars(df, symbol):
    mpf.plot(
        df,
        type="candle",
        volume=True,
        title=f"{symbol} - 5 Min Bars",
        style="charles",
    )

if __name__ == "__main__":
    bars = connector.get_bars("AAPL", "5Min")
    df = bars_to_dataframe(bars)
    plot_bars(df, "AAPL")