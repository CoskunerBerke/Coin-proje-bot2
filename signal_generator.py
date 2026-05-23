"""
Kripto Coin Analiz Uygulaması — Sinyal Üretici ve FinML Meta-Labeling Modülü (signal_generator.py)
"""

import json
import os
import math
import time
import numpy as np
from config import SIGNAL_WEIGHTS, RISK_LEVELS, DISCLAIMER, AI_MODE, INSTITUTIONAL_THRESHOLDS
from data_fetcher import DataFetcher
from log_manager import add_log

class QuantMetaFilter:
    """NumPy tabanlı, sıfır kütüphane bağımlılıklı, yüksek hızlı Logistic Regression Sınıflandırıcı (Model 2)."""
    def __init__(self):
        self.weights = None
        self.bias = 0.0
        self.mean = None
        self.std = None
        
    def train(self, X, y, lr=0.05, epochs=1000):
        if len(X) < 5:
            return
        
        try:
            X = np.array(X, dtype=np.float32)
            y = np.array(y, dtype=np.float32)
            
            self.mean = np.mean(X, axis=0)
            self.std = np.std(X, axis=0)
            self.std[self.std == 0.0] = 1.0
            X_norm = (X - self.mean) / self.std
            
            n_samples, n_features = X.shape
            self.weights = np.zeros(n_features, dtype=np.float32)
            self.bias = 0.0
            
            def sigmoid(z):
                return 1.0 / (1.0 + np.exp(-np.clip(z, -15.0, 15.0)))
                
            for _ in range(epochs):
                model_predictions = sigmoid(np.dot(X_norm, self.weights) + self.bias)
                dw = (1.0 / n_samples) * np.dot(X_norm.T, (model_predictions - y))
                db = (1.0 / n_samples) * np.sum(model_predictions - y)
                
                self.weights -= lr * dw
                self.bias -= lr * db
        except Exception as err:
            add_log(f"⚠️ Meta-Filter Model 2 eğitim hatası: {str(err)}")
            
    def predict_proba(self, x) -> float:
        if self.weights is None or self.mean is None or self.std is None:
            return 0.90
            
        try:
            x = np.array(x, dtype=np.float32)
            x_norm = (x - self.mean) / self.std
            z = np.dot(x_norm, self.weights) + self.bias
            prob = float(1.0 / (1.0 + np.exp(-np.clip(z, -15.0, 15.0))))
            return prob
        except:
            return 0.90

class ExpertModel:
    """Tek bir uzman kuant modelinin temel davranış şablonu."""
    def __init__(self, name: str):
        self.name = name
        self.confidence = 50.0  # 0 to 100
        self.direction = "NEUTRAL" # LONG, SHORT, NEUTRAL
        self.raw_score = 0.0     # -1 to +1

