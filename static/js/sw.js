// static/sw.js を作成
const CACHE_NAME = 'kabulog-v1.0.0';
const STATIC_CACHE = 'kabulog-static-v1.0.0';

// キャッシュするリソース
const STATIC_ASSETS = [
  '/',
  '/stockdiary/',
  '/static/css/common.css',
  '/static/css/diary-theme.css', 
  '/static/css/mobile-friendly.css',
  '/static/js/speed-dial.js',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css'
];

const OFFLINE_FALLBACK = '/offline/';

// インストール
self.addEventListener('install', (event) => {
  console.log('🔧 Service Worker: Installing...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('📦 Service Worker: Caching static assets');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => {
        console.log('✅ Service Worker: Installation complete');
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error('❌ Service Worker: Installation failed', error);
      })
  );
});

// アクティベート
self.addEventListener('activate', (event) => {
  console.log('🚀 Service Worker: Activating...');
  
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== CACHE_NAME && cacheName !== STATIC_CACHE) {
              console.log('🗑️ Service Worker: Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('✅ Service Worker: Activation complete');
        return self.clients.claim();
      })
  );
});

// フェッチ（ネットワーク戦略）
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  
  // HTMLページ
  if (request.headers.get('Accept')?.includes('text/html')) {
    event.respondWith(
      networkFirst(request)
        .catch(() => caches.match(OFFLINE_FALLBACK) || new Response('オフラインです'))
    );
    return;
  }
  
  // 静的アセット（CSS, JS, 画像）
  if (request.url.includes('/static/') || 
      request.url.includes('bootstrap') || 
      request.url.includes('fonts.googleapis.com')) {
    event.respondWith(cacheFirst(request));
    return;
  }
  
  // API リクエスト
  if (request.url.includes('/api/') || request.url.includes('/stockdiary/')) {
    event.respondWith(networkFirst(request));
    return;
  }
});

// ネットワーク優先戦略
async function networkFirst(request) {
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    throw error;
  }
}

// キャッシュ優先戦略
async function cacheFirst(request) {
  const cachedResponse = await caches.match(request);
  
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    throw error;
  }
}