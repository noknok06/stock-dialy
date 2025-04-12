/**
 * クイック作成モーダルのタブスワイプ機能
 * quickDiaryModal内のタブをスワイプで切り替えられるようにする
 */
document.addEventListener('DOMContentLoaded', function() {
    const tabContent = document.getElementById('quickDiaryTabContent');
    const tabButtons = document.querySelectorAll('#quickDiaryTabs .nav-link');
    
    // スワイプ関連の変数
    let touchStartX = 0;
    let touchEndX = 0;
    let currentTabIndex = 0;
    
    // タブインデックスの初期化
    function initTabIndex() {
      tabButtons.forEach((button, index) => {
        if (button.classList.contains('active')) {
          currentTabIndex = index;
        }
      });
    }
    
    // モーダルが表示されたときの処理
    const quickDiaryModal = document.getElementById('quickDiaryModal');
    if (quickDiaryModal) {
      quickDiaryModal.addEventListener('shown.bs.modal', function() {
        // タブインデックスの初期化
        initTabIndex();
        
        // スワイプヒントの表示/非表示
        const swipeHint = quickDiaryModal.querySelector('.swipe-hint');
        if (swipeHint) {
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
      });
    }
    
    // タブコンテンツにタッチイベントリスナーを追加
    if (tabContent) {
      // タッチ開始イベント
      tabContent.addEventListener('touchstart', function(e) {
        touchStartX = e.changedTouches[0].screenX;
        
        // スワイプ中のクラスを追加
        tabContent.classList.add('swiping');
      });
      
      // タッチ終了イベント
      tabContent.addEventListener('touchend', function(e) {
        touchEndX = e.changedTouches[0].screenX;
        
        // スワイプの方向を計算
        const swipeDistance = touchEndX - touchStartX;
        
        // スワイプ中のクラスを削除
        tabContent.classList.remove('swiping');
        
        // 100px以上のスワイプでタブ切り替え
        if (Math.abs(swipeDistance) > 100) {
          // 左スワイプ（次のタブへ）
          if (swipeDistance < 0 && currentTabIndex < tabButtons.length - 1) {
            // 次のタブをハイライト表示
            tabButtons[currentTabIndex + 1].classList.add('tab-highlight');
            
            // 少し遅延させてタブを切り替え（視覚効果のため）
            setTimeout(() => {
              tabButtons[currentTabIndex + 1].click();
              tabButtons.forEach(btn => btn.classList.remove('tab-highlight'));
              currentTabIndex++;
            }, 150);
          } 
          // 右スワイプ（前のタブへ）
          else if (swipeDistance > 0 && currentTabIndex > 0) {
            // 前のタブをハイライト表示
            tabButtons[currentTabIndex - 1].classList.add('tab-highlight');
            
            // 少し遅延させてタブを切り替え（視覚効果のため）
            setTimeout(() => {
              tabButtons[currentTabIndex - 1].click();
              tabButtons.forEach(btn => btn.classList.remove('tab-highlight'));
              currentTabIndex--;
            }, 150);
          }
        }
      });
      
      // スワイプキャンセルイベント
      tabContent.addEventListener('touchcancel', function() {
        tabContent.classList.remove('swiping');
      });
    }
    
    // タブ切り替えのナビゲーションボタンのイベントリスナー
    const toDetailsTab = document.getElementById('to-details-tab');
    const backToBasicTab = document.getElementById('back-to-basic-tab');
    const toTagsTab = document.getElementById('to-tags-tab');
    const backToDetailsTab = document.getElementById('back-to-details-tab');
    
    if (toDetailsTab) {
      toDetailsTab.addEventListener('click', function() {
        currentTabIndex = 1; // 詳細タブのインデックス
      });
    }
    
    if (backToBasicTab) {
      backToBasicTab.addEventListener('click', function() {
        currentTabIndex = 0; // 基本タブのインデックス
      });
    }
    
    if (toTagsTab) {
      toTagsTab.addEventListener('click', function() {
        currentTabIndex = 2; // タグタブのインデックス
      });
    }
    
    if (backToDetailsTab) {
      backToDetailsTab.addEventListener('click', function() {
        currentTabIndex = 1; // 詳細タブのインデックス
      });
    }
    
    // モーダル内のタブ切り替えイベントリスナー
    tabButtons.forEach((button, index) => {
      button.addEventListener('shown.bs.tab', function() {
        currentTabIndex = index;
      });
    });
  });