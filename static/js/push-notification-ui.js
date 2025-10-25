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
            // Service Workerとプッシュ通知のサポートを確認
            if (!('serviceWorker' in navigator)) {
                this.showStatus('Service Workerに非対応', 'warning');
                return;
            }
            
            if (!('PushManager' in window)) {
                this.showStatus('プッシュ通知に非対応', 'warning');
                return;
            }
            
            // 現在の状態を確認（タイムアウト付き）
            await this.checkCurrentStatusWithTimeout();
            
            // ボタンのイベントリスナーを設定
            if (this.enableBtn) {
                this.enableBtn.addEventListener('click', () => this.enablePushNotification());
            }
            
            if (this.disableBtn) {
                this.disableBtn.addEventListener('click', () => this.disablePushNotification());
            }
            
        } catch (error) {
            console.error('Init error:', error);
            this.showStatus('初期化エラー', 'danger');
            this.showError(error.message);
        }
    }
    
    async checkCurrentStatusWithTimeout() {
        try {
            // タイムアウト付きでService Workerを待機
            const registration = await Promise.race([
                navigator.serviceWorker.ready,
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Service Workerタイムアウト')), 5000)
                )
            ]);
            
            await this.checkSubscriptionStatus(registration);
            
        } catch (error) {
            console.error('Status check timeout:', error);
            
            // タイムアウトしても最低限の表示
            const permission = Notification.permission;
            
            if (permission === 'denied') {
                this.showStatus('通知: ブロック中', 'danger');
                this.showError('ブラウザの設定から通知を許可してください');
            } else if (permission === 'granted') {
                this.showStatus('通知許可済み', 'info');
                this.enableBtn.style.display = 'block';
            } else {
                this.showStatus('プッシュ通知: 無効', 'secondary');
                this.enableBtn.style.display = 'block';
            }
        }
    }
    
    async checkSubscriptionStatus(registration) {
        try {
            const subscription = await registration.pushManager.getSubscription();
            
            if (subscription) {
                this.showStatus('プッシュ通知: 有効', 'success');
                this.enableBtn.style.display = 'none';
                this.disableBtn.style.display = 'block';
            } else {
                const permission = Notification.permission;
                
                if (permission === 'denied') {
                    this.showStatus('プッシュ通知: ブロック中', 'danger');
                    this.showError('ブラウザの設定から通知を許可してください');
                } else {
                    this.showStatus('プッシュ通知: 無効', 'secondary');
                    this.enableBtn.style.display = 'block';
                    this.disableBtn.style.display = 'none';
                }
            }
        } catch (error) {
            console.error('Subscription check error:', error);
            this.showStatus('状態確認エラー', 'warning');
            // エラーでも有効化ボタンは表示
            this.enableBtn.style.display = 'block';
        }
    }
    
    async enablePushNotification() {
        try {
            this.enableBtn.disabled = true;
            this.enableBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>登録中...';
            this.hideError();
            
            console.log('🔔 プッシュ通知有効化開始');
            
            // 1. 通知許可を要求
            console.log('⏳ 通知許可を要求中...');
            const permission = await Notification.requestPermission();
            console.log('通知許可結果:', permission);
            
            if (permission !== 'granted') {
                throw new Error('通知が許可されませんでした');
            }
            
            // 2. Service Worker取得（タイムアウト付き）
            console.log('⏳ Service Worker取得中...');
            const registration = await Promise.race([
                navigator.serviceWorker.ready,
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Service Worker取得タイムアウト')), 10000)
                )
            ]);
            console.log('✅ Service Worker取得完了');
            
            // 3. VAPID鍵取得
            console.log('⏳ VAPID鍵取得中...');
            const vapidRes = await fetch('/api/push/vapid-key/');
            if (!vapidRes.ok) throw new Error('VAPID鍵の取得に失敗');
            const vapidData = await vapidRes.json();
            console.log('✅ VAPID鍵取得完了');
            
            // 4. サブスクリプション作成
            console.log('⏳ サブスクリプション作成中...');
            const subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: this.urlBase64ToUint8Array(vapidData.public_key)
            });
            console.log('✅ サブスクリプション作成完了');
            
            // 5. サーバーに保存
            console.log('⏳ サーバーに保存中...');
            const saveRes = await fetch('/api/push/subscribe/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    subscription: subscription.toJSON(),
                    device_name: /Mobile/.test(navigator.userAgent) ? 'Mobile' : 'Desktop',
                    user_agent: navigator.userAgent
                })
            });
            
            if (!saveRes.ok) {
                const errorText = await saveRes.text();
                console.error('保存エラー:', errorText);
                throw new Error('サーバーへの保存に失敗しました');
            }
            
            const result = await saveRes.json();
            console.log('✅ Push subscription registered:', result);
            
            // 成功メッセージ
            this.showStatus('プッシュ通知: 有効', 'success');
            this.enableBtn.style.display = 'none';
            this.disableBtn.style.display = 'block';
            this.disableBtn.disabled = false;
            this.disableBtn.innerHTML = '<i class="bi bi-bell-slash me-2"></i>プッシュ通知を無効にする';
            
            // テスト通知を表示
            try {
                new Notification('カブログ', {
                    body: 'プッシュ通知が有効になりました！',
                    icon: '/static/images/icon-192.png',
                    badge: '/static/images/badge-72.png'
                });
            } catch (e) {
                console.log('Test notification failed:', e);
            }
            
        } catch (error) {
            console.error('❌ Enable push error:', error);
            this.showError('エラー: ' + error.message);
            this.enableBtn.disabled = false;
            this.enableBtn.innerHTML = '<i class="bi bi-bell me-2"></i>プッシュ通知を有効にする';
        }
    }
    
    async disablePushNotification() {
        try {
            this.disableBtn.disabled = true;
            this.disableBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>解除中...';
            this.hideError();
            
            console.log('🔕 プッシュ通知無効化開始');
            
            const registration = await navigator.serviceWorker.ready;
            const subscription = await registration.pushManager.getSubscription();
            
            if (subscription) {
                console.log('⏳ サーバーに通知中...');
                
                // サーバーに通知（CSRFトークン不要）
                const unsubRes = await fetch('/api/push/unsubscribe/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        endpoint: subscription.endpoint
                    })
                });
                
                if (!unsubRes.ok) {
                    console.warn('サーバー通知失敗:', unsubRes.status);
                    // サーバー失敗でも続行
                }
                
                console.log('⏳ ブラウザから削除中...');
                await subscription.unsubscribe();
                console.log('✅ サブスクリプション削除完了');
            }
            
            this.showStatus('プッシュ通知: 無効', 'secondary');
            this.enableBtn.style.display = 'block';
            this.enableBtn.disabled = false;
            this.disableBtn.style.display = 'none';
            
        } catch (error) {
            console.error('❌ Disable push error:', error);
            this.showError('エラー: ' + error.message);
            this.disableBtn.disabled = false;
            this.disableBtn.innerHTML = '<i class="bi bi-bell-slash me-2"></i>プッシュ通知を無効にする';
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
        this.errorDiv.innerHTML = `<small>${message}</small>`;
        this.errorDiv.style.display = 'block';
    }
    
    hideError() {
        this.errorDiv.style.display = 'none';
    }
}

// DOMContentLoaded時に初期化
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('push-notification-section')) {
        new PushNotificationUI();
    }
});