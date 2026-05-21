# 🚨 ÖNEMLİ GELİŞTİRİCİ KURALLARI & VERİ KORUMA KILAVUZU

Bu dosya, bu depoda çalışan tüm yapay zeka asistanları ve geliştiriciler için **kesinlikle uyulması zorunlu** altın kuralları içerir.

---

## 💎 Altın Kurallar

### 1. ☁️ Kesinlikle Yerel (Local) Çalıştırma Yapmayın!
* Tüm bot motoru, simülasyon, veri toplama ve canlı sistemler **Render (Backend)** ve **Vercel (Frontend)** üzerinde çalışmaktadır.
* Geliştirici yerel bilgisayarda (local) bağımsız test veya simülasyon koşturmamalıdır.
* Yapılan her kod değişikliği, doğrudan GitHub deposuna gönderilmeli (`git push origin main`) ve buluttaki canlı sunucularda (Render & Vercel) otomatik derlenerek devreye sokulmalıdır.

### 2. 🗄️ İşlem Geçmişi Verilerini ASLA SİLMEYİN VEYA SIFIRLAMAYIN!
* `bot_trades.json` (işlem veri tabanı) ve `bot_avoided_trades.json` (engellenen işlemler) dosyalarındaki geçmiş veriler **ASLA yok edilmemeli, sıfırlanmamalı veya boşaltılmamalıdır.**
* Bir kod güncellemesi veya dosya yazma işlemi yapılacağı zaman:
  1. Dosyadaki mevcut tüm geçmiş veriler eksiksiz olarak okunmalı,
  2. Yeni veriler veya özellikler bu listenin **üzerine eklenmeli (append)**,
  3. Veri tabanı hiçbir zaman boş (`[]`) veya eksik şekilde commit edilmemelidir.
* Sunucuda çalışan canlı verilerin git güncellemeleri esnasında ezilmemesi için, yerel veri tabanı her zaman buluttaki en güncel işlem verileriyle senkronize tutulmalı ve korunmalıdır.

### 3. 🚀 Dağıtım (Deployment) Güvenliği
* Yeni özellikleri entegre ederken veya performans tabloları eklerken, mevcut kod yapısının stabilitesi bozulmamalıdır.
* Güncellemeler sonrasında sunucunun otomatik derlenmesi (`Render Build`) takip edilmeli ve hata almadığından emin olunmalıdır.
