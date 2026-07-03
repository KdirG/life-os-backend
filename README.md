# Kişisel AI Life OS ve Otomasyon Asistanı

Bu proje, $0 bütçe ile bulut üzerinde çalışan bir backend, mobil öncelikli PWA arayüzü, GitHub üzerinden senkronize olan Obsidian veritabanı ve yerel bilgisayarınızda çalışan bir otomasyon istemcisinden oluşan kişisel bir işletim sistemi (Life OS) altyapısı sunar.

## 🚀 Proje Mimarisi

1. **Beyin (Backend - FastAPI):** FastAPI ile yazılmıştır. Render.com veya Railway.app gibi platformların ücretsiz katmanında 7/24 çalışabilir. Google Gemini 2.5 Flash API ile entegre çalışır.
2. **Arayüz (Frontend - PWA):** Glassmorphic tasarıma sahip saf HTML5/JS ve Service Worker barındıran telefona yüklenebilir bir PWA arayüzüdür. GitHub Pages veya Netlify/Vercel üzerinde ücretsiz barındırılabilir.
3. **Veritabanı (Obsidian - GitHub):** Verileriniz doğrudan GitHub reposundaki markdown (`.md`) dosyalarına yazılır. Bu repoyu bilgisayarınızdaki Obsidian ile eşleyerek tüm verilere lokalde sahip olabilirsiniz.
4. **Otomasyon (PC Node):** Bilgisayarınızda çalışan, uTorrent veya jDownloader gibi hantal programlara ihtiyaç duymadan torrent (libtorrent), video (yt-dlp) ve normal dosyaları indiren, Steam oyunlarını uzaktan yükleyen bir Python scriptidir.

---

## 🛠️ Kurulum Adımları

### 1. Depo (Obsidian Vault) Hazırlığı
- GitHub üzerinde yeni bir **private (özel)** repository oluşturun (örn: `MyLifeOSVault`).
- İçerisine `Yemek_Log.md` ve `Hedefler.md` adında iki adet boş dosya oluşturup commit edin.

### 2. Backend (FastAPI) Kurulumu
1. Bu klasörü sunucunuza veya yerel bilgisayarınıza alın.
2. `.env.example` dosyasının adını `.env` olarak değiştirin ve ilgili alanları doldurun:
   - **GEMINI_API_KEY:** [Google AI Studio](https://aistudio.google.com/) üzerinden ücretsiz API anahtarı alın.
   - **GITHUB_TOKEN:** GitHub Developer Settings -> Personal Access Tokens (Classic) kısmından `repo` yetkisine sahip bir token oluşturun.
   - **GITHUB_REPO_OWNER / NAME:** GitHub kullanıcı adınız ve oluşturduğunuz reponun adı.
   - **NTFY_TOPIC:** Bildirimlerin gelmesini istediğiniz ntfy.sh kanalı (örn: `life_os_mysecret_channel`).
3. Gerekli kütüphaneleri kurun:
   ```bash
   pip install -r requirements.txt
   ```
   *(Eğer dependencies listesini doğrudan kurmak isterseniz: `pip install fastapi uvicorn google-generativeai requests python-dotenv pydantic jinja2 multipart`)*
4. Backend'i yerelde başlatın:
   ```bash
   uvicorn main:app --reload
   ```

### 3. Frontend (PWA) Yapılandırması
- `index.html` dosyası içindeki `const BACKEND_URL = ...` satırına FastAPI backend'inizin kurulu olduğu adresi girin (örn: Render veya Railway üzerindeki URL'niz).
- Dosyaları (index.html, manifest.json, sw.js) ücretsiz olarak GitHub Pages, Netlify veya Vercel'e yükleyin.
- Mobil tarayıcınızdan siteye gidip tarayıcı ayarlarından **"Ana Ekrana Ekle"** butonuna basarak uygulamayı telefonunuza yükleyin.

### 4. Telefon Bildirimleri (ntfy.sh)
- Telefonunuza App Store veya Google Play Store'dan ücretsiz **ntfy** uygulamasını indirin.
- Uygulama içinden `.env` dosyasında belirlediğiniz `NTFY_TOPIC` kanalını takibe alın. Bildirimleriniz anında telefonunuza push bildirimi olarak gelecektir.

### 5. PC Node Kurulumu
- Bilgisayarınızda python kurulu olduğundan emin olun.
- Gerekli kütüphaneleri kurun:
  ```bash
  pip install requests libtorrent yt-dlp
  ```
- `pc_node.py` dosyası içindeki `BACKEND_URL` parametresine FastAPI backend adresinizi girin.
- Terminalden scripti çalıştırın:
  ```bash
  python pc_node.py
  ```

---

## 🌟 Kullanım Senaryoları

* **Besin Girişi:**
  - Sesli veya metin olarak: *"Bugün 300 gram tavuk göğsü, 150 gram pilav yedim"*
  - **Sonuç:** Gemini besinleri algılar, kalorilerini ve makrolarını hesaplar ve GitHub üzerindeki `Yemek_Log.md` dosyasını otomatik günceller.
* **Hedef Girişi:**
  - Sesli veya metin olarak: *"Sporda bacak antrenmanımı bitirdim, ayrıca matematikten de 1.5 saat soru çözdüm"*
  - **Sonuç:** `Hedefler.md` dosyasındaki ilgili yapılacaklar güncellenerek tamamlandı işaretlenir.
* **İndirme ve Otomasyon:**
  - Metin olarak: *"GTA 5 oyununu kur"* veya magnet linkini gönderin.
  - **Sonuç:** PC Node açık olduğu anda komut kuyruktan çekilir ve indirme işlemi başlatılır veya Steam tetiklenir.
* **No-Code Dinamik Özellik Ekleme:**
  - Metin olarak: *"Bugün 2 litre su içtim"*
  - **Sonuç:** Gemini bunu yeni bir kategori olarak algılar, repoda `Su_Takibi.md` adında bir dosya yoksa oluşturur ve altına log satırını tarih/saat ile yazar.
