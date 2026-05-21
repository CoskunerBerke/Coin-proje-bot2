"""
Kripto Coin Analiz Uygulaması — Sade & Modern Dashboard UI (TAM VERSİYON)
"""

import streamlit as st
from datetime import datetime
from config import SUPPORTED_COINS, TIMEFRAMES, DISCLAIMER, BINANCE_API_KEY, BINANCE_SECRET_KEY


def inject_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    .stApp { background-color: #FFFFFF !important; color: #1E293B !important; }
    * { font-family: 'Inter', sans-serif !important; }
    h1, h2, h3, h4, h5, p { color: #1E293B !important; }
    [data-testid="stSidebar"] { background-color: #F8FAFC !important; border-right: 1px solid #E2E8F0; }
    .signal-container { background: #FFFFFF; border-radius: 20px; padding: 30px; text-align: center; border: 2px solid #F1F5F9; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
    .action-card { background: #F8FAFC; border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #E2E8F0; }
    .level-box { background: #F1F5F9; border-radius: 12px; padding: 15px; margin-bottom: 10px; border: 1px solid #E2E8F0; }
    .ai-box { background: #F1F5F9; border-radius: 12px; padding: 20px; color: #334155 !important; border-left: 5px solid #3B82F6; font-size: 14px; margin-top: 15px; }
    .bot-panel { background: #FFFBEB; border: 2px solid #F59E0B; border-radius: 15px; padding: 20px; margin-bottom: 20px; }
    .ai-learning-active {
        height: 12px;
        width: 12px;
        background-color: #10B981;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        box-shadow: 0 0 8px #10B981;
        animation: pulse 1.5s infinite;
        vertical-align: middle;
    }
    .ai-learning-inactive {
        height: 12px;
        width: 12px;
        background-color: #94A3B8;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        vertical-align: middle;
    }
    @keyframes pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    header, footer, #MainMenu { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)

def render_sidebar(defaults={}):
    with st.sidebar:
        st.markdown("<h3 style='margin-bottom:20px'>🤖 BOT KONTROL</h3>", unsafe_allow_html=True)
        bot_active = st.toggle("OTOMATİK BOTU AKTİF ET", value=defaults.get("bot_active", False))
        sim_mode = st.toggle("SİMÜLASYON MODU (TEST)", value=defaults.get("sim_mode", True))
        leverage = st.slider("💰 İşlem Kaldıracı (Leverage):", 1, 20, defaults.get("leverage", 1), help="Kâr ve zararı bu oranda katlar.")
        
        st.markdown("---")
        st.markdown("### 📱 Telegram Bildirim")
        tg_active = st.toggle("Telegram Bildirimleri", value=defaults.get("tg_active", False))
        tg_token = st.text_input("Bot Token:", value=defaults.get("tg_token", ""), type="password", help="BotFather'dan aldığınız token")
        tg_chat_id = st.text_input("Chat ID (İşlemler):", value=defaults.get("tg_chat_id", ""), help="İşlem bildirimlerinin gönderileceği kanal/grup ID'si")
        tg_data_chat_id = st.text_input("Yedek Veri Chat ID (JSON):", value=defaults.get("tg_data_chat_id", ""), help="Veritabanı yedeklerinin gönderileceği kanal/grup ID'si")
        test_btn = st.button("🔔 TEST MESAJI GÖNDER")
        
        st.markdown("---")
        coin_key = st.selectbox("Analiz Edilen Coin:", options=list(SUPPORTED_COINS.keys()), index=list(SUPPORTED_COINS.keys()).index(defaults.get("coin_key", "BTC")) if defaults.get("coin_key") in SUPPORTED_COINS else 0)
        timeframe = st.selectbox("Zaman Dilimi:", options=list(TIMEFRAMES.keys()), index=list(TIMEFRAMES.keys()).index(defaults.get("timeframe", "1h")) if defaults.get("timeframe") in TIMEFRAMES else 1)
        auto_refresh = st.checkbox("Oto Güncelle", value=defaults.get("auto_refresh", True))
        refresh_interval = st.slider("Saniye:", 10, 300, defaults.get("refresh_interval", 30))
        return bot_active, sim_mode, coin_key, timeframe, auto_refresh, refresh_interval, tg_active, tg_token, tg_chat_id, tg_data_chat_id, test_btn, leverage

def render_bot_panel(bot_active, sim_mode, balance):
    status = "AKTİF" if bot_active else "KAPALI"
    mode_text = "TEST MODU" if sim_mode else "GERÇEK İŞLEM"
    bg_color = "#FEF3C7" if bot_active else "#FFFBEB"
    border_color = "#F59E0B" if bot_active else "#FCD34D"
    
    # AI Işık Göstergesi
    if bot_active:
        ai_html = "<span class='ai-learning-active'></span><span style='font-size:12px; font-weight:600; color:#3B82F6;'>AI Veri Topluyor...</span>"
    else:
        ai_html = "<span class='ai-learning-inactive'></span><span style='font-size:12px; font-weight:600; color:#64748B;'>AI Beklemede</span>"

    st.markdown(f"""
    <div class="bot-panel" style="background-color: {bg_color}; border-color: {border_color}; display: flex; justify-content: space-between; align-items: center;">
        <div>
            <div style="font-size:14px; color:#92400E; font-weight:700">🤖 BOT DURUMU: {status} | {mode_text}</div>
            <div style="font-size:24px; font-weight:800; color:#1E293B">Bakiye: ${balance:,.2f}</div>
        </div>
        <div>
            {ai_html}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if not sim_mode and (not BINANCE_API_KEY or not BINANCE_SECRET_KEY):
        st.warning("⚠️ Binance API anahtarları eksik! Lütfen anahtarlarınızı `.env` dosyasına kaydedin. Sanal bakiye gösterilmektedir.")

def render_trade_history(trades):
    if not trades:
        st.info("Henüz bot tarafından yapılmış bir işlem bulunmuyor.")
        return
    
    st.markdown("#### 📊 İşlem Takibi & Kâr-Zarar (PNL)")
    
    # 🗂️ Açık pozisyonları her zaman en üste al, kapalıları tarihe göre (yeni->eski) sırala
    sorted_trades = sorted(
        trades,
        key=lambda x: (0 if x.get("durum") == "AÇIK" else 1, -int(x.get("id", 0)) if str(x.get("id", "")).isdigit() else 0)
    )
    
    html = "<div style='max-height: 300px; overflow-y: auto; border: 1px solid #E2E8F0; border-radius: 8px;'>"
    html += "<table style='width:100%; text-align:left; border-collapse: collapse; font-size:13px;'>"
    html += "<tr style='border-bottom: 2px solid #E2E8F0; color:#64748B; position: sticky; top: 0; background-color: white;'><th>Durum</th><th>Coin</th><th>Yön</th><th>Aşama</th><th>Miktar ($ / %)</th><th>Giriş</th><th>Güncel</th><th>PNL (%)</th><th>Kâr/Zarar</th></tr>"
    
    for t in sorted_trades: # Artık kaydırılabilir olduğu için tüm işlemleri gösteriyoruz
        durum = t.get("durum", "ESKİ")
        durum_color = "#3B82F6" if durum == "AÇIK" else "#64748B"
        
        pnl_yuzde = t.get("pnl_yuzde", 0)
        pnl_usdt = t.get("pnl_usdt", 0)
        pnl_color = "#10B981" if pnl_yuzde > 0 else "#EF4444" if pnl_yuzde < 0 else "#64748B"
        
        curr_price = t.get("guncel_fiyat", t.get("giris_fiyati", 0))
        
        miktar_usdt = t.get("miktar_usdt", 0.0)
        miktar_yuzde = t.get("miktar_yuzde", 0.0)
        if not miktar_yuzde and miktar_usdt > 0:
            giris_bakiye = t.get("giris_bakiye", 1000.0)
            miktar_yuzde = (miktar_usdt / (giris_bakiye if giris_bakiye > 0 else 1000.0)) * 100
        
        miktar_label = f"${miktar_usdt:,.2f} (%{miktar_yuzde:.1f})" if miktar_usdt > 0 else "-"
        
        # Determine the trade state badges
        state_dict = t.get("trade_state", {})
        if not isinstance(state_dict, dict):
            state_dict = {}
        
        tp1_hit = state_dict.get("tp1_hit", t.get("tp1_hit", False))
        be_active = state_dict.get("breakeven_active", t.get("break_even_activated", False))
        trail_active = state_dict.get("trailing_active", t.get("trailing_active", False))
        trend_ext = state_dict.get("trend_extension_mode", False)
        
        state_badges = []
        if trend_ext:
            state_badges.append("<span style='background:#8B5CF6; color:white; padding:2px 5px; border-radius:3px; font-size:10px; margin-right:3px; font-weight:bold;'>🚀 Trend Uzama</span>")
        if trail_active:
            state_badges.append("<span style='background:#EC4899; color:white; padding:2px 5px; border-radius:3px; font-size:10px; margin-right:3px; font-weight:bold;'>📈 Trailing</span>")
        if be_active:
            state_badges.append("<span style='background:#10B981; color:white; padding:2px 5px; border-radius:3px; font-size:10px; margin-right:3px; font-weight:bold;'>🛡️ BreakEven</span>")
        if tp1_hit:
            state_badges.append("<span style='background:#F59E0B; color:white; padding:2px 5px; border-radius:3px; font-size:10px; margin-right:3px; font-weight:bold;'>🎯 TP1</span>")
            
        if not state_badges:
            if t.get("durum") == "AÇIK":
                state_text = "<span style='color:#94A3B8; font-size:11px; font-style:italic;'>Giriş Takibi</span>"
            else:
                exit_reason = t.get("exit_reason", "")
                if "SL" in str(exit_reason):
                    state_text = "<span style='background:#EF4444; color:white; padding:2px 5px; border-radius:3px; font-size:10px; font-weight:bold;'>🔴 Stop Out</span>"
                elif "TP" in str(exit_reason):
                    state_text = "<span style='background:#10B981; color:white; padding:2px 5px; border-radius:3px; font-size:10px; font-weight:bold;'>🟢 Take Profit</span>"
                elif "TRAILING" in str(exit_reason):
                    state_text = "<span style='background:#EC4899; color:white; padding:2px 5px; border-radius:3px; font-size:10px; font-weight:bold;'>📈 Trailing Exit</span>"
                elif "WEAK_MOMENTUM" in str(exit_reason):
                    state_text = "<span style='background:#3B82F6; color:white; padding:2px 5px; border-radius:3px; font-size:10px; font-weight:bold;'>🔵 Momentum Exit</span>"
                elif "ZAMAN" in str(exit_reason):
                    state_text = "<span style='background:#64748B; color:white; padding:2px 5px; border-radius:3px; font-size:10px; font-weight:bold;'>⏱️ Time Exit</span>"
                else:
                    state_text = f"<span style='color:#64748B; font-size:11px;'>{exit_reason if exit_reason else '-'}</span>"
        else:
            state_text = "".join(state_badges)
            
        html += f"<tr style='border-bottom: 1px solid #F1F5F9;'>"
        html += f"<td style='padding:10px 8px;'><span style='background:{durum_color}; color:white; padding:2px 6px; border-radius:4px; font-size:10px;'>{durum}</span></td>"
        html += f"<td><strong>{t.get('coin', '-')}</strong></td>"
        html += f"<td>{t.get('yon', '-')}</td>"
        html += f"<td>{state_text}</td>"
        html += f"<td style='font-weight:bold; color:#475569;'>{miktar_label}</td>"
        html += f"<td>${t.get('giris_fiyati', 0):,.4f}</td>"
        html += f"<td>${curr_price:,.4f}</td>"
        html += f"<td style='color:{pnl_color}; font-weight:bold;'>{pnl_yuzde:+,.2f}%</td>"
        html += f"<td style='color:{pnl_color}; font-weight:bold;'>${pnl_usdt:+,.2f}</td>"
        html += "</tr>"
    html += "</table></div>"
    st.markdown(html, unsafe_allow_html=True)

def render_learning_metrics(trades, weights=None, coin_key=None):
    # Sadece ML verisi olan kapalı işlemleri analiz et
    ml_trades = [t for t in trades if t.get("durum") == "KAPALI" and "ml_data" in t]
    
    # 🧬 Phase 4: Bireysel Coin DNA Profili Gösterimi
    if coin_key:
        try:
            from coin_intelligence import CoinIntelligenceManager
            coin_intel = CoinIntelligenceManager()
            dna = coin_intel.get_coin_dna(coin_key)
            
            st.markdown(f"<h4 style='margin-top:20px;'>🧬 {coin_key} DNA Davranış Profili</h4>", unsafe_allow_html=True)
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                st.markdown(f"<div style='text-align:center; padding:10px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px;'>"
                            f"<div style='font-size:10px; color:#64748B;'>TREND GÜCÜ</div>"
                            f"<div style='font-size:16px; font-weight:bold; color:#3B82F6;'>%{dna['trendiness']*100:.0f}</div>"
                            f"</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div style='text-align:center; padding:10px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px;'>"
                            f"<div style='font-size:10px; color:#64748B;'>FAKEOUT RİSKİ</div>"
                            f"<div style='font-size:16px; font-weight:bold; color:#EF4444;'>%{dna['fakeout_prob']*100:.0f}</div>"
                            f"</div>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div style='text-align:center; padding:10px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px;'>"
                            f"<div style='font-size:10px; color:#64748B;'>ORTALAMAYA DÖNÜŞ</div>"
                            f"<div style='font-size:16px; font-weight:bold; color:#10B981;'>%{dna['mean_reversion']*100:.0f}</div>"
                            f"</div>", unsafe_allow_html=True)
            with c4:
                st.markdown(f"<div style='text-align:center; padding:10px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px;'>"
                            f"<div style='font-size:10px; color:#64748B;'>KIRILIM GÜVENİ</div>"
                            f"<div style='font-size:16px; font-weight:bold; color:#6366F1;'>%{dna['breakout_reliability']*100:.0f}</div>"
                            f"</div>", unsafe_allow_html=True)
            with c5:
                st.markdown(f"<div style='text-align:center; padding:10px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px;'>"
                            f"<div style='font-size:10px; color:#64748B;'>VOLATİLİTE SKORU</div>"
                            f"<div style='font-size:16px; font-weight:bold; color:#F59E0B;'>%{dna['volatility']*100:.0f}</div>"
                            f"</div>", unsafe_allow_html=True)
        except Exception as e:
            pass

    # Ağırlıkları göster
    if weights:
        st.markdown("<h4 style='margin-top:20px;'>⚖️ AI Coine Özel Karar Ağırlıkları (Canlı)</h4>", unsafe_allow_html=True)
        cols = st.columns(len(weights))
        for i, (k, v) in enumerate(weights.items()):
            with cols[i]:
                color = "#10B981" if v > 0.20 else "#64748B"
                st.markdown(f"<div style='text-align:center; padding:10px; background:#F8FAFC; border-radius:8px;'>"
                            f"<div style='font-size:12px; color:#475569;'>{k.upper()}</div>"
                            f"<div style='font-size:18px; font-weight:bold; color:{color};'>%{v*100:.1f}</div>"
                            f"</div>", unsafe_allow_html=True)

    # 🛡️ Avoided Loss (Kaçınılan Zarar) Hesabı
    import os
    import json
    avoided_file = "bot_avoided_trades.json"
    avoided_loss_usdt = 0.0
    avoided_count = 0
    missed_count = 0
    missed_profit_usdt = 0.0
    if os.path.exists(avoided_file):
        try:
            with open(avoided_file, "r", encoding="utf-8") as f:
                avoided_trades = json.load(f)
                avoided_wins = [t for t in avoided_trades if t.get("durum") == "BAŞARIYLA_KAÇINILDI"]
                avoided_count = len(avoided_wins)
                avoided_loss_usdt = sum(abs(float(t.get("pnl_usdt", t.get("risked_usdt", 0.0)))) for t in avoided_wins)
                
                missed_trades = [t for t in avoided_trades if t.get("durum") == "KAÇIRILAN_FIRSAT"]
                missed_count = len(missed_trades)
                missed_profit_usdt = sum(float(t.get("pnl_usdt", 0.0)) for t in missed_trades)
        except: pass
                            
    st.markdown("<h4 style='margin-top:20px;'>🧠 AI Öğrenme Başarısı</h4>", unsafe_allow_html=True)
    
    col_a, col_b = st.columns(2)
    with col_a:
        if len(ml_trades) >= 2:
            wins = [t for t in ml_trades if t.get("pnl_usdt", 0) > 0]
            win_rate = (len(wins) / len(ml_trades)) * 100
            st.markdown(f"📈 **AI Kazanma Oranı:** `%{win_rate:.1f}` ({len(ml_trades)} İşlem)")
        else:
            st.markdown("📈 **AI Kazanma Oranı:** `Yetersiz Veri` (Min 2 Kapalı İşlem)")
            
    with col_b:
        if avoided_count > 0:
            st.markdown(f"🛡️ **AI Önlenen Zarar (ALI):** `+${avoided_loss_usdt:,.2f}` (`{avoided_count}` Başarı)")
            if missed_count > 0:
                st.caption(f"⚠️ *Kaçırılan Potansiyel Kâr:* `${missed_profit_usdt:,.2f}` ({missed_count} Fırsat)")
        else:
            st.markdown("🛡️ **AI Önlenen Zarar (ALI):** `$0.00` (Fırsat Aranıyor)")

    if len(ml_trades) >= 2 and len([t for t in ml_trades if t.get("pnl_usdt", 0) > 0]) > 0:
        wins = [t for t in ml_trades if t.get("pnl_usdt", 0) > 0]
        avg_sent = sum(t["ml_data"].get("sentiment", 0) for t in wins) / len(wins)
        st.caption(f"💡 *AI Çıkarımı:* Kâr getiren işlemlerde ortalama Duygu (Sentiment) faktörü {avg_sent:+.2f} seviyesinde.")

    # 📊 Long ve Short İşlemleri Karşılaştırma
    closed_trades = [t for t in trades if t.get("durum") == "KAPALI"]
    long_trades = [t for t in closed_trades if t.get("yon") in ["LONG", "BUY"]]
    short_trades = [t for t in closed_trades if t.get("yon") in ["SHORT", "SELL"]]
    
    long_wins = len([t for t in long_trades if t.get("pnl_usdt", 0) > 0])
    short_wins = len([t for t in short_trades if t.get("pnl_usdt", 0) > 0])
    
    long_pnl_pct = sum(t.get("pnl_yuzde", 0.0) for t in long_trades)
    long_pnl_usdt = sum(t.get("pnl_usdt", 0.0) for t in long_trades)
    
    short_pnl_pct = sum(t.get("pnl_yuzde", 0.0) for t in short_trades)
    short_pnl_usdt = sum(t.get("pnl_usdt", 0.0) for t in short_trades)
    
    st.markdown("<h4 style='margin-top:20px;'>📊 Yönsel İşlem Başarısı (Long vs Short)</h4>", unsafe_allow_html=True)
    c_long, c_short = st.columns(2)
    with c_long:
        st.markdown(f"""
        <div style='padding:15px; background-color:#F0FDF4; border:1px solid #BBF7D0; border-radius:12px;'>
            <div style='font-size:11px; color:#15803d; font-weight:700;'>LONG İŞLEMLER</div>
            <div style='font-size:18px; font-weight:800; color:#15803d;'>{long_pnl_pct:+.2f}% (${long_pnl_usdt:+.2f})</div>
            <div style='font-size:11px; color:#16a34a;'>{len(long_trades)} İşlem ({long_wins} Kazanç)</div>
        </div>
        """, unsafe_allow_html=True)
    with c_short:
        st.markdown(f"""
        <div style='padding:15px; background-color:#FEF2F2; border:1px solid #FECACA; border-radius:12px;'>
            <div style='font-size:11px; color:#b91c1c; font-weight:700;'>SHORT İŞLEMLER</div>
            <div style='font-size:18px; font-weight:800; color:#b91c1c;'>{short_pnl_pct:+.2f}% (${short_pnl_usdt:+.2f})</div>
            <div style='font-size:11px; color:#dc2626;'>{len(short_trades)} İşlem ({short_wins} Kazanç)</div>
        </div>
        """, unsafe_allow_html=True)

def render_top_opportunities(top_opps):
    st.sidebar.markdown("### 🔥 Fırsatlar & AI Kararı")
    for opp in top_opps[:8]: # Son taranan tüm coinleri göster (max 8)
        color = "#10B981" if opp.get("direction") == "LONG" else "#EF4444" if opp.get("direction") == "SHORT" else "#64748B"
        is_tradable = opp.get("is_tradable", False)
        
        if is_tradable:
            badge_html = f"<span style='background:#10B981; color:white; padding:2px 5px; border-radius:4px; font-size:9px; font-weight:700;'>UYGUN</span>"
            right_html = f"<div style='float:right; color:{color} !important; font-weight:800; font-size:13px;'>%{opp['confidence']:.0f} (EV: {opp.get('ev', 0):+.2f})</div>"
        else:
            badge_html = f"<span style='background:#E2E8F0; color:#475569; padding:2px 5px; border-radius:4px; font-size:9px; font-weight:700;'>ELENDİ</span>"
            reason = opp.get("reject_reason", "Kriter Uyumsuz")
            right_html = f"<div style='font-size:11px; color:#94A3B8; text-align:right; font-style:italic;'>{reason}</div>"
            
        st.sidebar.markdown(f"""
        <div style="padding:12px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:10px; margin-bottom:8px">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <strong style="color:#0F172A !important; font-size:13px;">{opp['coin']} ({opp.get('direction', 'NÖTR')})</strong>
                {badge_html}
            </div>
            {right_html}
        </div>
        """, unsafe_allow_html=True)

def render_main_signal(signal):
    quantum_score = signal.get("quantum_score", 0.0)
    color = "#10B981" if signal["direction"] == "LONG" else "#EF4444" if signal["direction"] == "SHORT" else "#F59E0B"
    regime = signal.get("regime", "ANALİZ EDİLİYOR")
    is_tradable = signal.get("is_tradable", False)
    
    status_html = ""
    if signal["direction"] != "NEUTRAL":
        if is_tradable:
            status_html = f"<div style='color:#10B981; font-weight:700; font-size:13px; margin-top:12px; border-top:1px solid #F1F5F9; padding-top:10px;'>✅ İŞLEM UYGUN (Kuantum Skor: {quantum_score:.1f})</div>"
        else:
            status_html = f"<div style='color:#EF4444; font-weight:700; font-size:12px; margin-top:12px; border-top:1px solid #F1F5F9; padding-top:10px;'>❌ ELENDİ: {signal.get('reject_reason', 'Kriter Uyumsuzluğu')}</div>"

    st.markdown(f"""<div class="signal-container">
<div style="color:#64748B; font-weight:600; font-size:12px; margin-bottom:5px">PİYASA REJİMİ: {regime}</div>
<div style="color:#64748B; font-weight:600">SİNYAL YÖNÜ</div>
<div style="font-size:36px; font-weight:800; color:{color}; margin-top:5px; margin-bottom:15px;">{signal['direction_label']}</div>
<div style="display:flex; justify-content:space-around; margin-top:15px; border-top:1px solid #F1F5F9; padding-top:15px;">
<div>
<div style="font-size:11px; color:#64748B; font-weight:600;">KAZANMA OLASILIĞI</div>
<div style="font-size:20px; font-weight:800; color:#0F172A !important">%{signal['confidence']}</div>
</div>
<div>
<div style="font-size:11px; color:#64748B; font-weight:600;">BEKLENEN DEĞER (EV)</div>
<div style="font-size:20px; font-weight:800; color:{color}">{signal.get('ev', 0.0):+,.3f}</div>
</div>
</div>
<div style="display:flex; justify-content:space-around; margin-top:15px; border-top:1px solid #F1F5F9; padding-top:15px;">
<div>
<div style="font-size:11px; color:#64748B; font-weight:600;">BAYES BELİRSİZLİĞİ</div>
<div style="font-size:16px; font-weight:800; color:#475569">{signal.get('uncertainty_label', 'ORTA')}</div>
</div>
<div>
<div style="font-size:11px; color:#64748B; font-weight:600;">MONTE CARLO SAĞKALIM</div>
<div style="font-size:16px; font-weight:800; color:#10B981">%{signal.get('mc_survival_probability', 0.85)*100:.1f}</div>
</div>
</div>
<div style="display:flex; justify-content:space-around; margin-top:15px; border-top:1px solid #F1F5F9; padding-top:15px;">
<div>
<div style="font-size:11px; color:#64748B; font-weight:600;">KUANTUM BENZERLİK</div>
<div style="font-size:16px; font-weight:800; color:#3B82F6">%{signal.get('similarity_score', 1.0)*100:.1f}</div>
</div>
<div>
<div style="font-size:11px; color:#64748B; font-weight:600;">DNA FAKEOUT OLASILIĞI</div>
<div style="font-size:16px; font-weight:800; color:#EF4444">%{signal.get('fakeout_prob', 0.20)*100:.0f}</div>
</div>
<div>
<div style="font-size:11px; color:#64748B; font-weight:600;">EDGE ÇARPANI</div>
<div style="font-size:16px; font-weight:800; color:#10B981">{signal.get('edge_multiplier', 1.0):.2f}x</div>
</div>
</div>
{status_html}
</div>""", unsafe_allow_html=True)

def render_trade_plan(signal):
    st.markdown("#### 🎯 Al-Sat Seviyeleri")
    c1, c2, c3, c4 = st.columns(4)
    tp_list = signal.get("take_profit", [0.0])
    tp1 = tp_list[0]
    tp2 = tp_list[1] if len(tp_list) > 1 else tp1 * 1.05
    with c1: st.markdown(f'<div class="action-card"><div class="action-label">GİRİŞ</div><div class="action-price">${signal["entry"]:,.4f}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="action-card"><div class="action-label" style="color:#EF4444">STOP</div><div class="action-price" style="color:#EF4444">${signal["stop_loss"]:,.4f}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="action-card"><div class="action-label" style="color:#10B981">KAR AL 1</div><div class="action-price" style="color:#10B981">${tp1:,.4f}</div></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="action-card"><div class="action-label" style="color:#10B981">KAR AL 2</div><div class="action-price" style="color:#10B981">${tp2:,.4f}</div></div>', unsafe_allow_html=True)

def render_levels(sr):
    st.markdown("#### 📐 Kritik Seviyeler")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="level-box"><div style="font-weight:700">🛡️ Destekler</div>', unsafe_allow_html=True)
        for s in sr.get("supports", []): st.markdown(f"• ${s:,.4f}")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="level-box"><div style="font-weight:700">🚧 Dirençler</div>', unsafe_allow_html=True)
        for r in sr.get("resistances", []): st.markdown(f"• ${r:,.4f}")
        st.markdown('</div>', unsafe_allow_html=True)

def render_ai_summary(signal):
    st.markdown(f'<div class="ai-box"><strong>🤖 AI ANALİZİ:</strong> {signal["ai_comment"]}</div>', unsafe_allow_html=True)

def render_sentiment_simple(sent):
    st.markdown("<h4 style='margin-top:20px'>💬 Duygu & Haber</h4>", unsafe_allow_html=True)
    st.markdown(f"Piyasa Duygusu: **{sent['overall']['label']}** {sent['overall']['emoji']}")
    st.progress(sent['overall']['score']/100)

def render_news_simple(sent):
    for item in sent['news_sentiment']['scored_news'][:3]:
        st.markdown(f"<div style='font-size:12px; margin-bottom:5px;'>• {item['title']}</div>", unsafe_allow_html=True)

def render_disclaimer_simple():
    st.markdown(f'<div style="text-align:center; color:#94A3B8; font-size:11px; margin-top:30px">{DISCLAIMER}</div>', unsafe_allow_html=True)

def render_market_matrix(opportunities):
    st.markdown("<h3 style='margin-top:40px; text-align:center; color:#0F172A !important;'>📊 Tüm Kripto Market Trend Matrisi</h3>", unsafe_allow_html=True)
    if not opportunities:
        st.info("ℹ️ Market tarama verisi bekleniyor... Bot arka planda ilk taramasını tamamladığında bu alan otomatik olarak güncellenecektir.")
        return
        
    cols = st.columns(3)
    for idx, opp in enumerate(opportunities[:9]): # En popüler 9 coini göster
        col = cols[idx % 3]
        direction = opp.get("direction", "NEUTRAL")
        color = "#10B981" if direction == "LONG" else "#EF4444" if direction == "SHORT" else "#64748B"
        bg_card = "#F8FAFC"
        border_color = "#E2E8F0"
        
        # Sinyal Yönü Simgesi
        dir_icon = "📈 BOĞA (LONG)" if direction == "LONG" else "📉 AYI (SHORT)" if direction == "SHORT" else "↔️ YATAY (NÖTR)"
        
        status_badge = "UYGUN" if opp.get("is_tradable", False) else "ELENDİ"
        badge_bg = "#10B981" if opp.get("is_tradable", False) else "#94A3B8"
        
        col.markdown(f"""
        <div style="background:{bg_card}; border:1px solid {border_color}; border-radius:15px; padding:15px; margin-bottom:15px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <strong style="font-size:15px; color:#0F172A !important;">🪙 {opp['coin']}</strong>
                <span style="background:{badge_bg}; color:white; padding:2px 6px; border-radius:6px; font-size:10px; font-weight:700;">{status_badge}</span>
            </div>
            <div style="margin-top:10px; font-size:14px; font-weight:700; color:{color};">{dir_icon}</div>
            <div style="margin-top:8px; display:flex; justify-content:space-between; font-size:12px; color:#64748B;">
                <span>Güven: <b>%{opp['confidence']:.0f}</b></span>
                <span>EV: <b style="color:{color};">{opp.get('ev', 0.0):+,.2f}</b></span>
            </div>
            {"<div style='margin-top:6px; font-size:11px; color:#EF4444; font-style:italic;'>Elendi: " + opp.get('reject_reason') + "</div>" if not opp.get('is_tradable') else ""}
        </div>
        """, unsafe_allow_html=True)

def render_spot_portfolio():
    st.markdown("<h3 style='margin-top:40px; text-align:center; color:#0F172A !important;'>📈 Spot AI Yatırım Portföyü</h3>", unsafe_allow_html=True)
    import os
    import json
    spot_file = "bot_spot_portfolio.json"
    if not os.path.exists(spot_file):
        st.info("ℹ&nbsp; Spot AI Portföy verisi bekleniyor... Bot arka planda ilk günlük taramasını tamamladığında bu alan güncellenecektir.")
        return
        
    try:
        with open(spot_file, "r", encoding="utf-8") as f:
            spots = json.load(f)
            
        if not spots:
            st.info("ℹ&nbsp; Şu an için Spot AI koşullarına uygun coin bulunmuyor.")
            return
            
        cols = st.columns(3)
        for idx, spot in enumerate(spots[:9]):
            col = cols[idx % 3]
            col.markdown(f"""
            <div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:15px; padding:15px; margin-bottom:15px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong style="font-size:15px; color:#15803D !important;">🪙 {spot['coin']}</strong>
                    <span style="background:#10B981; color:white; padding:2px 6px; border-radius:6px; font-size:10px; font-weight:700;">SPOT SKOR: {spot['puan']}</span>
                </div>
                <div style="margin-top:10px; font-size:12px; color:#15803D;">🌱 <b>Giriş:</b> {spot['giris_bolgesi']}</div>
                <div style="margin-top:4px; font-size:12px; color:#1E293B;">🎯 <b>Hedefler:</b> TP1: ${spot['hedefler'][0]:,.4f} | TP2: ${spot['hedefler'][1]:,.4f}</div>
                <div style="margin-top:4px; font-size:11px; color:#64748B;">🛡️ <b>Stop Loss:</b> {spot['stop_loss']}</div>
                <div style="margin-top:6px; font-size:10px; color:#475569; font-style:italic;">💡 {", ".join(spot['gerekceler'][:2])}</div>
            </div>
            """, unsafe_allow_html=True)
    except Exception as spot_err:
        st.warning(f"Spot portföyü yüklenirken hata: {str(spot_err)}")

def render_trade_memory_panel():
    """🧠 AI Trade Hafıza Paneli — Bot'un öğrendiği desenleri ve kaçınma kurallarını gösterir."""
    st.markdown("<h3 style='margin-top:40px; text-align:center; color:#0F172A !important;'>🧠 AI Trade Hafıza & Öğrenme Merkezi</h3>", unsafe_allow_html=True)
    
    import os
    import json
    memory_file = "coin_trade_memory.json"
    if not os.path.exists(memory_file):
        st.info("ℹ️ Henüz trade hafızası oluşmadı. Bot ilk işlemlerini kapattığında bu alan güncellenecektir.")
        return
    
    try:
        with open(memory_file, "r", encoding="utf-8") as f:
            memory_data = json.load(f)
    except Exception as e:
        st.warning(f"Hafıza verisi yüklenemedi: {str(e)}")
        return
    
    if not memory_data:
        st.info("ℹ️ Trade hafızası boş.")
        return
    
    # --- Genel İstatistikler ---
    total_trades = 0
    total_wins = 0
    total_pnl = 0.0
    total_loss_pnl = 0.0
    total_win_pnl = 0.0
    coin_stats = []
    all_lessons = []
    
    for coin, trades in memory_data.items():
        if not trades:
            continue
        count = len(trades)
        wins = len([t for t in trades if t.get("outcome", 0) == 1])
        losses = count - wins
        pnl = sum(t.get("pnl_usdt", 0) for t in trades)
        win_pnl = sum(t.get("pnl_usdt", 0) for t in trades if t.get("outcome", 0) == 1)
        loss_pnl = sum(t.get("pnl_usdt", 0) for t in trades if t.get("outcome", 0) == 0)
        win_rate = (wins / count * 100) if count > 0 else 0
        
        total_trades += count
        total_wins += wins
        total_pnl += pnl
        total_win_pnl += win_pnl
        total_loss_pnl += loss_pnl
        coin_stats.append((coin, count, wins, losses, win_rate, pnl))
        
        for t in trades[-3:]:
            reason = t.get("exit_reason", "")
            if reason and len(reason) > 10:
                all_lessons.append({"coin": coin, "reason": reason, "outcome": t.get("outcome", 0), "regime": t.get("regime", "RANGE")})
    
    overall_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
    
    # Genel İstatistik Kartları
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div style='text-align:center; padding:15px; background:#F0FDF4; border:1px solid #BBF7D0; border-radius:12px;'>
            <div style='font-size:10px; color:#15803d; font-weight:700;'>TOPLAM İŞLEM</div>
            <div style='font-size:24px; font-weight:800; color:#15803d;'>{total_trades}</div>
            <div style='font-size:10px; color:#16a34a;'>{total_wins} Kazanç</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        wr_color = "#10B981" if overall_wr >= 50 else "#EF4444"
        st.markdown(f"""
        <div style='text-align:center; padding:15px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:12px;'>
            <div style='font-size:10px; color:#64748B; font-weight:700;'>KAZANMA ORANI</div>
            <div style='font-size:24px; font-weight:800; color:{wr_color};'>%{overall_wr:.1f}</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        pnl_color = "#10B981" if total_pnl >= 0 else "#EF4444"
        st.markdown(f"""
        <div style='text-align:center; padding:15px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:12px;'>
            <div style='font-size:10px; color:#64748B; font-weight:700;'>TOPLAM PNL</div>
            <div style='font-size:24px; font-weight:800; color:{pnl_color};'>${total_pnl:+.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        coins_learned = len(memory_data)
        st.markdown(f"""
        <div style='text-align:center; padding:15px; background:#EFF6FF; border:1px solid #BFDBFE; border-radius:12px;'>
            <div style='font-size:10px; color:#1d4ed8; font-weight:700;'>ÖĞRENİLEN COİN</div>
            <div style='font-size:24px; font-weight:800; color:#1d4ed8;'>{coins_learned}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # --- Coin Bazlı Detay Tablosu ---
    st.markdown("<h4 style='margin-top:20px;'>📊 Coin Bazlı Hafıza İstatistikleri</h4>", unsafe_allow_html=True)
    
    coin_stats_sorted = sorted(coin_stats, key=lambda x: x[5], reverse=True)
    
    html = "<div style='max-height:250px; overflow-y:auto; border:1px solid #E2E8F0; border-radius:8px;'>"
    html += "<table style='width:100%; text-align:left; border-collapse:collapse; font-size:13px;'>"
    html += "<tr style='border-bottom:2px solid #E2E8F0; color:#64748B; position:sticky; top:0; background-color:white;'>"
    html += "<th style='padding:8px;'>Coin</th><th>İşlem</th><th>Kazanç</th><th>Kayıp</th><th>Win Rate</th><th>PNL</th></tr>"
    
    for coin, count, wins, losses, wr, pnl in coin_stats_sorted:
        pnl_color = "#10B981" if pnl > 0 else "#EF4444" if pnl < 0 else "#64748B"
        wr_color = "#10B981" if wr >= 50 else "#EF4444"
        emoji = "🟢" if pnl > 0 else "🔴"
        html += f"<tr style='border-bottom:1px solid #F1F5F9;'>"
        html += f"<td style='padding:8px;'><strong>{emoji} {coin}</strong></td>"
        html += f"<td>{count}</td>"
        html += f"<td style='color:#10B981; font-weight:bold;'>{wins}</td>"
        html += f"<td style='color:#EF4444; font-weight:bold;'>{losses}</td>"
        html += f"<td style='color:{wr_color}; font-weight:bold;'>%{wr:.0f}</td>"
        html += f"<td style='color:{pnl_color}; font-weight:bold;'>${pnl:+.2f}</td>"
        html += "</tr>"
    html += "</table></div>"
    st.markdown(html, unsafe_allow_html=True)
    
    # --- Öğrenilen Dersler ve Hata Desenleri ---
    st.markdown("<h4 style='margin-top:20px;'>📝 Öğrenilen Dersler & Hata Desenleri</h4>", unsafe_allow_html=True)
    
    # Hata deseni kategorileri
    error_patterns = {
        "Direnç LONG": 0,
        "Destek SHORT": 0,
        "RSI Exhaustion": 0,
        "Düşük Hacim": 0,
        "EMA Yanlış": 0,
        "Trend Karşı": 0
    }
    
    for coin, trades in memory_data.items():
        for t in trades:
            reason = t.get("exit_reason", "").lower()
            if "direnç" in reason or "resistance" in reason:
                error_patterns["Direnç LONG"] += 1
            if "destek" in reason or "support" in reason:
                error_patterns["Destek SHORT"] += 1
            if "rsi" in reason or "exhaustion" in reason or "aşırı" in reason:
                error_patterns["RSI Exhaustion"] += 1
            if "hacim" in reason or "volume" in reason or "düşük" in reason:
                error_patterns["Düşük Hacim"] += 1
            if "ema" in reason:
                error_patterns["EMA Yanlış"] += 1
            if "trend" in reason and ("karşı" in reason or "bear" in reason):
                error_patterns["Trend Karşı"] += 1
    
    active_patterns = {k: v for k, v in error_patterns.items() if v > 0}
    
    if active_patterns:
        cols = st.columns(min(len(active_patterns), 3))
        for idx, (pattern, count) in enumerate(sorted(active_patterns.items(), key=lambda x: x[1], reverse=True)):
            col = cols[idx % min(len(active_patterns), 3)]
            icon_map = {
                "Direnç LONG": "🚧",
                "Destek SHORT": "🛡️",
                "RSI Exhaustion": "📈",
                "Düşük Hacim": "📉",
                "EMA Yanlış": "〰️",
                "Trend Karşı": "🔄"
            }
            icon = icon_map.get(pattern, "⚠️")
            col.markdown(f"""
            <div style='text-align:center; padding:12px; background:#FEF2F2; border:1px solid #FECACA; border-radius:10px; margin-bottom:8px;'>
                <div style='font-size:20px;'>{icon}</div>
                <div style='font-size:11px; color:#B91C1C; font-weight:700;'>{pattern}</div>
                <div style='font-size:18px; font-weight:800; color:#DC2626;'>{count}x</div>
                <div style='font-size:9px; color:#94A3B8;'>Tekrar eden hata</div>
            </div>
            """, unsafe_allow_html=True)
    
    # --- Son Öğrenme Notları ---
    if all_lessons:
        st.markdown("<h4 style='margin-top:15px;'>💡 Son Öğrenme Notları</h4>", unsafe_allow_html=True)
        for lesson in all_lessons[-6:]:
            emoji = "✅" if lesson["outcome"] == 1 else "❌"
            bg = "#F0FDF4" if lesson["outcome"] == 1 else "#FEF2F2"
            border = "#BBF7D0" if lesson["outcome"] == 1 else "#FECACA"
            reason_text = lesson["reason"][:120]
            st.markdown(f"""
            <div style='padding:8px 12px; background:{bg}; border:1px solid {border}; border-radius:8px; margin-bottom:5px; font-size:12px;'>
                {emoji} <strong>[{lesson['coin']}]</strong> <span style='color:#64748B;'>({lesson['regime']})</span> — {reason_text}
            </div>
            """, unsafe_allow_html=True)

def render_counterfactual_panel():
    """🔮 Counterfactual Analiz Paneli — 'Ya Girseydim / Ya Çıkmasaydım' sonuçları."""
    st.markdown("<h3 style='margin-top:40px; text-align:center; color:#0F172A !important;'>🔮 Ya Girseydim / Ya Çıkmasaydım — AI Analizi</h3>", unsafe_allow_html=True)
    
    import os
    import json

    # Doğrudan dosyadan oku
    cf_file = "counterfactual_data.json"
    lessons_file = "counterfactual_lessons.json"
    
    if not os.path.exists(cf_file) and not os.path.exists(lessons_file):
        st.info("ℹ️ Henüz counterfactual analiz verisi yok. Bot ilk işlemlerini kapattığında veya fırsatları elediğinde bu alan otomatik dolacaktır.")
        return
    
    try:
        from counterfactual_analyzer import CounterfactualAnalyzer
        cf = CounterfactualAnalyzer()
        stats = cf.get_summary_stats()
    except Exception as e:
        st.warning(f"Counterfactual verisi yüklenemedi: {str(e)}")
        return
    
    if stats["completed_scenarios"] == 0 and stats["active_scenarios"] == 0:
        st.info("ℹ️ Henüz counterfactual senaryosu oluşmadı. Bot çalıştıkça burada veriler göreceksiniz.")
        return
    
    # Özet kartları
    c1, c2, c3, c4 = st.columns(4)
    
    pe = stats.get("post_exit", {})
    me = stats.get("missed_entry", {})
    
    with c1:
        st.markdown(f"""
        <div style='text-align:center; padding:15px; background:#EFF6FF; border:1px solid #BFDBFE; border-radius:12px;'>
            <div style='font-size:10px; color:#1d4ed8; font-weight:700;'>AKTİF TAKİP</div>
            <div style='font-size:24px; font-weight:800; color:#1d4ed8;'>{stats['active_scenarios']}</div>
            <div style='font-size:10px; color:#3b82f6;'>Senaryo İzleniyor</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        exit_acc = pe.get("exit_accuracy_pct", 0)
        acc_color = "#10B981" if exit_acc >= 50 else "#EF4444"
        st.markdown(f"""
        <div style='text-align:center; padding:15px; background:#F0FDF4; border:1px solid #BBF7D0; border-radius:12px;'>
            <div style='font-size:10px; color:#15803d; font-weight:700;'>ÇIKIŞ DOĞRULUĞU</div>
            <div style='font-size:24px; font-weight:800; color:{acc_color};'>%{exit_acc:.0f}</div>
            <div style='font-size:10px; color:#16a34a;'>{pe.get("correct_exits", 0)} Doğru / {pe.get("early_exits", 0)} Erken</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        filter_acc = me.get("filter_accuracy_pct", 0)
        f_color = "#10B981" if filter_acc >= 50 else "#EF4444"
        st.markdown(f"""
        <div style='text-align:center; padding:15px; background:#FEF3C7; border:1px solid #FDE68A; border-radius:12px;'>
            <div style='font-size:10px; color:#92400e; font-weight:700;'>FİLTRE DOĞRULUĞU</div>
            <div style='font-size:24px; font-weight:800; color:{f_color};'>%{filter_acc:.0f}</div>
            <div style='font-size:10px; color:#b45309;'>{me.get("avoided_losses", 0)} Doğru / {me.get("missed_profits", 0)} Kaçırıldı</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div style='text-align:center; padding:15px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:12px;'>
            <div style='font-size:10px; color:#64748B; font-weight:700;'>TOPLAM DERS</div>
            <div style='font-size:24px; font-weight:800; color:#334155;'>{stats['total_lessons']}</div>
            <div style='font-size:10px; color:#94A3B8;'>AI Öğrenme Hafızası</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Detay bölümü: Çıkış ve Giriş analizi yan yana
    col_exit, col_entry = st.columns(2)
    
    with col_exit:
        st.markdown("""
        <div style='padding:15px; background:#FEFCE8; border:1px solid #FDE68A; border-radius:12px; margin-top:15px;'>
            <div style='font-size:13px; font-weight:700; color:#854D0E; margin-bottom:8px;'>🚪 Çıkış Analizi (Ya Çıkmasaydım?)</div>
        """, unsafe_allow_html=True)
        
        if pe.get("total", 0) > 0:
            st.markdown(f"""
                <div style='font-size:12px; color:#713F12; line-height:1.8;'>
                    ✅ Doğru Çıkış: <b>{pe['correct_exits']}</b><br>
                    ❌ Erken Çıkış: <b>{pe['early_exits']}</b> (Ort. kaçırılan: %{pe.get('avg_early_exit_missed_pct', 0):.1f})<br>
                    ➡️ Nötr: <b>{pe['neutral_exits']}</b>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='font-size:12px; color:#94A3B8;'>Henüz veri yok</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col_entry:
        st.markdown("""
        <div style='padding:15px; background:#EFF6FF; border:1px solid #BFDBFE; border-radius:12px; margin-top:15px;'>
            <div style='font-size:13px; font-weight:700; color:#1E40AF; margin-bottom:8px;'>🎯 Giriş Analizi (Ya Girseydim?)</div>
        """, unsafe_allow_html=True)
        
        if me.get("total", 0) > 0:
            st.markdown(f"""
                <div style='font-size:12px; color:#1E3A5F; line-height:1.8;'>
                    🛡️ Başarıyla Kaçınılan: <b>{me['avoided_losses']}</b> (Önlenen: ${me.get('total_avoided_loss_usdt', 0):,.2f})<br>
                    💰 Kaçırılan Kârlı: <b>{me['missed_profits']}</b> (Kaçırılan: ${me.get('total_missed_profit_usdt', 0):,.2f})<br>
                    ➡️ Nötr: <b>{me['neutral']}</b>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='font-size:12px; color:#94A3B8;'>Henüz veri yok</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Son Dersler
    recent_lessons = stats.get("recent_lessons", [])
    if recent_lessons:
        st.markdown("<h4 style='margin-top:20px;'>💡 Son Counterfactual Dersler</h4>", unsafe_allow_html=True)
        for lesson in reversed(recent_lessons):
            verdict = lesson.get("verdict", "")
            if verdict in ["DOGRU_CIKIS", "BASARIYLA_KACINILDI"]:
                emoji = "✅"
                bg = "#F0FDF4"
                border = "#BBF7D0"
            elif verdict in ["ERKEN_CIKIS", "KACIRILDI_KARLI"]:
                emoji = "❌"
                bg = "#FEF2F2"
                border = "#FECACA"
            else:
                emoji = "➡️"
                bg = "#F8FAFC"
                border = "#E2E8F0"
            
            lesson_text = lesson.get("lesson", "")[:140]
            st.markdown(f"""
            <div style='padding:8px 12px; background:{bg}; border:1px solid {border}; border-radius:8px; margin-bottom:5px; font-size:12px;'>
                {emoji} <strong>[{lesson.get('coin', '')}]</strong> <span style='color:#64748B;'>({lesson.get('type', '')})</span> — {lesson_text}
            </div>
            """, unsafe_allow_html=True)
