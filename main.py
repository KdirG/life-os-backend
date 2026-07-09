import os
import json
import base64
import asyncio
from typing import Optional, List, Dict
import requests
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from pywebpush import webpush, WebPushException

# Çevresel değişkenleri yükle
load_dotenv()

app = FastAPI(title="Life OS Brain API")

# CORS yapılandırması (PWA frontend erişimi için)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sistem Ayarları
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO_OWNER = os.getenv("GITHUB_REPO_OWNER")
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME")
NTFY_TOPIC = os.getenv("NTFY_TOPIC")  # ntfy.sh üzerinde benzersiz bir konu adı
PWA_URL = os.getenv("PWA_URL", "http://localhost:8000")  # Dağıtılan PWA arayüzünün URL'si
CRON_SECRET = os.getenv("CRON_SECRET", "life_os_secure_cron_token_123")  # Dış cron tetikleyicisi için şifre

# VAPID Anahtarlarını Otomatik Oluştur / Yükle
def ensure_vapid_keys():
    vapid_pub = os.getenv("VAPID_PUBLIC_KEY")
    vapid_priv = os.getenv("VAPID_PRIVATE_KEY")
    if not vapid_pub or not vapid_priv:
        print("[BİLGİ] VAPID anahtarları bulunamadı. Otomatik olarak oluşturuluyor...")
        try:
            from cryptography.hazmat.primitives.asymmetric import ec
            private_key = ec.generate_private_key(ec.SECP256R1())
            private_bytes = private_key.private_numbers().private_value.to_bytes(32, byteorder='big')
            public_numbers = private_key.public_key().public_numbers()
            public_bytes = b'\x04' + public_numbers.x.to_bytes(32, byteorder='big') + public_numbers.y.to_bytes(32, byteorder='big')
            
            vapid_priv = base64.urlsafe_b64encode(private_bytes).decode('utf-8').rstrip('=')
            vapid_pub = base64.urlsafe_b64encode(public_bytes).decode('utf-8').rstrip('=')
            
            # .env dosyasına yaz
            if os.path.exists(".env"):
                with open(".env", "a") as f:
                    f.write(f"\nVAPID_PUBLIC_KEY={vapid_pub}\nVAPID_PRIVATE_KEY={vapid_priv}\n")
                print("[BİLGİ] VAPID anahtarları .env dosyasına başarıyla eklendi.")
            else:
                with open(".env", "w") as f:
                    f.write(f"VAPID_PUBLIC_KEY={vapid_pub}\nVAPID_PRIVATE_KEY={vapid_priv}\n")
                    
            os.environ["VAPID_PUBLIC_KEY"] = vapid_pub
            os.environ["VAPID_PRIVATE_KEY"] = vapid_priv
        except Exception as e:
            print(f"[HATA] VAPID anahtarları oluşturulamadı: {e}")
    return vapid_pub, vapid_priv

VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY = ensure_vapid_keys()

# Bellek içi görev kuyruğu (PC Node long-polling ile bu listeyi okur)
pc_task_queue: List[Dict] = []

# --- Structured Output Pydantic Şemaları ---
class FoodItem(BaseModel):
    name: str = Field(description="Besin maddesinin adı (örn. Tavuk Göğsü)")
    weight_g: float = Field(description="Gram veya adet cinsinden miktar")
    calories: float = Field(description="Tahmin edilen kalori miktarı (kcal)")
    protein: float = Field(description="Tahmin edilen protein değeri (g)")
    fat: float = Field(description="Tahmin edilen yağ değeri (g)")
    carbs: float = Field(description="Tahmin edilen karbonhidrat değeri (g)")

class ParsedIntent(BaseModel):
    intent: str = Field(description="Niyet sınıflandırması: 'nutrition', 'goal_update', 'pc_command', 'custom_log'")
    extracted_text: str = Field(description="Ham ses veya metinden çözümlenen komut metni.")
    nutrition_items: Optional[List[FoodItem]] = Field(None, description="Tüketilen besinlerin listesi ve tahmini makro değerleri.")
    goal_query: Optional[str] = Field(None, description="Hedef takip güncellenecek veri detayı.")
    updated_file_content: Optional[str] = Field(None, description="Güncellenmiş markdown dosya içeriği (Client-side tarafından hazırlanır).")
    pc_action: Optional[str] = Field(None, description="PC eylemi: 'steam_install', 'download_url', 'download_torrent'")
    pc_payload: Optional[str] = Field(None, description="Steam AppID, indirme linki veya Torrent magnet linki.")
    custom_file_name: Optional[str] = Field(None, description="Dinamik oluşturulacak markdown dosyasının adı (örn: Su_Takibi.md)")
    custom_content: Optional[str] = Field(None, description="Dosyaya eklenecek markdown satırı (tarih ve saati içermelidir).")

