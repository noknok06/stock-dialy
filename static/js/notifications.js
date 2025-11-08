// 通知タイプに応じてフィールドを切り替え（削除）
// document.getElementById('notificationType')... の部分を削除

function getCookie(name) {
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

function getCSRFToken() {
  // 方法1: Cookieから取得
  let token = getCookie('csrftoken');
  
  // 方法2: hiddenフィールドから取得
  if (!token) {
    const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (csrfInput) {
      token = csrfInput.value;
    }
  }
  
  // 方法3: metaタグから取得
  if (!token) {
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (csrfMeta) {
      token = csrfMeta.content;
    }
  }
  
  return token;
}

async function saveNotification(diaryId) {
  const message = document.getElementById('notificationMessage').value;
  const remindAtValue = document.getElementById('remindAt').value;
  
  if (!remindAtValue) {
    showToast('通知日時を入力してください', 'warning');
    return;
  }
  
  const data = {
    remind_at: remindAtValue,
    message: message
  };
  
  try {
    const csrfToken = getCSRFToken();
    
    if (!csrfToken) {
      console.error('❌ CSRFトークンが見つかりません');
      showToast('セッションが無効です。ページを再読み込みしてください。', 'danger');
      return;
    }
    
    const url = `/stockdiary/api/diary/${diaryId}/notifications/create/`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
        'X-Requested-With': 'XMLHttpRequest'
      },
      credentials: 'same-origin',
      body: JSON.stringify(data)
    });
    
    const contentType = response.headers.get('content-type');
    
    if (response.status === 404) {
      console.error('❌ API endpoint not found (404)');
      showToast('APIエンドポイントが見つかりません。', 'danger');
      return;
    }
    
    if (response.status === 401 || response.status === 403) {
      console.error('❌ Authentication/Permission error');
      showToast('ログインが必要です。ページを再読み込みしてください。', 'danger');
      return;
    }
    
    if (!contentType || !contentType.includes('application/json')) {
      const responseText = await response.text();
      console.error('❌ Response is not JSON. Content-Type:', contentType);
      showToast('サーバーエラーが発生しました。', 'danger');
      return;
    }
    
    const result = await response.json();
    
    if (response.ok && result.success) {
      showToast(result.message || '通知を設定しました', 'success');
      
      const modal = bootstrap.Modal.getInstance(document.getElementById('notificationModal'));
      if (modal) {
        modal.hide();
      }
      
      document.getElementById('notificationMessage').value = '';
      document.getElementById('remindAt').value = '';
      
      // 通知一覧を更新
      if (typeof loadNotifications === 'function') {
        loadNotifications();
      }
    } else {
      const errorMsg = result.error || '通知設定に失敗しました';
      console.error('Error:', errorMsg);
      showToast(errorMsg, 'danger');
    }
    
  } catch (error) {
    console.error('❌ Network error:', error);
    showToast('通信エラーが発生しました: ' + error.message, 'danger');
  }
}

// ページ読み込み時にCSRFトークンを確認
document.addEventListener('DOMContentLoaded', function() {
  const csrfToken = getCookie('csrftoken');
  if (!csrfToken) {
    console.warn('⚠️ CSRFトークンが見つかりません');
  }
});