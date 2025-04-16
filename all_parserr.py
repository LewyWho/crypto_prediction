import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta
import glob

def collect_and_fix_pairs_cryptocurrencies():
    import ccxt
    import pandas as pd
    import time
    import os
    from datetime import datetime, timedelta

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

    days_back = 729
    start_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    def fetch_historical_data(symbol="BTC/USDT", timeframe="1h", start_date=start_date):
        filename = f"{symbol.replace('/', '_')}_{timeframe}.csv"

        if os.path.exists(filename):
            existing_df = pd.read_csv(filename)
            if not existing_df.empty:
                existing_df["timestamp"] = pd.to_datetime(existing_df["timestamp"])
                last_timestamp = existing_df["timestamp"].max()
                since = int(last_timestamp.timestamp() * 1000)
            else:
                since = exchange.parse8601(f"{start_date}T00:00:00Z")
        else:
            existing_df = pd.DataFrame()
            since = exchange.parse8601(f"{start_date}T00:00:00Z")

        now = exchange.milliseconds()
        all_data = []

        while since < now:
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
                if not ohlcv:
                    break

                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                all_data.append(df)

                since = ohlcv[-1][0] + 1


                time.sleep(0.5)

            except Exception as e:
                break

        if all_data:
            new_df = pd.concat(all_data)
            full_df = pd.concat([existing_df, new_df]).drop_duplicates().sort_values("timestamp")
            full_df.to_csv(filename, index=False)
            return full_df
        else:
            return existing_df if not existing_df.empty else None
        


    for pair in crypto_pairs:
        fetch_historical_data(symbol=pair, timeframe="1h", start_date=start_date)

    csv_files = glob.glob("*.csv")

    all_dfs = []

    for file in csv_files:
        if os.path.basename(file) != "combined_wide_assets.csv":
            try:
                asset_name = os.path.splitext(os.path.basename(file))[0]

                df = pd.read_csv(file, parse_dates=["timestamp"])
                df.set_index("timestamp", inplace=True)

                df.columns = [f"{asset_name}_{col}" for col in df.columns]

                all_dfs.append(df)
            except Exception as e:
                pass
        else:
            pass

    if all_dfs:
        merged_df = pd.concat(all_dfs, axis=1).sort_index()

        merged_df.rename(columns={'timestamp': 'Datetime'}, inplace=True)

        merged_df.to_csv("all_crypto_merged.csv")
    else:
        pass

    def delete_files(pattern):
        files_to_delete = glob.glob(pattern)
        for file in files_to_delete:
            if os.path.basename(file) != "combined_wide_assets.csv" and os.path.basename(file) != "all_crypto_merged.csv":
                os.remove(file)
            else:
                pass

    delete_files("*.csv")

    merged_df = pd.read_csv("all_crypto_merged.csv") 

    merged_df = merged_df.rename(columns={'timestamp': 'Datetime'})

    merged_df.to_csv('all_crypto_merged.csv', index=False)


def collect_and_fix_precious_metals():
    assets = {
        "gold": "GC=F",
        "silver": "SI=F",
        "crude_oil": "CL=F",
        "wheat": "ZW=F",
        "corn": "ZC=F",
        "soybeans": "ZS=F",
        "cattle": "LE=F",
    }

    end_date = datetime.today().strftime("%Y-%m-%d")

    def fetch_yfinance_data(ticker, name, interval="1h"):
        """Загружает почасовые исторические данные, проверяя последнюю дату."""
        filename = f"{name}_{interval}.csv"
        
        if os.path.exists(filename):
            existing_df = pd.read_csv(filename)
            if not existing_df.empty:
                existing_df["timestamp"] = pd.to_datetime(existing_df["timestamp"])
                last_timestamp = existing_df["timestamp"].max()
                start_date = last_timestamp.strftime("%Y-%m-%d %H:%M:%S")
            else:
                start_date = (datetime.today() - timedelta(days=729)).strftime("%Y-%m-%d")
        else:
            existing_df = pd.DataFrame()
            start_date = (datetime.today() - timedelta(days=729)).strftime("%Y-%m-%d")

        data = yf.download(ticker, start=start_date, end=end_date, interval=interval)

        if data.empty:
            return None

        data.reset_index(inplace=True)
        data.rename(columns={"index": "timestamp"}, inplace=True)

        if not existing_df.empty:
            full_df = pd.concat([existing_df, data]).drop_duplicates().sort_values("timestamp")
        else:
            full_df = data

        if isinstance(full_df.columns, pd.MultiIndex):
            full_df.columns = [' '.join(col).strip() for col in full_df.columns.values]

        full_df.to_csv(f'{filename}', index=False)
        return full_df

    datasets = {name: fetch_yfinance_data(ticker, name) for name, ticker in assets.items()}

    csv_files = glob.glob("*.csv")
    wide_format_dfs = []

    for file in csv_files:
        df = pd.read_csv(file)
        asset_name = os.path.basename(file).split("_")[0]
        
        df["Datetime"] = pd.to_datetime(df["Datetime"])

        df = df.rename(columns=lambda col: f"{asset_name}_{col}" if col != "Datetime" else col)

        wide_format_dfs.append(df)


    from functools import reduce
    combined_wide_df = reduce(lambda left, right: pd.merge(left, right, on="Datetime", how="outer"), wide_format_dfs)

    combined_wide_df = combined_wide_df.sort_values("Datetime")

    combined_wide_df.to_csv("combined_wide_assets.csv", index=False)

    def delete_files(pattern):
        files_to_delete = glob.glob(pattern)
        for file in files_to_delete:
            if os.path.basename(file) != "combined_wide_assets.csv":
                os.remove(file)
            else:
                pass

    delete_files("*.csv")

    merged_df = pd.read_csv("combined_wide_assets.csv")

    merged_df = merged_df.sort_values("Datetime").reset_index(drop=True)

    merged_df.fillna(method="ffill", inplace=True)
    merged_df.fillna(method="bfill", inplace=True)

    merged_df.to_csv("combined_wide_assets.csv", index=False)

