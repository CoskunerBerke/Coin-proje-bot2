"""
Kripto Coin Analiz Uygulaması — Veri Çekme Modülü
Binance (ccxt) ve CoinGecko API üzerinden fiyat, OHLCV ve market verisi çeker.
"""

import pandas as pd
import ccxt
import time
import requests
from datetime import datetime, timezone
from config import SUPPORTED_COINS, TA_PARAMS


class DataFetcher:
    """Binance ve CoinGecko API'lerinden kripto veri çekici."""

    def __init__(self):
        self.exchange = ccxt.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "future"}, # Futures piyasasına geçiş
        })
        self.coingecko_base = "https://api.coingecko.com/api/v3"
        self._coin_cache = {}
        self._cache_ttl = 30

    def _get_coin_info(self, coin_key: str) -> dict:
        """Coin bilgilerini getirir, desteklenmeyen coinler için otomatik fallback üretir."""
        coin_info = SUPPORTED_COINS.get(coin_key)
        if not coin_info:
            return {
                "name": coin_key,
                "coingecko_id": coin_key.lower(),
                "symbol": f"{coin_key}/USDT"
            }
        return coin_info

    def fetch_ohlcv(self, coin_key: str, timeframe: str = "1h", limit: int = None) -> pd.DataFrame:
        """Binance'ten OHLCV verisi çeker (Önbellekli)."""
        if limit is None:
            limit = TA_PARAMS["candle_limit"]
        coin_info = self._get_coin_info(coin_key)
        
        # Benzersiz önbellek anahtarı
        cache_key = f"ohlcv_{coin_key}_{timeframe}_{limit}"
        
        # Her zaman dilimi için uygun önbellek süresi (saniye cinsinden)
        ttl_map = {
            "1m": 25,
            "5m": 120,
            "15m": 300,
            "1h": 900,
            "4h": 1800,
            "1d": 7200
        }
        ttl = ttl_map.get(timeframe, 60)
        
        cached = self._get_cache(cache_key, ttl=ttl)
        if cached is not None:
            return cached

        symbol = coin_info["symbol"]
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if not ohlcv:
                raise ValueError(f"{symbol} için veri bulunamadı")
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            
            # Gelişmiş Hacim Verileri
            df['vol_ema'] = df['volume'].rolling(window=20).mean()
            df['relative_volume'] = df['volume'] / df['vol_ema']
            
            df.set_index("timestamp", inplace=True)
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
                
            self._set_cache(cache_key, df)
            return df
        except ccxt.NetworkError as e:
            raise ConnectionError(f"Ağ hatası: {e}")
        except ccxt.ExchangeError as e:
            raise ValueError(f"Borsa hatası: {e}")

    def fetch_ticker(self, coin_key: str) -> dict:
        """Anlık fiyat, 24h değişim, hacim bilgisi çeker (Önbellekli)."""
        coin_info = self._get_coin_info(coin_key)
        cache_key = f"ticker_{coin_key}"
        cached = self._get_cache(cache_key, ttl=10) # 10 saniye önbellek
        if cached:
            return cached
        try:
            ticker = self.exchange.fetch_ticker(coin_info["symbol"])
            result = {
                "last": ticker.get("last", 0),
                "high": ticker.get("high", 0),
                "low": ticker.get("low", 0),
                "volume": ticker.get("baseVolume", 0),
                "quoteVolume": ticker.get("quoteVolume", 0),
                "change": ticker.get("change", 0),
                "changePercent": ticker.get("percentage", 0),
                "bid": ticker.get("bid", 0),
                "ask": ticker.get("ask", 0),
                "vwap": ticker.get("vwap", 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._set_cache(cache_key, result)
            return result
        except Exception as e:
            raise RuntimeError(f"Ticker çekme hatası: {e}")

    def fetch_coin_info(self, coin_key: str) -> dict:
        """CoinGecko'dan detaylı coin bilgisi çeker (Uzatılmış Önbellekli)."""
        coin_info = self._get_coin_info(coin_key)
        cache_key = f"cginfo_{coin_key}"
        cached = self._get_cache(cache_key, ttl=7200) # 2 saat önbellek (429'ları önler)
        if cached:
            return cached
        try:
            url = f"{self.coingecko_base}/coins/{coin_info['coingecko_id']}"
            params = {"localization": "false", "tickers": "false", "market_data": "true",
                      "community_data": "true", "developer_data": "true"}
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 429 or response.status_code != 200:
                # 429 aldığında son başarılı önbelleği ömürsüz uzatıp dön
                old_cache = self._coin_cache.get(cache_key)
                if old_cache:
                    return old_cache[0]
                return self._empty_coin_info()
            data = response.json()
            market = data.get("market_data", {})
            community = data.get("community_data", {})
            result = {
                "name": data.get("name", coin_key),
                "symbol": data.get("symbol", "").upper(),
                "market_cap_rank": data.get("market_cap_rank", 0),
                "market_cap": market.get("market_cap", {}).get("usd", 0),
                "total_volume": market.get("total_volume", {}).get("usd", 0),
                "circulating_supply": market.get("circulating_supply", 0),
                "ath": market.get("ath", {}).get("usd", 0),
                "ath_change_percentage": market.get("ath_change_percentage", {}).get("usd", 0),
                "price_change_24h": market.get("price_change_percentage_24h", 0),
                "price_change_7d": market.get("price_change_percentage_7d", 0),
                "price_change_30d": market.get("price_change_percentage_30d", 0),
                "reddit_subscribers": community.get("reddit_subscribers", 0),
                "reddit_active_accounts_48h": community.get("reddit_accounts_active_48h", 0),
                "twitter_followers": community.get("twitter_followers", 0),
                "github_stars": data.get("developer_data", {}).get("stars", 0),
                "github_commits_4w": data.get("developer_data", {}).get("commit_count_4_weeks", 0),
                "sentiment_votes_up_percentage": data.get("sentiment_votes_up_percentage", 50),
                "sentiment_votes_down_percentage": data.get("sentiment_votes_down_percentage", 50),
                "image": data.get("image", {}).get("small", ""),
                "description": data.get("description", {}).get("en", "")[:500],
                "last_updated": data.get("last_updated", ""),
            }
            self._set_cache(cache_key, result)
            return result
        except Exception:
            old_cache = self._coin_cache.get(cache_key)
            if old_cache:
                return old_cache[0]
            return self._empty_coin_info()

    def fetch_fear_greed_index(self) -> dict:
        """Alternative.me Fear & Greed Index çeker (Önbellekli)."""
        cache_key = "fear_greed"
        cached = self._get_cache(cache_key, ttl=3600) # 1 saat önbellek
        if cached:
            return cached
        try:
            url = "https://api.alternative.me/fng/"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json().get("data", [{}])[0]
                result = {
                    "value": int(data.get("value", 50)),
                    "classification": data.get("value_classification", "Neutral"),
                    "timestamp": data.get("timestamp", ""),
                }
                self._set_cache(cache_key, result)
                return result
        except Exception:
            pass
        return {"value": 50, "classification": "Neutral", "timestamp": ""}

    def fetch_multi_timeframe(self, coin_key: str, timeframes: list = None) -> dict:
        """Birden fazla zaman dilimi için OHLCV verisi çeker (Zaten önbellekli)."""
        if timeframes is None:
            timeframes = ["15m", "1h", "4h", "1d"]
        results = {}
        for tf in timeframes:
            try:
                results[tf] = self.fetch_ohlcv(coin_key, tf)
                time.sleep(0.1) # Düşürüldü çünkü zaten cache'den geliyor
            except Exception:
                results[tf] = pd.DataFrame()
        return results

    def _get_cache(self, key: str, ttl: int = None):
        if ttl is None:
            ttl = self._cache_ttl
        if key in self._coin_cache:
            data, ts = self._coin_cache[key]
            if time.time() - ts < ttl:
                return data
        return None

    def _set_cache(self, key: str, data):
        self._coin_cache[key] = (data, time.time())

    def _empty_coin_info(self) -> dict:
        return {
            "name": "", "symbol": "", "market_cap_rank": 0, "market_cap": 0,
            "total_volume": 0, "circulating_supply": 0, "ath": 0,
            "ath_change_percentage": 0, "price_change_24h": 0,
            "price_change_7d": 0, "price_change_30d": 0,
            "reddit_subscribers": 0, "reddit_active_accounts_48h": 0,
            "twitter_followers": 0, "github_stars": 0, "github_commits_4w": 0,
            "sentiment_votes_up_percentage": 50,
            "sentiment_votes_down_percentage": 50,
            "image": "", "description": "", "last_updated": "",
        }

    def get_coin_list(self) -> list:
        return [{"key": k, "name": v["name"], "symbol": v["symbol"]}
                for k, v in SUPPORTED_COINS.items()]

    def search_custom_coin(self, symbol: str) -> bool:
        """Özel sembolün Binance'te var olup olmadığını kontrol eder."""
        try:
            test_symbol = f"{symbol.upper()}/USDT"
            ticker = self.exchange.fetch_ticker(test_symbol)
            return ticker is not None
        except Exception:
            return False

    def add_custom_coin(self, symbol: str):
        """Özel coin'i desteklenen listeye ekler."""
        symbol = symbol.upper()
        if symbol not in SUPPORTED_COINS:
            SUPPORTED_COINS[symbol] = {
                "name": symbol, "coingecko_id": symbol.lower(),
                "symbol": f"{symbol}/USDT",
            }

    def fetch_futures_data(self, coin_key: str) -> dict:
        """Futures piyasasına özel mikroyapı verilerini (OI, Funding, Spread) çeker (Önbellekli)."""
        cache_key = f"futures_{coin_key}"
        cached = self._get_cache(cache_key, ttl=120) # 2 dakika önbellek
        if cached:
            return cached

        coin_info = self._get_coin_info(coin_key)
        symbol = coin_info["symbol"]
        
        result = {"funding_rate": 0.0, "open_interest": 0.0, "spread_percent": 0.02, "oi_delta": 0.0}
        try:
            # 1. Spread Hesabı
            ob = self.exchange.fetch_order_book(symbol, limit=5)
            if ob and ob["asks"] and ob["bids"]:
                best_ask = ob["asks"][0][0]
                best_bid = ob["bids"][0][0]
                result["spread_percent"] = float((best_ask - best_bid) / best_bid * 100)
        except:
            pass

        try:
            # 2. Funding Rate
            funding = self.exchange.fetch_funding_rate(symbol)
            if funding and "fundingRate" in funding:
                result["funding_rate"] = float(funding["fundingRate"])
        except:
            pass

        try:
            # 3. Open Interest
            oi = self.exchange.fetch_open_interest(symbol)
            if oi and "openInterest" in oi:
                result["open_interest"] = float(oi["openInterest"])
                # Basit OI Değişimi
                prev_oi_key = f"prev_oi_val_{coin_key}"
                prev_oi = self._coin_cache.get(prev_oi_key, (None, 0))[0]
                if prev_oi:
                    result["oi_delta"] = float((result["open_interest"] - prev_oi) / prev_oi * 100)
                self._coin_cache[prev_oi_key] = (result["open_interest"], time.time())
        except:
            pass

        self._set_cache(cache_key, result)
        return result


