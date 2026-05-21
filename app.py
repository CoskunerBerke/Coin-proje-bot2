"""
Kripto Bot Arka Plan & REST API Sunucusu (app.py)
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import json
import threading
import time
import gc
from bot_engine import run_engine
from config import SUPPORTED_COINS, load_app_settings, save_app_settings
from log_manager import add_log
from trade_executor import TradeExecutor
from db_manager import db_manager
from data_fetcher import DataFetcher
from technical_analysis import TechnicalAnalyzer
from sentiment_analysis import SentimentAnalyzer
from signal_generator import SignalGenerator

app = Flask(__name__)
CORS(app)  # CORS politikası engellemelerini tamamen önler

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



# ⚙️ Küresel Nesne Kullanımı (Tek Seferlik Yüklenir - Muazzam Bellek Tasarrufu!)
executor = TradeExecutor(simulation_mode=True)
fetcher = DataFetcher()
analyzer = TechnicalAnalyzer()
sentiment_analyzer = SentimentAnalyzer()
signal_gen = SignalGenerator()

# 🛡️ Güncelleme Korumalı Veri Sıfırlama (Aktif pozisyonlar ASLA silinmez!)
RESET_FLAG_FILE = ".data_reset_v3_done"
if not os.path.exists(RESET_FLAG_FILE):
    add_log("🛡️ GÜNCELLEME KORUMALI BAŞLANGIÇ: Aktif pozisyonlar korunarak eski veriler arşivleniyor...")
    
    import shutil
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Aktif pozisyonları koru, sadece kapalıları arşivle
    active_trades = []
    if os.path.exists("bot_trades.json"):
        try:
            with open("bot_trades.json", "r", encoding="utf-8") as f:
                all_trades = json.load(f)
            active_trades = [t for t in all_trades if t.get("durum") == "AÇIK"]
            closed_trades = [t for t in all_trades if t.get("durum") != "AÇIK"]
            
            if closed_trades:
                backup_name = f"bot_trades_archive_{timestamp}.json"
                with open(backup_name, "w", encoding="utf-8") as f:
                    json.dump(closed_trades, f, indent=4)
                add_log(f"  📦 {len(closed_trades)} kapalı işlem arşivlendi: {backup_name}")
            
            if active_trades:
                add_log(f"  🛡️ {len(active_trades)} aktif pozisyon korundu!")
        except Exception as e:
            add_log(f"  ⚠️ Trade koruma hatası: {e}")
    
    # Avoided trades arşivle (bunlar güvenle arşivlenebilir)
    for fname in ["bot_avoided_trades.json"]:
        if os.path.exists(fname):
            try:
                backup_name = f"{fname.replace('.json', '')}_archive_{timestamp}.json"
                shutil.copy2(fname, backup_name)
                add_log(f"  📦 Arşivlendi: {fname} → {backup_name}")
            except Exception as e:
                add_log(f"  ⚠️ Arşivleme hatası ({fname}): {e}")
    
    # Aktif pozisyonlarla başla (coin_trade_memory.json ve counterfactual_data.json ASLA sıfırlanmaz!)
    with open("bot_trades.json", "w", encoding="utf-8") as f:
        json.dump(active_trades, f, indent=4)
    with open("bot_avoided_trades.json", "w", encoding="utf-8") as f:
        json.dump([], f)
    
    with open(RESET_FLAG_FILE, "w") as f:
        f.write(f"Reset completed at {timestamp}\nActive trades preserved: {len(active_trades)}\n")
    
    add_log(f"✅ Güncelleme korumalı başlangıç tamamlandı. {len(active_trades)} aktif pozisyon korundu.")

# 🧹 Her İstek Sonrası Çöpleri Temizle (OOM Koruması)
@app.after_request
def after_request(response):
    gc.collect()
    return response

def track_git_diff():
    try:
        import subprocess
        import re
        
        # Get current hash
        try:
            current_hash = subprocess.check_output("git rev-parse --short HEAD", shell=True).decode("utf-8").strip()
        except:
            return
            
        history_file = "git_commit_diffs.json"
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except:
                pass
                
        if any(h.get("commit_hash") == current_hash for h in history):
            return
            
        # Sığ clone (shallow clone) veya ilk commit kontrolü
        has_parent = False
        try:
            subprocess.check_output("git rev-parse --verify HEAD~1", stderr=subprocess.DEVNULL, shell=True)
            has_parent = True
        except:
            pass
            
        if not has_parent:
            new_entry = {
                "commit_hash": current_hash,
                "previous_hash": None,
                "stat": "İlk commit veya sığ clone (Render)",
                "insertions": 0,
                "deletions": 0,
                "total_lines": 0,
                "percentage_difference": 0.0,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            history.insert(0, new_entry)
            history = history[:50]
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4)
            return
            
        prev_hash = subprocess.check_output("git rev-parse --short HEAD~1", shell=True).decode("utf-8").strip()
        res = subprocess.check_output("git diff --shortstat HEAD~1 HEAD", shell=True).decode("utf-8").strip()
        
        total_lines = 0
        files_res = subprocess.check_output("git ls-files", shell=True).decode("utf-8").split("\n")
        for f in files_res:
            if f.endswith(".py") or f.endswith(".js") or f.endswith(".html") or f.endswith(".css"):
                if os.path.exists(f):
                    try:
                        with open(f, "r", encoding="utf-8") as file:
                            total_lines += len(file.readlines())
                    except:
                        pass
                        
        insertions = 0
        deletions = 0
        ins_match = re.search(r"(\d+) insertion", res)
        del_match = re.search(r"(\d+) deletion", res)
        if ins_match:
            insertions = int(ins_match.group(1))
        if del_match:
            deletions = int(del_match.group(1))
            
        changes = insertions + deletions
        pct = (changes / total_lines) * 100 if total_lines > 0 else 0.0
        
        new_entry = {
            "commit_hash": current_hash,
            "previous_hash": prev_hash,
            "stat": res,
            "insertions": insertions,
            "deletions": deletions,
            "total_lines": total_lines,
            "percentage_difference": round(pct, 2),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        history.insert(0, new_entry)
        history = history[:50]
        
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
            
        add_log(f"📈 Git Commit Takip Edildi: {current_hash} (Önceki: {prev_hash}) -> Değişim: %{pct:.2f} ({res})")
    except Exception as e:
        add_log(f"⚠️ Git commit fark takibi hatası: {str(e)}")

# 🤖 24/7 Arka Plan Bot Motorunu Başlat
def start_bot_thread():
    for t in threading.enumerate():
        if t.name == "BotEngineThread":
            add_log("⚠️ Bot motoru zaten çalışıyor, yeniden başlatılmadı.")
            return
    add_log("🚀 REST API: Arka plan BotEngineThread başlatılıyor...")
    thread = threading.Thread(target=run_engine, name="BotEngineThread", daemon=True)
    thread.start()

# Git takibini çalıştır ve botu başlat
track_git_diff()
start_bot_thread()

@app.route("/")
def index():
    bot_status = "active" if any(t.name == "BotEngineThread" for t in threading.enumerate()) else "inactive"
    return jsonify({
        "status": "healthy",
        "service": "kripto-analiz-botu-backend",
        "bot_engine": bot_status,
        "supported_coins": list(SUPPORTED_COINS.keys())
    })

@app.route("/api/git-diffs", methods=["GET"])
def get_git_diffs():
    if os.path.exists("git_commit_diffs.json"):
        try:
            with open("git_commit_diffs.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return jsonify(data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify([])

@app.route("/api/opportunities", methods=["GET"])
def get_opportunities():
    if os.path.exists("latest_opportunities.json"):
        try:
            with open("latest_opportunities.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return jsonify(sanitize_nan(data))
        except Exception as e:
            return jsonify({"error": f"Fırsatlar okunamadı: {str(e)}"}), 500
    return jsonify([])

last_sync_time = 0
sync_lock = threading.Lock()

def sync_db_async():
    """Triggers db_manager.sync_from_cloud() asynchronously inside a rate-limited background thread."""
    global last_sync_time
    now = time.time()
    if now - last_sync_time > 20:  # Allow cloud pull at most once every 20 seconds
        with sync_lock:
            if now - last_sync_time > 20:
                last_sync_time = now
                threading.Thread(target=db_manager.sync_from_cloud, daemon=True).start()

@app.route("/api/trades", methods=["GET"])
def get_trades():
    sync_db_async()
    if os.path.exists("bot_trades.json"):
        try:
            with open("bot_trades.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return jsonify(sanitize_nan(data))
        except Exception as e:
            return jsonify({"error": f"İşlem geçmişi okunamadı: {str(e)}"}), 500
    return jsonify([])

@app.route("/api/avoided", methods=["GET"])
def get_avoided_trades():
    sync_db_async()
    if os.path.exists("bot_avoided_trades.json"):
        try:
            with open("bot_avoided_trades.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return jsonify(sanitize_nan(data))
        except Exception as e:
            return jsonify({"error": f"Kaçınılan işlemler okunamadı: {str(e)}"}), 500
    return jsonify([])

@app.route("/api/memory", methods=["GET"])
def get_trade_memory():
    """Coin trade hafıza verisini döndürür — bot'un öğrenme geçmişi."""
    if os.path.exists("coin_trade_memory.json"):
        try:
            with open("coin_trade_memory.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                # İstatistik özeti ekle
                stats = {}
                total_trades = 0
                total_wins = 0
                total_pnl = 0.0
                for coin, trades in data.items():
                    count = len(trades)
                    wins = len([t for t in trades if t.get("outcome", 0) == 1])
                    pnl = sum(t.get("pnl_usdt", 0) for t in trades)
                    win_rate = (wins / count * 100) if count > 0 else 0
                    total_trades += count
                    total_wins += wins
                    total_pnl += pnl
                    stats[coin] = {"count": count, "wins": wins, "win_rate": round(win_rate, 1), "pnl": round(pnl, 2)}
                
                overall_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
                return jsonify(sanitize_nan({
                    "memory": data,
                    "stats": stats,
                    "overall": {
                        "total_trades": total_trades,
                        "total_wins": total_wins,
                        "win_rate": round(overall_wr, 1),
                        "total_pnl": round(total_pnl, 2)
                    }
                }))
        except Exception as e:
            return jsonify({"error": f"Hafıza verisi okunamadı: {str(e)}"}), 500
    return jsonify({"memory": {}, "stats": {}, "overall": {"total_trades": 0, "total_wins": 0, "win_rate": 0, "total_pnl": 0}})

@app.route("/api/memory-report", methods=["POST"])
def send_memory_report_telegram():
    """Hafıza raporunu Telegram'a gönderir."""
    try:
        settings = load_app_settings()
        token = os.getenv("TELEGRAM_TOKEN", settings.get("tg_token", ""))
        chat_id = os.getenv("TELEGRAM_CHAT_ID", settings.get("tg_chat_id", ""))
        if not token or not chat_id:
            return jsonify({"success": False, "message": "Telegram ayarları eksik."}), 400
        
        from telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier(token=token, chat_id=chat_id)
        
        memory_data = {}
        if os.path.exists("coin_trade_memory.json"):
            with open("coin_trade_memory.json", "r", encoding="utf-8") as f:
                memory_data = json.load(f)
        
        balance = executor.get_balance()
        success, msg = notifier.send_trade_memory_report(memory_data, balance)
        return jsonify({"success": success, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/spot-portfolio", methods=["GET"])
def get_spot_portfolio():
    if os.path.exists("bot_spot_portfolio.json"):
        try:
            with open("bot_spot_portfolio.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return jsonify(sanitize_nan(data))
        except Exception as e:
            return jsonify({"error": f"Spot portföyü okunamadı: {str(e)}"}), 500
    return jsonify([])

@app.route("/api/settings", methods=["GET", "POST"])
def manage_settings():
    if request.method == "POST":
        try:
            data = request.json
            if not data:
                return jsonify({"status": "error", "message": "Boş veri gönderildi"}), 400
            save_app_settings(data)
            return jsonify({"status": "success", "settings": data})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        settings = load_app_settings()
        # Render env vars override empty settings for Telegram
        env_token = os.getenv("TELEGRAM_TOKEN", "")
        env_chat = os.getenv("TELEGRAM_CHAT_ID", "")
        env_data_chat = os.getenv("TELEGRAM_DATA_CHAT_ID", "")
        if env_token and not settings.get("tg_token"):
            settings["tg_token"] = env_token
            settings["tg_active"] = True
        if env_chat and not settings.get("tg_chat_id"):
            settings["tg_chat_id"] = env_chat
        if env_data_chat and not settings.get("tg_data_chat_id"):
            settings["tg_data_chat_id"] = env_data_chat
        
        # 🔒 SABİT DEĞERLER: Frontend her zaman doğru göstersin
        settings["bot_active"] = True
        settings["sim_mode"] = True
        settings["leverage"] = 3
        
        return jsonify(settings)

@app.route("/api/logs", methods=["GET"])
def get_logs():
    if os.path.exists("bot_logs.txt"):
        try:
            with open("bot_logs.txt", "r", encoding="utf-8") as f:
                lines = f.readlines()
                # Son 100 log satırını ham liste olarak gönder
                return jsonify([line.strip() for line in lines])
        except Exception as e:
            return jsonify({"error": f"Loglar okunamadı: {str(e)}"}), 500
    return jsonify([])

@app.route("/api/balance", methods=["GET"])
def get_balance():
    try:
        settings = load_app_settings()
        sim_mode = settings.get("sim_mode", True)
        executor.simulation_mode = sim_mode
        return jsonify({"balance": executor.get_balance()})
    except Exception as e:
        return jsonify({"balance": 1000.0, "error": str(e)})

@app.route("/api/telegram-test", methods=["POST"])
def telegram_test():
    try:
        data = request.json
        token = data.get("tg_token")
        chat_id = data.get("tg_chat_id")
        if token and chat_id:
            from telegram_notifier import TelegramNotifier
            notifier = TelegramNotifier(token=token, chat_id=chat_id)
            success, msg = notifier.send_message("<b>🤖 TEST MESAJI:</b> Botunuz başarıyla bağlandı! İşlemler buradan bildirilecek.")
            return jsonify({"success": success, "message": msg})
        return jsonify({"success": False, "message": "Token ve Chat ID eksik."}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/close-trade/<trade_id>", methods=["POST"])
def close_trade_manually(trade_id):
    try:
        trades = executor.get_trade_history()
        found = False
        for t in trades:
            if t.get("id") == trade_id and t.get("durum") == "AÇIK":
                # Fetch latest price
                try:
                    ticker = fetcher.fetch_ticker(t["coin"])
                    current_price = ticker["last"]
                except:
                    current_price = t.get("guncel_fiyat", t["giris_fiyati"])
                    
                t["durum"] = "KAPALI"
                t["cikis_fiyati"] = current_price
                t["kapanis_tarihi"] = time.strftime("%Y-%m-%d %H:%M:%S")
                t["exit_reason"] = "MANUEL_KAPATMA (Kullanıcı Talebi)"
                
                # Re-calculate final PNL
                leverage = t.get("kaldirac", 1)
                entry_price = t["giris_fiyati"]
                if t["yon"] == "LONG":
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                else:
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100
                    
                commission_rate = 0.0004
                # Account for partial exits if any
                if t.get("tp2_hit", False):
                    remaining_usdt = t["miktar_usdt"] * 0.25
                    remaining_pnl = (((pnl_pct * leverage) / 100) * remaining_usdt) - (remaining_usdt * commission_rate)
                    t["pnl_usdt"] = round(t.get("tp1_pnl_usdt", 0) + t.get("tp2_pnl_usdt", 0) + remaining_pnl, 2)
                    t["pnl_yuzde"] = round((t["pnl_usdt"] / t["miktar_usdt"]) * 100, 2)
                elif t.get("tp1_hit", False):
                    remaining_usdt = t["miktar_usdt"] * 0.50
                    remaining_pnl = (((pnl_pct * leverage) / 100) * remaining_usdt) - (remaining_usdt * commission_rate)
                    t["pnl_usdt"] = round(t.get("tp1_pnl_usdt", 0) + remaining_pnl, 2)
                    t["pnl_yuzde"] = round((t["pnl_usdt"] / t["miktar_usdt"]) * 100, 2)
                else:
                    t["pnl_yuzde"] = round((pnl_pct * leverage) - (commission_rate * 2 * 100), 2)
                    t["pnl_usdt"] = round((((pnl_pct * leverage) / 100) * t["miktar_usdt"]) - (t["miktar_usdt"] * commission_rate * 2), 2)
                    
                executor.save_trade_history(trades)
                found = True
                
                # Send Telegram alert if notifier is configured
                try:
                    if executor.notifier:
                        executor.notifier.send_trade_alert(t, is_open=False, balance=executor.get_balance())
                except:
                    pass
                    
                add_log(f"🚪 MANUEL KAPATMA: {t['coin']} pozisyonu kullanıcı tarafından kapatıldı (PnL: %{t['pnl_yuzde']})")
                break
                
        if found:
            return jsonify({"status": "success", "message": f"İşlem {trade_id} başarıyla manuel kapatıldı."})
        return jsonify({"status": "error", "message": "Açık işlem bulunamadı"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/danger-reset-db", methods=["POST"])
def danger_reset_db():
    try:
        import requests
        from scratch.archive_and_reset_data import archive_and_reset
        archive_and_reset()
        
        # Clear in-memory executor database list
        executor.trades = []
        executor.save_trade_history([])
        
        # Unpin from Telegram if applicable
        try:
            from config import load_app_settings
            settings = load_app_settings()
            token = os.getenv("TELEGRAM_TOKEN", settings.get("tg_token", ""))
            chat_id = os.getenv("TELEGRAM_DATA_CHAT_ID", settings.get("tg_data_chat_id", os.getenv("TELEGRAM_CHAT_ID", settings.get("tg_chat_id", ""))))
            if str(chat_id) == "-5183733793":
                chat_id = "-1003958108455"
            if token and chat_id:
                url_unpin = f"https://api.telegram.org/bot{token}/unpinChatMessage"
                requests.post(url_unpin, data={"chat_id": chat_id}, timeout=5)
        except Exception as e:
            add_log(f"⚠️ unpin error during reset endpoint: {e}")
            
        add_log("🧹 DANGER RESET: Bütün işlemler silindi ve veritabanı boşaltıldı.")
        return jsonify({"status": "success", "message": "Database and in-memory trades reset successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/analysis/<coin>/<timeframe>", methods=["GET"])
def get_coin_analysis(coin, timeframe):
    try:
        clean_coin = coin.strip().upper()
        if clean_coin not in SUPPORTED_COINS:
            # Dynamically register custom coin in-memory to support on-the-fly analysis!
            SUPPORTED_COINS[clean_coin] = {
                "name": clean_coin,
                "coingecko_id": clean_coin.lower(),
                "symbol": f"{clean_coin}/USDT"
            }
            
        # Canlı fiyat ve market bilgilerini çek (Her zaman taze!)
        try:
            ticker = fetcher.fetch_ticker(coin)
            coin_info = fetcher.fetch_coin_info(coin)
        except Exception as ticker_err:
            add_log(f"⚠️ Market Bilgisi Çekilemedi ({coin}): {str(ticker_err)}")
            ticker = {"last": 0.0, "high": 0.0, "low": 0.0, "volume": 0.0, "quoteVolume": 0.0, "changePercent": 0.0}
            coin_info = {"market_cap_rank": 0, "market_cap": 0.0}

        from coin_intelligence import CoinIntelligenceManager
        intel = CoinIntelligenceManager()
        dna = intel.get_coin_dna(coin)
        weights = intel.get_adaptive_weights(coin)

        # 💾 RAM Dostu Önbellekten Oku (Varsa oradan al, yoksa canlı hesapla!)
        found_cached = False
        opp_data = {}
        if os.path.exists("latest_opportunities.json"):
            try:
                with open("latest_opportunities.json", "r", encoding="utf-8") as f:
                    all_opps = json.load(f)
                    for opp in all_opps:
                        if opp["coin"] == coin:
                            opp_data = opp
                            found_cached = True
                            break
            except Exception as cache_err:
                add_log(f"⚠️ Önbellek Okuma Hatası: {str(cache_err)}")

        if found_cached:
            res = {
                "status": "success",
                "ticker": ticker,
                "coin_info": coin_info,
                "ta_result": opp_data.get("ta_result"),
                "sentiment_result": opp_data.get("sentiment_result"),
                "signal": opp_data.get("signal"),
                "dna": dna,
                "weights": weights
            }
            return jsonify(sanitize_nan(res))

        # Eğer önbellek yoksa, CANLI olarak hemen hesapla ve dön! (Streamlit gibi dinamik)
        try:
            df = fetcher.fetch_ohlcv(coin, timeframe, limit=210)
            ta_result = analyzer.full_analysis(df)
            
            try:
                sentiment_result = sentiment_analyzer.full_analysis(coin, coin_info)
            except:
                sentiment_result = {
                    "overall": {"label": "Nötr", "emoji": "😐", "score": 50},
                    "news_sentiment": {"positive_pct": 50, "scored_news": []}
                }
                
            htf_map = {"1m": "15m", "5m": "1h", "15m": "1h", "1h": "4h", "4h": "1d", "1d": "1w"}
            htf = htf_map.get(timeframe, "4h")
            df_htf = fetcher.fetch_ohlcv(coin, htf, limit=210)
            mtf_data = analyzer.analyze_mtf_alignment(df, df_htf)
            
            signal = signal_gen.generate_signal(coin, ticker, ta_result, sentiment_result, timeframe, mtf_data)
            
            res = {
                "status": "success",
                "ticker": ticker,
                "coin_info": coin_info,
                "ta_result": ta_result,
                "sentiment_result": sentiment_result,
                "signal": signal,
                "dna": dna,
                "weights": weights
            }
            return jsonify(sanitize_nan(res))
        except Exception as live_err:
            add_log(f"⚠️ Canlı Analiz Hatası ({coin}): {str(live_err)}")
            return jsonify({
                "status": "waiting",
                "message": f"Piyasa verileri taranıyor: {str(live_err)}"
            })
    except Exception as e:
        return jsonify({"status": "error", "message": f"Analiz başarısız: {str(e)}"}), 500

@app.route("/api/counterfactuals", methods=["GET"])
def get_counterfactuals():
    """Counterfactual analiz verilerini döndürür — 'Ya girseydim / Ya çıkmasaydım' sonuçları."""
    try:
        from counterfactual_analyzer import CounterfactualAnalyzer
        cf = CounterfactualAnalyzer()
        stats = cf.get_summary_stats()
        return jsonify(sanitize_nan(stats))
    except Exception as e:
        return jsonify({"error": f"Counterfactual verisi okunamadı: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
