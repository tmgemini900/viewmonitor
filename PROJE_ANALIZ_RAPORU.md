# 🛰 ViewMonitor Pro — Kapsamlı Proje Analiz Raporu

**Tarih:** 12 Mart 2026
**Analiz Edilen Dosyalar:** viewmonitor_api.py, viewmonitor_api_prod.py, viewmonitor.html, viewmonitor_v2.html, Dockerfile, docker-compose.yml, render.yaml, github_deploy.yml, nginx.conf, requirements.txt, requirements_prod.txt, KURULUM.md, ADIM_ADIM_KURULUM.md, UZAK_ERISIM_KURULUM.md, README.md

---

## 🔴 KRİTİK HATALAR (Deployment'ı Kıran Sorunlar)

### 1. `main.py` Dosyası Yok — Render Deploy BAŞARISIZ Olur

`ADIM_ADIM_KURULUM.md` kullanıcıya şu Render ayarlarını girmesini söylüyor:

```
Root Directory: backend
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

Ancak projede **ne `backend/` klasörü ne de `main.py` dosyası var.** Bu ayarlarla Render deploy tamamen başarısız olur. `render.yaml` ise doğru `viewmonitor_api:app` modülünü referans alıyor ama kökde.

**Çözüm:** Ya dosyaları `backend/main.py` olarak yeniden düzenle ya da ADIM_ADIM_KURULUM.md dokümanını güncel yapıyla senkronize et.

---

### 2. İki Ayrı API Dosyası — Hangisi Kullanılacak?

Projede birbirine rakip iki backend var:

| Dosya | Sürüm | Özellikler |
|-------|-------|------------|
| `viewmonitor_api.py` | v4.1 | SQLite DB, SSE stream, Scheduler, USGS, AFAD, EONET, GDELT, 130+ RSS, 60+ Telegram |
| `viewmonitor_api_prod.py` | v2.1 | Sadece basit polling, API Key auth, Rate limiting, `.env` desteği, Scheduler/DB YOK |

Farklı rehberler farklı dosyaları işaret ediyor:
- `KURULUM.md` → `viewmonitor_api.py`
- `UZAK_ERISIM_KURULUM.md` → `viewmonitor_api_prod.py`
- `Dockerfile` → `viewmonitor_api.py`
- `render.yaml` → `viewmonitor_api:app` (v4.1'i kastediyor)

Bu durum kafaları karıştırıyor ve bakımı imkânsız hale getiriyor.

**Çözüm:** `viewmonitor_api_prod.py` içindeki güvenlik özelliklerini (API Key, Rate Limiting, `.env`) `viewmonitor_api.py`'ye entegre et, `_prod.py` dosyasını sil.

---

### 3. İki Ayrı HTML Dosyası — Hangisi Frontend?

| Dosya | Referans Edildiği Yer |
|-------|----------------------|
| `viewmonitor.html` | KURULUM.md, Dockerfile |
| `viewmonitor_v2.html` | UZAK_ERISIM_KURULUM.md |
| `index.html` | Hiçbir yerde belgelenmemiş |

Kullanıcı hangi HTML'i kullanacağını bilemiyor.

---

### 4. CORS Yapılandırması — GitHub Kullanıcı Adı Hardcode

`viewmonitor_api.py` satır 856–862:

```python
allow_origins=[
    "https://tmgemini900.github.io",   # ← HARDCODE kullanıcı adı!
    "http://localhost:5500",
    ...
]
```

Bu ayar **sadece `tmgemini900` kullanıcısının GitHub Pages'ini** kabul eder. Başka biri bu projeyi kendi GitHub'ına koyarsa frontend tamamen çalışmaz, CORS hatası alır.

**Çözüm:** `ALLOW_ORIGIN` ortam değişkenini zorunlu yap veya `["*"]` kullan (geliştirme için):
```python
allow_origins=os.environ.get("ALLOW_ORIGIN", "*").split(",")
```

---

### 5. `/tmp` DB Yolu — Render'da Tüm Veriler Silinir

`DB_PATH = os.environ.get("DB_PATH", "/tmp/viewmonitor.db")`

Render.com ücretsiz planında `/tmp` **ephemeral**'dır (geçicidir). Her yeniden başlatma veya deploy'da tüm haber veritabanı sıfırlanır. 8000 kayıt sınırına kadar toplanan veriler kaybolur.

**Çözüm:** Render'da `DB_PATH=/var/data/viewmonitor.db` kullan ve Render disk ekle (ücretli) **ya da** Render ücretsiz plan için SQLite yerine harici bir veritabanı (Supabase, PlanetScale ücretsiz tier) düşün.

---

### 6. `.env.example` Dosyası Yok

`UZAK_ERISIM_KURULUM.md` Docker bölümü adım 2:
```bash
cp .env.example .env
```
Projede `.env.example` dosyası **yok**. Komut hata verir.

---

## 🟠 ORTA ÖNEMLİ HATALAR (Güvenlik & Tutarsızlık)

### 7. Ana API'de Kimlik Doğrulama Yok

`viewmonitor_api.py` (Dockerfile ve render.yaml'da kullanılan ana API) hiçbir API Key authentication içermiyor. URL'i bilen herkes:
- Tüm haber veritabanını çekebilir (`/api/haberler`)
- Toplu veri çekimini tetikleyebilir (`/api/tetikle`)
- 1000 satıra kadar export alabilir (`/api/export`)
- SSE stream'e bağlanabilir (`/api/stream`)

`viewmonitor_api_prod.py`'deki güvenlik kodları ana API'ye taşınmamış.

---

### 8. SSE Endpoint'inde CORS Bypass

`/api/stream` endpoint'i (satır 921):
```python
headers={"Access-Control-Allow-Origin": "*"}
```
Bu satır, uygulamanın genel CORS middleware'ini **devre dışı bırakıyor**. Hardcode edilmiş `tmgemini900.github.io` kısıtlaması SSE için çalışmıyor, her domain erişebiliyor. Güvenlik yaklaşımında ciddi tutarsızlık.

---

### 9. Global Sayaçlar Eş Zamanlı Erişimde Güvenli Değil

```python
rss_idx = tg_idx = nt_idx = gdelt_sayac = usgs_sayac = afad_sayac = eonet_sayac = 0
```

`toplu_cek()` hem scheduler tarafından her 13 saniyede bir hem de `/api/tetikle` endpoint'ince manuel tetiklenir. Her ikisi aynı anda çalışırsa global sayaçlar çakışır, aynı kaynaktan çift çekim veya kaynak atlama olabilir.

---

### 10. `requirements.txt` ve `requirements_prod.txt` Senkron Değil

| Paket | requirements.txt | requirements_prod.txt |
|-------|-----------------|----------------------|
| aiosqlite | ✅ 0.19.0 | ❌ Yok |
| apscheduler | ✅ 3.10.4 | ❌ Yok |
| python-dotenv | ❌ Yok | ✅ 1.0.1 |
| fastapi | 0.110.0 | 0.111.0 |
| uvicorn | 0.27.1 | 0.29.0 |
| httpx | 0.26.0 | 0.27.0 |
| lxml | 5.1.0 | 5.2.2 |

Ana API (`viewmonitor_api.py`) `python-dotenv`'u optionally import etmeye çalışıyor ama requirements.txt'te yok. Production API'nin `aiosqlite` ve `apscheduler` olmadan çalışamayacağı açık.

---

### 11. `docker-compose.yml` Port Tutarsızlığı

```yaml
ports:
  - "8080:8080"
