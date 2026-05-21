import requests
import os
from datetime import datetime, timezone, timedelta

# Turkey Time Zone (UTC+3)
tr_tz = timezone(timedelta(hours=3))

class TelegramNotifier:
    def __init__(self, token=None, chat_id=None):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}" if token else None

    def send_message(self, message: str):
        """Telegram üzerinden mesaj gönderir."""
        if not self.token or not self.chat_id:
            return False, "Token veya Chat ID eksik."
            
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, data=payload, timeout=10)
            if response.status_code == 200:
                return True, "Başarılı"
            else:
                error_data = response.json()
                return False, f"Telegram Hatası: {error_data.get('description', 'Bilinmeyen hata')}"
        except Exception as e:
            return False, f"Bağlantı Hatası: {str(e)}"

    def send_trade_alert(self, trade: dict, is_open: bool = True, balance: float = None):
        """Yeni bir işlem açıldığında veya kapandığında detaylı bildirim gönderir."""
        coin = trade.get("coin", "-")
        yon = trade.get("yon", "-")
        leverage = trade.get("kaldirac", 1)
        emoji = "🚀" if is_open else "✅" if trade.get("pnl_usdt", 0) > 0 else "❌"
        
        intel = trade.get("intelligence_report") or {}
        
        if is_open:
            if intel:
                decision = intel.get("final_decision", "BUY" if yon == "LONG" else "SHORT")
                conf = intel.get("confidence") or trade.get("confidence", 50)
                if isinstance(conf, float):
                    conf_str = f"{conf:.1f}%"
                else:
                    conf_str = f"{conf}%"
                    
                msg = f"🧠 <b>STRATEGIC TRADING INTELLIGENCE REPORT</b> 🧠\n\n"
                msg += f"📊 <b>KARAR MODELİ</b>\n"
                msg += f"• <b>Nihai Karar:</b> <code>{decision}</code> 🟢\n"
                msg += f"• <b>Güven Skoru:</b> <code>{conf_str}</code>\n"
                msg += f"• <b>Devam Olasılığı:</b> <code>{intel.get('continuation_probability', 'MEDIUM')}</code> 🔥\n\n"
                
                msg += f"🛡️ <b>9-KATMANLI ANALİZ</b>\n"
                msg += f"• <b>Market Rejimi:</b> <code>{trade.get('market_regime', 'RANGE')}</code>\n"
                msg += f"• <b>Trend Gücü:</b> <code>TREND_SCORE: {intel.get('trend_score', 50)}/100</code>\n"
                msg += f"• <b>Momentum Kalitesi:</b> <code>MOMENTUM_SCORE: {intel.get('momentum_score', 50)}/100 Consensus</code>\n"
                msg += f"• <b>Fakeout Riski:</b> <code>{intel.get('fakeout_prob', 20.0)}% (DNA Onaylı)</code>\n"
                msg += f"• <b>Likidite Akışı:</b> <code>LIQUIDITY_SCORE: {intel.get('liquidity_score', 50)}/100</code>\n"
                msg += f"• <b>Psikolojik Durum:</b> <code>PSYCHOLOGY_SCORE: {intel.get('psychology_score', 50)}/100</code>\n"
                msg += f"• <b>Risk Seviyesi:</b> <code>RISK_SCORE: {intel.get('risk_score', 50)}/100</code>\n"
                msg += f"• <b>Pozisyon Sabır Skoru:</b> <code>{intel.get('patience_score', 70)}/100</code>\n"
                msg += f"• <b>Çıkış Verimliliği:</b> <code>{intel.get('exit_efficiency', 90)}/100 (AI Recoil Guard Aktif)</code>\n\n"
                
                msg += f"⚙️ <b>POZİSYON AYARLARI</b>\n"
                msg += f"• <b>Coin:</b> #{coin}\n"
                msg += f"• <b>Yön:</b> {yon} ({leverage}x)\n"
                msg += f"• <b>Giriş:</b> ${trade.get('giris_fiyati', 0):,.4f}\n"
                msg += f"• <b>Stop-Loss:</b> ${trade.get('stop_loss', 0):,.4f}\n"
                msg += f"• <b>Take-Profit:</b> ${trade.get('take_profit', 0):,.4f}\n"
                msg += f"• <b>Miktar:</b> ${trade.get('miktar_usdt', 0):,.2f}\n"
            else:
                msg = f"{emoji} <b>YENİ İŞLEM AÇILDI</b> {emoji}\n\n"
                msg += f"<b>Coin:</b> #{coin}\n"
                msg += f"<b>Yön:</b> {yon} ({leverage}x)\n"
                msg += f"<b>Giriş:</b> ${trade.get('giris_fiyati', 0):,.4f}\n"
                msg += f"<b>Stop-Loss:</b> ${trade.get('stop_loss', 0):,.4f}\n"
                msg += f"<b>Take-Profit:</b> ${trade.get('take_profit', 0):,.4f}\n"
                msg += f"<b>Miktar:</b> ${trade.get('miktar_usdt', 0):,.2f}\n"
        else:
            pnl_pct = trade.get("pnl_yuzde", 0)
            pnl_usdt = trade.get("pnl_usdt", 0)
            msg = f"{emoji} <b>İŞLEM KAPANDI</b> {emoji}\n\n"
            msg += f"<b>Coin:</b> #{coin}\n"
            msg += f"<b>Yön:</b> {yon} ({leverage}x)\n"
            msg += f"<b>Çıkış Fiyatı:</b> ${trade.get('cikis_fiyati', 0):,.4f}\n"
            msg += f"<b>Kâr/Zarar:</b> {pnl_pct:+.2f}% (${pnl_usdt:+.2f})\n"
            msg += f"<b>Neden:</b> {trade.get('exit_reason', 'Hedef Gerçekleşti')}\n"

        if balance is not None:
            msg += f"<b>Toplam Bakiye:</b> ${balance:,.2f}\n"

        msg += f"\n<i>Tarih: {datetime.now(tr_tz).strftime('%Y-%m-%d %H:%M:%S')}</i>"
        return self.send_message(msg)

    def send_partial_take_profit_alert(self, trade: dict, tp_level: int, realized_pnl: float, balance: float = None):
        """Kademeli kâr al (TP1/TP2) gerçekleştiğinde Telegram üzerinden bildirim gönderir."""
        coin = trade.get("coin", "-")
        yon = trade.get("yon", "-")
        leverage = trade.get("kaldirac", 1)
        
        sold_pct = "50" if tp_level == 1 else "25"
        remaining_pct = "50" if tp_level == 1 else "25"
        next_target = "TP2 (%4.5)" if tp_level == 1 else "Nihai Kapanış"
        
        emoji = "🎯"
        msg = f"{emoji} <b>KADEMELİ SATIŞ YAPILDI (TP{tp_level})</b> {emoji}\n\n"
        msg += f"<b>Coin:</b> #{coin}\n"
        msg += f"<b>Yön:</b> {yon} ({leverage}x)\n"
        msg += f"<b>Satılan Miktar:</b> Pozisyonun %{sold_pct}'si satıldı.\n"
        msg += f"<b>Realize Edilen Kâr:</b> +${realized_pnl:,.2f} (+{trade.get('pnl_yuzde', 0):.2f}%)\n"
        
        if tp_level == 1:
            msg += f"<b>Stop Loss Güncellemesi:</b> Giriş fiyatına (${trade.get('giris_fiyati', 0):,.4f}) çekilerek pozisyon risksiz hale getirildi! 🛡️\n"
        else:
            msg += f"<b>Stop Loss Güncellemesi:</b> Garanti %+1.2 kâr bölgesine (${trade.get('stop_loss', 0):,.4f}) çekildi! 🛡️\n"
            
        msg += f"<b>Kalan Pozisyon:</b> %{remaining_pct} ({next_target} bekleniyor...)\n"
        
        if balance is not None:
            msg += f"<b>Güncel Toplam Bakiye (Cüzdan):</b> ${balance:,.2f} 💰\n"
            
        msg += f"\n<i>Tarih: {datetime.now(tr_tz).strftime('%Y-%m-%d %H:%M:%S')}</i>"
        return self.send_message(msg)

    def send_trade_learning_update(self, trade: dict, memory_entry: dict):
        """Her işlem kapandığında öğrenilen dersi Telegram'a gönderir — hafıza birikimi sağlar."""
        coin = trade.get("coin", "-")
        yon = trade.get("yon", "-")
        pnl_usdt = trade.get("pnl_usdt", 0)
        pnl_yuzde = trade.get("pnl_yuzde", 0)
        regime = trade.get("market_regime", memory_entry.get("regime", "RANGE"))
        exit_reason = memory_entry.get("exit_reason", trade.get("exit_reason", "Bilinmiyor"))
        outcome = memory_entry.get("outcome", 0)
        
        emoji = "✅" if outcome == 1 else "❌"
        outcome_text = "BAŞARILI" if outcome == 1 else "BAŞARISIZ"
        
        msg = f"🧠 <b>AI HAFIZA GÜNCELLEMESİ</b> 🧠\n\n"
        msg += f"{emoji} <b>İşlem Sonucu:</b> <code>{outcome_text}</code>\n"
        msg += f"• <b>Coin:</b> #{coin} ({yon})\n"
        msg += f"• <b>Rejim:</b> <code>{regime}</code>\n"
        msg += f"• <b>PNL:</b> <code>{pnl_yuzde:+.2f}% (${pnl_usdt:+.2f})</code>\n"
        msg += f"• <b>Çıkış Sebebi:</b> {exit_reason}\n\n"
        
        # Vektör bilgisi
        vector = memory_entry.get("vector", [])
        if vector:
            labels = ["RSI", "MACD", "EMA_Cross", "Bollinger", "ADX", "Volume"]
            vector_str = " | ".join([f"{labels[i]}:{v:.2f}" for i, v in enumerate(vector) if i < len(labels)])
            msg += f"📊 <b>Karar Vektörü:</b>\n<code>{vector_str}</code>\n\n"
        
        msg += f"💾 <b>Hafızaya kaydedildi.</b> Bot bu deseni gelecekte tanıyacak.\n"
        msg += f"\n<i>Tarih: {datetime.now(tr_tz).strftime('%Y-%m-%d %H:%M:%S')}</i>"
        return self.send_message(msg)

    def send_trade_memory_report(self, memory_data: dict, balance: float = None):
        """Tüm coin hafıza istatistiklerini Telegram'a özet rapor olarak gönderir."""
        if not memory_data:
            return False, "Hafıza verisi boş."
        
        msg = f"📊 <b>AI HAFIZA RAPORU</b> 📊\n"
        msg += f"{'═' * 30}\n\n"
        
        total_trades = 0
        total_wins = 0
        total_pnl = 0.0
        coin_stats = []
        
        for coin, trades in memory_data.items():
            if not trades:
                continue
            count = len(trades)
            wins = len([t for t in trades if t.get("outcome", 0) == 1])
            pnl = sum(t.get("pnl_usdt", 0) for t in trades)
            win_rate = (wins / count * 100) if count > 0 else 0
            
            total_trades += count
            total_wins += wins
            total_pnl += pnl
            coin_stats.append((coin, count, wins, win_rate, pnl))
        
        # Genel istatistikler
        overall_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
        msg += f"🏆 <b>GENEL İSTATİSTİKLER</b>\n"
        msg += f"• Toplam İşlem: <code>{total_trades}</code>\n"
        msg += f"• Kazanma Oranı: <code>%{overall_wr:.1f}</code> ({total_wins}/{total_trades})\n"
        msg += f"• Toplam PNL: <code>${total_pnl:+.2f}</code>\n\n"
        
        # Coin bazlı detaylar
        msg += f"📈 <b>COİN BAZLI DETAY</b>\n"
        for coin, count, wins, wr, pnl in sorted(coin_stats, key=lambda x: x[4], reverse=True):
            emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
            msg += f"{emoji} <b>{coin}:</b> {count} işlem | %{wr:.0f} WR | <code>${pnl:+.2f}</code>\n"
        
        # Öğrenilen dersler — en son eklenen exit_reason'ları listele
        msg += f"\n📝 <b>SON ÖĞRENME NOTLARI</b>\n"
        all_lessons = []
        for coin, trades in memory_data.items():
            for t in trades[-2:]:  # Her coinden son 2
                reason = t.get("exit_reason", "")
                if reason and len(reason) > 10:
                    all_lessons.append(f"• [{coin}] {reason[:100]}")
        
        for lesson in all_lessons[-8:]:  # Max 8 ders göster
            msg += f"{lesson}\n"
        
        if balance is not None:
            msg += f"\n💰 <b>Güncel Bakiye:</b> ${balance:,.2f}\n"
        
        msg += f"\n<i>Rapor Tarihi: {datetime.now(tr_tz).strftime('%Y-%m-%d %H:%M:%S')}</i>"
        return self.send_message(msg)
