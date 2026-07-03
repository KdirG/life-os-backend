const CACHE_NAME = 'lifeos-cache-v1';
const ASSETS = [
  'index.html',
  'manifest.json'
];

// Service Worker Kurulum Aşaması - Statik Varlıkları Önbellekle
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log("Service Worker: Önbellek oluşturuluyor...");
      return cache.addAll(ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Service Worker Aktivasyon Aşaması
self.addEventListener('activate', e => {
  console.log("Service Worker: Aktifleşti.");
  e.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cache => {
          if (cache !== CACHE_NAME) {
            console.log("Service Worker: Eski önbellek temizleniyor...", cache);
            return caches.delete(cache);
          }
        })
      );
    })
  );
});

// Arama Aşaması - Ağ veya Önbellek Stratejisi
self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(response => {
      return response || fetch(e.request).catch(() => {
        return new Response("Bağlantı bulunamadı ve önbellekte veri yok.", {
          status: 503,
          statusText: "Service Unavailable"
        });
      });
    })
  );
});

// --- NATIVE WEB PUSH ENTEGRASYONU ---

// Sunucudan (FastAPI) gelen anlık bildirim push sinyalini dinle
self.addEventListener('push', event => {
  console.log("Service Worker: Push bildirimi alındı.");
  let data = { title: "Life OS", message: "Yeni bir güncelleme var!" };
  
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { title: "Life OS", message: event.data.text() };
    }
  }

  const options = {
    body: data.message,
    icon: 'https://cdn-icons-png.flaticon.com/512/3249/3249915.png', // Uygulama ikonu
    badge: 'https://cdn-icons-png.flaticon.com/512/3249/3249915.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: '1'
    },
    actions: [
      { action: 'open', title: 'Uygulamayı Aç' }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Bildirime tıklandığında uygulamanın açılmasını sağla
self.addEventListener('notificationclick', event => {
  console.log("Service Worker: Bildirime tıklandı.");
  event.notification.close();

  // Bildirime tıklandığında eğer uygulama açıksa odaklan, kapalıysa ana sayfayı aç
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then(windowClients => {
      for (let i = 0; i < windowClients.length; i++) {
        const client = windowClients[i];
        if (client.url === '/' && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow('/');
      }
    })
  );
});