volumes:
  - ./viewmonitor.db:/app/viewmonitor.db  # ← Sorun burada
```

`./viewmonitor.db` yerel makinede henüz yoksa Docker bunu bir **klasör** olarak oluşturur (dosya olarak değil). SQLite bu durumda `IsADirectoryError` verir.

**Çözüm:**
```yaml
volumes:
  - ./data:/app/data
environment:
  - DB_PATH=/app/data/viewmonitor.db
```

---

### 12. Sürüm Tutarsızlığı (4.0 vs 4.1)

| Konum | Gösterilen Sürüm |
|-------|----------------|
| Dosya başlığı (docstring) | v4.1 |
| `app = FastAPI(version=...)` | 4.1.0 |
| `/api/durum` response | "versiyon":"4.0" |
| Startup banner | "ViewMonitor Pro API v4.0" |

---

### 13. Nitter Instance'larının Büyük Çoğunluğu Ölü

```python
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",   # Kapalı
    "https://nitter.poast.org",        # Kapalı
    "https://nitter.1d4.us",           # Kapalı
    "https://nitter.rawbit.ninja",     # Kapalı
    "https://nitter.unixfox.eu",       # Kapalı/kısıtlı
    "https://xcancel.com",             # Kapalı
    "https://nitter.cz",               # Kapalı
    "https://nitter.kavin.rocks",      # Kapalı
]
```

Twitter'ın API politika değişikliklerinden bu yana neredeyse tüm Nitter instance'ları kapalı. Kod her seferinde 4 instance deniyor, hepsi hata veriyor, sessizce `None` dönüyor. Sonuç: Twitter verisi hiç gelmiyor ama kod hatasız çalışıyormuş gibi görünüyor.

---

## 🟡 DÜŞÜK ÖNEMLİ — İYİLEŞTİRME ÖNERİLERİ

### 14. Her HTTP İsteğinde Yeni Client Oluşturuluyor (Performans)

```python
async def rss_cek(k: dict):
    async with httpx.AsyncClient(timeout=9.0) as c:  # Her çağrıda yeni client!
