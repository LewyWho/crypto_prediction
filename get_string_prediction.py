import json
import last_candle

def collect_features_string_from_json(path="market_data.json"):
    last_candle.collect_last_candle()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    result = []

    for key in sorted(data.get("cryptocurrencies", {})):
        item = data["cryptocurrencies"][key]
        result.extend([
            item.get("open", 0),
            item.get("high", 0),
            item.get("low", 0),
            item.get("close", 0),
            item.get("volume", 0),
        ])

    for metal in ["cattle", "corn", "crude_oil", "gold", "silver", "soybeans", "wheat"]:
        metal_data = data.get("precious_metals", {}).get(metal, {})
        for param in ["close", "high", "low", "open", "volume"]:
            val_dict = metal_data.get(param, {})
            val = next(iter(val_dict.values()), 0)
            result.append(val)

    for index in sorted(data.get("main_indexes", {})):
        index_data = data["main_indexes"][index]
        for param in ["close", "high", "low", "open", "volume"]:
            val_dict = index_data.get(param, {})
            val = next(iter(val_dict.values()), 0)
            result.append(val)

    funding_rate = data.get("funding_rate_btcusdt", {}).get("funding_rate", 0)
    result.append(funding_rate)

    fear_greed_list = data.get("fear_greed_index", [])
    if fear_greed_list and isinstance(fear_greed_list, list):
        last_fgi = fear_greed_list[-1]
        fgi_value = last_fgi.get("Fear_Greed_Index") if isinstance(last_fgi, dict) else 0
        try:
            fgi_value = float(fgi_value)
        except:
            fgi_value = 0
        result.append(fgi_value)
    else:
        result.append(0)

    open_interest_list = data.get("open_interest", [])
    if open_interest_list and isinstance(open_interest_list, list):
        last_oi = open_interest_list[-1]
        oi_value = last_oi.get("open_interest", 0) if isinstance(last_oi, dict) else 0
        result.append(oi_value)
    else:
        result.append(0)

    google_trends = data.get("google_trends", [])
    trend_buy_crypto = 0
    trend_bitcoin = 0
    for trend_entry in google_trends:
        keyword = trend_entry.get("keyword", "").lower()
        trend_data = trend_entry.get("data", [])
        if trend_data:
            last_trend = trend_data[-1]
            score = last_trend.get("trend_score", 0)
            if keyword == "buy crypto":
                trend_buy_crypto = score
            elif keyword == "bitcoin":
                trend_bitcoin = score
    result.extend([trend_buy_crypto, trend_bitcoin])

    final_result = ",".join(map(str, result))
    return final_result

features_string = collect_features_string_from_json("market_data.json")