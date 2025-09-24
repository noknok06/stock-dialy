// static/js/pwa-init.js を作成
class PWAManager {
  constructor() {
    this.init();
  }

  async init() {
    // Service Worker登録
    await this.registerServiceWorker();
    
    // インストールプロンプトの設定
    this.setupInstallPrompt();
    
    // ネットワーク状態の監視
    this.setupNetworkMonitoring();
  }

  async registerServiceWorker() {
    if ('serviceWorker' in navigator) {
      try {
        const registration = await navigator.serviceWorker.register('/static/sw.js', {
          scope: '/'
        });
        
        console.log('✅ Service Worker registered:', registration.scope);
        
        // 更新チェック
        registration.addEventListener('updatefound', () => {
          this.handleServiceWorkerUpdate(registration);
        });
        
        return registration;
      } catch (error) {
        console.error('❌ Service Worker registration failed:', error);
      }
    }
  }

  setupInstallPrompt() {
    let deferredPrompt = null;
    
    // beforeinstallprompt イベントをキャッチ
    window.addEventListener('beforeinstallprompt', (e) => {
      console.log('💡 PWA install prompt available');
      e.preventDefault();
      deferredPrompt = e;
      
      // インストールボタンを表示
      this.showInstallButton(deferredPrompt);
    });
    
    // インストール完了イベント
    window.addEventListener('appinstalled', (e) => {
      console.log('✅ PWA installed successfully');
      this.hideInstallButton();
      this.showToast('カブログがインストールされました！', 'success');
    });
  }

  showInstallButton(deferredPrompt) {
    const installContainer = document.getElementById('pwa-install-container');
    if (installContainer) {
      installContainer.style.display = 'block';
      
      const installBtn = document.getElementById('pwa-install-btn');
      installBtn?.addEventListener('click', async () => {
        if (deferredPrompt) {
          deferredPrompt.prompt();
          const result = await deferredPrompt.userChoice;
          
          if (result.outcome === 'accepted') {
            console.log('✅ User accepted the PWA install');
          }
          
          deferredPrompt = null;
          installContainer.style.display = 'none';
        }
      });
    }
  }

  hideInstallButton() {
    const installContainer = document.getElementById('pwa-install-container');
    if (installContainer) {
      installContainer.style.display = 'none';
    }
  }

  setupNetworkMonitoring() {
    window.addEventListener('online', () => {
      this.showToast('オンラインに戻りました', 'success');
      document.body.classList.remove('offline');
    });

    window.addEventListener('offline', () => {
      this.showToast('オフラインモードです', 'warning');
      document.body.classList.add('offline');
    });
  }

  showToast(message, type = 'info') {
    // Bootstrap Toastまたは独自のトースト表示
    console.log(`📢 ${type.toUpperCase()}: ${message}`);
  }

  handleServiceWorkerUpdate(registration) {
    const newWorker = registration.installing;
    newWorker.addEventListener('statechange', () => {
      if (newWorker.state === 'installed') {
        if (navigator.serviceWorker.controller) {
          // 新しいバージョンが利用可能
          this.showUpdateNotification();
        }
      }
    });
  }

  showUpdateNotification() {
    const updateBanner = document.createElement('div');
    updateBanner.className = 'alert alert-info alert-dismissible fixed-top mx-3 mt-3';
    updateBanner.innerHTML = `
      <div class="d-flex justify-content-between align-items-center">
        <span>📱 新しいバージョンが利用可能です</span>
        <button class="btn btn-sm btn-outline-info" onclick="window.location.reload()">
          更新する
        </button>
      </div>
    `;
    document.body.appendChild(updateBanner);
  }
}

// PWAマネージャーを初期化
document.addEventListener('DOMContentLoaded', () => {
  new PWAManager();
});