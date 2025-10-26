// static/pwa-register.js
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      console.log('🔄 Service Worker登録処理開始...');
      
      // ブラウザ判定
      const userAgent = navigator.userAgent;
      const isSafari = /^((?!chrome|android).)*safari/i.test(userAgent);
      const isIOS = /iPhone|iPad|iPod/.test(userAgent);
      
      console.log(`ブラウザ: Safari=${isSafari}, iOS=${isIOS}`);
      
      // 既存のService Workerを確認
      const existingRegs = await navigator.serviceWorker.getRegistrations();
      console.log(`既存のService Worker: ${existingRegs.length}件`);
      
      for (const reg of existingRegs) {
        console.log(`- スコープ: ${reg.scope}, 状態: ${reg.active ? 'active' : 'inactive'}`);
        
        // スコープが /static/ の古いService Workerを解除
        if (reg.scope.includes('/static/')) {
          console.log('⚠️ 古いService Workerを解除:', reg.scope);
          try {
            await reg.unregister();
          } catch (e) {
            console.warn('解除失敗:', e);
          }
        }
      }
      
      // 新しいService Workerをルートスコープで登録
      console.log('新しいService Workerを登録中...');
      
      const registration = await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
        updateViaCache: 'none'  // Safari対応: キャッシュを使わない
      });
      
      console.log('✅ SW registered:', registration.scope);
      console.log('SW installing:', registration.installing);
      console.log('SW waiting:', registration.waiting);
      console.log('SW active:', registration.active);
      
      // Service Workerの状態を監視
      if (registration.installing) {
        console.log('Service Worker: インストール中');
        
        registration.installing.addEventListener('statechange', (e) => {
          console.log('SW state changed:', e.target.state);
        });
      } else if (registration.waiting) {
        console.log('Service Worker: 待機中');
      } else if (registration.active) {
        console.log('Service Worker: アクティブ');
      }
      
      // アクティブになるまで待機（Safari/iOSは長めのタイムアウト）
      const timeout = (isSafari || isIOS) ? 10000 : 5000;
      console.log(`Service Worker準備待機中（最大${timeout/1000}秒）...`);
      
      await Promise.race([
        navigator.serviceWorker.ready,
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Service Worker準備タイムアウト')), timeout)
        )
      ]);
      
      console.log('✅ Service Worker準備完了');
      
      // 🆕 Safari/iOSの場合、明示的にcontrollerを確認
      if (isSafari || isIOS) {
        console.log('Navigator controller:', navigator.serviceWorker.controller);
        
        if (!navigator.serviceWorker.controller) {
          console.warn('⚠️ Service Workerがコントロールしていません。ページをリロードします...');
          
          // 1秒後にリロード（Safari対応）
          setTimeout(() => {
            window.location.reload();
          }, 1000);
          
          return;
        }
      }
      
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
      console.error('スタック:', error.stack);
      
      // Safari/iOSの場合、ユーザーにフィードバック
      const userAgent = navigator.userAgent;
      const isSafari = /^((?!chrome|android).)*safari/i.test(userAgent);
      const isIOS = /iPhone|iPad|iPod/.test(userAgent);
      
      if (isSafari || isIOS) {
        console.error('Safari/iOS: Service Worker登録失敗。HTTPSを確認してください。');
      }
    }
  });
  
  // インストールプロンプトを監視
  let deferredPrompt;
  
  window.addEventListener('beforeinstallprompt', (e) => {
    console.log('💡 PWA installable!');
    e.preventDefault();
    deferredPrompt = e;
    showInstallButton();
  });
  
  function showInstallButton() {
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
  
  // 🆕 Service Workerのコントロール状態を監視
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    console.log('🔄 Service Worker controller changed');
  });
  
} else {
  console.warn('❌ Service Workerに非対応のブラウザです');
}