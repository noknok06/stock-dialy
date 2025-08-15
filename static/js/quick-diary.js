/**
 * Enhanced Quick Diary Form - ステップ式UI対応
 * PC・スマホ両対応のモダンなクイック日記作成機能
 */

class EnhancedQuickDiaryForm {
  constructor() {
    // DOM要素の参照
    this.modal = document.getElementById('quickDiaryModal');
    this.form = document.getElementById('quickDiaryForm');
    this.progressBar = document.getElementById('quick-progress-bar');
    this.alertsContainer = document.getElementById('quick-diary-alerts');
    this.loadingOverlay = document.getElementById('form-loading');
    
    // 入力要素
    this.symbolInput = document.getElementById('quick_stock_symbol');
    this.nameInput = document.getElementById('quick_stock_name');
    this.sectorInput = document.getElementById('quick_sector');
    this.dateInput = document.getElementById('quick_purchase_date');
    this.priceInput = document.getElementById('quick_purchase_price');
    this.quantityInput = document.getElementById('quick_purchase_quantity');
    this.reasonInput = document.getElementById('quick_reason');
    this.tagsSelect = document.getElementById('quick_tags');
    
    // ボタン要素
    this.fetchInfoBtn = document.getElementById('quick_fetch_stock_info');
    this.fetchPriceBtn = document.getElementById('quick_fetch_price');
    this.submitBtn = document.getElementById('quickDiarySubmit');
    
    // 記録タイプ
    this.recordTypeInputs = document.querySelectorAll('input[name="record_type"]');
    
    // ステップ管理
    this.currentStep = 1;
    this.totalSteps = 3;
    this.steps = document.querySelectorAll('.form-step');
    this.stepIndicators = document.querySelectorAll('.step');
    
    // 状態管理
    this.isSubmitting = false;
    this.stockInfo = null;
    
    // 初期化
    this.init();
  }
  
  init() {
    if (!this.modal || !this.form) {
      console.warn('クイック日記モーダルが見つかりません');
      return;
    }
    
    // Bootstrap Modal インスタンス
    this.modalInstance = new bootstrap.Modal(this.modal, {
      backdrop: 'static',
      keyboard: false
    });
    
    // イベントリスナーの設定
    this.setupEventListeners();
    
    // 初期設定
    this.updateProgress();
    this.loadTags();
    
    console.log('Enhanced Quick Diary Form initialized');
  }
  
  setupEventListeners() {
    // モーダルイベント
    this.modal.addEventListener('shown.bs.modal', () => this.onModalShown());
    this.modal.addEventListener('hidden.bs.modal', () => this.onModalHidden());
    
    // ステップナビゲーション
    this.setupStepNavigation();
    
    // 記録タイプ変更
    this.recordTypeInputs.forEach(input => {
      input.addEventListener('change', () => this.onRecordTypeChange());
    });
    
    // 株式情報取得
    if (this.fetchInfoBtn) {
      this.fetchInfoBtn.addEventListener('click', () => this.fetchStockInfo());
    }
    
    if (this.fetchPriceBtn) {
      this.fetchPriceBtn.addEventListener('click', () => this.fetchCurrentPrice());
    }
    
    // 入力監視
    this.setupInputValidation();
    
    // 投資金額計算
    this.setupInvestmentCalculation();
    
    // フォーム送信
    this.form.addEventListener('submit', (e) => this.handleSubmit(e));
    
    // キーボードナビゲーション
    this.setupKeyboardNavigation();
  }
  
