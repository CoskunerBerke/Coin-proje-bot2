"""
Kripto Coin Analiz Uygulaması — Yerel Tekil Sürüm (main.py)
"""

import streamlit as st
import time
import json
import os
import threading
from config import SUPPORTED_COINS, TIMEFRAMES, load_app_settings, save_app_settings, SIGNAL_WEIGHTS
from bot_engine import run_engine
from trade_executor import TradeExecutor
from db_manager import db_manager
from data_fetcher import DataFetcher
from technical_analysis import TechnicalAnalyzer
from sentiment_analysis import SentimentAnalyzer
from signal_generator import SignalGenerator
from log_manager import render_logs
from dashboard import (
    inject_custom_css, render_sidebar, render_main_signal,
    render_trade_plan, render_levels, render_ai_summary,
    render_disclaimer_simple, render_top_opportunities, render_bot_panel,
    render_sentiment_simple, render_news_simple, render_trade_history,
    render_learning_metrics, render_market_matrix, render_spot_portfolio,
    render_trade_memory_panel, render_counterfactual_panel
)

st.set_page_config(page_title="Net Analiz & Bot", page_icon="📈", layout="wide")

# 🤖 24/7 Arka Plan Bot Motorunu Başlat (Tamamen Yerel)
def start_bot_thread():
    for t in threading.enumerate():
        if t.name == "BotEngineThread":
            return
    thread = threading.Thread(target=run_engine, name="BotEngineThread", daemon=True)
    thread.start()

start_bot_thread()

# Yerel modülleri tek seferlik ilklendir (Bellek Tasarrufu için Caching)
@st.cache_resource
def get_bot_modules():
    return DataFetcher(), TechnicalAnalyzer(), SentimentAnalyzer(), TradeExecutor(simulation_mode=True), SignalGenerator()

fetcher, analyzer, sentiment_analyzer, executor, signal_gen = get_bot_modules()

