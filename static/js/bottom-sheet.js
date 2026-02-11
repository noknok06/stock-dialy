/**
 * Bottom Sheet Component
 * ネイティブアプリ風ボトムシート
 * - ドラッグで閉じる
 * - ステップ式フォーム
 * - オートコンプリート
 */

class BottomSheet {
  constructor(elementId, options = {}) {
    this.elementId = elementId;
    this.sheet = document.getElementById(elementId);

    if (!this.sheet) {
      console.warn(`BottomSheet: Element #${elementId} not found`);
      return;
    }

    this.backdrop = this.sheet.querySelector('.bottom-sheet-backdrop');
    this.content = this.sheet.querySelector('.bottom-sheet-content');
    this.handle = this.sheet.querySelector('.bottom-sheet-handle');
    this.body = this.sheet.querySelector('.bottom-sheet-body');

    // オプション
    this.options = {
      closeOnBackdrop: true,
      closeOnEscape: true,
      enableDrag: true,
      dragThreshold: 100,
      enableHaptics: true,
      onOpen: null,
      onClose: null,
      ...options
    };

    // ドラッグ関連
    this.startY = 0;
    this.currentY = 0;
    this.isDragging = false;

    // ステップ関連
    this.currentStep = 1;
    this.totalSteps = this.sheet.querySelectorAll('.form-step').length || 1;

    this.init();
  }