  setupStepNavigation() {
    // 次へボタン
    document.querySelectorAll('.btn-next').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const nextStep = parseInt(e.target.dataset.next);
        if (this.validateCurrentStep()) {
          this.goToStep(nextStep);
        }
      });
    });
    
    // 戻るボタン
    document.querySelectorAll('.btn-prev').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const prevStep = parseInt(e.target.dataset.prev);
        this.goToStep(prevStep);
      });
    });
  }
  
  setupInputValidation() {
    // リアルタイムバリデーション
    [this.symbolInput, this.nameInput, this.priceInput, this.quantityInput].forEach(input => {
      if (input) {
        input.addEventListener('input', () => this.validateInput(input));
        input.addEventListener('blur', () => this.validateInput(input));
      }
    });
    
    // 銘柄コード入力時のEnterキー
    if (this.symbolInput) {
      this.symbolInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          this.fetchStockInfo();
        }
      });
    }
    
    // 文字数カウンター
    if (this.reasonInput) {
      const counter = document.getElementById('reason-counter');
      this.reasonInput.addEventListener('input', () => {
        if (counter) {
          const length = this.reasonInput.value.length;
          counter.textContent = length;
          counter.parentElement.style.color = length > 1000 ? '#ef4444' : '#6b7280';
        }
      });
    }
  }
  
  setupInvestmentCalculation() {
    const updateCalculation = () => {
      const price = parseFloat(this.priceInput?.value || 0);
      const quantity = parseInt(this.quantityInput?.value || 0);
      
      if (price > 0 && quantity > 0) {
        const total = price * quantity;
        this.updateInvestmentPreview(total);
        this.updateInvestmentSummary();
      } else {
        this.hideInvestmentPreview();
      }
    };
    
    if (this.priceInput) {
      this.priceInput.addEventListener('input', updateCalculation);
    }
    if (this.quantityInput) {
      this.quantityInput.addEventListener('input', updateCalculation);
    }
  }
  
  setupKeyboardNavigation() {
    document.addEventListener('keydown', (e) => {
      if (!this.modal.classList.contains('show')) return;
      
      // Escapeキーでモーダルを閉じる（最初のステップのみ）
      if (e.key === 'Escape' && this.currentStep === 1) {
        this.hide();
      }
      
      // Ctrl+Enterで送信（最後のステップのみ）
      if (e.ctrlKey && e.key === 'Enter' && this.currentStep === this.totalSteps) {
        if (!this.isSubmitting) {
          this.handleSubmit(new Event('submit'));
        }
      }
    });
  }
  
  // ========== ステップ管理 ==========
  
  goToStep(stepNumber) {
    if (stepNumber < 1 || stepNumber > this.totalSteps) return;
    
    const currentStepEl = this.steps[this.currentStep - 1];
    const nextStepEl = this.steps[stepNumber - 1];
    
    // アニメーション方向を決定
    const isForward = stepNumber > this.currentStep;
    
    // 現在のステップを非表示
    currentStepEl.classList.remove('active');
    
    // 少し遅延してから次のステップを表示
    setTimeout(() => {
      nextStepEl.classList.add('active');
      nextStepEl.classList.add(isForward ? 'slide-in-right' : 'slide-in-left');
      
      // アニメーションクラスを削除
      setTimeout(() => {
        nextStepEl.classList.remove('slide-in-right', 'slide-in-left');
      }, 300);
    }, 150);
    
    // 状態更新
    this.currentStep = stepNumber;
    this.updateStepIndicators();
    this.updateProgress();
    this.updateMobileStepTitle();
    
    // ステップ別の初期化処理
    this.onStepChanged(stepNumber);
  }
  
  updateStepIndicators() {
    this.stepIndicators.forEach((indicator, index) => {
      const stepNum = index + 1;
      indicator.classList.remove('active', 'completed');
      
      if (stepNum === this.currentStep) {
        indicator.classList.add('active');
      } else if (stepNum < this.currentStep) {
        indicator.classList.add('completed');
      }
    });
  }
  
  updateProgress() {
    const progress = (this.currentStep / this.totalSteps) * 100;
    if (this.progressBar) {
      this.progressBar.style.width = `${progress}%`;
    }
  }
  
  updateMobileStepTitle() {
    const titleElement = document.querySelector('.step-title-mobile');
    const currentStepElement = document.querySelector('.current-step');
    
    if (currentStepElement) {
      currentStepElement.textContent = this.currentStep;
    }
    
    if (titleElement) {
      const titles = [
        '銘柄を選択してください',
        '価格情報を入力してください', 
        '詳細情報を入力してください'
      ];
      titleElement.textContent = titles[this.currentStep - 1] || '';
    }
  }
  
  onStepChanged(stepNumber) {
    switch (stepNumber) {
      case 1:
        // 銘柄入力にフォーカス
        setTimeout(() => this.symbolInput?.focus(), 300);
        break;
      
      case 2:
        // 日付を今日に設定（未設定の場合）
        if (this.dateInput && !this.dateInput.value) {
          this.dateInput.value = new Date().toISOString().split('T')[0];
        }
        this.onRecordTypeChange();
        break;
      
      case 3:
        // 投資サマリーを更新
        this.updateInvestmentSummary();
        break;
    }
  }
  
  validateCurrentStep() {
    switch (this.currentStep) {
      case 1:
        return this.validateStep1();
      case 2:
        return this.validateStep2();
      case 3:
        return this.validateStep3();
      default:
        return true;
    }
  }
  
  validateStep1() {
    const stockName = this.nameInput?.value?.trim();
    
    if (!stockName) {
      this.showAlert('銘柄名を入力してください', 'danger');
      this.nameInput?.focus();
      return false;
    }
    
    return true;
  }
  
  validateStep2() {
    const date = this.dateInput?.value;
    
    if (!date) {
      this.showAlert('日付を選択してください', 'danger');
      this.dateInput?.focus();
      return false;
    }
    
    // 売買記録の場合は価格・数量をチェック
    const recordType = document.querySelector('input[name="record_type"]:checked')?.value;
    if (recordType === 'trade') {
      const price = this.priceInput?.value;
      const quantity = this.quantityInput?.value;
      
      if (!price || parseFloat(price) <= 0) {
        this.showAlert('購入価格を入力してください', 'danger');
        this.priceInput?.focus();
        return false;
      }
      
      if (!quantity || parseInt(quantity) <= 0) {
        this.showAlert('購入数量を入力してください', 'danger');
        this.quantityInput?.focus();
        return false;
      }
    }
    
    return true;
  }
  
  validateStep3() {
    // 特に必須項目はない
    return true;
  }
  
  validateInput(input) {
    if (!input) return;
    
    input.classList.remove('is-invalid', 'is-valid');
    
    if (input.hasAttribute('required')) {
      if (input.value.trim()) {
        input.classList.add('is-valid');
      } else {
        input.classList.add('is-invalid');
      }
    }
  }
  
  // ========== 記録タイプ管理 ==========
  
  onRecordTypeChange() {
    const recordType = document.querySelector('input[name="record_type"]:checked')?.value;
    const priceQuantityArea = document.getElementById('price-quantity-area');
    const memoOnlyArea = document.getElementById('memo-only-area');
    
    if (recordType === 'memo') {
      // メモモード
      if (priceQuantityArea) priceQuantityArea.style.display = 'none';
      if (memoOnlyArea) memoOnlyArea.style.display = 'block';
      
      // 価格・数量をクリア
      if (this.priceInput) this.priceInput.value = '';
      if (this.quantityInput) this.quantityInput.value = '';
      
    } else {
      // 売買記録モード
      if (priceQuantityArea) priceQuantityArea.style.display = 'block';
      if (memoOnlyArea) memoOnlyArea.style.display = 'none';
    }
    
    this.updateInvestmentSummary();
  }
  
  // ========== 株式情報取得 ==========
  
  async fetchStockInfo() {
    const stockCode = this.symbolInput?.value?.trim();
    if (!stockCode) {
      this.showAlert('銘柄コードを入力してください', 'warning');
      return;
    }
    
    this.setLoading(this.fetchInfoBtn, true);
    this.showAlert('銘柄情報を取得中...', 'info');
    
    try {
      const response = await fetch(`/stockdiary/api/stock/info/${stockCode}/`);
      
      if (!response.ok) {
        throw new Error('銘柄情報の取得に失敗しました');
      }
      
      const data = await response.json();
      this.stockInfo = data;
      
      // フォームに情報を設定
      if (this.nameInput && data.company_name) {
        this.nameInput.value = data.company_name;
        this.validateInput(this.nameInput);
      }
      
      if (this.sectorInput && data.industry) {
        this.sectorInput.value = data.industry;
      }
      
      if (this.priceInput && data.price) {
        this.priceInput.value = data.price;
        this.validateInput(this.priceInput);
      }
      
      // 株式情報カードを表示
      this.displayStockInfo(data);
      
      this.showAlert(`${data.company_name} の情報を取得しました`, 'success');
      
    } catch (error) {
      console.error('Stock info fetch error:', error);
      
      if (!navigator.onLine) {
        this.showAlert('インターネット接続がありません。オフラインモードで続行します。', 'warning');
      } else {
        this.showAlert(`エラー: ${error.message}`, 'danger');
      }
    } finally {
      this.setLoading(this.fetchInfoBtn, false);
    }
  }
  
  async fetchCurrentPrice() {
    const stockCode = this.symbolInput?.value?.trim();
    if (!stockCode) {
      this.showAlert('銘柄コードを入力してください', 'warning');
      return;
    }
    
    this.setLoading(this.fetchPriceBtn, true);
    
    try {
      const response = await fetch(`/stockdiary/api/stock/price/${stockCode}/`);
      
      if (!response.ok) {
        throw new Error('価格の取得に失敗しました');
      }
      
      const data = await response.json();
      
      if (this.priceInput && data.price) {
        this.priceInput.value = data.price;
        this.validateInput(this.priceInput);
        
        // 投資金額を更新
        this.setupInvestmentCalculation();
      }
      
      this.showAlert(`現在価格: ${data.price?.toLocaleString()}円を取得しました`, 'success');
      
    } catch (error) {
      console.error('Price fetch error:', error);
      this.showAlert(`価格取得エラー: ${error.message}`, 'danger');
    } finally {
      this.setLoading(this.fetchPriceBtn, false);
    }
  }
  
  displayStockInfo(data) {
    const stockInfoCard = document.getElementById('stock-info-display');
    if (!stockInfoCard) return;
    
    // 各フィールドを更新
    const updateField = (id, value, formatter = null) => {
      const element = document.getElementById(id);
      if (element) {
        element.textContent = formatter ? formatter(value) : (value || '-');
      }
    };
    
    updateField('display-sector', data.industry);
    updateField('display-price', data.price, (price) => 
      price ? `${parseFloat(price).toLocaleString()}円` : '-'
    );
    updateField('display-change', data.change, (change) => {
      if (!change) return '-';
      const prefix = change > 0 ? '+' : '';
      return `${prefix}${change}`;
    });
    updateField('display-market', data.market);
    
    // カードを表示
    stockInfoCard.style.display = 'block';
    stockInfoCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  
  // ========== 投資計算 ==========
  
  updateInvestmentPreview(total) {
    const previewElement = document.getElementById('investment-preview');
    const amountElement = document.getElementById('preview-amount');
    
    if (previewElement && amountElement) {
      amountElement.textContent = `${total.toLocaleString()}円`;
      previewElement.style.display = 'block';
    }
  }
  
  hideInvestmentPreview() {
    const previewElement = document.getElementById('investment-preview');
    if (previewElement) {
      previewElement.style.display = 'none';
    }
  }
  
  updateInvestmentSummary() {
    const summaryElement = document.getElementById('investment-summary');
    if (!summaryElement) return;
    
    const recordType = document.querySelector('input[name="record_type"]:checked')?.value;
    
    if (recordType === 'trade') {
      const stockName = this.nameInput?.value || '-';
      const price = parseFloat(this.priceInput?.value || 0);
      const quantity = parseInt(this.quantityInput?.value || 0);
      const total = price * quantity;
      
      // サマリーを更新
      this.updateSummaryField('summary-stock', stockName);
      this.updateSummaryField('summary-price', price > 0 ? `${price.toLocaleString()}円` : '-');
      this.updateSummaryField('summary-quantity', quantity > 0 ? `${quantity}株` : '-');
      this.updateSummaryField('summary-amount', total > 0 ? `${total.toLocaleString()}円` : '-');
      
      summaryElement.style.display = 'block';
    } else {
      summaryElement.style.display = 'none';
    }
  }
  
  updateSummaryField(id, value) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = value;
    }
  }
  
  // ========== タグ管理 ==========
  
  async loadTags() {
    if (!this.tagsSelect) return;
    
    try {
      const response = await fetch('/tags/api/list/');
      if (!response.ok) throw new Error('タグの読み込みに失敗しました');
      
      const data = await response.json();
      
      // セレクトを初期化
      this.tagsSelect.innerHTML = '';
      
      if (data.tags && data.tags.length > 0) {
        data.tags.forEach(tag => {
          const option = document.createElement('option');
          option.value = tag.id;
          option.textContent = tag.name;
          this.tagsSelect.appendChild(option);
        });
      }
      
    } catch (error) {
      console.error('Tags loading error:', error);
    }
  }
  
  // ========== フォーム送信 ==========
  
  async handleSubmit(e) {
    e.preventDefault();
    
    if (this.isSubmitting) return;
    
    // 最終バリデーション
    if (!this.validateCurrentStep()) {
      return;
    }
    
    this.isSubmitting = true;
    this.setFormLoading(true);
    
    try {
      const formData = new FormData(this.form);
      
      // 記録タイプに応じてデータを調整
      const recordType = formData.get('record_type');
      if (recordType === 'memo') {
        formData.delete('purchase_price');
        formData.delete('purchase_quantity');
      }
      
      // 日付が設定されていない場合は今日の日付を設定
      if (!formData.get('purchase_date')) {
        formData.set('purchase_date', new Date().toISOString().split('T')[0]);
      }
      
      // CSRFトークンを追加
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
      
      const response = await fetch(this.form.action, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: formData
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || '日記の作成に失敗しました');
      }
      
      const data = await response.json();
      
      // 成功処理
      this.onSubmitSuccess(data);
      
    } catch (error) {
      console.error('Submit error:', error);
      this.showAlert(`エラー: ${error.message}`, 'danger');
    } finally {
      this.isSubmitting = false;
      this.setFormLoading(false);
    }
  }
  
  onSubmitSuccess(data) {
    this.showAlert('日記を作成しました！', 'success');
    
    // モーダルを閉じる
    setTimeout(() => {
      this.hide();
      
      // ページ遷移または更新
      if (data.redirect_url) {
        window.location.href = data.redirect_url;
      } else {
        window.location.reload();
      }
    }, 1000);
  }
  
  // ========== UI ユーティリティ ==========
  
  setLoading(button, isLoading) {
    if (!button) return;
    
    if (isLoading) {
      button.disabled = true;
      const icon = button.querySelector('i');
      if (icon) {
        icon.className = 'bi bi-arrow-repeat';
        icon.style.animation = 'spin 1s linear infinite';
      }
    } else {
      button.disabled = false;
      const icon = button.querySelector('i');
      if (icon) {
        icon.style.animation = '';
        // 元のアイコンに戻す（ボタンによって異なる）
        if (button.id === 'quick_fetch_stock_info') {
          icon.className = 'bi bi-search';
        } else if (button.id === 'quick_fetch_price') {
          icon.className = 'bi bi-arrow-clockwise';
        }
      }
    }
  }
  
  setFormLoading(isLoading) {
    if (this.loadingOverlay) {
      this.loadingOverlay.style.display = isLoading ? 'flex' : 'none';
    }
    
    if (this.submitBtn) {
      this.submitBtn.disabled = isLoading;
    }
  }
  
  showAlert(message, type = 'info') {
    if (!this.alertsContainer) return;
    
    // 既存のアラートをクリア
    this.alertsContainer.innerHTML = '';
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.innerHTML = `
      <div class="d-flex align-items-center">
        <i class="bi bi-${this.getAlertIcon(type)} me-2"></i>
        <span>${message}</span>
      </div>
    `;
    
    this.alertsContainer.appendChild(alertDiv);
    
    // 自動で消去（成功・情報メッセージのみ）
    if (type === 'success' || type === 'info') {
      setTimeout(() => {
        if (alertDiv.parentNode) {
          alertDiv.remove();
        }
      }, 5000);
    }
  }
  
  getAlertIcon(type) {
    const icons = {
      success: 'check-circle-fill',
      danger: 'exclamation-triangle-fill',
      warning: 'exclamation-triangle-fill',
      info: 'info-circle-fill'
    };
    return icons[type] || 'info-circle-fill';
  }
  
  // ========== モーダル管理 ==========
  
  show() {
    if (this.modalInstance) {
      this.modalInstance.show();
    }
  }
  
  hide() {
    if (this.modalInstance) {
      this.modalInstance.hide();
    }
  }
  
  onModalShown() {
    this.reset();
    this.goToStep(1);
    
    // フォーカス設定
    setTimeout(() => {
      this.symbolInput?.focus();
    }, 300);
  }
  
  onModalHidden() {
    this.reset();
  }
  
  reset() {
    // フォームリセット
    this.form.reset();
    
    // 状態リセット
    this.currentStep = 1;
    this.isSubmitting = false;
    this.stockInfo = null;
    
    // UI リセット
    this.alertsContainer.innerHTML = '';
    this.setFormLoading(false);
    
    // 日付を今日に設定
    if (this.dateInput) {
      this.dateInput.value = new Date().toISOString().split('T')[0];
    }
    
    // バリデーション状態をクリア
    this.form.querySelectorAll('.is-invalid, .is-valid').forEach(el => {
      el.classList.remove('is-invalid', 'is-valid');
    });
    
    // 株式情報カードを非表示
    const stockInfoCard = document.getElementById('stock-info-display');
    if (stockInfoCard) {
      stockInfoCard.style.display = 'none';
    }
    
    // 記録タイプを売買記録に設定
    const tradeRadio = document.getElementById('type_trade');
    if (tradeRadio) {
      tradeRadio.checked = true;
      this.onRecordTypeChange();
    }
    
    // 文字数カウンターリセット
    const counter = document.getElementById('reason-counter');
    if (counter) {
      counter.textContent = '0';
      counter.parentElement.style.color = '#6b7280';
    }
  }
}