```

`toplu_cek()` 5 RSS + 2 TG + 1 Nitter = en az 8 ayrı client oluşturuyor, her 13 saniyede bir. Persistent bir `httpx.AsyncClient` kullanmak bellek kullanımını ve bağlantı süresini önemli ölçüde iyileştirir.

---

### 15. Her DB İşleminde Yeni Bağlantı Açılıyor (Performans)

```python
async def db_kaydet(v: dict):
    async with aiosqlite.connect(DB_PATH) as db:  # Her insert'te yeni bağlantı
```

```python
async def db_listele(...):
    async with aiosqlite.connect(DB_PATH) as db:  # Her sorguda yeni bağlantı
```

`toplu_cek()` çıktısında her yeni haber için ayrı bir bağlantı açılıp kapanıyor. Uygulama başlangıcında persistent bir DB bağlantısı veya bağlantı havuzu tutmak çok daha verimli olurdu.

---

### 16. GoogleTranslator Async Context'te Senkron Çalışıyor

```python
ceviri = GoogleTranslator(source='auto', target='tr').translate(metin[:500])
```

Bu çağrı senkron bir HTTP isteği yapıyor ve async event loop'u bloklayabiliyor. `asyncio.to_thread()` ile thread havuzuna taşınmalı.

---

### 17. Zaman Damgası Yerel Saatle Yazılıyor

```python
"zaman": datetime.now().strftime("%H:%M:%S")
```

Sadece saat bilgisi (tarih yok) ve UTC yerine sunucu yerel saati kullanılıyor. Bu:
- Farklı zaman dilimlerinde çalışan sunucularda yanlış görünebilir
- Tarih içermediği için gece yarısı geçişlerinde kafa karışıklığı yaratır
- DB'deki `created_at` ile tutarsız

**Çözüm:** `datetime.now(timezone.utc).isoformat()` kullan.

---

### 18. `istek_sayaci` Memory Leak'i (`viewmonitor_api_prod.py`)

```python
istek_sayaci: dict = defaultdict(list)
```

Bu dict her yeni IP için büyüyor, hiçbir zaman temizlenmiyor. Yoğun trafik altında bellekte sınırsız büyüyebilir. 1 dakikadan eski kayıtlar her istek geldiğinde temizleniyor ama IP başına girdi hiç silinmiyor.

---

### 19. `/api/tetikle` POST Endpoint'i — Auth Yok

```python
@app.post("/api/tetikle")
async def tetikle():
```

30 saniyelik cooldown var ama authentication yok. Distributed saldırıda farklı IP'lerden sürekli istek gönderilebilir (cooldown tek IP bazlı değil, global).

---

### 20. Self-Ping Port Mantığı Eksik

```python
async def _self_ping():
    port = int(os.environ.get("PORT", 8080))
    async with httpx.AsyncClient(timeout=10) as hc:
        await hc.get(f"http://localhost:{port}/api/durum")
