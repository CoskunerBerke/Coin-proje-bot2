"""
Kripto Coin Analiz Uygulaması — Alım/Satım ve Pozisyon Yöneticisi
Kuantitatif Kelly Criterion tabanlı dinamik boyutlandırma ve gelişmiş risk kontrolleri içerir.
"""

import ccxt
import os
import json
import time
import numpy as np
from datetime import datetime, timezone, timedelta

# Turkey Time Zone (UTC+3)
tr_tz = timezone(timedelta(hours=3))
from config import BINANCE_API_KEY, BINANCE_SECRET_KEY, BOT_SETTINGS
from log_manager import add_log
from db_manager import db_manager

TRADE_LOG_FILE = "bot_trades.json"

import pandas as pd
from technical_analysis import TechnicalAnalyzer

class TradeExecutor:
    def __init__(self, simulation_mode=True):
        self.simulation_mode = simulation_mode
        self.notifier = None # Telegram Bildirimcisi (Main'den set edilecek)
        self.analyzer = TechnicalAnalyzer()
        self.exchange = None
        if not simulation_mode:
            try:
                self.exchange = ccxt.binance({
                    'apiKey': BINANCE_API_KEY,
                    'secret': BINANCE_SECRET_KEY,
                    'enableRateLimit': True,
                    'options': {'defaultType': 'spot'}
                })
            except: pass

    def calculate_momentum_score(self, df, ta_result, direction) -> float:
        try:
            if df is None or df.empty or "indicators" not in ta_result:
                return 0.5
                
            ind = ta_result["indicators"]
            adx = ind.get("adx", 20)
            adx_norm = min(adx / 50.0, 1.0)
            
            # EMA Alignment
            ema9 = ind["ema"].get(9, 0)
            ema21 = ind["ema"].get(21, 0)
            ema50 = ind["ema"].get(50, 0)
            ema200 = ind["ema"].get(200, 0)
            
            ema_align = 0.0
            if direction == "LONG":
                if ema9 > ema21 > ema50 > ema200:
                    ema_align = 1.0
                elif ema9 > ema21 > ema50:
                    ema_align = 0.7
                elif ema9 > ema21:
                    ema_align = 0.4
            else: # SHORT
                if ema9 < ema21 < ema50 < ema200:
                    ema_align = 1.0
                elif ema9 < ema21 < ema50:
                    ema_align = 0.7
                elif ema9 < ema21:
                    ema_align = 0.4
                    
            trend_strength = (adx_norm * 0.6) + (ema_align * 0.4)
            
            # Volume Strength
            rel_vol = df['relative_volume'].iloc[-1] if 'relative_volume' in df.columns else 1.0
            if np.isnan(rel_vol) or np.isinf(rel_vol):
                rel_vol = 1.0
            vol_norm = min(rel_vol / 2.5, 1.0)
            
            climax = 1.0 if ta_result.get("volume_analysis", {}).get("is_climax", False) else 0.0
            volume_strength = (vol_norm * 0.7) + (climax * 0.3)
            
            # Breakout Strength
            vol_regime = ta_result.get("volatility", {})
            sq_breakout = vol_regime.get("squeeze_breakout", "NONE")
            
            breakout_strength = 0.2
            if direction == "LONG" and sq_breakout == "BULLISH":
                breakout_strength = 1.0
            elif direction == "SHORT" and sq_breakout == "BEARISH":
                breakout_strength = 1.0
            else:
                vol_level = vol_regime.get("level", "Normal")
                if vol_level == "Çok Yüksek" or vol_level == "Yüksek":
                    breakout_strength = 0.6
                elif vol_level == "Normal":
                    breakout_strength = 0.4
                else:
                    breakout_strength = 0.1
                    
            # Candle Expansion & RSI
            close_val = df['close'].iloc[-1]
            open_val = df['open'].iloc[-1]
            atr = ind.get("atr", 0.01)
            body_size = abs(close_val - open_val)
            body_norm = min(body_size / (atr + 1e-8), 1.0)
            
            rsi = ind.get("rsi", 50)
            if direction == "LONG":
                rsi_score = max(0.0, min((rsi - 40) / 30.0, 1.0))
            else:
                rsi_score = max(0.0, min((60 - rsi) / 30.0, 1.0))
                
            candle_strength = (body_norm * 0.5) + (rsi_score * 0.5)
            
            # Final Momentum Score
            score = (
                trend_strength * 0.35 +
                volume_strength * 0.25 +
                breakout_strength * 0.20 +
                candle_strength * 0.20
            )
            return round(float(max(0.0, min(score, 1.0))), 2)
        except Exception:
            return 0.5

    def get_balance(self, trades=None):
        if self.simulation_mode or not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
            if trades is None:
                trades = self.get_trade_history()
            total_pnl = 0.0
            for t in trades:
                if t.get("durum") == "KAPALI":
                    total_pnl += t.get("pnl_usdt", 0)
                else:
                    if t.get("tp2_hit", False):
                        total_pnl += t.get("tp1_pnl_usdt", 0) + t.get("tp2_pnl_usdt", 0)
                    elif t.get("tp1_hit", False):
                        total_pnl += t.get("tp1_pnl_usdt", 0)
            
            # 🔒 Hafıza Tabanlı Bakiye Koruması:
            # Eğer trades dosyasında kapanmış işlem yoksa ama hafızada varsa,
            # hafızadaki PNL'leri kullanarak bakiyeyi düzelt (Render restart koruması)
            closed_in_trades = [t for t in trades if t.get("durum") == "KAPALI"]
            if not closed_in_trades:
                try:
                    memory_file = "coin_trade_memory.json"
                    if os.path.exists(memory_file):
                        with open(memory_file, "r", encoding="utf-8") as f:
                            memory = json.load(f)
                        memory_pnl = 0.0
                        for coin_key, entries in memory.items():
                            for entry in entries:
                                memory_pnl += entry.get("pnl_usdt", 0)
                        if abs(memory_pnl) > abs(total_pnl):
                            total_pnl = memory_pnl
                except Exception:
                    pass
            
            starting = BOT_SETTINGS.get("starting_balance", 1000.0)
            return starting + total_pnl
        try:
            balance = self.exchange.fetch_balance()
            return balance['free'].get('USDT', 0)
        except:
            if trades is None:
                trades = self.get_trade_history()
            total_pnl = 0.0
            for t in trades:
                if t.get("durum") == "KAPALI":
                    total_pnl += t.get("pnl_usdt", 0)
                else:
                    if t.get("tp2_hit", False):
                        total_pnl += t.get("tp1_pnl_usdt", 0) + t.get("tp2_pnl_usdt", 0)
                    elif t.get("tp1_hit", False):
                        total_pnl += t.get("tp1_pnl_usdt", 0)
            starting = BOT_SETTINGS.get("starting_balance", 1000.0)
            return starting + total_pnl

    def execute_trade(self, coin: str, signal_data: dict):
        # Aktif pozisyon kontrolü (Zaten açıksa tekrar açma)
        history = self.get_trade_history()
        active_trades = [t for t in history if t.get("durum") == "AÇIK" and t.get("coin") == coin]
        if active_trades:
            return {"status": "skipped", "reason": "Zaten açık pozisyon var"}

        # ⏳ REENTRY COOLDOWN CHECK (30 saniye bekleme süresi — AGRESİF)
        REENTRY_COOLDOWN_SECONDS = 30
        last_closed_same_coin = [t for t in history if t.get("coin") == coin and t.get("durum") == "KAPALI"]
        if last_closed_same_coin:
            last_close = last_closed_same_coin[0]
            try:
                close_time_str = last_close.get("kapanis_tarihi")
                if close_time_str:
                    close_time = datetime.strptime(close_time_str, "%Y-%m-%d %H:%M:%S")
                    now_naive = datetime.now(tr_tz).replace(tzinfo=None)
                    elapsed = (now_naive - close_time).total_seconds()
                    if elapsed < REENTRY_COOLDOWN_SECONDS:
                        return {"status": "skipped", "reason": f"Re-entry Cooldown Aktif ({int(REENTRY_COOLDOWN_SECONDS - elapsed)}s kaldı)"}
            except Exception as re_err:
                pass

        direction = signal_data["direction"]
        if direction == "NEUTRAL": return {"status": "skipped", "reason": "Nötr sinyal"}

        # 🚨 DEVRE KESİCİ (Circuit Breaker): Son 3 işlem zararla kapandıysa ve 1 saat geçmediyse engelle
        closed_trades = [t for t in history if t.get("durum") == "KAPALI"]
        if len(closed_trades) >= 3:
            last_3 = closed_trades[:3]
            if all(t.get("pnl_usdt", 0) <= 0 for t in last_3):
                try:
                    last_close_time_str = last_3[0].get("kapanis_tarihi")
                    if last_close_time_str:
                        last_close_time = datetime.strptime(last_close_time_str, "%Y-%m-%d %H:%M:%S")
                        now_naive = datetime.now(tr_tz).replace(tzinfo=None)
                        time_diff = now_naive - last_close_time
                        if time_diff < timedelta(minutes=20):  # AGRESİF: 20 dakika (eskiden 1 saat)
                            remaining_minutes = int(20 - (time_diff.total_seconds() / 60))
                            msg = f"🚨 DEVRE KESİCİ AKTİF: Son 3 işlem zararla kapandı! {remaining_minutes} dakika soğuma süresi kaldı."
                            add_log(msg)
                            return {"status": "skipped", "reason": msg}
                except Exception as cb_err:
                    add_log(f"⚠️ Devre kesici kontrol hatası: {str(cb_err)}")

        entry_price = signal_data["entry"]
        stop_loss = signal_data["stop_loss"]
        take_profit = signal_data["take_profit"][0]
        
           # 🧮 1. Kelly Criterion & Volatility-Normalized Risk Parity Sizing
        p = signal_data.get("p_win", 0.50)
        R = signal_data.get("reward_risk_ratio", 1.5)
        
        # Kelly fraction calculation as baseline input
        kelly_fraction = p - ((1.0 - p) / R)
        kelly_fraction = max(0.01, kelly_fraction)
        
        # Win streak analysis
        history = self.get_trade_history()
        balance = self.get_balance(trades=history)
        closed_trades = [t for t in history if t.get("durum") == "KAPALI"]
        
        win_streak = 0
        for t in closed_trades[:5]:
            if t.get("pnl_usdt", 0) > 0:
                win_streak += 1
            else:
                break
                
        kelly_multiplier = 0.25 + (win_streak * 0.05)
        kelly_multiplier = min(0.50, kelly_multiplier)
        
        # Standard baseline risk is 1.5% of account equity
        risk_pct = 0.015
        
        # Risk Multiplier from signal generator (0.5 or 1.0)
        risk_multiplier = signal_data.get("risk_multiplier", 1.0)
        
        # Stop Distance Pct
        stop_distance_pct = abs(entry_price - stop_loss) / entry_price
        if stop_distance_pct <= 0.001:
            stop_distance_pct = 0.015
            
        # 🛡️ 2. Gelişmiş Risk Azaltma Çarpanları
        drawdown_multiplier = 1.0
        starting = BOT_SETTINGS.get("starting_balance", 1000.0)
        if balance < starting:
            drawdown_pct = (starting - balance) / starting
            drawdown_multiplier = max(0.1, 1.0 - (drawdown_pct * 3.0))
            
        streak_multiplier = 1.0
        if len(closed_trades) >= 3:
            last_3 = closed_trades[:3]
            if all(t.get("pnl_usdt", 0) <= 0 for t in last_3):
                streak_multiplier = 0.5
                add_log("⚠️ KAYBETME SERİSİ TESPİT EDİLDİ: Sermaye koruması için pozisyon boyutu yarıya indirildi.")
                
        if len(closed_trades) >= 5:
            last_5 = closed_trades[:5]
            if all(t.get("pnl_usdt", 0) <= 0 for t in last_5):
                streak_multiplier = 0.25
                add_log("🚨 AĞIR KAYBETME SERİSİ TESPİT EDİLDİ: Sermaye koruması maksimuma çıkarıldı (Pozisyon riski %75 düşürüldü).")

        regime_multiplier = 1.0
        regime = signal_data.get("regime", "RANGE")
        if "SIDEWAYS" in regime or "RANGE" in regime:
            regime_multiplier = 0.7
            
        correlation_multiplier = 1.0
        open_trades = [ot for ot in history if ot.get("durum") == "AÇIK"]
        
        if open_trades:
            try:
                from data_fetcher import DataFetcher
                corr_fetcher = DataFetcher()
                new_df = corr_fetcher.fetch_ohlcv(coin, "1h", limit=30)
                if not new_df.empty:
                    new_closes = new_df["close"].values
                    max_corr = 0.0
                    for ot in open_trades:
                        ot_coin = ot.get("coin")
                        if ot_coin == coin: continue
                        
                        ot_df = corr_fetcher.fetch_ohlcv(ot_coin, "1h", limit=30)
                        if not ot_df.empty:
                            ot_closes = ot_df["close"].values
                            min_len = min(len(new_closes), len(ot_closes))
                            if min_len >= 15:
                                corr_matrix = np.corrcoef(new_closes[-min_len:], ot_closes[-min_len:])
                                corr = abs(corr_matrix[0, 1])
                                if not np.isnan(corr):
                                    max_corr = max(max_corr, corr)
                    
                    if max_corr >= 0.70:
                        correlation_multiplier = 0.50
                        add_log(f"⚠️ PORTFÖY KORELASYON UYARISI ({coin} ile max r: {max_corr:.2f}): Risk birikimini önlemek için pozisyon boyutu %50 düşürüldü.")
            except Exception as corr_err:
                add_log(f"⚠️ Portföy korelasyon analizi hatası: {str(corr_err)}")

        # Combined final risk multiplier with probability scaling
        prob = signal_data.get("trade_acceptance_probability", 0.55)
        thresh = signal_data.get("meta_probability_threshold", 0.55)
        prob_multiplier = 1.0
        if prob < thresh + 0.10:
            prob_multiplier = 0.5
            add_log(f"📉 Olasılık Eşiğe Yakın (%{prob*100:.1f} < Eşik %{(thresh+0.1)*100:.1f}): Pozisyon büyüklüğü koruma amaçlı 0.50x çarpanıyla ölçeklendi.")
            
        final_risk_multiplier = risk_multiplier * drawdown_multiplier * streak_multiplier * regime_multiplier * correlation_multiplier * prob_multiplier
        
        # 🌍 Makro Risk Çarpanı (Sadece BOT2_AGGRESSIVE, sadece YENİ işlemler)
        # Normal koşullarda macro_risk_multiplier = 1.0 → sıfır etki
        macro_risk_mult = signal_data.get("macro_risk_multiplier", 1.0)
        if macro_risk_mult < 1.0:
            final_risk_multiplier *= macro_risk_mult
            add_log(f"🌍 Makro Risk: Pozisyon boyutu {macro_risk_mult:.0%}'e düşürüldü (Seviye: {signal_data.get('macro_level', 'N/A')})")
        
        # Dinamik Kasa Yönetimi (Bileşik Getiri) & Entry Quality Boyutlandırma
        risk_per_trade = BOT_SETTINGS.get("risk_per_trade", 0.10)
        quality_multiplier = signal_data.get("quality_multiplier", 1.0)
        base_fraction = risk_per_trade * final_risk_multiplier * quality_multiplier
        
        # Sınırlandırma: Bir işleme kasanın en fazla %20'si, en az %2'si girebilir.
        final_fraction = max(0.02, min(0.20, base_fraction))
        amount_usdt = balance * final_fraction
        
        if amount_usdt < 10.0:
            amount_usdt = min(10.0, balance)
            if balance < 10.0:
                add_log(f"⚠️ {coin} işlemi yetersiz bakiye nedeniyle iptal edildi (Bakiye: ${balance:.2f}).")
                return {"status": "skipped", "reason": "INSUFFICIENT_BALANCE"}
            
        final_fraction = amount_usdt / balance
        
        # Timeframe'i dakikaya çevir (Dikey Bariyer hesabı için)
        timeframe_str = signal_data.get("timeframe", "1m")
        tf_multiplier = 1
        if "h" in timeframe_str: tf_multiplier = 60
        elif "d" in timeframe_str: tf_multiplier = 1440
        elif "w" in timeframe_str: tf_multiplier = 10080
        
        try:
            tf_num = int("".join(c for c in timeframe_str if c.isdigit()))
        except:
            tf_num = 1
        timeframe_minutes = tf_num * tf_multiplier
        
        start_ts = time.time()
        vertical_barrier_ts = start_ts + (24 * timeframe_minutes * 60) # 24 Mum sonra dikey bariyer

        trade_record = {
            "id": str(int(datetime.now(tr_tz).timestamp())),
            "tarih": datetime.now(tr_tz).strftime("%Y-%m-%d %H:%M:%S"),
            "coin": coin,
            "yon": direction,
            "durum": "AÇIK",
            "giris_fiyati": entry_price,
            "miktar_usdt": round(amount_usdt, 2),
            "giris_bakiye": round(balance, 2),
            "miktar_yuzde": round(final_fraction * 100, 2),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "support_level": signal_data.get("support_level", 0.0),
            "resistance_level": signal_data.get("resistance_level", 0.0),
            "kaldirac": signal_data.get("leverage", 1),
            "cikis_fiyati": None,
            "pnl_yuzde": 0,
            "pnl_usdt": 0,
            "mod": "SİMÜLASYON" if self.simulation_mode else "GERÇEK",
            "ml_data": signal_data.get("ml_data", {}),
            "ml_risk": signal_data.get("risk", {}).get("score", 50),
            "p_win": round(p, 4),
            "ev": round(signal_data.get("ev", 0), 4),
            "trade_acceptance_probability": signal_data.get("trade_acceptance_probability", 0.5),
            "meta_probability_threshold": signal_data.get("meta_probability_threshold", 0.5),
            "predicted_long_edge": round(prob if direction == "LONG" else 1.0 - prob, 4),
            "predicted_short_edge": round(1.0 - prob if direction == "LONG" else prob, 4),
            # 🔗 FinML Zengin Veri Saklama
            "market_regime": signal_data.get("regime", "RANGE"),
            "entry_features": signal_data.get("entry_features", {}),
            "intelligence_report": signal_data.get("intelligence_report", {}),
            "start_timestamp": start_ts,
            "vertical_barrier_timestamp": vertical_barrier_ts,
            "max_favorable_excursion": 0.0,
            "max_adverse_excursion": 0.0,
            "exit_reason": None,
            "realized_R_multiple": 0.0,
            "holding_time": 0.0,
            # 📊 Yeni Metrikler (Momentum ve Performans Analizi)
            "momentum_score_exit": 0.0,
            "peak_pnl_usdt": 0.0,
            "peak_pnl_pct": 0.0,
            "exit_efficiency": 0.0,
            "trailing_activation_level": None,
            "reentry_count": len([x for x in history if x.get("coin") == coin and x.get("durum") == "KAPALI"]),
            "trend_continuation_score": 0.0,
            # Advanced Filter Scores & Trackers
            "entry_quality_score": signal_data.get("entry_quality_score", 0.5),
            "btc_alignment_score": signal_data.get("btc_alignment_score", 0.5),
            "wick_trap_score": signal_data.get("wick_trap_score", 0.0),
            "breakout_confirmation_score": signal_data.get("breakout_confirmation_score", 0.5),
            "volume_confirmation_score": signal_data.get("volume_confirmation_score", 0.5),
            "quality_multiplier": quality_multiplier,
            "peak_momentum_score": 0.0,
            "invalidation_blocked_by_min_hold": False,
            "invalidation_threshold_used": None,
            # TP1 Post-Hit Trackers
            "tp1_hit_time": None,
            "pnl_at_tp1": 0.0,
            "post_tp1_max_pnl": 0.0,
            "post_tp1_exit_reason": None,
            "tp1_to_exit_giveback": 0.0,
            "trade_state": {
                "tp1_hit": False,
                "breakeven_active": False,
                "trailing_active": False,
                "trend_extension_mode": False
            }
        }

        self._save_trade(trade_record)
        
        if self.notifier:
            self.notifier.send_trade_alert(trade_record, is_open=True, balance=balance)

        return {"status": "success", "msg": f"{coin} {direction} pozisyonu açıldı."}

    def update_positions(self, fetcher, cf_analyzer=None):
        """Açık pozisyonları güncel fiyatla kontrol eder, Triple Barrier ve MFE/MAE güncellemelerini uygular."""
        trades = self.get_trade_history()
        updated = False
        current_ts = time.time()
        
        for t in trades:
            if t.get("durum") == "AÇIK":
                try:
                    # Ensure trade_state structure exists
                    if "trade_state" not in t:
                        t["trade_state"] = {
                            "tp1_hit": t.get("tp1_hit", False),
                            "breakeven_active": t.get("break_even_activated", False),
                            "trailing_active": t.get("trailing_active", False),
                            "trend_extension_mode": False
                        }
                    
                    ticker = fetcher.fetch_ticker(t.get("coin"))
                    current_price = ticker["last"]
                    
                    # 1. Fetch OHLCV data and compute momentum score
                    timeframe = t.get("timeframe", "15m")
                    df = fetcher.fetch_ohlcv(t["coin"], timeframe=timeframe)
                    ta_result = self.analyzer.full_analysis(df)
                    momentum_score = self.calculate_momentum_score(df, ta_result, t["yon"])
                    t["momentum_score_exit"] = momentum_score
                    
                    commission_rate = 0.0004
                    entry_price = t["giris_fiyati"]
                    stop_loss = t["stop_loss"]
                    risk_distance = abs(entry_price - stop_loss)
                    if risk_distance == 0.0: risk_distance = entry_price * 0.02
                    
                    if t["yon"] == "LONG":
                        pnl_pct = ((current_price - entry_price) / entry_price) * 100
                        deviation = current_price - entry_price
                    else:
                        pnl_pct = ((entry_price - current_price) / entry_price) * 100
                        deviation = entry_price - current_price
                    
                    leverage = t.get("kaldirac", 1)
                    
                    # 📈 Canlı PNL Hesaplaması (Dinamik ve Kademeli Kapatma Uyumlu)
                    raw_pnl_pct = pnl_pct * leverage
                    
                    if t.get("tp2_hit", False):
                        # %75'i satıldı, kalan %25 canlı fiyatla güncellenir
                        remaining_usdt = t["miktar_usdt"] * 0.25
                        remaining_pnl = (((pnl_pct * leverage) / 100) * remaining_usdt) - (remaining_usdt * commission_rate)
                        t["pnl_usdt"] = round(t["tp1_pnl_usdt"] + t["tp2_pnl_usdt"] + remaining_pnl, 2)
                        t["pnl_yuzde"] = round((t["pnl_usdt"] / t["miktar_usdt"]) * 100, 2)
                    elif t.get("tp1_hit", False):
                        # %50'si satıldı, kalan %50 canlı fiyatla güncellenir
                        remaining_usdt = t["miktar_usdt"] * 0.50
                        remaining_pnl = (((pnl_pct * leverage) / 100) * remaining_usdt) - (remaining_usdt * commission_rate)
                        t["pnl_usdt"] = round(t["tp1_pnl_usdt"] + remaining_pnl, 2)
                        t["pnl_yuzde"] = round((t["pnl_usdt"] / t["miktar_usdt"]) * 100, 2)
                    else:
                        t["pnl_yuzde"] = round(raw_pnl_pct - (commission_rate * 2 * 100), 2)
                        t["pnl_usdt"] = round((((pnl_pct * leverage) / 100) * t["miktar_usdt"]) - (t["miktar_usdt"] * commission_rate * 2), 2)
                        
                    t["guncel_fiyat"] = current_price
                    
                    # Peak stats
                    if "peak_pnl_usdt" not in t: t["peak_pnl_usdt"] = 0.0
                    if "peak_pnl_pct" not in t: t["peak_pnl_pct"] = 0.0
                    t["peak_pnl_usdt"] = max(t["peak_pnl_usdt"], t["pnl_usdt"])
                    t["peak_pnl_pct"] = max(t["peak_pnl_pct"], t["pnl_yuzde"])
                    t["peak_pnl_yuzde"] = t["peak_pnl_pct"] # Backwards compatibility
                    
                    t["peak_momentum_score"] = max(t.get("peak_momentum_score", 0.0), momentum_score)
                    
                    # 📈 MAE / MFE Hesaplaması (Risk Mesafesine Göre R Cinsinden)
                    excursion_r = deviation / risk_distance
                    if excursion_r > 0:
                        t["max_favorable_excursion"] = round(max(t.get("max_favorable_excursion", 0.0), excursion_r), 4)
                    else:
                        t["max_adverse_excursion"] = round(max(t.get("max_adverse_excursion", 0.0), abs(excursion_r)), 4)
                        
                    # Holding Time (Dakika)
                    t["holding_time"] = round((current_ts - t.get("start_timestamp", current_ts)) / 60, 2)
                    
                    # Adaptif TP1 / Trailing Activation Eşiği
                    base_tp1 = BOT_SETTINGS.get("tp1_profit_take_pct", 4.50)
                    atr_percent = ta_result.get("volatility", {}).get("atr_pct", t.get("entry_features", {}).get("volatility_regime", 1.0))
                    
                    if momentum_score >= 0.75:
                        tp1_pct = max(base_tp1, atr_percent * 2.5)
                    elif momentum_score >= 0.60:
                        tp1_pct = max(base_tp1 * 0.9, atr_percent * 2.0)
                    else:
                        tp1_pct = max(3.0, atr_percent * 1.5)

                    # TP1 Hit Metrics Tracking
                    if t["pnl_yuzde"] >= tp1_pct and not t.get("tp1_hit_recorded", False):
                        t["tp1_hit_recorded"] = True
                        t["tp1_hit_time"] = datetime.now(tr_tz).strftime("%Y-%m-%d %H:%M:%S")
                        t["pnl_at_tp1"] = t["pnl_yuzde"]
                        t["post_tp1_max_pnl"] = t["pnl_yuzde"]
                        
                    if t.get("tp1_hit_recorded", False):
                        t["post_tp1_max_pnl"] = max(t.get("post_tp1_max_pnl", t["pnl_yuzde"]), t["pnl_yuzde"])

                    # Peak PnL Protection check
                    peak_pnl_pct = t.get("peak_pnl_pct", 0.0)
                    peak_protection_triggered = False
                    if peak_pnl_pct >= 2.0 and t["pnl_yuzde"] <= 0.3:
                        if momentum_score >= 0.65:
                            # Tighten trailing stop
                            if not t.get("trailing_active", False):
                                t["trailing_active"] = True
                                t["trade_state"]["trailing_active"] = True
                                t["trailing_activation_level"] = round(current_price, 4)
                            
                            atr = ta_result["indicators"].get("atr", entry_price * 0.01)
                            trailing_distance = atr * 0.5
                            if t["yon"] == "LONG":
                                t["trailing_stop_level"] = t.get("highest_price", current_price) - trailing_distance
                                if current_price <= t["trailing_stop_level"]:
                                    peak_protection_triggered = True
                            else:
                                t["trailing_stop_level"] = t.get("lowest_price", current_price) + trailing_distance
                                if current_price >= t["trailing_stop_level"]:
                                    peak_protection_triggered = True
                        else:
                            peak_protection_triggered = True

                    # Momentum Decay Exit check
                    peak_momentum_score_val = t.get("peak_momentum_score", 0.0)
                    momentum_decay_triggered = False
                    if peak_momentum_score_val >= 0.70 and momentum_score < 0.45:
                        if t["pnl_yuzde"] > 0.0:
                            momentum_decay_triggered = True
                        else:
                            if not t.get("momentum_decay_sl_tightened", False):
                                if t["yon"] == "LONG":
                                    new_sl = entry_price - (entry_price - t["stop_loss"]) * 0.5
                                    t["stop_loss"] = max(t["stop_loss"], new_sl)
                                else:
                                    new_sl = entry_price + (t["stop_loss"] - entry_price) * 0.5
                                    t["stop_loss"] = min(t["stop_loss"], new_sl)
                                t["momentum_decay_sl_tightened"] = True
                                add_log(f"📉 {t['coin']} Momentum Azalması (Peak: {peak_momentum_score_val:.2f}, Güncel: {momentum_score:.2f}): Stop Loss sıkılaştırıldı ({t['stop_loss']:.4f}).")

                    # C) GÜÇLÜ MOMENTUM: Trailing Stop Aktivasyonu
                    if t["pnl_yuzde"] >= tp1_pct and momentum_score >= 0.65:
                        if not t.get("trailing_active", False):
                            t["trailing_active"] = True
                            t["trade_state"]["trailing_active"] = True
                            if momentum_score >= 0.80:
                                t["trade_state"]["trend_extension_mode"] = True
                            t["trailing_activation_level"] = round(current_price, 4)
                            add_log(f"📈 {t['coin']} Güçlü Momentum Takip Eden Stop Aktif Edildi (Fiyat: {current_price:.4f}, Momentum: {momentum_score:.2f}, Eşik: {tp1_pct:.2f}%)")
                            
                    # Update dynamic trend extension state if trailing is already active
                    if t.get("trailing_active", False):
                        if momentum_score >= 0.80:
                            t["trade_state"]["trend_extension_mode"] = True
                        elif momentum_score < 0.50:
                            t["trade_state"]["trend_extension_mode"] = False

                    trailing_stop_triggered = False
                    if t.get("trailing_active", False):
                        if t["yon"] == "LONG":
                            t["highest_price"] = max(t.get("highest_price", entry_price), current_price)
                        else:
                            t["lowest_price"] = min(t.get("lowest_price", entry_price), current_price)
                            
                        # Calculate ATR-based dynamic trailing distance (Optimized)
                        atr = ta_result["indicators"].get("atr", entry_price * 0.01)
                        if momentum_score >= 0.80:
                            trailing_distance = atr * 2.0
                        elif momentum_score >= 0.65:
                            trailing_distance = atr * 1.5
                        else:
                            trailing_distance = atr * 1.0
                            
                        if t["yon"] == "LONG":
                            t["trailing_stop_level"] = t["highest_price"] - trailing_distance
                            if current_price <= t["trailing_stop_level"]:
                                trailing_stop_triggered = True
                        else:
                            t["trailing_stop_level"] = t["lowest_price"] + trailing_distance
                            if current_price >= t["trailing_stop_level"]:
                                trailing_stop_triggered = True
                                
                    should_close = False
                    exit_reason = None
                    
                    weak_tp = max(
                        BOT_SETTINGS.get("weak_momentum_profit_take_pct", 3.0),
                        atr_percent * 1.25
                    )
                    
                    if peak_protection_triggered:
                        should_close = True
                        exit_reason = "PEAK_PROFIT_PROTECTION"
                    elif momentum_decay_triggered:
                        should_close = True
                        exit_reason = "MOMENTUM_DECAY_PROFIT_EXIT"
                    
                    # A) ZAYIF MOMENTUM (Zayıf Momentumla Kâr Al)
                    elif t["pnl_yuzde"] >= weak_tp and momentum_score < 0.45:
                        should_close = True
                        exit_reason = "WEAK_MOMENTUM_PROFIT_TAKE"
                        
                    # B) ORTA MOMENTUM (Orta Momentumla Kısmi Kâr Al ve Başabaş Noktası)
                    elif t["pnl_yuzde"] >= tp1_pct and 0.45 <= momentum_score < 0.65 and not t.get("tp1_hit", False):
                        t["tp1_hit"] = True
                        t["trade_state"]["tp1_hit"] = True
                        t["trade_state"]["breakeven_active"] = True
                        
                        t["tp1_hit_time"] = datetime.now(tr_tz).strftime("%Y-%m-%d %H:%M:%S")
                        t["pnl_at_tp1"] = t["pnl_yuzde"]
                        t["post_tp1_max_pnl"] = t["pnl_yuzde"]
                        
                        tp1_pnl_usdt = round(t["pnl_usdt"] * 0.5, 2)
                        t["tp1_pnl_usdt"] = tp1_pnl_usdt
                        t["stop_loss"] = entry_price  # Stop loss'u giriş fiyatına çek
                        t["break_even_activated"] = True
                        add_log(f"🎯 {t['coin']} Orta Momentum Kâr Al (+${tp1_pnl_usdt:.2f} realize edildi, kalan %50 için Stop Loss Giriş Fiyatına çekildi, Eşik: {tp1_pct:.2f}%).")
                        
                        if self.notifier:
                            self.notifier.send_partial_take_profit_alert(
                                trade=t,
                                tp_level=1,
                                realized_pnl=tp1_pnl_usdt,
                                balance=self.get_balance(trades=trades)
                            )
                            
                    # Takip Stop Çıkışı
                    elif trailing_stop_triggered:
                        should_close = True
                        exit_reason = "TRAILING_STRONG_MOMENTUM"
                        
                    # 1. Lower Barrier: Stop Loss
                    elif current_price <= t["stop_loss"] if t["yon"] == "LONG" else current_price >= t["stop_loss"]:
                        should_close = True
                        exit_reason = "SL (Alt Bariyer)"
                        
                    # 2. Upper Barrier: Take Profit (Acil Durum TP Limiti)
                    elif (current_price >= t["take_profit"] if t["yon"] == "LONG" else current_price <= t["take_profit"]):
                        should_close = True
                        exit_reason = "TP (Üst Bariyer)"
                        
                    # 2b. Structure-based Exit (Likidite Süpürme Koruması - Sweep Buffer Entegrasyonu)
                    elif t.get("support_level", 0.0) > 0 and t["yon"] == "LONG":
                        atr_pct = t.get("entry_features", {}).get("volatility_regime", 0.02)
                        buffer = t["giris_fiyati"] * atr_pct * 0.15
                        if current_price < (t["support_level"] - buffer):
                            should_close = True
                            exit_reason = "STRUCTURE (Fiyat Destek + Tampon Altına Kırıldı)"
                    elif t.get("resistance_level", 0.0) > 0 and t["yon"] == "SHORT":
                        atr_pct = t.get("entry_features", {}).get("volatility_regime", 0.02)
                        buffer = t["giris_fiyati"] * atr_pct * 0.15
                        if current_price > (t["resistance_level"] + buffer):
                            should_close = True
                            exit_reason = "STRUCTURE (Fiyat Direnç + Tampon Üstüne Kırıldı)"
                            
                    # 3. Zamana Dayalı Erken Zarar Çıkışı (6 Saat Barajı)
                    elif t["pnl_yuzde"] < -0.5 and t.get("holding_time", 0) >= 360.0:
                        should_close = True
                        exit_reason = "ZAMAN_BARAJI (Negatif PnL ile 6 Saat Geçti)"
                        
                    # 4. Vertical Barrier: Time Limit (24 Mum, Momentum Uyumlu)
                    else:
                        timeout_multiplier = 2.0 if momentum_score >= 0.65 else 1.0
                        timeframe_str = t.get("timeframe", "15m")
                        tf_multiplier = 1
                        if "h" in timeframe_str: tf_multiplier = 60
                        elif "d" in timeframe_str: tf_multiplier = 1440
                        elif "w" in timeframe_str: tf_multiplier = 10080
                        try:
                            tf_num = int("".join(c for c in timeframe_str if c.isdigit()))
                        except:
                            tf_num = 1
                        timeframe_minutes = tf_num * tf_multiplier
                        
                        max_holding_time_seconds = 24 * timeframe_minutes * 60 * timeout_multiplier
                        dynamic_vertical_barrier = t.get("start_timestamp", current_ts) + max_holding_time_seconds
                        
                        if current_ts >= dynamic_vertical_barrier:
                            should_close = True
                            exit_reason = "ZAMAN_ASIMI (Dikey Bariyer)"
                        
                    if should_close:
                        t["durum"] = "KAPALI"
                        t["cikis_fiyati"] = current_price
                        t["kapanis_tarihi"] = datetime.now(tr_tz).strftime("%Y-%m-%d %H:%M:%S")
                        t["exit_reason"] = exit_reason
                        t["realized_R_multiple"] = round(excursion_r, 4)
                        
                        # Exit efficiency and final scores
                        peak_pct = t.get("peak_pnl_pct", 0.0)
                        t["exit_efficiency"] = round(t["pnl_yuzde"] / peak_pct, 4) if peak_pct > 0 else 0.0
                        t["trend_continuation_score"] = momentum_score
                        
                        # Calculate custom quality_score
                        r_mult = float(t.get("realized_R_multiple", 0.0))
                        mfe = float(t.get("max_favorable_excursion", 0.0))
                        mae = float(t.get("max_adverse_excursion", 0.0))
                        mfe_mae_ratio = float(mfe / mae) if mae > 0 else float(mfe)
                        exit_eff = float(t.get("exit_efficiency", 0.0))
                        h_time = float(t.get("holding_time", 1.0))
                        
                        r_part = min(100.0, max(0.0, (r_mult + 1.5) * 22.0))
                        ratio_part = min(100.0, max(0.0, mfe_mae_ratio * 20.0))
                        eff_part = min(100.0, max(0.0, exit_eff * 100.0))
                        base_quality = (r_part * 0.4) + (ratio_part * 0.3) + (eff_part * 0.3)
                        time_penalty = min(15.0, (h_time / 60.0) * 2.0)
                        quality_score = round(max(0.0, min(100.0, base_quality - time_penalty)), 2)
                        
                        # Calculate outcome label
                        tp1_hit = bool(t.get("tp1_hit", False))
                        pnl_yuzde = float(t.get("pnl_yuzde", 0.0))
                        outcome = 1 if (tp1_hit or r_mult >= 0.75 or pnl_yuzde >= 1.0) else 0
                        
                        t["quality_score"] = quality_score
                        t["outcome"] = outcome
                        
                        # Update post-tp1 stats if hit
                        if t.get("tp1_hit_recorded", False):
                            t["post_tp1_exit_reason"] = exit_reason
                            t["tp1_to_exit_giveback"] = round(t.get("post_tp1_max_pnl", 0.0) - t["pnl_yuzde"], 2)
                        
                        # Create exit features and result metrics dictionaries
                        exit_features_dict = {
                            "exit_price": float(current_price),
                            "exit_timestamp": float(current_ts),
                            "pnl_usdt": float(t["pnl_usdt"]),
                            "pnl_yuzde": pnl_yuzde,
                            "realized_R_multiple": r_mult,
                            "max_favorable_excursion": mfe,
                            "max_adverse_excursion": mae,
                            "holding_time": h_time,
                            "exit_reason": exit_reason,
                            "tp1_hit": tp1_hit,
                            "tp2_hit": bool(t.get("tp2_hit", False)),
                            "quality_score": quality_score,
                            # Advanced filters:
                            "entry_quality_score": t.get("entry_quality_score", 0.5),
                            "btc_alignment_score": t.get("btc_alignment_score", 0.5),
                            "wick_trap_score": t.get("wick_trap_score", 0.0),
                            "breakout_confirmation_score": t.get("breakout_confirmation_score", 0.5),
                            "volume_confirmation_score": t.get("volume_confirmation_score", 0.5),
                            "peak_momentum_score": t.get("peak_momentum_score", 0.0),
                            "momentum_decay": t.get("peak_momentum_score", 0.0) - momentum_score,
                            "peak_pnl_pct": peak_pct,
                            "peak_to_realized_giveback": peak_pct - pnl_yuzde,
                            "invalidation_threshold_used": t.get("invalidation_threshold_used"),
                            "invalidation_blocked_by_min_hold": t.get("invalidation_blocked_by_min_hold", False),
                            # TP1 Post-Hit stats
                            "tp1_hit_time": t.get("tp1_hit_time"),
                            "pnl_at_tp1": t.get("pnl_at_tp1"),
                            "post_tp1_max_pnl": t.get("post_tp1_max_pnl"),
                            "post_tp1_exit_reason": t.get("post_tp1_exit_reason"),
                            "tp1_to_exit_giveback": t.get("tp1_to_exit_giveback")
                        }
                        
                        result_metrics_dict = exit_features_dict.copy()
                        
                        t["exit_features"] = exit_features_dict
                        t["result_metrics"] = result_metrics_dict
                        
                        # Log AI observation
                        pred_long = t.get("predicted_long_edge", 0.5)
                        pred_short = t.get("predicted_short_edge", 0.5)
                        add_log(f"🧠 AI_OBSERVATION: symbol={t['coin']} direction={t['yon']} predicted_long_edge={pred_long:.4f} predicted_short_edge={pred_short:.4f} actual_outcome={outcome} quality_score={quality_score:.2f}")

                        # 🧠 Phase 4: Kaydedilen bu işlemi Coin Hafızasına ekle!
                        try:
                            from coin_intelligence import CoinIntelligenceManager
                            coin_intel = CoinIntelligenceManager()
                            coin_intel.log_completed_trade(t["coin"], t)
                            
                            # 🧠 Telegram'a öğrenme güncellemesi gönder
                            if self.notifier:
                                try:
                                    memory_entry = coin_intel.memory.get(t["coin"], [{}])[-1]
                                    self.notifier.send_trade_learning_update(t, memory_entry)
                                except Exception as e_tg_learn:
                                    add_log(f"⚠️ Telegram Hafıza Bildirimi Hatası: {str(e_tg_learn)}")
                        except Exception as e_intel:
                            add_log(f"⚠️ Coin Hafıza Kayıt Hatası: {str(e_intel)}")
                        
                        # 🔮 Counterfactual POST_EXIT takibi başlat
                        if cf_analyzer:
                            try:
                                cf_analyzer.track_post_exit(t)
                            except Exception as cf_err:
                                add_log(f"⚠️ Counterfactual POST_EXIT Hatası: {str(cf_err)}")
                            
                        # Debug exit log
                        exit_log_msg = (
                            f"\n🚪 EXIT:\n"
                            f"symbol={t['coin']}\n"
                            f"reason={exit_reason}\n"
                            f"pnl_pct={t['pnl_yuzde']:.1f}\n"
                            f"pnl_usdt={t['pnl_usdt']:.2f}\n"
                            f"momentum_score={momentum_score:.2f}\n"
                            f"atr_percent={atr_percent:.2f}\n"
                            f"peak_pnl={t.get('peak_pnl_pct', 0.0):.1f}\n"
                            f"holding_time={int(t['holding_time'])}m"
                        )
                        add_log(exit_log_msg)
                        
                        if self.notifier:
                            self.notifier.send_trade_alert(t, is_open=False, balance=self.get_balance(trades=trades))
                            
                    updated = True
                except Exception as update_err:
                    add_log(f"⚠️ Pozisyon güncelleme döngü hatası ({t.get('coin')}): {str(update_err)}")
                    continue
        
        if updated:
            temp_file = TRADE_LOG_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(trades, f, indent=4)
            os.replace(temp_file, TRADE_LOG_FILE)
            try:
                db_manager.push_to_cloud(TRADE_LOG_FILE, "trades")
            except: pass

        try:
            self.update_avoided_losses(fetcher)
        except Exception as e:
            add_log(f"⚠️ Kaçınılan zarar güncelleme hatası: {str(e)}")

    def _save_trade(self, trade):
        history = self.get_trade_history()
        
        found = False
        for i, existing in enumerate(history):
            if existing.get("id") == trade.get("id"):
                history[i] = trade
                found = True
                break
                
        if not found:
            history.insert(0, trade)
            
        temp_file = TRADE_LOG_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
        os.replace(temp_file, TRADE_LOG_FILE)
        try:
            db_manager.push_to_cloud(TRADE_LOG_FILE, "trades")
        except: pass

    def get_trade_history(self):
        if os.path.exists(TRADE_LOG_FILE):
            try:
                with open(TRADE_LOG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: return []
        return []

    def save_trade_history(self, trades):
        """Kayıtlı işlem listesini atomik olarak dosyaya kaydeder."""
        temp_file = TRADE_LOG_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(trades, f, indent=4)
        os.replace(temp_file, TRADE_LOG_FILE)
        try:
            db_manager.push_to_cloud(TRADE_LOG_FILE, "trades")
        except: pass

    def track_avoided_trade(self, coin, signal_data, balance):
        """İşlem açılmaktan vazgeçilen/filtrelenen fırsatları zarar takibi için kaydeder."""
        try:
            avoided_file = "bot_avoided_trades.json"
            history = []
            if os.path.exists(avoided_file):
                try:
                    with open(avoided_file, "r", encoding="utf-8") as f:
                        history = json.load(f)
                except: pass
            
            if any(h["coin"] == coin and h["durum"] == "TAKİPTE" for h in history):
                return
                
            entry_price = signal_data.get("entry", 0.0)
            if entry_price == 0.0: return
            
            risked_usdt = round(balance * 0.05, 2)
            
            record = {
                "id": str(int(time.time())),
                "tarih": datetime.now(tr_tz).strftime("%Y-%m-%d %H:%M:%S"),
                "coin": coin,
                "yon": signal_data.get("direction", "LONG"),
                "durum": "TAKİPTE",
                "giris_fiyati": entry_price,
                "stop_loss": signal_data.get("stop_loss", 0.0),
                "take_profit": signal_data.get("take_profit", [0.0])[0],
                "risked_usdt": risked_usdt,
                "reject_reason": signal_data.get("reject_reason", "Bilinmeyen Filtre"),
                "start_timestamp": time.time(),
                "vertical_barrier_timestamp": time.time() + (24 * 60 * 60)
            }
            
            history.insert(0, record)
            temp_file = avoided_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4)
            os.replace(temp_file, avoided_file)
        except Exception as e:
            add_log(f"⚠️ Avoided trade kaydetme hatası: {str(e)}")

    def update_avoided_losses(self, fetcher):
        """Filtrelenen işlemlerin fiyat hareketlerini kontrol ederek kaçınılan zararı günceller."""
        avoided_file = "bot_avoided_trades.json"
        if not os.path.exists(avoided_file): return
        
        try:
            with open(avoided_file, "r", encoding="utf-8") as f:
                avoided_trades = json.load(f)
        except: return
        
        updated = False
        current_ts = time.time()
        
        for t in avoided_trades:
            if t.get("durum") == "TAKİPTE":
                try:
                    ticker = fetcher.fetch_ticker(t["coin"])
                    current_price = ticker["last"]
                    
                    stop_loss = t["stop_loss"]
                    take_profit = t["take_profit"]
                    
                    should_close = False
                    status = "TAKİPTE"
                    
                    entry_price = t["giris_fiyati"]
                    leverage = 3
                    if t["yon"] == "LONG":
                        pnl_pct = ((current_price - entry_price) / entry_price) * 100
                        if current_price <= stop_loss:
                            should_close = True
                            status = "BAŞARIYLA_KAÇINILDI"
                        elif current_price >= take_profit:
                            should_close = True
                            status = "KAÇIRILAN_FIRSAT"
                    else:
                        pnl_pct = ((entry_price - current_price) / entry_price) * 100
                        if current_price >= stop_loss:
                            should_close = True
                            status = "BAŞARIYLA_KAÇINILDI"
                        elif current_price <= take_profit:
                            should_close = True
                            status = "KAÇIRILAN_FIRSAT"
                            
                    if not should_close and current_ts >= t.get("vertical_barrier_timestamp", current_ts):
                        should_close = True
                        status = "SÜRESİ_DOLDU"
                        
                    if should_close:
                        t["durum"] = status
                        t["cikis_fiyati"] = current_price
                        t["kapanis_tarihi"] = datetime.now(tr_tz).strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Gölge PNL hesapla
                        commission_rate = 0.0004
                        t["pnl_yuzde"] = round((pnl_pct * leverage) - (commission_rate * 2 * 100), 2)
                        t["pnl_usdt"] = round((((pnl_pct * leverage) / 100) * t["risked_usdt"]) - (t["risked_usdt"] * commission_rate * 2), 2)
                        
                        updated = True
                        
                        if status == "BAŞARIYLA_KAÇINILDI":
                            add_log(f"🛡️ AI AVOIDED LOSS BAŞARISI: {t['coin']} {t['yon']} işlemi açılmayarak {abs(t['pnl_usdt'])} USDT zarar önlendi! (Filtre: {t['reject_reason']})")
                        elif status == "KAÇIRILAN_FIRSAT":
                            add_log(f"📈 AI AVOIDED LOSS KAÇAN FIRSAT: {t['coin']} {t['yon']} işlemi açılmayarak {t['pnl_usdt']} USDT potansiyel kâr kaçırıldı. (Filtre: {t['reject_reason']})")
                except Exception as avoided_err:
                    add_log(f"⚠️ Kaçınılan işlem güncellenirken hata: {str(avoided_err)}")
                    continue
                    
        if updated:
            temp_file = avoided_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(avoided_trades, f, indent=4)
            os.replace(temp_file, avoided_file)
