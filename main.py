from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import xmltodict
from datetime import datetime, timedelta
from typing import Optional

app = FastAPI(title="YTÜ Ulaşım Backend API", version="1.0.0")

# CORS Ayarları - Tüm originlere izin ver
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# İBB API Anahtarı
IBB_API_KEY = "679fe901-5d08-4ce8-855b-e113547fa3d8"

# Cache Süresi (Saniye) - İBB'nin saatlik 100 istek limitini aşmamak için
CACHE_DURATION = 40  # 40 saniye = Saatte maksimum 90 istek (güvenli marj)

# Cache Yapısı (RAM'de tutulacak)
cache = {}

class CacheItem:
    def __init__(self, data, timestamp):
        self.data = data
        self.timestamp = timestamp
    
    def is_expired(self):
        """Cache'in süresi dolmuş mu kontrol eder (40 saniye)"""
        return (datetime.now() - self.timestamp).total_seconds() > CACHE_DURATION


@app.get("/")
def read_root():
    """Ana sayfa - API durumu"""
    return {
        "status": "active",
        "message": "YTÜ Ulaşım Backend API çalışıyor",
        "cache_duration": f"{CACHE_DURATION} saniye",
        "rate_limit_protection": f"Saatte maksimum {int(3600 / CACHE_DURATION)} İBB API isteği",
        "info": "40 saniyelik akıllı cache ile 1 milyon kullanıcıya hizmet verebilir",
        "endpoints": {
            "/otobusler/{hat_kodu}": "Belirtilen hat için otobüs konumlarını getirir (40s cache)",
            "/cache/status": "Cache durumunu gösterir (debug)",
            "/docs": "API dokümantasyonu (Swagger UI)"
        }
    }


@app.get("/otobusler/{hat_kodu}")
def get_bus_locations(hat_kodu: str):
    """
    Belirtilen hat kodu için otobüs konumlarını getirir.
    40 saniye boyunca cache'lenir (İBB rate limit koruması).
    
    Mantık:
    - Veri 40 saniyeden yeniyse: Cache'ten dön (İBB'ye GİTME)
    - Veri 40 saniyeden eskiyse: İBB'den çek, cache'e al, dön
    
    Bu sayede 1 milyon kullanıcı olsa bile dakikada sadece 1-2 istek gider.
    
    Örnek: /otobusler/41AT veya /otobusler/85C
    """
    
    # Cache kontrolü - ÖNCE BURAYA BAK!
    if hat_kodu in cache:
        cached_item = cache[hat_kodu]
        if not cached_item.is_expired():
            # ✅ Cache hala geçerli - İBB'ye GİTME!
            return {
                "source": "cache",
                "hat_kodu": hat_kodu,
                "cached_at": cached_item.timestamp.isoformat(),
                "cache_expires_in_seconds": int(CACHE_DURATION - (datetime.now() - cached_item.timestamp).total_seconds()),
                "data": cached_item.data
            }
    
    # Cache yoksa veya süresi dolmuşsa, İBB API'ye istek at
    try:
        # SOAP İstek Zarfı
        soap_envelope = f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Header>
        <AuthHeader xmlns="http://tempuri.org/">
            <Username>{IBB_API_KEY}</Username>
            <Password>{IBB_API_KEY}</Password>
        </AuthHeader>
    </soap:Header>
    <soap:Body>
        <GetHatOtoKonum_json xmlns="http://tempuri.org/">
            <HatKodu>{hat_kodu}</HatKodu>
        </GetHatOtoKonum_json>
    </soap:Body>
</soap:Envelope>'''
        
        # İBB SOAP API'ye istek
        response = requests.post(
            'https://api.ibb.gov.tr/iett/FiloDurum/SeferGerceklesme.asmx',
            headers={
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://tempuri.org/GetHatOtoKonum_json'
            },
            data=soap_envelope.encode('utf-8'),
            timeout=10
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"İBB API'den veri alınamadı. HTTP {response.status_code}"
            )
        
        # XML'i Python dict'e çevir
        xml_dict = xmltodict.parse(response.text)
        
        # JSON içeriğini çıkar
        json_result = xml_dict['soap:Envelope']['soap:Body']['GetHatOtoKonum_jsonResponse']['GetHatOtoKonum_jsonResult']
        
        # JSON string'i Python objesine çevir
        import json
        bus_data = json.loads(json_result) if json_result else []
        
        # Cache'e kaydet - 40 saniye boyunca saklanacak
        current_time = datetime.now()
        cache[hat_kodu] = CacheItem(data=bus_data, timestamp=current_time)
        
        return {
            "source": "api",
            "hat_kodu": hat_kodu,
            "fetched_at": current_time.isoformat(),
            "cache_duration_seconds": CACHE_DURATION,
            "next_refresh_at": (current_time + timedelta(seconds=CACHE_DURATION)).isoformat(),
            "data": bus_data
        }
    
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="İBB API'ye istek zaman aşımına uğradı")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"İBB API'ye bağlanılamadı: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sunucu hatası: {str(e)}")


@app.get("/cache/status")
def cache_status():
    """Cache durumunu gösterir (debug amaçlı)"""
    status = {}
    current_time = datetime.now()
    for hat_kodu, cached_item in cache.items():
        age_seconds = (current_time - cached_item.timestamp).total_seconds()
        status[hat_kodu] = {
            "cached_at": cached_item.timestamp.isoformat(),
            "expired": cached_item.is_expired(),
            "age_seconds": int(age_seconds),
            "remaining_seconds": int(CACHE_DURATION - age_seconds) if not cached_item.is_expired() else 0
        }
    return {
        "cache_duration": CACHE_DURATION,
        "cache": status,
        "info": "40 saniyelik cache ile saatte maksimum 90 İBB API isteği garanti edilir"
    }


@app.delete("/cache/{hat_kodu}")
def clear_cache(hat_kodu: str):
    """Belirli bir hat için cache'i temizler"""
    if hat_kodu in cache:
        del cache[hat_kodu]
        return {"message": f"{hat_kodu} için cache temizlendi"}
    return {"message": f"{hat_kodu} için cache bulunamadı"}
