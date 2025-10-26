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
            
            // iOS判定
            const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent);
            const isStandalone = window.navigator.standalone === true || 
                                 window.matchMedia('(display-mode: standalone)').matches;
            
            console.log(`デバイス情報: iOS=${isIOS}, スタンドアロン=${isStandalone}`);
            
            // Service Workerとプッシュ通知のサポートを確認
            if (!('serviceWorker' in navigator)) {
                this.showStatus('Service Workerに非対応', 'warning');
                this.showError('このブラウザではプッシュ通知を利用できません');
                return;
            }
            
            if (!('PushManager' in window)) {
                this.showStatus('プッシュ通知に非対応', 'warning');
                if (isIOS && !isStandalone) {
                    this.showError('iOSでは、ホーム画面に追加後にプッシュ通知を有効にできます');
                } else {
                    this.showError('このブラウザではプッシュ通知を利用できません');
                }
                return;
            }
            
            // 🆕 iOSでスタンドアロンモードでない場合の警告
            if (isIOS && !isStandalone) {
                this.showStatus('プッシュ通知: 利用不可', 'warning');
                this.showError('Safari の共有ボタン → 「ホーム画面に追加」からアプリをインストールしてください');
                return;
            }
            
            // 🆕 iOS対応: より積極的にボタンを表示
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
            this.showError(`エラー: ${error.message}`);
            // 🆕 エラーでもボタンは表示
            if (this.enableBtn) {
                this.enableBtn.style.display = 'block';
                this.enableBtn.disabled = false;
            }
        }
    }
    
    async checkCurrentStatusSimple() {
        try {
            // 通知許可状態をチェック（Service Worker不要）
            const permission = Notification.permission;
            
            console.log('通知許可状態:', permission);
            
            if (permission === 'denied') {
                this.showStatus('通知: ブロック中', 'danger');
                this.showError('設定 → Safari → 通知 からこのサイトの通知を許可してください');
                return;
            }
            
            if (permission === 'default') {
                this.showStatus('プッシュ通知: 無効', 'secondary');
                if (this.enableBtn) {
                    this.enableBtn.style.display = 'block';
                    this.enableBtn.disabled = false;
                }
                return;
            }
            
            // 🆕 iOS対応: Service Worker待機のタイムアウトを500msに短縮
            console.log('Service Worker確認中...');
            
            const swCheckPromise = navigator.serviceWorker.ready.then(async registration => {
                console.log('✅ Service Worker取得成功');
                const subscription = await registration.pushManager.getSubscription();
                return subscription;
            });
            
            const timeoutPromise = new Promise((_, reject) => 
                setTimeout(() => reject(new Error('timeout')), 500)  // 500msに短縮
            );
            
            try {
                const subscription = await Promise.race([swCheckPromise, timeoutPromise]);
                
                if (subscription) {
                    this.showStatus('プッシュ通知: 有効', 'success');
                    if (this.enableBtn) this.enableBtn.style.display = 'none';
                    if (this.disableBtn) {
                        this.disableBtn.style.display = 'block';
                        this.disableBtn.disabled = false;
                    }
                } else {
                    this.showStatus('プッシュ通知: 無効', 'secondary');
                    if (this.enableBtn) {
                        this.enableBtn.style.display = 'block';
                        this.enableBtn.disabled = false;
                    }
                }
            } catch (e) {
                // 🆕 タイムアウトまたはエラーの場合も有効化ボタンを表示
                console.log('⚠️ Service Worker待機をスキップ:', e.message);
                this.showStatus('プッシュ通知: 無効', 'secondary');
                if (this.enableBtn) {
                    this.enableBtn.style.display = 'block';
                    this.enableBtn.disabled = false;
                }
            }
            
        } catch (error) {
            console.error('❌ ステータス確認エラー:', error);
            // エラーでもボタンは表示
            this.showStatus('プッシュ通知: 無効', 'secondary');
            if (this.enableBtn) {
                this.enableBtn.style.display = 'block';
                this.enableBtn.disabled = false;
            }
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
                throw new Error('通知が許可されませんでした。設定から通知を許可してください。');
            }
            
            // 🆕 2. Service Worker取得（タイムアウト30秒、iOSは時間がかかる場合がある）
            console.log('2️⃣ Service Worker取得中...');
            const registration = await Promise.race([
                navigator.serviceWorker.ready,
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Service Worker取得タイムアウト（30秒）')), 30000)
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
            const deviceInfo = this.getDeviceInfo();
            const saveRes = await fetch('/api/push/subscribe/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({
                    subscription: subscription.toJSON(),
                    device_name: deviceInfo.name,
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
            
            // 🆕 iOSではテスト通知をスキップ（権限エラーが出る可能性があるため）
            const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent);
            if (!isIOS) {
                try {
                    new Notification('カブログ', {
                        body: 'プッシュ通知が有効になりました！',
                        icon: '/static/images/icon-192.png'
                    });
                } catch (e) {
                    console.log('テスト通知スキップ:', e.message);
                }
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
            if (this.disableBtn) {
                this.disableBtn.disabled = false;
                if (!completed) {
                    this.disableBtn.innerHTML = '<i class="bi bi-bell-slash me-2"></i>プッシュ通知を無効にする';
                }
            }
        }
    }
    
    // 🆕 デバイス情報取得を改善
    getDeviceInfo() {
        const ua = navigator.userAgent;
        let name = 'Unknown Device';
        
        if (/iPhone/.test(ua)) {
            // iPhoneモデルを判定
            if (window.screen.height === 844) name = 'iPhone 12/13/14';
            else if (window.screen.height === 926) name = 'iPhone 12/13/14 Pro Max';
            else name = 'iPhone';
        } else if (/iPad/.test(ua)) {
            name = 'iPad';
        } else if (/iPod/.test(ua)) {
            name = 'iPod';
        } else if (/Android/.test(ua)) {
            name = 'Android';
        } else if (/Windows/.test(ua)) {
            name = 'Windows PC';
        } else if (/Mac/.test(ua)) {
            name = 'Mac';
        }
        
        return { name };
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