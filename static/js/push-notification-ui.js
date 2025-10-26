// static/js/push-notification-ui.js

class PushNotificationUI {
    constructor() {
        this.enableBtn = document.getElementById('enable-push-btn');
        this.disableBtn = document.getElementById('disable-push-btn');
        this.statusDiv = document.getElementById('push-status');
        this.errorDiv = document.getElementById('push-error');
        
        this.init();
    }
    
    async init() {
        try {
            console.log('🔄 PushNotificationUI初期化開始');
            
            // Service Workerとプッシュ通知のサポートを確認
            if (!('serviceWorker' in navigator)) {
                this.showStatus('Service Workerに非対応', 'warning');
                return;
            }
            
            if (!('PushManager' in window)) {
                this.showStatus('プッシュ通知に非対応', 'warning');
                return;
            }
            
            // 現在の状態を確認（簡易版）
            await this.checkCurrentStatusSimple();
            
            // ボタンのイベントリスナーを設定
            if (this.enableBtn) {
                this.enableBtn.addEventListener('click', () => this.enablePushNotification());
            }
            
            if (this.disableBtn) {
                this.disableBtn.addEventListener('click', () => this.disablePushNotification());
            }
            
            console.log('✅ PushNotificationUI初期化完了');
            
        } catch (error) {
            console.error('❌ Init error:', error);
            this.showStatus('初期化エラー', 'danger');
            // エラーでもボタンは表示
            if (this.enableBtn) this.enableBtn.style.display = 'block';
        }
    }
    
