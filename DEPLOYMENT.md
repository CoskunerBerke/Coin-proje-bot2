# 🪙 Kripto Bot 24/7 Bulut Kurulum Rehberi (Render & UptimeRobot)

Bu rehber, Kripto Analiz ve Al-Sat Botu uygulamasını **Render.com** üzerinde tamamen **ücretsiz** bir şekilde barındırarak, tarayıcı veya bilgisayar kapalıyken bile **7/24 aktif** tutma ve **UptimeRobot** yardımıyla sunucuyu uyutmadan sürekli yapay zeka eğitimini sürdürme adımlarını içerir.

---

## 🚀 1. Adım: Kodları GitHub'a Yükleyin

Uygulamayı Render'a bağlamak için öncelikle kodlarımızı GitHub'a (güvenlik için **Private / Gizli** bir repo olarak) yüklemeniz gerekir.

1. **GitHub Hesabı Oluşturun:** Eğer yoksa [github.com](https://github.com/) adresinden ücretsiz bir hesap açın.
2. **Yeni Repo Oluşturun:** Sağ üstteki `+` işaretine tıklayıp **New repository** deyin.
   - Repository name: `coin-proje`
   - **ÖNEMLİ:** Gizlilik ayarını mutlaka **Private** seçin! (API anahtarları ve stratejilerinizin güvenliği için).
   - *Create repository* butonuna tıklayın.
3. **Kodları Push Edin (Yükleyin):** Local terminalinizde (projenin içinde):
   ```bash
   git init
   git add .
   git commit -m "feat: 24/7 cloud support architecture"
   git branch -M main
   git remote add origin https://github.com/KULLANICI_ADINIZ/coin-proje.git
   git push -u origin main
   ```

---

## 🛠️ 2. Adım: Render.com Üzerinde Web Service Oluşturun

Render, projelerinizi doğrudan GitHub'dan çekip barındıran harika bir bulut platformudur.

1. **Giriş Yapın:** [render.com](https://render.com/) adresine gidin ve **GitHub ile Giriş Yap (Sign in with GitHub)** butonuna tıklayın.
2. **Yeni Hizmet Ekleyin:** Kontrol panelinde sağ üstteki **New +** butonuna tıklayın ve **Web Service** seçeneğini seçin.
3. **Reponuzu Bağlayın:** Listeden az önce oluşturduğunuz `coin-proje` reponuzu bulun ve yanındaki **Connect** butonuna tıklayın.
4. **Yapılandırma Bilgilerini Girin:**
   - **Name:** `kripto-analiz-botu`
   - **Region:** `Frankfurt (EU)` veya size en yakın konum.
   - **Branch:** `main`
   - **Runtime:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `streamlit run main.py --server.port $PORT --server.address 0.0.0.0` (Dosyalardaki `Procfile` sayesinde bunu otomatik de algılayabilir).
   - **Instance Type:** `Free` (Ücretsiz plan).

5. **API Anahtarlarını (Çevre Değişkenleri) Ekleyin:**
   Sayfanın altındaki **Advanced** butonuna tıklayın ve **Add Environment Variable** diyerek aşağıdaki anahtarları girin. Bu işlem `.env` dosyasındaki değerleri buluta güvenle aktarır:
   
   | Key | Value (Değerleriniz) |
   |-----|-----|
   | `BINANCE_API_KEY` | Binance Spot/Futures API Keyiniz |
   | `BINANCE_SECRET_KEY` | Binance API Secret Keyiniz |
   | `CRYPTOPANIC_API_KEY` | CryptoPanic API Keyiniz (Haberler için) |
   | `TELEGRAM_TOKEN` | Telegram bot belirteciniz (Örn: `123456:ABC...`) |
   | `TELEGRAM_CHAT_ID` | Telegram chat/grup ID'niz (Örn: `987654321`) |

6. **Dağıtımı Başlatın:** En alttaki **Create Web Service** butonuna tıklayın. Render botu kurup çalıştıracaktır. Kurulum tamamlandığında size üstte `https://kripto-analiz-botu.onrender.com` benzeri canlı bir web adresi verecektir. Bu adresi kopyalayın!

---

## ⏰ 3. Adım: UptimeRobot ile 7/24 Kesintisiz Çalışma (Sihirli Yöntem)

Render'ın ücretsiz planları, 15 dakika boyunca hiç ziyaretçi (istek) almazsa sunucuyu "uyku moduna (spin down)" alır. Sunucu uyursa arka plan botumuz çalışmayı durdurur. Bunu engellemek için **UptimeRobot** kullanarak sunucuyu asla uyutmayacağız!

1. **UptimeRobot'a Kaydolun:** [uptimerobot.com](https://uptimerobot.com/) adresine gidin ve tamamen ücretsiz bir hesap oluşturun.
2. **Yeni Monitör Ekleyin:** Kontrol panelinde sol üstteki **+ Add New Monitor** butonuna tıklayın.
3. **Monitör Ayarlarını Yapın:**
   - **Monitor Type:** `HTTPS` seçin.
   - **Friendly Name:** `Kripto Bot Uyanık Tutucu`
   - **URL (or IP):** Render'dan kopyaladığınız canlı site adresini yapıştırın (Örn: `https://kripto-analiz-botu.onrender.com`).
   - **Monitoring Interval:** `Every 5 minutes` (Her 5 dakikada bir) seçin.
4. **Oluşturun:** Sağ alttaki **Create Monitor** butonuna tıklayın.

### 🎉 Sonuç:
UptimeRobot, sitenize her 5 dakikada bir gizlice "tık" atarak Render sunucusunun **hiç uyumamasını** sağlar. Böylece:
* Sunucunuz **7 gün 24 saat kesintisiz** çalışır.
* Arka plan bot motorunuz (`bot_engine.py`) piyasayı aralıksız tarar ve sinyalleri yakalar.
* Yapay zeka (`update_weights_from_history`) her biten işlemden sonra **öğrenmeye devam eder**.
* Telegram bildirimleriniz anında telefonunuza düşer!
* Ve tüm bunlar için **$0 (sıfır dolar)** ödersiniz!
