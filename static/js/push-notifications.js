// static/js/push-notifications.js
class PushNotificationManager {
    constructor() {
      this.registration = null;
      this.subscription = null;
      this.vapidPublicKey = null;
    }
  
    async initialize() {
      if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        console.warn('プッシュ通知はこのブラウザでサポートされていません');
        return false;
      }
  
      try {
        // Service Worker取得
        this.registration = await navigator.serviceWorker.ready;
        
        // VAPID公開鍵を取得
        const response = await fetch('/api/push/vapid-key/');
        const data = await response.json();
        this.vapidPublicKey = data.public_key;
  
        // 既存のサブスクリプションを確認
        this.subscription = await this.registration.pushManager.getSubscription();
        
        return true;
      } catch (error) {
        console.error('初期化エラー:', error);
        return false;
      }
    }
  
    async requestPermission() {
      const permission = await Notification.requestPermission();
      
      if (permission === 'granted') {
        await this.subscribe();
        return true;
      } else if (permission === 'denied') {
        this.showToast('通知が拒否されました。ブラウザの設定から通知を許可してください。', 'warning');
        return false;
      }
      return false;
    }
  
    async subscribe() {
      try {
        const subscription = await this.registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: this.urlBase64ToUint8Array(this.vapidPublicKey)
        });
  
        await this.sendSubscriptionToServer(subscription);
        this.subscription = subscription;
        
        return subscription;
      } catch (error) {
        console.error('サブスクリプションエラー:', error);
        throw error;
      }
    }
  
    async unsubscribe() {
      if (!this.subscription) {
        return;
      }
  
      try {
        await this.subscription.unsubscribe();
        await this.removeSubscriptionFromServer(this.subscription);
        this.subscription = null;
      } catch (error) {
        console.error('サブスクリプション解除エラー:', error);
        throw error;
      }
    }
  
    async sendSubscriptionToServer(subscription) {
      const response = await fetch('/api/push/subscribe/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCookie('csrftoken')
        },
        body: JSON.stringify({
          subscription: subscription.toJSON(),
          device_name: this.getDeviceName(),
          user_agent: navigator.userAgent
        })
      });
  
      if (!response.ok) {
        throw new Error('サーバーへの送信に失敗しました');
      }
      
      const data = await response.json();
      this.showToast(data.message || 'プッシュ通知を有効にしました', 'success');
    }
  
    async removeSubscriptionFromServer(subscription) {
      await fetch('/api/push/unsubscribe/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCookie('csrftoken')
        },
        body: JSON.stringify({
          endpoint: subscription.endpoint
        })
      });
    }
  
    isSubscribed() {
      return this.subscription !== null;
    }
  
    getPermissionState() {
      return Notification.permission;
    }
  
    urlBase64ToUint8Array(base64String) {
      const padding = '='.repeat((4 - base64String.length % 4) % 4);
      const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');
  
      const rawData = window.atob(base64);
      const outputArray = new Uint8Array(rawData.length);
  
      for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
      }
      return outputArray;
    }
  
    getCookie(name) {
      let cookieValue = null;
      if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
          const cookie = cookies[i].trim();
          if (cookie.substring(0, name.length + 1) === (name + '=')) {
            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
            break;
          }
        }
      }
      return cookieValue;
    }
  
    getDeviceName() {
      const ua = navigator.userAgent;
      if (/iPhone/.test(ua)) return 'iPhone';
      if (/iPad/.test(ua)) return 'iPad';
      if (/Android/.test(ua)) return 'Android';
      if (/Windows/.test(ua)) return 'Windows PC';
      if (/Mac/.test(ua)) return 'Mac';
      return 'Unknown Device';
    }
  
    showToast(message, type = 'info') {
      if (typeof showToast === 'function') {
        showToast(message, type);
      } else {
        // console.log(`[${type}] ${message}`);
      }
    }
  }
  
  // グローバルインスタンス
  const pushNotificationManager = new PushNotificationManager();