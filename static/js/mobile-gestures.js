/**
 * mobile-gestures.js - スマートフォン向けジェスチャー対応とUI改善
 * カブログでのHTMXベースのスマートフォン操作性向上のための機能
 */

document.addEventListener('DOMContentLoaded', function() {
  // スピードダイアルとの互換性確保
  if (typeof window.speedDialInstance !== 'undefined') {
    console.log('Speed Dial already initialized, maintaining compatibility');
  }

  // モバイルデバイス判定
  const isMobile = window.innerWidth < 768 || navigator.maxTouchPoints > 1;
  if (!isMobile) return; // モバイルのみ機能を有効化

  // スワイプ検出のための変数
  let touchStartX = 0;
  let touchStartY = 0;
  let touchEndX = 0;
  let touchEndY = 0;
  let touchThreshold = 100; // スワイプと判定する最小距離（ピクセル単位）
  let touchStartTime = 0;
  let longPressThreshold = 500; // 長押しと判定する時間（ミリ秒）
  const activeSwipeElements = new Set(); // アクティブにスワイプ中の要素
  
  // プル・トゥ・リフレッシュの変数
  let pullStartY = 0;
  let pullMoveY = 0;
  let isPulling = false;
  const pullThreshold = 120; // プルトゥリフレッシュのしきい値
  let pullIndicator = null;
  
  // 初期化処理
  initSwipeDetection();
  initPullToRefresh();
  initScrollToTop();
  initTouchFeedback();
  setupOfflineDetection();
  
  /**
   * スワイプ検出の初期化
   */
  function initSwipeDetection() {
    console.log('Initializing swipe detection for mobile');
    
    // スワイプ可能な要素にクラスを追加
    document.querySelectorAll('[hx-swipe]').forEach(elem => {
      elem.classList.add('swipeable');
    });
    
    // 日記カードにスワイプイベントを設定
    setupAllDiaryCards();
    
    // カレンダーにスワイプイベントを設定
    const calendarContainer = document.querySelector('#mobile-calendar-container, #desktop-calendar-container');
    if (calendarContainer) {
      setupCalendarSwipe(calendarContainer);
    }
    
    // htmxがロードした新しい要素に対してもスワイプを設定
    document.body.addEventListener('htmx:afterSwap', function(evt) {
      console.log('HTMX afterSwap event triggered on target:', evt.detail.target.id);
      
      if (evt.detail.target.id === 'diary-container') {
        // イベント発火の少し後（DOM更新後）に実行
        setTimeout(() => {
          console.log('Setting up swipe handlers for new diary cards');
          setupAllDiaryCards();
        }, 50);
      }
    });
    
    // 単一の日記追加時のイベント（クイック日記作成などで使用）
    document.body.addEventListener('htmx:afterSettle', function(evt) {
      if (evt.detail.target.classList.contains('diary-card')) {
        console.log('Setting up swipe handler for newly added diary card');
        setupSwipeHandlers(evt.detail.target);
      }
    });
  }
  
  /**
   * すべての日記カードにスワイプハンドラーを設定
   */
  function setupAllDiaryCards() {
    const diaryCards = document.querySelectorAll('.diary-card');
    console.log(`Found ${diaryCards.length} diary cards to setup swipe handlers`);
    
    diaryCards.forEach(card => {
      // すべての日記カードに対して再設定
      // data-swipe-initialized属性を削除してリセット
      card.removeAttribute('data-swipe-initialized');
      setupSwipeHandlers(card);
    });
  }
  
  /**
   * 要素にスワイプハンドラを設定
   */
  function setupSwipeHandlers(element) {
    // すでに設定済みならスキップ
    if (element.dataset.swipeInitialized === 'true') {
      return;
    }
    
    element.dataset.swipeInitialized = 'true';
    
    // 既存のイベントリスナーを削除（重複防止）
    element.removeEventListener('touchstart', handleTouchStart);
    element.removeEventListener('touchmove', handleTouchMove);
    element.removeEventListener('touchend', handleTouchEnd);
    
    // タッチイベントをセットアップ
    element.addEventListener('touchstart', handleTouchStart, {passive: true});
    element.addEventListener('touchmove', handleTouchMove, {passive: false});
    element.addEventListener('touchend', handleTouchEnd, {passive: true});
    
    console.log('Swipe handlers set up for:', element.getAttribute('data-diary-id') || 'unknown diary');
  }
  
  /**
   * タッチ開始時の処理
   */
  function handleTouchStart(e) {
    const touch = e.touches[0];
    touchStartX = touch.clientX;
    touchStartY = touch.clientY;
    touchStartTime = Date.now();
    
    // 長押し検出用のタイマー設定
    this.longPressTimer = setTimeout(() => {
      const touchElement = this;
      
      // 長押しイベントをトリガー（hx-trigger="longpress"用）
      if (this.hasAttribute('hx-trigger') && this.getAttribute('hx-trigger').includes('longpress')) {
        // カスタムイベントをディスパッチ
        const longPressEvent = new CustomEvent('longpress', {
          bubbles: true,
          cancelable: true
        });
        this.dispatchEvent(longPressEvent);
        
        // 振動フィードバック
        if (navigator.vibrate) {
          navigator.vibrate(50);
        }
        
        // 視覚的フィードバック
        touchElement.classList.add('long-press-active');
        setTimeout(() => {
          touchElement.classList.remove('long-press-active');
        }, 300);
      }
    }, longPressThreshold);
  }
  
  /**
   * タッチ移動中の処理
   */
  function handleTouchMove(e) {
    // 長押し検出をキャンセル
    if (this.longPressTimer) {
      clearTimeout(this.longPressTimer);
      this.longPressTimer = null;
    }
    
    const touch = e.touches[0];
    touchEndX = touch.clientX;
    touchEndY = touch.clientY;
    
    // 水平方向の移動が大きい場合のみ、ページスクロールを防止
    const diffX = Math.abs(touchEndX - touchStartX);
    const diffY = Math.abs(touchEndY - touchStartY);
    
    if (diffX > diffY && diffX > 30) {
      // 水平スワイプの場合はページスクロールを防止
      e.preventDefault();
      
      // スワイプに応じてカードを動かす視覚的効果
      const moveX = touchEndX - touchStartX;
      if (Math.abs(moveX) > 20) {
        // スワイプの方向に応じてカードを動かす
        this.style.transform = `translateX(${moveX / 3}px)`;
        
        // スワイプの方向に応じたスタイルを適用
        if (moveX > 0) {
          // 右スワイプ（編集アクション）
          this.classList.add('swipe-right-active');
          this.classList.remove('swipe-left-active');
        } else {
          // 左スワイプ（削除アクション）
          this.classList.add('swipe-left-active');
          this.classList.remove('swipe-right-active');
        }
        
        // アクティブなスワイプ要素として登録
        activeSwipeElements.add(this);
      }
    }
  }
  
  /**
   * タッチ終了時の処理
   */
  function handleTouchEnd(e) {
    // 長押し検出をキャンセル
    if (this.longPressTimer) {
      clearTimeout(this.longPressTimer);
      this.longPressTimer = null;
    }
    
    const diffX = touchEndX - touchStartX;
    const diffY = touchEndY - touchStartY;
    const touchDuration = Date.now() - touchStartTime;
    
    // スワイプの処理
    if (Math.abs(diffX) > touchThreshold && Math.abs(diffY) < touchThreshold) {
      // 振動フィードバック
      if (navigator.vibrate) {
        navigator.vibrate(25);
      }
      
      // スワイプ方向を判定
      const swipeDirection = diffX > 0 ? 'right' : 'left';
      
      // スワイプに対応するアクションをトリガー
      handleSwipeAction(this, swipeDirection);
    }
    
    // スワイプ中のスタイルをリセット
    resetSwipeStyles(this);
    
    // 短いタップとして処理（100ms以下のタッチ）
    if (touchDuration < 100 && Math.abs(diffX) < 5 && Math.abs(diffY) < 5) {
      // タップ効果
      this.classList.add('tap-active');
      setTimeout(() => {
        this.classList.remove('tap-active');
      }, 150);
    }
  }
  
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
    
    activeSwipeElements.delete(element);
  }
  
  /**
   * スワイプアクションを処理
   */
  function handleSwipeAction(element, direction) {
    // 日記カードの場合
    if (element.classList.contains('diary-card')) {
      const diaryId = element.getAttribute('data-diary-id');
      
      if (direction === 'right') {
        // 右スワイプ：編集アクション
        // アクション確認ダイアログを表示
        showActionDrawer(element, 'edit', diaryId);
      } else {
        // 左スワイプ：削除アクション
        showActionDrawer(element, 'delete', diaryId);
      }
    } 
    // カレンダーの場合
    else if (element.closest('#mobile-calendar-container') || element.closest('#desktop-calendar-container')) {
      const currentMonth = element.querySelector('#desktop-current-year-month, .calendar-date-display');
      
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
   * カレンダーのスワイプ設定
   */
  function setupCalendarSwipe(calendarContainer) {
    calendarContainer.addEventListener('touchstart', function(e) {
      const touch = e.touches[0];
      touchStartX = touch.clientX;
      touchStartY = touch.clientY;
    }, {passive: true});
    
    calendarContainer.addEventListener('touchmove', function(e) {
      const touch = e.touches[0];
      touchEndX = touch.clientX;
      touchEndY = touch.clientY;
      
      // 水平方向の移動が大きい場合はページスクロールを防止
      const diffX = Math.abs(touchEndX - touchStartX);
      const diffY = Math.abs(touchEndY - touchStartY);
      
      if (diffX > diffY && diffX > 30) {
        e.preventDefault();
      }
    }, {passive: false});
    
    calendarContainer.addEventListener('touchend', function(e) {
      const diffX = touchEndX - touchStartX;
      const diffY = touchEndY - touchStartY;
      
      // 水平スワイプの場合のみ処理
      if (Math.abs(diffX) > touchThreshold && Math.abs(diffY) < touchThreshold) {
        // スワイプ方向を判定
        const swipeDirection = diffX > 0 ? 'right' : 'left';
        
        // カレンダーナビゲーションボタンのクリックをシミュレート
        if (swipeDirection === 'right') {
          // 右スワイプ：前月
          const prevButton = calendarContainer.querySelector('.calendar-nav-button:first-child');
          if (prevButton) prevButton.click();
        } else {
          // 左スワイプ：翌月
          const nextButton = calendarContainer.querySelector('.calendar-nav-button:nth-child(2)');
          if (nextButton) nextButton.click();
        }
      }
    }, {passive: true});
  }
  
  /**
   * アクションドロワーを表示
   */
  function showActionDrawer(element, actionType, diaryId) {
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
  
  /**
   * プル・トゥ・リフレッシュの初期化
   */
  function initPullToRefresh() {
    // プル・トゥ・リフレッシュ対象のコンテナ
    const containerElement = document.getElementById('diary-container');
    if (!containerElement) return;
    
    // インジケーターが存在しなければ作成
    if (!document.getElementById('pull-indicator')) {
      pullIndicator = document.createElement('div');
      pullIndicator.id = 'pull-indicator';
      pullIndicator.className = 'pull-indicator';
      pullIndicator.innerHTML = `<div class="pull-indicator-content">
        <div class="pull-spinner"></div>
        <span class="pull-text">引っ張って更新</span>
      </div>`;
      
      // コンテナの前に挿入
      containerElement.parentNode.insertBefore(pullIndicator, containerElement);
    } else {
      pullIndicator = document.getElementById('pull-indicator');
    }
    
    // タッチイベントのセットアップ
    document.addEventListener('touchstart', handlePullStart, {passive: true});
    document.addEventListener('touchmove', handlePullMove, {passive: false});
    document.addEventListener('touchend', handlePullEnd, {passive: true});
  }
  
  /**
   * プル開始の処理
   */
  function handlePullStart(e) {
    // スクロール位置が先頭にある場合のみ有効
    if (window.scrollY > 0) return;
    
    const touch = e.touches[0];
    pullStartY = touch.clientY;
    isPulling = true;
  }
  
  /**
   * プル中の処理
   */
  function handlePullMove(e) {
    if (!isPulling) return;
    
    const touch = e.touches[0];
    pullMoveY = touch.clientY;
    const pullDistance = pullMoveY - pullStartY;
    
    // 下に引っ張った場合のみ処理
    if (pullDistance > 0 && window.scrollY <= 0) {
      // インジケーターの表示
      if (pullIndicator) {
        // 引っ張りの距離に応じてインジケーターを表示
        const height = Math.min(Math.pow(pullDistance, 0.8), pullThreshold);
        pullIndicator.style.height = `${height}px`;
        pullIndicator.classList.add('active');
        
        // しきい値を超えたらリリース可能状態に
        if (pullDistance > pullThreshold) {
          pullIndicator.classList.add('ready');
          pullIndicator.querySelector('.pull-text').textContent = 'リリースして更新';
        } else {
          pullIndicator.classList.remove('ready');
          pullIndicator.querySelector('.pull-text').textContent = '引っ張って更新';
        }
        
        // スピナーの回転角度も引っ張りに合わせる
        const rotation = Math.min(pullDistance / pullThreshold * 180, 180);
        pullIndicator.querySelector('.pull-spinner').style.transform = `rotate(${rotation}deg)`;
      }
      
      // スクロールを防止
      e.preventDefault();
    }
  }
  
  /**
   * プル終了の処理
   */
  function handlePullEnd(e) {
    if (!isPulling) return;
    
    const pullDistance = pullMoveY - pullStartY;
    
    // しきい値を超えた場合はHTMXリクエストをトリガー
    if (pullDistance > pullThreshold && window.scrollY <= 0) {
      // リフレッシュインジケーターの表示
      if (pullIndicator) {
        pullIndicator.classList.add('refreshing');
        pullIndicator.style.height = '60px';
        pullIndicator.querySelector('.pull-text').textContent = '更新中...';
      }
      
      // 振動フィードバック
      if (navigator.vibrate) {
        navigator.vibrate(30);
      }
      
      // 日記コンテナのリロードをトリガー
      const diaryContainer = document.getElementById('diary-container');
      if (diaryContainer && typeof htmx !== 'undefined') {
        console.log('Triggering pulldown event for diary container');
        // htmxのGETリクエストをトリガー
        htmx.trigger(diaryContainer, 'pulldown');
        
        // HTMX完了イベントを監視
        document.body.addEventListener('htmx:afterSwap', function resetPullIndicator(e) {
          // 日記コンテナへのスワップが完了したらインジケーターを非表示
          if (e.detail.target.id === 'diary-container') {
            setTimeout(() => {
              if (pullIndicator) {
                pullIndicator.classList.remove('active', 'ready', 'refreshing');
                pullIndicator.style.height = '0';
              }
              
              // リロード後に再度スワイプハンドラーを初期化
              setupAllDiaryCards();
            }, 500);
            
            // イベントリスナーを削除
            document.body.removeEventListener('htmx:afterSwap', resetPullIndicator);
          }
        });
      } else {
        // htmxが利用できない場合は通常のページリロード
        window.location.reload();
      }
    } else {
      // しきい値未満の場合はインジケーターを非表示
      if (pullIndicator) {
        pullIndicator.classList.remove('active', 'ready');
        pullIndicator.style.height = '0';
      }
    }
    
    // プル状態をリセット
    isPulling = false;
  }
  
  /**
   * スクロールトップボタンの初期化
   */
  function initScrollToTop() {
    // 既存のボタンがなければ作成
    if (!document.getElementById('scroll-top-btn')) {
      const scrollBtn = document.createElement('button');
      scrollBtn.id = 'scroll-top-btn';
      scrollBtn.className = 'scroll-top-btn';
      scrollBtn.innerHTML = '<i class="bi bi-arrow-up"></i>';
      scrollBtn.setAttribute('aria-label', 'トップにスクロール');
      document.body.appendChild(scrollBtn);
      
      // クリックイベントの設定
      scrollBtn.addEventListener('click', () => {
        window.scrollTo({
          top: 0,
          behavior: 'smooth'
        });
      });
      
      // スクロール位置に応じて表示/非表示
      window.addEventListener('scroll', debounce(() => {
        if (window.scrollY > 300) {
          scrollBtn.classList.add('visible');
        } else {
          scrollBtn.classList.remove('visible');
        }
      }, 100));
    }
  }
  
  /**
   * タッチフィードバックの初期化
   */
  function initTouchFeedback() {
    // クリック可能な要素のタッチフィードバックを強化
    const clickableSelector = 'a, button, .btn, .action-icon-btn, [role="button"], .diary-card';
    
    function addTouchFeedback(elem) {
      if (!elem.classList.contains('touch-enhanced')) {
        elem.classList.add('touch-enhanced');
        
        // タッチスタート時のエフェクト
        elem.addEventListener('touchstart', function(e) {
          this.classList.add('touch-active');
        }, {passive: true});
        
        // タッチ終了時のエフェクト
        elem.addEventListener('touchend', function(e) {
          this.classList.remove('touch-active');
        }, {passive: true});
        
        // タッチキャンセル時のエフェクト
        elem.addEventListener('touchcancel', function(e) {
          this.classList.remove('touch-active');
        }, {passive: true});
      }
    }
    
    // 既存の要素に適用
    document.querySelectorAll(clickableSelector).forEach(addTouchFeedback);
    
    // 新しく追加される要素にも適用
    // MutationObserverを使用して動的に追加される要素をキャッチ
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'childList' && mutation.addedNodes.length) {
          mutation.addedNodes.forEach((node) => {
            if (node.nodeType === 1) { // Element nodes only
              if (node.matches && node.matches(clickableSelector)) {
                addTouchFeedback(node);
              }
              
              // 子孫ノードも確認
              if (node.querySelectorAll) {
                node.querySelectorAll(clickableSelector).forEach(addTouchFeedback);
              }
            }
          });
        }
      });
    });
    
    // ルートノードの変更を監視
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
    
    // HTMXイベントでも適用
    document.body.addEventListener('htmx:afterSwap', function(evt) {
      const container = evt.detail.target;
      if (container && container.querySelectorAll) {
        container.querySelectorAll(clickableSelector).forEach(addTouchFeedback);
      }
    });
  }
  
  /**
   * オフライン状態検出の設定
   */
  function setupOfflineDetection() {
    // オンライン状態の変化を検出
    window.addEventListener('online', function() {
      document.body.classList.remove('is-offline');
      
      // オフラインキューを処理（htmxの拡張機能を使用）
      if (typeof htmx !== 'undefined' && htmx.trigger) {
        htmx.trigger(document.body, 'online');
      }
      
      // トースト通知
      showToast('ネットワーク接続が回復しました', 'success');
    });
    
    window.addEventListener('offline', function() {
      document.body.classList.add('is-offline');
      
      // トースト通知
      showToast('オフラインモードになりました', 'warning');
    });
    
    // htmxリクエスト前にオフラインチェック
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
      if (!navigator.onLine) {
        // オフラインの場合はhtmxリクエストをキャンセル
        evt.preventDefault();
        
        // オフライン通知
        showToast('オフラインのため更新できません', 'warning');
      }
    });
  }
  
  /**
   * トースト通知を表示
   */
  function showToast(message, type = 'info') {
    // 既存のトーストがあれば削除
    const existingToast = document.querySelector('.mobile-toast');
    if (existingToast) {
      existingToast.remove();
    }
    
    // トースト要素を作成
    const toast = document.createElement('div');
    toast.className = `mobile-toast mobile-toast-${type}`;
    
    // アイコンを設定
    let icon = 'info-circle';
    if (type === 'success') icon = 'check-circle';
    if (type === 'warning') icon = 'exclamation-triangle';
    if (type === 'danger') icon = 'exclamation-circle';
    
    toast.innerHTML = `
      <div class="mobile-toast-content">
        <i class="bi bi-${icon}"></i>
        <span>${message}</span>
      </div>
    `;
    
    // DOMに追加
    document.body.appendChild(toast);
    
    // 表示アニメーション
    setTimeout(() => {
      toast.classList.add('mobile-toast-visible');
    }, 10);
    
    // 3秒後に非表示
    setTimeout(() => {
      toast.classList.remove('mobile-toast-visible');
      setTimeout(() => {
        toast.remove();
      }, 300);
    }, 3000);
  }
  
  /**
   * デバウンス関数
   */
  function debounce(func, wait) {
    let timeout;
    return function() {
      const context = this;
      const args = arguments;
      clearTimeout(timeout);
      timeout = setTimeout(() => {
        func.apply(context, args);
      }, wait);
    };
  }
});

