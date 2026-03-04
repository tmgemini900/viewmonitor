# 🛰 ViewMonitor Pro — Global OSINT Platform

Gerçek zamanlı global haber ve istihbarat izleme sistemi.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

## 🌐 Canlı Demo
- **Frontend:** `https://KULLANICI_ADIN.github.io/viewmonitor`
- **Backend API:** `https://viewmonitor-api.onrender.com`

---

## 🚀 Hızlı Kurulum (2 adım)

### Adım 1 — Backend: Render.com'a Deploy

1. [render.com](https://render.com) → GitHub ile giriş yap
2. **New → Web Service** → Bu repoyu seç
3. Ayarlar:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`  
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
4. **Deploy** → URL al: `https://viewmonitor-api.onrender.com`

### Adım 2 — Frontend: GitHub Pages

1. Repo → **Settings → Pages**
2. **Source:** `Deploy from a branch`
3. **Branch:** `main`, **Folder:** `/docs`
4. **Save** → `https://KULLANICI_ADIN.github.io/viewmonitor` hazır

### Adım 3 — Bağla

Frontend'i ilk açtığında API adresi sorar:
```
https://viewmonitor-api.onrender.com
```
gir ve **BAĞLAN**'a bas.

---

## 📦 Veri Kaynakları

| Kaynak | Adet | Açıklama |
|--------|------|----------|
| RSS    | 90+  | TR/KKTC/Kıbrıs/Orta Doğu/Asya/ABD/Afrika |
| Telegram | 70+ | OSINT/Breaking/Çatışma/Bölgesel |
| Nitter/X | 30+ | OSINT hesapları |
| GDELT  | -    | Global çatışma veritabanı |

## 🔧 Özellikler

- Gerçek zamanlı SSE akışı
- 5-8 saniyede bir güncelleme
- Leaflet harita + alarm marker sistemi
- Canlı TV (16 kanal HLS/YouTube)
- Uçuş & gemi trafiği overlay
- Çatışma haritası overlay
- Keyword watchlist
- Export (JSON/CSV)
- Priority scoring (KRİTİK/YÜKSEK/ORTA/DÜŞÜK)

---

## ⚠️ Not

Render.com ücretsiz planı **15 dakika** işlem olmadığında uyur.
İlk açılışta 30-60 saniye beklemen gerekebilir.

Uyku modunu devre dışı bırakmak için ücretsiz **UptimeRobot** kullan:
→ `https://uptimerobot.com` → her 10 dakikada API'ye ping at
→ URL: `https://viewmonitor-api.onrender.com/api/durum`