class SignalGenerator:
    """Gelişmiş FinML Ensemble AI, 6-Tier Rejim ve Monte Carlo tabanlı olasılıksal sinyal motoru."""

    def __init__(self):
        from coin_intelligence import CoinIntelligenceManager
        self.coin_intel = CoinIntelligenceManager()
        self.weights = SIGNAL_WEIGHTS.copy()
        self.fetcher = DataFetcher()
        self.meta_filter = QuantMetaFilter()
        
    def _calculate_weights_for_batch(self, batch):
        if not batch:
            return self.weights.copy()
            
        total_trades = len(batch)
        indicator_utilities = {k: 0.0 for k in SIGNAL_WEIGHTS.keys()}
        
        for t in batch:
            # Clipped realized R
            realized_r = t.get("realized_R_multiple", 0.0)
            if realized_r == 0.0:
                pnl_pct = t.get("pnl_yuzde", 0.0)
                leverage = t.get("kaldirac", 1.0)
                realized_r = pnl_pct / (leverage * 100.0) if leverage > 0 else pnl_pct / 100.0
                
            reward_r = max(-2.0, min(3.0, realized_r))
            direction_mult = 1 if t.get("yon") == "LONG" else -1
            
            for key, score in t["ml_data"].items():
                if key in indicator_utilities:
                    # Attribution (Free-rider protection)
                    signal_supported = (score * direction_mult) > 0
                    if signal_supported:
                        indicator_utilities[key] += reward_r * abs(score)
                        
        new_weights = self.weights.copy()
        learning_rate = 0.03
        for key, utility in indicator_utilities.items():
            avg_utility = utility / total_trades
            new_weights[key] += avg_utility * learning_rate
            new_weights[key] = max(0.02, min(0.45, new_weights[key]))
            
        total_weight = sum(new_weights.values())
        return {k: round(v / total_weight, 3) for k, v in new_weights.items()}

    def _get_features_array(self, ml_data, entry_features, direction: str = "LONG") -> list:
        # Base features
        rsi = float(ml_data.get("rsi", 0.0))
        macd = float(ml_data.get("macd", 0.0))
        ema = float(ml_data.get("ema_crossover", 0.0))
        vol = float(ml_data.get("volume", 0.0))
        sent = float(ml_data.get("sentiment", 0.0))
        spread = float(entry_features.get("spread", 0.02))
        funding = float(entry_features.get("funding", 0.0))
        oi_delta = float(entry_features.get("oi_delta", 0.0))
        vol_regime = float(entry_features.get("volatility_regime", 1.0))
        
        # BTC Compass direction alignment feature
        btc_dir = entry_features.get("BTC direction", entry_features.get("btc_direction", "NEUTRAL"))
        if btc_dir == "NEUTRAL":
            btc_align = 0.0
        elif btc_dir == direction:
            btc_align = 1.0
        else:
            btc_align = -1.0
        
        # Yön Hizalaması (Yön bağımsız eğitim için)
        if direction == "SHORT":
            rsi = 100.0 - rsi
            macd = -macd
            ema = -ema
            sent = 100.0 - sent
            funding = -funding
            
        # Etkileşim Öznitelikleri (Interaction features)
        inter1 = rsi * ema             # Momentum * Crossover
        inter2 = vol * ema             # Volume * Crossover strength
        inter3 = funding * oi_delta    # Position crowding dynamics
        inter4 = vol_regime * spread   # Volatility/liquidity friction
        inter5 = sent * macd           # News sentiment * momentum convergence
        
        return [
            rsi, macd, ema, vol, sent, spread, funding, oi_delta, vol_regime,
            btc_align, inter1, inter2, inter3, inter4, inter5
        ]

    def _get_model_stats(self) -> tuple:
        try:
            if not os.path.exists("bot_trades.json"):
                return 0.0, 0.50
            with open("bot_trades.json", "r", encoding="utf-8") as f:
                trades = json.load(f)
            
            # 1. Drawdown hesabı
            balance = 1000.0
            history = [balance]
            closed_trades = [t for t in trades if t.get("durum") == "KAPALI"]
            closed_trades.sort(key=lambda x: x.get("kapanis_tarihi", ""))
            for t in closed_trades:
                balance += t.get("pnl_usdt", 0.0)
                history.append(balance)
            peak = max(history)
            current = balance
            drawdown = (peak - current) / peak if peak > 0 else 0.0
            
            # 2. Model 2 Win Rate hesabı (Eşik belirlemede referans)
            ml_trades = [t for t in closed_trades if "ml_data" in t]
            y_labels = []
            for t in ml_trades[-100:]:
                realized_r = t.get("realized_R_multiple", 0.0)
                if realized_r == 0.0:
                    pnl_pct = t.get("pnl_yuzde", 0.0)
                    leverage = t.get("kaldirac", 1.0)
                    realized_r = pnl_pct / (leverage * 100.0) if leverage > 0 else pnl_pct / 100.0
                
                mae = t.get("max_adverse_excursion", 1.0)
                mfe = t.get("max_favorable_excursion", 0.0)
                mfe_mae_ratio = mfe / max(0.1, mae)
                
                exit_reason = t.get("exit_reason", "")
                exit_eff = 1.0 if any(r in exit_reason for r in ["TP", "TS", "AI_KAR"]) else 0.2
                
                holding_time = t.get("holding_time", 0.0)
                duration_penalty = min(0.2, (holding_time / 1440.0) * 0.10)
                
                quality_score = (realized_r * 0.45) + (mfe_mae_ratio * 0.20) + (exit_eff * 0.25) - duration_penalty
                if 0.45 < quality_score < 0.55:
                    continue
                outcome = 1.0 if quality_score >= 0.55 else 0.0
                y_labels.append(outcome)
                
            win_rate = sum(y_labels) / len(y_labels) if y_labels else 0.50
            return max(0.0, drawdown), win_rate
        except:
            return 0.0, 0.50

    def update_weights_from_history(self):
        """Geçmiş işlemleri analiz ederek indikatör ağırlıklarını ve Model 2 Meta-Filtresini optimize eder."""
        try:
            if not os.path.exists("bot_trades.json"): return
            with open("bot_trades.json", "r", encoding="utf-8") as f:
                trades = json.load(f)
        except: return

        ml_trades = [t for t in trades if t.get("durum") == "KAPALI" and "ml_data" in t]
        if len(ml_trades) < 20: return
        
        # 📊 1. Çoklu Pencere İndikatör Ağırlıkları Optimizasyonu
        w_short = self._calculate_weights_for_batch(ml_trades[-50:])
        w_medium = self._calculate_weights_for_batch(ml_trades[-200:])
        w_long = self._calculate_weights_for_batch(ml_trades[-1000:])
        
        combined_weights = {}
        for key in SIGNAL_WEIGHTS.keys():
            combined_weights[key] = (0.50 * w_short[key]) + (0.30 * w_medium[key]) + (0.20 * w_long[key])
            
        total_weight = sum(combined_weights.values())
        self.weights = {k: round(v / total_weight, 3) for k, v in combined_weights.items()}
        
        # 🧠 2. MODEL 2: Meta-Labeling Eğitimi (Expectancy Quality Score Target)
        X = []
        y = []
        batch = ml_trades[-100:]
        for t in batch:
            ml_data = t.get("ml_data", {})
            entry_features = t.get("entry_features", {})
            
            features = self._get_features_array(ml_data, entry_features, t.get("yon", "LONG"))
            
            # Expectancy Quality Score labeling
            mae = t.get("max_adverse_excursion", 1.0)
            mfe = t.get("max_favorable_excursion", 0.0)
            mfe_mae_ratio = mfe / max(0.1, mae)
            
            realized_r = t.get("realized_R_multiple", 0.0)
            if realized_r == 0.0:
                pnl_pct = t.get("pnl_yuzde", 0.0)
                leverage = t.get("kaldirac", 1.0)
                realized_r = pnl_pct / (leverage * 100.0) if leverage > 0 else pnl_pct / 100.0
                
            exit_reason = t.get("exit_reason", "")
            exit_eff = 1.0 if any(r in exit_reason for r in ["TP", "TS", "AI_KAR"]) else 0.2
            
            holding_time = t.get("holding_time", 0.0)
            duration_penalty = min(0.2, (holding_time / 1440.0) * 0.10)
            
            quality_score = (realized_r * 0.45) + (mfe_mae_ratio * 0.20) + (exit_eff * 0.25) - duration_penalty
            
            # Gri Alan Filtresi (ML Noise Guard): 0.45 - 0.55 aralığındaki kararsız işlemleri ele
            if 0.45 < quality_score < 0.55:
                continue
                
            outcome = 1.0 if quality_score >= 0.55 else 0.0
            X.append(features)
            y.append(outcome)
            
        if len(X) >= 20:
            self.meta_filter.train(X, y)
            add_log(f"🧠 Meta-Labeling Model 2 (Kabul Filtresi) {len(X)} işlem ile yerel olarak yeniden eğitildi!")

    def generate_signal(self, coin_key: str, ticker: dict, ta_result: dict,
                        sentiment_result: dict, timeframe: str = "1h", mtf_data: dict = None,
                        btc_trend: str = "NEUTRAL", btc_regime: str = "RANGE",
                        btc_reversal_trigger: bool = False, daily_trend_long: bool = True,
                        ta_1h: dict = None, ta_4h: dict = None,
                        macro_risk_data: dict = None) -> dict:
        """Triple Barrier, Ensemble Voting, Bayesian Uncertainty, MTF Alignment ve Trade Quality Scoring tabanlı sinyal üretir."""
        if not ta_result or not ta_result.get("indicators"):
            return self._empty_signal()

        indicators = ta_result["indicators"]
        trend = ta_result["trend"]
        volatility = ta_result["volatility"]
        volume = ta_result["volume_analysis"]
        mapped_regime = ta_result.get("regime", "RANGE")
        close = indicators.get("last_close", 0)
        
        # Borsa Mikroyapı Verileri
        try:
            micro = self.fetcher.fetch_futures_data(coin_key)
        except:
            micro = {"funding_rate": 0.0, "open_interest": 0.0, "spread_percent": 0.02, "oi_delta": 0.0}
            
        spread_percent = micro.get("spread_percent", 0.02)
        funding_rate = micro.get("funding_rate", 0.0)
        oi_delta = micro.get("oi_delta", 0.0)
        atr_pct = volatility.get("atr_pct", 1.0)
        rsi = indicators.get("rsi", 50)
        macd_hist = indicators.get("macd_histogram", 0)
        adx = indicators.get("adx", 0)
        vol_ratio = volume.get("ratio", 1.0)
        sent_score = sentiment_result.get("overall", {}).get("score", 50)

        # ========================================================
        # 🤖 1. ENSEMBLE AI ARCHITECTURE (8 UZMAN MODEL)
        # ========================================================
        experts = []
        t_score = trend.get("direction_score", 0)

        # 1. Trend Following Expert
        exp_trend = ExpertModel("Trend_Following")
        if adx > 22 and t_score != 0:
            exp_trend.direction = "LONG" if t_score > 0 else "SHORT"
            exp_trend.confidence = float(min(100.0, 50.0 + (adx * 1.5)))
            exp_trend.raw_score = 0.8 if t_score > 0 else -0.8
        experts.append(exp_trend)

        # 2. Mean Reversion Expert
        exp_rev = ExpertModel("Mean_Reversion")
        if rsi < 32:
            exp_rev.direction = "LONG"
            exp_rev.confidence = float(min(100.0, 50.0 + (30 - rsi) * 3))
            exp_rev.raw_score = 0.7
        elif rsi > 68:
            exp_rev.direction = "SHORT"
            exp_rev.confidence = float(min(100.0, 50.0 + (rsi - 70) * 3))
            exp_rev.raw_score = -0.7
        experts.append(exp_rev)

        # 3. Breakout Expert
        exp_break = ExpertModel("Breakout_Detection")
        bb_width = indicators.get("bb_width", 0.05)
        if vol_ratio > 1.6 and bb_width > 0.06:
            exp_break.direction = "LONG" if close > indicators.get("bb_middle", close) else "SHORT"
            exp_break.confidence = float(min(100.0, 50.0 + (vol_ratio * 12)))
            exp_break.raw_score = 0.6 if exp_break.direction == "LONG" else -0.6
        experts.append(exp_break)

        # 4. Scalping Expert
        exp_scalp = ExpertModel("Scalping")
        if macd_hist != 0:
            exp_scalp.direction = "LONG" if macd_hist > 0 else "SHORT"
            exp_scalp.confidence = 65.0
            exp_scalp.raw_score = 0.5 if macd_hist > 0 else -0.5
        experts.append(exp_scalp)

        # 5. Volatility Expansion Expert
        exp_vol = ExpertModel("Volatility_Expansion")
        if bb_width < 0.03 and vol_ratio > 1.3:
            exp_vol.direction = "LONG" if close > indicators.get("prev_close", close) else "SHORT"
            exp_vol.confidence = 70.0
            exp_vol.raw_score = 0.7 if exp_vol.direction == "LONG" else -0.7
        experts.append(exp_vol)

        # 6. Liquidity Sweep Expert
        exp_liq = ExpertModel("Liquidity_Sweep")
        candle_imbalance = abs(close - indicators.get("prev_close", close)) / (close * 0.0001 + 1e-6)
        if candle_imbalance > 15.0 and vol_ratio > 1.8:
            exp_liq.direction = "SHORT" if close > indicators.get("prev_close", close) else "LONG"
            exp_liq.confidence = 75.0
            exp_liq.raw_score = -0.8 if close > indicators.get("prev_close", close) else 0.8
        experts.append(exp_liq)

        # 7. Momentum Continuation Expert
        exp_mom = ExpertModel("Momentum_Continuation")
        if adx > 25 and vol_ratio > 1.2:
            exp_mom.direction = "LONG" if rsi > 52 else "SHORT"
            exp_mom.confidence = 68.0
            exp_mom.raw_score = 0.6 if rsi > 52 else -0.6
        experts.append(exp_mom)

        # 8. Reversal Expert
        exp_reversal = ExpertModel("Reversal_Detection")
        if (rsi < 35 and t_score < 0) or (rsi > 65 and t_score > 0):
            exp_reversal.direction = "LONG" if rsi < 35 else "SHORT"
            exp_reversal.confidence = 60.0
            exp_reversal.raw_score = 0.5 if rsi < 35 else -0.5
        experts.append(exp_reversal)

        # ========================================================
        # 🔄 2. REGIME SWITCHING GATING NETWORK (META-VOTE)
        # ========================================================
        expert_weights = {exp.name: 0.05 for exp in experts} # Varsayılan küçük taban ağırlığı

        if mapped_regime in ["TRENDING_BULL", "TRENDING_BEAR"]:
            expert_weights["Trend_Following"] = 0.40
            expert_weights["Momentum_Continuation"] = 0.30
            expert_weights["Breakout_Detection"] = 0.15
        elif mapped_regime == "RANGE":
            expert_weights["Mean_Reversion"] = 0.45
            expert_weights["Scalping"] = 0.30
            expert_weights["Reversal_Detection"] = 0.15
        elif mapped_regime == "VOLATILITY_EXPANSION":
            expert_weights["Breakout_Detection"] = 0.35
            expert_weights["Volatility_Expansion"] = 0.35
            expert_weights["Liquidity_Sweep"] = 0.20
        elif mapped_regime == "COMPRESSION":
            expert_weights["Volatility_Expansion"] = 0.40
            expert_weights["Breakout_Detection"] = 0.30
            expert_weights["Scalping"] = 0.20

        # 🧠 Phase 4: Coine Özel Adaptif İndikatör Ağırlıklarını Yükle
        opt_weights = self.coin_intel.get_adaptive_weights(coin_key)
        
        # Uzman Modellerin Gösterge Eşleşmeleri
        expert_ta_mapping = {
            "Trend_Following": "ema_crossover",
            "Mean_Reversion": "rsi",
            "Breakout_Detection": "volume",
            "Scalping": "macd",
            "Volatility_Expansion": "bollinger",
            "Liquidity_Sweep": "volume",
            "Momentum_Continuation": "trend_adx",
            "Reversal_Detection": "rsi"
        }

        # Ağırlıklı Oylama (Meta-Vote)
        total_vote_score = 0.0
        for exp in experts:
            w_regime = expert_weights.get(exp.name, 0.05)
            ta_key = expert_ta_mapping.get(exp.name, "rsi")
            w_coin = opt_weights.get(ta_key, 0.12)
            
            w_final = w_regime * (w_coin * 8.0)
            total_vote_score += exp.raw_score * w_final

        direction = "NEUTRAL"
        direction_label = "➡️ Kararsız / Yatay"
        direction_color = "#FFD740"
        
        min_vote = INSTITUTIONAL_THRESHOLDS["min_direction_vote"]  # 0.15 (eski: 0.01)
        if total_vote_score > min_vote:
            direction = "LONG"
            direction_label = "📈 Long Ağırlıklı"
            direction_color = "#00E676"
        elif total_vote_score < -min_vote:
            direction = "SHORT"
            direction_label = "📉 Short Ağırlıklı"
            direction_color = "#FF5252"

        # ========================================================
        # ⚖️ 3. BAYESIAN UNCERTAINTY & PROBABILITY CALIBRATION
        # ========================================================
        vote_directions = []
        for exp in experts:
            if exp.direction == "LONG": vote_directions.append(1.0)
            elif exp.direction == "SHORT": vote_directions.append(-1.0)
            else: vote_directions.append(0.0)
            
        uncertainty = float(np.std(vote_directions))
        uncertainty_label = "DÜŞÜK (Fikir Birliği)" if uncertainty < 0.4 else "ORTA" if uncertainty < 0.7 else "YÜKSEK (Uyumsuzluk)"

        # Olasılık Bileşenleri (Sigmoid Girişi)
        regime_score = 1.0 if ("BULL" in mapped_regime and direction == "LONG") or ("BEAR" in mapped_regime and direction == "SHORT") else -0.5
        
        mtf_score = 0.0
        if mtf_data:
            alignment = mtf_data.get("alignment", "UYUMSUZ")
            if "ALIGNMENT" in alignment:
                mtf_score = 1.0 if (direction == "LONG" and "BULL" in alignment) or (direction == "SHORT" and "BEAR" in alignment) else -1.0

        funding_bias = 1.0 if (direction == "LONG" and funding_rate < 0) or (direction == "SHORT" and funding_rate > 0) else -0.3
        oi_bias = 0.8 if oi_delta > 1.0 else -0.2

        z = (
            3.0 * abs(total_vote_score) +
            1.2 * regime_score +
            1.0 * mtf_score +
            0.5 * funding_bias +
            0.5 * oi_bias -
            0.8 * uncertainty
        )
        p_win = 1.0 / (1.0 + math.exp(-z))
        confidence_pct = p_win * 100

        # Dinamik ATR TP/SL Seviyeleri (Triple Barrier)
        atr = indicators.get("atr", 0)
        if mapped_regime in ["TRENDING_BULL", "TRENDING_BEAR"]:
            risk_r = 2.0
            reward_r = 4.5
        elif mapped_regime == "VOLATILITY_EXPANSION":
            risk_r = 3.2
            reward_r = 3.2
        else:
            risk_r = 1.5
            reward_r = 2.5

        # 🧠 5. STRATEGIC HEGDE FUND INTELLIGENCE (PART 1 - MOMENTUM & PATIENCE WIDENING)
        raw_mom = total_vote_score
        momentum_score = int(min(100, max(0, 50 + raw_mom * 50)))
        patience_score = 70
        momentum_multiplier = 1.0
        exit_patience = 1.0     # 🔮 Default (counterfactual'dan sonra güncellenecek)
        entry_courage = 1.0     # 🔮 Default (counterfactual'dan sonra güncellenecek)
        
        if direction != "NEUTRAL":
            if momentum_score >= 80:
                patience_score = 95
                momentum_multiplier = 1.35
            elif momentum_score >= 65:
                patience_score = 85
                momentum_multiplier = 1.15

        if direction == "LONG":
            stop_loss = close - (atr * risk_r)
            tp = close + (atr * reward_r * momentum_multiplier * exit_patience)
        elif direction == "SHORT":
            stop_loss = close + (atr * risk_r)
            tp = close - (atr * reward_r * momentum_multiplier * exit_patience)
        else:
            stop_loss = 0.0
            tp = 0.0

        # ========================================================
        # 🎲 4. VECTORIZED MONTE CARLO RISK ENGINE (10,000 RUNS)
        # ========================================================
        n_simulations = 10000
        n_steps = 24
        vol_fraction = float(atr_pct * 0.01)
        dt = 1.0 / n_steps
        drift = float((p_win - 0.5) * (reward_r * momentum_multiplier) * vol_fraction)
        
        rand_shocks = np.random.normal(0, 1, (n_simulations, n_steps))
        paths = np.zeros((n_simulations, n_steps + 1), dtype=np.float32)
        paths[:, 0] = close
        log_returns = drift * dt + vol_fraction * math.sqrt(dt) * rand_shocks
        paths[:, 1:] = close * np.exp(np.cumsum(log_returns, axis=1))
        
        if direction == "LONG" and stop_loss > 0 and tp > 0:
            hit_tp = np.any(paths >= tp, axis=1)
            hit_sl = np.any(paths <= stop_loss, axis=1)
        elif direction == "SHORT" and stop_loss > 0 and tp > 0:
            hit_tp = np.any(paths <= tp, axis=1)
            hit_sl = np.any(paths >= stop_loss, axis=1)
        else:
            hit_tp = np.zeros(n_simulations, dtype=bool)
            hit_sl = np.zeros(n_simulations, dtype=bool)
            
        survival_prob = float(np.sum(~hit_sl) / n_simulations)
        ruin_prob = float(np.sum(hit_sl & ~hit_tp) / n_simulations)
        worst_dd = float(np.min((paths - close) / close) * 100) if direction == "LONG" else float(np.min((close - paths) / close) * 100)

        # Expected Value (EV) Hesabı
        cost_r = 0.15 + (spread_percent * 0.1)
        p_loss = 1.0 - p_win
        ev = (p_win * reward_r * momentum_multiplier) - (p_loss * risk_r) - cost_r

        # MODEL 2 (Meta-Filter): Olasılık Kontrolü
        ml_data = {
            "rsi": rsi,
            "macd": macd_hist,
            "ema_crossover": t_score,
            "volume": vol_ratio,
            "sentiment": sent_score
        }
        current_features = self._get_features_array(ml_data, {
            "spread": spread_percent,
            "funding": funding_rate,
            "oi_delta": oi_delta,
            "volatility_regime": atr_pct
        }, direction)
        trade_acceptance_probability = self.meta_filter.predict_proba(current_features)
        
        # Win Rate ve Drawdown bazlı dinamik ve adaptif olasılık eşiği (Sniper Modu için düşürüldü)
        drawdown_pct, win_rate = self._get_model_stats()
        base_threshold = max(0.15, min(0.35, win_rate - 0.10))
        
        if mapped_regime in ["TRENDING_BULL", "TRENDING_BEAR"]:
            meta_threshold = base_threshold
        elif mapped_regime in ["RANGE", "SIDEWAYS"]:
            meta_threshold = base_threshold + 0.05
        else:
            meta_threshold = base_threshold + 0.10
            
        meta_threshold += min(0.05, drawdown_pct * 0.5)

        # Vektör Benzerliği Oylaması
        current_vector = [
            float(rsi), float(macd_hist), float(t_score),
            float(bb_width), float(adx), float(vol_ratio)
        ]
        intel_res = self.coin_intel.evaluate_final_intelligence(
            coin_key, current_vector, confidence_pct, mapped_regime
        )

        # 🔮 Counterfactual Bias: Kaçırılan fırsatlar ve erken çıkışlardan öğrenme
        cf_bias = self.coin_intel.get_counterfactual_bias(coin_key)
        entry_courage = cf_bias.get("entry_courage_multiplier", 1.0)
        exit_patience = cf_bias.get("exit_patience_multiplier", 1.0)
        
        # 🔮 TP'yi güncellenmiş exit_patience ile yeniden hesapla (eğer değiştiyse)
        if exit_patience > 1.0 and direction != "NEUTRAL":
            if direction == "LONG" and close > 0:
                tp = close + (atr * reward_r * momentum_multiplier * exit_patience)
            elif direction == "SHORT" and close > 0:
                tp = close - (atr * reward_r * momentum_multiplier * exit_patience)

        # ========================================================
        # 4. HIERARCHICAL MULTI-TIMEFRAME CONFIRMATION
        # ========================================================
        htf_alignment_score = 0
        if direction != "NEUTRAL":
            # 4H macro trend check
            bullish_4h = False
            bearish_4h = False
            if ta_4h and ta_4h.get("indicators"):
                c_4h = ta_4h["indicators"]["last_close"]
                ema200_4h = ta_4h["indicators"]["ema"].get(200, 0)
                bullish_4h = c_4h > ema200_4h
                bearish_4h = c_4h < ema200_4h
            else:
                # Fallback to daily trend filter
                bullish_4h = daily_trend_long
                bearish_4h = not daily_trend_long

            # 1H structure trend check
            bullish_1h = False
            bearish_1h = False
            if ta_1h and ta_1h.get("indicators"):
                c_1h = ta_1h["indicators"]["last_close"]
                ema50_1h = ta_1h["indicators"]["ema"].get(50, 0)
                bullish_1h = c_1h > ema50_1h
                bearish_1h = c_1h < ema50_1h
            else:
                # Fallback to mtf_data alignment
                if mtf_data:
                    bullish_1h = "BULL" in mtf_data.get("large", "")
                    bearish_1h = "BEAR" in mtf_data.get("large", "")

            if direction == "LONG":
                if bullish_4h: htf_alignment_score += 50
                if bullish_1h: htf_alignment_score += 50
            elif direction == "SHORT":
                if bearish_4h: htf_alignment_score += 50
                if bearish_1h: htf_alignment_score += 50

        # ========================================================
        # 5. TRADE QUALITY SCORING ENGINE
        # ========================================================
        adx_val = float(adx)
        liq_sweep = ta_result.get("liquidity_sweep", "NONE")
        trade_quality_score = 50
        if direction != "NEUTRAL":
            trend_quality = 0
            if adx_val > 25: trend_quality += 10
            if adx_val > 35: trend_quality += 5
            # Trigger EMA alignment
            ema9_tr = indicators.get("ema", {}).get(9, 0)
            ema21_tr = indicators.get("ema", {}).get(21, 0)
            ema50_tr = indicators.get("ema", {}).get(50, 0)
            if direction == "LONG" and ema9_tr > ema21_tr > ema50_tr:
                trend_quality += 5
            elif direction == "SHORT" and ema9_tr < ema21_tr < ema50_tr:
                trend_quality += 5

            volume_conf = 0
            if vol_ratio > 1.2: volume_conf += 10
            if vol_ratio > 1.8: volume_conf += 10

            vol_expansion_score = 0
            if bb_width > 0.04: vol_expansion_score += 5
            if mapped_regime == "VOLATILITY_EXPANSION": vol_expansion_score += 10

            momentum_score_val = 0
            if direction == "LONG" and 45 < rsi < 65: momentum_score_val += 7
            elif direction == "SHORT" and 35 < rsi < 55: momentum_score_val += 7
            if direction == "LONG" and macd_hist > 0: momentum_score_val += 8
            elif direction == "SHORT" and macd_hist < 0: momentum_score_val += 8

            htf_score_contribution = int(htf_alignment_score * 0.20)

            breakout_sweep_score = 0
            if (liq_sweep == "BULLISH" and direction == "LONG") or (liq_sweep == "BEARISH" and direction == "SHORT"):
                breakout_sweep_score += 10
            elif ta_result.get("volatility", {}).get("squeeze_breakout", "NONE") != "NONE":
                breakout_sweep_score += 10

            trade_quality_score = 30 + trend_quality + volume_conf + vol_expansion_score + momentum_score_val + htf_score_contribution + breakout_sweep_score
            trade_quality_score = min(100, max(0, trade_quality_score))

        risk_multiplier = 1.0
        if direction != "NEUTRAL":
            if trade_quality_score < 75:
                risk_multiplier = 0.5

        # Trend Score (ADX & Direction)
        trend_score = int(min(100, max(0, 50 + t_score * (adx_val * 0.8))))

        # Liquidity Score
        liq_score_base = 70.0
        liq_score_base -= min(30.0, spread_percent * 300)
        liq_score_base += min(15.0, max(-15.0, oi_delta * 5))
        if direction == "LONG":
            liq_score_base += (10.0 if funding_rate < 0 else -10.0)
        else:
            liq_score_base += (10.0 if funding_rate > 0 else -10.0)
        liquidity_score = int(min(100, max(0, liq_score_base)))

        # Psychology Score
        psy_score_base = float(sent_score)
        if liq_sweep == "BULLISH" and direction == "LONG":
            psy_score_base = min(100, psy_score_base + 15)
        elif liq_sweep == "BEARISH" and direction == "SHORT":
            psy_score_base = min(100, psy_score_base + 15)
        psychology_score = int(min(100, max(0, psy_score_base)))

        volatility_score = int(min(100.0, (atr_pct * 15) + (bb_width * 200)))

        # Risk Score
        risk_score_val = (ruin_prob * 60) + (abs(worst_dd) * 4) + (spread_percent * 200)
        similarity_weight = intel_res["similarity_score"]
        risk_score_val -= (similarity_weight - 0.5) * 15
        risk_score = int(min(100, max(5, risk_score_val)))

        survival_pct = survival_prob * 100
        if survival_pct >= 90.0: continuation_prob_label = "EXTREME"
        elif survival_pct >= 75.0: continuation_prob_label = "HIGH"
        elif survival_pct >= 60.0: continuation_prob_label = "MEDIUM"
        else: continuation_prob_label = "LOW"

        exit_eff_score = 90
        if bb_width > 0.05: exit_eff_score += 5
        exit_eff_score = min(100, exit_eff_score)

        # Karar Filtreleri ve Asimetrik Eşik Sistemi (SNIPER SCALPER: Kaliteli ama sık işlem)
        base_threshold = 42.0
        adaptive_threshold = base_threshold + (atr_pct * 2.5) + (spread_percent * 3.0)
        
        is_tradable = True
        reject_reason = ""

        # 🚨 BTC Trend Filtresi & Asimetrik Eşik Güçlendirme (Short/Long Bias)
        if coin_key != "BTC":
            if btc_reversal_trigger:
                if direction == "LONG":
                    adaptive_threshold = max(40.0, adaptive_threshold - 15.0)
                elif direction == "SHORT":
                    adaptive_threshold = max(75.0, adaptive_threshold + 20.0)
            else:
                if btc_regime in ["TRENDING_BEAR", "STRONG_BEAR"] or btc_trend == "SHORT":
                    if direction == "LONG":
                        adaptive_threshold = max(85.0, adaptive_threshold + 30.0)
                    elif direction == "SHORT":
                        adaptive_threshold = max(40.0, adaptive_threshold - 15.0)
                elif btc_regime in ["TRENDING_BULL", "STRONG_BULL"] or btc_trend == "LONG":
                    if direction == "SHORT":
                        adaptive_threshold = max(85.0, adaptive_threshold + 30.0)
                    elif direction == "LONG":
                        adaptive_threshold = max(40.0, adaptive_threshold - 15.0)

        # 🛡️ 1 Günlük (1d) Grafikten Trend Yönü Filtresi (EMA 200)
        if coin_key != "BTC" and is_tradable:
            if daily_trend_long:
                if direction == "SHORT":
                    adaptive_threshold += 10.0
                elif direction == "LONG":
                    adaptive_threshold = max(40.0, adaptive_threshold - 5.0)
            else:
                if direction == "LONG":
                    adaptive_threshold += 15.0
                elif direction == "SHORT":
                    adaptive_threshold = max(40.0, adaptive_threshold - 5.0)

        # Eşiği makul seviyede sınırlandır (SNIPER: %75 tavanlı — kaliteyi koru)
        adaptive_threshold = min(75.0, adaptive_threshold)
        
        # 🌍 Makro Risk Eşik Ayarı (Normal koşullarda macro_risk_data=None → sıfır etki)
        macro_risk_multiplier = 1.0
        macro_level = "NORMAL"
        macro_short_bias = 0.0
        if macro_risk_data and macro_risk_data.get('level', 'NORMAL') != 'NORMAL':
            macro_level = macro_risk_data.get('level', 'NORMAL')
            macro_threshold_adj = macro_risk_data.get('threshold_adjustment', 0.0)
            macro_risk_multiplier = macro_risk_data.get('risk_multiplier', 1.0)
            macro_short_bias = macro_risk_data.get('short_bias', 0.0)
            adaptive_threshold += macro_threshold_adj
            
            # Makro krizde SHORT'a yatkınlık artır
            if direction == "SHORT" and macro_short_bias > 0:
                adaptive_threshold = max(40.0, adaptive_threshold - (macro_short_bias * 20))
            
            add_log(f"🌍 Makro Risk ({macro_level}): Eşik +{macro_threshold_adj}, Çarpan {macro_risk_multiplier:.0%}")

        # BTC Chaotic Volatility Filter
        if btc_regime == "CHAOTIC_VOLATILE":
            is_tradable = False
            reject_reason = "BTC_CHAOTIC_VOLATILITY"

        # Volatility, Breakout and Volume checks for Entry Quality Score
        daily_align = 1.0 if (direction == "LONG" and daily_trend_long) or (direction == "SHORT" and not daily_trend_long) else 0.2
        trend_alignment = (htf_alignment_score / 100.0) * 0.6 + daily_align * 0.4
        
        breakout_strength = 0.5
        if ta_result.get("volatility", {}).get("squeeze_breakout", "NONE") != "NONE":
            breakout_strength += 0.3
        if (liq_sweep == "BULLISH" and direction == "LONG") or (liq_sweep == "BEARISH" and direction == "SHORT"):
            breakout_strength += 0.2
        breakout_strength = min(1.0, breakout_strength + min(0.3, adx_val / 100.0))
        
        volume_confirmation = min(1.0, max(0.0, vol_ratio / 2.0))
        
        atr_score = min(1.0, atr_pct / 1.5) if atr_pct > 0.5 else 0.3
        spread_penalty = max(0.0, min(1.0, spread_percent / 0.1))
        volatility_quality = max(0.1, atr_score * (1.0 - spread_penalty))
        
        btc_alignment_val = 0.5
        if btc_trend == direction:
            btc_alignment_val = 1.0
        elif btc_trend == "NEUTRAL":
            btc_alignment_val = 0.6
        else:
            btc_alignment_val = 0.2
            
        entry_quality_score = (
            trend_alignment * 0.30 +
            breakout_strength * 0.25 +
            volume_confirmation * 0.20 +
            volatility_quality * 0.15 +
            btc_alignment_val * 0.10
        )
        entry_quality_score = round(max(0.0, min(1.0, entry_quality_score)), 3)

        # Quality Multipliers
        quality_multiplier = 1.0
        if entry_quality_score < 0.35:
            confidence_pct = confidence_pct * 0.90
            quality_multiplier = 0.7
            add_log(f"⚠️ DÜŞÜK GİRİŞ KALİTESİ ({entry_quality_score:.2f} < 0.35): Sinyal güven skoru hafif düşürüldü (%{confidence_pct:.1f}).")
        elif entry_quality_score >= 0.75:
            quality_multiplier = 1.2

        # Directional Wick Trap Filter
        wick_ratio = 0.0
        try:
            o_last = float(ticker.get("bid", close))
            c_last = float(close)
            h_last = float(ticker.get("high", close))
            l_last = float(ticker.get("low", close))
            total_range = h_last - l_last
            
            if total_range > 0:
                if direction == "LONG":
                    upper_wick = h_last - max(o_last, c_last)
                    wick_ratio = upper_wick / total_range
                elif direction == "SHORT":
                    lower_wick = min(o_last, c_last) - l_last
                    wick_ratio = lower_wick / total_range
        except Exception as wick_err:
            wick_ratio = 0.0

        if direction != "NEUTRAL" and is_tradable:
            if wick_ratio > 0.60 and volume_confirmation < 0.50:
                is_tradable = False
                reject_reason = f"WICK_TRAP_RISK (Wick Oranı: %{wick_ratio*100:.1f} > %60.0 ve Hacim Onayı: {volume_confirmation:.2f} < 0.50)"
            elif btc_alignment_val < 0.40:
                is_tradable = False
                reject_reason = f"BTC_NOT_ALIGNED (Yön: {direction}, BTC Yönü: {btc_trend})"

        # 🏦 INSTITUTIONAL FILTERS — Deterministik Sayısal Eşikler
        # Funding Overcrowded: Kalabalık tarafa işlem açma (likidite avı riski)
        if direction != "NEUTRAL" and is_tradable:
            funding_long_limit = INSTITUTIONAL_THRESHOLDS["funding_overcrowded_long"]
            funding_short_limit = INSTITUTIONAL_THRESHOLDS["funding_overcrowded_short"]
            if direction == "LONG" and funding_rate > funding_long_limit:
                is_tradable = False
                reject_reason = f"FUNDING_OVERCROWDED_LONG (Funding: {funding_rate:.4f} > {funding_long_limit}) — Long tarafı aşırı kalabalık, likidite avı riski"
            elif direction == "SHORT" and funding_rate < funding_short_limit:
                is_tradable = False
                reject_reason = f"FUNDING_OVERCROWDED_SHORT (Funding: {funding_rate:.4f} < {funding_short_limit}) — Short tarafı aşırı kalabalık, likidite avı riski"

        # OI Spike Squeeze Koruması: Anlık OI patlaması squeeze işareti
        if direction != "NEUTRAL" and is_tradable:
            oi_spike_limit = INSTITUTIONAL_THRESHOLDS["oi_spike_threshold"]
            if abs(oi_delta) > oi_spike_limit:
                is_tradable = False
                reject_reason = f"OI_SPIKE_SQUEEZE_RISK (OI Delta: {oi_delta:.1f}% > {oi_spike_limit}%) — Squeeze/likidasyon kaskadı riski"

        # Volume Minimum Filtresi: Yetersiz hacimde işlem açma
        if direction != "NEUTRAL" and is_tradable:
            vol_min = INSTITUTIONAL_THRESHOLDS["volume_min_ratio"]
            if vol_ratio < vol_min:
                is_tradable = False
                reject_reason = f"VOLUME_TOO_LOW (Hacim Oranı: {vol_ratio:.2f} < {vol_min}) — Yetersiz hacim onayı"

        if not is_tradable:
            pass
        elif direction == "NEUTRAL":
            is_tradable = False
            reject_reason = "Kararsız Piyasa Eğilimi"
        elif direction != "NEUTRAL" and htf_alignment_score == 0 and trade_quality_score < 25:
            is_tradable = False
            reject_reason = f"HTF Trend Alignment Uyumsuzluğu (Karşı Trend)"
        elif direction != "NEUTRAL" and trade_quality_score < INSTITUTIONAL_THRESHOLDS["min_quality_score"]:
            is_tradable = False
            reject_reason = f"Düşük Kalite Skoru ({trade_quality_score} < {INSTITUTIONAL_THRESHOLDS['min_quality_score']})"
        elif not intel_res["is_approved"]:
            is_tradable = False
            reject_reason = intel_res["reject_reason"]
        elif ev <= INSTITUTIONAL_THRESHOLDS["min_ev_threshold"]:
            is_tradable = False
            reject_reason = f"Negatif Expected Value (EV: {ev:.3f} <= {INSTITUTIONAL_THRESHOLDS['min_ev_threshold']})"
        elif confidence_pct <= adaptive_threshold:
            # 🔮 Counterfactual cesaret çarpanı: Kaçırılan fırsatlar çoksa eşiği %5'e kadar düşür
            adjusted_threshold = adaptive_threshold / entry_courage if entry_courage > 1.0 else adaptive_threshold
            if confidence_pct <= adjusted_threshold:
                is_tradable = False
                reject_reason = f"Olasılık Eşik Altında (%{confidence_pct:.1f} <= %{adjusted_threshold:.1f})"
                if entry_courage > 1.0:
                    reject_reason += f" [CF Cesaret: {entry_courage:.2f}x uygulandı]"
        elif trade_acceptance_probability < meta_threshold:
            is_tradable = False
            reject_reason = f"Model 2 Meta-Filter Reddi (%{trade_acceptance_probability*100:.1f} < Eşik %{meta_threshold*100:.1f})"
        elif survival_prob < 0.25:
            is_tradable = False
            reject_reason = f"Düşük Monte Carlo Sağkalım Oranı (%{survival_prob*100:.1f} < %25.0)"
        elif (reward_r / risk_r) < INSTITUTIONAL_THRESHOLDS["min_rr_ratio"]:
            is_tradable = False
            reject_reason = f"Risk/Ödül Yetersiz ({reward_r/risk_r:.2f} < {INSTITUTIONAL_THRESHOLDS['min_rr_ratio']}) — Minimum 1:{INSTITUTIONAL_THRESHOLDS['min_rr_ratio']:.0f} gerekli"
        elif spread_percent >= 0.10:
            is_tradable = False
            reject_reason = f"Spread Kabul Edilemez Derecede Geniş (%{spread_percent:.3f})"

        # 8. Final Decision Mapping
        if AI_MODE == "OBSERVE_ONLY":
            if direction != "NEUTRAL":
                if not is_tradable:
                    add_log(f"ℹ️ AI_OBSERVATION (OBSERVE_ONLY): {coin_key} {direction} için engelleme ({reject_reason}) devredışı bırakıldı.")
                is_tradable = True
                reject_reason = ""

        # 🧠 LEARN_AND_APPLY MODE: Öğrenmeye devam et + öğrendiklerini uygula (kümülatif)
        # Kritik filtreler aktif kalır, yumuşak eşikler %30 esnetilir → daha fazla öğrenme fırsatı ama tehlikeli işlemler engellenir
        if AI_MODE == "LEARN_AND_APPLY":
            if direction != "NEUTRAL" and not is_tradable:
                # 🔴 KESİN ENGELLER — bunlar her zaman aktif kalır (öğrenilmiş dersler)
                hard_block_reasons = [
                    "BTC_CHAOTIC_VOLATILITY",
                    "WICK_TRAP_RISK",
                    "BTC_NOT_ALIGNED",
                ]
                
                is_hard_block = any(reason in reject_reason for reason in hard_block_reasons)
                
                # Negatif EV kontrolü (institutional: EV <= 0.0 olan işlemler para kaybettiriyor)
                if ev <= INSTITUTIONAL_THRESHOLDS["min_ev_threshold"]:
                    is_hard_block = True
                
                # Monte Carlo sağkalım düşükse engelle (SNIPER: %25)
                if survival_prob < 0.25:
                    is_hard_block = True
                
                # Risk/Ödül yetersizse engelle (institutional: minimum 1:2)
                if risk_r > 0 and (reward_r / risk_r) < INSTITUTIONAL_THRESHOLDS["min_rr_ratio"]:
                    is_hard_block = True
                
                # Funding Overcrowded engeli (institutional)
                if "FUNDING_OVERCROWDED" in reject_reason:
                    is_hard_block = True
                
                # OI Spike Squeeze engeli (institutional)
                if "OI_SPIKE_SQUEEZE" in reject_reason:
                    is_hard_block = True
                
                # Volume yetersiz engeli (SNIPER: volume bloğu geri aktif)
                if "VOLUME_TOO_LOW" in reject_reason:
                    is_hard_block = True
                    
                # Spread çok genişse engelle (SNIPER: 0.10 sıkılaştırıldı)
                if spread_percent >= 0.10:
                    is_hard_block = True
                
                # Coin Intelligence reddi (geçmiş benzer setup'lar kaybetmişse) — ÖĞRENİLMİŞ DERS
                if "quantum_score" in reject_reason.lower() or "similarity" in reject_reason.lower() or "fakeout" in reject_reason.lower() or "edge" in reject_reason.lower():
                    is_hard_block = True
                
                if is_hard_block:
                    # 🛑 Tehlikeli işlem — engelle ama öğrenme için kaydet
                    add_log(f"🛡️ AI_LEARN_AND_APPLY: {coin_key} {direction} — KRİTİK FİLTRE ENGELİ: {reject_reason}. İşlem engellendi, ders kaydedildi.")
                else:
                    # 🟡 Yumuşak red (olasılık eşiği, kalite skoru vb.) — eşiği %30 esnet
                    # Eğer orijinal eşiğin %70'ini geçiyorsa, öğrenme fırsatı olarak geçir
                    softened = False
                    if "Olasılık Eşik Altında" in reject_reason:
                        soft_threshold = adaptive_threshold * 0.70
                        if confidence_pct > soft_threshold:
                            softened = True
                    elif "Meta-Filter" in reject_reason:
                        soft_meta = meta_threshold * 0.70
                        if trade_acceptance_probability > soft_meta:
                            softened = True
                    elif "HTF Trend" in reject_reason:
                        softened = True  # SNIPER: HTF uyumsuzluğu esnetilir ama EV kontrolü yapılır
                    elif "Düşük Kalite" in reject_reason:
                        softened = False  # SNIPER: Düşük kalite artık geçirilmez
                    
                    if softened:
                        add_log(f"🧠 AI_LEARN_AND_APPLY: {coin_key} {direction} — Yumuşak red ({reject_reason}) esnetilerek geçirildi. Öğrenme + uygulama modu.")
                        is_tradable = True
                        reject_reason = ""
                    else:
                        add_log(f"📚 AI_LEARN_AND_APPLY: {coin_key} {direction} — Red ({reject_reason}) uygulandı. Öğrenilen ders aktif.")

        # 🧠 LEARN MODE (ESKİ): Agresif öğrenme — mümkün olan her sinyale gir, veri topla
        elif AI_MODE == "LEARN":
            if direction != "NEUTRAL":
                if not is_tradable:
                    add_log(f"🧠 AI_LEARN: {coin_key} {direction} — Red sebebi ({reject_reason}) öğrenme modu için geçersiz kılındı.")
                is_tradable = True
                reject_reason = ""

        if not is_tradable:
            final_decision = "AVOID"
        elif confidence_pct >= 75.0 and ev > 0.6:
            final_decision = "STRONG BUY" if direction == "LONG" else "STRONG SHORT"
        else:
            final_decision = "BUY" if direction == "LONG" else "SHORT"

        intelligence_report = {
            "trend_score": trend_score,
            "momentum_score": momentum_score,
            "liquidity_score": liquidity_score,
            "psychology_score": psychology_score,
            "volatility_score": volatility_score,
            "risk_score": risk_score,
            "continuation_probability": continuation_prob_label,
            "final_decision": final_decision,
            "exit_efficiency": exit_eff_score,
            "patience_score": patience_score,
            "fakeout_prob": round(intel_res["fakeout_prob"] * 100, 1),
            "mc_survival_prob": round(survival_prob * 100, 1),
            "ev": round(ev, 3),
            "trade_quality_score": trade_quality_score,
            "htf_alignment_score": htf_alignment_score
        }

        struct_ta = ta_1h if ta_1h and ta_1h.get("support_resistance") else ta_result
        supports = struct_ta.get("support_resistance", {}).get("supports", [])
        resistances = struct_ta.get("support_resistance", {}).get("resistances", [])
        support_level = round(supports[0], 6) if supports else 0.0
        resistance_level = round(resistances[0], 6) if resistances else 0.0

        ai_comment = self._generate_ai_comment(
            coin_key, mapped_regime, uncertainty_label, survival_prob,
            direction, confidence_pct, ev, is_tradable, reject_reason
        )

        # Safe extraction for entry_features
        try:
            rsi_val = float(rsi)
        except:
            rsi_val = 50.0

        try:
            atr_pct_val = float(atr_pct)
        except:
            atr_pct_val = 1.0

        try:
            vol_ratio_val = float(vol_ratio)
        except:
            vol_ratio_val = 1.0

        try:
            trend_score_val = float(trend_score)
        except:
            trend_score_val = 50.0

        try:
            momentum_score_val = float(momentum_score)
        except:
            momentum_score_val = 50.0

        try:
            ema9 = float(indicators.get("ema", {}).get(9, 0))
            ema21 = float(indicators.get("ema", {}).get(21, 0))
            ema50 = float(indicators.get("ema", {}).get(50, 0))
            ema_align = bool((ema9 > ema21 > ema50) or (ema9 < ema21 < ema50))
        except:
            ema_align = False

        try:
            body_wick = float(indicators.get("body_wick_ratio", 1.0))
        except:
            body_wick = 1.0
            
        entry_features_dict = {
            "symbol": coin_key,
            "direction": direction,
            "timeframe": timeframe,
            "entry_price": float(close),
            "timestamp": float(time.time()),
            "RSI": rsi_val,
            "ATR percent": atr_pct_val,
            "volume_ratio": vol_ratio_val,
            "trend_strength": trend_score_val,
            "momentum_score": momentum_score_val,
            "EMA alignment": ema_align,
            "candle body/wick ratio": body_wick,
            "market_regime": mapped_regime,
            "BTC direction": btc_trend,
            # Model 2 features compatibility:
            "spread": spread_percent,
            "funding": funding_rate,
            "oi_delta": oi_delta,
            "volatility_regime": atr_pct,
            # Advanced filters:
            "entry_quality_score": entry_quality_score,
            "btc_alignment_score": btc_alignment_val,
            "wick_trap_score": wick_ratio,
            "breakout_confirmation_score": breakout_strength,
            "volume_confirmation_score": volume_confirmation,
            "quality_multiplier": quality_multiplier
        }

        return {
            "direction": direction,
            "direction_label": direction_label,
            "direction_color": direction_color,
            "confidence": round(confidence_pct),
            "p_win": round(p_win, 4),
            "ev": round(ev, 4),
            "is_tradable": is_tradable,
            "reject_reason": reject_reason,
            "adaptive_threshold": round(adaptive_threshold, 2),
            "reward_risk_ratio": round(reward_r / risk_r, 2),
            "weighted_score": round(total_vote_score, 3),
            "entry": round(close, 6),
            "stop_loss": round(stop_loss, 6),
            "take_profit": [round(tp, 6)],
            "support_level": support_level,
            "resistance_level": resistance_level,
            "risk_r": round(risk_r, 2),
            "reward_r": round(reward_r * momentum_multiplier, 2),
            "regime": mapped_regime,
            "timeframe": timeframe,
            "trade_acceptance_probability": round(trade_acceptance_probability, 4),
            "meta_probability_threshold": round(meta_threshold, 4),
            "uncertainty": round(uncertainty, 4),
            "uncertainty_label": uncertainty_label,
            "mc_survival_probability": round(survival_prob, 4),
            "mc_ruin_probability": round(ruin_prob, 4),
            "mc_worst_drawdown": round(worst_dd, 2),
            "quantum_score": round(intel_res["final_score"], 2),
            "similarity_score": round(intel_res["similarity_score"], 4),
            "edge_multiplier": round(intel_res["edge_multiplier"], 2),
            "fakeout_prob": round(intel_res["fakeout_prob"], 2),
            "trade_quality_score": trade_quality_score,
            "risk_multiplier": risk_multiplier,
            "htf_alignment_score": htf_alignment_score,
            "micro": {
                "spread": round(spread_percent, 4),
                "funding": round(funding_rate, 6),
                "oi_delta": round(oi_delta, 2)
            },
            "entry_features": entry_features_dict,
            "scores": {exp.name: round(exp.raw_score, 3) for exp in experts},
            "ai_comment": ai_comment,
            "disclaimer": DISCLAIMER,
            "ml_data": ml_data,
            "intelligence_report": intelligence_report,
            # Advanced filters root variables:
            "entry_quality_score": entry_quality_score,
            "btc_alignment_score": btc_alignment_val,
            "wick_trap_score": wick_ratio,
            "breakout_confirmation_score": breakout_strength,
            "volume_confirmation_score": volume_confirmation,
            "quality_multiplier": quality_multiplier,
            "macro_risk_multiplier": macro_risk_multiplier,
            "macro_level": macro_level
        }

    def _generate_ai_comment(self, coin, regime, uncertainty, survival,
                             direction, confidence, ev, is_tradable, reject_reason) -> str:
        lines = []
        lines.append(f"🤖 {coin} Ensemble AI Analizi: [{regime}] rejiminde, {uncertainty} belirsizlik tespit edildi.")
        
        if is_tradable:
            lines.append(
                f"✅ Pozitif EV ({ev:.3f}) ve %{survival*100:.1f} Monte Carlo Sağkalım güveniyle "
                f"işlem açılabilir olarak onaylandı!"
            )
        else:
            lines.append(f"❌ Filtre Engelini Geçemedi: {reject_reason}.")
        
        return " ".join(lines)

    def _empty_signal(self) -> dict:
        return {
            "direction": "NEUTRAL",
            "direction_label": "❓ Veri Yetersiz",
            "direction_color": "#9E9E9E",
            "confidence": 0,
            "p_win": 0.50,
            "ev": -1.0,
            "is_tradable": False,
            "reject_reason": "Yetersiz piyasa verisi",
            "adaptive_threshold": 55.0,
            "reward_risk_ratio": 1.0,
            "weighted_score": 0,
            "entry": 0, "stop_loss": 0,
            "take_profit": [0],
            "support_level": 0.0,
            "resistance_level": 0.0,
            "risk_r": 2.0, "reward_r": 2.0,
            "regime": "RANGE",
            "timeframe": "1h",
            "trade_acceptance_probability": 0.90,
            "uncertainty": 1.0,
            "uncertainty_label": "YÜKSEK",
            "mc_survival_probability": 0.50,
            "mc_ruin_probability": 0.50,
            "mc_worst_drawdown": -100.0,
            "trade_quality_score": 50,
            "risk_multiplier": 0.5,
            "htf_alignment_score": 50,
            "micro": {"spread": 0.02, "funding": 0.0, "oi_delta": 0.0},
            "entry_features": {"spread": 0.02, "funding": 0.0, "oi_delta": 0.0, "volatility_regime": 1.0},
            "scores": {}, "ai_comment": "Analiz için yeterli veri bulunamadı.",
            "disclaimer": DISCLAIMER,
            "ml_data": {},
            "intelligence_report": {
                "trend_score": 50,
                "momentum_score": 50,
                "liquidity_score": 50,
                "psychology_score": 50,
                "volatility_score": 50,
                "risk_score": 50,
                "continuation_probability": "LOW",
                "final_decision": "AVOID",
                "exit_efficiency": 50,
                "patience_score": 50,
                "fakeout_prob": 50.0,
                "mc_survival_prob": 50.0,
                "ev": -1.0,
                "trade_quality_score": 50,
                "htf_alignment_score": 50
            }
        }
