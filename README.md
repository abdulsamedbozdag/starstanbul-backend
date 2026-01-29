# YTÜ Ulaşım Backend API

Python FastAPI ile yazılmış, İBB IETT otobüs verilerini cache'leyerek sunan REST API.

## 🚀 Kurulum

### 1. Gerekli Paketleri Yükleyin

```bash
cd backend
pip install -r requirements.txt
```

### 2. Sunucuyu Başlatın

```bash
python main.py
```

veya

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 📡 API Endpoints

### 1. Ana Sayfa
```
GET http://localhost:8000/
```

### 2. Otobüs Konumları (Cache'li)
```
GET http://localhost:8000/otobusler/{hat_kodu}
```

**Örnek:**
- `http://localhost:8000/otobusler/41AT`
- `http://localhost:8000/otobusler/85C`

**Özellikler:**
- ✅ 40 saniye boyunca cache'lenir (İBB rate limit koruması)
- ✅ Cache'teki veri varsa İBB API'ye KESİNLİKLE gitmez
- ✅ XML'den JSON'a otomatik dönüşüm
- ✅ 1 milyon kullanıcıya aynı anda hizmet verebilir

**Response:**
```json
{
  "source": "cache",
  "hat_kodu": "41AT",
  "cached_at": "2026-01-30T00:17:45.123456",
  "data": [
    {
      "kapino": "34ABC123",
      "enlem": "41.0256",
      "boylam": "28.8880",
      "yon": "G"
    }
  ]
}
```

### 3. Cache Durumu (Debug)
```
GET http://localhost:8000/cache/status
```

### 4. Cache Temizleme
```
DELETE http://localhost:8000/cache/{hat_kodu}
```

## 📚 API Dokümantasyonu (Swagger)

Sunucu çalışırken şu adresten interaktif API dokümantasyonuna erişebilirsiniz:

```
http://localhost:8000/docs
```

## 🔧 Teknik Detaylar

- **Framework:** FastAPI
- **Cache Süresi:** 40 saniye (RAM'de)
- **Rate Limit Koruması:** Saatte maksimum 90 İBB API isteği
- **CORS:** Tüm originlere açık
- **İBB API Timeout:** 10 saniye
- **Port:** 8000
- **Kapasite:** 1+ milyon eşzamanlı kullanıcı

## 🔒 Güvenlik Notu

⚠️ API Key (`679fe901-5d08-4ce8-855b-e113547fa3d8`) kodda açık şekilde bulunmaktadır. Production ortamında bu değer environment variable olarak alınmalıdır:

```python
import os
IBB_API_KEY = os.getenv("IBB_API_KEY", "default-key")
```
