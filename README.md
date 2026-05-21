# 🪙 Kripto Coin Analiz Dashboard

Tamamen local çalışan, Python + Streamlit tabanlı kripto para analiz uygulaması.
Seçilen coin için teknik analiz, sentiment analizi ve kısa vadeli long/short yön tahmini üretir.

> ⚠️ **DİKKAT:** Bu uygulama yatırım tavsiyesi vermez. Sadece teknik ve veri tabanlı analiz üretir.
> Yatırım kararlarınızı kendi araştırmanıza dayanarak verin.

---

## 🚀 Özellikler

- **30+ Coin Desteği:** BTC, ETH, SOL, XRP, DOGE, AVAX ve daha fazlası
- **6 Zaman Dilimi:** 1m, 5m, 15m, 1h, 4h, 1d
- **İnteraktif Mum Grafikleri:** Plotly ile zoom, hover ve pan
- **Teknik İndikatörler:** RSI, MACD, EMA (9/21/50/200), Bollinger Bands, ADX, ATR, Stochastic RSI
- **Destek & Direnç:** Otomatik seviye tespiti + Pivot Points + Fibonacci
- **Mum Formasyonları:** Doji, Hammer, Engulfing ve daha fazlası
- **Sentiment Analizi:** CryptoPanic haberleri + VADER NLP + Fear & Greed Index
- **Long/Short Sinyal:** 8 faktörlü ağırlıklı skor sistemi
- **AI Yorum:** Türkçe doğal dilde analiz açıklaması
- **Özel Coin:** İstediğiniz sembolü girerek analiz yapabilirsiniz

---

## 📦 Kurulum

### 1. Python 3.9+ Gerekli

Python yüklü değilse: [python.org](https://www.python.org/downloads/)

### 2. Bağımlılıkları Yükleyin

```bash
cd COİN_PROJE
pip install -r requirements.txt
```

### 3. (Opsiyonel) API Key'leri Ayarlayın

`.env.example` dosyasını `.env` olarak kopyalayın:

```bash
copy .env.example .env
```

**CryptoPanic API Key (Ücretsiz):**
- [cryptopanic.com/developers/api](https://cryptopanic.com/developers/api/) adresinden ücretsiz alın
- `.env` dosyasına ekleyin: `CRYPTOPANIC_API_KEY=your_key_here`
- Bu key olmadan da uygulama çalışır, ancak haber bölümü sınırlı olur

### 4. Çalıştırın

```bash
streamlit run main.py
```

Tarayıcınızda otomatik olarak `http://localhost:8501` açılacaktır.

---

## 🖥️ Kullanım

1. **Sol menüden coin seçin** (BTC, ETH, SOL vb.)
2. **Zaman dilimi seçin** (1m, 5m, 15m, 1h, 4h, 1d)
3. **Özel coin** girmek istiyorsanız sembolünü yazın (ör: FLOKI)
4. Dashboard otomatik olarak güncellenir
5. **Oto güncelleme** açabilir ve süresini ayarlayabilirsiniz

---

## 📁 Proje Yapısı

```
COİN_PROJE/
├── main.py                  # Ana giriş noktası
├── dashboard.py             # Streamlit UI bileşenleri
├── charts.py                # Plotly grafik fonksiyonları
├── data_fetcher.py          # Binance + CoinGecko veri çekme
├── technical_analysis.py    # Teknik indikatörler + formasyonlar
├── sentiment_analysis.py    # Haber + duygu analizi
├── signal_generator.py      # Long/Short sinyal üretimi + AI yorum
├── config.py                # Sabitler ve ayarlar
├── requirements.txt         # Python bağımlılıkları
├── .env.example             # API key şablonu
└── README.md                # Bu dosya
```

---

## 🔧 Teknik Detaylar

### Veri Kaynakları
| Kaynak | Veri | API Key |
|--------|------|---------|
| Binance (ccxt) | OHLCV, Fiyat, Hacim | Gerekmiyor |
| CoinGecko | Market Cap, Topluluk | Gerekmiyor |
| CryptoPanic | Haberler | Opsiyonel (ücretsiz) |
| Alternative.me | Fear & Greed Index | Gerekmiyor |

### Sinyal Ağırlıkları
| Faktör | Ağırlık |
|--------|---------|
| EMA Kesişim | %20 |
| RSI | %15 |
| MACD | %15 |
| Sentiment | %15 |
| Bollinger Bands | %10 |
| Trend (ADX) | %10 |
| Hacim | %10 |
| Mum Formasyon | %5 |

---

## ⚠️ Önemli Uyarılar

1. Bu uygulama **yatırım tavsiyesi değildir**
2. Kripto para piyasaları **son derece volatildir** ve yatırım riski içerir
3. Sinyaller **olasılık ve risk mantığıyla** üretilir, kesinlik iddiası taşımaz
4. "Kesin artacak" veya "kesin düşecek" gibi ifadeler kullanılmaz
5. Yatırım kararlarınızı **kendi araştırmanıza** dayanarak verin
6. Geçmiş performans gelecekteki sonuçların garantisi değildir
