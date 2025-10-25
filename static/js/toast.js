// static/js/toast.js
/**
 * トースト通知を表示する共通関数
 * @param {string} message - 表示するメッセージ
 * @param {string} type - トーストのタイプ (success, danger, warning, info)
 * @param {number} duration - 表示時間（ミリ秒）
 */
function showToast(message, type = 'info', duration = 3000) {
  // 既存のトーストコンテナを取得または作成
  let toastContainer = document.getElementById('toast-container');
  
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toast-container';
    toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    toastContainer.style.zIndex = '9999';
    document.body.appendChild(toastContainer);
  }

  // トーストの色を決定
  const bgColorClass = {
    'success': 'bg-success',
    'danger': 'bg-danger',
    'warning': 'bg-warning',
    'info': 'bg-info',
    'primary': 'bg-primary',
  }[type] || 'bg-info';

  // アイコンを決定
  const icon = {
    'success': 'bi-check-circle-fill',
    'danger': 'bi-x-circle-fill',
    'warning': 'bi-exclamation-triangle-fill',
    'info': 'bi-info-circle-fill',
  }[type] || 'bi-info-circle-fill';

  // トーストHTML
  const toastId = `toast-${Date.now()}`;
  const toastHTML = `
    <div id="${toastId}" class="toast align-items-center text-white ${bgColorClass} border-0" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body">
          <i class="bi ${icon} me-2"></i>
          ${message}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>
  `;

  // トーストを追加
  toastContainer.insertAdjacentHTML('beforeend', toastHTML);

  // Bootstrapのトーストを初期化して表示
  const toastElement = document.getElementById(toastId);
  const toast = new bootstrap.Toast(toastElement, {
    delay: duration,
    autohide: true
  });

  toast.show();

  // トーストが非表示になったら要素を削除
  toastElement.addEventListener('hidden.bs.toast', function() {
    toastElement.remove();
  });
}

// グローバルに公開
window.showToast = showToast;