// Service Workerの更新検知と強制リロード
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      const registration = await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
        updateViaCache: 'none'
      });
      
      // 🆕 更新チェック（1時間ごと）
      setInterval(() => {
        registration.update();
      }, 60 * 60 * 1000);
      
      // 🆕 新しいService Workerが待機中の場合、ユーザーに通知
      registration.addEventListener('updatefound', () => {
        const newWorker = registration.installing;
        
        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
            // 新しいバージョンが利用可能
            if (confirm('新しいバージョンが利用可能です。更新しますか？')) {
              newWorker.postMessage({ type: 'SKIP_WAITING' });
              window.location.reload();
            }
          }
        });
      });
      
      // 🆕 Service Workerがアクティブになったらリロード
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        window.location.reload();
      });
      
    } catch (error) {
      console.error('SW registration failed:', error);
    }
  });
}