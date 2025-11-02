// static/sw.js
const CACHE_NAME = 'kabulog-v1.0.3';  // バージョンアップ
const STATIC_CACHE_NAME = 'kabulog-static-v1.0.3';

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
  // console.log('Service Worker: Installing...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE_NAME)
      .then(cache => {
        // console.log('Service Worker: Caching static assets');
        return cache.addAll(STATIC_ASSETS);
      })
      .catch(err => {
        console.error('Service Worker: Cache failed:', err);
      })
      .then(() => self.skipWaiting())
  );
});

// アクティベート時の処理
self.addEventListener('activate', event => {
  // console.log('Service Worker: Activating...');
  
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            if (cacheName !== CACHE_NAME && cacheName !== STATIC_CACHE_NAME) {
              // console.log('Service Worker: Deleting old cache:', cacheName);
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
  
  // 🔧 POSTリクエストはキャッシュしない（そのまま通す）
  if (request.method !== 'GET') {
    event.respondWith(fetch(request));
    return;
  }
  
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
  
  // API リクエストの場合（GETのみ）
  if (request.url.includes('/api/') || request.url.includes('/stockdiary/')) {
    event.respondWith(networkFirstStrategy(request));
    return;
  }
  
  // デフォルト：ネットワーク優先
  event.respondWith(fetch(request));
});

// ネットワーク優先戦略（GETリクエストのみキャッシュ）
async function networkFirstStrategy(request) {
  try {
    const networkResponse = await fetch(request);
    
    // 🔧 成功したGETリクエストのみキャッシュ
    if (networkResponse.ok && request.method === 'GET') {
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
    
    if (networkResponse.ok && request.method === 'GET') {
      const cache = await caches.open(STATIC_CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    throw error;
  }
}

// プッシュ通知受信
self.addEventListener('push', event => {
  // console.log('Push notification received');
  
  const data = event.data ? event.data.json() : {};
  
  const options = {
    body: data.message || '新しい通知があります',
    icon: data.icon || '/static/images/icon-192.png',
    badge: data.badge || '/static/images/badge-72.png',
    vibrate: [200, 100, 200],
    tag: data.tag || 'notification',
    data: {
      url: data.url || '/',
      notification_id: data.notification_id
    },
    actions: [
      { action: 'open', title: '開く' },
      { action: 'close', title: '閉じる' }
    ],
    requireInteraction: false,
    renotify: true,
  };

  event.waitUntil(
    self.registration.showNotification(
      data.title || 'カブログ',
      options
    )
  );
});

// 通知クリック時
self.addEventListener('notificationclick', event => {
  // console.log('Notification clicked');
  event.notification.close();
  
  const urlToOpen = event.notification.data.url || '/';
  const notificationId = event.notification.data.notification_id;

  if (event.action === 'open' || !event.action) {
    event.waitUntil(
      clients.matchAll({ type: 'window', includeUncontrolled: true })
        .then(clientList => {
          for (const client of clientList) {
            if (client.url.includes(urlToOpen) && 'focus' in client) {
              return client.focus();
            }
          }
          if (clients.openWindow) {
            return clients.openWindow(urlToOpen);
          }
        })
        .then(() => {
          if (notificationId) {
            return fetch(`/api/notifications/${notificationId}/click/`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' }
            }).catch(err => console.error('Failed to mark as clicked:', err));
          }
        })
    );
  }
});

// バックグラウンド同期
self.addEventListener('sync', event => {
  if (event.tag === 'sync-notifications') {
    event.waitUntil(syncNotifications());
  }
});

async function syncNotifications() {
  try {
    const response = await fetch('/api/notifications/logs/?unread=true');
    const data = await response.json();
    
    if (data.unread_count > 0) {
      self.registration.showNotification('カブログ', {
        body: `${data.unread_count}件の未読通知があります`,
        icon: '/static/images/icon-192.png',
        badge: '/static/images/badge-72.png',
        data: { url: '/notifications/' }
      });
    }
  } catch (error) {
    console.error('Sync failed:', error);
  }
}