  // ========== 初期化 ==========
  init() {
    // Backdropクリックで閉じる
    if (this.backdrop && this.options.closeOnBackdrop) {
      this.backdrop.addEventListener('click', () => this.close());
    }

    // 閉じるボタン
    const closeBtn = this.sheet.querySelector('.btn-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => this.close());
    }

    // ドラッグ操作
    if (this.handle && this.options.enableDrag) {
      this.setupDragHandlers();
    }

    // ESCキーで閉じる
    if (this.options.closeOnEscape) {
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.sheet.classList.contains('active')) {
          this.close();
        }
      });
    }

    // ステップナビゲーション
    this.setupStepNavigation();

    // body内のスクロールを制御
    this.setupScrollBehavior();
  }

  // ========== ドラッグハンドラー ==========
  setupDragHandlers() {
    // タッチイベント
    this.handle.addEventListener('touchstart', (e) => this.onDragStart(e), { passive: true });
    this.handle.addEventListener('touchmove', (e) => this.onDragMove(e), { passive: false });
    this.handle.addEventListener('touchend', () => this.onDragEnd());
    this.handle.addEventListener('touchcancel', () => this.onDragEnd());

    // マウスイベント（デスクトップ対応）
    this.handle.addEventListener('mousedown', (e) => this.onDragStart(e));
    document.addEventListener('mousemove', (e) => {
      if (this.isDragging) this.onDragMove(e);
    });
    document.addEventListener('mouseup', () => {
      if (this.isDragging) this.onDragEnd();
    });
  }

  onDragStart(e) {
    this.startY = e.touches ? e.touches[0].clientY : e.clientY;
    this.isDragging = true;
    this.handle.style.cursor = 'grabbing';
    this.content.style.transition = 'none';
  }

  onDragMove(e) {
    if (!this.isDragging) return;

    // スクロール位置が一番上の場合のみドラッグ可能
    if (this.body && this.body.scrollTop > 0) {
      return;
    }

    this.currentY = e.touches ? e.touches[0].clientY : e.clientY;
    const diff = this.currentY - this.startY;

    // 下方向のドラッグのみ許可
    if (diff > 0) {
      e.preventDefault();
      this.content.style.transform = `translateY(${diff}px)`;
    }
  }

  onDragEnd() {
    if (!this.isDragging) return;

    const diff = this.currentY - this.startY;

    this.content.style.transition = '';
    this.isDragging = false;
    this.handle.style.cursor = 'grab';

    // 閾値を超えたら閉じる
    if (diff > this.options.dragThreshold) {
      this.close();
    } else {
      this.content.style.transform = '';
    }
  }

  // ========== スクロール制御 ==========
  setupScrollBehavior() {
    if (!this.body) return;

    // iOS Safari対策: ボディ外へのスクロール伝播を防ぐ
    this.body.addEventListener('touchstart', () => {
      const scrollTop = this.body.scrollTop;
      const scrollHeight = this.body.scrollHeight;
      const height = this.body.clientHeight;
      const atTop = scrollTop === 0;
      const atBottom = scrollTop + height >= scrollHeight;

      if (atTop) {
        this.body.scrollTop = 1;
      } else if (atBottom) {
        this.body.scrollTop = scrollHeight - height - 1;
      }
    }, { passive: true });
  }

  // ========== ステップナビゲーション ==========
  setupStepNavigation() {
    const prevBtn = this.sheet.querySelector('#prevBtn');
    const nextBtn = this.sheet.querySelector('#nextBtn');
    const submitBtn = this.sheet.querySelector('#submitBtn');

    if (prevBtn) {
      prevBtn.addEventListener('click', () => this.prevStep());
    }

    if (nextBtn) {
      nextBtn.addEventListener('click', () => this.nextStep());
    }

    // 初期状態の更新
    if (this.totalSteps > 1) {
      this.updateSteps();
    }
  }

  nextStep() {
    if (this.currentStep < this.totalSteps) {
      // バリデーション
      if (!this.validateStep(this.currentStep)) {
        return;
      }

      this.currentStep++;
      this.updateSteps();
      this.hapticFeedback('light');

      // 次のステップの最初の入力欄にフォーカス
      this.focusFirstInput();
    }
  }

  prevStep() {
    if (this.currentStep > 1) {
      this.currentStep--;
      this.updateSteps();
      this.hapticFeedback('light');
      this.focusFirstInput();
    }
  }

  updateSteps() {
    // ステップ表示を更新
    const steps = this.sheet.querySelectorAll('.form-step');
    steps.forEach((step, index) => {
      if (index + 1 === this.currentStep) {
        step.classList.add('active');
      } else {
        step.classList.remove('active');
      }
    });

    // インジケーター更新
    const indicators = this.sheet.querySelectorAll('.step-indicator .step');
    indicators.forEach((indicator, index) => {
      if (index + 1 < this.currentStep) {
        indicator.classList.add('completed');
        indicator.classList.remove('active');
        indicator.innerHTML = '<i class="bi bi-check-lg"></i>';
      } else if (index + 1 === this.currentStep) {
        indicator.classList.add('active');
        indicator.classList.remove('completed');
        indicator.textContent = index + 1;
      } else {
        indicator.classList.remove('active', 'completed');
        indicator.textContent = index + 1;
      }
    });

    // ボタン表示制御
    const prevBtn = this.sheet.querySelector('#prevBtn');
    const nextBtn = this.sheet.querySelector('#nextBtn');
    const submitBtn = this.sheet.querySelector('#submitBtn');

    if (prevBtn) {
      prevBtn.style.display = this.currentStep === 1 ? 'none' : 'flex';
    }

    if (nextBtn) {
      nextBtn.style.display = this.currentStep === this.totalSteps ? 'none' : 'flex';
    }

    if (submitBtn) {
      submitBtn.style.display = this.currentStep === this.totalSteps ? 'flex' : 'none';
    }
  }

  validateStep(step) {
    const currentStepEl = this.sheet.querySelector(`.form-step[data-step="${step}"]`);
    if (!currentStepEl) return true;

    // Step 1は銘柄名が任意になったのでバリデーション不要
    if (step === 1) {
      return true;
    }

    // 必須フィールドのチェック（Step 2, 3）
    const requiredInputs = currentStepEl.querySelectorAll('[required]');
    for (const input of requiredInputs) {
      if (!input.value.trim()) {
        input.focus();
        this.showError(input, `${input.placeholder || 'この項目'}を入力してください`);
        this.hapticFeedback('error');
        return false;
      }
    }

    return true;
  }

  showError(input, message) {
    // エラー表示（既存のエラー要素を削除）
    const existingError = input.parentElement.querySelector('.error-message');
    if (existingError) {
      existingError.remove();
    }

    // 新しいエラーメッセージを表示
    const errorEl = document.createElement('div');
    errorEl.className = 'error-message text-danger small mt-1';
    errorEl.textContent = message;
    input.parentElement.appendChild(errorEl);

    // 入力フィールドにエラースタイル
    input.style.borderColor = 'var(--danger-color, #ef4444)';

    // 入力時にエラーを解除
    const clearError = () => {
      errorEl.remove();
      input.style.borderColor = '';
      input.removeEventListener('input', clearError);
    };
    input.addEventListener('input', clearError);
  }

  focusFirstInput() {
    setTimeout(() => {
      const currentStepEl = this.sheet.querySelector(`.form-step[data-step="${this.currentStep}"]`);
      if (currentStepEl) {
        const firstInput = currentStepEl.querySelector('input, textarea, select');
        if (firstInput) {
          firstInput.focus();
        }
      }
    }, 100);
  }

  // ========== 開く・閉じる ==========
  open() {
    this.sheet.classList.add('active');
    document.body.style.overflow = 'hidden'; // 背景スクロール防止

    // フォーカスを最初の入力欄に
    this.focusFirstInput();

    // 触覚フィードバック
    this.hapticFeedback('open');

    // コールバック
    if (typeof this.options.onOpen === 'function') {
      this.options.onOpen(this);
    }

    // ARIAステート
    this.sheet.setAttribute('aria-hidden', 'false');
  }

  close() {
    this.sheet.classList.remove('active');
    document.body.style.overflow = '';

    // リセット
    this.currentStep = 1;
    this.updateSteps();
    this.content.style.transform = '';

    // 触覚フィードバック
    this.hapticFeedback('close');

    // コールバック
    if (typeof this.options.onClose === 'function') {
      this.options.onClose(this);
    }

    // ARIAステート
    this.sheet.setAttribute('aria-hidden', 'true');
  }

  toggle() {
    if (this.sheet.classList.contains('active')) {
      this.close();
    } else {
      this.open();
    }
  }

  // ========== 触覚フィードバック ==========
  hapticFeedback(type = 'light') {
    if (!this.options.enableHaptics || !navigator.vibrate) return;

    // prefers-reduced-motionをチェック
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const patterns = {
      light: [5],
      medium: [10],
      open: [10],
      close: [5],
      error: [20, 10, 20]
    };

    navigator.vibrate(patterns[type] || patterns.light);
  }

  // ========== ユーティリティ ==========
  reset() {
    // フォームをリセット
    const form = this.sheet.querySelector('form');
    if (form) {
      form.reset();
    }

    // ステップを最初に戻す
    this.currentStep = 1;
    this.updateSteps();

    // エラーメッセージを削除
    const errors = this.sheet.querySelectorAll('.error-message');
    errors.forEach(error => error.remove());
  }

  destroy() {
    // イベントリスナーをクリーンアップ
    // （実装省略: 必要に応じて追加）
  }
}

