"""
Kripto Coin Analiz Uygulaması — Gelişmiş Coin-Specific Memory & DNA Profiling Modülü (C-Speed NumPy)
"""

import os
import json
import numpy as np
from datetime import datetime, timezone, timedelta

# Turkey Time (UTC+3) Helper
tr_tz = timezone(timedelta(hours=3))
def get_now_tr():
    return datetime.now(tr_tz).replace(tzinfo=None)

# Hafıza Dosyası
MEMORY_FILE = "coin_trade_memory.json"

# Coin'lere Özel Varsayılan DNA Profilleri (Soğuk Başlangıç Çözümü)
COIN_DEFAULT_DNA = {
    "BTC": {
        "trendiness": 0.85, "fakeout_prob": 0.15, "volatility": 0.40,
        "manipulation": 0.10, "liquidity": 0.95, "funding_sensitivity": 0.30,
        "whale_dependency": 0.20, "btc_correlation": 1.00,
        "mean_reversion": 0.30, "breakout_reliability": 0.80,
        "opt_weights": {"rsi": 0.08, "macd": 0.22, "ema_crossover": 0.25, "bollinger": 0.08, "trend_adx": 0.15, "volume": 0.12, "sentiment": 0.05, "candle_pattern": 0.05}
    },
    "ETH": {
        "trendiness": 0.80, "fakeout_prob": 0.20, "volatility": 0.50,
        "manipulation": 0.15, "liquidity": 0.90, "funding_sensitivity": 0.40,
        "whale_dependency": 0.25, "btc_correlation": 0.88,
        "mean_reversion": 0.40, "breakout_reliability": 0.75,
        "opt_weights": {"rsi": 0.10, "macd": 0.20, "ema_crossover": 0.20, "bollinger": 0.10, "trend_adx": 0.12, "volume": 0.14, "sentiment": 0.08, "candle_pattern": 0.06}
    },
    "SOL": {
        "trendiness": 0.90, "fakeout_prob": 0.25, "volatility": 0.75,
        "manipulation": 0.30, "liquidity": 0.80, "funding_sensitivity": 0.60,
        "whale_dependency": 0.40, "btc_correlation": 0.70,
        "mean_reversion": 0.30, "breakout_reliability": 0.85,
        "opt_weights": {"rsi": 0.20, "macd": 0.12, "ema_crossover": 0.12, "bollinger": 0.06, "trend_adx": 0.10, "volume": 0.25, "sentiment": 0.10, "candle_pattern": 0.05}
    },
    "DOGE": {
        "trendiness": 0.50, "fakeout_prob": 0.45, "volatility": 0.95,
        "manipulation": 0.80, "liquidity": 0.65, "funding_sensitivity": 0.80,
        "whale_dependency": 0.85, "btc_correlation": 0.50,
        "mean_reversion": 0.65, "breakout_reliability": 0.40,
        "opt_weights": {"rsi": 0.25, "macd": 0.05, "ema_crossover": 0.05, "bollinger": 0.12, "trend_adx": 0.05, "volume": 0.20, "sentiment": 0.20, "candle_pattern": 0.08}
    },
    "XRP": {
        "trendiness": 0.40, "fakeout_prob": 0.60, "volatility": 0.70,
        "manipulation": 0.60, "liquidity": 0.85, "funding_sensitivity": 0.50,
        "whale_dependency": 0.50, "btc_correlation": 0.60,
        "mean_reversion": 0.80, "breakout_reliability": 0.35,
        "opt_weights": {"rsi": 0.30, "macd": 0.05, "ema_crossover": 0.05, "bollinger": 0.20, "trend_adx": 0.05, "volume": 0.15, "sentiment": 0.10, "candle_pattern": 0.10}
    },
    "AVAX": {
        "trendiness": 0.75, "fakeout_prob": 0.30, "volatility": 0.80,
        "manipulation": 0.35, "liquidity": 0.70, "funding_sensitivity": 0.65,
        "whale_dependency": 0.45, "btc_correlation": 0.78,
        "mean_reversion": 0.45, "breakout_reliability": 0.70,
        "opt_weights": {"rsi": 0.15, "macd": 0.15, "ema_crossover": 0.15, "bollinger": 0.10, "trend_adx": 0.10, "volume": 0.18, "sentiment": 0.12, "candle_pattern": 0.05}
    },
    "BNB": {
        "trendiness": 0.70, "fakeout_prob": 0.20, "volatility": 0.45,
        "manipulation": 0.20, "liquidity": 0.85, "funding_sensitivity": 0.35,
        "whale_dependency": 0.30, "btc_correlation": 0.80,
        "mean_reversion": 0.50, "breakout_reliability": 0.72,
        "opt_weights": {"rsi": 0.12, "macd": 0.18, "ema_crossover": 0.18, "bollinger": 0.12, "trend_adx": 0.10, "volume": 0.12, "sentiment": 0.12, "candle_pattern": 0.06}
    },
    "PEPE": {
        "trendiness": 0.60, "fakeout_prob": 0.40, "volatility": 0.98,
        "manipulation": 0.75, "liquidity": 0.85, "funding_sensitivity": 0.85,
        "whale_dependency": 0.80, "btc_correlation": 0.45,
        "mean_reversion": 0.55, "breakout_reliability": 0.45,
        "opt_weights": {"rsi": 0.22, "macd": 0.10, "ema_crossover": 0.05, "bollinger": 0.10, "trend_adx": 0.05, "volume": 0.23, "sentiment": 0.20, "candle_pattern": 0.05}
    },
    "SUI": {
        "trendiness": 0.88, "fakeout_prob": 0.25, "volatility": 0.78,
        "manipulation": 0.35, "liquidity": 0.80, "funding_sensitivity": 0.55,
        "whale_dependency": 0.45, "btc_correlation": 0.72,
        "mean_reversion": 0.35, "breakout_reliability": 0.82,
        "opt_weights": {"rsi": 0.10, "macd": 0.18, "ema_crossover": 0.22, "bollinger": 0.08, "trend_adx": 0.15, "volume": 0.15, "sentiment": 0.07, "candle_pattern": 0.05}
    },
    "RENDER": {
        "trendiness": 0.82, "fakeout_prob": 0.28, "volatility": 0.80,
        "manipulation": 0.40, "liquidity": 0.75, "funding_sensitivity": 0.60,
        "whale_dependency": 0.50, "btc_correlation": 0.75,
        "mean_reversion": 0.40, "breakout_reliability": 0.78,
        "opt_weights": {"rsi": 0.12, "macd": 0.16, "ema_crossover": 0.18, "bollinger": 0.10, "trend_adx": 0.12, "volume": 0.15, "sentiment": 0.12, "candle_pattern": 0.05}
    },
    "PHB": {
        "trendiness": 0.72, "fakeout_prob": 0.38, "volatility": 0.95,
        "manipulation": 0.70, "liquidity": 0.55, "funding_sensitivity": 0.75,
        "whale_dependency": 0.75, "btc_correlation": 0.58,
        "mean_reversion": 0.48, "breakout_reliability": 0.62,
        "opt_weights": {"rsi": 0.20, "macd": 0.12, "ema_crossover": 0.10, "bollinger": 0.12, "trend_adx": 0.08, "volume": 0.20, "sentiment": 0.12, "candle_pattern": 0.06}
    },
    "FET": {
        "trendiness": 0.80, "fakeout_prob": 0.30, "volatility": 0.82,
        "manipulation": 0.45, "liquidity": 0.82, "funding_sensitivity": 0.65,
        "whale_dependency": 0.52, "btc_correlation": 0.74,
        "mean_reversion": 0.42, "breakout_reliability": 0.75,
        "opt_weights": {"rsi": 0.12, "macd": 0.16, "ema_crossover": 0.16, "bollinger": 0.10, "trend_adx": 0.12, "volume": 0.16, "sentiment": 0.12, "candle_pattern": 0.06}
    },
    "COMP": {
        "trendiness": 0.62, "fakeout_prob": 0.32, "volatility": 0.68,
        "manipulation": 0.35, "liquidity": 0.70, "funding_sensitivity": 0.45,
        "whale_dependency": 0.40, "btc_correlation": 0.78,
        "mean_reversion": 0.68, "breakout_reliability": 0.58,
        "opt_weights": {"rsi": 0.22, "macd": 0.10, "ema_crossover": 0.08, "bollinger": 0.18, "trend_adx": 0.08, "volume": 0.12, "sentiment": 0.10, "candle_pattern": 0.12}
    },
    "NEAR": {
        "trendiness": 0.85, "fakeout_prob": 0.24, "volatility": 0.76,
        "manipulation": 0.30, "liquidity": 0.78, "funding_sensitivity": 0.58,
        "whale_dependency": 0.42, "btc_correlation": 0.84,
        "mean_reversion": 0.38, "breakout_reliability": 0.80,
        "opt_weights": {"rsi": 0.10, "macd": 0.18, "ema_crossover": 0.22, "bollinger": 0.08, "trend_adx": 0.15, "volume": 0.12, "sentiment": 0.10, "candle_pattern": 0.05}
    },
    "LINK": {
        "trendiness": 0.78, "fakeout_prob": 0.22, "volatility": 0.58,
        "manipulation": 0.22, "liquidity": 0.88, "funding_sensitivity": 0.40,
        "whale_dependency": 0.35, "btc_correlation": 0.86,
        "mean_reversion": 0.45, "breakout_reliability": 0.74,
        "opt_weights": {"rsi": 0.12, "macd": 0.18, "ema_crossover": 0.20, "bollinger": 0.12, "trend_adx": 0.12, "volume": 0.12, "sentiment": 0.08, "candle_pattern": 0.06}
    }
}