def collect_and_fix_main_indexes():
    import yfinance as yf
    import pandas as pd
    from datetime import datetime, timedelta

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

    end_date = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=729)).strftime("%Y-%m-%d")

    def fetch_yfinance_data(ticker, name, start, end, interval="1h"):
        try:
            data = yf.download(ticker, start=start, end=end, interval=interval)
            
            if data.empty:
                return None
            
            filename = f"{name}_{interval}.csv"
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [' '.join(col).strip() for col in data.columns.values]
            data.to_csv(filename)
            return data
        except Exception as e:
            return None

    datasets = {name: fetch_yfinance_data(ticker, name, start_date, end_date, "1h") for name, ticker in indices.items()}

    csv_files = glob.glob("*.csv")
    wide_format_dfs = []

    for file in csv_files:
        if os.path.basename(file) != "combined_wide_assets.csv" and os.path.basename(file) != "all_crypto_merged.csv":
            df = pd.read_csv(file)
            asset_name = os.path.basename(file).split("_")[0]
            
            df["Datetime"] = pd.to_datetime(df["Datetime"])

            df = df.rename(columns=lambda col: f"{asset_name}_{col}" if col != "Datetime" else col)

            wide_format_dfs.append(df)


    from functools import reduce
    combined_wide_df = reduce(lambda left, right: pd.merge(left, right, on="Datetime", how="outer"), wide_format_dfs)

    combined_wide_df = combined_wide_df.sort_values("Datetime")

    combined_wide_df.to_csv("combined_wide_indexes.csv", index=False)

    def delete_files(pattern):
        files_to_delete = glob.glob(pattern)
        for file in files_to_delete:
            if os.path.basename(file) != "combined_wide_assets.csv" and os.path.basename(file) != "all_crypto_merged.csv" and os.path.basename(file) != "combined_wide_indexes.csv":
                os.remove(file)
            else:
                pass

    delete_files("*.csv")

    merged_df = pd.read_csv("combined_wide_indexes.csv")

    merged_df = merged_df.sort_values("Datetime").reset_index(drop=True)

    merged_df.fillna(method="ffill", inplace=True)
    merged_df.fillna(method="bfill", inplace=True)

    merged_df.to_csv("combined_wide_indexes.csv", index=False)


def merge_dataframes_by_timestamp(all_crypto_merged, combined_wide_assets, combined_wide_indexes):
    """
    Объединяет три датафрейма по временной метке.
    
    :param all_crypto_merged: путь к файлу all_crypto_merged
    :param combined_wide_assets: путь к файлу с combined_wide_assets
    :param combined_wide_indexes: путь к файлу с combined_wide_indexes
    :return: сохраняет объединённый DataFrame в 'merged_data.csv'
    """
    df_crypto = pd.read_csv(all_crypto_merged)
    df_assets = pd.read_csv(combined_wide_assets)
    df_indexes = pd.read_csv(combined_wide_indexes)

    for df in [df_crypto, df_assets, df_indexes]:
        df['Datetime'] = pd.to_datetime(df['Datetime'], utc=True).dt.tz_convert(None)

    merged_df = df_crypto.merge(df_assets, on="Datetime", how="outer")
    merged_df = merged_df.merge(df_indexes, on="Datetime", how="outer")

    merged_df.to_csv('merged_data.csv', index=False)