# Web Push Abonelik Şeması
class SubscriptionModel(BaseModel):
    endpoint: str
    keys: Dict[str, str]

# --- GitHub API Helpers ---
def get_github_file(
    path: str,
    gh_token: Optional[str] = None,
    gh_owner: Optional[str] = None,
    gh_repo: Optional[str] = None
) -> tuple[str, Optional[str]]:
    """Belirtilen pathteki dosyayı GitHub reposundan çeker. Dosya içeriğini ve SHA değerini döndürür."""
    token = gh_token if gh_token else GITHUB_TOKEN
    owner = gh_owner if gh_owner else GITHUB_REPO_OWNER
    repo = gh_repo if gh_repo else GITHUB_REPO_NAME

    if not token or not owner or not repo:
        print("[HATA] GitHub API ayarları (headers veya .env) eksik!")
        return "", None
        
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]
    elif r.status_code == 404:
        return "", None
    else:
        print(f"[GITHUB API HATA] Durum kodu: {r.status_code}, Cevap: {r.text}")
        return "", None

def update_github_file(
    path: str,
    content: str,
    sha: Optional[str] = None,
    message: str = "Life OS Güncellemesi",
    gh_token: Optional[str] = None,
    gh_owner: Optional[str] = None,
    gh_repo: Optional[str] = None
) -> bool:
    """Belirtilen pathteki dosyayı GitHub reposunda günceller veya yoksa oluşturur."""
    token = gh_token if gh_token else GITHUB_TOKEN
    owner = gh_owner if gh_owner else GITHUB_REPO_OWNER
    repo = gh_repo if gh_repo else GITHUB_REPO_NAME

    if not token or not owner or not repo:
        print("[HATA] GitHub API ayarları (headers veya .env) eksik!")
        return False
        
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8")
    }
    if sha:
        payload["sha"] = sha
        
    r = requests.put(url, json=payload, headers=headers)
    if r.status_code in [200, 201]:
        return True
    else:
        print(f"[GITHUB API YAZMA HATASI] Durum: {r.status_code}, Cevap: {r.text}")
        return False

# --- ntfy.sh & Web Push Notification ---
def send_push_notification(
    title: str,
    message: str,
    gh_token: Optional[str] = None,
    gh_owner: Optional[str] = None,
    gh_repo: Optional[str] = None
):
    """ntfy.sh ve tarayıcı native Web Push üzerinden telefona bildirim gönderir."""
    # 1. ntfy.sh Bildirimi (Opsiyonel)
    if NTFY_TOPIC:
        url = f"https://ntfy.sh/{NTFY_TOPIC}"
        headers = {
            "Title": title.encode('utf-8'),
            "Priority": "default",
            "Click": PWA_URL
        }
        try:
            requests.post(url, data=message.encode('utf-8'), headers=headers, timeout=5)
        except Exception as e:
            print(f"[NTFY BİLDİRİM HATASI] {e}")

    # 2. Native Web Push Bildirimi
    if not VAPID_PRIVATE_KEY:
        print("[WEB PUSH] VAPID private key eksik, web push gönderilmedi.")
        return
        
    path = "Subscribers.json"
    content, _ = get_github_file(path, gh_token=gh_token, gh_owner=gh_owner, gh_repo=gh_repo)
    if not content:
        return
        
    try:
        subs = json.loads(content)
    except Exception as e:
        print(f"[WEB PUSH ERROR] Aboneler okunamadı: {e}")
        return
        
    payload = json.dumps({"title": title, "message": message})
    broken_subs = []
    
    for sub in subs:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": "mailto:admin@lifeos.local"},
            )
            print("[WEB PUSH] Bir aboneye başarıyla push gönderildi.")
        except WebPushException as ex:
            print(f"[WEB PUSH UYARI] Bildirim gönderilemedi: {ex}")
            if ex.response is not None and ex.response.status_code in [404, 410]:
                broken_subs.append(sub)
                  
    if broken_subs:
        content, sha = get_github_file(path)
        try:
            current_subs = json.loads(content)
            updated_subs = [s for s in current_subs if s not in broken_subs]
            update_github_file(path, json.dumps(updated_subs, indent=2), sha, message="Geçersiz aboneleri temizle")
            print(f"[WEB PUSH] {len(broken_subs)} geçersiz abone temizlendi.")
        except Exception as e:
            print(f"[WEB PUSH] Temizleme hatası: {e}")

