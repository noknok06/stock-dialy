/**
 * card-swipe-note.js
 * ホームの diary カードヘッダーを左スワイプして
 * クイック継続記録（ボトムシート）を開く。
 *
 * 依存:
 *   - bottom-sheet.js : openBottomSheet / closeBottomSheet (home.html で読み込み済み)
 *   - toast.js        : showToast (home.html で読み込み済み)
 */

(function () {
  'use strict';

  const PANEL_WIDTH    = 80;   // アクションパネルの幅 (px)
  const SNAP_THRESHOLD = 60;   // この距離を超えたらパネルを固定 (px)
  const VERTICAL_LIMIT = 30;   // 縦移動がこれを超えたらスクロールと判定 (px)
  const HAPTIC_MS      = 15;

  let currentOpenHeader = null; // 現在アクションパネルが開いているヘッダー

  // ============================================================
  // スワイプハンドラのバインド
  // ============================================================
  function setupSwipeHandlers() {
    document.querySelectorAll('.diary-header').forEach(function (header) {
      if (header._swipeNoteSetup) return;
      header._swipeNoteSetup = true;

      var inner = header.querySelector('.diary-header-inner');
      if (!inner) return;

      var startX, startY, moveX = 0, isTracking = false, isScrolling = null;

      header.addEventListener('touchstart', function (e) {
        // アクションパネルへのタップは JS で処理するため除外
        if (e.target.closest('.note-action-panel')) return;
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
        moveX = 0;
        isTracking = true;
        isScrolling = null;
        inner.style.transition = 'none';
      }, { passive: true });

      header.addEventListener('touchmove', function (e) {
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

        // 右スワイプ: パネルを閉じる
        if (diffX < 0) {
          snapBack(inner);
          return;
        }

        e.preventDefault(); // 水平スクロールを防止
        moveX = Math.min(diffX, PANEL_WIDTH);
        inner.style.transform = 'translateX(-' + moveX + 'px)';
      }, { passive: false });

      header.addEventListener('touchend', function () {
        if (!isTracking) return;
        isTracking = false;

        if (moveX >= SNAP_THRESHOLD) {
          openPanel(header, inner);
        } else {
          snapBack(inner);
        }
      });

      // デスクトップ用「＋」ボタン
      var addBtn = header.querySelector('.note-add-btn');
      if (addBtn) {
        addBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          openSheet(header);
        });
      }
    });
  }

  // ============================================================
  // アクションパネルの開閉
  // ============================================================
  function openPanel(header, inner) {
    // 他に開いているパネルを閉じる
    if (currentOpenHeader && currentOpenHeader !== header) {
      closePanel(currentOpenHeader);
    }

    inner.style.transition = 'transform 0.2s ease';
    inner.style.transform  = 'translateX(-' + PANEL_WIDTH + 'px)';
    currentOpenHeader = header;
    if (navigator.vibrate) navigator.vibrate(HAPTIC_MS);

    // アクションパネルのタップ: 一度だけバインド
    var panel = header.querySelector('.note-action-panel');
    if (panel && !panel._tapBound) {
      panel._tapBound = true;
      panel.addEventListener('click', function () {
        snapBack(inner);
        currentOpenHeader = null;
        openSheet(header);
      });
    }
  }

  function closePanel(header) {
    var inner = header.querySelector('.diary-header-inner');
    if (inner) snapBack(inner);
  }

  function snapBack(inner) {
    inner.style.transition = 'transform 0.2s ease';
    inner.style.transform  = 'translateX(0)';
  }

  // ヘッダー外タップでパネルを閉じる
  document.addEventListener('touchstart', function (e) {
    if (!currentOpenHeader) return;
    if (!currentOpenHeader.contains(e.target)) {
      closePanel(currentOpenHeader);
      currentOpenHeader = null;
    }
  }, { passive: true });

  // ============================================================
  // ボトムシートを開く
  // ============================================================
  function openSheet(header) {
    var stockName = header.dataset.stockName || '';
    var noteUrl   = header.dataset.quickNoteUrl || '';

    var titleEl = document.getElementById('qnSheetTitle');
    if (titleEl) {
      titleEl.textContent = stockName ? stockName + '  継続記録を追加' : '継続記録を追加';
    }

    var urlInput = document.getElementById('qnNoteUrl');
    if (urlInput) urlInput.value = noteUrl;

    resetForm();

    if (typeof openBottomSheet === 'function') {
      openBottomSheet('quickNoteFromHomeSheet');
    }
  }

  function resetForm() {
    // ノートタイプ: analysis をデフォルト
    document.querySelectorAll('.qn-type-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.value === 'analysis');
    });
    // 重要度: medium をデフォルト
    document.querySelectorAll('.qn-importance-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.value === 'medium');
    });
    var ta = document.getElementById('qnContent');
    if (ta) { ta.value = ''; updateQnCharCount(); }
  }

  // ============================================================
  // フォーム送信
  // ============================================================
  function submitNote() {
    var urlInput  = document.getElementById('qnNoteUrl');
    var ta        = document.getElementById('qnContent');
    var typeBtn   = document.querySelector('.qn-type-btn.active');
    var impBtn    = document.querySelector('.qn-importance-btn.active');
    var submitBtn = document.getElementById('qnSubmitBtn');

    if (!urlInput || !ta || !urlInput.value) return;

    var content = ta.value.trim();
    if (!content) {
      if (typeof showToast === 'function') showToast('内容を入力してください', 'warning');
      return;
    }

    if (submitBtn) submitBtn.disabled = true;

    fetch(urlInput.value, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-CSRFToken': getCsrfToken(),
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        content:    content,
        note_type:  typeBtn ? typeBtn.dataset.value : 'analysis',
        importance: impBtn  ? impBtn.dataset.value  : 'medium',
      }),
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
      if (data.success) {
        if (typeof closeBottomSheet === 'function') {
          closeBottomSheet('quickNoteFromHomeSheet');
        }
        if (typeof showToast === 'function') showToast('継続記録を追加しました', 'success');
        incrementNoteBadge(urlInput.value);
      } else {
        if (typeof showToast === 'function') showToast(data.message || 'エラーが発生しました', 'danger');
      }
    })
    .catch(function () {
      if (typeof showToast === 'function') showToast('送信に失敗しました。もう一度お試しください。', 'danger');
    })
    .finally(function () {
      if (submitBtn) submitBtn.disabled = false;
    });
  }

  // ============================================================
  // 継続タブのバッジカウントを1増やす
  // ============================================================
  function incrementNoteBadge(url) {
    var match = url.match(/\/quick\/(\d+)\/note\//);
    if (!match) return;
    var diaryId = match[1];
    var badge = document.querySelector(
      '.diary-article[data-diary-id="' + diaryId + '"] ' +
      '[data-tab="notes-' + diaryId + '"] .tab-badge'
    );
    if (badge) {
      badge.textContent = parseInt(badge.textContent || '0', 10) + 1;
    }
  }

  // ============================================================
  // 文字数カウンター（グローバル公開）
  // ============================================================
  function updateQnCharCount() {
    var ta      = document.getElementById('qnContent');
    var counter = document.getElementById('qnCharCount');
    if (!ta || !counter) return;
    var len = ta.value.length;
    counter.textContent = len + ' / 3000';
    counter.classList.toggle('text-danger', len > 3000);
    counter.classList.toggle('text-warning', len > 2700 && len <= 3000);
  }

  // ============================================================
  // CSRF トークン取得
  // ============================================================
  function getCsrfToken() {
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el) return el.value;
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  // ============================================================
  // フッター「記録追加」ボタンのバインド
  // ============================================================
  function setupFooterButtons() {
    document.querySelectorAll('.note-add-footer-btn').forEach(function (btn) {
      if (btn._footerBound) return;
      btn._footerBound = true;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var selector = btn.dataset.diaryHeader;
        if (!selector) return;
        var header = document.querySelector(selector);
        if (header) openSheet(header);
      });
    });
  }

  // ============================================================
  // 初回訪問時スワイプヒント（セッション1回だけ）
  // ============================================================
  function showSwipeHintOnce() {
    // タッチデバイスのみ
    if (!('ontouchstart' in window)) return;
    // 1セッション1回だけ
    if (sessionStorage.getItem('swipe-hint-shown')) return;
    sessionStorage.setItem('swipe-hint-shown', '1');

    // 最初のカードの header-inner で peek
    var firstInner = document.querySelector('.diary-header .diary-header-inner');
    if (!firstInner) return;

    setTimeout(function () {
      firstInner.classList.add('swipe-peek');
      firstInner.addEventListener('animationend', function () {
        firstInner.classList.remove('swipe-peek');
      }, { once: true });
    }, 1800); // カード表示アニメーション後
  }

  // ============================================================
  // グローバル公開
  // ============================================================
  window.qnSubmitNote        = submitNote;
  window.updateQnCharCount   = updateQnCharCount;
  // フッターボタン等の外部から openSheet を呼べるよう公開
  window.openQuickNoteSheet  = openSheet;

  // ============================================================
  // 初期化
  // ============================================================
  document.addEventListener('DOMContentLoaded', function () {
    setupSwipeHandlers();
    setupFooterButtons();
    showSwipeHintOnce();
  });

  // HTMX の再レンダリング後にも再バインド
  document.addEventListener('htmx:afterSwap', function (e) {
    if (e.detail && e.detail.target && e.detail.target.id === 'diary-container') {
      setupSwipeHandlers();
      setupFooterButtons();
      showSwipeHintOnce();
    }
  });

}());
