// static/sw.js
const CACHE_NAME = 'kabulog-v1.0.0';
const STATIC_CACHE_NAME = 'kabulog-static-v1.0.0';

// キャッシュするリソース
const STATIC_ASSETS = [
  '/',
  '/stockdiary/',
  '/static/css/common.css',
  '/static/css/diary-theme.css',
  '/static/css/mobile-friendly.css',
  '/static/js/speed-dial.js',
  '/static/images/icon-modern.svg',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css'
];

// オフライン時のフォールバックページ
const OFFLINE_FALLBACK = '/offline/';

// インストール時の処理
self.addEventListener('install', event => {
  console.log('Service Worker: Installing...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE_NAME)
      .then(cache => {
        console.log('Service Worker: Caching static assets');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => self.skipWaiting())
  );
});

// アクティベート時の処理
self.addEventListener('activate', event => {
  console.log('Service Worker: Activating...');
  
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            if (cacheName !== CACHE_NAME && cacheName !== STATIC_CACHE_NAME) {
              console.log('Service Worker: Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => self.clients.claim())
  );
});

// フェッチ時の処理（キャッシュ戦略）
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  
  // HTMLリクエストの場合
  if (request.headers.get('Accept').includes('text/html')) {
    event.respondWith(
      networkFirstStrategy(request)
        .catch(() => caches.match(OFFLINE_FALLBACK))
    );
    return;
  }
  
  // 静的アセット（CSS, JS, 画像）の場合
  if (request.url.includes('/static/') || 
      request.url.includes('bootstrap') || 
      request.url.includes('bootstrap-icons')) {
    event.respondWith(cacheFirstStrategy(request));
    return;
  }
  
  // API リクエストの場合
  if (request.url.includes('/api/') || request.url.includes('/stockdiary/')) {
    event.respondWith(networkFirstStrategy(request));
    return;
  }
});

// ネットワーク優先戦略
async function networkFirstStrategy(request) {
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
async function cacheFirstStrategy(request) {
  const cachedResponse = await caches.match(request);
  
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(STATIC_CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    throw error;
  }
}