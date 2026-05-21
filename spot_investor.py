"""
Kripto Coin Analiz Uygulaması — Uzun Vadeli Spot AI Yatırım Modülü
Günlük (1d) grafikler üzerinden Wyckoff birikimi, EMA kırılımı ve RSI oversold durumlarını tarar.
"""

import os
import json
import time
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
from log_manager import add_log

SPOT_PORTFOLIO_FILE = "bot_spot_portfolio.json"
tr_tz = timezone(timedelta(hours=3))

class SpotInvestor:
    def __init__(self, fetcher, analyzer):
        self.fetcher = fetcher
        self.analyzer = analyzer

    def scan_spot_opportunities(self):
        """Tüm desteklenen coinleri günlük (1d) zaman diliminde tarayarak spot alım fırsatlarını belirler."""
        from config import SUPPORTED_COINS
        add_log("🔍 SPOT AI PORTFÖY TARAMASI BAŞLATILDI (Günlük Grafikler)...")
        
        opportunities = []
        for coin in list(SUPPORTED_COINS.keys()):
            try:
                # Günlük mumları çek
                df = self.fetcher.fetch_ohlcv(coin, "1d", limit=100)
                if df.empty or len(df) < 50: continue
                
                # Teknik analiz yap
                ta = self.analyzer.full_analysis(df)
                indicators = ta.get("indicators", {})
                rsi = indicators.get("rsi", 50)
                macd_hist = indicators.get("macd_histogram", 0)
                close = indicators.get("last_close", 0.0)
                
                # Spot analiz için geçmiş EMA ve MACD Histogram verilerini güvenli bir şekilde hesapla
                import ta as ta_lib
                df['ema_20'] = ta_lib.trend.EMAIndicator(df['close'], window=20).ema_indicator()
                df['ema_50'] = ta_lib.trend.EMAIndicator(df['close'], window=50).ema_indicator()
                df['ema_200'] = ta_lib.trend.EMAIndicator(df['close'], window=200).ema_indicator()
                df['macd_histogram'] = ta_lib.trend.MACD(df['close'], window_slow=26, window_fast=12, window_sign=9).macd_diff()
                
                # EMA değerleri
                ema20 = float(df['ema_20'].iloc[-1]) if not pd.isna(df['ema_20'].iloc[-1]) else close
                ema50 = float(df['ema_50'].iloc[-1]) if not pd.isna(df['ema_50'].iloc[-1]) else close
                ema200 = float(df['ema_200'].iloc[-1]) if not pd.isna(df['ema_200'].iloc[-1]) else close
                
                # Spot Puanı Hesaplama
                spot_score = 0.0
                reasons = []
                
                # Kriter 1: RSI Aşırı Satım / Akümülasyon Bölgesi (%30 Ağırlık)
                if 28 <= rsi <= 45:
                    spot_score += 30.0
                    reasons.append("Tarihsel Akümülasyon/Ucuzluk Bölgesinde (RSI 30-45)")
                elif rsi < 28:
                    spot_score += 35.0 # Ekstra puan
                    reasons.append("Aşırı Satım / Büyük Dip Fırsatı (RSI < 28)")
                    
                # Kriter 2: EMA Kırılımı ve Trend Hizalanması (%25 Ağırlık)
                if close > ema20 > ema50:
                    spot_score += 25.0
                    reasons.append("Boğa Eğilimi ve EMA20/50 Üzerinde Tutunma")
                elif close > ema20 and df['close'].iloc[-2] <= df['ema_20'].iloc[-2]:
                    spot_score += 20.0
                    reasons.append("Günlük EMA20 Direnci Yukarı Yönlü Kırıldı")
                    
                # Kriter 3: MACD Boğa Kesişimi (%20 Ağırlık)
                if macd_hist > 0 and df['macd_histogram'].iloc[-2] <= 0:
                    spot_score += 20.0
                    reasons.append("Günlük Grafikte MACD Al Sinyali (Kesişim)")
                elif macd_hist > 0:
                    spot_score += 10.0
                    
                # Kriter 4: Hacim Akümülasyonu (%25 Ağırlık)
                vol_ratio = ta.get("volume_analysis", {}).get("ratio", 1.0)
                if vol_ratio > 1.3:
                    spot_score += 20.0
                    reasons.append(f"Ortalamanın Üzerinde Alım Hacmi Akümülasyonu ({vol_ratio:.1f}x)")
                
                # Eğer spot alım puanı 60 veya üzerindeyse fırsat olarak kaydet
                if spot_score >= 60.0:
                    # Giriş bölgesi ve kademeli hedefler
                    entry_range = f"${close * 0.98:.4f} - ${close * 1.01:.4f}"
                    tp1 = round(close * 1.15, 4) # +15%
                    tp2 = round(close * 1.35, 4) # +35%
                    tp3 = round(close * 1.60, 4) # +60% (Büyük Koşu)
                    
                    stop_loss = round(close * 0.85, 4) # -15% stop (veya uzun vadeli)
                    if coin in ["BTC", "ETH"]:
                        stop_loss_str = "Uzun Vadeli Tut (Stop Yok)"
                    else:
                        stop_loss_str = f"${stop_loss:.4f}"
                        
                    opp = {
                        "id": f"spot_{coin}_{int(time.time())}",
                        "coin": coin,
                        "tarih": datetime.now(tr_tz).strftime("%Y-%m-%d %H:%M:%S"),
                        "puan": round(spot_score),
                        "guncel_fiyat": close,
                        "giris_bolgesi": entry_range,
                        "stop_loss": stop_loss_str,
                        "hedefler": [tp1, tp2, tp3],
                        "gerekceler": reasons,
                        "potansiyel_getiri": "+60.0%"
                    }
                    opportunities.append(opp)
                    
            except Exception as e:
                add_log(f"⚠️ {coin} Spot tarama hatası: {str(e)}")
                
        # Puanlara göre sırala
        opportunities = sorted(opportunities, key=lambda x: x["puan"], reverse=True)
        
        # Dosyaya kaydet
        with open(SPOT_PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            json.dump(opportunities, f, indent=4, ensure_ascii=False)
            
        add_log(f"✅ SPOT AI PORTFÖY TARAMASI TAMAMLANDI! {len(opportunities)} adet spot fırsat bulundu.")
        return opportunities

    def get_spot_portfolio(self):
        """Kaydedilmiş spot yatırım fırsatlarını yükler."""
        if os.path.exists(SPOT_PORTFOLIO_FILE):
            try:
                with open(SPOT_PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: return []
        return []
