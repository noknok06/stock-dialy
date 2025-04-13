/**
 * mobile-gestures.js - スマートフォン向けジェスチャー対応とUI改善
 * カブログでのHTMXベースのスマートフォン操作性向上のための機能
 * デバッグ強化版
 */

// デバッグモードを有効化
const DEBUG = false;

// デバッグログ関数
function debugLog(...args) {
  if (DEBUG) {
    console.log('[Swipe Debug]', ...args);
  }
}

document.addEventListener('DOMContentLoaded', function() {
  debugLog('DOM Content Loaded - Initializing mobile gestures');
  
  // スピードダイアルとの互換性確保
  if (typeof window.speedDialInstance !== 'undefined') {
    debugLog('Speed Dial already initialized, maintaining compatibility');
  }

  // モバイルデバイス判定 - デバッグ用にPC検証でも常に有効化
  const isMobile = true; // デバッグ用に常にtrue - 本番環境では元の条件に戻す

  // グローバルで共有するイベントハンドラーを定義
  window.handleTouchStart = function(e) {
    debugLog('Touch START on element', this.tagName, this.className, 'data-diary-id:', this.getAttribute('data-diary-id'));
    
    const touch = e.touches[0];
    window.touchStartX = touch.clientX;
    window.touchStartY = touch.clientY;
    window.touchStartTime = Date.now();
    
    // 視覚的フィードバックを追加
    this.style.backgroundColor = 'rgba(200, 200, 255, 0.1)';
    
    // 長押し検出用のタイマー設定
    this.longPressTimer = setTimeout(() => {
      debugLog('Long press detected');
      const touchElement = this;
      
      // 長押しイベントをトリガー
      if (this.hasAttribute('hx-trigger') && this.getAttribute('hx-trigger').includes('longpress')) {
        const longPressEvent = new CustomEvent('longpress', {
          bubbles: true,
          cancelable: true
        });
        this.dispatchEvent(longPressEvent);
        
        // 振動フィードバック
        if (navigator.vibrate) {
          navigator.vibrate(50);
        }
        
        touchElement.classList.add('long-press-active');
        setTimeout(() => {
          touchElement.classList.remove('long-press-active');
        }, 300);
      }
    }, 500);
  };

  window.handleTouchMove = function(e) {
    // 長押し検出をキャンセル
    if (this.longPressTimer) {
      clearTimeout(this.longPressTimer);
      this.longPressTimer = null;
    }
    
    const touch = e.touches[0];
    window.touchEndX = touch.clientX;
    window.touchEndY = touch.clientY;
    
    // 移動距離を計算
    const diffX = window.touchEndX - window.touchStartX;
    const diffY = Math.abs(window.touchEndY - window.touchStartY);
    
    // 水平方向の移動が大きい場合、スワイプとして処理
    if (Math.abs(diffX) > 30 && diffY < 50) {
      debugLog('Swipe detected during movement', diffX, 'px');
      
      // ページスクロールを防止
      e.preventDefault();
      
      // スワイプ方向に応じてカードを動かす視覚的効果
      this.style.transition = 'none';
      this.style.transform = `translateX(${diffX}px)`;
      
      // スワイプの方向に応じたスタイルを適用
      if (diffX > 0) {
        // 右スワイプ（編集アクション）
        this.classList.add('swipe-right-active');
        this.classList.remove('swipe-left-active');
      } else {
        // 左スワイプ（削除アクション）
        this.classList.add('swipe-left-active');
        this.classList.remove('swipe-right-active');
      }
    }
  };

  window.handleTouchEnd = function(e) {
    debugLog('Touch END on element', this.tagName, this.className);
    
    // 長押し検出をキャンセル
    if (this.longPressTimer) {
      clearTimeout(this.longPressTimer);
      this.longPressTimer = null;
    }
    
    // 視覚的フィードバックをリセット
    this.style.backgroundColor = '';
    
    // タッチ終了時の位置を取得
    let finalX = window.touchEndX;
    let finalY = window.touchEndY;
    
    if (e.changedTouches && e.changedTouches.length > 0) {
      finalX = e.changedTouches[0].clientX;
      finalY = e.changedTouches[0].clientY;
    }
    
    const diffX = finalX - window.touchStartX;
    const diffY = Math.abs(finalY - window.touchStartY);
    const touchDuration = Date.now() - window.touchStartTime;
    
    debugLog('Touch ended with diffX:', diffX, 'diffY:', diffY, 'duration:', touchDuration);
    
    // スワイプの処理 - 閾値を下げてテスト用に調整
    const swipeThreshold = 80; // 通常は100だが、テスト用に閾値を下げる
    
    if (Math.abs(diffX) > swipeThreshold && diffY < 50) {
      debugLog('SWIPE ACTION TRIGGERED!', diffX > 0 ? 'RIGHT' : 'LEFT');
      
      // 振動フィードバック
      if (navigator.vibrate) {
        navigator.vibrate(25);
      }
      
      // スワイプ方向を判定
      const swipeDirection = diffX > 0 ? 'right' : 'left';
      
      // スワイプに対応するアクションをトリガー
      handleSwipeAction(this, swipeDirection);
      
      // イベントをさらに伝播させない
      e.stopPropagation();
    }
    
    // スワイプ中のスタイルをリセット
    resetSwipeStyles(this);
    
    // 短いタップとして処理（200ms以下のタッチ）
    if (touchDuration < 200 && Math.abs(diffX) < 10 && diffY < 10) {
      debugLog('Short tap detected');
      
      // タップ効果
      this.classList.add('tap-active');
      setTimeout(() => {
        this.classList.remove('tap-active');
      }, 150);
    }
  };

  /**
   * スワイプ時のスタイルをリセット
   */
  function resetSwipeStyles(element) {
    // トランスフォームアニメーションを設定
    element.style.transition = 'transform 0.3s ease-out';
    element.style.transform = 'translateX(0)';
    
    // アニメーション終了後にスタイルをクリーンアップ
    setTimeout(() => {
      element.style.transition = '';
      element.classList.remove('swipe-left-active', 'swipe-right-active');
    }, 300);
  }

  /**
   * スワイプアクションを処理
   */
  function handleSwipeAction(element, direction) {
    // 日記カードの場合
    if (element.classList.contains('diary-card')) {
      const diaryId = element.getAttribute('data-diary-id');
      
      debugLog('Processing swipe action for diary card', diaryId, 'direction:', direction);
      
      if (direction === 'right') {
        // 右スワイプ：編集アクション
        debugLog('RIGHT SWIPE - Opening edit drawer for diary', diaryId);
        showActionDrawer(element, 'edit', diaryId);
      } else {
        // 左スワイプ：削除アクション
        debugLog('LEFT SWIPE - Opening delete drawer for diary', diaryId);
        showActionDrawer(element, 'delete', diaryId);
      }
    } 
    // カレンダーの場合
    else if (element.closest('#mobile-calendar-container') || element.closest('#desktop-calendar-container')) {
      debugLog('Calendar swipe detected:', direction);
      
      if (direction === 'right') {
        // 右スワイプ：前月
        const prevButton = element.querySelector('.calendar-nav-button:first-child');
        if (prevButton) prevButton.click();
      } else {
        // 左スワイプ：翌月
        const nextButton = element.querySelector('.calendar-nav-button:nth-child(2)');
        if (nextButton) nextButton.click();
      }
    }
  }

  /**
   * アクションドロワーを表示
   */
  function showActionDrawer(element, actionType, diaryId) {
    debugLog('Showing action drawer', actionType, 'for diary', diaryId);
    
    // 既存のドロワーを削除
    const existingDrawer = document.getElementById('action-drawer');
    if (existingDrawer) {
      existingDrawer.remove();
    }
    
    // ドロワーを作成
    const drawer = document.createElement('div');
    drawer.id = 'action-drawer';
    drawer.className = 'action-drawer action-drawer-' + actionType;
    
    // アクションタイプに応じたコンテンツを設定
    if (actionType === 'edit') {
      drawer.innerHTML = `
        <div class="action-drawer-content">
          <div class="action-drawer-header">
            <h5><i class="bi bi-pencil me-2"></i>編集オプション</h5>
            <button type="button" class="action-drawer-close">×</button>
          </div>
          <div class="action-drawer-body">
            <a href="/stockdiary/${diaryId}/update/" class="action-btn">
              <i class="bi bi-pencil-square"></i>日記を編集
            </a>
            ${element.classList.contains('memo-card') ? '' : 
              `<a href="/stockdiary/sell/${diaryId}/" class="action-btn">
                <i class="bi bi-cash-coin"></i>売却情報を登録
              </a>`
            }
            <a href="/stockdiary/${diaryId}/" class="action-btn">
              <i class="bi bi-eye"></i>詳細を表示
            </a>
            <a href="#" class="action-btn" id="addNoteBtn" data-diary-id="${diaryId}">
              <i class="bi bi-journal-plus"></i>継続記録を追加
            </a>
          </div>
        </div>
      `;
    } else {
      drawer.innerHTML = `
        <div class="action-drawer-content">
          <div class="action-drawer-header">
            <h5><i class="bi bi-trash me-2"></i>削除の確認</h5>
            <button type="button" class="action-drawer-close">×</button>
          </div>
          <div class="action-drawer-body">
            <p class="text-danger">この日記を削除してもよろしいですか？</p>
            <div class="action-buttons">
              <a href="/stockdiary/${diaryId}/delete/" class="action-btn action-btn-danger">
                <i class="bi bi-trash"></i>削除する
              </a>
              <button type="button" class="action-btn action-btn-secondary action-drawer-cancel">
                <i class="bi bi-x"></i>キャンセル
              </button>
            </div>
          </div>
        </div>
      `;
    }
    
    // ドロワーを追加
    document.body.appendChild(drawer);
    
    // 表示アニメーション
    setTimeout(() => {
      drawer.classList.add('action-drawer-active');
    }, 10);
    
    // クローズボタンのイベントを設定
    drawer.querySelector('.action-drawer-close').addEventListener('click', () => {
      closeActionDrawer(drawer);
    });
    
    // キャンセルボタンのイベント
    const cancelBtn = drawer.querySelector('.action-drawer-cancel');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => {
        closeActionDrawer(drawer);
      });
    }
    
    // 継続記録追加ボタンのイベント
    const addNoteBtn = drawer.querySelector('#addNoteBtn');
    if (addNoteBtn) {
      addNoteBtn.addEventListener('click', (e) => {
        e.preventDefault();
        
        // ドロワーを閉じる
        closeActionDrawer(drawer);
        
        // 詳細ページに移動
        window.location.href = `/stockdiary/${diaryId}/#add-note`;
      });
    }
    
    // ドロワー外クリックでクローズ
    drawer.addEventListener('click', (e) => {
      if (e.target === drawer) {
        closeActionDrawer(drawer);
      }
    });
  }

  /**
   * アクションドロワーを閉じる
   */
  function closeActionDrawer(drawer) {
    drawer.classList.remove('action-drawer-active');
    setTimeout(() => {
      drawer.remove();
    }, 300);
  }

  // === 日記カードのスワイプ設定 ===
  function setupDiaryCardSwipeHandler() {
    debugLog('Setting up swipe handlers for all diary cards');
    
    // すべての日記カードにスワイプハンドラーを追加
    const diaryCards = document.querySelectorAll('.diary-card');
    debugLog(`Found ${diaryCards.length} diary cards`);
    
    diaryCards.forEach((card, index) => {
      // 既存のイベントリスナーを削除
      card.removeEventListener('touchstart', window.handleTouchStart);
      card.removeEventListener('touchmove', window.handleTouchMove);
      card.removeEventListener('touchend', window.handleTouchEnd);
      
      // コメントアウトを解除して新しいイベントリスナーを追加
      card.addEventListener('touchstart', window.handleTouchStart, {passive: true});
      card.addEventListener('touchmove', window.handleTouchMove, {passive: false});
      card.addEventListener('touchend', window.handleTouchEnd, {passive: true});
      
      debugLog(`Set up swipe handler for card ${index+1}/${diaryCards.length}`, card.getAttribute('data-diary-id'));
    });
    
    // 視覚的なデバッグ表示を追加
    diaryCards.forEach(card => {
      // デバッグ用インジケーターを追加
      const debugIndicator = document.createElement('div');
      debugIndicator.className = 'swipe-debug-indicator';
      debugIndicator.style.position = 'absolute';
      debugIndicator.style.top = '0';
      debugIndicator.style.right = '0';
      debugIndicator.style.background = 'rgba(0, 255, 0, 0.5)';
      debugIndicator.style.padding = '2px 5px';
      debugIndicator.style.fontSize = '10px';
      debugIndicator.style.borderRadius = '0 0 0 5px';
      debugIndicator.textContent = 'スワイプOK';
      debugIndicator.style.zIndex = '10';
      
      // すでに存在していないことを確認
      // const existingIndicator = card.querySelector('.swipe-debug-indicator');
      // if (!existingIndicator) {
      //   card.style.position = 'relative';
      //   card.appendChild(debugIndicator);
      // }
    });
  }

  // 初期化関数呼び出し
  setupDiaryCardSwipeHandler();

  // HTMX イベントリスナー
  document.body.addEventListener('htmx:afterSwap', function(evt) {
    debugLog('HTMX afterSwap event on', evt.detail.target.id);
    
    if (evt.detail.target.id === 'diary-container') {
      // DOM更新を待ってから実行
      setTimeout(() => {
        debugLog('Re-applying swipe handlers after HTMX swap');
        setupDiaryCardSwipeHandler();
      }, 100);
    }
  });

  // タブなどの表示切り替え後にも再初期化
  document.addEventListener('shown.bs.tab', function() {
    debugLog('Tab shown event - reinitializing swipe handlers');
    setTimeout(setupDiaryCardSwipeHandler, 50);
  });

  // リサイズイベントでも再初期化（レイアウト変更に対応）
  window.addEventListener('resize', function() {
    debugLog('Window resize - reinitializing swipe handlers');
    setTimeout(setupDiaryCardSwipeHandler, 100);
  });

  // 手動での再初期化ボタン追加（デバッグ用）
  function addDebugControls() {
    const controlPanel = document.createElement('div');
    controlPanel.style.position = 'fixed';
    controlPanel.style.bottom = '80px';
    controlPanel.style.right = '10px';
    controlPanel.style.zIndex = '9999';
    controlPanel.style.background = 'rgba(0,0,0,0.7)';
    controlPanel.style.color = 'white';
    controlPanel.style.padding = '10px';
    controlPanel.style.borderRadius = '5px';
    controlPanel.style.fontSize = '12px';
    
    // controlPanel.innerHTML = `
    //   <div>スワイプデバッグ</div>
    //   <button id="reinitSwipe" style="background:#4a90e2;color:white;border:none;padding:5px;margin:5px;border-radius:3px;">
    //     再初期化
    //   </button>
    //   <div id="swipeStatus">準備完了</div>
    // `;
    
    // document.body.appendChild(controlPanel);
    
    document.getElementById('reinitSwipe').addEventListener('click', function() {
      setupDiaryCardSwipeHandler();
      document.getElementById('swipeStatus').textContent = '再初期化完了: ' + new Date().toLocaleTimeString();
    });
  }
  
  // デバッグコントロールパネルを追加
  if (DEBUG) {
    addDebugControls();
  }
});