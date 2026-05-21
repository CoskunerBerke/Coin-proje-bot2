"""
Kripto Coin Analiz Uygulaması — 24/7 Kesintisiz Arka Plan Motoru (bot_engine.py)
"""

import time
import os
import json
from datetime import datetime, timezone, timedelta
from data_fetcher import DataFetcher
from technical_analysis import TechnicalAnalyzer
from sentiment_analysis import SentimentAnalyzer
from signal_generator import SignalGenerator
from trade_executor import TradeExecutor
from telegram_notifier import TelegramNotifier
from config import load_app_settings, SUPPORTED_COINS, ACTIVE_COINS, BOT_SETTINGS, INSTITUTIONAL_THRESHOLDS
from log_manager import add_log
from counterfactual_analyzer import CounterfactualAnalyzer

tr_tz = timezone(timedelta(hours=3))

def sanitize_nan(data):
    """Sözlük veya listelerdeki tüm NaN veya inf değerleri JSON uyumlu None (null) ile değiştirir.
    Ayrıca tüm NumPy türlerini (np.generic, np.ndarray) standart Python türlerine dönüştürür."""
    import math
    try:
        import numpy as np
        has_numpy = True
    except ImportError:
        has_numpy = False

    if has_numpy:
        if isinstance(data, np.generic):
            val = data.item()
            if isinstance(val, float):
                if math.isnan(val) or math.isinf(val):
                    return None
            return val
        elif isinstance(data, np.ndarray):
            return [sanitize_nan(x) for x in data.tolist()]

    if isinstance(data, dict):
        return {k: sanitize_nan(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_nan(x) for x in data]
    elif isinstance(data, bool):
        return bool(data)
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
        return float(data)
    elif isinstance(data, int):
        return int(data)
        
    # Check by class name to be ultra-safe in case of weird numpy imports
    tname = type(data).__name__
    if "bool" in tname:
        return bool(data)
    elif "int" in tname:
        return int(data)
    elif "float" in tname:
        return float(data)
        
    return data


def run_engine():
    """Botun 24/7 çalışacak kesintisiz arka plan iş parçacığı."""
    add_log("⏳ Render OOM Koruması: Sunucu başlangıç aşamasında bot motoru 30 saniye bekletiliyor...")
    time.sleep(30)
    add_log("🚀 Kripto Bot Arka Plan Motoru Başlatıldı!")
    
    # 🏦 Günlük Ardışık Zarar ve Toplam Kayıp Takipçisi (Institutional Daily Risk Guard)
    def get_daily_loss_stats(trade_executor):
        """Bugün kapanan işlemleri analiz eder: ardışık zarar sayısı ve toplam günlük PNL döndürür."""
        try:
            history = trade_executor.get_trade_history()
            today_str = datetime.now(tr_tz).strftime("%Y-%m-%d")
            starting_balance = trade_executor.get_balance()
            
            # Bugün kapanan işlemleri filtrele
            today_closed = []
            for t in history:
                if t.get("durum") == "KAPANDI":
                    close_time = t.get("kapanis_zamani", "")
                    if today_str in str(close_time):
                        today_closed.append(t)
            
            if not today_closed:
                return {"consecutive_losses": 0, "daily_pnl_pct": 0.0, "is_banned": False}
            
            # Kapanış zamanına göre sırala (en son kapanan en sonda)
            today_closed.sort(key=lambda x: str(x.get("kapanis_zamani", "")))
            
            # Ardışık zarar sayısını hesapla (sondan başa doğru)
            consecutive_losses = 0
            for t in reversed(today_closed):
                pnl = float(t.get("pnl_usdt", 0))
                if pnl < 0:
                    consecutive_losses += 1
                else:
                    break  # İlk kârlı işlemde dur
            
            # Toplam günlük PNL yüzdesi
            total_daily_pnl = sum(float(t.get("pnl_usdt", 0)) for t in today_closed)
            daily_pnl_pct = (total_daily_pnl / max(starting_balance, 1.0)) * 100
            
            # Ban kontrolü
            max_consecutive = INSTITUTIONAL_THRESHOLDS["max_daily_consecutive_losses"]
            max_daily_loss = INSTITUTIONAL_THRESHOLDS["max_daily_loss_pct"]
            is_banned = consecutive_losses >= max_consecutive or daily_pnl_pct <= -max_daily_loss
            
            return {
                "consecutive_losses": consecutive_losses,
                "daily_pnl_pct": round(daily_pnl_pct, 2),
                "is_banned": is_banned,
                "total_daily_pnl": round(total_daily_pnl, 2),
                "closed_today": len(today_closed)
            }
        except Exception as e:
            add_log(f"⚠️ Günlük zarar takip hatası: {str(e)}")
            return {"consecutive_losses": 0, "daily_pnl_pct": 0.0, "is_banned": False}
    
    # Modülleri ilklendir
    fetcher = DataFetcher()
    analyzer = TechnicalAnalyzer()
    sentiment_analyzer = SentimentAnalyzer()
    signal_gen = SignalGenerator()
    executor = TradeExecutor(simulation_mode=True)
    cf_analyzer = CounterfactualAnalyzer()  # 🔮 Counterfactual Analiz Motoru
    
    from spot_investor import SpotInvestor
    spot_investor = SpotInvestor(fetcher, analyzer)
    
    # Zamanlayıcılar (Timers)
    last_scan_time = 0
    last_pnl_check_time = 0
    last_spot_scan_time = 0
    last_memory_report_time = 0
    last_cf_update_time = 0  # 🔮 Counterfactual güncelleme zamanlayıcısı
    
    scan_interval = 40     # 40 Saniyede bir tüm fırsatları tara (1m Grafik senkronizasyonu)
    pnl_check_interval = 15 # 15 Saniyede bir açık pozisyonları güncelle (SL/TP)
    
    while True:
        try:
            current_time = time.time()
            
            # 💾 Ayarları kalıcı dosyadan oku
            settings = load_app_settings()
            
            # If running on Render, force bot_active to True. Otherwise check settings.
            bot_active = (os.getenv("RENDER") == "true") or settings.get("bot_active", False)
            sim_mode = settings.get("sim_mode", True)
            timeframe = settings.get("timeframe", "1h")
            leverage = settings.get("leverage", 1)
            tg_active = settings.get("tg_active", False)
            tg_token = settings.get("tg_token", "")
            tg_chat_id = settings.get("tg_chat_id", "")
            
            # Alım-Satım Yöneticisini Güncel Mod ile Ayarla
            executor.simulation_mode = sim_mode
            if not sim_mode and executor.exchange is None:
                try:
                    import ccxt
                    from config import BINANCE_API_KEY, BINANCE_SECRET_KEY
                    executor.exchange = ccxt.binance({
                        'apiKey': BINANCE_API_KEY,
                        'secret': BINANCE_SECRET_KEY,
                        'enableRateLimit': True,
                        'options': {'defaultType': 'spot'}
                    })
                except: pass
            
            # 📱 Telegram Notifier Ayarla
            if tg_active and tg_token and tg_chat_id:
                executor.notifier = TelegramNotifier(token=tg_token, chat_id=tg_chat_id)
            else:
                executor.notifier = None
            
            # 🛡️ 1. Açık Pozisyonların Takip ve Kapatma Şartları (SL/TP/Trailing Stop)
            if current_time - last_pnl_check_time >= pnl_check_interval:
                try:
                    # Açık pozisyon varsa fiyatı Binance'ten kontrol edip kapatma koşullarını uygular
                    executor.update_positions(fetcher, cf_analyzer=cf_analyzer)
                    # 🧹 Pozisyon kontrolü sonrası hızlı temizlik
                    import gc
                    gc.collect()
                except Exception as pnl_err:
                    add_log(f"⚠️ Pozisyon Güncelleme Hatası: {str(pnl_err)}")
                
                # 🔮 Counterfactual Senaryoları Güncelle (30 saniyede bir)
                if current_time - last_cf_update_time >= 30:
                    try:
                        cf_analyzer.update_counterfactuals(fetcher)
                    except Exception as cf_err:
                        add_log(f"⚠️ Counterfactual Güncelleme Hatası: {str(cf_err)}")
                    last_cf_update_time = current_time
                
                last_pnl_check_time = current_time
            
            # 📈 4. Spot AI Portföy Taraması (12 Saatte Bir Çalışır)
            if current_time - last_spot_scan_time >= 43200:
                try:
                    spot_investor.scan_spot_opportunities()
                    last_spot_scan_time = current_time
                except Exception as spot_err:
                    add_log(f"⚠️ Spot AI Portföy Taraması Hatası: {str(spot_err)}")
            
            # 🧠 2. AI Kendi Kendini Eğitme / Karar Ağırlıklarını Optimize Etme
            try:
                signal_gen.update_weights_from_history()
            except Exception as ml_err:
                add_log(f"⚠️ AI Ağırlık Güncelleme Hatası: {str(ml_err)}")
            
            # 🚀 3. Sinyal Taraması ve İşlem Açma
            if bot_active:
                if current_time - last_scan_time >= scan_interval:
                    add_log("🔍 Bot Aktif! Fırsatlar taranıyor...")
                    
                    # Tüm piyasayı tara
                    all_signals = []
                    htf_map = {"1m": "15m", "5m": "1h", "15m": "1h", "1h": "4h", "4h": "1d", "1d": "1w"}
                    htf = htf_map.get(timeframe, "4h")

                    # 🧭 1. Önce BTC Trend ve Rejimini Canlı Analiz Et (Piyasa Pusulası)
                    btc_trend = "NEUTRAL"
                    btc_regime = "RANGE"
                    btc_reversal_trigger = False
                    try:
                        btc_ticker = fetcher.fetch_ticker("BTC")
                        btc_df = fetcher.fetch_ohlcv("BTC", timeframe, limit=210)
                        btc_df_htf = fetcher.fetch_ohlcv("BTC", htf, limit=210)
                        
                        btc_ta = analyzer.full_analysis(btc_df)
                        btc_trend = btc_ta.get("trend", {}).get("direction", "NEUTRAL")
                        raw_regime = btc_ta.get("regime", "SIDEWAYS")
                        
                        regime_map = {
                            "HIGH VOLATILITY": "CHAOTIC_VOLATILE",
                            "STRONG BULL": "STRONG_BULL",
                            "WEAK BULL": "WEAK_BULL",
                            "STRONG BEAR": "STRONG_BEAR",
                            "WEAK BEAR": "WEAK_BEAR",
                            "SIDEWAYS": "RANGE"
                        }
                        btc_regime = regime_map.get(raw_regime, "RANGE")
                        
                        # ⚡ Ani Dönüş (Reversal) Dedektörü
                        btc_rsi_15m = btc_ta.get("indicators", {}).get("rsi", 50)
                        if len(btc_df) >= 4:
                            btc_change_pct = ((btc_df['close'].iloc[-1] - btc_df['close'].iloc[-4]) / btc_df['close'].iloc[-4]) * 100
                            # Eğer son 4 mumda %1.0'den fazla yükseldi veya RSI aşırı yükseldi ise ani long dönüşü tetikle
                            if btc_change_pct > 1.0 or btc_rsi_15m > 70:
                                btc_reversal_trigger = True
                                add_log(f"⚡ BTC ANİ YÖN DÖNÜŞ TETİKLEYİCİSİ AKTİF: Yükseliş=%{btc_change_pct:.2f}, RSI={btc_rsi_15m:.1f}")
                        
                        add_log(f"🧭 BTC Pusulası Güncellendi: Yön={btc_trend}, Rejim={btc_regime}, Ani Dönüş={btc_reversal_trigger}")
                    except Exception as btc_err:
                        add_log(f"⚠️ BTC Pusulası Analiz Hatası (Güvenli Varsayılan Kullanılıyor): {str(btc_err)}")
                    
                    for coin in ACTIVE_COINS:
                        try:
                            ticker = fetcher.fetch_ticker(coin)
                            # 🎯 DÜZELTME: EMA 200 hesaplanabilsin diye limit 100 yerine 210'a çıkarıldı!
                            df = fetcher.fetch_ohlcv(coin, timeframe, limit=210)
                            df_htf = fetcher.fetch_ohlcv(coin, htf, limit=210)
                            df_1h = fetcher.fetch_ohlcv(coin, "1h", limit=210)
                            df_4h = fetcher.fetch_ohlcv(coin, "4h", limit=210)
                            
                            # 1 Günlük (1d) Grafikten Trend Yönü Filtresi (EMA 200)
                            daily_trend_long = True
                            try:
                                df_daily = fetcher.fetch_ohlcv(coin, "1d", limit=210)
                                if df_daily is not None and not df_daily.empty and len(df_daily) >= 200:
                                    daily_ema200 = df_daily['close'].ewm(span=200, adjust=False).mean().iloc[-1]
                                    daily_close = df_daily['close'].iloc[-1]
                                    daily_trend_long = bool(daily_close > daily_ema200)
                            except Exception as daily_err:
                                pass
                            
                            ta = analyzer.full_analysis(df)
                            ta_1h = analyzer.full_analysis(df_1h)
                            ta_4h = analyzer.full_analysis(df_4h)
                            mtf_data = analyzer.analyze_mtf_alignment(df, df_htf)
                            
                            # Hızlı Duygu Analizi (Hata durumunda güvenli koruma)
                            try:
                                coin_info = fetcher.fetch_coin_info(coin)
                                sentiment_result = sentiment_analyzer.full_analysis(coin, coin_info)
                            except:
                                sentiment_result = {
                                    "overall": {"label": "Nötr", "emoji": "😐", "score": 50},
                                    "news_sentiment": {"positive_pct": 50, "scored_news": []}
                                }
                            
                            signal = signal_gen.generate_signal(
                                coin, ticker, ta, sentiment_result, timeframe, mtf_data,
                                btc_trend=btc_trend, btc_regime=btc_regime,
                                btc_reversal_trigger=btc_reversal_trigger,
                                daily_trend_long=daily_trend_long,
                                ta_1h=ta_1h, ta_4h=ta_4h
                            )
                            all_signals.append({
                                "coin": coin, 
                                "confidence": signal["confidence"], 
                                "direction": signal["direction"], 
                                "score": signal["weighted_score"], 
                                "label": signal["direction_label"],
                                "is_tradable": signal["is_tradable"],
                                "reject_reason": signal["reject_reason"],
                                "ev": signal["ev"],
                                "signal": signal,
                                "ta_result": ta,
                                "sentiment_result": sentiment_result
                            })
                            
                            # 🧹 Döngü İçi Agresif RAM Temizliği (Peak RAM birikimini sıfırlar!)
                            del df, df_htf, df_1h, df_4h, ta, ta_1h, ta_4h, sentiment_result, signal
                            import gc
                            gc.collect()
                            
                            time.sleep(1.5) # 💤 API Limit Koruması ve RAM Yayılımı (Peak OOM Koruması)
                        except Exception as coin_err:
                            add_log(f"⚠️ {coin} Tarama Hatası: {str(coin_err)}")
                            import gc
                            gc.collect()
                            continue
                    
                    all_opps = sorted(all_signals, key=lambda x: x["confidence"], reverse=True)
                    
                    # 🛡️ Sinyal Bozulma Kalkanı (Signal Invalidation Guard)
                    try:
                        history = executor.get_trade_history()
                        active_trades = [t for t in history if t.get("durum") == "AÇIK"]
                        for t in active_trades:
                            coin = t.get("coin")
                            direction = t.get("yon")
                            
                            # Bu coin için taramada üretilen anlık sinyali bul
                            coin_sig_data = next((s for s in all_signals if s["coin"] == coin), None)
                            if coin_sig_data:
                                sig_direction = coin_sig_data["direction"]
                                confidence = coin_sig_data["confidence"]
                                
                                # Eğer eldeki pozisyonun ters yönünde güçlü bir sinyal varsa
                                base_invalidation_threshold = settings.get("signal_invalidation_threshold", BOT_SETTINGS.get("signal_invalidation_threshold", 88.0))
                                
                                c_ticker = fetcher.fetch_ticker(coin)
                                c_price = c_ticker["last"]
                                entry_price = t["giris_fiyati"]
                                leverage = t.get("kaldirac", 1)
                                commission_rate = 0.0004
                                
                                if direction == "LONG":
                                    pnl_pct = ((c_price - entry_price) / entry_price) * 100
                                else:
                                    pnl_pct = ((entry_price - c_price) / entry_price) * 100
                                    
                                current_trade_pnl = (pnl_pct * leverage) - (commission_rate * 2 * 100)
                                
                                invalidation_threshold = base_invalidation_threshold
                                
                                # 2) PnL rules
                                if current_trade_pnl > 0.0:
                                    invalidation_threshold += 5.0
                                if current_trade_pnl > 1.0:
                                    invalidation_threshold += 8.0
                                    
                                # 3) Momentum rule
                                try:
                                    t_df = fetcher.fetch_ohlcv(coin, timeframe="15m")
                                    t_ta = executor.analyzer.full_analysis(t_df)
                                    t_momentum = executor.calculate_momentum_score(t_df, t_ta, direction)
                                except Exception as m_err:
                                    t_momentum = 0.5
                                    add_log(f"⚠️ Invalidation Guard momentum hesabı hatası: {str(m_err)}")
                                    
                                if t_momentum >= 0.65:
                                    invalidation_threshold += 5.0
                                    
                                # 4) Minimum holding time block logic
                                holding_time_minutes = (time.time() - t.get("start_timestamp", time.time())) / 60
                                block_invalidation_close = False
                                if holding_time_minutes < 15.0:
                                    block_invalidation_close = True
                                    # Force override if counter signal is extremely strong
                                    counter_prob = coin_sig_data.get("trade_acceptance_probability", 0.0)
                                    if counter_prob >= 0.95 or confidence >= 95.0:
                                        block_invalidation_close = False
                                        add_log(f"⚠️ {coin} için Min Holding Time (<15m) bypass edildi (Ters yön prob: %{counter_prob*100:.1f}, güven: %{confidence:.1f}).")
                                    else:
                                        t["invalidation_blocked_by_min_hold"] = True
                                        executor._save_trade(t)
                                    
                                if (direction == "SHORT" and sig_direction == "LONG" and confidence >= invalidation_threshold) or \
                                   (direction == "LONG" and sig_direction == "SHORT" and confidence >= invalidation_threshold):
                                    
                                    if block_invalidation_close:
                                        # Log or record blocked invalidation once
                                        if not t.get("invalidation_block_logged", False):
                                            add_log(f"🛡️ Sinyal Bozulma Kalkanı engellendi (Coin: {coin}, Sure: {holding_time_minutes:.1f} dk < 15 dk limit).")
                                            t["invalidation_block_logged"] = True
                                            t["invalidation_blocked_by_min_hold"] = True
                                            executor._save_trade(t)
                                    else:
                                        # Pozisyonu kapat!
                                        t["durum"] = "KAPALI"
                                        t["cikis_fiyati"] = c_price
                                        t["pnl_yuzde"] = round(current_trade_pnl, 2)
                                        t["pnl_usdt"] = round((((pnl_pct * leverage) / 100) * t["miktar_usdt"]) - (t["miktar_usdt"] * commission_rate * 2), 2)
                                        t["kapanis_tarihi"] = datetime.now(tr_tz).strftime("%Y-%m-%d %H:%M:%S")
                                        t["exit_reason"] = f"SINYAL_BOZULMA_KALKANI (Ters Yön Güven: %{confidence:.1f})"
                                        t["invalidation_threshold_used"] = invalidation_threshold
                                        
                                        # Update post-tp1 stats if hit
                                        if t.get("tp1_hit_recorded", False):
                                            t["post_tp1_exit_reason"] = t["exit_reason"]
                                            t["tp1_to_exit_giveback"] = round(t.get("post_tp1_max_pnl", 0.0) - t["pnl_yuzde"], 2)
                                            
                                        # Compile final exit features dict
                                        r_mult = round((c_price - entry_price) / (entry_price * 0.02) if direction == "LONG" else (entry_price - c_price) / (entry_price * 0.02), 4)
                                        
                                        # Exit efficiency
                                        peak_pct = t.get("peak_pnl_pct", 0.0)
                                        exit_efficiency = round(t["pnl_yuzde"] / peak_pct, 4) if peak_pct > 0 else 0.0
                                        
                                        # Calculate outcome
                                        outcome = 1 if (bool(t.get("tp1_hit", False)) or r_mult >= 0.75 or t["pnl_yuzde"] >= 1.0) else 0
                                        
                                        exit_features_dict = {
                                            "exit_price": float(c_price),
                                            "exit_timestamp": float(time.time()),
                                            "pnl_usdt": float(t["pnl_usdt"]),
                                            "pnl_yuzde": float(t["pnl_yuzde"]),
                                            "realized_R_multiple": r_mult,
                                            "max_favorable_excursion": float(t.get("max_favorable_excursion", 0.0)),
                                            "max_adverse_excursion": float(t.get("max_adverse_excursion", 0.0)),
                                            "holding_time": float(t.get("holding_time", 0.0)),
                                            "exit_reason": t["exit_reason"],
                                            "tp1_hit": bool(t.get("tp1_hit", False)),
                                            "tp2_hit": bool(t.get("tp2_hit", False)),
                                            "quality_score": float(t.get("quality_score", 50.0)),
                                            # Advanced filters:
                                            "entry_quality_score": t.get("entry_quality_score", 0.5),
                                            "btc_alignment_score": t.get("btc_alignment_score", 0.5),
                                            "wick_trap_score": t.get("wick_trap_score", 0.0),
                                            "breakout_confirmation_score": t.get("breakout_confirmation_score", 0.5),
                                            "volume_confirmation_score": t.get("volume_confirmation_score", 0.5),
                                            "peak_momentum_score": t.get("peak_momentum_score", 0.0),
                                            "momentum_decay": t.get("peak_momentum_score", 0.0) - t_momentum,
                                            "peak_pnl_pct": peak_pct,
                                            "peak_to_realized_giveback": peak_pct - t["pnl_yuzde"],
                                            "invalidation_threshold_used": invalidation_threshold,
                                            "invalidation_blocked_by_min_hold": t.get("invalidation_blocked_by_min_hold", False),
                                            # TP1 Post-Hit stats
                                            "tp1_hit_time": t.get("tp1_hit_time"),
                                            "pnl_at_tp1": t.get("pnl_at_tp1"),
                                            "post_tp1_max_pnl": t.get("post_tp1_max_pnl"),
                                            "post_tp1_exit_reason": t.get("post_tp1_exit_reason"),
                                            "tp1_to_exit_giveback": t.get("tp1_to_exit_giveback")
                                        }
                                        
                                        t["exit_features"] = exit_features_dict
                                        t["result_metrics"] = exit_features_dict.copy()
                                        
                                        executor._save_trade(t)
                                        
                                        # Log AI observation
                                        pred_long = t.get("predicted_long_edge", 0.5)
                                        pred_short = t.get("predicted_short_edge", 0.5)
                                        add_log(f"🧠 AI_OBSERVATION: symbol={coin} direction={direction} predicted_long_edge={pred_long:.4f} predicted_short_edge={pred_short:.4f} actual_outcome={outcome} quality_score={t.get('quality_score', 50.0)}")
                                        
                                        try:
                                            from coin_intelligence import CoinIntelligenceManager
                                            coin_intel = CoinIntelligenceManager()
                                            coin_intel.log_completed_trade(coin, t)
                                            
                                            # 🔮 Counterfactual POST_EXIT takibi başlat
                                            try:
                                                cf_analyzer.track_post_exit(t)
                                            except Exception as cf_pe_err:
                                                add_log(f"⚠️ Counterfactual POST_EXIT Hatası: {str(cf_pe_err)}")
                                            
                                            # 🧠 Telegram'a öğrenme güncellemesi gönder
                                            if executor.notifier:
                                                try:
                                                    memory_entry = coin_intel.memory.get(coin, [{}])[-1]
                                                    executor.notifier.send_trade_learning_update(t, memory_entry)
                                                except Exception as e_tg_learn:
                                                    add_log(f"⚠️ Telegram Hafıza Bildirimi Hatası: {str(e_tg_learn)}")
                                        except Exception as e_intel:
                                            add_log(f"⚠️ Coin Hafıza Kayıt Hatası: {str(e_intel)}")
                                            
                                        # Yeni multiline invalidation log formatı
                                        invalidation_log_msg = (
                                            f"\n🛡️ INVALIDATION_CLOSE:\n"
                                            f"symbol={coin}\n"
                                             f"counter_signal_confidence={confidence:.1f}\n"
                                             f"threshold={invalidation_threshold:.1f}\n"
                                             f"trade_pnl={current_trade_pnl:.1f}"
                                         )
                                        add_log(invalidation_log_msg)
                                         
                                        if executor.notifier:
                                            executor.notifier.send_trade_alert(t, is_open=False, balance=executor.get_balance())
                    except Exception as sig_guard_err:
                        add_log(f"⚠️ Sinyal Bozulma Kalkanı Hatası: {str(sig_guard_err)}")

                    # Fırsatları UI için dosyaya kaydet (Sıfır kasma için - Atomik Yazma ile Çakışma Önlenir)
                    try:
                        clean_opp = sanitize_nan(all_opps)
                        temp_file = "latest_opportunities.json.tmp"
                        with open(temp_file, "w", encoding="utf-8") as f:
                            json.dump(clean_opp, f, indent=4)
                        os.replace(temp_file, "latest_opportunities.json")
                    except Exception as dump_err:
                        add_log(f"⚠️ Fırsatlar Dosya Kayıt Hatası: {str(dump_err)}")
                    
                    # Fırsatları Kontrol Et ve Pozisyon Aç
                    opened_in_cycle = 0
                    
                    # 🏦 INSTITUTIONAL DAILY RISK GUARD: Günlük zarar ve ardışık stop kontrolü
                    daily_stats = get_daily_loss_stats(executor)
                    if daily_stats["is_banned"]:
                        ban_reason = ""
                        if daily_stats["consecutive_losses"] >= INSTITUTIONAL_THRESHOLDS["max_daily_consecutive_losses"]:
                            ban_reason = f"Ardışık {daily_stats['consecutive_losses']} zarar (limit: {INSTITUTIONAL_THRESHOLDS['max_daily_consecutive_losses']})"
                        if daily_stats["daily_pnl_pct"] <= -INSTITUTIONAL_THRESHOLDS["max_daily_loss_pct"]:
                            ban_reason += f" | Günlük zarar: %{daily_stats['daily_pnl_pct']:.1f} (limit: -%{INSTITUTIONAL_THRESHOLDS['max_daily_loss_pct']:.0f})"
                        add_log(f"🚫 GÜNLÜK İŞLEM YASAĞI AKTİF: {ban_reason}. Bugün yeni işlem açılmayacak (Kapanan: {daily_stats['closed_today']}, Toplam PNL: ${daily_stats['total_daily_pnl']:.2f}).")
                    
                    for opp in all_opps:
                        if opp.get("is_tradable", False):
                            try:
                                history = executor.get_trade_history()
  
                                # Eğer bu coinde zaten açık işlem yoksa (Maksimum aktif pozisyon limiti kaldırıldı)
                                if not any(t["coin"] == opp["coin"] and t["durum"] == "AÇIK" for t in history):
                                    # 🏦 Günlük ban kontrolü (Ardışık zarar veya günlük kayıp limiti)
                                    if daily_stats["is_banned"]:
                                        add_log(f"🚫 {opp['coin']} — Günlük işlem yasağı nedeniyle atlandı.")
                                        continue
                                    
                                    add_log(f"🚀 FIRSAT YAKALANDI: {opp['coin']} %{opp['confidence']} (EV: {opp['ev']})!")
                                    add_log(f"⚡ {opp['coin']} için emir gönderiliyor...")
                                    
                                    o_sig = opp["signal"]
                                    o_ticker = fetcher.fetch_ticker(opp["coin"])
                                    o_sig["entry"] = o_ticker["last"]
                                    o_sig["leverage"] = leverage
                                    
                                    if o_sig.get("is_tradable", False):
                                        res = executor.execute_trade(opp["coin"], o_sig)
                                        if res["status"] == "success":
                                            add_log(f"✅ İŞLEM AÇILDI: {opp['coin']} {o_sig['direction']}")
                                            # Risk Yönetimi: Döngü sınırı kaldırıldı, tüm fırsatlar açılır
                                            pass
                                        else:
                                            reason = res.get('msg') or res.get('reason') or "Bilinmeyen sebep"
                                            add_log(f"⚠️ ATLANDI ({opp['coin']}): {reason}")
                                    else:
                                        add_log(f"⚠️ ATLANDI ({opp['coin']}): Anlık emir doğrulamasında elendi ({o_sig.get('reject_reason')})")
                                    
                                    # 🧹 Emir aşaması geçici nesnelerini temizle
                                    del o_sig
                                    import gc
                                    gc.collect()
                            except Exception as o_err:
                                import gc
                                gc.collect()
                                add_log(f"⚠️ {opp['coin']} İşlem Hatası: {str(o_err)}")
                                continue
                        else:
                            try:
                                executor.track_avoided_trade(opp["coin"], opp["signal"], executor.get_balance())
                                # 🔮 Counterfactual MISSED_ENTRY takibi başlat
                                try:
                                    cf_analyzer.track_missed_entry(opp["coin"], opp["signal"], executor.get_balance())
                                except:
                                    pass
                            except: pass
                                
                    last_scan_time = current_time
                    add_log("💤 Tarama tamamlandı. Bekleme moduna geçiliyor.")
                    
                    # 🧠 Periyodik Hafıza Raporu (6 saatte bir Telegram'a gönder)
                    if current_time - last_memory_report_time >= 21600:  # 6 saat = 21600 saniye
                        try:
                            if executor.notifier:
                                import json as _json
                                memory_data = {}
                                if os.path.exists("coin_trade_memory.json"):
                                    with open("coin_trade_memory.json", "r", encoding="utf-8") as f:
                                        memory_data = _json.load(f)
                                if memory_data:
                                    executor.notifier.send_trade_memory_report(memory_data, executor.get_balance())
                                    add_log("📊 Periyodik Hafıza Raporu Telegram'a gönderildi.")
                            last_memory_report_time = current_time
                        except Exception as mem_rpt_err:
                            add_log(f"⚠️ Periyodik Hafıza Raporu Hatası: {str(mem_rpt_err)}")
                            last_memory_report_time = current_time
                    
                    # 🧹 Döngü Sonu Genel RAM Temizliği
                    import gc
                    gc.collect()
            else:
                # Bot kapalıysa scan sayacını güncelle ki aktif edildiğinde bekletmeden hemen başlasın
                last_scan_time = 0
                
        except Exception as main_err:
            add_log(f"❌ Motor Sistem Hatası: {str(main_err)}")
            time.sleep(5) # Hata durumunda CPU yorulmasını önleme
            
        time.sleep(5) # Döngü nefes aralığı

if __name__ == "__main__":
    run_engine()