/**
 * HTMXのカスタムイベントと拡張
 * モバイル向けの拡張機能
 */
if (typeof htmx !== 'undefined') {
  // プルトゥリフレッシュのカスタムイベント
  htmx.defineExtension('pulldown-refresh', {
    onEvent: function(name, evt) {
      if (name === 'pulldown') {
        // カスタムHTMXトリガーを発火
        htmx.trigger(evt.target, 'pulldown-triggered');
        
        // GETリクエストを送信
        const path = evt.target.getAttribute('hx-get');
        if (path) {
          htmx.ajax('GET', path, {
            target: evt.target,
            swap: evt.target.getAttribute('hx-swap') || 'innerHTML'
          });
        }
        
        return true;
      }
    }
  });
  
  // オフラインキュー対応
  htmx.defineExtension('offline-queue', {
    onEvent: function(name, evt) {
      // オフライン時にフォーム送信を保存
      if (name === 'htmx:beforeRequest' && evt.detail.element.hasAttribute('data-hx-offline-queue')) {
        if (!navigator.onLine) {
          evt.preventDefault();
          
          // オフラインキューにリクエストを保存
          const offlineQueue = JSON.parse(localStorage.getItem('htmx-offline-queue') || '[]');
          
          // リクエスト情報を保存
          offlineQueue.push({
            url: evt.detail.path,
            method: evt.detail.verb,
            body: new URLSearchParams(new FormData(evt.detail.element)).toString(),
            target: evt.detail.target.id,
            swap: evt.detail.swap,
            triggerTime: new Date().getTime()
          });
          
          // ローカルストレージに保存
          localStorage.setItem('htmx-offline-queue', JSON.stringify(offlineQueue));
          
          // ユーザーにフィードバック
          if (typeof showToast === 'function') {
            showToast('オフラインで保存しました。オンラインになったら同期します', 'info');
          }
          
          return false;
        }
      }
      
      // オンラインに戻ったときにキューを処理
      if (name === 'online') {
        const offlineQueue = JSON.parse(localStorage.getItem('htmx-offline-queue') || '[]');
        
        if (offlineQueue.length > 0) {
          // キューの処理
          offlineQueue.forEach((request, idx) => {
            setTimeout(() => {
              // リクエストを再送信
              const targetElem = document.getElementById(request.target);
              if (targetElem) {
                htmx.ajax(request.method, request.url, {
                  target: targetElem,
                  swap: request.swap,
                  values: request.body
                });
              }
              
              // 処理済みのリクエストを削除
              const updatedQueue = JSON.parse(localStorage.getItem('htmx-offline-queue') || '[]');
              updatedQueue.splice(0, 1);
              localStorage.setItem('htmx-offline-queue', JSON.stringify(updatedQueue));
            }, idx * 1000); // リクエストを1秒ごとに処理
          });
          
          // ユーザーにフィードバック
          if (typeof showToast === 'function') {
            showToast(`${offlineQueue.length}件のオフラインデータを同期しています`, 'success');
          }
        }
      }
    }
  });
  
  // インラインバリデーション
  htmx.defineExtension('inline-validation', {
    onEvent: function(name, evt) {
      if (name === 'htmx:afterRequest' && evt.detail.target.classList.contains('validate-inline')) {
        // バリデーション結果を表示
        const input = evt.detail.target;
        const feedbackEl = document.getElementById(input.getAttribute('hx-target').substring(1));
        
        if (feedbackEl && evt.detail.successful) {
          const response = evt.detail.xhr.response;
          
          try {
            const result = JSON.parse(response);
            
            if (result.valid) {
              input.classList.remove('is-invalid');
              input.classList.add('is-valid');
              feedbackEl.innerHTML = `<div class="valid-feedback d-block">${result.message}</div>`;
            } else {
              input.classList.remove('is-valid');
              input.classList.add('is-invalid');
              feedbackEl.innerHTML = `<div class="invalid-feedback d-block">${result.message}</div>`;
            }
          } catch (e) {
            // JSONでない場合はそのまま表示
            feedbackEl.innerHTML = response;
          }
        }
      }
    }
  });
  
  // ページ遷移後のスワイプ再初期化
  htmx.onLoad(function(content) {
    // ページの主要コンテンツがロードされた後に呼び出される
    if (content.id === 'diary-container') {
      console.log('HTMX onLoad: Reinitializing swipe for diary container');
      
      // 少し遅延させて実行（DOMが完全に更新された後）
      setTimeout(() => {
        // 日記カードにスワイプハンドラーを適用
        const diaryCards = content.querySelectorAll('.diary-card');
        diaryCards.forEach(card => {
          // data-swipe-initialized属性をリセット
          card.removeAttribute('data-swipe-initialized');
          
          // 既存のイベントリスナーを削除
          card.removeEventListener('touchstart', null);
          card.removeEventListener('touchmove', null);
          card.removeEventListener('touchend', null);
        });
        
        // イベントを発火して再初期化
        const event = new CustomEvent('reinitialize-swipe');
        document.dispatchEvent(event);
      }, 100);
    }
  });
}

// スワイプ再初期化のためのイベントリスナー
document.addEventListener('reinitialize-swipe', function() {
  console.log('Reinitializing swipe handlers on demand');
  
  // 日記カードにスワイプイベントを設定
  document.querySelectorAll('.diary-card').forEach(card => {
    // スワイプハンドラを再設定
    card.removeAttribute('data-swipe-initialized');
    
    // 既存のイベントを削除してから再設定
    const newCard = card.cloneNode(true);
    card.parentNode.replaceChild(newCard, card);
    
    // 新しいハンドラーを設定
    if (typeof setupSwipeHandlers === 'function') {
      setupSwipeHandlers(newCard);
    }
  });
});