"""
Kripto Coin Analiz Uygulaması — Sentiment Analizi Modülü
Haber toplama (CryptoPanic + RSS), duygu analizi ve topluluk verisi.
"""

import requests
import time
import feedparser
from datetime import datetime, timezone
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from config import CRYPTOPANIC_API_KEY, RSS_FEEDS


class SentimentAnalyzer:
    """Haber kaynaklarından (RSS + API) sentiment analizi yapar."""

    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        self._cache = {}
        self._cache_ttl = 300 # 5 dakika
        self._rss_cache = None
        self._rss_cache_ts = 0
        self._rss_cache_ttl = 600 # 10 dakika

    def full_analysis(self, coin_key: str, coin_info: dict = None) -> dict:
        cache_key = f"sentiment_{coin_key}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        # 1. RSS Haberlerini Tara (Hızlı ve Güvenilir)
        rss_news = self._fetch_rss_news(coin_key)
        
        # 2. CryptoPanic/API Haberlerini Çek
        api_news = self._fetch_api_news(coin_key)
        
        all_news = rss_news + api_news
        
        # 3. Sentiment Hesapla
        news_sentiment = self._analyze_news_sentiment(all_news)
        
        # 4. Fear & Greed
        fear_greed = self._fetch_fear_greed()

        # 5. Genel skor
        overall = self._calculate_overall_sentiment(news_sentiment, coin_info, fear_greed)

        result = {
            "news": all_news[:20],
            "news_sentiment": news_sentiment,
            "fear_greed": fear_greed,
            "overall": overall,
            "has_breaking": any(news_sentiment.get("hype_detected", False) for _ in [1]),
        }

        self._set_cache(cache_key, result)
        return result

    def _fetch_rss_news(self, coin_key: str) -> list:
        """Major haber sitelerinin RSS feedlerini tarar (Önbellekli)."""
        now = time.time()
        # RSS beslemelerini 10 dakikada bir küresel olarak çekip önbelleğe al
        if not self._rss_cache or (now - self._rss_cache_ts > self._rss_cache_ttl):
            all_entries = []
            for url in RSS_FEEDS:
                try:
                    feed = feedparser.parse(url)
                    for entry in feed.entries[:10]:
                        all_entries.append({
                            "title": entry.title,
                            "link": entry.link,
                            "published": entry.get("published", "")
                        })
                except:
                    continue
            self._rss_cache = all_entries
            self._rss_cache_ts = now
            
        news = []
        for entry in self._rss_cache:
            title = entry["title"]
            # Sadece ilgili coinle veya kriptoyla ilgili haberleri filtrele
            if coin_key.lower() in title.lower() or "crypto" in title.lower():
                news.append({
                    "title": title,
                    "source": "Official News",
                    "url": entry["link"],
                    "published_at": entry["published"],
                    "is_breaking": "breaking" in title.lower() or "alert" in title.lower()
                })
        return news

    def _fetch_api_news(self, coin_key: str) -> list:
        news = []
        if CRYPTOPANIC_API_KEY:
            try:
                url = f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_API_KEY}&currencies={coin_key}"
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("results", [])[:10]:
                        news.append({
                            "title": item.get("title", ""),
                            "source": item.get("source", {}).get("title", "CryptoPanic"),
                            "url": item.get("url", ""),
                            "published_at": item.get("published_at", ""),
                            "is_breaking": item.get("votes", {}).get("important", 0) > 2
                        })
            except:
                pass
        return news

    def _analyze_news_sentiment(self, news: list) -> dict:
        if not news:
            return {"positive_pct": 33, "negative_pct": 33, "neutral_pct": 34, "avg_score": 0, "total_news": 0, "scored_news": []}

        scores = []
        scored_news = []
        pos, neg, neu = 0, 0, 0
        breaking_count = 0

        for item in news:
            sent = self.vader.polarity_scores(item["title"])
            score = sent["compound"]
            
            # Önemli haber bonusu
            if item.get("is_breaking"):
                score *= 1.2
                breaking_count += 1
            
            scores.append(score)
            
            if score > 0.05: pos += 1
            elif score < -0.05: neg += 1
            else: neu += 1
            
            scored_news.append({
                "title": item["title"],
                "source": item["source"],
                "score": score,
                "url": item["url"]
            })

        total = len(news)
        avg = sum(scores) / total if total > 0 else 0
        
        return {
            "positive_pct": round(pos/total*100),
            "negative_pct": round(neg/total*100),
            "neutral_pct": round(neu/total*100),
            "avg_score": avg,
            "total_news": total,
            "hype_detected": breaking_count > 0 or avg > 0.4,
            "scored_news": scored_news
        }

    def _fetch_fear_greed(self) -> dict:
        try:
            resp = requests.get("https://api.alternative.me/fng/", timeout=10)
            data = resp.json().get("data", [{}])[0]
            val = int(data.get("value", 50))
            return {"value": val, "classification": data.get("value_classification", "Neutral")}
        except:
            return {"value": 50, "classification": "Neutral"}

    def _calculate_overall_sentiment(self, news_sent, coin_info, fg) -> dict:
        # News weight is high
        news_score = (news_sent["avg_score"] + 1) * 50
        fg_score = fg["value"]
        
        # CoinGecko sentiment if available
        cg_score = coin_info.get("sentiment_votes_up_percentage", 50) if coin_info else 50
        
        weighted = (news_score * 0.6) + (fg_score * 0.2) + (cg_score * 0.2)
        
        return {
            "score": round(weighted),
            "label": "Pozitif" if weighted > 65 else "Negatif" if weighted < 35 else "Nötr",
            "emoji": "🟢" if weighted > 65 else "🔴" if weighted < 35 else "🟡"
        }

    def _get_cache(self, key):
        if key in self._cache:
            data, ts = self._cache[key]
            if time.time() - ts < self._cache_ttl: return data
        return None

    def _set_cache(self, key, data):
        self._cache[key] = (data, time.time())
