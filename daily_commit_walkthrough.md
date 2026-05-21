# Günlük Git Commit Walkthrough & Teknik Özet

Bu dosya, bugün yapılan 3 ana commitin detaylı Türkçe özetini, teknik walkthrough analizini ve değişen tüm parametre/formül tablolarını içermektedir.

---

## 1. Commit Özetleri ve Dosya Değişimleri

### Commit 1 (Saat 12:51) — `36b2b28`
**Başlık:** *Optimize risk-to-reward ratio and fix take profit bug in trade executor*

*   **Etkilenen Dosya:**
    *   [trade_executor.py](file:///c:/Users/berke/OneDrive/Masaüstü/COİN_PROJE/trade_executor.py) (+42 satır, -27 satır)
*   **Açıklama:**
    *   Sistemdeki Take Profit (TP - Kâr Al) bariyeri mantığındaki hesaplama hataları giderildi.
    *   Kademeli kâr alım (PTP - Partial Take Profit) mekanizmasındaki matematiksel bug'lar çözülerek **risk/ödül oranları (R:R)** optimize edildi. İşlemlerin risk bütçesine göre daha sağlıklı R-Multiple vermesi sağlandı.

---

### Commit 2 (Saat 13:25) — `42e3f26`
**Başlık:** *Optimize bot engine and trade execution logic: volatility parity sizing, structure exits, regime adjusted trailing stops, and MTF data validation*

*   **Etkilenen Dosyalar:**
    *   [technical_analysis.py](file:///c:/Users/berke/OneDrive/Masaüstü/COİN_PROJE/technical_analysis.py) (+85 satır, -15 satır)
    *   [signal_generator.py](file:///c:/Users/berke/OneDrive/Masaüstü/COİN_PROJE/signal_generator.py) (+242 satır, -148 satır)
    *   [trade_executor.py](file:///c:/Users/berke/OneDrive/Masaüstü/COİN_PROJE/trade_executor.py) (+86 satır, -48 satır)
    *   [bot_engine.py](file:///c:/Users/berke/OneDrive/Masaüstü/COİN_PROJE/bot_engine.py) (+19 satır, -4 satır)
*   **Açıklama:**
    *   **Market Rejimi Tespiti:** Volatilite yüzdeleri, Bollinger Band genişliği, ADX gücü ve hacim genişlemesi kullanılarak rejim sınıflandırması (`COMPRESSION`, `VOLATILITY_EXPANSION`, `TRENDING_BULL`, `TRENDING_BEAR`, `RANGE`) yapıldı.
    *   **Çoklu Zaman Dilimi (MTF) Doğrulaması:** Sinyaller 1H yapısal ve 4H makro trend pencereleri üzerinden hiyerarşik filtrelemeye tabi tutuldu.
    *   **Oynaklık Normlu Pozisyon Büyüklüğü (Risk Parity):** `position_size_usd = (balance * risk_pct * risk_multiplier) / stop_distance_pct` formülü ile volatiliteye göre ölçeklenen ve maksimum **3.0x** kaldıraçla sınırlanan pozisyon boyutu mimarisi kuruldu.
    *   **Yapısal Kapanış Motoru:** 1H grafikten alınan destek/direnç seviyelerinin altına/üstüne sarkmalarda işlemi doğrudan `STRUCTURE` sebebiyle kapatan erken stop sistemi eklendi.
    *   **Rejim Duyarlı Takip Stopu (Trailing Stop):** Trend rejimlerinde daha gevşek (`0.4x` kâr hedefi toleransı), yatay (`RANGE`) rejimlerde ise daha sıkı (`0.15x` kâr hedefi toleransı) çalışan dinamik takip stopları entegre edildi.

---

### Commit 3 (Saat 13:38) — `168e510`
**Başlık:** *Optimize ML meta-labeling target, weights attribution, and add git diff tracking*

*   **Etkilenen Dosyalar:**
    *   [app.py](file:///c:/Users/berke/OneDrive/Masaüstü/COİN_PROJE/app.py) (+79 satır)
    *   [signal_generator.py](file:///c:/Users/berke/OneDrive/Masaüstü/COİN_PROJE/signal_generator.py) (+165 satır, -42 satır)
    *   [trade_executor.py](file:///c:/Users/berke/OneDrive/Masaüstü/COİN_PROJE/trade_executor.py) (+13 satır, -1 satır)
    *   [.gitignore](file:///c:/Users/berke/OneDrive/Masaüstü/COİN_PROJE/.gitignore) (+1 satır)
*   **Açıklama:**
    *   **Git Değişim Yüzdesi Takibi (Git Diff Tracking):** Sunucu her başladığında son iki commit arasındaki farkı `git diff --shortstat` ile çekerek kod tabanındaki yüzdelik değişimi hesaplayan ve bunu `/api/git-diffs` API rotasından sunan mekanizma eklendi.
    *   **Çok Pencereli Bellek (Multi-Window Weighting):** İndikatör ağırlık optimizasyonu son 50 (kısa vadeli - %50 ağırlık), son 200 (orta vadeli - %30 ağırlık) ve son 1000 (uzun vadeli - %20 ağırlık) işlemlik pencerelerden beslenen karma yapıya geçirildi.
    *   **Asimetrik Ödüllendirme & Beleşçi Koruyucu (Attribution):** Ağırlık güncellemeleri ham win/loss yerine realize edilen asimetrik R-multiple (`realized_R_multiple`) tabanlı yapıldı. İndikatörün sadece işlemin yönünü desteklediği durumlarda güncellenmesi (attribution) sağlandı.
    *   **ML Kalite Skoru Hedefi (Expectancy Quality Score Target):** Model 2 (`QuantMetaFilter`) hedefi, şans eseri kazanılan işlemlerin elenmesi için MFE/MAE oranı, işlem süresi cezası ve çıkış verimliliğini birleştiren kalite skoruna göre eğitilecek şekilde yeniden modellendi.
    *   **Interaction Features (Doğrusal Olmayan Çapraz İlişkiler):** Lojistik regresyonun doğrusal kısıtlamalarını kırmak için çapraz özellikler (`rsi * ema`, `vol * ema`, vb.) modele girdi olarak eklendi.
    *   **Dinamik Olasılık Eşikleri ve Pozisyon Ölçekleme:** Model 2 olasılık eşiği drawdown durumuna ve rejim yapısına göre dinamik hale getirildi. Sinyal kalitesi eşiğe yakın olan işlemlerde pozisyon boyutu otomatik olarak `0.5x` çarpanıyla düşürüldü.

---

## 2. Değişen Formüller, Risk Çarpanları ve Parametre Karşılaştırmaları

### A. Pozisyon Büyüklüğü ve Risk Yönetimi Değişimleri
| Parametre | Önceki Durum | Yeni Durum (Şimdiki) | Amacı |
| :--- | :--- | :--- | :--- |
| **Ana Risk Yüzdesi** | Belirsiz / Sabit Kelly | Kasa bakiyesinin net **%1.5**'i (`risk_pct = 0.015`) | Sabit risk kuralı |
| **Maksimum Kaldıraç** | Limit yoktu | En fazla **3.0x** kaldıraç | Likidasyon riskini önleme |
| **Ardışık Kayıp Koruması** | Yoktu | **3 kayıp:** %50 boyut düşürme<br>**5 kayıp:** %75 boyut düşürme | Seri kayıplarda kasayı koruma |
| **Korelasyon Koruması** | Yoktu | Açık pozisyonlarla korelasyon **$\ge 0.70$** ise yeni işlem boyutu **%50 düşürülür** | Risk birikimini önleme |
| **Rejim Çarpanı** | Yoktu | `RANGE` veya `SIDEWAYS` rejimlerinde pozisyon boyutu **%30 düşürülür** (`0.70x`) | Kararsız piyasada az risk |
| **Yapay Zeka (Model 2) Çarpanı** | Yoktu | Eğer tahmin olasılığı eşiğe çok yakınsa ($+10\%$ bandı) işlem boyutu **%50 düşürülür** | Düşük güvenli işlem koruması |

### B. Kâr Al / Zarar Durdur ve Takip Stopu (Trailing) Değişimleri
| Parametre / Özellik | Önceki Durum | Yeni Durum (Şimdiki) | Amacı |
| :--- | :--- | :--- | :--- |
| **Trend Takip Stopu (Trailing)** | Sabit callback değeri | **0.4x Hedef Kâr** (En az %0.8 fiyat hareketi tetiklemeli) | Trend yönünde maksimum kârı sürme |
| **Yatay Piyasa Takip Stopu** | Sabit callback değeri | **0.15x Hedef Kâr** (En az %0.3 fiyat hareketi tetiklemeli) | Kârı hızlıca realize etme |
| **Yapısal Erken Çıkış (Structure Exit)** | Yoktu | **1H Zaman dilimindeki** destek kırılırsa (Long) veya direnç aşılırsa (Short) işlem anında kapanır. | Büyük stop patlamalarını önleme |

### C. Yapay Zeka (Model 2 Meta-Filter) Karar ve Eğitim Eşikleri
| Özellik | Önceki Durum | Yeni Durum (Şimdiki) | Amacı |
| :--- | :--- | :--- | :--- |
| **Model Tahmin Eşiği** | Sabit **0.55** olasılık eşiği | **Trend:** 0.55 basamak<br>**Yatay:** 0.65 basamak<br>**Volatil/Sıkışma:** 0.72 basamak | Piyasa durumuna göre seçiciliği artırma |
| **Drawdown (Kayıp) Cezası** | Yoktu | Eşiğe **`+ (drawdown_pct * 1.5)`** eklenir (Maksimum %+15) | Bakiye erirken botun filtrelerini zorlaştırma |
| **Model Eğitim Hedefi (Labeling)** | Kazandı/Kaybetti (PnL > 0 $\to$ 1) | **Expectancy Quality Score $\ge 0.50$** ise 1, değilse 0. | Şans eseri kazanılan hatalı işlemlerin yapay zeka tarafından öğrenilmesini engelleme |

> 💡 **Expectancy Quality Score Formülü:**
> `Skor = (realized_R * 0.45) + (MFE/MAE_orani * 0.20) + (cikis_verim * 0.25) - holding_time_cezasi`

### D. İndikatör Ağırlıkları Güncelleme Kuralları
*   **Önceki:** Son 100 işlemin win/loss durumuna göre her indikatörün ağırlığı sabit artıp azalıyordu. Beleşçi (free-rider) indikatörler de kazanan işlemden ödül alıyordu.
*   **Şimdi:** 
    *   **Çoklu Pencere:** Son 50 (Ağırlık payı %50), son 200 (Ağırlık payı %30) ve son 1000 (Ağırlık payı %20) işlemin birleşik ağırlığı hesaplanıyor.
    *   **Beleşçi Koruması (Attribution):** İndikatörün verdiği sinyal açılan işlem yönüyle (Long/Short) eşleşmiyorsa, işlem kâr etse bile o indikatör ödüllendirilmiyor.
    *   **R-Multiple Tabanlı:** Ödül/Ceza puanı kazanılan paranın riske oranına göre (`realized_R_multiple`) veriliyor. (Çarpan: `-2.0` ile `+3.0` arasında sınırlandırılmıştır).