    async checkCurrentStatusSimple() {
        // 通知許可状態をチェック（Service Worker不要）
        const permission = Notification.permission;
        
        console.log('通知許可状態:', permission);
        
        if (permission === 'denied') {
            this.showStatus('通知: ブロック中', 'danger');
            this.showError('ブラウザの設定から通知を許可してください');
            return;
        }
        
        if (permission === 'default') {
            this.showStatus('プッシュ通知: 無効', 'secondary');
            if (this.enableBtn) this.enableBtn.style.display = 'block';
            return;
        }
        
        // granted の場合、Service Workerをチェック（タイムアウト短め）
        try {
            const registration = await Promise.race([
                navigator.serviceWorker.ready,
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('timeout')), 2000)
                )
            ]);
            
            const subscription = await registration.pushManager.getSubscription();
            
            if (subscription) {
                this.showStatus('プッシュ通知: 有効', 'success');
                if (this.enableBtn) this.enableBtn.style.display = 'none';
                if (this.disableBtn) this.disableBtn.style.display = 'block';
            } else {
                this.showStatus('プッシュ通知: 無効', 'secondary');
                if (this.enableBtn) this.enableBtn.style.display = 'block';
            }
        } catch (e) {
            console.log('Service Worker待機スキップ:', e.message);
            // タイムアウトでも有効化ボタンは表示
            this.showStatus('プッシュ通知: 無効', 'secondary');
            if (this.enableBtn) this.enableBtn.style.display = 'block';
        }
    }
    
    async enablePushNotification() {
        try {
            this.enableBtn.disabled = true;
            this.enableBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>登録中...';
            this.hideError();
            
            console.log('━━━ プッシュ通知有効化開始 ━━━');
            
            // 1. 通知許可を要求
            console.log('1️⃣ 通知許可を要求中...');
            const permission = await Notification.requestPermission();
            console.log('通知許可結果:', permission);
            
            if (permission !== 'granted') {
                throw new Error('通知が許可されませんでした');
            }
            
            // 2. Service Worker取得（タイムアウト10秒）
            console.log('2️⃣ Service Worker取得中...');
            const registration = await Promise.race([
                navigator.serviceWorker.ready,
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Service Worker取得タイムアウト（10秒）')), 10000)
                )
            ]);
            console.log('✅ Service Worker取得完了');
            
            // 3. VAPID鍵取得
            console.log('3️⃣ VAPID鍵取得中...');
            const vapidRes = await fetch('/api/push/vapid-key/');
            if (!vapidRes.ok) throw new Error('VAPID鍵取得失敗');
            const vapidData = await vapidRes.json();
            console.log('✅ VAPID鍵取得完了');
            
            // 4. サブスクリプション作成
            console.log('4️⃣ サブスクリプション作成中...');
            const subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: this.urlBase64ToUint8Array(vapidData.public_key)
            });
            console.log('✅ サブスクリプション作成完了');
            
            // 5. サーバーに保存
            console.log('5️⃣ サーバーに保存中...');
            const saveRes = await fetch('/api/push/subscribe/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({
                    subscription: subscription.toJSON(),
                    device_name: /Mobile/.test(navigator.userAgent) ? 'Mobile' : 'Desktop',
                    user_agent: navigator.userAgent
                })
            });
            
            if (!saveRes.ok) {
                throw new Error(`サーバー保存失敗: ${saveRes.status}`);
            }
            
            const result = await saveRes.json();
            console.log('✅ サーバー保存完了:', result);
            console.log('━━━ プッシュ通知有効化完了 ━━━');
            
            // UI更新
            this.showStatus('プッシュ通知: 有効', 'success');
            this.enableBtn.style.display = 'none';
            this.disableBtn.style.display = 'block';
            this.disableBtn.disabled = false;
            this.disableBtn.innerHTML = '<i class="bi bi-bell-slash me-2"></i>プッシュ通知を無効にする';
            
            // テスト通知
            try {
                new Notification('カブログ', {
                    body: 'プッシュ通知が有効になりました！',
                    icon: '/static/images/icon-192.png'
                });
            } catch (e) {
                console.log('テスト通知スキップ:', e.message);
            }
            
        } catch (error) {
            console.error('━━━ エラー発生 ━━━');
            console.error(error);
            this.showError('エラー: ' + error.message);
            this.enableBtn.disabled = false;
            this.enableBtn.innerHTML = '<i class="bi bi-bell me-2"></i>プッシュ通知を有効にする';
        }
    }
    
    async disablePushNotification() {
        // エラーハンドリングを強化
        let completed = false;
        
        try {
            this.disableBtn.disabled = true;
            this.disableBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>解除中...';
            this.hideError();
            
            console.log('━━━ プッシュ通知無効化開始 ━━━');
            
            // Service Worker取得（タイムアウト5秒）
            console.log('1️⃣ Service Worker取得中...');
            const registration = await Promise.race([
                navigator.serviceWorker.ready,
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('timeout')), 5000)
                )
            ]);
            
            console.log('2️⃣ サブスクリプション取得中...');
            const subscription = await registration.pushManager.getSubscription();
            
            if (subscription) {
                console.log('3️⃣ サーバーに通知中...');
                
                try {
                    const unsubRes = await fetch('/api/push/unsubscribe/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify({ endpoint: subscription.endpoint })
                    });
                    
                    if (unsubRes.ok) {
                        console.log('✅ サーバー通知完了');
                    } else {
                        console.warn('⚠️ サーバー通知失敗:', unsubRes.status);
                    }
                } catch (e) {
                    console.warn('⚠️ サーバー通知エラー:', e.message);
                    // サーバー通知失敗でも続行
                }
                
                console.log('4️⃣ ブラウザから削除中...');
                await subscription.unsubscribe();
                console.log('✅ ブラウザから削除完了');
            } else {
                console.log('ℹ️ サブスクリプションなし');
            }
            
            completed = true;
            console.log('━━━ プッシュ通知無効化完了 ━━━');
            
            // UI更新
            this.showStatus('プッシュ通知: 無効', 'secondary');
            this.enableBtn.style.display = 'block';
            this.enableBtn.disabled = false;
            this.disableBtn.style.display = 'none';
            
        } catch (error) {
            console.error('━━━ エラー発生 ━━━');
            console.error(error);
            
            // エラーでもUI更新を試みる
            if (error.message === 'timeout') {
                console.log('タイムアウトですが、サーバー側で削除されている可能性があります');
                completed = true;
                this.showStatus('プッシュ通知: 無効', 'secondary');
                this.enableBtn.style.display = 'block';
                this.disableBtn.style.display = 'none';
            } else {
                this.showError('エラー: ' + error.message);
            }
            
        } finally {
            // 必ずボタンを戻す
            if (this.disableBtn) {
                this.disableBtn.disabled = false;
                if (!completed) {
                    this.disableBtn.innerHTML = '<i class="bi bi-bell-slash me-2"></i>プッシュ通知を無効にする';
                }
            }
        }
    }
    
    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }
    
    showStatus(message, type) {
        if (!this.statusDiv) return;
        const badges = {
            'success': 'bg-success',
            'danger': 'bg-danger',
            'warning': 'bg-warning',
            'info': 'bg-info',
            'secondary': 'bg-secondary'
        };
        this.statusDiv.innerHTML = `<span class="badge ${badges[type] || 'bg-secondary'}">${message}</span>`;
    }
    
    showError(message) {
        if (!this.errorDiv) return;
        this.errorDiv.innerHTML = `<small>${message}</small>`;
        this.errorDiv.style.display = 'block';
    }
    
    hideError() {
        if (!this.errorDiv) return;
        this.errorDiv.style.display = 'none';
    }
}

// DOMContentLoaded時に初期化
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded: PushNotificationUI確認中...');
    
    if (document.getElementById('push-notification-section')) {
        console.log('push-notification-section発見、初期化開始');
        new PushNotificationUI();
    } else {
        console.log('push-notification-section未発見');
    }
});