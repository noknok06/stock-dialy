  // 通知タイプに応じてフィールドを切り替え
  document.getElementById('notificationType').addEventListener('change', function() {
    const type = this.value;
    document.getElementById('reminderFields').style.display = type === 'reminder' ? 'block' : 'none';
    document.getElementById('priceAlertFields').style.display = type === 'price_alert' ? 'block' : 'none';
    document.getElementById('periodicFields').style.display = type === 'periodic' ? 'block' : 'none';
  });
    
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
        console.log('✅ CSRFトークンをhiddenフィールドから取得');
      }
    }
    
    // 方法3: metaタグから取得
    if (!token) {
      const csrfMeta = document.querySelector('meta[name="csrf-token"]');
      if (csrfMeta) {
        token = csrfMeta.content;
        console.log('✅ CSRFトークンをmetaタグから取得');
      }
    }
    
    return token;
  }
  
  async function saveNotification(diaryId) {
    const type = document.getElementById('notificationType').value;
    const message = document.getElementById('notificationMessage').value;
    
    console.log('=== Saving Notification ===');
    console.log('Diary ID:', diaryId);
    console.log('Type:', type);
    console.log('Message:', message);
    
    const data = {
      notification_type: type,
      message: message
    };
    
    // タイプ別のデータ収集
    if (type === 'reminder') {
      const remindAtValue = document.getElementById('remindAt').value;
      if (!remindAtValue) {
        showToast('通知日時を入力してください', 'warning');
        return;
      }
      data.remind_at = remindAtValue;
      console.log('Remind at:', remindAtValue);
      
    } else if (type === 'price_alert') {
      const targetPrice = document.getElementById('targetPrice').value;
      if (!targetPrice) {
        showToast('目標価格を入力してください', 'warning');
        return;
      }
      data.target_price = parseFloat(targetPrice);
      data.alert_above = document.getElementById('alertAbove').checked;
      console.log('Target price:', targetPrice, 'Alert above:', data.alert_above);
      
    } else if (type === 'periodic') {
      const frequency = document.getElementById('frequency').value;
      const notifyTime = document.getElementById('notifyTime').value;
      
      if (!frequency) {
        showToast('通知頻度を選択してください', 'warning');
        return;
      }
      
      data.frequency = frequency;
      if (notifyTime) {
        data.notify_time = notifyTime;
      }
      console.log('Frequency:', frequency, 'Notify time:', notifyTime);
    }
    
    console.log('Sending data:', JSON.stringify(data, null, 2));
    
    try {
      const csrfToken = getCSRFToken();
      console.log('CSRF Token:', csrfToken ? 'Found' : 'Not found');
      
      if (!csrfToken) {
        console.error('❌ CSRFトークンが見つかりません');
        console.error('ページにCSRFトークンが含まれていることを確認してください');
        showToast('セッションが無効です。ページを再読み込みしてください。', 'danger');
        return;
      }
      
      // 🔧 修正: 複数のURLパターンを試す
      const possibleUrls = [
        `/stockdiary/api/diary/${diaryId}/notifications/create/`,
        `/api/diary/${diaryId}/notifications/create/`,
        `/diary/${diaryId}/notifications/create/`,
        `/stockdiary/diary/${diaryId}/notifications/create/`
      ];
      
      const url = possibleUrls[0]; // まず最初のURLを試す
      console.log('Request URL:', url);
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest' // AJAX リクエストであることを明示
        },
        credentials: 'same-origin', // Cookie を含める
        body: JSON.stringify(data)
      });
      
      console.log('Response status:', response.status);
      console.log('Response headers:', response.headers.get('content-type'));
      
      // 🔧 追加: レスポンステキストを確認
      const responseText = await response.text();
      console.log('Response text (first 300 chars):', responseText.substring(0, 300));
      
      // 🔧 修正: ステータスコードとコンテンツタイプを確認
      const contentType = response.headers.get('content-type');
      
      // 404の場合、別のURLを試すことを提案
      if (response.status === 404) {
        console.error('❌ API endpoint not found (404)');
        console.error('Tried URL:', url);
        console.error('Available URLs to check:', possibleUrls);
        showToast('APIエンドポイントが見つかりません。URLを確認してください。', 'danger');
        return;
      }
      
      // 認証エラーの場合
      if (response.status === 401 || response.status === 403) {
        console.error('❌ Authentication/Permission error');
        showToast('ログインが必要です。ページを再読み込みしてください。', 'danger');
        return;
      }
      
      // HTMLレスポンスの場合（リダイレクトやエラーページ）
      if (!contentType || !contentType.includes('application/json')) {
        console.error('❌ Response is not JSON. Content-Type:', contentType);
        console.error('Full response (first 500 chars):', responseText.substring(0, 500));
        
        // HTMLの場合、タイトルを抽出して表示
        const titleMatch = responseText.match(/<title>(.*?)<\/title>/i);
        const pageTitle = titleMatch ? titleMatch[1] : 'Unknown Page';
        console.error('Received HTML page:', pageTitle);
        
        showToast(`サーバーエラー: ${pageTitle}。開発者ツールのコンソールを確認してください。`, 'danger');
        return;
      }
      
      const result = JSON.parse(responseText);
      console.log('Response data:', result);
      
      if (response.ok && result.success) {
        showToast(result.message || '通知を設定しました', 'success');
        
        // モーダルを閉じる
        const modal = bootstrap.Modal.getInstance(document.getElementById('notificationModal'));
        if (modal) {
          modal.hide();
        }
        
        // フォームをリセット
        document.getElementById('notificationMessage').value = '';
        document.getElementById('remindAt').value = '';
        document.getElementById('targetPrice').value = '';
        document.getElementById('notifyTime').value = '';
        
        // 通知一覧を更新（オプション）
        console.log('Notification created with ID:', result.notification_id);
        
      } else {
        const errorMsg = result.error || '通知設定に失敗しました';
        console.error('Error:', errorMsg);
        showToast(errorMsg, 'danger');
      }
      
    } catch (error) {
      console.error('❌ Network error:', error);
      console.error('Error stack:', error.stack);
      showToast('通信エラーが発生しました: ' + error.message, 'danger');
    }
  }

  // ページ読み込み時にCSRFトークンを確認
  document.addEventListener('DOMContentLoaded', function() {
    const csrfToken = getCookie('csrftoken');
    if (!csrfToken) {
      console.warn('⚠️ CSRFトークンが見つかりません');
    } else {
      console.log('✅ CSRFトークンが見つかりました');
    }
  });