def merge_30min_to_hour(data, datetime_col='Datetime'):
    import pandas as pd

    if isinstance(data, str):
        df = pd.read_csv(data)
    else:
        df = data.copy()

    df[datetime_col] = pd.to_datetime(df[datetime_col])

    df['Datetime'] = df[datetime_col].dt.floor('H')

    grouped = df.groupby('Datetime').mean(numeric_only=True).reset_index()

    cleaned = grouped.dropna(how='all')

    cleaned.fillna(method="ffill", inplace=True)
    cleaned.fillna(method="bfill", inplace=True)

    cleaned.to_csv('merged_fix_to_hour.csv', index=False)

def funding_rates():
    import ccxt
    import pandas as pd
    import time
    from datetime import datetime, timezone
    exchange = ccxt.bybit({
    "enableRateLimit": True})

    def fetch_funding_btc_linear(days_back=729):

        now = datetime.now(timezone.utc)
        since = int((now - pd.Timedelta(days=days_back)).timestamp() * 1000)
        all_funding = []

        while since < exchange.milliseconds():
            try:
                funding = exchange.fetch_funding_rate_history(
                    symbol="BTCUSDT",
                    since=since,
                    limit=1000,
                    params={"category": "linear"}
                )

                if not funding:
                    break

                for f in funding:
                    all_funding.append({
                        "timestamp": datetime.fromtimestamp(f["timestamp"] / 1000, timezone.utc),
                        "funding_rate": f["fundingRate"]
                    })

                since = funding[-1]["timestamp"] + 1
                time.sleep(0.5)

            except Exception as e:
                break

        if all_funding:
            df = pd.DataFrame(all_funding)
            df = df.sort_values("timestamp").reset_index(drop=True)
            df.to_csv("BTCUSDT_funding_rates.csv", index=False)
            return df
        else:
            return None

    fetch_funding_btc_linear()

    df = pd.read_csv("BTCUSDT_funding_rates.csv", parse_dates=["timestamp"])

    df.set_index("timestamp", inplace=True)

    start = df.index.min()
    end = df.index.max()
    hourly_index = pd.date_range(start=start, end=end, freq="1h")

    df_hourly = df.reindex(hourly_index, method='ffill')

    df_hourly = df_hourly.rename_axis("timestamp").reset_index()
    df_hourly.rename(columns={'timestamp': 'Datetime'}, inplace=True)
    df_hourly['Datetime'] = pd.to_datetime(df_hourly['Datetime'], utc=True).dt.tz_convert(None)
    df_hourly.to_csv("BTCUSDT_funding_rates_hourly.csv", index=False)
    os.remove('BTCUSDT_funding_rates.csv')

    merged_data = pd.read_csv('merged_fix_to_hour.csv')

    merged_data['Datetime'] = pd.to_datetime(merged_data['Datetime'])

    merged_data = merged_data.merge(df_hourly, on="Datetime", how="outer")

    merged_data.fillna(method="ffill", inplace=True)
    merged_data.fillna(method="bfill", inplace=True)

    merged_data.to_csv('merged_fix_to_hour.csv', index=False)

def fetch_fear_greed_index(days=729):
    import requests
    import pandas as pd
    from datetime import datetime
    import os

    url = f"https://api.alternative.me/fng/?limit={days}&format=json"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()['data']
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='s', utc=True)
        df['value'] = df['value'].astype(int)
        df = df[['timestamp', 'value']]
        df = df.sort_values('timestamp').reset_index(drop=True)
        df = df.rename(columns={'timestamp': 'Datetime'})

        start = df['Datetime'].min().floor('h')
        end = df['Datetime'].max().ceil('h')
        hourly_index = pd.date_range(start=start, end=end, freq='1h')

        df.set_index('Datetime', inplace=True)
        df_hourly = df.reindex(hourly_index, method='ffill')
        df_hourly = df_hourly.rename_axis("Datetime").reset_index()

        df_hourly['Datetime'] = pd.to_datetime(df_hourly['Datetime'], utc=True).dt.tz_convert(None)

        df_hourly.to_csv("fear_greed_index.csv", index=False)

        merged_data = pd.read_csv('merged_fix_to_hour.csv')
        merged_data['Datetime'] = pd.to_datetime(merged_data['Datetime'])

        df_hourly['Datetime'] = pd.to_datetime(df_hourly['Datetime'])

        merged_data = merged_data.merge(df_hourly, on="Datetime", how="outer")

        merged_data = merged_data.sort_values('Datetime').reset_index(drop=True)
        merged_data.fillna(method="ffill", inplace=True)
        merged_data.fillna(method="bfill", inplace=True)

        merged_data.to_csv('merged_fix_to_hour.csv', index=False)

    else:
        return None


