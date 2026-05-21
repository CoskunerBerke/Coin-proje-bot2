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
        
        # Initial sync on startup (Cloud -> Local) — SKIP if fresh reset was just performed
        RESET_FLAG = ".data_reset_v2_done"
        if os.path.exists(RESET_FLAG):
            add_log("☁️ Telegram Cloud Sync: Temiz başlangıç bayrağı algılandı — buluttan çekme atlanıyor.")
            # Push the clean empty data TO the cloud to overwrite old backup
            self._force_push_empty_to_cloud()
        else:
            self.sync_from_cloud()

    def _merge_trades(self, local_trades, cloud_trades):
        """Merges two trade histories, taking the union based on trade ID with strict validation."""
        trade_map = {}
        
        def is_valid(t):
            if not isinstance(t, dict):
                return False
            if "coin" not in t or "id" not in t:
                return False
            # Filter out known malformed/dummy test items
            tid = str(t.get("id"))
            if tid in ("render_avax_live", "avoid_btc") or t.get("coin") in ("AVAX", "BTC") and (len(t) < 4):
                return False
            return True

        # Load local first
        for t in local_trades:
            if is_valid(t):
                tid = str(t.get("id"))
                trade_map[tid] = t
            
        # Overwrite/Add cloud trades (cloud is considered more up-to-date for Render redeploys)
        for t in cloud_trades:
            if is_valid(t):
                tid = str(t.get("id"))
                if tid in trade_map:
                    local_t = trade_map[tid]
                    # If cloud version has KAPALI status and local doesn't, or has newer updates, merge it
                    if t.get("durum") == "KAPALI" and local_t.get("durum") != "KAPALI":
                        trade_map[tid] = t
                    elif t.get("pnl_usdt", 0) != 0 and local_t.get("pnl_usdt", 0) == 0:
                        trade_map[tid] = t
                    else:
                        # Keep local if it has more fields or same status
                        pass
                else:
                    trade_map[tid] = t
                
        # Sort trades by descending timestamp or date
        merged = list(trade_map.values())
        try:
            merged.sort(key=lambda x: x.get("tarih", ""), reverse=True)
        except Exception:
            pass
        return merged

    def _force_push_empty_to_cloud(self):
        """Pushes empty trade data to Telegram cloud to overwrite old backups after a reset."""
        try:
            from config import load_app_settings
            settings = load_app_settings()
        except Exception:
            settings = {}
            
        token = os.getenv("TELEGRAM_TOKEN", settings.get("tg_token", ""))
        chat_id = os.getenv("TELEGRAM_DATA_CHAT_ID", settings.get("tg_data_chat_id", os.getenv("TELEGRAM_CHAT_ID", settings.get("tg_chat_id", ""))))
        
        if str(chat_id) == "-5183733793":
            chat_id = "-1003958108455"
            
        if not token or not chat_id:
            return
            
        try:
            backup_data = {"trades": [], "avoided": []}
            backup_file = "db_backup.json"
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, indent=4, ensure_ascii=False)
                
            # Unpin old
            url_unpin = f"https://api.telegram.org/bot{token}/unpinChatMessage"
            requests.post(url_unpin, data={"chat_id": chat_id}, timeout=5)
            
            # Send empty backup
            url_send = f"https://api.telegram.org/bot{token}/sendDocument"
            with open(backup_file, "rb") as f:
                res = requests.post(url_send, data={"chat_id": chat_id, "caption": "=== CLEAN RESET: BTC+SOL $1000 ==="}, files={"document": f}, timeout=10)
            
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
        """Blocking initial pull from Telegram Pinned Message to restore any lost files after Render restarts."""
        # Block sync if reset was performed — don't let old cloud data overwrite clean slate
        if os.path.exists(".data_reset_v2_done"):
            return
            
        # Avoid circular import of load_app_settings
        try:
            from config import load_app_settings
            settings = load_app_settings()
        except Exception:
            settings = {}
            
        token = os.getenv("TELEGRAM_TOKEN", settings.get("tg_token", ""))
        chat_id = os.getenv("TELEGRAM_DATA_CHAT_ID", settings.get("tg_data_chat_id", os.getenv("TELEGRAM_CHAT_ID", settings.get("tg_chat_id", ""))))
        
        # Upgrade/normalize old migrated group chat ID to the new supergroup ID
        if str(chat_id) == "-5183733793":
            chat_id = "-1003958108455"
            
        if not token or not chat_id:
            add_log("⚠️ Telegram Cloud Sync: Telegram ayarları eksik. Bulut senkronizasyonu devre dışı bırakıldı.")
            return

        with self.lock:
            try:
                # add_log("☁️ Telegram Cloud Sync: Buluttan güncel yedek taranıyor...")
                url_get = f"https://api.telegram.org/bot{token}/getChat"
                res = requests.get(url_get, params={"chat_id": chat_id}, timeout=8)
                if res.status_code != 200:
                    add_log(f"⚠️ Telegram Cloud Sync: getChat başarısız (HTTP {res.status_code})")
                    return
                    
                chat_info = res.json()
                pinned = chat_info.get("result", {}).get("pinned_message", {})
                if pinned and pinned.get("document"):
                    doc = pinned["document"]
                    file_id = doc["file_id"]
                    
                    # Fetch file path
                    url_file = f"https://api.telegram.org/bot{token}/getFile"
                    file_res = requests.get(url_file, params={"file_id": file_id}, timeout=8).json()
                    file_path = file_res["result"]["file_path"]
                    
                    # Download file
                    download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                    download_res = requests.get(download_url, timeout=10)
                    if download_res.status_code == 200:
                        backup_data = download_res.json()
                        trades = backup_data.get("trades", [])
                        avoided = backup_data.get("avoided", [])
                        memory = backup_data.get("memory", {})
                        
                        # 0. Sync Memory (coin_trade_memory.json)
                        if memory and isinstance(memory, dict):
                            local_memory = {}
                            if os.path.exists(MEMORY_FILE):
                                try:
                                    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                                        local_memory = json.load(f)
                                except Exception: pass
                            # Merge: cloud entries extend local, dedup by timestamp
                            for coin, cloud_entries in memory.items():
                                if coin not in local_memory:
                                    local_memory[coin] = cloud_entries
                                else:
                                    existing_timestamps = {e.get("timestamp") for e in local_memory[coin]}
                                    for entry in cloud_entries:
                                        if entry.get("timestamp") not in existing_timestamps:
                                            local_memory[coin].append(entry)
                                    # Keep max 100 per coin (sliding window)
                                    local_memory[coin] = local_memory[coin][-100:]
                            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                                json.dump(local_memory, f, indent=4, ensure_ascii=False)
                        
                        # 1. Sync Trades
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
                            
                        # add_log(f"☁️ Telegram Cloud Sync: Buluttan {len(merged_trades)} işlem ve {len(merged_avoided)} engellenen işlem başarıyla geri yüklendi.")
                    else:
                        add_log("⚠️ Telegram Cloud Sync: Yedekleme dosyası indirilemedi.")
                else:
                    add_log("ℹ️ Telegram Cloud Sync: Pinned yedek bulunamadı. Bulutta yeni profil oluşturulacak.")
            except Exception as e:
                add_log(f"⚠️ Telegram Cloud Sync Hatası: {str(e)}")

    def push_to_cloud(self, filename=None, key=None):
        """Schedules a debounced asynchronous upload to Telegram to prevent notification spamming."""
        with self.lock:
            if self.upload_timer is not None:
                try:
                    self.upload_timer.cancel()
                except Exception:
                    pass
            
            # Debounce: wait 15 seconds after the last activity before pushing, reducing spam
            self.upload_timer = threading.Timer(15.0, self._upload_worker)
            self.upload_timer.start()

    def _upload_worker(self):
        try:
            from config import load_app_settings
            settings = load_app_settings()
        except Exception:
            settings = {}
            
        token = os.getenv("TELEGRAM_TOKEN", settings.get("tg_token", ""))
        chat_id = os.getenv("TELEGRAM_DATA_CHAT_ID", settings.get("tg_data_chat_id", os.getenv("TELEGRAM_CHAT_ID", settings.get("tg_chat_id", ""))))
        
        # Upgrade/normalize old migrated group chat ID to the new supergroup ID
        if str(chat_id) == "-5183733793":
            chat_id = "-1003958108455"
            
        if not token or not chat_id:
            return
            
        with self.lock:
            self.upload_timer = None
            # Load local trades
            trades_data = []
            if os.path.exists(TRADE_FILE):
                try:
                    with open(TRADE_FILE, "r", encoding="utf-8") as f:
                        trades_data = json.load(f)
                except Exception: pass
                
            # Load local avoided
            avoided_data = []
            if os.path.exists(AVOIDED_FILE):
                try:
                    with open(AVOIDED_FILE, "r", encoding="utf-8") as f:
                        avoided_data = json.load(f)
                except Exception: pass
                
            # Load local memory
            memory_data = {}
            if os.path.exists(MEMORY_FILE):
                try:
                    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                        memory_data = json.load(f)
                except Exception: pass
                
            backup_data = {
                "trades": trades_data,
                "avoided": avoided_data,
                "memory": memory_data
            }
            
            backup_file = "db_backup.json"
            try:
                # Save to a temporary single JSON file
                with open(backup_file, "w", encoding="utf-8") as f:
                    json.dump(backup_data, f, indent=4, ensure_ascii=False)
                    
                # 1. Send Document to Telegram Chat
                url_send = f"https://api.telegram.org/bot{token}/sendDocument"
                with open(backup_file, "rb") as f:
                    res = requests.post(url_send, data={"chat_id": chat_id, "caption": "=== COIN PROJE DB BACKUP ==="}, files={"document": f}, timeout=10)
                
                send_res = res.json()
                if send_res.get("ok"):
                    message_id = send_res["result"]["message_id"]
                    
                    # 2. Unpin the currently pinned message (keeps chat clean)
                    url_unpin = f"https://api.telegram.org/bot{token}/unpinChatMessage"
                    requests.post(url_unpin, data={"chat_id": chat_id}, timeout=10)
                    
                    # 3. Pin the newly uploaded backup message
                    url_pin = f"https://api.telegram.org/bot{token}/pinChatMessage"
                    requests.post(url_pin, data={"chat_id": chat_id, "message_id": message_id, "disable_notification": True}, timeout=10)
                    
                    # Log success internally
                    # add_log(f"☁️ Telegram Cloud Sync: Yedekleme başarıyla yüklendi ve sabitlendi.")
            except Exception as e:
                add_log(f"⚠️ Telegram Cloud Sync push hatası: {str(e)}")
            finally:
                if os.path.exists(backup_file):
                    try:
                        os.remove(backup_file)
                    except Exception: pass

# Global instance initialization to trigger early sync at import time
db_manager = HybridDatabaseManager()
