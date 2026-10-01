"""
Offline demo server — runs the real Flask API on synthetic market data.

What it does
  * creates a demo data directory with clearly fictional, simulated trades
    (ids start with "demo-"), coin memory and a spot-scan result,
  * starts app.py with DISABLE_BOT_ENGINE=1 (no 24/7 engine thread),
  * replaces the exchange/news calls with a seeded random walk, so the
    technical analysis, signal generation and every API endpoint run for real
    without Binance, CoinGecko, RSS feeds or Telegram.

Nothing here is real market data or real trading performance.

Usage
  python scripts/demo_server.py                 # API on http://localhost:5000
  python -m http.server 8080 -d frontend        # panel on http://localhost:8080
"""

import argparse
import json
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR_TZ = timezone(timedelta(hours=3))

# Synthetic price anchors — fictional, only used to shape the random walk.
BASE_PRICE = {"BTC": 64000.0, "SOL": 140.0}
TF_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440, "1w": 10080}


SERIES_LENGTH = 1500


def synthetic_ohlcv(coin, timeframe, limit):
    """Deterministic random walk candles (same coin + timeframe -> same series; `limit` only slices it)."""
    import pandas as pd

    minutes = TF_MINUTES.get(timeframe, 60)
    rng = random.Random(f"{coin}-{timeframe}")
    price = BASE_PRICE.get(coin, 1.0) * (0.92 + 0.16 * rng.random())
    vol_step = 0.0015 * math.sqrt(minutes)
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0, tzinfo=None)
    total = max(SERIES_LENGTH, limit)
    rows = []
    for i in range(total):
        drift = 0.0004 * math.sin(i / 17.0)
        change = rng.gauss(drift, vol_step)
        open_ = price
        close = max(price * (1 + change), 0.0001)
        high = max(open_, close) * (1 + abs(rng.gauss(0, vol_step / 2)))
        low = min(open_, close) * (1 - abs(rng.gauss(0, vol_step / 2)))
        volume = 1000 * (1 + abs(rng.gauss(0, 0.6)))
        ts = end - timedelta(minutes=minutes * (total - 1 - i))
        rows.append([ts, open_, high, low, close, volume])
        price = close
    # Re-anchor the walk so the latest close sits near the coin's anchor price.
    scale = BASE_PRICE.get(coin, 1.0) * (0.98 + 0.04 * rng.random()) / rows[-1][4]
    rows = [[ts, o * scale, h * scale, lo * scale, c * scale, v] for ts, o, h, lo, c, v in rows]
    df = pd.DataFrame(rows[-limit:], columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["vol_ema"] = df["volume"].rolling(window=20).mean()
    df["relative_volume"] = df["volume"] / df["vol_ema"]
    df.set_index("timestamp", inplace=True)
    return df


class SyntheticFetcher:
    """Drop-in replacement for the network methods of data_fetcher.DataFetcher."""

    def fetch_ohlcv(self, coin_key, timeframe="1h", limit=None):
        return synthetic_ohlcv(coin_key.upper(), timeframe, limit or 200)

    def fetch_ticker(self, coin_key):
        df = synthetic_ohlcv(coin_key.upper(), "15m", 96)
        last = float(df["close"].iloc[-1])
        first = float(df["open"].iloc[0])
        return {
            "last": last, "high": float(df["high"].max()), "low": float(df["low"].min()),
            "volume": float(df["volume"].sum()), "quoteVolume": float((df["volume"] * df["close"]).sum()),
            "change": last - first, "changePercent": (last - first) / first * 100,
            "bid": last * 0.9999, "ask": last * 1.0001, "vwap": float(df["close"].mean()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def fetch_coin_info(self, coin_key):
        return {"name": coin_key, "symbol": coin_key, "market_cap_rank": 0, "market_cap": 0,
                "sentiment_votes_up_percentage": 50, "sentiment_votes_down_percentage": 50}

    def fetch_futures_data(self, coin_key):
        return {"funding_rate": 0.0, "open_interest": 0.0, "spread_percent": 0.02, "oi_delta": 0.0}


def _pnl(direction, entry, exit_price, amount, leverage=3, commission=0.0004):
    move = (exit_price - entry) / entry * 100 if direction == "LONG" else (entry - exit_price) / entry * 100
    pnl_pct = round(move * leverage - commission * 2 * 100, 2)
    pnl_usdt = round(move * leverage / 100 * amount - amount * commission * 2, 2)
    return pnl_pct, pnl_usdt


def build_demo_trades(fetcher):
    """Fictional simulated trades. Prices follow the synthetic random walk."""
    now = datetime.now(TR_TZ)
    rng = random.Random("demo-trades")
    reasons = ["TP (Üst Bariyer)", "SL (Alt Bariyer)", "WEAK_MOMENTUM_PROFIT_TAKE",
               "STRUCTURE (Fiyat Destek + Tampon Altına Kırıldı)", "ZAMAN_ASIMI (Dikey Bariyer)",
               "TRAILING_STRONG_MOMENTUM", "PEAK_PROFIT_PROTECTION", "SL (Alt Bariyer)"]
    trades = []
    for i, reason in enumerate(reasons):
        coin = "BTC" if i % 2 == 0 else "SOL"
        direction = "LONG" if i % 3 != 1 else "SHORT"
        entry = BASE_PRICE[coin] * (0.95 + 0.1 * rng.random())
        win = not reason.startswith("SL") and "ZAMAN" not in reason
        move = (0.004 + 0.01 * rng.random()) * (1 if win else -1)
        exit_price = entry * (1 + move) if direction == "LONG" else entry * (1 - move)
        amount = round(40 + 30 * rng.random(), 2)
        pnl_pct, pnl_usdt = _pnl(direction, entry, exit_price, amount)
        opened = now - timedelta(days=4 - i * 0.45, hours=3)
        closed = opened + timedelta(hours=1 + 2 * rng.random())
        trades.append({
            "id": f"demo-{i + 1:03d}", "tarih": opened.strftime("%Y-%m-%d %H:%M:%S"),
            "kapanis_tarihi": closed.strftime("%Y-%m-%d %H:%M:%S"),
            "coin": coin, "yon": direction, "durum": "KAPALI", "mod": "SİMÜLASYON",
            "giris_fiyati": round(entry, 4), "cikis_fiyati": round(exit_price, 4), "guncel_fiyat": round(exit_price, 4),
            "miktar_usdt": amount, "giris_bakiye": 1000.0, "miktar_yuzde": round(amount / 10, 1),
            "kaldirac": 3, "pnl_yuzde": pnl_pct, "pnl_usdt": pnl_usdt, "exit_reason": reason,
            "tp1_hit": reason.startswith("TP"), "regime": "TRENDING_BULL" if direction == "LONG" else "TRENDING_BEAR",
            "timeframe": "15m",
        })
    for j, (coin, direction) in enumerate([("BTC", "LONG"), ("SOL", "SHORT")]):
        current = fetcher.fetch_ticker(coin)["last"]
        entry = current * (0.994 if direction == "LONG" else 1.004)
        amount = 55.0 + 10 * j
        pnl_pct, pnl_usdt = _pnl(direction, entry, current, amount)
        opened = now - timedelta(minutes=50 + 35 * j)
        trades.append({
            "id": f"demo-open-{j + 1}", "tarih": opened.strftime("%Y-%m-%d %H:%M:%S"),
            "start_timestamp": opened.timestamp(), "coin": coin, "yon": direction, "durum": "AÇIK",
            "mod": "SİMÜLASYON", "giris_fiyati": round(entry, 4), "guncel_fiyat": round(current, 4),
            "miktar_usdt": amount, "giris_bakiye": 1000.0, "miktar_yuzde": round(amount / 10, 1),
            "kaldirac": 3, "stop_loss": round(entry * (0.985 if direction == "LONG" else 1.015), 4),
            "take_profit": round(entry * (1.03 if direction == "LONG" else 0.97), 4),
            "cikis_fiyati": None, "pnl_yuzde": pnl_pct, "pnl_usdt": pnl_usdt, "timeframe": "15m",
        })
    return sorted(trades, key=lambda t: t["tarih"], reverse=True)


DEMO_FILES = ("bot_trades.json", "bot_avoided_trades.json", "coin_trade_memory.json", "bot_spot_portfolio.json",
              "bot_logs.txt", "persistent_settings.json", "latest_opportunities.json", "counterfactual_data.json",
              "counterfactual_lessons.json", ".data_reset_v3_done")


def seed_demo_data(data_dir, fetcher):
    os.makedirs(data_dir, exist_ok=True)
    os.chdir(data_dir)
    for name in DEMO_FILES:  # start from a clean slate every time
        if os.path.exists(name):
            os.remove(name)
    trades = build_demo_trades(fetcher)
    with open("bot_trades.json", "w", encoding="utf-8") as f:
        json.dump(trades, f, indent=4, ensure_ascii=False)
    with open("bot_avoided_trades.json", "w", encoding="utf-8") as f:
        json.dump([], f)
    # app.py archives closed trades on its very first start unless this flag exists.
    with open(".data_reset_v3_done", "w", encoding="utf-8") as f:
        f.write("demo data — skip the one-time archive step\n")
    with open("bot_logs.txt", "w", encoding="utf-8") as f:
        f.write(f"[{datetime.now(TR_TZ):%Y-%m-%d %H:%M:%S}] 🧪 DEMO: synthetic market data, simulated trades only.\n")

    from coin_intelligence import CoinIntelligenceManager
    intel = CoinIntelligenceManager()
    for t in reversed(trades):
        if t["durum"] == "KAPALI":
            intel.log_completed_trade(t["coin"], t)

    from spot_investor import SpotInvestor
    from technical_analysis import TechnicalAnalyzer
    SpotInvestor(fetcher, TechnicalAnalyzer()).scan_spot_opportunities()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=os.path.join(REPO_ROOT, "demo-data"),
                        help="where the demo JSON files are written (default: ./demo-data, git-ignored)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 5000)))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--keep", action="store_true", help="reuse existing demo files instead of re-seeding")
    args = parser.parse_args()

    os.environ["DISABLE_BOT_ENGINE"] = "1"
    for name in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_DATA_CHAT_ID", "CRYPTOPANIC_API_KEY"):
        os.environ[name] = ""  # the demo never talks to Telegram or news APIs
    os.environ.setdefault("CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080")
    sys.path.insert(0, REPO_ROOT)

    fetcher = SyntheticFetcher()
    data_dir = os.path.abspath(args.data_dir)
    if args.keep and os.path.exists(os.path.join(data_dir, "bot_trades.json")):
        os.chdir(data_dir)
    else:
        seed_demo_data(data_dir, fetcher)

    import app as api
    import sentiment_analysis

    for target in (api.fetcher, api.signal_gen.fetcher):
        for name in ("fetch_ohlcv", "fetch_ticker", "fetch_coin_info", "fetch_futures_data"):
            setattr(target, name, getattr(fetcher, name))
    sentiment_analysis.SentimentAnalyzer._fetch_rss_news = lambda self, coin_key: []
    sentiment_analysis.SentimentAnalyzer._fetch_api_news = lambda self, coin_key: []
    sentiment_analysis.SentimentAnalyzer._fetch_fear_greed = lambda self: {"value": 50, "classification": "Neutral"}

    print(f"Demo API on http://{args.host}:{args.port} (data: {data_dir}); CORS: {os.environ['CORS_ORIGINS']}")
    api.app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