// CSS アニメーション定義
const style = document.createElement('style');
style.textContent = `
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
`;
document.head.appendChild(style);

// ページロード時の初期化
document.addEventListener('DOMContentLoaded', function() {
  // グローバルインスタンスを作成
  window.enhancedQuickDiaryForm = new EnhancedQuickDiaryForm();
  
  // 既存のクイック作成ボタンを新しいインスタンスに接続
  const quickCreateButtons = document.querySelectorAll('.speed-dial-btn.action-quick-add');
  quickCreateButtons.forEach(btn => {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      
      if (window.enhancedQuickDiaryForm) {
        window.enhancedQuickDiaryForm.show();
      }
    });
  });
  
  // 下位互換性のため既存の変数名も維持
  window.quickDiaryForm = window.enhancedQuickDiaryForm;
});

// タッチデバイス用のスワイプサポート（オプション）
if ('ontouchstart' in window) {
  let touchStartX = 0;
  let touchEndX = 0;
  
  document.addEventListener('touchstart', function(e) {
    const modal = document.getElementById('quickDiaryModal');
    if (modal && modal.classList.contains('show')) {
      touchStartX = e.changedTouches[0].screenX;
    }
  });
  
  document.addEventListener('touchend', function(e) {
    const modal = document.getElementById('quickDiaryModal');
    if (modal && modal.classList.contains('show') && window.enhancedQuickDiaryForm) {
      touchEndX = e.changedTouches[0].screenX;
      const diff = touchStartX - touchEndX;
      
      // 50px以上のスワイプで反応
      if (Math.abs(diff) > 50) {
        if (diff > 0) {
          // 左スワイプ - 次のステップ
          const nextStep = window.enhancedQuickDiaryForm.currentStep + 1;
          if (nextStep <= window.enhancedQuickDiaryForm.totalSteps) {
            if (window.enhancedQuickDiaryForm.validateCurrentStep()) {
              window.enhancedQuickDiaryForm.goToStep(nextStep);
            }
          }
        } else {
          // 右スワイプ - 前のステップ
          const prevStep = window.enhancedQuickDiaryForm.currentStep - 1;
          if (prevStep >= 1) {
            window.enhancedQuickDiaryForm.goToStep(prevStep);
          }
        }
      }
    }
  });
}