/**
 * diary-detail-tabs.js - 日記詳細ページのタブスワイプ機能
 * 全タブ間（基本情報、継続記録、タイムライン）のスワイプ操作を実装
 */
document.addEventListener('DOMContentLoaded', function() {
    // console.log('=== 日記詳細タブスワイプ機能 初期化開始 ===');
    
    // タブ要素を取得
    const tabContent = document.getElementById('diaryDetailTabContent');
    const tabsContainer = document.getElementById('diaryDetailTabs');
    
    // 必須要素が存在しない場合は何もしない
    if (!tabContent || !tabsContainer) {
        // console.log('必須要素が見つかりません');
        return;
    }
    
    // 全タブを順序通りに取得
    const getAllTabs = () => {
        const tabs = [];
        const tabButtons = tabsContainer.querySelectorAll('.improved-tab-link');
        
        tabButtons.forEach(button => {
            const targetId = button.getAttribute('data-bs-target');
            const targetPane = document.querySelector(targetId);
            
            if (targetPane) {
                tabs.push({
                    button: button,
                    pane: targetPane,
                    id: targetId,
                    name: button.querySelector('.tab-label')?.textContent || 'Unknown'
                });
            }
        });
        
        // console.log('検出されたタブ:', tabs.map((tab, index) => `${index}: ${tab.name} (${tab.id})`));
        return tabs;
    };
    
    const allTabs = getAllTabs();
    
    if (allTabs.length === 0) {
        // console.log('有効なタブが見つかりません');
        return;
    }
    
    // 現在のアクティブタブのインデックスを取得
    const getCurrentTabIndex = () => {
        for (let i = 0; i < allTabs.length; i++) {
            if (allTabs[i].button.classList.contains('active')) {
                // console.log('現在のアクティブタブ:', i, allTabs[i].name);
                return i;
            }
        }
        // console.log('アクティブタブが見つかりません、0を返す');
        return 0;
    };
    
    // 指定されたインデックスのタブをアクティブ化
    const activateTab = (index) => {
        if (index >= 0 && index < allTabs.length) {
            // console.log(`タブ${index}をアクティブ化:`, allTabs[index].name);
            
            const tabInstance = new bootstrap.Tab(allTabs[index].button);
            tabInstance.show();
            
            return true;
        }
        // console.log(`無効なタブインデックス: ${index} (範囲: 0-${allTabs.length - 1})`);
        return false;
    };
    
    // スワイプ関連の変数
    let touchStartX = 0;
    let touchStartY = 0;
    let touchEndX = 0;
    let touchMoveX = 0;
    let startTime = 0;
    let moveDistance = 0;
    let isDragging = false;
    let isAnimating = false;
    let isScrolling = false;
    
    // 定数
    const TRANSITION_DURATION = 300; // ミリ秒
    const DRAG_THRESHOLD = 80; // スワイプと判定する最小距離（px）
    const VELOCITY_THRESHOLD = 0.5; // スワイプと判定する最小速度（px/ms）
    
    // スワイプ状態のリセット
    function resetSwipeState() {
        touchStartX = 0;
        touchStartY = 0;
        touchEndX = 0;
        touchMoveX = 0;
        moveDistance = 0;
        isDragging = false;
        isAnimating = false;
        isScrolling = false;
        tabContent.classList.remove('swiping');
        
        // タブハイライトをリセット
        allTabs.forEach(tab => {
            tab.button.classList.remove('tab-highlight');
        });
    }
    
    // スワイプ方向のインジケーターを更新
    function updateDirectionIndicators() {
        const currentIndex = getCurrentTabIndex();
        
        // すべてのハイライトをリセット
        allTabs.forEach(tab => {
            tab.button.classList.remove('tab-highlight');
        });
        
        if (moveDistance > 0) {
            // 右スワイプ - 前のタブが存在する場合はハイライト
            if (currentIndex > 0) {
                allTabs[currentIndex - 1].button.classList.add('tab-highlight');
            }
        } else if (moveDistance < 0) {
            // 左スワイプ - 次のタブが存在する場合はハイライト
            if (currentIndex < allTabs.length - 1) {
                allTabs[currentIndex + 1].button.classList.add('tab-highlight');
            }
        }
    }
    
    // タッチ開始イベント
    function handleTouchStart(e) {
        if (isAnimating) return;
        
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
        startTime = Date.now();
        isDragging = false;
        isScrolling = false;
        moveDistance = 0;
        
        // console.log('タッチ開始:', { x: touchStartX, y: touchStartY });
        
        // タップ振動フィードバック（対応ブラウザのみ）
        if (navigator.vibrate) {
            navigator.vibrate(5);
        }
    }
    
    // タッチ移動イベント
    function handleTouchMove(e) {
        if (isAnimating || !touchStartX || !touchStartY) return;
        
        touchMoveX = e.touches[0].clientX;
        const touchMoveY = e.touches[0].clientY;
        
        const diffX = Math.abs(touchMoveX - touchStartX);
        const diffY = Math.abs(touchMoveY - touchStartY);
        
        // 縦スクロールが主な動きの場合はフリックを無効化
        if (diffY > diffX && diffY > 10) {
            isScrolling = true;
            // console.log('縦スクロール検出 - フリック無効化');
            return;
        }
        
        // 横移動が主な動きの場合はドラッグを開始
        if (diffX > 10 && !isScrolling) {
            isDragging = true;
            moveDistance = touchMoveX - touchStartX;
            
            // スワイプ中であることを示す
            tabContent.classList.add('swiping');
            
            // スワイプ方向の視覚的フィードバックを更新
            updateDirectionIndicators();
        }
    }
    
    // タッチ終了イベント
    function handleTouchEnd(e) {
        if (isAnimating || isScrolling || !touchStartX || !touchStartY) {
            resetSwipeState();
            return;
        }
        
        touchEndX = e.changedTouches[0].clientX;
        
        // スワイプの終了時間と速度を計算
        const endTime = Date.now();
        const duration = endTime - startTime;
        const swipeDistance = touchEndX - touchStartX;
        const velocity = Math.abs(swipeDistance) / duration; // 速度（px/ms）
        
        // トランジションを有効化
        tabContent.classList.remove('swiping');
        
        // 素早いスワイプまたは十分な距離があればタブ切り替え
        if ((Math.abs(swipeDistance) > DRAG_THRESHOLD || velocity > VELOCITY_THRESHOLD) && isDragging) {
            const currentIndex = getCurrentTabIndex();
            
            if (swipeDistance > 0) {
                // 右スワイプ（前のタブへ）
                const prevIndex = currentIndex - 1;
                // console.log(`右フリック: タブ${currentIndex} → タブ${prevIndex}`);
                
                if (prevIndex >= 0) {
                    switchToTab(prevIndex);
                } else {
                    // console.log('これ以上左に移動できません');
                    resetSwipeState();
                }
            } else {
                // 左スワイプ（次のタブへ）
                const nextIndex = currentIndex + 1;
                // console.log(`左フリック: タブ${currentIndex} → タブ${nextIndex}`);
                
                if (nextIndex < allTabs.length) {
                    switchToTab(nextIndex);
                } else {
                    // console.log('これ以上右に移動できません');
                    resetSwipeState();
                }
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
        // console.log('タッチキャンセル');
        resetSwipeState();
    }
    
    // 指定したインデックスのタブに切り替え
    function switchToTab(index) {
        if (index < 0 || index >= allTabs.length) {
            // console.log('無効なタブインデックス:', index);
            return;
        }
        
        // アニメーション中フラグをセット
        isAnimating = true;
        // console.log(`タブ切り替え開始: ${index} (${allTabs[index].name})`);
        
        // タブボタンのハイライト
        allTabs[index].button.classList.add('tab-highlight');
        
        // タブ切り替えアニメーション
        setTimeout(() => {
            activateTab(index);
            
            // ハイライトを解除
            setTimeout(() => {
                allTabs.forEach(tab => {
                    tab.button.classList.remove('tab-highlight');
                });
            }, 150);
            
            // アニメーション完了後に状態をリセット
            setTimeout(() => {
                isAnimating = false;
                resetSwipeState();
                // console.log('タブ切り替え完了');
            }, TRANSITION_DURATION);
        }, 50);
        
        // ハプティックフィードバック
        if (navigator.vibrate) {
            navigator.vibrate(50);
        }
    }
    
    // イベントリスナーの設定
    function setupEventListeners() {
        // タブコンテンツにタッチイベントリスナーを追加
        tabContent.addEventListener('touchstart', handleTouchStart, { passive: true });
        tabContent.addEventListener('touchmove', handleTouchMove, { passive: true });
        tabContent.addEventListener('touchend', handleTouchEnd, { passive: true });
        tabContent.addEventListener('touchcancel', handleTouchCancel, { passive: true });
        
        // 各タブの切り替えイベントリスナー
        allTabs.forEach((tab, index) => {
            tab.button.addEventListener('shown.bs.tab', function() {
                // console.log(`タブ切り替えイベント: ${index} (${tab.name})`);
                setTimeout(resetSwipeState, 50);
            });
        });
    }
    
    // スタイルの初期化
    function initStyles() {
        // 既存のスタイルがあるかチェック
        if (document.getElementById('diary-detail-tabs-style')) return;
        
        const styleEl = document.createElement('style');
        styleEl.id = 'diary-detail-tabs-style';
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
                50% { background-color: rgba(var(--primary-color, 90, 126, 197), 0.1); }
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
    
    // 初期化関数
    function init() {
        initStyles();
        setupEventListeners();
        resetSwipeState();
    }
    
    // 初期化を実行
    init();
});

// スワイプヒント関連の機能（既存の関数を保持）
function hideSwipeHint() {
    const hint = document.getElementById('swipeHint');
    if (hint) {
        hint.classList.add('fade-out');
        setTimeout(() => {
            hint.style.display = 'none';
        }, 500);
        
        // ローカルストレージに保存（今後表示しない）
        localStorage.setItem('swipeHintDismissed', 'true');
    }
}

// スワイプヒントの表示制御
document.addEventListener('DOMContentLoaded', function() {
    const swipeHint = document.getElementById('swipeHint');
    const isMobile = window.innerWidth < 768;
    const isDismissed = localStorage.getItem('swipeHintDismissed');
    
    if (swipeHint && isMobile && !isDismissed) {
        setTimeout(() => {
            swipeHint.classList.add('show');
        }, 1000);
        
        // 8秒後に自動で非表示
        setTimeout(() => {
            hideSwipeHint();
        }, 8000);
    }
});