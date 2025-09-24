// static/js/pwa-register.js を作成
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      const registration = await navigator.serviceWorker.register('/static/sw.js');
      console.log('✅ SW registered:', registration);
      
      // PWAインストール可能性をチェック
      if ('getInstalledRelatedApps' in navigator) {
        const installedApps = await navigator.getInstalledRelatedApps();
        console.log('Installed apps:', installedApps);
      }
      
    } catch (error) {
      console.error('❌ SW registration failed:', error);
    }
  });
  
  // インストールプロンプトを監視
  let deferredPrompt;
  
  window.addEventListener('beforeinstallprompt', (e) => {
    console.log('💡 PWA installable!');
    e.preventDefault();
    deferredPrompt = e;
    
    // 手動でボタン表示
    showInstallButton();
  });
  
  function showInstallButton() {
    const btn = document.createElement('button');
    btn.textContent = '📱 アプリをインストール';
    btn.className = 'btn btn-success position-fixed top-0 end-0 m-3';
    btn.onclick = async () => {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        const result = await deferredPrompt.userChoice;
        console.log('Install result:', result.outcome);
        deferredPrompt = null;
        btn.remove();
      }
    };
    document.body.appendChild(btn);
  }
}