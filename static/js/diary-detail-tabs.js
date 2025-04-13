/**
 * diary-detail-tabs.js - 日記詳細ページのタブスワイプ機能
 * 継続記録とタイムラインタブ間のスワイプ操作を実装
 */
document.addEventListener('DOMContentLoaded', function() {
    // タブ要素を取得
    const tabContent = document.getElementById('diaryDetailTabContent');
    const notesTab = document.getElementById('notes-tab');
    const timelineTab = document.getElementById('timeline-tab');
    
    // タブ要素が存在しない場合は何もしない
    if (!tabContent || !notesTab || !timelineTab) return;
    
    // Bootstrap Tab インスタンスを取得
    const notesTabInstance = new bootstrap.Tab(notesTab);
    const timelineTabInstance = new bootstrap.Tab(timelineTab);
    
    // スワイプ関連の変数
    let touchStartX = 0;
    let touchEndX = 0;
    let touchMoveX = 0;
    let startTime = 0;
    let moveDistance = 0;
    let currentTabIndex = 0;
    let isDragging = false;
    let isAnimating = false;
    
    // 定数
    const TRANSITION_DURATION = 300; // ミリ秒
    const DRAG_THRESHOLD = 80; // スワイプと判定する最小距離（px）
    const VELOCITY_THRESHOLD = 0.5; // スワイプと判定する最小速度（px/ms）
    
    // 現在のタブインデックスを設定
    function initTabIndex() {
      if (notesTab.classList.contains('active')) {
        currentTabIndex = 0;
      } else if (timelineTab.classList.contains('active')) {
        currentTabIndex = 1;
      } else {
        currentTabIndex = 0;
      }
    }
    
    // スワイプ状態のリセット
    function resetSwipeState() {
      touchStartX = 0;
      touchEndX = 0;
      touchMoveX = 0;
      moveDistance = 0;
      isDragging = false;
      isAnimating = false;
      tabContent.classList.remove('swiping');
    }
    
    // スワイプ方向のインジケーターを更新
    function updateDirectionIndicators() {
      // スワイプの方向によって、視覚的なフィードバックを提供する
      if (moveDistance > 0) {
        // 右スワイプ - 前のタブが存在する場合はハイライト
        if (currentTabIndex > 0) {
          timelineTab.classList.remove('tab-highlight');
          notesTab.classList.add('tab-highlight');
        }
      } else if (moveDistance < 0) {
        // 左スワイプ - 次のタブが存在する場合はハイライト
        if (currentTabIndex < 1) {
          notesTab.classList.remove('tab-highlight');
          timelineTab.classList.add('tab-highlight');
        }
      } else {
        // ハイライトをリセット
        notesTab.classList.remove('tab-highlight');
        timelineTab.classList.remove('tab-highlight');
      }
    }
    
    // タッチ開始イベント
    function handleTouchStart(e) {
      if (isAnimating) return;
      
      touchStartX = e.touches[0].clientX;
      startTime = Date.now();
      isDragging = true;
      moveDistance = 0;
      
      // トランジションを無効化してスワイプ中であることを示す
      tabContent.classList.add('swiping');
      
      // タップ振動フィードバック（対応ブラウザのみ）
      if (navigator.vibrate) {
        navigator.vibrate(5);
      }
    }
    
    // タッチ移動イベント
    function handleTouchMove(e) {
      if (!isDragging || isAnimating) return;
      
      touchMoveX = e.touches[0].clientX;
      moveDistance = touchMoveX - touchStartX;
      
      // スワイプ方向の視覚的フィードバックを更新
      updateDirectionIndicators();
    }
    
    // タッチ終了イベント
    function handleTouchEnd(e) {
      if (!isDragging || isAnimating) return;
      
      isDragging = false;
      touchEndX = e.changedTouches[0].clientX;
      
      // スワイプの終了時間と速度を計算
      const endTime = Date.now();
      const duration = endTime - startTime;
      const velocity = Math.abs(moveDistance) / duration; // 速度（px/ms）
      
      // トランジションを有効化
      tabContent.classList.remove('swiping');
      
      // スワイプ距離
      const swipeDistance = touchEndX - touchStartX;
      
      // 素早いスワイプまたは十分な距離があればタブ切り替え
      if (Math.abs(swipeDistance) > DRAG_THRESHOLD || velocity > VELOCITY_THRESHOLD) {
        // 左スワイプ（次のタブへ）
        if (swipeDistance < 0 && currentTabIndex === 0) {
          switchToTab(1);
        } 
        // 右スワイプ（前のタブへ）
        else if (swipeDistance > 0 && currentTabIndex === 1) {
          switchToTab(0);
        } else {
          resetSwipeState();
        }
      } else {
        resetSwipeState();
      }
      
      // 完了時のフィードバック振動
      if (navigator.vibrate) {
        navigator.vibrate(10);
      }
    }
    
    // タッチキャンセルイベント
    function handleTouchCancel() {
      if (isDragging) {
        isDragging = false;
        tabContent.classList.remove('swiping');
        resetSwipeState();
      }
    }
    
    // 指定したインデックスのタブに切り替え
    function switchToTab(index) {
      if (index < 0 || index > 1) return;
      
      // アニメーション中フラグをセット
      isAnimating = true;
      
      // タブの切り替え
      setTimeout(() => {
        if (index === 0) {
          notesTabInstance.show();
        } else {
          timelineTabInstance.show();
        }
        
        // 現在のタブインデックスを更新
        currentTabIndex = index;
        
        // アニメーション完了後に状態をリセット
        setTimeout(() => {
          isAnimating = false;
          resetSwipeState();
        }, TRANSITION_DURATION);
      }, 50);
    }
    
    // イベントリスナーの設定
    function setupEventListeners() {
      // タブコンテンツにタッチイベントリスナーを追加
      tabContent.addEventListener('touchstart', handleTouchStart, { passive: true });
      tabContent.addEventListener('touchmove', handleTouchMove, { passive: true });
      tabContent.addEventListener('touchend', handleTouchEnd, { passive: true });
      tabContent.addEventListener('touchcancel', handleTouchCancel, { passive: true });
      
      // タブ切り替えイベントリスナー
      notesTab.addEventListener('shown.bs.tab', function() {
        currentTabIndex = 0;
        setTimeout(resetSwipeState, 50);
      });
      
      timelineTab.addEventListener('shown.bs.tab', function() {
        currentTabIndex = 1;
        setTimeout(resetSwipeState, 50);
      });
    }
    
    // スタイルの初期化
    function initStyles() {
      // スワイプ用のスタイルを追加
      const styleEl = document.createElement('style');
      styleEl.textContent = `
        #diaryDetailTabContent {
          position: relative;
          touch-action: pan-y;
          overflow: hidden;
        }
        
        #diaryDetailTabContent.swiping {
          transition: none;
        }
        
        .tab-pane {
          transition: opacity ${TRANSITION_DURATION}ms ease;
        }
        
        .tab-highlight {
          animation: tab-glow 0.3s ease-out;
        }
        
        @keyframes tab-glow {
          0% { background-color: transparent; }
          50% { background-color: rgba(var(--primary-color-rgb, 90, 126, 197), 0.1); }
          100% { background-color: transparent; }
        }
        
        .swipe-hint {
          opacity: 1;
          transition: opacity 0.5s ease;
          font-size: 0.8rem;
          color: #6c757d;
          margin-bottom: 0.5rem;
        }
      `;
      document.head.appendChild(styleEl);
    }
    
    // スワイプヒントの表示/非表示を管理
    function handleSwipeHint() {
      const swipeHint = document.querySelector('.swipe-hint');
      if (!swipeHint) return;
      
      // モバイルデバイスかどうかをチェック
      const isMobile = window.innerWidth < 768 || navigator.maxTouchPoints > 1;
      
      if (isMobile) {
        // モバイルデバイスではスワイプヒントを表示
        swipeHint.style.display = 'block';
        swipeHint.style.opacity = '1';
        
        // 5秒後に非表示
        setTimeout(() => {
          swipeHint.style.opacity = '0';
          setTimeout(() => {
            swipeHint.style.display = 'none';
          }, 500);
        }, 5000);
      } else {
        // デスクトップでは非表示
        swipeHint.style.display = 'none';
      }
    }
    
    // 初期化関数
    function init() {
      initStyles();
      initTabIndex();
      setupEventListeners();
      handleSwipeHint();
      resetSwipeState();
    }
    
    // 初期化を実行
    init();
  });