```

Render ortamında `PORT` env var'ı dynamic bir değer (örneğin 10000). Kod bunu doğru okuyor. Ancak self-ping zaten UptimeRobot önerisinin yapılmasını gereksizleştiriyor — iki farklı yöntem çakışıyor ve hangisinin öncelikli olduğu belgelenmemiş.

---

### 21. `nginx.conf`'ta `limit_req_zone` Tanımsız

```nginx
location /api/ {
    limit_req zone=api burst=10 nodelay;  # ← zone=api tanımlı değil!
}
```

`limit_req_zone` direktifi `# http bloğuna ekleyin: /etc/nginx/nginx.conf` yorumuyla sadece comment olarak gösteriliyor. Kullanıcı bu adımı atlayıp conf'u kopyalarsa Nginx başlamayı reddeder: `"zone "api" not found"`.

---

### 22. `export` Endpoint'inde `format` Parametresi — Python Built-in Çakışması

```python
@app.get("/api/export")
async def export(format: str = Query("json")):
```

`format` Python'un yerleşik bir fonksiyonu. Parametre ismi olarak kullanmak teknik olarak çalışsa da kötü pratik. `fmt` veya `dosya_tipi` tercih edilmeli.

---

### 23. `viewmonitor_api.py` İçinde `import os` İkinci Kez

```python
@app.get("/")
def root():
    import os       # ← Dosya başında zaten import edilmiş!
    if os.path.exists("index.html"):
```

Gereksiz tekrar import. Zararlı değil ama kötü pratik.

---

## 📋 YAPISAL / DOKÜMANTASyon SORUNLARI

### 24. Repo Klasör Yapısı Tutarsız

README ve ADIM_ADIM_KURULUM.md şu yapıyı vadediyor:
```
backend/main.py
backend/requirements.txt
docs/index.html
render.yaml
```

Gerçekte:
```
viewmonitor_api.py          (backend, kökte)
viewmonitor_api_prod.py     (ikinci backend, kökte)
viewmonitor.html            (frontend 1)
viewmonitor_v2.html         (frontend 2)
index.html                  (frontend 3 — belgelenmemiş)
requirements.txt
requirements_prod.txt
Dockerfile
docker-compose.yml
render.yaml
nginx.conf
github_deploy.yml
```