# --- API Uç Noktaları ---

@app.post("/api/process")
async def process_user_input(
    result: ParsedIntent,
    x_github_token: Optional[str] = Header(None),
    x_github_owner: Optional[str] = Header(None),
    x_github_repo: Optional[str] = Header(None)
):
    """Telefon tarafından Gemini ile çözümlenmiş hazır JSON nesnesini alır ve işler."""
    
    if result.intent == "nutrition":
        if not result.nutrition_items:
            raise HTTPException(status_code=400, detail="Besin öğeleri ayrıştırılamadı veya tahmin edilemedi.")
            
        path = "Yemek_Log.md"
        content, sha = get_github_file(path, gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
        
        import datetime
        today_str = datetime.date.today().isoformat()
        
        log_line = ""
        day_calories, day_protein, day_fat, day_carbs = 0.0, 0.0, 0.0, 0.0
        
        for f in result.nutrition_items:
            log_line += f"\n- [x] {datetime.datetime.now().strftime('%H:%M')} - {f.weight_g}g {f.name} ({f.calories} kcal | P: {f.protein}g | Y: {f.fat}g | K: {f.carbs}g)"
            day_calories += f.calories
            day_protein += f.protein
            day_fat += f.fat
            day_carbs += f.carbs
            
        import re
        if today_str not in content:
            cumulative_calories = day_calories
            cumulative_protein = day_protein
            cumulative_fat = day_fat
            cumulative_carbs = day_carbs
            
            new_content = f"{content.strip()}\n\n## {today_str}{log_line}\n---\n**Günlük Toplam:** {cumulative_calories:.1f} kcal | Protein: {cumulative_protein:.1f}g | Yağ: {cumulative_fat:.1f}g | Karbonhidrat: {cumulative_carbs:.1f}g"
        else:
            parts = content.split(f"## {today_str}")
            header = parts[0] + f"## {today_str}"
            rest = parts[1]
            body_parts = rest.split("---")
            old_entries = body_parts[0]
            
            old_total_text = body_parts[1] if len(body_parts) > 1 else ""
            old_cal = re.findall(r"Günlük Toplam:\*\*\s*([\d\.]+)\s*kcal", old_total_text)
            old_prot = re.findall(r"Protein:\s*([\d\.]+)g", old_total_text)
            old_fat = re.findall(r"Yağ:\s*([\d\.]+)g", old_total_text)
            old_carb = re.findall(r"Karbonhidrat:\s*([\d\.]+)g", old_total_text)
            
            val_cal = float(old_cal[0]) if old_cal else 0.0
            val_prot = float(old_prot[0]) if old_prot else 0.0
            val_fat = float(old_fat[0]) if old_fat else 0.0
            val_carb = float(old_carb[0]) if old_carb else 0.0
            
            cumulative_calories = val_cal + day_calories
            cumulative_protein = val_prot + day_protein
            cumulative_fat = val_fat + day_fat
            cumulative_carbs = val_carb + day_carbs
            
            updated_entries = old_entries.strip() + log_line
            new_total = f"\n---\n**Günlük Toplam:** {cumulative_calories:.1f} kcal | Protein: {cumulative_protein:.1f}g | Yağ: {cumulative_fat:.1f}g | Karbonhidrat: {cumulative_carbs:.1f}g"
            
            new_content = header + "\n" + updated_entries + new_total
            if len(body_parts) > 2:
                new_content += "---" + "---".join(body_parts[2:])
                
        update_github_file(path, new_content, sha, message=f"Yemek eklendi: {result.extracted_text}", gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
        
        food_summary = ", ".join([f"{f.weight_g}g {f.name}" for f in result.nutrition_items])
        send_push_notification(
            "Yemek Eklendi 🍎", 
            f"{food_summary} (+{day_calories:.0f} kcal)\n"
            f"Günlük Toplam: {cumulative_calories:.0f} kcal | P: {cumulative_protein:.0f}g | Y: {cumulative_fat:.0f}g | K: {cumulative_carbs:.0f}g",
            gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo
        )
        return {"status": "success", "intent": "nutrition", "data": result.nutrition_items}
        
    elif result.intent == "goal_update":
        if not result.updated_file_content:
            raise HTTPException(status_code=400, detail="Güncellenmiş hedef belgesi bulunamadı.")
            
        path = "Hedefler.md"
        _, sha = get_github_file(path, gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
        
        update_github_file(path, result.updated_file_content, sha, message=f"Hedef güncellendi: {result.goal_query}", gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
        send_push_notification("Life OS Hedef Güncelleme", f"Hedef güncellendi: {result.goal_query}", gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
        return {"status": "success", "intent": "goal_update"}
        
    elif result.intent == "pc_command":
        import uuid
        task = {
            "id": str(uuid.uuid4()),
            "action": result.pc_action,
            "payload": result.pc_payload,
            "status": "pending"
        }
        pc_task_queue.append(task)
        send_push_notification("Life OS PC Otomasyonu", f"PC kuyruğuna eklendi: {result.pc_action}", gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
        return {"status": "success", "intent": "pc_command", "task": task}
        
    elif result.intent == "custom_log":
        path = result.custom_file_name
        content, sha = get_github_file(path, gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
        
        import datetime
        today_str = datetime.date.today().isoformat()
        
        if not content:
            new_content = f"# {path.replace('.md', '')}\n\n## {today_str}\n{result.custom_content}"
        else:
            if today_str not in content:
                new_content = f"{content.strip()}\n\n## {today_str}\n{result.custom_content}"
            else:
                new_content = content.replace(f"## {today_str}", f"## {today_str}\n{result.custom_content}")
                
        update_github_file(path, new_content, sha, message=f"Özel Log Eklendi: {path}", gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
        send_push_notification("Life OS Özel Log", f"{path} dosyasına veri yazıldı.", gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
        return {"status": "success", "intent": "custom_log", "file": path}
        
    return {"status": "unknown"}

@app.get("/api/file/{filename}")
def get_file_content(
    filename: str,
    x_github_token: Optional[str] = Header(None),
    x_github_owner: Optional[str] = Header(None),
    x_github_repo: Optional[str] = Header(None)
):
    """GitHub'dan belirtilen dosyanın içeriğini okur (PWA istemcisinin alabilmesi için)."""
    if filename not in ["Hedefler.md", "Yemek_Log.md", "Aliskanliklar.md", "Mufredat.md"]:
        raise HTTPException(status_code=403, detail="Erişim engellendi.")
    content, _ = get_github_file(filename, gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
    return {"content": content}

class FileUpdateModel(BaseModel):
    content: str
    message: Optional[str] = "Dosya güncellendi"

@app.post("/api/file/{filename}")
def save_file_content(
    filename: str,
    payload: FileUpdateModel,
    x_github_token: Optional[str] = Header(None),
    x_github_owner: Optional[str] = Header(None),
    x_github_repo: Optional[str] = Header(None)
):
    """GitHub'daki dosya içeriğini doğrudan günceller (PWA'den gelen düzenleme/silmeler için)."""
    if filename not in ["Hedefler.md", "Yemek_Log.md", "Aliskanliklar.md", "Mufredat.md"]:
        raise HTTPException(status_code=403, detail="Erişim engellendi.")
    _, sha = get_github_file(filename, gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
    success = update_github_file(filename, payload.content, sha, message=payload.message, gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
    if not success:
        raise HTTPException(status_code=500, detail="Dosya güncellenirken GitHub hatası oluştu.")
    
    if filename == "Yemek_Log.md":
        send_push_notification("Life OS Güncelleme 📝", "Yemek günlüğü başarıyla güncellendi.", gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
    elif filename == "Aliskanliklar.md":
        send_push_notification("Alışkanlık Güncellendi ✅", "Günlük alışkanlık durumunuz kaydedildi.", gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
    elif filename == "Mufredat.md":
        send_push_notification("Müfredat Güncellendi 📚", "Ders çalışma müfredatınız güncellendi.", gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
        
    return {"status": "success"}

# --- PWA Web Push Abone Olma Endpoint'leri ---

@app.get("/api/vapid-public-key")
def get_vapid_public_key():
    return {"public_key": VAPID_PUBLIC_KEY}

@app.post("/api/subscribe")
def subscribe_client(
    subscription: SubscriptionModel,
    x_github_token: Optional[str] = Header(None),
    x_github_owner: Optional[str] = Header(None),
    x_github_repo: Optional[str] = Header(None)
):
    path = "Subscribers.json"
    content, sha = get_github_file(path, gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
    
    try:
        subs = json.loads(content) if content else []
    except:
        subs = []
        
    sub_dict = subscription.dict()
    
    if sub_dict not in subs:
        subs.append(sub_dict)
        update_github_file(path, json.dumps(subs, indent=2), sha, message="Yeni PWA abonesi eklendi", gh_token=x_github_token, gh_owner=x_github_owner, gh_repo=x_github_repo)
        print("[WEB PUSH] Yeni bir abone Subscribers.json dosyasına yazıldı.")
        
    return {"status": "subscribed"}

# --- PC Node Long-Polling Endpoint'leri ---

@app.get("/api/pc/tasks")
def get_pending_pc_tasks():
    pending = [t for t in pc_task_queue if t["status"] == "pending"]
    return pending

@app.post("/api/pc/tasks/{task_id}/status")
def update_pc_task_status(task_id: str, payload: Dict):
    for t in pc_task_queue:
        if t["id"] == task_id:
            t["status"] = payload.get("status", "completed")
            return {"status": "updated"}
    raise HTTPException(status_code=404, detail="Görev bulunamadı.")

# --- 3 Saatte Bir Çalışacak Durum Raporlama Mantığı (Gemini Bağımsız) ---
def run_daily_report_logic():
    """Yemek günlüklerini analiz eden ve yerel makro durumunu bildiren yerel python mantığı."""
    try:
        content, _ = get_github_file("Yemek_Log.md")
        import datetime
        today_str = datetime.date.today().isoformat()
        
        if today_str in content:
            import re
            parts = content.split(f"## {today_str}")
            rest = parts[1]
            body_parts = rest.split("---")
            total_text = body_parts[1] if len(body_parts) > 1 else ""
            
            old_cal = re.findall(r"Günlük Toplam:\*\*\s*([\d\.]+)\s*kcal", total_text)
            old_prot = re.findall(r"Protein:\s*([\d\.]+)g", total_text)
            old_fat = re.findall(r"Yağ:\s*([\d\.]+)g", total_text)
            old_carb = re.findall(r"Karbonhidrat:\s*([\d\.]+)g", total_text)
            
            cal = float(old_cal[0]) if old_cal else 0.0
            prot = float(old_prot[0]) if old_prot else 0.0
            fat = float(old_fat[0]) if old_fat else 0.0
            carb = float(old_carb[0]) if old_carb else 0.0
            
            report_text = f"Bugün toplam {cal:.0f} kalori aldınız.\nMakrolar: Protein {prot:.0f}g, Yağ {fat:.0f}g, Karbonhidrat {carb:.0f}g."
            send_push_notification("Life OS Günlük Makro Durumu", report_text)
            print("[CRON] Durum raporu başarıyla gönderildi.")
        else:
            send_push_notification("Life OS Hatırlatıcı", "Bugün henüz hiçbir yemek logu girmediniz. Beslenmenizi takip etmeyi unutmayın!")
            print("[CRON] Yemek logu bulunmadığı için hatırlatıcı gönderildi.")
    except Exception as e:
        print(f"[CRON HATA] Rapor gönderilemedi: {e}")

# --- Güvenli Dış Cron Tetikleyicisi Endpoint'i (Render Uyku Modu Çözümü) ---
@app.post("/api/cron")
async def trigger_cron_api(x_cron_token: Optional[str] = Header(None)):
    """cron-job.org gibi dış servislerin sunucuyu uykudan uyandırarak 3 saatlik bildirimi atmasını sağlar."""
    if not CRON_SECRET or x_cron_token != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Yetkisiz erişim. Geçersiz cron token.")
    
    # Raporu çalıştır
    run_daily_report_logic()
    return {"status": "success", "message": "Bildirim tetiklendi."}

# --- Dahili 3 Saatlik Döngü (Sunucu Uyumadığı Sürece Yedek Çalışır) ---
async def daily_report_cron_loop():
    while True:
        await asyncio.sleep(10800)  # 3 saat bekle
        run_daily_report_logic()

@app.on_event("startup")
async def startup_event():
    # Yedek döngüyü arka planda başlat
    asyncio.create_task(daily_report_cron_loop())

@app.get("/api/config")
def get_config():
    return {"ntfy_topic": NTFY_TOPIC}

@app.get("/api/ping")
def ping():
    return {"status": "alive"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
