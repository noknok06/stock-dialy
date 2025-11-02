// static/js/pwa.js
class PWAManager {
    constructor() {
      this.deferredPrompt = null;
      this.init();
    }
  
    init() {
      // Service Worker登録
      this.registerServiceWorker();
      
      // インストールプロンプト処理
      this.setupInstallPrompt();
      
      // オンライン/オフライン状態の監視
      this.setupNetworkStatus();
      
      // アプリ更新の処理
      this.setupAppUpdate();
    }
  
    async registerServiceWorker() {
      if ('serviceWorker' in navigator) {
        try {
          const registration = await navigator.serviceWorker.register('/static/sw.js');
          // console.log('Service Worker registered:', registration);
          
          // 更新をチェック
          registration.addEventListener('updatefound', () => {
            this.showUpdateAvailable();
          });
        } catch (error) {
          console.error('Service Worker registration failed:', error);
        }
      }
    }
  
    setupInstallPrompt() {
      const installPrompt = document.getElementById('install-prompt');
      const installBtn = document.getElementById('install-btn');
      const dismissBtn = document.getElementById('install-dismiss');
  
      // インストールプロンプトイベント
      window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        this.deferredPrompt = e;
        
        // 既にインストール済みかチェック
        if (!this.isInstalled()) {
          installPrompt.style.display = 'block';
        }
      });
  
      // インストールボタンクリック
      installBtn?.addEventListener('click', async () => {
        if (this.deferredPrompt) {
          this.deferredPrompt.prompt();
          const result = await this.deferredPrompt.userChoice;
          
          if (result.outcome === 'accepted') {
            // console.log('PWA installed');
          }
          
          this.deferredPrompt = null;
          installPrompt.style.display = 'none';
        }
      });
  
      // 後でボタンクリック
      dismissBtn?.addEventListener('click', () => {
        installPrompt.style.display = 'none';
        localStorage.setItem('install-dismissed', Date.now().toString());
      });
  
      // インストール完了後
      window.addEventListener('appinstalled', () => {
        installPrompt.style.display = 'none';
        this.showToast('カブログをインストールしました！', 'success');
      });
    }
  
    setupNetworkStatus() {
      const updateNetworkStatus = () => {
        const isOnline = navigator.onLine;
        document.body.classList.toggle('is-offline', !isOnline);
        
        if (isOnline) {
          this.showToast('オンラインに戻りました', 'success', 2000);
          this.syncOfflineData();
        } else {
          this.showToast('オフラインモードです', 'warning', 3000);
        }
      };
  
      window.addEventListener('online', updateNetworkStatus);
      window.addEventListener('offline', updateNetworkStatus);
      
      // 初期状態をチェック
      updateNetworkStatus();
    }
  
    setupAppUpdate() {
      let refreshing = false;
      
      navigator.serviceWorker?.addEventListener('controllerchange', () => {
        if (refreshing) return;
        refreshing = true;
        window.location.reload();
      });
    }
  
    isInstalled() {
      return window.matchMedia('(display-mode: standalone)').matches ||
             window.navigator.standalone === true;
    }
  
    showUpdateAvailable() {
      const updateBanner = document.createElement('div');
      updateBanner.className = 'alert alert-info alert-dismissible fade show position-fixed top-0 start-0 end-0 z-index-1060';
      updateBanner.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
          <span>新しいバージョンが利用可能です</span>
          <button type="button" class="btn btn-sm btn-outline-info" onclick="window.location.reload()">
            更新
          </button>
        </div>
      `;
      document.body.appendChild(updateBanner);
    }
  
    showToast(message, type = 'info', duration = 3000) {
      const toast = document.createElement('div');
      toast.className = `toast align-items-center text-white bg-${type} border-0 position-fixed bottom-0 end-0 m-3`;
      toast.setAttribute('role', 'alert');
      toast.innerHTML = `
        <div class="d-flex">
          <div class="toast-body">${message}</div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
      `;
      
      document.body.appendChild(toast);
      const bsToast = new bootstrap.Toast(toast, { delay: duration });
      bsToast.show();
      
      toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
      });
    }
  
    async syncOfflineData() {
      // オフライン時に蓄積されたデータを同期
      // 実装は段階2で詳細化
      // console.log('Syncing offline data...');
    }
  }
  
  // PWAマネージャーを初期化
  document.addEventListener('DOMContentLoaded', () => {
    new PWAManager();
  });