def main():
    inject_custom_css()
    
    # 💾 Ayarları Yerel Dosyadan Yükle
    saved_settings = load_app_settings()
    
    # Yan Menüyü Yükle ve Ayarları Al
    bot_active, sim_mode, coin_key, timeframe, auto_refresh, refresh_interval, tg_active, tg_token, tg_chat_id, tg_data_chat_id, test_btn, leverage = render_sidebar(saved_settings)
    
    # 💾 Ayarları Güncelle (Değişiklik varsa yerel dosyaya kaydet)
    current_settings = {
        "bot_active": bot_active, "sim_mode": sim_mode, "tg_active": tg_active,
        "tg_token": tg_token, "tg_chat_id": tg_chat_id, "tg_data_chat_id": tg_data_chat_id, "coin_key": coin_key,
        "timeframe": timeframe, "auto_refresh": auto_refresh, "refresh_interval": refresh_interval,
        "leverage": leverage
    }
    if current_settings != saved_settings:
        save_app_settings(current_settings)
        saved_settings = current_settings

    # 🧪 Telegram Test Butonu (Doğrudan Yerel Çağrı)
    if test_btn:
        if tg_active and tg_token and tg_chat_id:
            with st.sidebar:
                from telegram_notifier import TelegramNotifier
                notifier = TelegramNotifier(token=tg_token, chat_id=tg_chat_id)
                success, msg = notifier.send_message("<b>🤖 TEST MESAJI:</b> Botunuz yerel arayüzden başarıyla bağlandı!")
                if success:
                    st.success("Test mesajı gönderildi!")
                else:
                    st.error(f"Hata! {msg}")
        else:
            st.sidebar.error("Telegram ayarları eksik!")

    # Yan Menü: Canlı Günlük (Loglar)
    with st.sidebar:
        st.markdown("---")
        render_logs()
        
        # Son Fırsatlar (Yerel Önbellekten)
        st.markdown("---")
        if os.path.exists("latest_opportunities.json"):
            try:
                with open("latest_opportunities.json", "r", encoding="utf-8") as f:
                    all_opps = json.load(f)
                    if all_opps and isinstance(all_opps, list):
                        render_top_opportunities(all_opps[:3])
            except:
                pass

    # Alım-Satım Yöneticisi (Küresel Önbellekli Nesne Ayarı)
    executor.simulation_mode = sim_mode
    balance = executor.get_balance()
    render_bot_panel(bot_active, sim_mode, balance)
    
    # İşlem Geçmişi (Yerel Dosyadan)
    trades = []
    if os.path.exists("bot_trades.json"):
        try:
            with open("bot_trades.json", "r", encoding="utf-8") as f:
                trades = json.load(f)
        except:
            pass
    render_trade_history(trades)
    
    # 🧬 Coine Özel Karar Odakları / Ağırlık Metrikleri & DNA Profili
    coin_weights = signal_gen.coin_intel.get_adaptive_weights(coin_key)
    render_learning_metrics(trades, weights=coin_weights, coin_key=coin_key)
    st.markdown("---")

    # Seçilen coin için CANLI TEKNİK VE DUYGU ANALİZİ (Tamamen Yerel ve Işık Hızında!)
    st.markdown(f"<h2 style='text-align: center;'>🪙 {coin_key} Analizi</h2>", unsafe_allow_html=True)
    
    with st.spinner("Piyasa verileri yerel olarak analiz ediliyor..."):
        try:
            # Canlı Verileri Çek
            ticker = fetcher.fetch_ticker(coin_key)
            df = fetcher.fetch_ohlcv(coin_key, timeframe)
            coin_info = fetcher.fetch_coin_info(coin_key)
            
            # Teknik ve Duygu Analizlerini Yap
            ta_result = analyzer.full_analysis(df)
            
            try:
                sentiment_result = sentiment_analyzer.full_analysis(coin_key, coin_info)
            except:
                sentiment_result = {
                    "overall": {"label": "Nötr", "emoji": "😐", "score": 50},
                    "news_sentiment": {"positive_pct": 50, "scored_news": []}
                }
                
            # MTF Analizi
            htf_map = {"1m": "15m", "5m": "1h", "15m": "1h", "1h": "4h", "4h": "1d", "1d": "1w"}
            htf = htf_map.get(timeframe, "4h")
            df_htf = fetcher.fetch_ohlcv(coin_key, htf)
            mtf_data = analyzer.analyze_mtf_alignment(df, df_htf)
            
            # Sinyal Üret
            signal = signal_gen.generate_signal(coin_key, ticker, ta_result, sentiment_result, timeframe, mtf_data)
            signal["leverage"] = leverage
            
            # Arayüzü Çiz
            render_main_signal(signal)
            render_trade_plan(signal)
            render_levels(ta_result["support_resistance"])
            
            c1, c2 = st.columns(2)
            with c1: render_sentiment_simple(sentiment_result)
            with c2: 
                st.markdown("<h4 style='margin-top:20px'>📰 Haber Akışı</h4>", unsafe_allow_html=True)
                render_news_simple(sentiment_result)
            
            render_ai_summary(signal)
            
        except Exception as analysis_err:
            st.warning(f"Analiz sırasında hata oluştu: {str(analysis_err)}")

    # 📊 Tüm Kripto Market Trend Matrisi (Yerel Önbellekten)
    all_opps = []
    if os.path.exists("latest_opportunities.json"):
        try:
            with open("latest_opportunities.json", "r", encoding="utf-8") as f:
                all_opps = json.load(f)
        except:
            pass
    render_market_matrix(all_opps)

    # 📈 Spot AI Yatırım Portföyü (Günlük Grafik Taraması)
    render_spot_portfolio()

    # 🧠 AI Trade Hafıza & Öğrenme Merkezi
    render_trade_memory_panel()

    # 🔮 Ya Girseydim / Ya Çıkmasaydım Analizi
    render_counterfactual_panel()

    render_disclaimer_simple()
    
    # 🧹 RAM Temizliği
    import gc
    gc.collect()
    
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    main()