def fetch_open_interest(symbol="BTCUSDT", interval="1h", days_back=729):
    import ccxt
    import pandas as pd
    import time
    from datetime import datetime, timezone

    exchange = ccxt.bybit({
        "enableRateLimit": True
    })


    now = datetime.now(timezone.utc)
    since = int((now - pd.Timedelta(days=days_back)).timestamp() * 1000)

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
        df = pd.DataFrame(all_oi)
        df = df.sort_values("timestamp").reset_index(drop=True)
        df = df.rename(columns={'timestamp': 'Datetime'})
        df.to_csv("BTCUSDT_open_interest_hourly.csv", index=False)

        merged_data = pd.read_csv('merged_fix_to_hour.csv')
        merged_data['Datetime'] = pd.to_datetime(merged_data['Datetime'])

        df['Datetime'] = pd.to_datetime(df['Datetime'])
        df['Datetime'] = pd.to_datetime(df['Datetime'], utc=True).dt.tz_convert(None)


        merged_data = merged_data.merge(df, on="Datetime", how="outer")

        merged_data = merged_data.sort_values('Datetime').reset_index(drop=True)
        merged_data.fillna(method="ffill", inplace=True)
        merged_data.fillna(method="bfill", inplace=True)

        merged_data = merged_data.rename(columns={'value': 'fear_gread_index'})

        merged_data.to_csv('merged_fix_to_hour.csv', index=False)

        return df
    else:
        return None
    

def fetch_google_trends(keyword="buy crypto", days_back=729):
    from pytrends.request import TrendReq
    import pandas as pd
    from datetime import datetime, timedelta

    pytrends = TrendReq(hl='en-US', tz=0)
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    pytrends.build_payload([keyword], cat=0, timeframe=f"{start_date} {datetime.now().strftime('%Y-%m-%d')}", geo='', gprop='')

    data = pytrends.interest_over_time()

    if not data.empty:
        data = data.reset_index()
        data = data.rename(columns={keyword: "trend_score"})
        data = data[["date", "trend_score"]]
        data.to_csv(f"google_trends_{keyword}.csv", index=False)
        return data
    else:
        return None

def merge_google_trends():
    csv_files = ["google_trends_buy crypto.csv", "google_trends_bitcoin.csv"]
    merged_data = pd.DataFrame()

    for file in csv_files:
        df = pd.read_csv(file)
        df.columns = [col.strip() for col in df.columns]
        keyword = os.path.splitext(file)[0].replace("google_trends_", "").replace(" ", "_")
        df = df.rename(columns={df.columns[1]: f"google_trends_{keyword}"})
        if merged_data.empty:
            merged_data = df
        else:
            merged_data = pd.merge(merged_data, df, on="date", how="outer")

    merged_data["date"] = pd.to_datetime(merged_data["date"])
    merged_data = merged_data.sort_values("date").reset_index(drop=True)

    hourly_data = pd.DataFrame()
    for _, row in merged_data.iterrows():
        for hour in range(24):
            hour_row = row.copy()
            hour_row["Datetime"] = row["date"] + pd.Timedelta(hours=hour)
            hourly_data = pd.concat([hourly_data, hour_row.to_frame().T], ignore_index=True)

    hourly_data = hourly_data.drop(columns=["date"])
    hourly_data = hourly_data.sort_values("Datetime").reset_index(drop=True)

    hourly_data.to_csv("google_trends_merged_hourly.csv", index=False)

    merged_data = pd.read_csv('merged_fix_to_hour.csv')
    merged_data['Datetime'] = pd.to_datetime(merged_data['Datetime'])

    hourly_data['Datetime'] = pd.to_datetime(hourly_data['Datetime'], utc=True).dt.tz_convert(None)

    combined = pd.merge(merged_data, hourly_data, on="Datetime", how="outer")

    combined = combined.sort_values('Datetime').reset_index(drop=True)
    combined.fillna(method="ffill", inplace=True)
    combined.fillna(method="bfill", inplace=True)


    combined.to_csv('merged_fix_to_hour.csv', index=False)



def collect_main():
    import time
    collect_and_fix_precious_metals()
    collect_and_fix_pairs_cryptocurrencies()
    collect_and_fix_main_indexes()
    merge_dataframes_by_timestamp('all_crypto_merged.csv', 'combined_wide_assets.csv', 'combined_wide_indexes.csv')
    merge_30min_to_hour('merged_data.csv')
    funding_rates()
    fetch_fear_greed_index()
    fetch_open_interest()
    fetch_google_trends("buy crypto")
    time.sleep(60)
    fetch_google_trends("bitcoin")
    merge_google_trends()

collect_main()