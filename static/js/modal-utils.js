// static/js/modal-utils.js
// モーダル管理のユーティリティ関数

/**
 * すべてのモーダル背景を強制的にクリーンアップ
 */
function forceCleanupModals() {
    // すべての .modal-backdrop を削除
    const backdrops = document.querySelectorAll('.modal-backdrop');
    backdrops.forEach(backdrop => {
      backdrop.classList.remove('show');
      setTimeout(() => backdrop.remove(), 150);
    });
    
    // すべてのモーダルを非表示にする
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
      modal.classList.remove('show');
      modal.style.display = 'none';
      modal.setAttribute('aria-hidden', 'true');
    });
    
    // body のクラスとスタイルをクリーンアップ
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    document.body.style.paddingRight = '';
    
    // console.log('Modal cleanup completed');
  }
  
  /**
   * 安全にモーダルを開く
   * @param {string} modalId - モーダルのID
   * @param {Object} options - Bootstrap モーダルのオプション
   */
  function safeOpenModal(modalId, options = {}) {
    // 既存のモーダルをクリーンアップ
    forceCleanupModals();
    
    // 少し待ってから新しいモーダルを開く
    setTimeout(() => {
      const modalElement = document.getElementById(modalId);
      if (!modalElement) {
        console.error(`Modal with id "${modalId}" not found`);
        return;
      }
      
      const defaultOptions = {
        backdrop: 'static',
        keyboard: false
      };
      
      const modal = new bootstrap.Modal(modalElement, {
        ...defaultOptions,
        ...options
      });
      
      modal.show();
    }, 100);
  }
  
  /**
   * 安全にモーダルを閉じる
   * @param {string} modalId - モーダルのID
   */
  function safeCloseModal(modalId) {
    const modalElement = document.getElementById(modalId);
    if (!modalElement) {
      console.error(`Modal with id "${modalId}" not found`);
      return;
    }
    
    const modalInstance = bootstrap.Modal.getInstance(modalElement);
    if (modalInstance) {
      modalInstance.hide();
    }
    
    // 念のため強制クリーンアップ
    setTimeout(forceCleanupModals, 300);
  }
  
  /**
   * モーダルの状態を確認
   */
  function checkModalState() {
    const backdrops = document.querySelectorAll('.modal-backdrop');
    const openModals = document.querySelectorAll('.modal.show');
    
    // console.log('Modal state check:');
    // console.log(`- Backdrops found: ${backdrops.length}`);
    // console.log(`- Open modals: ${openModals.length}`);
    // console.log(`- Body has modal-open: ${document.body.classList.contains('modal-open')}`);
    
    if (backdrops.length > 0 && openModals.length === 0) {
      console.warn('⚠️ Orphaned backdrop detected! Cleaning up...');
      forceCleanupModals();
    }
  }
  
  /**
   * グローバルなモーダルエラーハンドリング
   */
  function setupGlobalModalHandlers() {
    // すべてのモーダルに共通のイベントリスナーを設定
    document.querySelectorAll('.modal').forEach(modal => {
      // モーダルが表示される前
      modal.addEventListener('show.bs.modal', function(e) {
        // console.log(`Modal ${this.id} is showing`);
      });
      
      // モーダルが完全に表示された後
      modal.addEventListener('shown.bs.modal', function(e) {
        // console.log(`Modal ${this.id} is shown`);
        // 最初のフォーカス可能な要素にフォーカス
        const firstInput = this.querySelector('input:not([type="hidden"]), select, textarea');
        if (firstInput) {
          firstInput.focus();
        }
      });
      
      // モーダルが隠れる前
      modal.addEventListener('hide.bs.modal', function(e) {
        // console.log(`Modal ${this.id} is hiding`);
      });
      
      // モーダルが完全に隠れた後
      modal.addEventListener('hidden.bs.modal', function(e) {
        // console.log(`Modal ${this.id} is hidden`);
        // クリーンアップを実行
        setTimeout(() => {
          const remainingBackdrops = document.querySelectorAll('.modal-backdrop');
          if (remainingBackdrops.length > 0) {
            console.warn('Cleaning up remaining backdrops');
            forceCleanupModals();
          }
        }, 100);
      });
    });
    
    // ページ読み込み完了後に状態チェック
    window.addEventListener('load', () => {
      setTimeout(checkModalState, 500);
    });
    
    // ページ離脱時のクリーンアップ
    window.addEventListener('beforeunload', forceCleanupModals);
    
    // Escキーでモーダルを閉じる（グローバル）
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        const openModal = document.querySelector('.modal.show');
        if (openModal) {
          safeCloseModal(openModal.id);
        }
      }
    });
    
    // console.log('Global modal handlers initialized');
  }
  
  // DOMContentLoaded で初期化
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupGlobalModalHandlers);
  } else {
    setupGlobalModalHandlers();
  }
  
  // グローバルに公開
  window.forceCleanupModals = forceCleanupModals;
  window.safeOpenModal = safeOpenModal;
  window.safeCloseModal = safeCloseModal;
  window.checkModalState = checkModalState;