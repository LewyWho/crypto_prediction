def collect_last_candle():

    import json


    def collect_current_cryptocurrencies():
        import ccxt
        import time
        from datetime import datetime, timezone

        exchange = ccxt.bybit({
            "rateLimit": 1000,
            "enableRateLimit": True
        })

        crypto_pairs = [
            "BTC/USDT",
            "BNB/USDT",
            "DOGE/USDT",
            "ETH/USDT",
            "SOL/USDT",
            "XRP/USDT"
        ]

        result = {}

        for pair in crypto_pairs:
            try:
                ohlcv = exchange.fetch_ohlcv(pair, timeframe="1h", limit=1)
                if ohlcv:
                    candle = ohlcv[0]
                    result[pair] = {
                        "timestamp": datetime.fromtimestamp(candle[0] / 1000, timezone.utc),
                        "open": candle[1],
                        "high": candle[2],
                        "low": candle[3],
                        "close": candle[4],
                        "volume": candle[5]
                    }
                else:
                    pass
            except Exception as e:
                pass
            time.sleep(0.3)

        return result

    def collect_current_precious_metals():
        import yfinance as yf
        from datetime import datetime
        import pandas as pd

        assets = {
            "gold": "GC=F",
            "silver": "SI=F",
            "crude_oil": "CL=F",
            "wheat": "ZW=F",
            "corn": "ZC=F",
            "soybeans": "ZS=F",
            "cattle": "LE=F",
        }

        result = {}

        for name, ticker in assets.items():
            try:
                data = yf.download(ticker, period="7d", interval="1h", progress=False)
                if not data.empty:
                    last_row = data.iloc[-1]
                    result[name] = {
                        "timestamp": last_row.name.to_pydatetime(),
                        "open": last_row["Open"],
                        "high": last_row["High"],
                        "low": last_row["Low"],
                        "close": last_row["Close"],
                        "volume": last_row["Volume"]
                    }
                else:
                    pass
            except Exception as e:
                pass

        return result

    def collect_current_main_indexes():
        import yfinance as yf
        from datetime import datetime
        import pandas as pd

        indices = {
            "MOEX": "IMOEX.ME",
            "RTS": "RTSI.ME",
            "Dow_Jones": "^DJI",
            "S&P_500": "^GSPC",
            "NASDAQ": "^IXIC",
            "Russell_2000": "^RUT",
            "VIX": "^VIX",
            "S&P_TSX": "^GSPTSE",
            "IBOVESPA": "^BVSP",
            "IPC_Mexico": "^MXX",
            "DAX": "^GDAXI",
            "FTSE_100": "^FTSE",
            "CAC_40": "^FCHI",
            "EURO_STOXX_50": "^STOXX50E",
        }

        result = {}

        for name, ticker in indices.items():
            try:
                data = yf.download(ticker, period="7d", interval="1h", progress=False)
                if not data.empty:
                    last_row = data.iloc[-1]
                    result[name] = {
                        "timestamp": last_row.name.to_pydatetime(),
                        "open": last_row["Open"],
                        "high": last_row["High"],
                        "low": last_row["Low"],
                        "close": last_row["Close"],
                        "volume": last_row["Volume"]
                    }
                else:
                    pass
            except Exception as e:
                pass

        return result


    def fetch_current_funding_rate_btcusdt():
        import ccxt
        import time
        from datetime import datetime, timezone

        exchange = ccxt.bybit({"enableRateLimit": True})

        try:
            funding = exchange.fetch_funding_rate_history(
                symbol="BTCUSDT",
                limit=1,
                params={"category": "linear"}
            )

            if not funding:
                pass
                return None

            last = funding[0]
            return {
                "timestamp": datetime.fromtimestamp(last["timestamp"] / 1000, timezone.utc).replace(tzinfo=None),
                "funding_rate": last["fundingRate"]
            }

        except Exception as e:
            return None
        
    def fetch_fear_greed_index():
        import requests
        from datetime import datetime, timezone

        url = "https://api.alternative.me/fng/?limit=1&format=json"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()['data']
            
            result = []
            for item in data:
                timestamp = datetime.fromtimestamp(int(item['timestamp']), tz=timezone.utc).replace(tzinfo=None)
                result.append({
                    "Datetime": timestamp,
                    "Fear_Greed_Index": item['value']
                })
            
            return result
        else:
            return None

    def fetch_open_interest(symbol="BTCUSDT", interval="1h"):
        import ccxt
        import time
        from datetime import datetime, timezone

        exchange = ccxt.bybit({
            "enableRateLimit": True
        })


        now = datetime.now(timezone.utc)
        today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

        since = int(today_start.timestamp() * 1000)

        all_oi = []

        while since < exchange.milliseconds():
            try:
                data = exchange.fetch_open_interest_history(
                    symbol=symbol,
                    timeframe=interval,
                    since=since,
                    limit=200,
                    params={"category": "linear"}
                )

                if not data:
                    break

                for entry in data:
                    all_oi.append({
                        "timestamp": datetime.fromtimestamp(entry["timestamp"] / 1000, timezone.utc),
                        "open_interest": float(entry["openInterestValue"])
                    })

                since = data[-1]["timestamp"] + 1
                time.sleep(0.5)

            except Exception as e:
                break

        if all_oi:
            return all_oi
        else:
            return None

    def fetch_google_trends(keywords=["bitcoin", "buy crypto"]):
        from pytrends.request import TrendReq
        import pandas as pd
        from datetime import datetime, timedelta

        pytrends = TrendReq(hl='en-US', tz=0)

        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day)

        today = today_start.strftime('%Y-%m-%d')
        yesterday = (today_start - timedelta(days=1)).strftime('%Y-%m-%d')

        all_trends_data = []

        def get_trends_data(keyword, start_date, end_date):
            try:
                pytrends.build_payload([keyword], cat=0, timeframe=f"now 1-d", geo='', gprop='')
                data = pytrends.interest_over_time()

                if not data.empty:
                    data = data.reset_index()
                    data = data.rename(columns={keyword: "trend_score"})
                    data = data[["date", "trend_score"]]
                    return data
                else:
                    return None
            except Exception as e:
                return None

        for keyword in keywords:
            data_today = get_trends_data(keyword, today, today)

            if data_today is None:
                data_today = get_trends_data(keyword, yesterday, yesterday)

            if data_today is not None:
                all_trends_data.append({
                    "keyword": keyword,
                    "data": data_today
                })
            else:
                pass

        if all_trends_data:
            return all_trends_data
        else:
            return None


    def convert_datetime(obj):
        from datetime import datetime
        from pandas import Series, DataFrame, Timestamp
        if isinstance(obj, dict):
            return {k: convert_datetime(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_datetime(i) for i in obj]
        elif isinstance(obj, (datetime, Timestamp)):
            return obj.isoformat()
        elif isinstance(obj, Series):
            return convert_datetime(obj.to_dict())
        elif isinstance(obj, DataFrame):
            return [convert_datetime(row) for row in obj.to_dict(orient='records')]
        return obj

    crypto_pairs = collect_current_cryptocurrencies()
    metals = collect_current_precious_metals()
    indexes = collect_current_main_indexes()
    funding_rate = fetch_current_funding_rate_btcusdt()
    fear_greed = fetch_fear_greed_index()
    open_interest = fetch_open_interest()
    google_trends = fetch_google_trends()

    data = {
        "cryptocurrencies": crypto_pairs,
        "precious_metals": metals,
        "main_indexes": indexes,
        "funding_rate_btcusdt": funding_rate,
        "fear_greed_index": fear_greed,
        "open_interest": open_interest,
        "google_trends": google_trends
    }

    with open("market_data.json", "w", encoding="utf-8") as f:
        json.dump(convert_datetime(data), f, ensure_ascii=False, indent=4)