// ========== グローバル関数（便利メソッド） ==========

function openBottomSheet(id) {
  const sheetId = id || 'quickRecordSheet';

  if (!window.bottomSheets) {
    window.bottomSheets = {};
  }

  if (!window.bottomSheets[sheetId]) {
    window.bottomSheets[sheetId] = new BottomSheet(sheetId);
  }

  window.bottomSheets[sheetId].open();
}

function closeBottomSheet(id) {
  const sheetId = id || 'quickRecordSheet';

  if (window.bottomSheets && window.bottomSheets[sheetId]) {
    window.bottomSheets[sheetId].close();
  }
}

function nextStep() {
  // デフォルトはquickRecordSheet
  if (window.bottomSheets && window.bottomSheets.quickRecordSheet) {
    window.bottomSheets.quickRecordSheet.nextStep();
  }
}

function prevStep() {
  if (window.bottomSheets && window.bottomSheets.quickRecordSheet) {
    window.bottomSheets.quickRecordSheet.prevStep();
  }
}

// ========== Speed Dial統合用関数 ==========

function openQuickRecordSheet() {
  openBottomSheet('quickRecordSheet');
}

// ========== 自動初期化（DOMContentLoaded） ==========

document.addEventListener('DOMContentLoaded', function() {
  // ページ内のすべてのボトムシートを検出して初期化
  const sheets = document.querySelectorAll('.bottom-sheet');

  if (!window.bottomSheets) {
    window.bottomSheets = {};
  }

  sheets.forEach(sheet => {
    if (sheet.id && !window.bottomSheets[sheet.id]) {
      window.bottomSheets[sheet.id] = new BottomSheet(sheet.id);
    }
  });
});
