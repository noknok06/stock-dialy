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
        // Service Workerとプッシュ通知のサポートを確認
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            this.showStatus('このブラウザはプッシュ通知に対応していません', 'warning');
            return;
        }
        
        // 現在の状態を確認
        await this.checkCurrentStatus();
        
        // ボタンのイベントリスナーを設定
        if (this.enableBtn) {
            this.enableBtn.addEventListener('click', () => this.enablePushNotification());
        }
        
        if (this.disableBtn) {
            this.disableBtn.addEventListener('click', () => this.disablePushNotification());
        }
    }
    
    async checkCurrentStatus() {
        try {
            // Service Workerの状態を確認
            const registration = await navigator.serviceWorker.ready;
            const subscription = await registration.pushManager.getSubscription();
            
            if (subscription) {
                this.showStatus('プッシュ通知: 有効', 'success');
                this.enableBtn.style.display = 'none';
                this.disableBtn.style.display = 'block';
            } else {
                const permission = Notification.permission;
                
                if (permission === 'denied') {
                    this.showStatus('プッシュ通知: ブロックされています', 'danger');
                    this.showError('ブラウザの設定から通知を許可してください');
                } else {
                    this.showStatus('プッシュ通知: 無効', 'secondary');
                    this.enableBtn.style.display = 'block';
                    this.disableBtn.style.display = 'none';
                }
            }
        } catch (error) {
            console.error('Status check error:', error);
            this.showStatus('状態を確認できませんでした', 'warning');
        }
    }
    
    async enablePushNotification() {
        try {
            this.enableBtn.disabled = true;
            this.enableBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>登録中...';
            this.hideError();
            
            // 1. 通知許可を要求
            const permission = await Notification.requestPermission();
            
            if (permission !== 'granted') {
                throw new Error('通知が許可されませんでした');
            }
            
            // 2. Service Worker取得
            const registration = await navigator.serviceWorker.ready;
            
            // 3. VAPID鍵取得
            const vapidRes = await fetch('/api/push/vapid-key/');
            if (!vapidRes.ok) throw new Error('VAPID鍵の取得に失敗しました');
            const vapidData = await vapidRes.json();
            
            // 4. サブスクリプション作成
            const subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: this.urlBase64ToUint8Array(vapidData.public_key)
            });
            
            // 5. サーバーに保存
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
                throw new Error('サーバーへの保存に失敗しました');
            }
            
            const result = await saveRes.json();
            console.log('Push subscription registered:', result);
            
            // 成功メッセージ
            this.showStatus('プッシュ通知: 有効', 'success');
            this.enableBtn.style.display = 'none';
            this.disableBtn.style.display = 'block';
            
            // テスト通知を表示
            new Notification('カブログ', {
                body: 'プッシュ通知が有効になりました！',
                icon: '/static/images/icon-192.png'
            });
            
        } catch (error) {
            console.error('Enable push error:', error);
            this.showError('エラー: ' + error.message);
            this.enableBtn.disabled = false;
            this.enableBtn.innerHTML = '<i class="bi bi-bell me-2"></i>プッシュ通知を有効にする';
        }
    }
    
    async disablePushNotification() {
        try {
            this.disableBtn.disabled = true;
            this.disableBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>解除中...';
            
            const registration = await navigator.serviceWorker.ready;
            const subscription = await registration.pushManager.getSubscription();
            
            if (subscription) {
                // サーバーに通知
                await fetch('/api/push/unsubscribe/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        endpoint: subscription.endpoint
                    })
                });
                
                // ブラウザから削除
                await subscription.unsubscribe();
            }
            
            this.showStatus('プッシュ通知: 無効', 'secondary');
            this.enableBtn.style.display = 'block';
            this.disableBtn.style.display = 'none';
            
        } catch (error) {
            console.error('Disable push error:', error);
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
        this.statusDiv.innerHTML = `<span class="badge bg-${type}">${message}</span>`;
    }
    
    showError(message) {
        this.errorDiv.textContent = message;
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