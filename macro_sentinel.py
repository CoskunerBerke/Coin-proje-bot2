# -*- coding: utf-8 -*-
"""
Kripto Coin Analiz Uygulaması — Makro Ekonomik Farkındalık Modülü (Macro Sentinel)
Sadece BOT2_AGGRESSIVE için aktif. BOT1_PASSIVE'de devre dışı kalır.

USD/TRY, BTC Dominansı, Stablecoin Akışları ve Fear & Greed verilerini
analiz ederek makro risk skoru üretir. Bu skor sinyal kalitesini,
pozisyon boyutunu ve işlem kararlarını etkiler.

⚡ OLAY ODAKLI: Normal piyasa koşullarında SIFIR etki!
Sadece gerçek kriz anlarında (TL çöküşü >%1.5, TCMB müdahalesi, piyasa çöküşü) devreye girer.
"""

import time
import requests
from datetime import datetime, timezone, timedelta
from log_manager import add_log
from db_manager import BOT_IDENTIFIER

tr_tz = timezone(timedelta(hours=3))


class MacroSentinel:
    """Makro ekonomik risk izleme motoru. Sadece BOT2_AGGRESSIVE için aktif."""

    def __init__(self):
        self._cache = {}
        self._cache_ttl = 1800  # 30 dakika
        self._last_level = None  # Seviye değişimi takibi (Telegram bildirimi için)
        self._enabled = (BOT_IDENTIFIER == "BOT2_AGGRESSIVE")
        
        if self._enabled:
            add_log("🌍 Macro Sentinel AKTIF — BOT2_AGGRESSIVE makro ekonomik verileri takip edecek.")
        else:
            add_log(f"ℹ️ Macro Sentinel DEVRE DIŞI — Bot kimliği: {BOT_IDENTIFIER} (Sadece BOT2_AGGRESSIVE için aktif)")

    def is_enabled(self) -> bool:
        """Macro Sentinel'in aktif olup olmadığını döndürür."""
        return self._enabled

    def get_macro_risk_score(self) -> dict:
        """Ana makro risk skorunu hesaplar ve döndürür."""
        if not self._enabled:
            return self._disabled_result()

        # Önbellekten kontrol
        cached = self._get_cache("macro_risk")
        if cached:
            return cached

        # === Veri Kaynaklarını Çek ===
        try:
            usd_try_data = self._fetch_usd_try()
        except Exception as e:
            add_log(f"⚠️ Macro Sentinel USD/TRY Hatası: {e}")
            usd_try_data = {"change_24h_pct": 0.0, "current_rate": 0.0, "intervention_detected": False, "risk_points": 0}

        try:
            btc_dominance_data = self._fetch_btc_dominance()
        except Exception as e:
            add_log(f"⚠️ Macro Sentinel BTC Dominans Hatası: {e}")
            btc_dominance_data = {"dominance_pct": 50.0, "market_cap_change_24h": 0.0, "risk_points": 0}

        try:
            fear_greed_data = self._fetch_fear_greed()
        except Exception as e:
            add_log(f"⚠️ Macro Sentinel Fear & Greed Hatası: {e}")
            fear_greed_data = {"value": 50, "classification": "Neutral", "risk_points": 0}

        # === Risk Skoru Hesapla ===
        # ⚡ Base skor 0: Normal koşullarda bot'a SIFIR etki!
        # Sadece gerçek makro olaylar (TL krizi, piyasa çöküşü, TCMB müdahalesi) puanı yükseltir.
        base_score = 0
        total_score = base_score
        total_score += usd_try_data.get("risk_points", 0)
        total_score += btc_dominance_data.get("risk_points", 0)
        total_score += fear_greed_data.get("risk_points", 0)

        # Sınırla [0, 100]
        total_score = max(0, min(100, total_score))

        # Seviye belirle — Geniş NORMAL bandı: Küçük dalgalanmalar bot'u etkilemez
        if total_score >= 85:
            level = "KRIZ"
            risk_multiplier = 0.25
            threshold_adj = 25.0
            short_bias = 0.3
        elif total_score >= 65:
            level = "YUKSEK_RISK"
            risk_multiplier = 0.50
            threshold_adj = 15.0
            short_bias = 0.2
        elif total_score >= 40:
            level = "DIKKATLI"
            risk_multiplier = 0.75
            threshold_adj = 5.0
            short_bias = 0.1
        else:
            level = "NORMAL"
            risk_multiplier = 1.0       # Normal pozisyon boyutu — HİÇ ETKİ YOK
            threshold_adj = 0.0
            short_bias = 0.0

        # Seviye değişimi tespiti (Telegram bildirimi için)
        level_changed = (self._last_level is not None and self._last_level != level)
        self._last_level = level

        result = {
            "score": total_score,
            "level": level,
            "level_changed": level_changed,
            "risk_multiplier": risk_multiplier,
            "threshold_adjustment": threshold_adj,
            "short_bias": short_bias,
            "details": {
                "usd_try": usd_try_data,
                "btc_dominance": btc_dominance_data,
                "fear_greed": fear_greed_data
            }
        }

        # Log
        emoji_map = {"NORMAL": "🟢", "DIKKATLI": "🟡", "YUKSEK_RISK": "🟠", "KRIZ": "🔴"}
        add_log(f"{emoji_map.get(level, '⚪')} Macro Sentinel: Skor={total_score}/100, Seviye={level}, "
                f"USD/TRY Δ={usd_try_data.get('change_24h_pct', 0):.2f}%, "
                f"BTC Dom={btc_dominance_data.get('dominance_pct', 0):.1f}%, "
                f"F&G={fear_greed_data.get('value', 50)}")

        self._set_cache("macro_risk", result)
        return result

    # ─── Veri Kaynakları ────────────────────────────────────────────────────

    def _fetch_usd_try(self) -> dict:
        """USD/TRY kurunu çeker ve değişimi hesaplar."""
        cached = self._get_cache("usd_try")
        if cached:
            return cached

        risk_points = 0
        current_rate = 0.0
        change_24h_pct = 0.0
        intervention_detected = False

        try:
            resp = requests.get("https://api.frankfurter.app/latest", params={"from": "USD", "to": "TRY"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                current_rate = data.get("rates", {}).get("TRY", 0.0)

            today = datetime.now(tr_tz).date()
            start_date = today - timedelta(days=5)
            
            resp_hist = requests.get(f"https://api.frankfurter.app/{start_date}..{today}", params={"from": "USD", "to": "TRY"}, timeout=10)
            if resp_hist.status_code == 200:
                hist_data = resp_hist.json()
                rates = hist_data.get("rates", {})
                
                if rates and current_rate > 0:
                    sorted_dates = sorted(rates.keys())
                    
                    if len(sorted_dates) >= 2:
                        oldest_rate = rates[sorted_dates[0]].get("TRY", current_rate)
                        change_24h_pct = ((current_rate - oldest_rate) / oldest_rate) * 100

                        all_rates = [rates[d].get("TRY", 0) for d in sorted_dates if rates[d].get("TRY", 0) > 0]
                        if len(all_rates) >= 3:
                            max_rate = max(all_rates)
                            min_rate = min(all_rates)
                            spike_pct = ((max_rate - min_rate) / min_rate) * 100
                            retrace_pct = ((max_rate - current_rate) / max_rate) * 100
                            
                            if spike_pct > 1.5 and retrace_pct > 0.5:
                                intervention_detected = True

            # Risk puanları — Sadece ciddi hareketlerde tetiklenir
            abs_change = abs(change_24h_pct)
            if change_24h_pct > 0:
                if abs_change > 3.0:
                    risk_points += 40
                elif abs_change > 2.0:
                    risk_points += 30
                elif abs_change > 1.5:
                    risk_points += 20

            if intervention_detected:
                risk_points += 20

        except requests.exceptions.RequestException as e:
            add_log(f"⚠️ USD/TRY API erişim hatası: {str(e)[:100]}")

        result = {
            "current_rate": round(current_rate, 4),
            "change_24h_pct": round(change_24h_pct, 2),
            "intervention_detected": intervention_detected,
            "risk_points": risk_points
        }
        self._set_cache("usd_try", result)
        return result

    def _fetch_btc_dominance(self) -> dict:
        """BTC dominansı ve market cap değişimini çeker."""
        cached = self._get_cache("btc_dominance")
        if cached:
            return cached

        risk_points = 0
        dominance_pct = 50.0
        market_cap_change = 0.0

        try:
            resp = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                dominance_pct = data.get("market_cap_percentage", {}).get("btc", 50.0)
                market_cap_change = data.get("market_cap_change_percentage_24h_usd", 0.0)

                if dominance_pct > 62:
                    risk_points += 15

                if market_cap_change < -5.0:
                    risk_points += 20
                elif market_cap_change < -3.0:
                    risk_points += 10

            elif resp.status_code == 429:
                add_log("⚠️ CoinGecko API rate limit — makro dominans verisi atlanıyor.")

        except requests.exceptions.RequestException as e:
            add_log(f"⚠️ BTC Dominans API hatası: {str(e)[:100]}")

        result = {
            "dominance_pct": round(dominance_pct, 2),
            "market_cap_change_24h": round(market_cap_change, 2),
            "risk_points": risk_points
        }
        self._set_cache("btc_dominance", result)
        return result

    def _fetch_fear_greed(self) -> dict:
        """Fear & Greed Index'i çeker."""
        cached = self._get_cache("fear_greed")
        if cached:
            return cached

        risk_points = 0
        value = 50
        classification = "Neutral"

        try:
            resp = requests.get("https://api.alternative.me/fng/", timeout=10)
            if resp.status_code == 200:
                data = resp.json().get("data", [{}])[0]
                value = int(data.get("value", 50))
                classification = data.get("value_classification", "Neutral")

                if value <= 15:
                    risk_points += 20
                elif value <= 20:
                    risk_points += 10
                elif value >= 85:
                    risk_points += 10

        except requests.exceptions.RequestException:
            pass

        result = {
            "value": value,
            "classification": classification,
            "risk_points": risk_points
        }
        self._set_cache("fear_greed", result)
        return result

    # ─── Yardımcı Metodlar ──────────────────────────────────────────────────

    def format_telegram_alert(self, macro_data: dict) -> str:
        """Makro risk verilerini Telegram bildirimi formatına çevirir."""
        level = macro_data.get("level", "NORMAL")
        score = macro_data.get("score", 0)
        details = macro_data.get("details", {})
        
        usd_try = details.get("usd_try", {})
        btc_dom = details.get("btc_dominance", {})
        fg = details.get("fear_greed", {})
        
        emoji_map = {"NORMAL": "🟢", "DIKKATLI": "🟡", "YUKSEK_RISK": "🟠", "KRIZ": "🔴"}
        emoji = emoji_map.get(level, "⚪")
        
        msg = (
            f"{emoji} MAKRO RİSK DURUMU DEĞİŞTİ\n\n"
            f"📊 Skor: {score}/100 ({level})\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"💵 USD/TRY: {usd_try.get('current_rate', 0):.2f} (Δ{usd_try.get('change_24h_pct', 0):+.2f}%)\n"
        )
        
        if usd_try.get("intervention_detected"):
            msg += "⚠️ TCMB müdahale sinyali tespit edildi!\n"
        
        msg += (
            f"₿ BTC Dominans: %{btc_dom.get('dominance_pct', 0):.1f}\n"
            f"📈 Market Cap Δ24h: {btc_dom.get('market_cap_change_24h', 0):+.1f}%\n"
            f"😱 Fear & Greed: {fg.get('value', 50)} ({fg.get('classification', 'Neutral')})\n"
            f"━━━━━━━━━━━━━━━━━\n"
        )
        
        if level == "KRIZ":
            msg += "🚨 KRİZ MODU: Yeni işlem açılması durduruldu!\nMevcut pozisyonların SL'leri korunuyor."
        elif level == "YUKSEK_RISK":
            msg += "⚠️ Pozisyon boyutu %50'ye düşürüldü.\nSadece güçlü sinyaller kabul edilecek."
        elif level == "DIKKATLI":
            msg += "📌 Pozisyon boyutu %75'e düşürüldü.\nDikkatli işlem modu aktif."
        else:
            msg += "✅ Normal işlem modu aktif."
        
        return msg

    def _disabled_result(self) -> dict:
        return {
            "score": 0,
            "level": "DEVRE_DISI",
            "level_changed": False,
            "risk_multiplier": 1.0,
            "threshold_adjustment": 0.0,
            "short_bias": 0.0,
            "details": {}
        }

    def _get_cache(self, key):
        if key in self._cache:
            data, ts = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return data
        return None

    def _set_cache(self, key, data):
        self._cache[key] = (data, time.time())
