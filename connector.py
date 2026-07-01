import os 
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

Base = "https://data.alpaca.markets/v2/stocks"

load_dotenv()

HEADERS = {
    "APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"],
    "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET_KEY"],
}

def get_bars(symbol, timeframe="5Min", days=30, feed='iex'):
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    params = {
        "symbols": symbol,
        "timeframe": timeframe,
        "start": start,
        "feed": feed,  
    }

    bars=[]
    page_token = None

    while True:
        if page_token:
            params["page_token"] = page_token

        r = requests.get(f"{Base}/bars", headers=HEADERS, params=params)
        r.raise_for_status()
        data = r.json()
        bars.extend(data.get("bars", {}).get(symbol, []))
        page_token = data.get("next_page_token")
        if not page_token:
            break
    return bars

def get_latest_quote(symbol, feed="iex"):
    r = requests.get(f"{Base}/{symbol}/quotes/latest", headers=HEADERS, 
                     params={"feed":feed})
    r.raise_for_status()
    data = r.json()
    quote= data["quote"]

    return {"bid": quote["bp"], "ask": quote["ap"]} 

def get_latest_trade(symbol, feed="iex"):
    r = requests.get(f"{Base}/{symbol}/trades/latest", headers=HEADERS, 
                     params={"feed":feed})
    r.raise_for_status()
    data = r.json()
    trade = data["trade"]

    return {"price": trade['p']}


if __name__ == "__main__":
    bars = get_bars('AAPL', '1Min')
    print(bars[0])
    print(bars[77])
