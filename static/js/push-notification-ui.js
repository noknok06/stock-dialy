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
            
            // ブラウザ判定
            const userAgent = navigator.userAgent;
            const isSafari = /^((?!chrome|android).)*safari/i.test(userAgent);
            const isIOS = /iPhone|iPad|iPod/.test(userAgent);
            const isStandalone = window.navigator.standalone === true || 
                                 window.matchMedia('(display-mode: standalone)').matches;
            
            console.log(`🔍 ブラウザ情報:`, {
                isSafari,
                isIOS,
                isStandalone,
                userAgent: userAgent.substring(0, 100)
            });
            
            // Service Workerとプッシュ通知のサポートを確認
            if (!('serviceWorker' in navigator)) {
                this.showStatus('Service Workerに非対応', 'warning');
                this.showError('このブラウザではプッシュ通知を利用できません');
                return;
            }
            
            if (!('PushManager' in window)) {
                this.showStatus('プッシュ通知に非対応', 'warning');
                if (isIOS && !isStandalone) {
                    this.showError('ホーム画面に追加後、プッシュ通知を有効にできます');
                } else {
                    this.showError('このブラウザではプッシュ通知を利用できません');
                }
                return;
            }
            
            // iOSでスタンドアロンモードでない場合
            if (isIOS && !isStandalone) {
                this.showStatus('PWAとしてインストールが必要', 'warning');
                this.showError('Safari の共有ボタン → 「ホーム画面に追加」からアプリをインストールしてください');
                return;
            }
            
            // 🆕 Safari/iOSの場合は、まずService Workerが登録されているか確認
            if (isSafari || isIOS) {
                console.log('Safari/iOS検出: Service Worker確認中...');
                const swRegistration = await this.waitForServiceWorker(isIOS ? 5000 : 3000);
                
                if (!swRegistration) {
                    console.warn('⚠️ Service Workerが見つかりません');
                    this.showStatus('Service Worker未登録', 'warning');
                    this.showError('ページを再読み込みしてください');
                    
                    // それでもボタンは表示（再試行可能にする）
                    if (this.enableBtn) {
                        this.enableBtn.style.display = 'block';
                        this.enableBtn.disabled = false;
                    }
                    return;
                }
                
                console.log('✅ Service Worker登録確認完了');
            }
            
            // 現在の状態を確認
            await this.checkCurrentStatus(isSafari || isIOS);
            
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
            this.showError(`${error.message}`);
            
            // エラーでもボタンは表示
            if (this.enableBtn) {
                this.enableBtn.style.display = 'block';
                this.enableBtn.disabled = false;
            }
        }
    }
    
    // 🆕 Service Workerの登録を待つ専用関数
    async waitForServiceWorker(timeoutMs = 3000) {
        try {
            // すでに登録されているか確認
            const existingRegistration = await navigator.serviceWorker.getRegistration('/');
            if (existingRegistration) {
                console.log('既存のService Worker発見:', existingRegistration.scope);
                return existingRegistration;
            }
            
            // 登録されていない場合は待機
            console.log(`Service Worker登録待機中（最大${timeoutMs}ms）...`);
            
            const registration = await Promise.race([
                navigator.serviceWorker.ready,
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Service Worker待機タイムアウト')), timeoutMs)
                )
            ]);
            
            return registration;
            
        } catch (error) {
            console.error('Service Worker取得エラー:', error);
            return null;
        }
    }
    
    async checkCurrentStatus(isSafariOrIOS = false) {
        try {
            // 通知許可状態をチェック
            const permission = Notification.permission;
            console.log('通知許可状態:', permission);
            
            if (permission === 'denied') {
                this.showStatus('通知: ブロック中', 'danger');
                if (isSafariOrIOS) {
                    this.showError('Safari の環境設定 → Webサイト → 通知 から許可してください');
                } else {
                    this.showError('ブラウザの設定から通知を許可してください');
                }
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
            
            // granted の場合、サブスクリプションを確認
            console.log('サブスクリプション確認中...');
            
            try {
                // 🆕 Safari/iOSの場合はより長いタイムアウト
                const timeout = isSafariOrIOS ? 3000 : 1000;
                
                const registration = await Promise.race([
                    navigator.serviceWorker.ready,
                    new Promise((_, reject) => 
                        setTimeout(() => reject(new Error('timeout')), timeout)
                    )
                ]);
                
                const subscription = await registration.pushManager.getSubscription();
                
                if (subscription) {
                    console.log('✅ サブスクリプション存在');
                    this.showStatus('プッシュ通知: 有効', 'success');
                    if (this.enableBtn) this.enableBtn.style.display = 'none';
                    if (this.disableBtn) {
                        this.disableBtn.style.display = 'block';
                        this.disableBtn.disabled = false;
                    }
                } else {
                    console.log('ℹ️ サブスクリプション未登録');
                    this.showStatus('プッシュ通知: 無効', 'secondary');
                    if (this.enableBtn) {
                        this.enableBtn.style.display = 'block';
                        this.enableBtn.disabled = false;
                    }
                }
            } catch (e) {
                console.log('⚠️ サブスクリプション確認スキップ:', e.message);
                this.showStatus('プッシュ通知: 無効', 'secondary');
                if (this.enableBtn) {
                    this.enableBtn.style.display = 'block';
                    this.enableBtn.disabled = false;
                }
            }
            
        } catch (error) {
            console.error('❌ ステータス確認エラー:', error);
            this.showStatus('プッシュ通知: 無効', 'secondary');
            if (this.enableBtn) {
                this.enableBtn.style.display = 'block';
                this.enableBtn.disabled = false;
            }
        }
    }
    
    async enablePushNotification() {
        const userAgent = navigator.userAgent;
        const isSafari = /^((?!chrome|android).)*safari/i.test(userAgent);
        const isIOS = /iPhone|iPad|iPod/.test(userAgent);
        
        try {
            this.enableBtn.disabled = true;
            this.enableBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>登録中...';
            this.hideError();
            
            console.log('━━━ プッシュ通知有効化開始 ━━━');
            console.log(`ブラウザ: Safari=${isSafari}, iOS=${isIOS}`);
            
            // 1. 通知許可を要求
            console.log('1️⃣ 通知許可を要求中...');
            const permission = await Notification.requestPermission();
            console.log('通知許可結果:', permission);
            
            if (permission !== 'granted') {
                throw new Error('通知が許可されませんでした');
            }
            
            // 2. Service Worker取得（Safari/iOSは長めのタイムアウト）
            console.log('2️⃣ Service Worker取得中...');
            const timeout = (isSafari || isIOS) ? 30000 : 10000;
            console.log(`タイムアウト設定: ${timeout}ms`);
            
            const registration = await Promise.race([
                navigator.serviceWorker.ready,
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error(`Service Worker取得タイムアウト（${timeout/1000}秒）`)), timeout)
                )
            ]);
            console.log('✅ Service Worker取得完了:', registration.scope);
            
            // 3. VAPID鍵取得
            console.log('3️⃣ VAPID鍵取得中...');
            const vapidRes = await fetch('/api/push/vapid-key/');
            if (!vapidRes.ok) {
                throw new Error(`VAPID鍵取得失敗: ${vapidRes.status}`);
            }
            const vapidData = await vapidRes.json();
            console.log('✅ VAPID鍵取得完了');
            
            // 4. サブスクリプション作成
            console.log('4️⃣ サブスクリプション作成中...');
            
            // 🆕 Safari/iOSでは既存のサブスクリプションを先に削除
            if (isSafari || isIOS) {
                const existingSub = await registration.pushManager.getSubscription();
                if (existingSub) {
                    console.log('既存のサブスクリプションを削除...');
                    await existingSub.unsubscribe();
                }
            }
            
            const subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: this.urlBase64ToUint8Array(vapidData.public_key)
            });
            console.log('✅ サブスクリプション作成完了');
            console.log('エンドポイント:', subscription.endpoint.substring(0, 50) + '...');
            
            // 5. サーバーに保存
            console.log('5️⃣ サーバーに保存中...');
            const deviceInfo = this.getDeviceInfo();
            
            const saveRes = await fetch('/api/push/subscribe/', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    subscription: subscription.toJSON(),
                    device_name: deviceInfo.name,
                    user_agent: navigator.userAgent
                })
            });
            
            if (!saveRes.ok) {
                const errorText = await saveRes.text();
                console.error('サーバーエラー:', errorText);
                throw new Error(`サーバー保存失敗: ${saveRes.status}`);
            }
            
            const result = await saveRes.json();
            console.log('✅ サーバー保存完了:', result);
            console.log('━━━ プッシュ通知有効化完了 ━━━');
            
            // UI更新
            this.showStatus('プッシュ通知: 有効', 'success');
            this.enableBtn.style.display = 'none';
            if (this.disableBtn) {
                this.disableBtn.style.display = 'block';
                this.disableBtn.disabled = false;
                this.disableBtn.innerHTML = '<i class="bi bi-bell-slash me-2"></i>プッシュ通知を無効にする';
            }
            
            // 🆕 テスト通知（Safari/iOSではスキップ）
            if (!isSafari && !isIOS) {
                try {
                    new Notification('カブログ', {
                        body: 'プッシュ通知が有効になりました！',
                        icon: '/static/images/icon-192.png'
                    });
                } catch (e) {
                    console.log('テスト通知スキップ:', e.message);
                }
            } else {
                console.log('Safari/iOS: テスト通知スキップ');
            }
            
        } catch (error) {
            console.error('━━━ エラー発生 ━━━');
            console.error('エラー詳細:', error);
            console.error('スタック:', error.stack);
            
            let errorMessage = error.message;
            
            // Safari/iOS特有のエラーメッセージ
            if (isSafari || isIOS) {
                if (error.message.includes('timeout')) {
                    errorMessage = 'Service Workerの準備に時間がかかっています。ページを再読み込みして再度お試しください。';
                } else if (error.message.includes('NotAllowedError')) {
                    errorMessage = '通知が許可されていません。Safari の環境設定から通知を許可してください。';
                } else if (error.message.includes('NotSupportedError')) {
                    errorMessage = 'このデバイス/ブラウザではプッシュ通知がサポートされていません。';
                }
            }
            
            this.showError('エラー: ' + errorMessage);
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
            
            const registration = await Promise.race([
                navigator.serviceWorker.ready,
                new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('timeout')), 5000)
                )
            ]);
            
            const subscription = await registration.pushManager.getSubscription();
            
            if (subscription) {
                console.log('サーバーに通知中...');
                
                try {
                    const unsubRes = await fetch('/api/push/unsubscribe/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify({ endpoint: subscription.endpoint })
                    });
                    
                    if (unsubRes.ok) {
                        console.log('✅ サーバー通知完了');
                    }
                } catch (e) {
                    console.warn('⚠️ サーバー通知エラー:', e.message);
                }
                
                console.log('ブラウザから削除中...');
                await subscription.unsubscribe();
                console.log('✅ ブラウザから削除完了');
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
    
    getDeviceInfo() {
        const ua = navigator.userAgent;
        let name = 'Unknown Device';
        
        if (/iPhone/.test(ua)) {
            const height = window.screen.height;
            if (height === 844) name = 'iPhone 12/13/14';
            else if (height === 926) name = 'iPhone 12/13/14 Pro Max';
            else if (height === 896) name = 'iPhone 11/XR/XS Max';
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
        this.errorDiv.innerHTML = `<small class="text-danger">${message}</small>`;
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