class CoinIntelligenceManager:
    def __init__(self):
        self.memory_file = MEMORY_FILE
        self.memory = self._load_memory()

    def _load_memory(self) -> dict:
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_memory(self):
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, indent=4)
        except Exception as e:
            print(f"Error saving coin trade memory: {e}")

    def log_completed_trade(self, coin: str, trade: dict):
        """Kapanan bir işlemi belleğe ve vektör havuzuna kaydeder (Maksimum 100 işlem/coin)"""
        if coin not in self.memory:
            self.memory[coin] = []

        # Bellek vektörünü oluştur (RSI, MACD, ATR_pct, Volume_climax, Funding_rate, Trend_score)
        ml_data = trade.get("ml_data", {})
        
        # 6-Boyutlu Hafif Karar Vektörü (Öğrenme ve Eşleştirme İçin)
        vector = [
            float(ml_data.get("rsi", 0.0)),
            float(ml_data.get("macd", 0.0)),
            float(ml_data.get("ema_crossover", 0.0)),
            float(ml_data.get("bollinger", 0.0)),
            float(ml_data.get("trend_adx", 0.0)),
            float(ml_data.get("volume", 0.0))
        ]

        # 🧠 Strict AI Meta-Labeling (Yapay Zeka Etiketleme)
        # Sadece gerçek başarılar (TP1 vurması, net >%1 kâr, yüksek R-Multiple veya yeni momentum çıkışları) outcome=1 olur.
        pnl_usdt = float(trade.get("pnl_usdt", 0.0))
        pnl_yuzde = float(trade.get("pnl_yuzde", 0.0))
        r_multiple = float(trade.get("realized_R_multiple", 0.0))
        tp1_hit = bool(trade.get("tp1_hit", False))
        exit_reason = trade.get("exit_reason", "")

        outcome = 1 if (
            tp1_hit or 
            r_multiple >= 0.75 or
            pnl_yuzde >= 1.0
        ) else 0

        # Hafıza elemanı
        memory_item = {
            "timestamp": get_now_tr().strftime("%Y-%m-%d %H:%M:%S"),
            "regime": trade.get("regime", "RANGE"),
            "direction": trade.get("yon", "LONG"),
            "vector": vector,
            "outcome": outcome,
            "pnl_usdt": pnl_usdt,
            "risked_usdt": float(trade.get("miktar_usdt", 0.0)) * 0.05, # %5 riske edilen tutar
            "duration_minutes": float(trade.get("duration_minutes", 15.0)),
            "exit_reason": exit_reason or trade.get("neden", "Unknown")
        }

        self.memory[coin].append(memory_item)
        
        # Bellek Sürgülü Penceresi (Sliding Window - Max 100 trade) to prevent memory bloating
        if len(self.memory[coin]) > 100:
            self.memory[coin] = self.memory[coin][-100:]

        self._save_memory()

    def get_coin_dna(self, coin: str) -> dict:
        """Coin'in canlı DNA profilini döndürür. Hafıza boşsa varsayılana döner (Cold Start koruması)."""
        dna = COIN_DEFAULT_DNA.get(coin, COIN_DEFAULT_DNA["BTC"]).copy()
        
        coin_history = self.memory.get(coin, [])
        if len(coin_history) < 10:
            return dna # Cold start

        # Geçmişe göre DNA metriklerini adapte et
        total = len(coin_history)
        losses = len([t for t in coin_history if t["outcome"] == 0])
        
        # Fakeout Probability: Fiyatın kâr yönünde gidip sonradan SL olma oranı
        fakeouts = len([t for t in coin_history if t["outcome"] == 0 and t.get("exit_reason") == "SL" and t.get("pnl_usdt", 0) > -0.2])
        dna["fakeout_prob"] = round((fakeouts / max(losses, 1)) * 0.4 + dna["fakeout_prob"] * 0.6, 2)
        
        # Mean Reversion vs Breakout adaptasyonu
        wins = [t for t in coin_history if t["outcome"] == 1]
        if wins:
            # Karşıt trend işlemlerinin başarı oranı
            mr_count = len([t for t in wins if t["exit_reason"] == "TP" and t["direction"] != t["regime"]])
            dna["mean_reversion"] = round((mr_count / len(wins)) * 0.5 + dna["mean_reversion"] * 0.5, 2)

        return dna

    def get_adaptive_weights(self, coin: str) -> dict:
        """Coine özel canlı indikatör ağırlıklarını verir."""
        dna = self.get_coin_dna(coin)
        return dna.get("opt_weights", COIN_DEFAULT_DNA["BTC"]["opt_weights"])

    def calculate_similarity_edge(self, coin: str, current_vector: list, regime: str) -> dict:
        """Gelen sinyal vektörünü, coinin geçmiş hafızasındaki rejim uyumlu işlemlerle Cosine & Euclidean olarak arar."""
        coin_history = self.memory.get(coin, [])
        
        # Rejim uyumlu ve ML verisi olan geçmiş işlemleri filtrele
        regime_history = [t for t in coin_history if t.get("regime") == regime]
        
        # Eğer bu rejimde yeterli işlem yoksa genel hafızaya bak
        if len(regime_history) < 3:
            regime_history = coin_history

        # Cold Start Fallback
        if len(regime_history) < 3:
            return {
                "similarity_score": 1.0, 
                "historical_expectancy": 0.1, 
                "win_rate": 0.55,
                "matches_count": 0
            }

        # Vektörleri matrisleştir (C-Speed Vectorized NumPy)
        history_vectors = np.array([t["vector"] for t in regime_history])
        target_vector = np.array(current_vector)

        # ⏳ Recency-Weighted Decay (Üstel Zaman Unutması)
        # Yeni işlemlerin ağırlığı 1.0, eski işlemlerinki 0.3'e kadar üstel decay formülüyle azalır
        now = get_now_tr()
        decay_weights = []
        for t in regime_history:
            try:
                t_date = datetime.strptime(t["timestamp"], "%Y-%m-%d %H:%M:%S")
                days_diff = max((now - t_date).days, 0)
                # Lambda = 0.05 (14 gün yarılanma ömrü)
                weight = np.exp(-0.05 * days_diff)
                decay_weights.append(max(weight, 0.30))
            except:
                decay_weights.append(0.50)
        decay_weights = np.array(decay_weights)

        # 📐 Cosine Similarity Hesaplama
        dot_products = np.dot(history_vectors, target_vector)
        norms_history = np.linalg.norm(history_vectors, axis=1)
        norm_target = np.linalg.norm(target_vector)
        
        # Sıfır bölme koruması
        norms_history = np.where(norms_history == 0, 1e-9, norms_history)
        norm_target = 1e-9 if norm_target == 0 else norm_target

        cosine_similarities = dot_products / (norms_history * norm_target)
        # Sınırla [-1, 1]
        cosine_similarities = np.clip(cosine_similarities, -1.0, 1.0)
        
        # Kosinüs Benzerliğini %0-100 arasına dönüştür
        similarity_percentages = (cosine_similarities + 1.0) / 2.0

        # En yakın 3 komşuyu bul (Nearest Neighbors)
        top_indices = np.argsort(similarity_percentages)[-3:]
        
        best_similarities = similarity_percentages[top_indices]
        best_outcomes = np.array([regime_history[i]["outcome"] for i in top_indices])
        best_pnls = np.array([regime_history[i]["pnl_usdt"] for i in top_indices])
        best_weights = decay_weights[top_indices]

        # Ağırlıklı Win Rate ve Expectancy hesabı
        weighted_win_rate = float(np.sum(best_outcomes * best_weights) / np.sum(best_weights))
        weighted_expectancy = float(np.sum(best_pnls * best_weights) / np.sum(best_weights))
        avg_similarity = float(np.mean(best_similarities))

        return {
            "similarity_score": avg_similarity,
            "historical_expectancy": weighted_expectancy,
            "win_rate": weighted_win_rate,
            "matches_count": len(top_indices)
        }

    def get_historical_edge(self, coin: str, regime: str) -> dict:
        """Coin'in o rejimdeki anlık kâr beklentisini ve edge katsayısını hesaplar."""
        coin_history = self.memory.get(coin, [])
        regime_history = [t for t in coin_history if t.get("regime") == regime]

        if len(regime_history) < 5:
            # Yetersiz veri durumunda coinin global profiline ve rejim uyumuna bak
            dna = self.get_coin_dna(coin)
            # Rejime göre default edge çarpanı üret
            edge_val = 1.0
            if regime in ["STRONG_BULL", "STRONG_BEAR"]:
                edge_val = 1.2 * dna["trendiness"]
            elif regime == "RANGE":
                edge_val = 1.1 * dna["mean_reversion"]
            elif regime == "HIGH VOLATILITY":
                edge_val = 0.9 * dna["breakout_reliability"]
                
            return {
                "edge_multiplier": edge_val,
                "drawdown_risk": "Düşük",
                "expectancy": 0.05,
                "win_rate": 0.55
            }

        # İstatistiksel Edge Hesaplamaları
        wins = [t for t in regime_history if t["outcome"] == 1]
        losses = [t for t in regime_history if t["outcome"] == 0]
        
        win_rate = len(wins) / len(regime_history)
        avg_win = np.mean([t["pnl_usdt"] for t in wins]) if wins else 0.0
        avg_loss = abs(np.mean([t["pnl_usdt"] for t in losses])) if losses else 0.1
        
        # Matematiksel Expectancy (Beklenen Değer)
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        # Max Drawdown Takibi
        pnls = [t["pnl_usdt"] for t in regime_history]
        cumulative = np.cumsum(pnls)
        peak = np.maximum.accumulate(cumulative)
        drawdowns = peak - cumulative
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
        
        dd_risk = "Düşük"
        if max_dd > 5.0: dd_risk = "Çok Yüksek"
        elif max_dd > 2.0: dd_risk = "Yüksek"
        elif max_dd > 1.0: dd_risk = "Orta"

        # Edge Çarpanı Üret
        edge_multiplier = 1.0 + (expectancy * 2.0)
        # Sınırla [0.15, 1.8] (AGRESİF: alt limit 0.3→0.15)
        edge_multiplier = np.clip(edge_multiplier, 0.15, 1.8)

        return {
            "edge_multiplier": float(edge_multiplier),
            "drawdown_risk": dd_risk,
            "expectancy": float(expectancy),
            "win_rate": float(win_rate)
        }

    def evaluate_final_intelligence(self, coin: str, current_vector: list, signal_quality: float, regime: str) -> dict:
        """CurrentSignalQuality * CoinHistoricalEdge * SetupSimilarity oylamasıyla Final Kararı üretir."""
        # 1. Similarity Engine'den benzerlik kontrolü yap
        sim_res = self.calculate_similarity_edge(coin, current_vector, regime)
        
        # 2. Historical Edge'i çıkar
        edge_res = self.get_historical_edge(coin, regime)
        
        # 3. Coin DNA Fakeout risk cezasını hesapla
        dna = self.get_coin_dna(coin)
        fakeout_penalty = 1.0 - (dna["fakeout_prob"] * 0.5) # Fakeout olasılığı yüksekse çarpan düşer
        
        # 🧪 Final Çarpımsal Kuantum Skoru (Multi-Factor Multiplicative Gating)
        final_score = signal_quality * sim_res["similarity_score"] * edge_res["edge_multiplier"] * fakeout_penalty
        
        # 🛡️ Karar Filtreleri
        is_approved = True
        reject_reason = ""
        
        # Eğer beklenen değer veya benzerlik çok düşükse trade'i engelle (No-Trade Intelligence)
        if sim_res["win_rate"] < 0.25 and sim_res["matches_count"] >= 5:
            is_approved = False
            reject_reason = f"Hafıza Uyumsuzluğu (Benzer setup geçmiş başarı oranı: %{sim_res['win_rate']*100:.0f})"
        elif edge_res["edge_multiplier"] < 0.30:
            is_approved = False
            reject_reason = f"Düşük Tarihsel Edge (Çarpan: {edge_res['edge_multiplier']:.2f})"
        elif dna["fakeout_prob"] > 0.75 and regime == "RANGE":
            is_approved = False
            reject_reason = "Yüksek Fakeout Riski (Coine özel DNA engeli)"
        elif final_score < 8.0: # AGRESİF: Minimum eşik 15→8
            is_approved = False
            reject_reason = f"Düşük Kuantum Zeka Skoru ({final_score:.1f})"

        return {
            "final_score": float(final_score),
            "is_approved": is_approved,
            "reject_reason": reject_reason,
            "similarity_score": sim_res["similarity_score"],
            "edge_multiplier": edge_res["edge_multiplier"],
            "fakeout_prob": dna["fakeout_prob"]
        }

    def get_counterfactual_bias(self, coin: str) -> dict:
        """Counterfactual analizden öğrenme bias'ı çeker.
        
        Returns:
            dict: {
                'early_exit_ratio': float,
                'missed_profit_ratio': float,
                'exit_patience_multiplier': float,
                'entry_courage_multiplier': float,
                'total_lessons': int
            }
        """
        try:
            from counterfactual_analyzer import CounterfactualAnalyzer
            cf = CounterfactualAnalyzer()
            return cf.get_counterfactual_bias(coin)
        except Exception:
            return {
                "early_exit_ratio": 0.0,
                "missed_profit_ratio": 0.0,
                "exit_patience_multiplier": 1.0,
                "entry_courage_multiplier": 1.0,
                "total_lessons": 0
            }
