# -*- coding: utf-8 -*-
import os
import json
import requests
import threading
from log_manager import add_log

# Target files
TRADE_FILE = "bot_trades.json"
AVOIDED_FILE = "bot_avoided_trades.json"
MEMORY_FILE = "coin_trade_memory.json"

# 🔒 Bu botun kimliği — sync sırasında diğer botun verisi yüklenmesini engeller
BOT_IDENTIFIER = "BOT2_AGGRESSIVE"

class HybridDatabaseManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(HybridDatabaseManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.lock = threading.Lock()
        self.upload_timer = None
        
        # 🧹 Başlangıç temizliği: Bot 2 sadece BTC ve SOL trade eder
        self._cleanup_wrong_coins()
        
        # Initial sync on startup (Cloud -> Local)
        RESET_FLAG = ".data_reset_v2_done"
        if os.path.exists(RESET_FLAG):
            add_log("☁️ Telegram Cloud Sync: Temiz başlangıç bayrağı algılandı — buluttan çekme atlanıyor.")
            self._force_push_empty_to_cloud()
        else:
            self.sync_from_cloud()
        
        # 🔄 Tek Seferlik Veri Geri Yükleme (seed_restore.json varsa eski verileri birleştir)
        self._apply_seed_restore()
        
        # 🔒 Çift pozisyon temizliği: Aynı coinde birden fazla AÇIK trade varsa yeniyi koru, eskiyi iptal et
        self._cleanup_duplicate_open_trades()

    def _cleanup_wrong_coins(self):
        """Bot 2 sadece BTC ve SOL trade eder. Yanlış coinlerin verilerini temizle."""
        ALLOWED_COINS = {"BTC", "SOL"}
        
        # Trades temizle
        if os.path.exists(TRADE_FILE):
            try:
                with open(TRADE_FILE, "r", encoding="utf-8") as f:
                    trades = json.load(f)
                original_count = len(trades)
                trades = [t for t in trades if t.get("coin", "") in ALLOWED_COINS]
                if len(trades) < original_count:
                    with open(TRADE_FILE, "w", encoding="utf-8") as f:
                        json.dump(trades, f, indent=4, ensure_ascii=False)
                    removed = original_count - len(trades)
                    add_log(f"🧹 Başlangıç Temizliği: {removed} yanlış coin trade'i silindi (sadece BTC/SOL tutuldu).")
            except Exception:
                pass
        
        # Memory temizle
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    memory = json.load(f)
                original_keys = set(memory.keys())
                memory = {k: v for k, v in memory.items() if k in ALLOWED_COINS}
                removed_keys = original_keys - set(memory.keys())
                if removed_keys:
                    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                        json.dump(memory, f, indent=4, ensure_ascii=False)
                    add_log(f"🧹 Hafıza Temizliği: {removed_keys} coin hafızası silindi (sadece BTC/SOL tutuldu).")
            except Exception:
                pass

    def _get_sync_credentials(self):
        """Sync kanalı bilgilerini döndürür."""
        try:
            from config import load_app_settings
            settings = load_app_settings()
        except Exception:
            settings = {}
            
        token = os.getenv("TELEGRAM_TOKEN", settings.get("tg_token", ""))
        # 📊 DATA kanalı — sync ve görüntüleme buradan
        data_chat_id = os.getenv("TELEGRAM_DATA_CHAT_ID", settings.get("tg_data_chat_id", os.getenv("TELEGRAM_CHAT_ID", settings.get("tg_chat_id", ""))))
        
        return token, data_chat_id

    def _merge_trades(self, local_trades, cloud_trades):
        """Merges two trade histories, taking the union based on trade ID with strict validation."""
        trade_map = {}
        ALLOWED_COINS = {"BTC", "SOL"}
        
        def is_valid(t):
            if not isinstance(t, dict):
                return False
            if "coin" not in t or "id" not in t:
                return False
            # Bot 2 sadece BTC ve SOL trade eder
            if t.get("coin", "") not in ALLOWED_COINS:
                return False
            tid = str(t.get("id"))
            if tid in ("render_avax_live", "avoid_btc"):
                return False
            return True

        for t in local_trades:
            if is_valid(t):
                tid = str(t.get("id"))
                trade_map[tid] = t
            
        for t in cloud_trades:
            if is_valid(t):
                tid = str(t.get("id"))
                if tid in trade_map:
                    local_t = trade_map[tid]
                    if t.get("durum") == "KAPALI" and local_t.get("durum") != "KAPALI":
                        trade_map[tid] = t
                    elif t.get("pnl_usdt", 0) != 0 and local_t.get("pnl_usdt", 0) == 0:
                        trade_map[tid] = t
                else:
                    trade_map[tid] = t
                
        merged = list(trade_map.values())
        try:
            merged.sort(key=lambda x: x.get("tarih", ""), reverse=True)
        except Exception:
            pass
        return merged

    def _cleanup_duplicate_open_trades(self):
        """Aynı coinde birden fazla AÇIK trade varsa en yeniyi koru, diğerlerini İPTAL et."""
        if not os.path.exists(TRADE_FILE):
            return
        try:
            with open(TRADE_FILE, "r", encoding="utf-8") as f:
                trades = json.load(f)
            
            # Coin bazlı AÇIK trade'leri grupla
            open_by_coin = {}
            for i, t in enumerate(trades):
                if t.get("durum") == "AÇIK":
                    coin = t.get("coin", "")
                    if coin not in open_by_coin:
                        open_by_coin[coin] = []
                    open_by_coin[coin].append(i)
            
            changed = False
            for coin, indices in open_by_coin.items():
                if len(indices) <= 1:
                    continue
                
                # En yeni trade'i bul (start_timestamp veya tarih bazlı)
                best_idx = indices[0]
                best_ts = trades[best_idx].get("start_timestamp", 0)
                for idx in indices[1:]:
                    ts = trades[idx].get("start_timestamp", 0)
                    if ts > best_ts:
                        best_ts = ts
                        best_idx = idx
                
                # Diğerlerini İPTAL et (PNL sıfırla, durum KAPALI yap)
                for idx in indices:
                    if idx != best_idx:
                        trades[idx]["durum"] = "KAPALI"
                        trades[idx]["exit_reason"] = "DUPLICATE_CLEANUP (Çift pozisyon temizliği — restart sonrası)"
                        trades[idx]["pnl_usdt"] = 0.0
                        trades[idx]["pnl_yuzde"] = 0.0
                        trades[idx]["cikis_fiyati"] = trades[idx].get("giris_fiyati", 0)
                        from datetime import datetime, timezone, timedelta
                        tr_tz = timezone(timedelta(hours=3))
                        trades[idx]["kapanis_tarihi"] = datetime.now(tr_tz).strftime("%Y-%m-%d %H:%M:%S")
                        add_log(f"🔒 ÇİFT POZİSYON TEMİZLİĞİ: {coin} — Eski çift trade (ID: {trades[idx].get('id', '?')}) sıfır PNL ile kapatıldı. Yeni trade (ID: {trades[best_idx].get('id', '?')}) korunuyor.")
                        changed = True
            
            if changed:
                with open(TRADE_FILE, "w", encoding="utf-8") as f:
                    json.dump(trades, f, indent=4, ensure_ascii=False)
                add_log("✅ Çift pozisyon temizliği tamamlandı.")
        except Exception as e:
            add_log(f"⚠️ Çift pozisyon temizliği hatası: {str(e)}")

    def _apply_seed_restore(self):
        """Tek seferlik veri geri yükleme: seed_restore.json varsa eski verileri mevcut verilerle birleştirir.
        ÖNEMLİ: Seed'den gelen AÇIK trade'ler, lokalde aynı coin'de zaten AÇIK trade varsa eklenmez."""
        SEED_FILE = "seed_restore.json"
        if not os.path.exists(SEED_FILE):
            return
        
        try:
            add_log("🔄 SEED RESTORE: Eski veri dosyası bulundu, birleştirme başlıyor...")
            
            with open(SEED_FILE, "r", encoding="utf-8") as f:
                seed_data = json.load(f)
            
            seed_trades = seed_data.get("trades", [])
            seed_avoided = seed_data.get("avoided", [])
            seed_memory = seed_data.get("memory", {})
            
            # Mevcut lokal verileri oku
            local_trades = []
            if os.path.exists(TRADE_FILE):
                with open(TRADE_FILE, "r", encoding="utf-8") as f:
                    local_trades = json.load(f)
            
            local_avoided = []
            if os.path.exists(AVOIDED_FILE):
                with open(AVOIDED_FILE, "r", encoding="utf-8") as f:
                    local_avoided = json.load(f)
            
            local_memory = {}
            if os.path.exists(MEMORY_FILE):
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    local_memory = json.load(f)
            
            # 🛡️ Lokalde zaten AÇIK olan coinleri bul
            local_open_coins = set()
            for t in local_trades:
                if t.get("durum") == "AÇIK":
                    local_open_coins.add(t.get("coin", ""))
            
            # Seed trade'lerinden AÇIK olanları filtrele (çakışma varsa ekleme)
            filtered_seed_trades = []
            skipped_count = 0
            for t in seed_trades:
                if t.get("durum") == "AÇIK" and t.get("coin", "") in local_open_coins:
                    skipped_count += 1
                    add_log(f"🔄 SEED: {t.get('coin')} AÇIK trade atlandı — lokalde zaten aktif pozisyon var.")
                    continue
                filtered_seed_trades.append(t)
            
            if skipped_count > 0:
                add_log(f"🔄 SEED: {skipped_count} çift AÇIK trade atlandı (lokalde zaten var).")
            
            # Trade'leri birleştir (ID bazlı)
            merged_trades = self._merge_trades(local_trades, filtered_seed_trades)
            
            # Avoided trade'leri birleştir (ID bazlı)
            avoided_map = {}
            for a in seed_avoided:
                aid = str(a.get("id", ""))
                if aid:
                    avoided_map[aid] = a
            for a in local_avoided:
                aid = str(a.get("id", ""))
                if aid:
                    avoided_map[aid] = a  # Lokal öncelikli
            merged_avoided = list(avoided_map.values())
            
            # Memory'yi birleştir (coin bazlı)
            merged_memory = dict(seed_memory)
            for coin, entries in local_memory.items():
                if coin in merged_memory:
                    existing_ids = {str(e.get("timestamp", "")) for e in merged_memory[coin]}
                    for entry in entries:
                        if str(entry.get("timestamp", "")) not in existing_ids:
                            merged_memory[coin].append(entry)
                else:
                    merged_memory[coin] = entries
            
            # Dosyalara yaz
            with open(TRADE_FILE, "w", encoding="utf-8") as f:
                json.dump(merged_trades, f, indent=4, ensure_ascii=False)
            
            with open(AVOIDED_FILE, "w", encoding="utf-8") as f:
                json.dump(merged_avoided, f, indent=4, ensure_ascii=False)
            
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(merged_memory, f, indent=4, ensure_ascii=False)
            
            # Seed dosyasını sil (tekrar çalışmasın)
            os.remove(SEED_FILE)
            
            add_log(f"✅ SEED RESTORE TAMAMLANDI: {len(merged_trades)} trade, {len(merged_avoided)} avoided, {len(merged_memory)} coin memory birleştirildi.")
            
            # ☁️ Buluta hemen yükle (Telegram yedeğini kalıcı olarak güncelle)
            add_log("☁️ SEED RESTORE: Birleştirilen veriler Telegram bulutuna yükleniyor...")
            self._upload_worker()
            
        except Exception as e:
            add_log(f"⚠️ SEED RESTORE HATASI: {str(e)}")
            try:
                os.remove(SEED_FILE)
            except:
                pass

    def _force_push_empty_to_cloud(self):
        """Pushes empty trade data to Telegram cloud to overwrite old backups after a reset."""
        token, chat_id = self._get_sync_credentials()
            
        if not token or not chat_id:
            return
            
        try:
            backup_data = {"trades": [], "avoided": [], "bot_id": BOT_IDENTIFIER}
            backup_file = "db_backup.json"
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=4, ensure_ascii=False)
                
            url_send = f"https://api.telegram.org/bot{token}/sendDocument"
            with open(backup_file, "rb") as f:
                res = requests.post(url_send, data={"chat_id": chat_id, "caption": f"=== {BOT_IDENTIFIER} CLEAN RESET ==="}, files={"document": f}, timeout=10)
            
            send_res = res.json()
            if send_res.get("ok"):
                message_id = send_res["result"]["message_id"]
                url_pin = f"https://api.telegram.org/bot{token}/pinChatMessage"
                requests.post(url_pin, data={"chat_id": chat_id, "message_id": message_id, "disable_notification": True}, timeout=10)
                add_log("☁️ Telegram Cloud: Bulut yedeği boş veriyle güncellendi (temiz başlangıç).")
                
            if os.path.exists(backup_file):
                os.remove(backup_file)
        except Exception as e:
            add_log(f"⚠️ Telegram Cloud temiz push hatası: {e}")

    def sync_from_cloud(self):
        """Blocking initial pull — sadece BU BOTA ait verileri yükler.
        Diğer botun verisi bulunursa atlanır.
        """
        if os.path.exists(".data_reset_v2_done"):
            return
            
        token, chat_id = self._get_sync_credentials()
        
        if not token or not chat_id:
            add_log("⚠️ Telegram Cloud Sync: Telegram ayarları eksik.")
            return

        with self.lock:
            try:
                # Bu botun ID'sini al
                my_info = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5).json()
                my_bot_id = my_info.get("result", {}).get("id", 0)
                
                url_get = f"https://api.telegram.org/bot{token}/getChat"
                res = requests.get(url_get, params={"chat_id": chat_id}, timeout=8)
                if res.status_code != 200:
                    add_log(f"⚠️ Telegram Cloud Sync: getChat başarısız (HTTP {res.status_code})")
                    return
                    
                chat_info = res.json()
                pinned = chat_info.get("result", {}).get("pinned_message", {})
                if pinned and pinned.get("document"):
                    # 🛡️ Gönderen kontrolü: Sadece BU botun gönderdiği mesajı oku
                    pinned_sender_id = pinned.get("from", {}).get("id", 0)
                    if pinned_sender_id != my_bot_id and my_bot_id != 0:
                        add_log(f"ℹ️ Telegram Cloud Sync: Pinli mesaj başka bota ait (sender: {pinned_sender_id}, ben: {my_bot_id}). Atlanıyor.")
                        return
                    
                    doc = pinned["document"]
                    file_id = doc["file_id"]
                    
                    url_file = f"https://api.telegram.org/bot{token}/getFile"
                    file_res = requests.get(url_file, params={"file_id": file_id}, timeout=8).json()
                    file_path = file_res["result"]["file_path"]
                    
                    download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                    download_res = requests.get(download_url, timeout=10)
                    if download_res.status_code == 200:
                        backup_data = download_res.json()
                        
                        # 🛡️ Bot kimlik kontrolü: Yanlış botun verisi yüklenmesini engelle
                        backup_bot_id = backup_data.get("bot_id", "")
                        if backup_bot_id and backup_bot_id != BOT_IDENTIFIER:
                            add_log(f"⚠️ Telegram Cloud Sync: Yedek başka bota ait ({backup_bot_id}). Atlanıyor.")
                            return
                        
                        trades = backup_data.get("trades", [])
                        avoided = backup_data.get("avoided", [])
                        memory = backup_data.get("memory", {})
                        
                        # 0. Sync Memory
                        if memory and isinstance(memory, dict):
                            # Sadece BTC ve SOL hafızasını al
                            ALLOWED = {"BTC", "SOL"}
                            memory = {k: v for k, v in memory.items() if k in ALLOWED}
                            
                            local_memory = {}
                            if os.path.exists(MEMORY_FILE):
                                try:
                                    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                                        local_memory = json.load(f)
                                except Exception: pass
                            for coin, cloud_entries in memory.items():
                                if coin not in local_memory:
                                    local_memory[coin] = cloud_entries
                                else:
                                    existing_timestamps = {e.get("timestamp") for e in local_memory[coin]}
                                    for entry in cloud_entries:
                                        if entry.get("timestamp") not in existing_timestamps:
                                            local_memory[coin].append(entry)
                                    local_memory[coin] = local_memory[coin][-100:]
                            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                                json.dump(local_memory, f, indent=4, ensure_ascii=False)
                        
                        # 1. Sync Trades (merge filtreli — sadece BTC/SOL)
                        local_trades = []
                        if os.path.exists(TRADE_FILE):
                            try:
                                with open(TRADE_FILE, "r", encoding="utf-8") as f:
                                    local_trades = json.load(f)
                            except Exception: pass
                        merged_trades = self._merge_trades(local_trades, trades)
                        with open(TRADE_FILE, "w", encoding="utf-8") as f:
                            json.dump(merged_trades, f, indent=4, ensure_ascii=False)
                            
                        # 2. Sync Avoided
                        local_avoided = []
                        if os.path.exists(AVOIDED_FILE):
                            try:
                                with open(AVOIDED_FILE, "r", encoding="utf-8") as f:
                                    local_avoided = json.load(f)
                            except Exception: pass
                        merged_avoided = self._merge_trades(local_avoided, avoided)
                        with open(AVOIDED_FILE, "w", encoding="utf-8") as f:
                            json.dump(merged_avoided, f, indent=4, ensure_ascii=False)
                            
                        add_log(f"☁️ Telegram Cloud Sync: Buluttan {len(merged_trades)} işlem geri yüklendi.")
                    else:
                        add_log("⚠️ Telegram Cloud Sync: Dosya indirilemedi.")
                else:
                    if not getattr(self, '_pinned_not_found_logged', False):
                        add_log("ℹ️ Telegram Cloud Sync: Pinned yedek bulunamadı.")
                        self._pinned_not_found_logged = True
            except Exception as e:
                add_log(f"⚠️ Telegram Cloud Sync Hatası: {str(e)}")

    def push_to_cloud(self, filename=None, key=None):
        """Schedules a debounced asynchronous upload."""
        with self.lock:
            if self.upload_timer is not None:
                try:
                    self.upload_timer.cancel()
                except Exception:
                    pass
            self.upload_timer = threading.Timer(15.0, self._upload_worker)
            self.upload_timer.start()

    def _upload_worker(self):
        token, chat_id = self._get_sync_credentials()
            
        if not token or not chat_id:
            return
            
        with self.lock:
            self.upload_timer = None
            trades_data = []
            if os.path.exists(TRADE_FILE):
                try:
                    with open(TRADE_FILE, "r", encoding="utf-8") as f:
                        trades_data = json.load(f)
                except Exception: pass
                
            avoided_data = []
            if os.path.exists(AVOIDED_FILE):
                try:
                    with open(AVOIDED_FILE, "r", encoding="utf-8") as f:
                        avoided_data = json.load(f)
                except Exception: pass
                
            memory_data = {}
            if os.path.exists(MEMORY_FILE):
                try:
                    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                        memory_data = json.load(f)
                except Exception: pass
                
            backup_data = {
                "trades": trades_data,
                "avoided": avoided_data,
                "memory": memory_data,
                "bot_id": BOT_IDENTIFIER
            }
            
            backup_file = "db_backup.json"
            try:
                with open(backup_file, "w", encoding="utf-8") as f:
                    json.dump(backup_data, f, indent=4, ensure_ascii=False)
                    
                url_send = f"https://api.telegram.org/bot{token}/sendDocument"
                with open(backup_file, "rb") as f:
                    res = requests.post(url_send, data={"chat_id": chat_id, "caption": f"=== {BOT_IDENTIFIER} DB BACKUP ==="}, files={"document": f}, timeout=10)
                
                send_res = res.json()
                if send_res.get("ok"):
                    message_id = send_res["result"]["message_id"]
                    
                    url_pin = f"https://api.telegram.org/bot{token}/pinChatMessage"
                    requests.post(url_pin, data={"chat_id": chat_id, "message_id": message_id, "disable_notification": True}, timeout=10)
                    
            except Exception as e:
                add_log(f"⚠️ Telegram Cloud Sync push hatası: {str(e)}")
            finally:
                if os.path.exists(backup_file):
                    try:
                        os.remove(backup_file)
                    except Exception: pass

# Global instance initialization to trigger early sync at import time
db_manager = HybridDatabaseManager()
