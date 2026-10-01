import os
import re
from datetime import datetime, timezone, timedelta
import streamlit as st

LOG_FILE = "bot_logs.txt"

# 🔐 Telegram token'ı URL'nin içinde taşınır (https://api.telegram.org/bot<TOKEN>/...).
# requests bağlantı hataları bu URL'yi mesajına koyar; log ise herkese açık /api/logs'ta görünür.
_TG_URL_TOKEN_RE = re.compile(r"(bot)\d+(?::|%3[Aa])[A-Za-z0-9_-]+")
_TG_BARE_TOKEN_RE = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{30,}")
REDACTED = "<gizlendi>"


def redact_secrets(text):
    """Metindeki Telegram bot token'larını gizler (log ve hata mesajları için)."""
    text = str(text)
    env_token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if len(env_token) >= 8:
        text = text.replace(env_token, REDACTED)
    text = _TG_URL_TOKEN_RE.sub(r"\1" + REDACTED, text)
    return _TG_BARE_TOKEN_RE.sub(REDACTED, text)


def get_now_tr():
    return datetime.now(timezone(timedelta(hours=3)))

def add_log(message):
    """Yeni bir log mesajını bot_logs.txt dosyasına yazar ve son 100 satırı tutar."""
    message = redact_secrets(message)
    timestamp = get_now_tr().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {message}\n"
    
    # 💻 Terminale canlı yazdır (Sıfır arayüz kullanımı için)
    try:
        print(f"[{timestamp}] {message}", flush=True)
    except UnicodeEncodeError:
        try:
            import sys
            encoding = sys.stdout.encoding or 'utf-8'
            print(f"[{timestamp}] {message}".encode(encoding, errors='replace').decode(encoding), flush=True)
        except:
            pass
    
    existing_logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                existing_logs = f.readlines()
        except:
            pass
            
    existing_logs.append(full_msg)
    # Son 100 satırı koru
    existing_logs = existing_logs[-100:]
    
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.writelines(existing_logs)
    except:
        pass

def render_logs(api_logs=None):
    """Logları ekranda şık bir şekilde gösterir."""
    st.markdown("#### 📜 Bot İzleme Günlüğü")
    
    if api_logs is not None:
        lines = api_logs
    else:
        if not os.path.exists(LOG_FILE):
            st.info("Loglar bekleniyor...")
            return
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except:
            st.info("Loglar yükleniyor...")
            return
        
    if not lines:
        st.info("Henüz log bulunmuyor.")
        return
        
    # En yeni logları en üstte göstermek için listeyi ters çevirelim ve son 25 logu alalım
    recent_logs = [redact_secrets(line.strip()) for line in reversed(lines)][:25]
    log_text = "\n".join(recent_logs)
    
    st.text_area("Canlı Aktivite (Son 25 İşlem)", value=log_text, height=200, disabled=True)

