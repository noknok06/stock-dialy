/**
 * mobile-gestures.js - スマートフォン向けジェスチャー対応とUI改善
 * カブログでのHTMXベースのスマートフォン操作性向上のための機能
 * タブ切り替え最適化版
 */

// デバッグモードを有効化
const DEBUG = false;

// デバッグログ関数
function debugLog(...args) {
  if (DEBUG) {
    // console.log('[Swipe Debug]', ...args);
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
    // タブ切り替えでは視覚的フィードバックのみ提供し、実際の切り替えはタッチ終了時に行う
    if (Math.abs(diffX) > 30 && diffY < 50) {
      debugLog('Swipe detected during movement', diffX, 'px');
      
      // ページスクロールを防止（タブ内のスワイプの場合のみ）
      if (this.classList.contains('diary-card') || this.closest('.diary-card')) {
        e.preventDefault();
      }
      
      // 視覚的なフィードバックとして軽い移動効果を適用
      this.style.transition = 'none';
      this.style.transform = `translateX(${diffX/3}px)`; // 抵抗感を出すために移動量を3分の1に
    }
  };

  window.handleTouchEnd = function(e) {
    debugLog('Touch END on element', this.tagName, this.className);
    
    // 長押し検出をキャンセル
    if (this.longPressTimer) {
      clearTimeout(this.longPressTimer);
      this.longPressTimer = null;
    }
    
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
    
    // スワイプの処理
    const swipeThreshold = 80;
    
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
    
    // トランスフォームアニメーションをリセット
    this.style.transition = 'transform 0.3s ease-out';
    this.style.transform = 'translateX(0)';
    
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
   * スワイプアクションを処理
   * 日記カードの場合はタブ切り替え、カレンダーの場合は月切り替え
   */
  function handleSwipeAction(element, direction) {
    // 日記カードの場合
    const diaryCard = element.classList.contains('diary-card') ? element : element.closest('.diary-card');
    
    if (diaryCard) {
      debugLog('Processing swipe action for diary card', diaryCard.getAttribute('data-diary-id'), 'direction:', direction);
      
      // タブコンテナを取得
      const tabsContainer = diaryCard.querySelector('.nav-tabs');
      if (!tabsContainer) {
        debugLog('No tabs container found in diary card');
        return;
      }
      
      // 現在アクティブなタブを取得
      const activeTab = tabsContainer.querySelector('.nav-link.active');
      if (!activeTab) {
        debugLog('No active tab found');
        return;
      }
      
      // すべてのタブボタンを配列として取得
      const allTabs = Array.from(tabsContainer.querySelectorAll('.nav-link'));
      const currentIndex = allTabs.indexOf(activeTab);
      
      debugLog('Current active tab index:', currentIndex, 'total tabs:', allTabs.length);
      
      let nextIndex = currentIndex;
      
      // 次または前のタブのインデックスを計算
      if (direction === 'left' && currentIndex < allTabs.length - 1) {
        // 左スワイプ → 次のタブ
        nextIndex = currentIndex + 1;
      } else if (direction === 'right' && currentIndex > 0) {
        // 右スワイプ → 前のタブ
        nextIndex = currentIndex - 1;
      }
      
      // インデックスが変わった場合のみタブ切り替え
      if (nextIndex !== currentIndex) {
        debugLog('Switching to tab index:', nextIndex);
        
        // 選択したタブをハイライト
        allTabs[nextIndex].classList.add('tab-highlight');
        
        // タブ切り替えイベントを発火
        allTabs[nextIndex].click();
        
        // タブハイライト効果を遅延解除
        setTimeout(() => {
          allTabs[nextIndex].classList.remove('tab-highlight');
        }, 300);
      }
    } 
    // カレンダーの場合
    else if (element.closest('#mobile-calendar-container') || element.closest('#desktop-calendar-container')) {
      debugLog('Calendar swipe detected:', direction);
      
      const calendarContainer = element.closest('#mobile-calendar-container') || element.closest('#desktop-calendar-container');
      
      if (direction === 'right') {
        // 右スワイプ：前月
        const prevButton = calendarContainer.querySelector('.calendar-nav-button:first-child');
        if (prevButton) prevButton.click();
      } else {
        // 左スワイプ：翌月
        const nextButton = calendarContainer.querySelector('.calendar-nav-button:nth-child(2)');
        if (nextButton) nextButton.click();
      }
    }
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
      
      // 新しいイベントリスナーを追加
      card.addEventListener('touchstart', window.handleTouchStart, {passive: true});
      card.addEventListener('touchmove', window.handleTouchMove, {passive: false});
      card.addEventListener('touchend', window.handleTouchEnd, {passive: true});
      
      debugLog(`Set up swipe handler for card ${index+1}/${diaryCards.length}`, card.getAttribute('data-diary-id'));
    });
  }

  // 初期化関数呼び出し
  setupDiaryCardSwipeHandler();

  // HTMX イベントリスナー - コンテンツ更新時にスワイプハンドラーを再設定
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

  // オフライン検出イベントを追加
  window.addEventListener('online', function() {
    debugLog('Device is now online');
  });
  
  window.addEventListener('offline', function() {
    debugLog('Device is now offline');
  });
});
/**
 * モバイル最適化版カブログのタブスワイプ機能
 */
