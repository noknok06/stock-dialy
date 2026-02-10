/**
 * mobile-gestures.js - ホーム画面の日記カードタブをスワイプで切り替える
 * .diary-tab-content 領域で左右スワイプを検出し、タブを切り替える
 */

(function() {
  'use strict';

  // スワイプ設定
  const SWIPE_THRESHOLD = 50;       // スワイプと判定する最小水平距離 (px)
  const VERTICAL_LIMIT = 60;        // 縦移動がこれを超えたらスクロールと判定 (px)
  const DRAG_RESISTANCE = 3;        // ドラッグ中の移動量を割る値（抵抗感）
  const ANIMATION_DURATION = 250;   // タブ切替アニメーション時間 (ms)

  /**
   * 記事内のタブボタン一覧を取得
   */
  function getTabButtons(article) {
    return Array.from(article.querySelectorAll('.diary-tabs .tab-btn'));
  }

  /**
   * 現在アクティブなタブのインデックスを返す
   */
  function getActiveIndex(tabs) {
    return tabs.findIndex(function(btn) { return btn.classList.contains('active'); });
  }

  /**
   * 指定インデックスのタブをクリックして切り替える
   * diary-tabs.js の click ハンドラが処理するため .click() で委譲
   */
  function switchToTab(tabs, index) {
    if (index >= 0 && index < tabs.length) {
      tabs[index].click();
    }
  }

  /**
   * 各 diary-article 内の .diary-tab-content にスワイプハンドラを設定
   */
  function setupSwipeHandlers() {
    var articles = document.querySelectorAll('.diary-article');

    articles.forEach(function(article) {
      var tabContent = article.querySelector('.diary-tab-content');
      if (!tabContent) return;

      // 既にセットアップ済みならスキップ
      if (tabContent._swipeSetup) return;
      tabContent._swipeSetup = true;

      var startX = 0;
      var startY = 0;
      var moveX = 0;
      var isTracking = false;
      var isScrolling = null; // null=未判定, true=縦スクロール, false=横スワイプ

      tabContent.addEventListener('touchstart', function(e) {
        var touch = e.touches[0];
        startX = touch.clientX;
        startY = touch.clientY;
        moveX = 0;
        isTracking = true;
        isScrolling = null;
        tabContent.style.transition = 'none';
      }, { passive: true });

      tabContent.addEventListener('touchmove', function(e) {
        if (!isTracking) return;

        var touch = e.touches[0];
        var diffX = touch.clientX - startX;
        var diffY = touch.clientY - startY;

        // 初回移動で方向を判定
        if (isScrolling === null) {
          if (Math.abs(diffY) > 10 || Math.abs(diffX) > 10) {
            isScrolling = Math.abs(diffY) > Math.abs(diffX);
          }
        }

        // 縦スクロールと判定されたら何もしない
        if (isScrolling) return;

        // 横スワイプと判定 — 縦移動が大きすぎたらキャンセル
        if (Math.abs(diffY) > VERTICAL_LIMIT) {
          isTracking = false;
          tabContent.style.transform = '';
          tabContent.style.transition = '';
          return;
        }

        // スクロールを抑制して水平のドラッグフィードバックを表示
        e.preventDefault();
        moveX = diffX;
        tabContent.style.transform = 'translateX(' + (diffX / DRAG_RESISTANCE) + 'px)';
      }, { passive: false });

      tabContent.addEventListener('touchend', function() {
        if (!isTracking) return;
        isTracking = false;

        // アニメーション付きで元の位置に戻す
        tabContent.style.transition = 'transform ' + ANIMATION_DURATION + 'ms ease-out';
        tabContent.style.transform = '';

        // スワイプ閾値チェック
        if (Math.abs(moveX) < SWIPE_THRESHOLD) return;

        var tabs = getTabButtons(article);
        if (tabs.length <= 1) return;

        var current = getActiveIndex(tabs);
        var next = current;

        if (moveX < -SWIPE_THRESHOLD && current < tabs.length - 1) {
          // 左スワイプ → 次のタブ
          next = current + 1;
        } else if (moveX > SWIPE_THRESHOLD && current > 0) {
          // 右スワイプ → 前のタブ
          next = current - 1;
        }

        if (next !== current) {
          // 触覚フィードバック
          if (navigator.vibrate) {
            navigator.vibrate(15);
          }

          // タブ切替ハイライト
          tabs[next].classList.add('tab-highlight');
          switchToTab(tabs, next);

          setTimeout(function() {
            tabs[next].classList.remove('tab-highlight');
          }, 300);
        }
      }, { passive: true });

      tabContent.addEventListener('touchcancel', function() {
        isTracking = false;
        tabContent.style.transition = 'transform ' + ANIMATION_DURATION + 'ms ease-out';
        tabContent.style.transform = '';
      }, { passive: true });
    });
  }

  // --- 初期化 ---

  // DOMContentLoaded で初期セットアップ
  document.addEventListener('DOMContentLoaded', function() {
    setupSwipeHandlers();
  });

  // HTMX でコンテンツが読み込まれた後に再セットアップ
  document.body.addEventListener('htmx:afterSwap', function(evt) {
    if (evt.detail.target.id === 'diary-container') {
      setTimeout(setupSwipeHandlers, 100);
    }
  });

  // HTMX の afterSettle でも再セットアップ（無限スクロール対応）
  document.body.addEventListener('htmx:afterSettle', function(evt) {
    if (evt.detail.target.id === 'diary-container') {
      setTimeout(setupSwipeHandlers, 50);
    }
  });
})();
