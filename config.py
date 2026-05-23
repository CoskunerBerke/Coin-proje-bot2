"""
Kripto Coin Analiz Uygulaması — Eksiksiz Konfigürasyon
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

SETTINGS_FILE = "persistent_settings.json"
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")

def save_app_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)

def load_app_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

# ─── API Keys ───────────────────────────────────────────────────────────────
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")

# ─── Bot Ayarları ───────────────────────────────────────────────────────────
AI_MODE = "LEARN_AND_APPLY"  # LEARN_AND_APPLY = öğrenmeye devam et + öğrendiklerini uygula (kümülatif)

# ─── Institutional-Grade Deterministik Eşikler ─────────────────────────────
# Bu kurallar subjektif prompt ifadelerini ("healthy volatility", "strong confidence")
# sayısal, tekrarlanabilir ve deterministik filtrelere dönüştürür.
INSTITUTIONAL_THRESHOLDS = {
    "funding_overcrowded_long": 0.04,    # Funding > 0.04 → Long tarafı aşırı kalabalık
    "funding_overcrowded_short": -0.04,  # Funding < -0.04 → Short tarafı aşırı kalabalık
    "oi_spike_threshold": 10.0,          # OI değişimi > %10 → Squeeze riski
    "atr_anomaly_multiplier": 2.5,       # ATR > 20-periyot ortalamasının 2.5 katı
    "volume_min_ratio": 0.05,            # Volume ratio < 0.05 → Yetersiz hacim (AGRESİF)
    "min_rr_ratio": 1.0,                 # Risk/Ödül < 1:1.0 → İşlem yasak (AGRESİF ama makul)
    "min_direction_vote": 0.03,          # Yön oyu < 0.03 → Kararsız
    "min_ev_threshold": -0.10,           # EV <= -0.10 → Negatif beklenen değer (AGRESİF ama kontrollü)
    "min_quality_score": 20,             # Kalite < 20/100 → Düşük kalite (AGRESİF ama çöpü filtrele)
    "max_daily_consecutive_losses": 3,   # Gün içi üst üste 3 stop → O gün yasak
    "max_daily_loss_pct": 3.0,           # Günlük toplam zarar > %3 → O gün yasak
}

BOT_SETTINGS = {
    "is_active": True,
    "simulation_mode": True,
    "starting_balance": 1000.0,
    "min_confidence": 15,              # 🔥 AGRESİF: Daha düşük güven eşiği
    "risk_per_trade": 0.06,            # 🔥 AGRESİF: Daha büyük pozisyon (%6)
    "leverage": 5,
    "max_active_trades": 10,           # 🎯 10 eş zamanlı işlem — fırsatları kaçırma
    "weak_momentum_profit_take_pct": 1.50,  # 🎯 Zayıf sinyalde hızlı çık (%1.5)
    "tp1_profit_take_pct": 2.00,       # 🎯 Erken kâr al (%2) — sık kazanç
    "trailing_activation_pct": 2.00,   # 🎯 Kârı hızlı kilitle (%2)
    "signal_invalidation_threshold": 85.0,
}

# ─── Aktif Taranacak Coinler ────────────────────────────────────────────────
# Sadece bu listedeki coinler taranır ve trade açılır.
# SUPPORTED_COINS'den bağımsız — istediğin zaman değiştir.
ACTIVE_COINS = ["BTC", "SOL"]

TELEGRAM_SETTINGS = {
    "token": os.getenv("TELEGRAM_TOKEN", ""),
    "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    "data_chat_id": os.getenv("TELEGRAM_DATA_CHAT_ID", ""),
    "is_active": False
}

# Tüm desteklenen coinler (referans sözlüğü, UI vs. için kalır)
SUPPORTED_COINS = {
    "BTC": {"name": "Bitcoin", "coingecko_id": "bitcoin", "symbol": "BTC/USDT"},
    "SOL": {"name": "Solana", "coingecko_id": "solana", "symbol": "SOL/USDT"},
}

TIMEFRAMES = {
    "1m": {"label": "1 Dakika", "minutes": 1},
    "5m": {"label": "5 Dakika", "minutes": 5},
    "15m": {"label": "15 Dakika", "minutes": 15},
    "1h": {"label": "1 Saat", "minutes": 60},
}

# ─── Teknik Analiz Parametreleri (FULL) ─────────────────────────────────────
TA_PARAMS = {
    "rsi_period": 14,
    "stoch_rsi_period": 14,
    "stoch_rsi_smooth1": 3,
    "stoch_rsi_smooth2": 3,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "ema_periods": [9, 21, 50, 200],
    "bb_period": 20,
    "bb_std": 2,
    "atr_period": 14,
    "adx_period": 14,
    "candle_limit": 200,
}

# ─── Sinyal Ağırlıkları ─────────────────────────────────────────────────────
SIGNAL_WEIGHTS = {
    "rsi": 0.12, "macd": 0.12, "ema_crossover": 0.18, "bollinger": 0.08,
    "trend_adx": 0.10, "volume": 0.10, "sentiment": 0.25, "candle_pattern": 0.05,
}

# ─── Risk Seviyeleri ────────────────────────────────────────────────────────
RISK_LEVELS = {
    (0, 25): {"label": "Düşük", "color": "#4CAF50", "emoji": "🟢"},
    (25, 50): {"label": "Orta", "color": "#FFC107", "emoji": "🟡"},
    (50, 75): {"label": "Yüksek", "color": "#FF9800", "emoji": "🟠"},
    (75, 101): {"label": "Çok Yüksek", "color": "#F44336", "emoji": "🔴"},
}

RSS_FEEDS = [
    "https://cointelegraph.com/rss", 
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cryptopotato.com/tr/feed/",
    "https://cryptopotato.com/feed/",
    "https://tr.investing.com/rss/news_301.rss",
    "https://uzmancoin.com/feed/"
]
DISCLAIMER = "⚠️ Bu analiz yatırım tavsiyesi değildir. Bot kullanımı finansal risk içerir."
