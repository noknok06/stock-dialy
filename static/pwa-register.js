// static/js/pwa-register.js
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      console.log('🔄 Service Worker登録処理開始...');
      
      // 既存のService Workerを確認・解除
      const existingRegs = await navigator.serviceWorker.getRegistrations();
      console.log(`既存のService Worker: ${existingRegs.length}件`);
      
      for (const reg of existingRegs) {
        // スコープが /static/ の古いService Workerを解除
        if (reg.scope.includes('/static/')) {
          console.log('⚠️ 古いService Workerを解除:', reg.scope);
          await reg.unsubscribe();
          await reg.unregister();
        }
      }
      
      // 新しいService Workerをルートスコープで登録
      const registration = await navigator.serviceWorker.register('/sw.js', {
        scope: '/'
      });
      
      console.log('✅ SW registered:', registration.scope);
      
      // Service Workerの状態を監視
      if (registration.installing) {
        console.log('Service Worker: インストール中');
      } else if (registration.waiting) {
        console.log('Service Worker: 待機中');
      } else if (registration.active) {
        console.log('Service Worker: アクティブ');
      }
      
      // アクティブになるまで待機
      await navigator.serviceWorker.ready;
      console.log('✅ Service Worker準備完了');
      
      // PWAインストール可能性をチェック
      if ('getInstalledRelatedApps' in navigator) {
        const installedApps = await navigator.getInstalledRelatedApps();
        if (installedApps.length > 0) {
          console.log('✅ インストール済みアプリ:', installedApps);
        }
      }
      
    } catch (error) {
      console.error('❌ SW registration failed:', error);
      console.error('詳細:', error.message);
    }
  });
  
  // インストールプロンプトを監視
  let deferredPrompt;
  
  window.addEventListener('beforeinstallprompt', (e) => {
    console.log('💡 PWA installable!');
    e.preventDefault();
    deferredPrompt = e;
    
    // 手動でインストールボタンを表示
    showInstallButton();
  });
  
  function showInstallButton() {
    // 既存のボタンがあれば削除
    const existingBtn = document.getElementById('pwa-install-btn');
    if (existingBtn) {
      existingBtn.remove();
    }
    
    const btn = document.createElement('button');
    btn.id = 'pwa-install-btn';
    btn.innerHTML = '<i class="bi bi-download"></i> アプリをインストール';
    btn.className = 'btn btn-success position-fixed bottom-0 end-0 m-3 shadow-lg';
    btn.style.zIndex = '1050';
    
    btn.onclick = async () => {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        const result = await deferredPrompt.userChoice;
        console.log('Install result:', result.outcome);
        
        if (result.outcome === 'accepted') {
          console.log('✅ ユーザーがPWAをインストールしました');
        } else {
          console.log('❌ ユーザーがインストールを拒否しました');
        }
        
        deferredPrompt = null;
        btn.remove();
      }
    };
    
    document.body.appendChild(btn);
  }
  
  // PWAがインストールされた後
  window.addEventListener('appinstalled', (e) => {
    console.log('✅ PWAがインストールされました');
    deferredPrompt = null;
    
    const installBtn = document.getElementById('pwa-install-btn');
    if (installBtn) {
      installBtn.remove();
    }
  });
}