GitHub Pages `docs/` klasöründen yayın yapmayı bekliyor (`github_deploy.yml`'de `path: './docs'`), ama docs klasörü yok.

---

### 25. GitHub Actions Workflow — `docs/` Klasörü Yok

`github_deploy.yml`:
```yaml
- name: Upload artifact
  uses: actions/upload-pages-artifact@v3
  with:
    path: './docs'   # Bu klasör yok!
```

GitHub Pages deploy işlemi başarısız olur çünkü `docs/` klasörü oluşturulmamış.

---

### 26. README'de Placeholder URL'ler

```
- **Frontend:** `https://tmgemini900.github.io/viewmonitor`
- **Backend API:** `https://viewmonitor-api.onrender.com`
```

Backend URL'i `viewmonitor-api.onrender.com` — bu gerçek bir URL değil, kime ait? Her kullanıcının farklı bir Render URL'i olacak. Bu URL dokümanın her yerinde sabit yazılmış ama çalışmıyor olabilir.

---

## ✅ İYİ YAPILMIŞ ŞEYLER

Eleştiri dengeli olsun diye olumlu noktaları da belirtmek gerekir:

- **Hash bazlı duplicate kontrolü** — aynı haberin tekrar eklenmesi engelleniyor
- **DB migration sistemi** — eski DB'lerde eksik kolonlar otomatik ekleniyor
- **APScheduler + SSE kombinasyonu** — gerçek zamanlı veri akışı için iyi mimari seçim
- **Çok katmanlı öncelik sistemi** (KRİTİK/YÜKSEK/ORTA/DÜŞÜK) — kelime bazlı skorlama mantıklı
- **Paralel veri çekimi** (`asyncio.gather`) — performans için doğru yaklaşım
- **Kapsamlı kaynak listesi** (130+ RSS, 60+ Telegram, USGS, AFAD, EONET, GDELT)
- **Healthcheck** hem Dockerfile'da hem docker-compose.yml'de mevcut
- **Nginx SSE ayarları** (`proxy_buffering off`, `proxy_read_timeout 3600s`) doğru yapılmış
- **Zaman filtreli Telegram çekimi** (12 saat sınırı, eski mesajları atlıyor)

---

## 🗂 ÖNCELİKLİ DÜZELTME LİSTESİ

Aşağıdaki sorunlar deploy/kullanım için en kritik olanlar:

| # | Sorun | Öncelik | Etki |
|---|-------|---------|------|
| 1 | `main.py` / `backend/` klasörü yok | 🔴 KRİTİK | Render deploy başarısız |
| 2 | `docs/` klasörü yok | 🔴 KRİTİK | GitHub Pages deploy başarısız |
| 3 | CORS hardcode kullanıcı adı | 🔴 KRİTİK | Diğer kullanıcılarda çalışmaz |
| 4 | İki ayrı API dosyası | 🟠 YÜKSEK | Bakım karmaşası, hatalı dokümantasyon |
| 5 | DB `/tmp` yolu | 🟠 YÜKSEK | Render'da veri kaybı |
| 6 | `.env.example` yok | 🟠 YÜKSEK | Docker kurulumu başarısız |
| 7 | Ana API'de auth yok | 🟠 YÜKSEK | Güvenlik açığı |
| 8 | docker-compose.yml DB volume sorunu | 🟡 ORTA | Docker start hatası |
| 9 | Nitter instance'ları ölü | 🟡 ORTA | Twitter verisi gelmiyor |
| 10 | nginx.conf `limit_req_zone` eksik | 🟡 ORTA | Nginx başlamaz |
| 11 | Sürüm tutarsızlığı (4.0 vs 4.1) | 🟢 DÜŞÜK | Kafa karışıklığı |
| 12 | GoogleTranslator sync bloklama | 🟢 DÜŞÜK | Performans |
| 13 | Zaman damgası UTC değil | 🟢 DÜŞÜK | Saat kayması |

---

## 🏗 ÖNERİLEN PROJE YAPISI

```
viewmonitor/
├── backend/
│   ├── main.py               ← viewmonitor_api.py buraya taşı, API key ekle
│   ├── requirements.txt      ← python-dotenv da ekle
│   └── .env.example          ← Yeni oluştur
├── docs/
│   └── index.html            ← viewmonitor_v2.html buraya, index.html olarak
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml    ← DB volume düzeltilmiş
│   └── nginx.conf            ← limit_req_zone dahil edilmiş
├── .github/
│   └── workflows/
│       └── deploy.yml        ← Mevcut, iyi
├── render.yaml               ← Root dir backend/ olarak güncelle
└── README.md                 ← Güncel yapıyı yansıt
```

---

*Rapor oluşturma tarihi: 12 Mart 2026*
