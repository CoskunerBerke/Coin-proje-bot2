import json
from data_fetcher import DataFetcher
from technical_analysis import TechnicalAnalyzer
from sentiment_analysis import SentimentAnalyzer
from signal_generator import SignalGenerator
from coin_intelligence import CoinIntelligenceManager
from app import sanitize_nan

fetcher = DataFetcher()
analyzer = TechnicalAnalyzer()
sentiment_analyzer = SentimentAnalyzer()
signal_gen = SignalGenerator()
intel = CoinIntelligenceManager()

coin = "BTC"
timeframe = "15m"

print("--- Running Test Analysis ---")
ticker = fetcher.fetch_ticker(coin)
coin_info = fetcher.fetch_coin_info(coin)
df = fetcher.fetch_ohlcv(coin, timeframe, limit=210)
ta_result = analyzer.full_analysis(df)
sentiment_result = sentiment_analyzer.full_analysis(coin, coin_info)

htf_map = {"1m": "15m", "5m": "1h", "15m": "1h", "1h": "4h", "4h": "1d", "1d": "1w"}
htf = htf_map.get(timeframe, "4h")
df_htf = fetcher.fetch_ohlcv(coin, htf, limit=210)
mtf_data = analyzer.analyze_mtf_alignment(df, df_htf)

signal = signal_gen.generate_signal(coin, ticker, ta_result, sentiment_result, timeframe, mtf_data)
dna = intel.get_coin_dna(coin)
weights = intel.get_adaptive_weights(coin)

res = {
    "status": "success",
    "ticker": ticker,
    "coin_info": coin_info,
    "ta_result": ta_result,
    "sentiment_result": sentiment_result,
    "signal": signal,
    "dna": dna,
    "weights": weights
}

print("--- Sanitizing ---")
sanitized = sanitize_nan(res)

print("--- Testing JSON dumps ---")
try:
    json_str = json.dumps(sanitized)
    print("SUCCESS! JSON serialized perfectly!")
except Exception as e:
    print(f"FAILED: {str(e)}")
    # Let's inspect the types recursively to find the culprit
    def find_culprit(data, path=""):
        if isinstance(data, dict):
            for k, v in data.items():
                find_culprit(v, f"{path} -> {k}")
        elif isinstance(data, list):
            for i, x in enumerate(data):
                find_culprit(x, f"{path} -> [{i}]")
        else:
            try:
                json.dumps(data)
            except Exception as e:
                print(f"CULPRIT at {path}: Value={data}, Type={type(data)}, Error={str(e)}")

    find_culprit(sanitized)
