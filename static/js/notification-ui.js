// static/js/notification-ui.js
class NotificationUI {
    constructor() {
      this.init();
    }
  
    async init() {
      await this.updateNotificationButton();
      await this.loadNotificationBadge();
      this.setupEventListeners();
    }
  
    setupEventListeners() {
      // 通知トグルボタン
      const toggleBtn = document.getElementById('notification-toggle-btn');
      if (toggleBtn) {
        toggleBtn.addEventListener('click', () => this.toggleNotifications());
      }
  
      // 通知パネルを開く
      const bellIcon = document.getElementById('notification-bell');
      if (bellIcon) {
        bellIcon.addEventListener('click', () => this.openNotificationPanel());
      }
  
      // すべて既読ボタン
      const markAllReadBtn = document.getElementById('mark-all-read-btn');
      if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', () => this.markAllAsRead());
      }
    }
  
    async updateNotificationButton() {
      await pushNotificationManager.initialize();
      
      const button = document.getElementById('notification-toggle-btn');
      if (!button) return;
  
      const isSubscribed = pushNotificationManager.isSubscribed();
      const permission = pushNotificationManager.getPermissionState();
  
      if (permission === 'granted' && isSubscribed) {
        button.innerHTML = '<i class="bi bi-bell-fill"></i> 通知オン';
        button.classList.remove('btn-outline-primary');
        button.classList.add('btn-success');
      } else {
        button.innerHTML = '<i class="bi bi-bell"></i> 通知オフ';
        button.classList.remove('btn-success');
        button.classList.add('btn-outline-primary');
      }
    }
  
    async toggleNotifications() {
      if (pushNotificationManager.isSubscribed()) {
        if (confirm('プッシュ通知を無効にしますか？')) {
          await pushNotificationManager.unsubscribe();
          await this.updateNotificationButton();
          showToast('プッシュ通知を無効にしました', 'info');
        }
      } else {
        const success = await pushNotificationManager.requestPermission();
        if (success) {
          await this.updateNotificationButton();
        }
      }
    }
  
    async loadNotificationBadge() {
      try {
        const response = await fetch('/api/notifications/logs/?unread=true&limit=1');
        const data = await response.json();
        
        const badge = document.getElementById('notification-badge');
        if (badge && data.unread_count > 0) {
          badge.textContent = data.unread_count > 99 ? '99+' : data.unread_count;
          badge.style.display = 'inline-block';
        }
      } catch (error) {
        console.error('通知バッジ読み込みエラー:', error);
      }
    }
  
    async openNotificationPanel() {
      const panel = document.getElementById('notification-panel');
      if (!panel) return;
  
      // パネルを表示
      panel.classList.add('show');
  
      // 通知履歴を読み込み
      await this.loadNotificationLogs();
    }
  
    async loadNotificationLogs() {
      try {
        const response = await fetch('/api/notifications/logs/?limit=20');
        const data = await response.json();
        
        const container = document.getElementById('notification-list');
        if (!container) return;
  
        if (data.logs.length === 0) {
          container.innerHTML = '<p class="text-muted text-center py-4">通知はありません</p>';
          return;
        }
  
        container.innerHTML = data.logs.map(log => `
          <div class="notification-item ${log.is_read ? 'read' : 'unread'}" 
               data-log-id="${log.id}"
               onclick="notificationUI.handleNotificationClick(${log.id}, '${log.url}')">
            <div class="d-flex justify-content-between">
              <strong>${log.title}</strong>
              <small class="text-muted">${this.formatDate(log.sent_at)}</small>
            </div>
            <p class="mb-0 small">${log.message}</p>
          </div>
        `).join('');
      } catch (error) {
        console.error('通知履歴読み込みエラー:', error);
      }
    }
  
    async handleNotificationClick(logId, url) {
      try {
        await fetch(`/api/notifications/${logId}/read/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': this.getCookie('csrftoken')
          }
        });
  
        if (url) {
          window.location.href = url;
        }
      } catch (error) {
        console.error('通知クリックエラー:', error);
      }
    }
  
    async markAllAsRead() {
      try {
        await fetch('/api/notifications/mark-all-read/', {
          method: 'POST',
          headers: {
            'X-CSRFToken': this.getCookie('csrftoken')
          }
        });
  
        await this.loadNotificationLogs();
        await this.loadNotificationBadge();
        showToast('すべての通知を既読にしました', 'success');
      } catch (error) {
        console.error('一括既読エラー:', error);
      }
    }
  
    formatDate(isoString) {
      const date = new Date(isoString);
      const now = new Date();
      const diff = now - date;
      
      const minutes = Math.floor(diff / 60000);
      const hours = Math.floor(diff / 3600000);
      const days = Math.floor(diff / 86400000);
  
      if (minutes < 1) return 'たった今';
      if (minutes < 60) return `${minutes}分前`;
      if (hours < 24) return `${hours}時間前`;
      if (days < 7) return `${days}日前`;
      
      return date.toLocaleDateString('ja-JP', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
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
  }
  
  // グローバルインスタンス
  const notificationUI = new NotificationUI();