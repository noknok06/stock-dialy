/**
 * 修正版クイック作成モーダルのタブスワイプ機能
 * スワイプ後に操作できなくなる問題を修正
 */
document.addEventListener('DOMContentLoaded', function() {
  const tabContent = document.getElementById('quickDiaryTabContent');
  const tabsNav = document.getElementById('quickDiaryTabs');
  const tabButtons = document.querySelectorAll('#quickDiaryTabs .nav-link');
  
  // タブコンテンツがない場合は処理しない
  if (!tabContent || !tabsNav || tabButtons.length === 0) return;
  
  // スワイプ関連の変数
  let touchStartX = 0;
  let touchEndX = 0;
  let touchMoveX = 0;
  let startTime = 0;
  let moveDistance = 0;
  let currentTabIndex = 0;
  let isDragging = false;
  let isAnimating = false; // アニメーション中かどうかのフラグ
  
  // トランジション設定
  const TRANSITION_DURATION = 300; // ミリ秒
  const DRAG_THRESHOLD = 80; // スワイプと判定する最小距離（px）
  const VELOCITY_THRESHOLD = 0.5; // スワイプと判定する最小速度（px/ms）
  
  // タブインデックスの初期化
  function initTabIndex() {
    tabButtons.forEach((button, index) => {
      if (button.classList.contains('active')) {
        currentTabIndex = index;
      }
    });
  }
  
  // スタイルの初期化（CSSの追加）
  function initStyles() {
    // すでに追加済みかチェック
    if (document.getElementById('quick-diary-tabs-style')) return;
    
    // スタイルタグを作成
    const styleEl = document.createElement('style');
    styleEl.id = 'quick-diary-tabs-style';
    styleEl.textContent = `
      #quickDiaryTabContent {
        position: relative;
        touch-action: pan-y;
        overflow: hidden;
      }
      
      #quickDiaryTabContent.swiping {
        transition: none;
      }
      
      .tab-pane {
        transition: opacity ${TRANSITION_DURATION}ms ease;
      }
      
      .swipe-hint {
        opacity: 1;
        transition: opacity 0.5s ease;
      }
      
      .swipe-direction-indicator {
        position: absolute;
        top: 50%;
        width: 24px;
        height: 24px;
        margin-top: -12px;
        border-width: 0 3px 3px 0;
        border-style: solid;
        border-color: var(--primary-color);
        opacity: 0;
        transition: opacity 0.3s ease;
        z-index: 5;
        pointer-events: none;
      }
      
      .swipe-direction-indicator.left {
        left: 15px;
        transform: rotate(135deg);
      }
      
      .swipe-direction-indicator.right {
        right: 15px;
        transform: rotate(-45deg);
      }
      
      #quickDiaryTabContent.swiping .swipe-direction-indicator {
        opacity: 0.7;
      }
      
      .tab-highlight {
        animation: tab-glow 0.3s ease-out;
      }
      
      @keyframes tab-glow {
        0% {
          background-color: transparent;
        }
        50% {
          background-color: rgba(var(--primary-color-rgb, 90, 126, 197), 0.1);
        }
        100% {
          background-color: transparent;
        }
      }
    `;
    
    // DOMに追加
    document.head.appendChild(styleEl);
    
    // 方向インジケーターを追加
    const leftIndicator = document.createElement('div');
    leftIndicator.className = 'swipe-direction-indicator left';
    tabContent.appendChild(leftIndicator);
    
    const rightIndicator = document.createElement('div');
    rightIndicator.className = 'swipe-direction-indicator right';
    tabContent.appendChild(rightIndicator);
  }
  
  // モーダルが表示されたときの処理
  const quickDiaryModal = document.getElementById('quickDiaryModal');
  
  // モーダルが存在しない場合は処理を終了
  if (!quickDiaryModal) return;
  
  // モーダルが表示されたときに特定のボタンのイベントハンドラーを設定
  quickDiaryModal.addEventListener('shown.bs.modal', function() {
    // 該当するボタンを取得
    const toBasicTabBtn = document.getElementById('to-basic-tab');
    const toDetailsTabBtn = document.getElementById('to-details-tab');
    const toTagsTabBtn = document.getElementById('to-tags-tab');
    const backToBasicTabBtn = document.getElementById('back-to-basic-tab');
    const backToDetailsTabBtn = document.getElementById('back-to-details-tab');
    
    // Bootstrapのタブ要素を取得
    const tabLinks = document.querySelectorAll('#quickDiaryTabs .nav-link');
    const tabLinksArray = Array.from(tabLinks);
    
    // 直接対応するタブのインデックスを設定
    const tabMapping = {
      'to-basic-tab': 0,
      'to-details-tab': 1,
      'to-tags-tab': 2,
      'back-to-basic-tab': 0,
      'back-to-details-tab': 1
    };
    
    // ボタンごとにIDベースのイベントハンドラを設定
    [toBasicTabBtn, toDetailsTabBtn, toTagsTabBtn, backToBasicTabBtn, backToDetailsTabBtn].forEach(button => {
      if (button) {
        // 古いイベントリスナーをクリア
        const newButton = button.cloneNode(true);
        if (button.parentNode) {
          button.parentNode.replaceChild(newButton, button);
        }
        
        // 新しいイベントリスナーを追加
        newButton.addEventListener('click', function(e) {
          e.preventDefault();
          e.stopPropagation();
          
          const buttonId = this.id;
          const targetTabIndex = tabMapping[buttonId];
          
          if (targetTabIndex !== undefined && tabLinksArray[targetTabIndex]) {
            // Bootstrap 5のタブAPIを使用して切り替え
            const tab = new bootstrap.Tab(tabLinksArray[targetTabIndex]);
            tab.show();
            
            console.log(`IDベースのボタン ${buttonId} がクリックされ、タブインデックス ${targetTabIndex} に移動しました`);
            
            // 振動フィードバック
            if (navigator.vibrate) {
              navigator.vibrate(5);
            }
          } else {
            console.warn(`ボタン ${buttonId} に対応するタブが見つかりません`);
          }
        });
        
        console.log(`ボタン ${button.id} のイベントハンドラーを設定しました`);
      }
    });
    
    // 通常の「次へ」「戻る」ボタンも処理
    const genericNextButtons = document.querySelectorAll('.quick-diary-next-btn');
    const genericPrevButtons = document.querySelectorAll('.quick-diary-prev-btn');
    
    genericNextButtons.forEach(button => {
      // すでに特定IDを持つボタンの場合はスキップ
      if (button.id && tabMapping[button.id] !== undefined) return;
      
      // 汎用「次へ」ボタンの処理
      const newButton = button.cloneNode(true);
      if (button.parentNode) {
        button.parentNode.replaceChild(newButton, button);
      }
      
      newButton.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        // 現在のアクティブタブを取得
        const activeTab = document.querySelector('#quickDiaryTabs .nav-link.active');
        if (!activeTab) return;
        
        const currentIndex = tabLinksArray.indexOf(activeTab);
        if (currentIndex < tabLinksArray.length - 1) {
          // 次のタブに移動
          const tab = new bootstrap.Tab(tabLinksArray[currentIndex + 1]);
          tab.show();
          
          console.log(`汎用「次へ」ボタンがクリックされ、${currentIndex} -> ${currentIndex + 1} に移動しました`);
          
          // 振動フィードバック
          if (navigator.vibrate) {
            navigator.vibrate(5);
          }
        }
      });
    });
    
    genericPrevButtons.forEach(button => {
      // すでに特定IDを持つボタンの場合はスキップ
      if (button.id && tabMapping[button.id] !== undefined) return;
      
      // 汎用「戻る」ボタンの処理
      const newButton = button.cloneNode(true);
      if (button.parentNode) {
        button.parentNode.replaceChild(newButton, button);
      }
      
      newButton.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        // 現在のアクティブタブを取得
        const activeTab = document.querySelector('#quickDiaryTabs .nav-link.active');
        if (!activeTab) return;
        
        const currentIndex = tabLinksArray.indexOf(activeTab);
        if (currentIndex > 0) {
          // 前のタブに移動
          const tab = new bootstrap.Tab(tabLinksArray[currentIndex - 1]);
          tab.show();
          
          console.log(`汎用「戻る」ボタンがクリックされ、${currentIndex} -> ${currentIndex - 1} に移動しました`);
          
          // 振動フィードバック
          if (navigator.vibrate) {
            navigator.vibrate(5);
          }
        }
      });
    });
  });
  
  console.log('特定IDに対応するボタンイベントハンドラーの初期化を待機中...');
  
  // 「次へ」および「戻る」ボタンのイベントハンドラーを初期化
  function initButtonEvents() {
    // ボタン要素の取得
    const nextButtons = document.querySelectorAll('.quick-diary-next-btn');
    const prevButtons = document.querySelectorAll('.quick-diary-prev-btn');
    
    // 「次へ」ボタンのイベントリスナー設定
    nextButtons.forEach(button => {
      // 既存のイベントリスナーを削除
      button.removeEventListener('click', handleNextBtn);
      // 新しいイベントリスナーを追加
      button.addEventListener('click', handleNextBtn);
    });
    
    // 「戻る」ボタンのイベントリスナー設定
    prevButtons.forEach(button => {
      // 既存のイベントリスナーを削除
      button.removeEventListener('click', handlePrevBtn);
      // 新しいイベントリスナーを追加
      button.addEventListener('click', handlePrevBtn);
    });
    
    console.log('ボタンイベントハンドラーを初期化しました（ボタン数: 次へ=' + nextButtons.length + ', 戻る=' + prevButtons.length + '）');
  }
  
  // 「次へ」ボタンのクリックハンドラー
  function handleNextBtn(e) {
    e.preventDefault();
    e.stopPropagation();
    
    console.log('「次へ」ボタンがクリックされました');
    
    // 現在のタブが最後のタブでない場合、次のタブに移動
    if (currentTabIndex < tabButtons.length - 1) {
      const nextTabIndex = currentTabIndex + 1;
      console.log('タブ切り替え: ' + currentTabIndex + ' -> ' + nextTabIndex);
      
      // タブを切り替え
      switchToTab(nextTabIndex);
      
      // 振動フィードバック
      if (navigator.vibrate) {
        navigator.vibrate(5);
      }
    }
  }
  
  // 「戻る」ボタンのクリックハンドラー
  function handlePrevBtn(e) {
    e.preventDefault();
    e.stopPropagation();
    
    console.log('「戻る」ボタンがクリックされました');
    
    // 現在のタブが最初のタブでない場合、前のタブに移動
    if (currentTabIndex > 0) {
      const prevTabIndex = currentTabIndex - 1;
      console.log('タブ切り替え: ' + currentTabIndex + ' -> ' + prevTabIndex);
      
      // タブを切り替え
      switchToTab(prevTabIndex);
      
      // 振動フィードバック
      if (navigator.vibrate) {
        navigator.vibrate(5);
      }
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
    
    // 方向インジケーターのリセット
    const leftIndicator = tabContent.querySelector('.swipe-direction-indicator.left');
    const rightIndicator = tabContent.querySelector('.swipe-direction-indicator.right');
    
    if (leftIndicator) leftIndicator.style.opacity = '0';
    if (rightIndicator) rightIndicator.style.opacity = '0';
    
    // ハイライトのリセット
    tabButtons.forEach(btn => btn.classList.remove('tab-highlight'));
  }
  
  // タッチ開始イベント
  function handleTouchStart(e) {
    // アニメーション中は新しいスワイプを開始しない
    if (isAnimating) return;
    
    touchStartX = e.touches[0].clientX;
    startTime = Date.now();
    isDragging = true;
    moveDistance = 0;
    
    // トランジションを無効化
    tabContent.classList.add('swiping');
    
    // 方向インジケーターを更新
    updateDirectionIndicators();
    
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
    
    // スワイプ方向の視覚的フィードバック
    updateDirectionIndicators();
    
    // とりあえず抵抗感を持たせるために移動量を調整（実際には操作は実行しない）
    const resistance = 0.5; // 抵抗値（小さいほど抵抗が大きい）
    const adjustedMove = moveDistance * resistance;
    
    // 現在のタブが最初または最後なら、さらに抵抗を強める
    if ((currentTabIndex === 0 && moveDistance > 0) || 
        (currentTabIndex === tabButtons.length - 1 && moveDistance < 0)) {
      // 移動可能なタブがない方向にはより強い抵抗をかける
      // ここでは視覚的フィードバックのみ
    }
    
    // アクティブなタブボタンをハイライト
    highlightActiveTab();
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
    
    // スワイプ方向と距離に基づいてタブを切り替えるかどうか判断
    const swipeDistance = touchEndX - touchStartX;
    
    // スワイプの方向と強さをログに出力（デバッグ用）
    console.log('Swipe distance:', swipeDistance, 'velocity:', velocity);
    
    // 素早いスワイプまたは十分な距離があればタブ切り替え
    if (Math.abs(swipeDistance) > DRAG_THRESHOLD || velocity > VELOCITY_THRESHOLD) {
      // 左スワイプ（次のタブへ）
      if (swipeDistance < 0 && currentTabIndex < tabButtons.length - 1) {
        switchToTab(currentTabIndex + 1);
      } 
      // 右スワイプ（前のタブへ）
      else if (swipeDistance > 0 && currentTabIndex > 0) {
        switchToTab(currentTabIndex - 1);
      }
    } else {
      // スワイプが不十分だった場合は状態をすぐにリセット
      resetSwipeState();
    }
    
    // 完了時のフィードバック振動
    if (navigator.vibrate) {
      navigator.vibrate(10);
    }
  }
  
  // スワイプキャンセルイベント
  function handleTouchCancel() {
    if (isDragging) {
      isDragging = false;
      tabContent.classList.remove('swiping');
      resetSwipeState();
    }
  }
  
  // 方向インジケーターを更新
  function updateDirectionIndicators() {
    const leftIndicator = tabContent.querySelector('.swipe-direction-indicator.left');
    const rightIndicator = tabContent.querySelector('.swipe-direction-indicator.right');
    
    if (!leftIndicator || !rightIndicator) return;
    
    // 左右どちらにスワイプしているかでインジケーターの表示を調整
    if (moveDistance > 0) {
      // 右スワイプ（前のタブが存在する場合）
      leftIndicator.style.opacity = currentTabIndex > 0 ? '0.7' : '0.2';
      rightIndicator.style.opacity = '0';
    } else if (moveDistance < 0) {
      // 左スワイプ（次のタブが存在する場合）
      rightIndicator.style.opacity = currentTabIndex < tabButtons.length - 1 ? '0.7' : '0.2';
      leftIndicator.style.opacity = '0';
    } else {
      // スワイプなし
      leftIndicator.style.opacity = '0';
      rightIndicator.style.opacity = '0';
    }
  }
  
  // アクティブなタブをハイライト
  function highlightActiveTab() {
    // ハイライトクラスをリセット
    tabButtons.forEach(btn => btn.classList.remove('tab-highlight'));
    
    // スワイプ方向に基づいて次/前のタブをハイライト
    if (moveDistance < -DRAG_THRESHOLD/2 && currentTabIndex < tabButtons.length - 1) {
      tabButtons[currentTabIndex + 1].classList.add('tab-highlight');
    } else if (moveDistance > DRAG_THRESHOLD/2 && currentTabIndex > 0) {
      tabButtons[currentTabIndex - 1].classList.add('tab-highlight');
    }
  }
  
  // 指定したインデックスのタブに切り替え
  function switchToTab(index) {
    if (index < 0 || index >= tabButtons.length) return;
    
    // アニメーション中フラグをセット
    isAnimating = true;
    console.log('Animation started');
    
    // タブボタンのハイライト
    tabButtons[index].classList.add('tab-highlight');
    
    // タブ切り替えアニメーション
    setTimeout(() => {
      // Bootstrapのタブを切り替え
      const tabInstance = new bootstrap.Tab(tabButtons[index]);
      tabInstance.show();
      
      // ハイライトを解除
      setTimeout(() => {
        tabButtons.forEach(btn => btn.classList.remove('tab-highlight'));
      }, 150);
      
      // 現在のタブインデックスを更新
      currentTabIndex = index;
      
      // アニメーション完了後に状態をリセット
      setTimeout(() => {
        isAnimating = false;
        resetSwipeState();
        console.log('Animation completed, state reset');
      }, TRANSITION_DURATION);
    }, 50);
  }
  
  // イベントリスナーをクリーンアップする関数
  function cleanupEventListeners() {
    if (tabContent) {
      tabContent.removeEventListener('touchstart', handleTouchStart);
      tabContent.removeEventListener('touchmove', handleTouchMove);
      tabContent.removeEventListener('touchend', handleTouchEnd);
      tabContent.removeEventListener('touchcancel', handleTouchCancel);
    }
  }
  
  // イベントリスナーを再設定する関数
  function setupEventListeners() {
    if (tabContent) {
      cleanupEventListeners(); // 重複を防ぐために一度削除
      tabContent.addEventListener('touchstart', handleTouchStart, { passive: true });
      tabContent.addEventListener('touchmove', handleTouchMove, { passive: true });
      tabContent.addEventListener('touchend', handleTouchEnd, { passive: true });
      tabContent.addEventListener('touchcancel', handleTouchCancel, { passive: true });
    }
  }
  
  // タブコンテンツにタッチイベントリスナーを追加
  setupEventListeners();
  
  // タブ切り替えのナビゲーションボタンのイベントリスナー
  const toDetailsTab = document.getElementById('to-details-tab');
  const backToBasicTab = document.getElementById('back-to-basic-tab');
  const toTagsTab = document.getElementById('to-tags-tab');
  const backToDetailsTab = document.getElementById('back-to-details-tab');
  
  if (toDetailsTab) {
    toDetailsTab.addEventListener('click', function() {
      currentTabIndex = 1; // 詳細タブのインデックス
      resetSwipeState();
    });
  }
  
  if (backToBasicTab) {
    backToBasicTab.addEventListener('click', function() {
      currentTabIndex = 0; // 基本タブのインデックス
      resetSwipeState();
    });
  }
  
  if (toTagsTab) {
    toTagsTab.addEventListener('click', function() {
      currentTabIndex = 2; // タグタブのインデックス
      resetSwipeState();
    });
  }
  
  if (backToDetailsTab) {
    backToDetailsTab.addEventListener('click', function() {
      currentTabIndex = 1; // 詳細タブのインデックス
      resetSwipeState();
    });
  }
  
  // モーダル内のタブ切り替えイベントリスナー
  tabButtons.forEach((button, index) => {
    button.addEventListener('shown.bs.tab', function() {
      currentTabIndex = index;
      
      // タブ切り替え後に状態をリセット
      setTimeout(() => {
        resetSwipeState();
      }, 50);
    });
  });
  
  // モーダルが閉じられたときのクリーンアップ
  if (quickDiaryModal) {
    quickDiaryModal.addEventListener('hidden.bs.modal', function() {
      resetSwipeState();
    });
  }
  
  // 初回実行
  initStyles();
  
  console.log('クイック日記作成モーダルのタブナビゲーションを初期化しました');
});