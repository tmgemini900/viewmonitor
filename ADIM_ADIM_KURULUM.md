# 📖 ViewMonitor Pro — Adım Adım Kalıcı Yayın Rehberi

GitHub Pages + Render.com = **Ücretsiz, Kalıcı, Otomatik Deploy**

---

## 📁 Proje Yapısı

```
viewmonitor/
├── backend/
│   ├── main.py              ← Backend API (v4.1)
│   ├── requirements.txt     ← Python bağımlılıkları
│   └── .env.example         ← Ortam değişkeni şablonu
├── docs/
│   └── index.html           ← Frontend (GitHub Pages buradan yayınlanır)
├── .github/
│   └── workflows/
│       └── deploy.yml       ← Otomatik GitHub Pages deploy
├── Dockerfile               ← Docker kurulumu için
├── docker-compose.yml       ← Docker Compose ile çalıştırma
├── nginx.conf               ← Nginx reverse proxy (kendi sunucusu için)
├── render.yaml              ← Render.com otomatik deploy ayarları
└── .gitignore               ← .env dosyasını git'ten gizler
```

---

## Ne Alacaksın?

| Servis | URL Örneği | Ücret |
|--------|-----------|-------|
| Frontend (HTML) | `https://tmgemini900.github.io/viewmonitor` | Ücretsiz |
| Backend (API) | `https://viewmonitor-api.onrender.com` | Ücretsiz |

---

## 1️⃣ GitHub'a Repo Yükle

### Yeni repo oluştur
1. [github.com/new](https://github.com/new) git
2. Repository name: **`viewmonitor`**
3. **Public** seç (GitHub Pages için gerekli)
4. **Create repository**

### Dosyaları yükle
```bash
cd viewmonitor
git init
git remote add origin https://github.com/tmgemini900/viewmonitor.git
git add .
git commit -m "ViewMonitor Pro v4.1 — ilk kurulum"
git push -u origin main
```

---

## 2️⃣ GitHub Pages Aç

1. Repo → **Settings** → **Pages**
2. **Source** → `GitHub Actions`
3. Her `git push` sonrası otomatik deploy olur

✅ Adres:
```
https://tmgemini900.github.io/viewmonitor
```

---

## 3️⃣ Render.com'da Backend Deploy

1. [render.com](https://render.com) → GitHub ile giriş
2. **New +** → **Web Service** → `viewmonitor` reposunu seç

**ÖNEMLİ Ayarlar:**

```
Root Directory: backend
Build Command:  pip install -r requirements.txt
Start Command:  uvicorn main:app --host 0.0.0.0 --port $PORT
Plan:           Free
```

**Environment Variables ekle:**

| Key | Value |
|-----|-------|
| `ALLOW_ORIGIN` | `https://tmgemini900.github.io` |
| `API_KEY` | boş bırak |

3. **Create Web Service** → Deploy URL'ini kopyala

---

## 4️⃣ Frontend'i Bağla

1. GitHub Pages adresini aç
2. API adresi (Render URL'i) gir → **BAĞLAN**

---

## 5️⃣ Arkadaşınla Paylaş

```
https://tmgemini900.github.io/viewmonitor?api=https://viewmonitor-api.onrender.com
```

---

## 6️⃣ Render Uyku Modunu Engelle

1. [uptimerobot.com](https://uptimerobot.com) → Ücretsiz kayıt
2. **Add New Monitor** → HTTP(s) → `https://viewmonitor-api.onrender.com/api/durum` → 10 dakika

---

## 🐳 Docker ile Yerel Çalıştırma

```bash
cp backend/.env.example backend/.env
# .env düzenle: ALLOW_ORIGIN, API_KEY
docker-compose up -d
curl http://localhost:8080/api/durum
```

---

## ❓ Sık Sorulan Sorular

**"CORS error"** → Render'da `ALLOW_ORIGIN=https://tmgemini900.github.io` ayarla

**GitHub Pages açılmıyor** → Repo Public olmalı, `docs/index.html` var mı kontrol et

**Haberler gelmiyor** → UptimeRobot kur (adım 6)
