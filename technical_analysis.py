"""
Kripto Coin Analiz Uygulaması — Bağımsız Teknik Analiz Modülü
Bu modül, dış dosyalardan bağımsız olarak kendi varsayılan ayarlarını içerir.
"""

import pandas as pd
import numpy as np
import ta as ta_lib

# Varsayılan ayarları doğrudan buraya yazıyorum (Garanti olsun diye)
DEFAULT_PARAMS = {
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

class TechnicalAnalyzer:
    def __init__(self):
        try:
            from config import TA_PARAMS
            self.params = TA_PARAMS if TA_PARAMS else DEFAULT_PARAMS
        except:
            self.params = DEFAULT_PARAMS

    def full_analysis(self, df: pd.DataFrame) -> dict:
        if df is None or df.empty or len(df) < 30:
            return self._empty_analysis()
        
        try:
            ind = self._calculate_indicators(df)
            sr = self._find_support_resistance(df)
            
            # Trend Belirleme
            trend_direction = "LONG" if ind["last_close"] > ind["ema"].get(21, 0) else "SHORT"
            trend_score = 1 if trend_direction == "LONG" else -1
            trend = {"direction": trend_direction, "direction_score": trend_score}
            
            summary = {
                "bullish_percentage": 100 if trend_direction == "LONG" else 0,
                "bearish_percentage": 0 if trend_direction == "LONG" else 100,
                "overall": "Analiz Edildi"
            }
            
            # Sıkışma & Kırılım
            sq_info = self.detect_squeeze_breakout(df)
            
            # Volatilite Seviyesi
            atr_pct = (ind["atr"] / ind["last_close"]) * 100
            vol_level = "Normal"
            if atr_pct > 2.5:
                vol_level = "Çok Yüksek"
            elif atr_pct > 1.5:
                vol_level = "Yüksek"
            elif atr_pct < 0.6:
                vol_level = "Düşük"
            
            return {
                "indicators": ind, 
                "support_resistance": sr, 
                "trend": trend,
                "summary": summary, 
                "candle_patterns": [], 
                "volatility": {
                    "level": vol_level, 
                    "is_squeeze": sq_info["is_squeeze"],
                    "squeeze_breakout": sq_info["squeeze_breakout"],
                    "atr_pct": atr_pct
                },
                "volume_analysis": self.analyze_volume_climax(df),
                "regime": self.detect_market_regime(df),
                "liquidity_sweep": self.detect_liquidity_sweep(df),
                "fake_breakout": self.detect_fake_breakout(df),
                "trend_exhaustion": self.calculate_trend_exhaustion(df, ind)
            }
        except Exception:
            return self._empty_analysis()

    def _calculate_indicators(self, df: pd.DataFrame) -> dict:
        ind = {}
        c = df["close"]
        h = df["high"]
        l = df["low"]
        p = self.params
        
        # RSI
        ind["rsi"] = round(float(ta_lib.momentum.RSIIndicator(c, window=p.get("rsi_period", 14)).rsi().iloc[-1]), 2)
        
        # MACD
        macd = ta_lib.trend.MACD(c, window_slow=p.get("macd_slow", 26), window_fast=p.get("macd_fast", 12), window_sign=p.get("macd_signal", 9))
        ind["macd_line"] = round(float(macd.macd().iloc[-1]), 4)
        ind["macd_histogram"] = round(float(macd.macd_diff().iloc[-1]), 4)

        # EMAs
        ind["ema"] = {}
        for period in p.get("ema_periods", [9, 21, 50, 200]):
            ind["ema"][period] = round(float(ta_lib.trend.EMAIndicator(c, window=period).ema_indicator().iloc[-1]), 4)

        # Bollinger Bands
        bb = ta_lib.volatility.BollingerBands(c, window=p.get("bb_period", 20), window_dev=p.get("bb_std", 2))
        ind["bb_upper"] = round(float(bb.bollinger_hband().iloc[-1]), 4)
        ind["bb_lower"] = round(float(bb.bollinger_lband().iloc[-1]), 4)
        ind["bb_middle"] = round(float(bb.bollinger_mavg().iloc[-1]), 4)

        # ADX
        adx_ind = ta_lib.trend.ADXIndicator(h, l, c, window=p.get("adx_period", 14))
        ind["adx"] = round(float(adx_ind.adx().iloc[-1]), 2)

        # ATR
        atr_indicator = ta_lib.volatility.AverageTrueRange(h, l, c, window=p.get("atr_period", 14))
        ind["atr"] = round(float(atr_indicator.average_true_range().iloc[-1]), 6)
        
        # Candle Body/Wick Ratio
        try:
            o_last = float(df["open"].iloc[-1])
            c_last = float(c.iloc[-1])
            h_last = float(h.iloc[-1])
            l_last = float(l.iloc[-1])
            body = abs(c_last - o_last)
            wick = (h_last - max(c_last, o_last)) + (min(c_last, o_last) - l_last)
            ind["body_wick_ratio"] = round(body / wick, 4) if wick > 0 else round(body, 4)
        except Exception:
            ind["body_wick_ratio"] = 1.0
            
        ind["last_close"] = float(c.iloc[-1])
        ind["prev_close"] = float(c.iloc[-2])
        return ind

    def _find_support_resistance(self, df: pd.DataFrame) -> dict:
        close = float(df["close"].iloc[-1])
        high = float(df["high"].rolling(20).max().iloc[-1])
        low = float(df["low"].rolling(20).min().iloc[-1])
        return {
            "supports": [round(low, 4), round(low * 0.98, 4)],
            "resistances": [round(high, 4), round(high * 1.02, 4)],
            "pivot": round((high + low + close) / 3, 4)
        }

    def detect_market_regime(self, df: pd.DataFrame) -> str:
        """Piyasanın genel karakterini (Trending, Ranging, Compression, Volatility Expansion) tespit eder."""
        if df is None or df.empty or len(df) < 50:
            return "RANGE"
        
        try:
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df['volume']
            
            # Bollinger Bands for Squeeze detection
            bb = ta_lib.volatility.BollingerBands(close, window=20, window_dev=2)
            bb_upper = bb.bollinger_hband()
            bb_lower = bb.bollinger_lband()
            bb_middle = bb.bollinger_mavg()
            bb_width = (bb_upper - bb_lower) / (bb_middle + 1e-8)
            
            # ADX for Trend Strength
            adx_indicator = ta_lib.trend.ADXIndicator(high, low, close, window=14)
            adx = adx_indicator.adx().iloc[-1]
            
            # EMAs for Trend Direction and Spread
            ema9 = ta_lib.trend.EMAIndicator(close, window=9).ema_indicator()
            ema21 = ta_lib.trend.EMAIndicator(close, window=21).ema_indicator()
            ema50 = ta_lib.trend.EMAIndicator(close, window=50).ema_indicator()
            
            # Volume Expansion
            vol_avg = volume.rolling(20).mean()
            vol_ratio = volume.iloc[-1] / (vol_avg.iloc[-1] + 1e-8)
            
            # Realized Volatility Percentile
            log_returns = np.log(close / close.shift(1).replace(0, np.nan))
            realized_vol = log_returns.rolling(20).std() * 100
            max_vol = realized_vol.rolling(100).max().iloc[-1]
            vol_pct = (realized_vol.iloc[-1] / (max_vol + 1e-8)) * 100
            
            # Squeeze (Compression) Check: BB width is in the lowest 15th percentile of 100 candles
            squeeze_threshold = bb_width.rolling(100).quantile(0.15).iloc[-1]
            is_squeeze = bb_width.iloc[-1] <= squeeze_threshold
            
            # Volatility Expansion Check
            bb_expanding = bb_width.iloc[-1] > bb_width.iloc[-2]
            is_expansion = bb_expanding and vol_ratio > 1.8 and vol_pct > 75.0
            
            # Trend spread checks
            ema_spread = ((ema9.iloc[-1] - ema50.iloc[-1]) / (ema50.iloc[-1] + 1e-8)) * 100
            
            if is_squeeze:
                return "COMPRESSION"
            elif is_expansion:
                return "VOLATILITY_EXPANSION"
            elif adx > 25:
                if ema9.iloc[-1] > ema21.iloc[-1] > ema50.iloc[-1] and ema_spread > 0.3:
                    return "TRENDING_BULL"
                elif ema9.iloc[-1] < ema21.iloc[-1] < ema50.iloc[-1] and ema_spread < -0.3:
                    return "TRENDING_BEAR"
            
            return "RANGE"
        except Exception:
            return "RANGE"

    def analyze_mtf_alignment(self, df_small, df_large):
        """Küçük ve büyük zaman dilimi uyumunu kontrol eder."""
        reg_s = self.detect_market_regime(df_small)
        reg_l = self.detect_market_regime(df_large)
        alignment = "UYUMSUZ"
        if "BULL" in reg_s and "BULL" in reg_l:
            alignment = "STRONG BULL ALIGNMENT"
        elif "BEAR" in reg_s and "BEAR" in reg_l:
            alignment = "STRONG BEAR ALIGNMENT"
        elif "RANGE" in reg_l:
            alignment = "HTF SIDEWAYS"
        return {"small": reg_s, "large": reg_l, "alignment": alignment}

    def analyze_volume_climax(self, df):
        """Hacim patlamalarını ve balina hareketlerini analiz eder."""
        curr_vol = df['volume'].iloc[-1]
        avg_vol = df['volume'].rolling(20).mean().iloc[-1]
        rel_vol = curr_vol / avg_vol
        
        is_climax = rel_vol > 2.0
        direction = "BULLISH" if df['close'].iloc[-1] > df['open'].iloc[-1] else "BEARISH"
        
        return {
            "ratio": round(rel_vol, 2),
            "is_climax": is_climax,
            "climax_direction": direction if is_climax else "NONE"
        }

    def detect_squeeze_breakout(self, df: pd.DataFrame) -> dict:
        """Bollinger Bantları üzerinden volatilite sıkışması ve kırılımını tespit eder."""
        if len(df) < 100: return {"is_squeeze": False, "squeeze_breakout": "NONE"}
        bb = ta_lib.volatility.BollingerBands(df['close'])
        bb_upper = bb.bollinger_hband()
        bb_lower = bb.bollinger_lband()
        bandwidth = (bb_upper - bb_lower) / df['close']
        
        # Sıkışma kontrolü (En düşük %15 bandındaysa)
        is_squeeze = bandwidth.iloc[-1] <= bandwidth.rolling(100).quantile(0.15).iloc[-1]
        
        # Kırılım kontrolü: Önceki barda sıkışma vardı, şimdi bandwidth genişliyor
        prev_squeeze = bandwidth.iloc[-2] <= bandwidth.rolling(100).quantile(0.15).iloc[-2]
        bandwidth_expanding = bandwidth.iloc[-1] > bandwidth.iloc[-2]
        
        squeeze_breakout = "NONE"
        if prev_squeeze and bandwidth_expanding:
            if df["close"].iloc[-1] > bb_upper.iloc[-1]:
                squeeze_breakout = "BULLISH"
            elif df["close"].iloc[-1] < bb_lower.iloc[-1]:
                squeeze_breakout = "BEARISH"
                
        return {"is_squeeze": is_squeeze, "squeeze_breakout": squeeze_breakout}

    def detect_liquidity_sweep(self, df: pd.DataFrame, window: int = 20) -> str:
        """Bireysel yatırımcı stoplarının süpürüldüğü bölgeleri (liquidity sweep) algılar."""
        if len(df) < window + 1:
            return "NONE"
        
        hist_high = df["high"].iloc[-window-1:-1].max()
        hist_low = df["low"].iloc[-window-1:-1].min()
        
        curr_low = df["low"].iloc[-1]
        curr_high = df["high"].iloc[-1]
        curr_close = df["close"].iloc[-1]
        
        if curr_low < hist_low and curr_close > hist_low:
            return "BULLISH"
        elif curr_high > hist_high and curr_close < hist_high:
            return "BEARISH"
        return "NONE"

    def detect_fake_breakout(self, df: pd.DataFrame) -> str:
        """Bollinger bantlarından anlık taşmaları (sahte kırılımları) algılar."""
        if len(df) < 5: return "NONE"
        bb = ta_lib.volatility.BollingerBands(df['close'])
        upper = bb.bollinger_hband()
        lower = bb.bollinger_lband()
        
        prev_close = df["close"].iloc[-2]
        curr_close = df["close"].iloc[-1]
        
        if prev_close > upper.iloc[-2] and curr_close < upper.iloc[-1]:
            return "BEARISH"
        elif prev_close < lower.iloc[-2] and curr_close > lower.iloc[-1]:
            return "BULLISH"
        return "NONE"

    def calculate_trend_exhaustion(self, df: pd.DataFrame, ind: dict) -> float:
        """RSI, EMA200 sapması ve ardışık mumlar üzerinden trend yorgunluğunu hesaplar."""
        if not ind or "rsi" not in ind: return 0.0
        score = 0.0
        
        # 1. RSI ekstremleri
        rsi = ind["rsi"]
        if rsi > 80 or rsi < 20:
            score += 40
        elif rsi > 75 or rsi < 25:
            score += 25
            
        # 2. Ortalama Uzaklığı (EMA 200)
        ema200 = ind["ema"].get(200, 0)
        close = ind["last_close"]
        if ema200 > 0:
            deviation = abs(close - ema200) / ema200 * 100
            if deviation > 15:
                score += 30
            elif deviation > 10:
                score += 15
                
        # 3. Ardışık Mumlar
        if len(df) >= 5:
            last_5 = df["close"].iloc[-5:]
            opens = df["open"].iloc[-5:]
            all_green = all(last_5.iloc[i] > opens.iloc[i] for i in range(5))
            all_red = all(last_5.iloc[i] < opens.iloc[i] for i in range(5))
            if all_green or all_red:
                score += 30
                
        return float(min(100.0, score))

    def _empty_analysis(self):
        return {
            "indicators": {"last_close": 0, "ema": {9:0, 21:0, 50:0, 200:0}, "rsi": 50, "stoch_rsi_k": 50, "atr": 0.0, "adx": 0.0},
            "support_resistance": {"supports": [], "resistances": [], "pivot": 0},
            "trend": {"direction": "NEUTRAL", "direction_score": 0},
            "summary": {"bullish_percentage": 50, "bearish_percentage": 50, "overall": "Nötr"},
            "regime": "YOK",
            "volatility": {"level": "Normal", "is_squeeze": False, "squeeze_breakout": "NONE", "atr_pct": 1.0}, 
            "volume_analysis": {"ratio": 1.0, "is_climax": False, "climax_direction": "NONE"},
            "liquidity_sweep": "NONE",
            "fake_breakout": "NONE",
            "trend_exhaustion": 0.0
        }
