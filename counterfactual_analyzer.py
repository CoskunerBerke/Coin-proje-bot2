"""
Kripto Coin Analiz Uygulaması — Counterfactual (Ya Olsaydı?) Analiz Motoru
Bu modül, kapattığımız işlemlerin sonrasını ve girmediğimiz fırsatların sonucunu takip eder.
Böylece AI, "erken mi çıktım?" veya "girseydim ne olurdu?" sorularını veriyle yanıtlar.
"""

import os
import json
import time
from datetime import datetime, timezone, timedelta
from log_manager import add_log

tr_tz = timezone(timedelta(hours=3))

COUNTERFACTUAL_FILE = "counterfactual_data.json"
COUNTERFACTUAL_LESSONS_FILE = "counterfactual_lessons.json"

# Takip süresi: 24 saat (saniye)
TRACKING_DURATION_SECONDS = 24 * 60 * 60


class CounterfactualAnalyzer:
    """İki tür counterfactual senaryoyu takip eder:
    1. POST_EXIT: Kapattığımız işlemden sonra fiyat ne yaptı?
    2. MISSED_ENTRY: Girmediğimiz fırsat sonrası fiyat ne yaptı?
    """

    def __init__(self):
        self.scenarios = self._load_scenarios()
        self.lessons = self._load_lessons()

    def _load_scenarios(self) -> list:
        if os.path.exists(COUNTERFACTUAL_FILE):
            try:
                with open(COUNTERFACTUAL_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
        return []

    def _save_scenarios(self):
        try:
            temp_file = COUNTERFACTUAL_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.scenarios, f, indent=4, ensure_ascii=False)
            os.replace(temp_file, COUNTERFACTUAL_FILE)
        except Exception as e:
            add_log(f"⚠️ Counterfactual kayıt hatası: {str(e)}")

    def _load_lessons(self) -> list:
        if os.path.exists(COUNTERFACTUAL_LESSONS_FILE):
            try:
                with open(COUNTERFACTUAL_LESSONS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
        return []

    def _save_lessons(self):
        try:
            temp_file = COUNTERFACTUAL_LESSONS_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.lessons, f, indent=4, ensure_ascii=False)
            os.replace(temp_file, COUNTERFACTUAL_LESSONS_FILE)
        except Exception as e:
            add_log(f"⚠️ Counterfactual ders kayıt hatası: {str(e)}")

    # =========================================================================
    # 1. POST_EXIT: "Ya çıkmasaydım?" takibi
    # =========================================================================
    def track_post_exit(self, trade: dict):
        """Bir trade kapatıldığında çağrılır. Çıkış sonrası fiyat hareketini takip etmek için senaryo açar."""
        coin = trade.get("coin", "")
        trade_id = trade.get("id", "")

        # Aynı trade için zaten senaryo varsa ekleme
        if any(s["trade_id"] == trade_id and s["type"] == "POST_EXIT" for s in self.scenarios):
            return

        exit_price = trade.get("cikis_fiyati", trade.get("giris_fiyati", 0))
        direction = trade.get("yon", "LONG")
        exit_reason = trade.get("exit_reason", "")
        entry_price = trade.get("giris_fiyati", 0)
        realized_pnl_usdt = trade.get("pnl_usdt", 0)
        realized_pnl_pct = trade.get("pnl_yuzde", 0)
        stop_loss = trade.get("stop_loss", 0)
        take_profit = trade.get("take_profit", 0)
        leverage = trade.get("kaldirac", 1)
        miktar_usdt = trade.get("miktar_usdt", 50.0)

        scenario = {
            "id": f"CF_{trade_id}_{int(time.time())}",
            "type": "POST_EXIT",
            "trade_id": trade_id,
            "coin": coin,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "leverage": leverage,
            "risked_usdt": miktar_usdt,
            "realized_pnl_usdt": realized_pnl_usdt,
            "realized_pnl_pct": realized_pnl_pct,
            "durum": "TAKİPTE",
            "start_timestamp": time.time(),
            "end_timestamp": time.time() + TRACKING_DURATION_SECONDS,
            "tarih": datetime.now(tr_tz).strftime("%Y-%m-%d %H:%M:%S"),
            # Takip metrikleri
            "post_exit_max_price": exit_price,
            "post_exit_min_price": exit_price,
            "post_exit_last_price": exit_price,
            "post_exit_max_favorable": 0.0,
            "post_exit_max_adverse": 0.0,
            "phantom_pnl_pct": 0.0,
            "phantom_pnl_usdt": 0.0,
            "verdict": None,
            "lesson": None
        }

        self.scenarios.append(scenario)
        self._save_scenarios()
        add_log(f"🔮 POST_EXIT Counterfactual başlatıldı: {coin} {direction} (Çıkış: ${exit_price:.4f}, PnL: ${realized_pnl_usdt:+.2f})")

    # =========================================================================
    # 2. MISSED_ENTRY: "Ya girseydim?" takibi
    # =========================================================================
    def track_missed_entry(self, coin: str, signal_data: dict, balance: float):
        """Girmediğimiz bir fırsat için counterfactual takip başlatır."""
        entry_price = signal_data.get("entry", 0.0)
        if entry_price == 0.0:
            return

        direction = signal_data.get("direction", "LONG")
        if direction == "NEUTRAL":
            return

        reject_reason = signal_data.get("reject_reason", "Bilinmeyen Filtre")

        # Aynı coin ve yönde zaten aktif missed_entry takibi varsa ekleme
        if any(s["coin"] == coin and s["direction"] == direction and s["type"] == "MISSED_ENTRY" and s["durum"] == "TAKİPTE" for s in self.scenarios):
            return

        stop_loss = signal_data.get("stop_loss", 0)
        take_profit = signal_data.get("take_profit", [0])
        tp_price = take_profit[0] if isinstance(take_profit, list) and take_profit else take_profit
        risked_usdt = round(balance * 0.05, 2)
        confidence = signal_data.get("confidence", 0)
        ev = signal_data.get("ev", 0)
        regime = signal_data.get("regime", "RANGE")

        scenario = {
            "id": f"CM_{coin}_{int(time.time())}",
            "type": "MISSED_ENTRY",
            "trade_id": None,
            "coin": coin,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": None,
            "exit_reason": None,
            "stop_loss": stop_loss,
            "take_profit": tp_price,
            "leverage": 3,
            "realized_pnl_usdt": 0,
            "realized_pnl_pct": 0,
            "risked_usdt": risked_usdt,
            "reject_reason": reject_reason,
            "confidence": confidence,
            "ev": ev,
            "regime": regime,
            "durum": "TAKİPTE",
            "start_timestamp": time.time(),
            "end_timestamp": time.time() + TRACKING_DURATION_SECONDS,
            "tarih": datetime.now(tr_tz).strftime("%Y-%m-%d %H:%M:%S"),
            # Takip metrikleri
            "post_exit_max_price": entry_price,
            "post_exit_min_price": entry_price,
            "post_exit_last_price": entry_price,
            "post_exit_max_favorable": 0.0,
            "post_exit_max_adverse": 0.0,
            "phantom_pnl_pct": 0.0,
            "phantom_pnl_usdt": 0.0,
            "verdict": None,
            "lesson": None
        }

        self.scenarios.append(scenario)
        self._save_scenarios()
        add_log(f"🔮 MISSED_ENTRY Counterfactual başlatıldı: {coin} {direction} @ ${entry_price:.4f} (Eleme: {reject_reason})")

    # =========================================================================
    # 3. Tüm aktif senaryoları güncel fiyatla güncelle
    # =========================================================================
    def update_counterfactuals(self, fetcher):
        """Tüm aktif counterfactual senaryolarını güncel fiyatla günceller. Bot döngüsünden çağrılır."""
        if not self.scenarios:
            return

        updated = False
        current_ts = time.time()
        coins_to_fetch = set()

        # Aktif senaryolardaki coinleri topla
        for s in self.scenarios:
            if s["durum"] == "TAKİPTE":
                coins_to_fetch.add(s["coin"])

        if not coins_to_fetch:
            return

        # Fiyatları toplu çek
        price_cache = {}
        for coin in coins_to_fetch:
            try:
                ticker = fetcher.fetch_ticker(coin)
                price_cache[coin] = ticker["last"]
            except:
                continue

        for s in self.scenarios:
            if s["durum"] != "TAKİPTE":
                continue

            coin = s["coin"]
            if coin not in price_cache:
                continue

            current_price = price_cache[coin]
            direction = s["direction"]
            ref_price = s["exit_price"] if s["type"] == "POST_EXIT" else s["entry_price"]
            leverage = s.get("leverage", 3)

            if ref_price == 0 or ref_price is None:
                continue

            # Fiyat takibi güncelle
            s["post_exit_last_price"] = current_price
            s["post_exit_max_price"] = max(s.get("post_exit_max_price", current_price), current_price)
            s["post_exit_min_price"] = min(s.get("post_exit_min_price", current_price), current_price)

            # Phantom PnL hesapla (çıkmasaydım / girseydim)
            if direction == "LONG":
                phantom_pnl_pct = ((current_price - ref_price) / ref_price) * 100 * leverage
                max_fav = ((s["post_exit_max_price"] - ref_price) / ref_price) * 100 * leverage
                max_adv = ((ref_price - s["post_exit_min_price"]) / ref_price) * 100 * leverage
            else:  # SHORT
                phantom_pnl_pct = ((ref_price - current_price) / ref_price) * 100 * leverage
                max_fav = ((ref_price - s["post_exit_min_price"]) / ref_price) * 100 * leverage
                max_adv = ((s["post_exit_max_price"] - ref_price) / ref_price) * 100 * leverage

            commission = 0.0004 * 2 * 100  # Komisyon
            s["phantom_pnl_pct"] = round(phantom_pnl_pct - commission, 2)
            s["post_exit_max_favorable"] = round(max(s.get("post_exit_max_favorable", 0), max_fav - commission), 2)
            s["post_exit_max_adverse"] = round(max(s.get("post_exit_max_adverse", 0), max_adv + commission), 2)

            risked = s.get("risked_usdt", 50.0)
            s["phantom_pnl_usdt"] = round((phantom_pnl_pct / 100) * risked if risked else 0, 2)

            # Senaryo kapatma koşulları
            should_close = False
            close_reason = None

            # 1. Süre doldu
            if current_ts >= s.get("end_timestamp", current_ts):
                should_close = True
                close_reason = "SÜRE_DOLDU"

            # 2. SL veya TP vuruldu (phantom olarak)
            sl = s.get("stop_loss", 0)
            tp = s.get("take_profit", 0)
            if sl and tp:
                if direction == "LONG":
                    if current_price <= sl:
                        should_close = True
                        close_reason = "PHANTOM_SL"
                    elif current_price >= tp:
                        should_close = True
                        close_reason = "PHANTOM_TP"
                else:
                    if current_price >= sl:
                        should_close = True
                        close_reason = "PHANTOM_SL"
                    elif current_price <= tp:
                        should_close = True
                        close_reason = "PHANTOM_TP"

            if should_close:
                s["durum"] = "TAMAMLANDI"
                if s["type"] == "MISSED_ENTRY":
                    s["exit_price"] = current_price
                s["kapanis_tarihi"] = datetime.now(tr_tz).strftime("%Y-%m-%d %H:%M:%S")
                s["close_reason"] = close_reason

                # Verdict (karar) belirle
                verdict = self._determine_verdict(s)
                s["verdict"] = verdict
                s["lesson"] = self._generate_lesson(s, verdict)

                # Ders kaydet
                self._save_lesson_to_memory(s)

                if s["type"] == "POST_EXIT":
                    emoji = "✅" if verdict == "DOGRU_CIKIS" else "❌" if verdict == "ERKEN_CIKIS" else "➡️"
                    add_log(f"{emoji} COUNTERFACTUAL SONUÇ [{coin}]: {verdict} — Çıkmasaydım: {s['phantom_pnl_pct']:+.2f}% (Max Lehime: {s['post_exit_max_favorable']:+.2f}%, Max Aleyhime: {s['post_exit_max_adverse']:+.2f}%)")
                else:
                    emoji = "💰" if s["phantom_pnl_pct"] > 0 else "🛡️"
                    add_log(f"{emoji} COUNTERFACTUAL SONUÇ [{coin}]: Girseydim: {s['phantom_pnl_pct']:+.2f}% (${s['phantom_pnl_usdt']:+.2f}) — Karar: {verdict}")

            updated = True

        if updated:
            self._save_scenarios()

        # Bellek temizliği: 500'den fazla tamamlanmış senaryo varsa eski olanları sil
        completed = [s for s in self.scenarios if s["durum"] == "TAMAMLANDI"]
        if len(completed) > 500:
            completed_sorted = sorted(completed, key=lambda x: x.get("start_timestamp", 0))
            ids_to_remove = set(s["id"] for s in completed_sorted[:200])
            self.scenarios = [s for s in self.scenarios if s["id"] not in ids_to_remove]
            self._save_scenarios()

    # =========================================================================
    # 4. Verdict (Karar) Belirleme
    # =========================================================================
    def _determine_verdict(self, scenario: dict) -> str:
        """Senaryo sonucuna göre karar verir."""
        s_type = scenario["type"]
        phantom_pnl = scenario.get("phantom_pnl_pct", 0)
        max_favorable = scenario.get("post_exit_max_favorable", 0)

        if s_type == "POST_EXIT":
            if max_favorable >= 2.0:
                return "ERKEN_CIKIS"
            elif phantom_pnl <= -1.0:
                return "DOGRU_CIKIS"
            else:
                return "NOTR_CIKIS"

        elif s_type == "MISSED_ENTRY":
            if phantom_pnl >= 2.0 or max_favorable >= 3.0:
                return "KACIRILDI_KARLI"
            elif phantom_pnl <= -1.0:
                return "BASARIYLA_KACINILDI"
            else:
                return "NOTR_KARAR"

        return "NOTR"

    # =========================================================================
    # 5. Ders Üretme
    # =========================================================================
    def _generate_lesson(self, scenario: dict, verdict: str) -> str:
        """Senaryodan insanı okunabilir ders çıkarır."""
        coin = scenario["coin"]
        direction = scenario["direction"]
        phantom_pnl = scenario.get("phantom_pnl_pct", 0)
        max_fav = scenario.get("post_exit_max_favorable", 0)
        exit_reason = scenario.get("exit_reason", "")
        reject_reason = scenario.get("reject_reason", "")

        if verdict == "ERKEN_CIKIS":
            return (f"{coin} {direction}: Çıkış sonrası fiyat lehimize %{max_fav:.1f} devam etti. "
                    f"Çıkış sebebi '{exit_reason}' erken tetiklendi. Trailing stop daha geniş tutulmalı veya momentum güçlüyken çıkılmamalı.")
        elif verdict == "DOGRU_CIKIS":
            return (f"{coin} {direction}: Çıkış sonrası fiyat aleyhimize döndü (%{phantom_pnl:+.1f}). "
                    f"Çıkış kararı doğruydu. '{exit_reason}' sebebi güvenilir.")
        elif verdict == "KACIRILDI_KARLI":
            return (f"{coin} {direction}: Girmeyi reddettiğimiz sinyal %{phantom_pnl:+.1f} kâr verdi (max %{max_fav:+.1f}). "
                    f"Eleme sebebi '{reject_reason}' bu durumda çok katı olabilir.")
        elif verdict == "BASARIYLA_KACINILDI":
            return (f"{coin} {direction}: Girmeyi reddettiğimiz sinyal %{phantom_pnl:+.1f} zarar verirdi. "
                    f"Eleme sebebi '{reject_reason}' doğru çalıştı.")
        else:
            return f"{coin} {direction}: Belirgin bir fark oluşmadı. Fiyat nötr kaldı."

    # =========================================================================
    # 6. Ders Kaydetme (Coin Intelligence entegrasyonu)
    # =========================================================================
    def _save_lesson_to_memory(self, scenario: dict):
        """Tamamlanan senaryoyu öğrenme hafızasına kaydeder."""
        lesson_entry = {
            "timestamp": datetime.now(tr_tz).strftime("%Y-%m-%d %H:%M:%S"),
            "type": scenario["type"],
            "coin": scenario["coin"],
            "direction": scenario["direction"],
            "verdict": scenario["verdict"],
            "phantom_pnl_pct": scenario.get("phantom_pnl_pct", 0),
            "phantom_pnl_usdt": scenario.get("phantom_pnl_usdt", 0),
            "max_favorable_pct": scenario.get("post_exit_max_favorable", 0),
            "max_adverse_pct": scenario.get("post_exit_max_adverse", 0),
            "exit_reason": scenario.get("exit_reason", ""),
            "reject_reason": scenario.get("reject_reason", ""),
            "lesson": scenario.get("lesson", ""),
            "regime": scenario.get("regime", "RANGE")
        }

        self.lessons.append(lesson_entry)

        # Max 300 ders sakla
        if len(self.lessons) > 300:
            self.lessons = self.lessons[-300:]

        self._save_lessons()

    # =========================================================================
    # 7. Counterfactual Bias Hesaplama (Signal Generator tarafından kullanılır)
    # =========================================================================
    def get_counterfactual_bias(self, coin: str) -> dict:
        """Bir coin için counterfactual verilerden öğrenme bias'ı çıkarır."""
        coin_lessons = [l for l in self.lessons if l["coin"] == coin]

        if len(coin_lessons) < 3:
            return {
                "early_exit_ratio": 0.0,
                "missed_profit_ratio": 0.0,
                "exit_patience_multiplier": 1.0,
                "entry_courage_multiplier": 1.0,
                "total_lessons": len(coin_lessons)
            }

        recent = coin_lessons[-50:]

        post_exit_lessons = [l for l in recent if l["type"] == "POST_EXIT"]
        missed_lessons = [l for l in recent if l["type"] == "MISSED_ENTRY"]

        # Erken çıkış oranı
        early_exits = len([l for l in post_exit_lessons if l["verdict"] == "ERKEN_CIKIS"])
        early_exit_ratio = early_exits / max(len(post_exit_lessons), 1)

        # Kaçırılan kârlı fırsat oranı
        missed_profits = len([l for l in missed_lessons if l["verdict"] == "KACIRILDI_KARLI"])
        missed_profit_ratio = missed_profits / max(len(missed_lessons), 1)

        # Çıkış sabır çarpanı
        exit_patience_multiplier = 1.0 + (early_exit_ratio * 0.5)
        exit_patience_multiplier = min(1.5, exit_patience_multiplier)

        # Giriş cesaret çarpanı
        entry_courage_multiplier = 1.0 + (missed_profit_ratio * 0.3)
        entry_courage_multiplier = min(1.3, entry_courage_multiplier)

        return {
            "early_exit_ratio": round(early_exit_ratio, 3),
            "missed_profit_ratio": round(missed_profit_ratio, 3),
            "exit_patience_multiplier": round(exit_patience_multiplier, 3),
            "entry_courage_multiplier": round(entry_courage_multiplier, 3),
            "total_lessons": len(coin_lessons)
        }

    # =========================================================================
    # 8. İstatistik Özeti (Dashboard ve API için)
    # =========================================================================
    def get_summary_stats(self) -> dict:
        """Tüm counterfactual verilerinin özet istatistiklerini döndürür."""
        completed = [s for s in self.scenarios if s["durum"] == "TAMAMLANDI"]
        active = [s for s in self.scenarios if s["durum"] == "TAKİPTE"]

        post_exit = [s for s in completed if s["type"] == "POST_EXIT"]
        missed = [s for s in completed if s["type"] == "MISSED_ENTRY"]

        early_exits = len([s for s in post_exit if s["verdict"] == "ERKEN_CIKIS"])
        correct_exits = len([s for s in post_exit if s["verdict"] == "DOGRU_CIKIS"])
        neutral_exits = len([s for s in post_exit if s["verdict"] == "NOTR_CIKIS"])

        missed_profits = len([s for s in missed if s["verdict"] == "KACIRILDI_KARLI"])
        avoided_losses = len([s for s in missed if s["verdict"] == "BASARIYLA_KACINILDI"])
        neutral_missed = len([s for s in missed if s["verdict"] == "NOTR_KARAR"])

        total_missed_profit = sum(s.get("phantom_pnl_usdt", 0) for s in missed if s.get("phantom_pnl_usdt", 0) > 0)
        total_avoided_loss = sum(abs(s.get("phantom_pnl_usdt", 0)) for s in missed if s.get("phantom_pnl_usdt", 0) < 0)
        total_early_exit_missed = sum(s.get("post_exit_max_favorable", 0) for s in post_exit if s.get("verdict") == "ERKEN_CIKIS")

        return {
            "active_scenarios": len(active),
            "completed_scenarios": len(completed),
            "post_exit": {
                "total": len(post_exit),
                "early_exits": early_exits,
                "correct_exits": correct_exits,
                "neutral_exits": neutral_exits,
                "exit_accuracy_pct": round((correct_exits / max(len(post_exit), 1)) * 100, 1),
                "avg_early_exit_missed_pct": round(total_early_exit_missed / max(early_exits, 1), 2)
            },
            "missed_entry": {
                "total": len(missed),
                "missed_profits": missed_profits,
                "avoided_losses": avoided_losses,
                "neutral": neutral_missed,
                "filter_accuracy_pct": round((avoided_losses / max(len(missed), 1)) * 100, 1),
                "total_missed_profit_usdt": round(total_missed_profit, 2),
                "total_avoided_loss_usdt": round(total_avoided_loss, 2)
            },
            "total_lessons": len(self.lessons),
            "recent_lessons": self.lessons[-5:] if self.lessons else []
        }