document.addEventListener('DOMContentLoaded', function() {
  // スワイプインジケーターの追加
  const addSwipeIndicators = function() {
    document.querySelectorAll('.card-tabs').forEach(tabContainer => {
      // すでに存在する場合は作成しない
      if (tabContainer.querySelector('.swipe-indicator')) return;
      
      // 左右のスワイプインジケーターを追加
      const leftIndicator = document.createElement('span');
      leftIndicator.className = 'swipe-indicator left';
      
      const rightIndicator = document.createElement('span');
      rightIndicator.className = 'swipe-indicator right';
      
      tabContainer.appendChild(leftIndicator);
      tabContainer.appendChild(rightIndicator);
    });
  };
  
  // カードクリックイベントの処理
  const setupCardClickHandler = function() {
    document.querySelectorAll('.diary-card').forEach(card => {
      card.addEventListener('click', function(e) {
        // タブやボタンがクリックされた場合は何もしない
        if (e.target.closest('.nav-link') || 
            e.target.closest('button') || 
            e.target.closest('a') ||
            e.target.closest('.tab-content')) {
          return;
        }
        
        // カードのクリックで詳細ページへ移動
        const diaryId = this.getAttribute('data-diary-id');
        if (diaryId) {
          window.location.href = `/stockdiary/${diaryId}/`;
        }
      });
    });
  };
  
  // スワイプ操作の処理強化
  const enhanceSwipeHandling = function() {
    // すでに定義されているスワイプ処理に追加機能を提供
    const originalHandleSwipeAction = window.handleSwipeAction || function() {};
    
    window.handleSwipeAction = function(element, direction) {
      // 元の処理を実行
      originalHandleSwipeAction(element, direction);
      
      // 視覚的フィードバックを追加
      const tabsContainer = element.querySelector('.card-tabs') || 
                          element.closest('.diary-card')?.querySelector('.card-tabs');
      
      if (tabsContainer) {
        // アクティブタブと全タブを取得
        const activeTab = tabsContainer.querySelector('.nav-link.active');
        const allTabs = Array.from(tabsContainer.querySelectorAll('.nav-link'));
        
        if (activeTab && allTabs.length > 1) {
          const currentIndex = allTabs.indexOf(activeTab);
          
          // スワイプ方向に基づいて次/前のタブをハイライト
          if (direction === 'left' && currentIndex < allTabs.length - 1) {
            allTabs[currentIndex + 1].classList.add('tab-highlight');
            setTimeout(() => allTabs[currentIndex + 1].classList.remove('tab-highlight'), 300);
          } else if (direction === 'right' && currentIndex > 0) {
            allTabs[currentIndex - 1].classList.add('tab-highlight');
            setTimeout(() => allTabs[currentIndex - 1].classList.remove('tab-highlight'), 300);
          }
        }
      }
    };
  };
  
  // 機能の初期化
  addSwipeIndicators();
  setupCardClickHandler();
  enhanceSwipeHandling();
  
  // HTMX イベントリスナー - コンテンツ更新時に機能を再初期化
  document.body.addEventListener('htmx:afterSwap', function(evt) {
    setTimeout(() => {
      addSwipeIndicators();
      setupCardClickHandler();
    }, 100);
  });
});