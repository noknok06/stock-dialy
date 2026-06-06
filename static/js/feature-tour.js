// static/js/feature-tour.js
/**
 * driver.js を使った機能ツアーの共通ラッパー
 * 初回アクセス時に自動起動し、完了後は localStorage に記録して再表示しない。
 * 「もう一度見る」ボタンなどから手動再生する場合は force: true を渡す。
 *
 * 使い方:
 *   FeatureTour.start('trading-dashboard-v1', [
 *     { element: '#xxx', popover: { title: '...', description: '...' } },
 *   ]);
 *
 * 依存: driver.js (https://driverjs.com/) を読み込み済みのページで使用する
 */
(function () {
  'use strict';

  function storageKey(tourId) {
    return 'tour-completed:' + tourId;
  }

  function isCompleted(tourId) {
    return !!localStorage.getItem(storageKey(tourId));
  }

  function markCompleted(tourId) {
    localStorage.setItem(storageKey(tourId), '1');
  }

  function start(tourId, steps, options) {
    options = options || {};
    var force = !!options.force;

    if (!force && isCompleted(tourId)) return;
    if (!window.driver || !window.driver.js) return;
    if (!steps || steps.length === 0) return;

    var driverObj = window.driver.js.driver({
      showProgress: true,
      allowClose: true,
      nextBtnText: '次へ',
      prevBtnText: '戻る',
      doneBtnText: '完了',
      progressText: '{{current}} / {{total}}',
      onDestroyed: function () {
        markCompleted(tourId);
      },
      steps: steps,
    });

    driverObj.drive();
  }

  window.FeatureTour = {
    start: start,
    isCompleted: isCompleted,
  };
})();
