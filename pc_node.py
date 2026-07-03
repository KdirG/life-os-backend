import os
import time
import requests

# Yapılandırmalar
BACKEND_URL = "http://localhost:8000"  # Bulut FastAPI adresi (örn: https://app.onrender.com)
DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "LifeOS")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# libtorrent kütüphanesini içe aktarmayı dene
try:
    import libtorrent as lt
except ImportError:
    lt = None
    print("[UYARI] 'libtorrent' kütüphanesi yüklü değil. Torrent/Magnet indirmeleri çalışmayacaktır.")
    print("Yüklemek için: pip install libtorrent (Veya Python sürümünüz için uyumlu binary bulun)")

# yt-dlp kütüphanesini içe aktarmayı dene
try:
    import yt_dlp
except ImportError:
    yt_dlp = None
    print("[UYARI] 'yt-dlp' kütüphanesi yüklü değil. Sosyal medya videoları (Youtube vb.) indirilemeyecektir.")
    print("Yüklemek için: pip install yt-dlp")


# --- Steam Entegrasyonu ---
def handle_steam_install(app_id: str) -> bool:
    """Steam AppID üzerinden yerel bilgisayarda indirmeyi tetikler."""
    print(f"[STEAM] Game AppID {app_id} kurulumu tetikleniyor...")
    try:
        # Steam protokol handler'ını çalıştır
        os.startfile(f"steam://install/{app_id}")
        return True
    except Exception as e:
        print(f"[STEAM HATASI] {e}")
        return False

# --- URL ve Video İndirici (Requests & yt-dlp) ---
def handle_url_download(url: str) -> bool:
    """URL normal bir dosya ise requests ile, medya/video sitesi ise yt-dlp ile indirir."""
    print(f"[İNDİRME] URL tetiklendi: {url}")
    
    # 1. Medya Siteleri İçin yt-dlp (YouTube, Twitter vb.)
    is_media_site = any(domain in url for domain in ["youtube.com", "youtu.be", "twitter.com", "x.com", "vimeo.com"])
    
    if is_media_site:
        if not yt_dlp:
            print("[HATA] Medya indirme isteği geldi fakat 'yt-dlp' yüklü değil!")
            return False
            
        print("[İNDİRME] yt-dlp ile video indiriliyor...")
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
            'format': 'best'
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            print("[İNDİRME] Medya indirmesi tamamlandı.")
            return True
        except Exception as e:
            print(f"[YT-DLP HATASI] {e}")
            return False
            
    # 2. Standart Dosya İndirme (Requests)
    else:
        try:
            # URL'den dosya adını ayıkla
            file_name = url.split('/')[-1].split('?')[0]
            if not file_name or '.' not in file_name:
                file_name = "downloaded_file"
                
            local_filename = os.path.join(DOWNLOAD_DIR, file_name)
            
            print(f"[İNDİRME] Dosya indiriliyor: {local_filename}")
            
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            
            print(f"[İNDİRME] Dosya başarıyla kaydedildi: {local_filename}")
            return True
        except Exception as e:
            print(f"[İNDİRME HATASI] {e}")
            return False

# --- Torrent & Magnet İndirici (Libtorrent) ---
def handle_torrent_download(magnet_link: str) -> bool:
    """Magnet linkini libtorrent kullanarak arka planda indirir."""
    if not lt:
        print("[HATA] libtorrent yüklü olmadığı için magnet indirilemedi.")
        return False
        
    print(f"[TORRENT] Magnet bağlantısı başlatılıyor: {magnet_link}")
    
    try:
        ses = lt.session()
        # Standart DHT portlarını dinle
        ses.listen_on(6881, 6891)
        
        # İndirme ayarları
        params = {
            'save_path': DOWNLOAD_DIR,
            'storage_mode': lt.storage_mode_t.storage_mode_sparse
        }
        
        # Magnet linkini kuyruğa ekle
        handle = lt.add_magnet_uri(ses, magnet_link, params)
        print("[TORRENT] Metadata bekleniyor (Bu işlem birkaç dakika sürebilir)...")
        
        # Metadata'nın gelmesini bekle
        timeout_counter = 0
        while not handle.has_metadata():
            time.sleep(1)
            timeout_counter += 1
            if timeout_counter > 300: # 5 dakika zaman aşımı
                print("[TORRENT HATA] Zaman aşımı: Metadata çekilemedi.")
                return False
                
        print(f"[TORRENT] İsim: {handle.name()}")
        print("[TORRENT] Dosya indirilmeye başlanıyor...")
        
        # İndirme durumunu takip et
        while handle.status().state != lt.torrent_status.seeding:
            s = handle.status()
            print(f"Durum: {s.state} | İlerleme: %{s.progress * 100:.2f} | "
                  f"İndirme Hızı: {s.download_rate / 1024:.1f} KB/s | "
                  f"Eşler: {s.num_peers}")
            time.sleep(5)
            
        print(f"[TORRENT] İndirme tamamlandı! Dosyalar klasörde: {DOWNLOAD_DIR}")
        return True
    except Exception as e:
        print(f"[TORRENT HATASI] {e}")
        return False

# --- Wake-on-LAN (Modüler Genişletme) ---
def handle_wake_on_lan():
    """Gelecekte bilgisayarı uzaktan ağ üzerinden açmak amacıyla eklenecek mantıksal alan."""
    pass

# --- Poller / Sorgulayıcı Döngü ---
def start_polling():
    print("----------------------------------------")
    print(f"Life OS PC Node Çalışıyor...")
    print(f"İndirme Konumu: {DOWNLOAD_DIR}")
    print(f"Backend Adresi: {BACKEND_URL}")
    print("Komutlar bekleniyor...")
    print("----------------------------------------")
    
    while True:
        try:
            # Bekleyen görevleri sorgula
            response = requests.get(f"{BACKEND_URL}/api/pc/tasks", timeout=5)
            if response.status_code == 200:
                tasks = response.json()
                for task in tasks:
                    task_id = task["id"]
                    action = task["action"]
                    payload = task["payload"]
                    
                    print(f"\n[YENİ GÖREV] ID: {task_id} | Eylem: {action}")
                    
                    success = False
                    if action == "steam_install":
                        success = handle_steam_install(payload)
                    elif action == "download_url":
                        success = handle_url_download(payload)
                    elif action == "download_torrent":
                        success = handle_torrent_download(payload)
                        
                    # Durumu sunucuya rapor et
                    status_payload = {"status": "completed" if success else "failed"}
                    requests.post(f"{BACKEND_URL}/api/pc/tasks/{task_id}/status", json=status_payload, timeout=5)
                    print(f"[RAPOR] Görev durumu sunucuya gönderildi: {status_payload['status']}")
                    
        except requests.exceptions.ConnectionError:
            # Sunucuya erişilemiyorsa sessiz kal
            pass
        except Exception as e:
            print(f"[POLL HATASI] {e}")
            
        time.sleep(10)  # Her 10 saniyede bir sorgula

if __name__ == "__main__":
    start_polling()
