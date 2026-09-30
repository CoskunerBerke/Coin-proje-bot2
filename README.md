# coin-proje-bot2 — Crypto Signal & Simulation Bot (earlier iteration)

A Python crypto analysis bot that combines technical indicators, news sentiment and a small self-trained model to produce long/short signals, then manages **simulated** trades with a web control panel and Telegram alerts.

![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?logo=flask&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?logo=numpy&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-3F4F75?logo=plotly&logoColor=white)
![ccxt](https://img.shields.io/badge/ccxt-Binance-222222)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-06B6D4?logo=tailwindcss&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-alerts-26A5E4?logo=telegram&logoColor=white)
![Render](https://img.shields.io/badge/Render-backend-46E3B7?logo=render&logoColor=black)
![Vercel](https://img.shields.io/badge/Vercel-frontend-000000?logo=vercel&logoColor=white)

**Backend API (Render):** https://coin-proje-bot2.onrender.com — the default API address used by the control panel.

> **Status:** earlier iteration. This was one of my first trading-bot projects; the ideas were later rebuilt, with a much
> stricter paper-trading and measurement approach, in [trading2](https://github.com/CoskunerBerke/trading2).
> Simulation mode is the default. This project is not financial advice.

## Overview

The bot scans selected coins (currently BTC and SOL, configurable in `config.py`) on short timeframes, scores each setup, and opens virtual positions on a simulated 1,000 USDT balance. Every closed trade is fed back into a small learning step that re-weights the signal factors. It runs as a Flask backend with a background engine thread, a static HTML control panel, and an optional local Streamlit dashboard. This repository is the "BOT2_AGGRESSIVE" profile (lower confidence threshold, macro filter enabled).

## Features

- **Technical analysis** — RSI, Stochastic RSI, MACD, EMA 9/21/50/200, Bollinger Bands, ADX, ATR, support/resistance, pivot points and candle patterns.
- **Sentiment analysis** — news from CryptoPanic and RSS feeds, scored with VADER, plus the Fear & Greed index.
- **Weighted long/short signal** — eight factors (EMA crossover, RSI, MACD, sentiment, Bollinger, ADX trend, volume, candle pattern) with market-regime detection and multi-timeframe checks.
- **Self-adjusting weights** — a small logistic model (NumPy) is retrained from trade history (`update_weights_from_history`).
- **Simulated trade management** — position sizing by stop distance, leverage cap, partial take-profit, regime-aware trailing stops, daily loss limits.
- **Counterfactual analysis** — tracks skipped signals and closed trades to answer "what if I had entered / held?".
- **Coin memory and macro sentinel** — per-coin trade history profile; macro risk score from USD/TRY, BTC dominance, stablecoin flows and Fear & Greed.
- **Long-term spot scanner** — daily-chart checks (EMA breakouts, RSI oversold, accumulation patterns).
- **REST API + control panel** — trades, skipped trades, memory, logs, balance, settings and per-coin analysis; TradingView chart widget in the panel.
- **Telegram** — trade alerts and JSON backup of trade data to a Telegram chat.

## Tech stack

| Area | Tools |
|---|---|
| Backend | Python 3.10, Flask, Flask-CORS |
| Local dashboard | Streamlit, Plotly |
| Data & analysis | ccxt (Binance), CoinGecko (pycoingecko), pandas, NumPy, `ta`, vaderSentiment, feedparser, BeautifulSoup |
| Frontend | Single-page HTML, Tailwind CSS (CDN), Font Awesome, TradingView widget |
| Hosting | Render (`Procfile`), Vercel (`vercel.json`) |

## Project structure

```text
coin-proje-bot2/
├── app.py                    # Flask REST API + starts the background engine
├── bot_engine.py             # 24/7 scan → signal → trade loop
├── main.py, dashboard.py     # optional local Streamlit dashboard
├── data_fetcher.py           # Binance (ccxt) + CoinGecko data
├── technical_analysis.py     # indicators, levels, candle patterns
├── sentiment_analysis.py     # news + VADER sentiment
├── signal_generator.py       # weighted signal + learning step
├── trade_executor.py         # simulated positions, stops, take-profits
├── counterfactual_analyzer.py, coin_intelligence.py, macro_sentinel.py, spot_investor.py
├── db_manager.py             # JSON trade store + Telegram backup sync
├── telegram_notifier.py
├── frontend/index.html       # control panel (deployed on Vercel)
├── config.py                 # coins, timeframes, weights, risk settings
└── DEPLOYMENT.md             # Render + UptimeRobot guide (Turkish)
```

## Getting started

```bash
git clone https://github.com/CoskunerBerke/coin-proje-bot2.git
cd coin-proje-bot2
pip install -r requirements.txt
cp .env.example .env          # optional keys, see below

python app.py                 # API + bot engine on http://localhost:5000
# or the local dashboard:
streamlit run main.py         # http://localhost:8501
```

Open `frontend/index.html` in a browser; on localhost it talks to `http://localhost:5000`.

### Environment variables (names only)

`CRYPTOPANIC_API_KEY`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_DATA_CHAT_ID`, `BINANCE_API_KEY`, `BINANCE_SECRET_KEY` (only needed if simulation is turned off), `BACKEND_URL`, `PORT`.
All are optional; the bot runs in simulation mode without them.

## Deployment

- **Backend:** Render web service, started by the `Procfile` (`web: python app.py`), Python version in `runtime.txt`.
- **Frontend:** Vercel serves `frontend/index.html` as a static site (`vercel.json`).
- Step-by-step guide: [DEPLOYMENT.md](DEPLOYMENT.md).

## Disclaimer

Signals are probabilistic and produced for learning purposes. Crypto markets are highly volatile. This is not financial advice.

---

## Türkçe

**coin-proje-bot2**, teknik göstergeleri, haber duygu analizini ve kendi kendini güncelleyen küçük bir modeli birleştirerek long/short sinyali üreten ve **simülasyon** işlemlerini web paneli ve Telegram bildirimleriyle yöneten bir Python kripto botudur.

> **Durum:** eski sürüm. İlk trading bot projelerimden biridir; fikirler daha sonra çok daha sıkı bir kâğıt işlem ve ölçüm
> yaklaşımıyla [trading2](https://github.com/CoskunerBerke/trading2) projesinde yeniden yazıldı. Varsayılan mod simülasyondur.
> Yatırım tavsiyesi değildir.

### Genel bakış

Bot, seçili coinleri (şu an BTC ve SOL; `config.py` içinden değiştirilebilir) kısa zaman dilimlerinde tarar, her kurulumu puanlar ve 1.000 USDT'lik sanal bakiyeyle pozisyon açar. Kapanan her işlem, sinyal faktörlerinin ağırlıklarını yeniden hesaplayan öğrenme adımına geri beslenir. Flask backend + arka plan motoru, statik HTML kontrol paneli ve isteğe bağlı yerel Streamlit panelinden oluşur. Bu depo "BOT2_AGGRESSIVE" profilidir.

### Özellikler

- **Teknik analiz:** RSI, Stochastic RSI, MACD, EMA 9/21/50/200, Bollinger, ADX, ATR, destek/direnç, pivot, mum formasyonları.
- **Duygu analizi:** CryptoPanic ve RSS haberleri, VADER puanlaması, Korku & Açgözlülük endeksi.
- **Ağırlıklı long/short sinyali:** 8 faktör, piyasa rejimi tespiti ve çoklu zaman dilimi kontrolü.
- **Kendini ayarlayan ağırlıklar:** işlem geçmişinden yeniden eğitilen küçük lojistik model.
- **Simülasyon işlem yönetimi:** stop mesafesine göre boyut, kaldıraç sınırı, kademeli kâr alma, rejime duyarlı takip stopu, günlük zarar limiti.
- **Karşı-olgusal analiz:** "girseydim / tutsaydım ne olurdu?" sorusunu veriyle yanıtlar.
- **Coin hafızası, makro risk skoru ve uzun vadeli spot tarayıcı.**
- **REST API + kontrol paneli** ve **Telegram** bildirimleri / veri yedeği.

### Kurulum

```bash
git clone https://github.com/CoskunerBerke/coin-proje-bot2.git
cd coin-proje-bot2
pip install -r requirements.txt
cp .env.example .env          # isteğe bağlı anahtarlar
python app.py                 # API + bot motoru: http://localhost:5000
streamlit run main.py         # veya yerel panel: http://localhost:8501
```

Ortam değişkenleri isteğe bağlıdır; anahtar olmadan bot simülasyon modunda çalışır. Canlıya alma adımları (Render + Vercel) için [DEPLOYMENT.md](DEPLOYMENT.md) dosyasına bakın.

### Uyarı

Sinyaller olasılığa dayalıdır ve öğrenme amacıyla üretilmiştir. Kripto piyasaları çok oynaktır. Yatırım tavsiyesi değildir.

---

Built by [Berke Coşkuner](https://github.com/CoskunerBerke)
