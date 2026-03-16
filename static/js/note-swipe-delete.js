/**
 * note-swipe-delete.js
 * 継続記録カード（.note-card）を左スワイプして削除シェルフを表示する。
 *
 * card-swipe-note.js と同パターン（CSS Grid による重なりを利用）:
 *   .note-card          → display:grid のアウター（タッチイベント受付）
 *   .note-slide-content → grid-row:1/col:1, z-index:1（スライドするコンテンツ）
 *   .note-delete-shelf  → grid-row:1/col:1, justify-self:end（右端に隠れているシェルフ）
 */

(function () {
  'use strict';

  const SHELF_WIDTH     = 80;   // 削除シェルフの幅 (px)
  const SNAP_THRESHOLD  = 50;   // この距離を超えたらシェルフを固定 (px)
  const VERTICAL_LIMIT  = 30;   // 縦移動がこれを超えたらスクロールと判定 (px)
  const HAPTIC_MS       = 15;

  let currentOpenCard = null; // 現在シェルフが開いているカード

  // ============================================================
  // スワイプハンドラのバインド
  // ============================================================
  function setupSwipeHandlers() {
    document.querySelectorAll('.note-card').forEach(function (card) {
      if (card._swipeDeleteSetup) return;
      card._swipeDeleteSetup = true;

      var inner = card.querySelector('.note-slide-content');
      if (!inner) return;

      var startX, startY, moveX = 0, isTracking = false, isScrolling = null;

      card.addEventListener('touchstart', function (e) {
        // 削除シェルフへのタップは除外（click で処理）
        if (e.target.closest('.note-delete-shelf')) return;
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
        moveX = 0;
        isTracking = true;
        isScrolling = null;
        inner.style.transition = 'none';
      }, { passive: true });

      card.addEventListener('touchmove', function (e) {
        if (!isTracking) return;

        var diffX = startX - e.touches[0].clientX; // 左スワイプで正
        var diffY = Math.abs(e.touches[0].clientY - startY);

        // 縦スクロール判定
        if (isScrolling === null) {
          isScrolling = diffY > VERTICAL_LIMIT;
        }
        if (isScrolling) {
          isTracking = false;
          snapBack(inner);
          return;
        }

        // 右スワイプ: 閉じる
        if (diffX < 0) {
          snapBack(inner);
          return;
        }

        e.preventDefault();
        moveX = Math.min(diffX, SHELF_WIDTH);
        inner.style.transform = 'translateX(-' + moveX + 'px)';
      }, { passive: false });

      card.addEventListener('touchend', function () {
        if (!isTracking) return;
        isTracking = false;

        if (moveX >= SNAP_THRESHOLD) {
          openShelf(card, inner);
        } else {
          snapBack(inner);
        }
      });
    });
  }

  // ============================================================
  // シェルフの開閉
  // ============================================================
  function openShelf(card, inner) {
    // 他に開いているシェルフを閉じる
    if (currentOpenCard && currentOpenCard !== card) {
      var prevInner = currentOpenCard.querySelector('.note-slide-content');
      if (prevInner) snapBack(prevInner);
    }

    inner.style.transition = 'transform 0.2s ease';
    inner.style.transform  = 'translateX(-' + SHELF_WIDTH + 'px)';
    currentOpenCard = card;

    if (navigator.vibrate) navigator.vibrate(HAPTIC_MS);

    // 削除シェルフのタップ: 一度だけバインド
    var shelf = card.querySelector('.note-delete-shelf');
    if (shelf && !shelf._tapBound) {
      shelf._tapBound = true;
      shelf.addEventListener('click', function () {
        snapBack(inner);
        currentOpenCard = null;

        if (typeof window.confirmDeleteNote === 'function') {
          window.confirmDeleteNote(
            parseInt(shelf.dataset.noteId, 10),
            shelf.dataset.noteDate,
            shelf.dataset.noteTypeLabel,
            parseInt(shelf.dataset.diaryId, 10)
          );
        }
      });
    }
  }

  function snapBack(inner) {
    inner.style.transition = 'transform 0.2s ease';
    inner.style.transform  = 'translateX(0)';
  }

  // カード外タップでシェルフを閉じる
  document.addEventListener('touchstart', function (e) {
    if (!currentOpenCard) return;
    if (!currentOpenCard.contains(e.target)) {
      var prevInner = currentOpenCard.querySelector('.note-slide-content');
      if (prevInner) snapBack(prevInner);
      currentOpenCard = null;
    }
  }, { passive: true });

  // ============================================================
  // 初期化
  // ============================================================
  document.addEventListener('DOMContentLoaded', function () {
    setupSwipeHandlers();
  });

  window.setupNoteSwipeDelete = setupSwipeHandlers;

}());
