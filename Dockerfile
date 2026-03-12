FROM python:3.11-slim

WORKDIR /app

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl && rm -rf /var/lib/apt/lists/*

# Düzeltme: backend/ klasöründen requirements.txt kopyalanıyor
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend kaynak dosyası
COPY backend/main.py .

# Frontend (docs/index.html kopyalanıyor)
COPY docs/index.html ./index.html

# Düzeltme: data/ klasörü oluşturuluyor — DB burada tutulacak
RUN mkdir -p /app/data

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8080/api/durum || exit 1

# Düzeltme: python3 main.py ile başlatılıyor (backend/main.py)
CMD ["python3", "main.py"]
