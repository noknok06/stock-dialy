// static/js/quick-diary.js

/**
 * クイック日記作成機能
 * スピードダイアルから直接モーダルを表示して日記を作成する
 */
// static/js/quick-diary.js

/**
 * クイック日記作成機能
 * スピードダイアルから直接モーダルを表示して日記を作成する
 */
class QuickDiaryForm {
    constructor() {
      // 要素の参照
      this.modal = document.getElementById('quickDiaryModal');
      this.form = document.getElementById('quickDiaryForm');
      this.submitBtn = document.getElementById('quickDiarySubmit');
      this.symbolInput = document.getElementById('quick_stock_symbol');
      this.nameInput = document.getElementById('quick_stock_name');
      this.sectorInput = document.getElementById('quick_sector');
      this.priceInput = document.getElementById('quick_purchase_price');
      this.fetchInfoBtn = document.getElementById('quick_fetch_stock_info');
      this.fetchPriceBtn = document.getElementById('quick_fetch_price');
      this.feedbackEl = document.querySelector('.stock-info-feedback');
      this.formStatusEl = document.querySelector('.form-status-feedback');
      this.tagsSelect = document.getElementById('quick_tags');
      
      // 要素の存在チェック
      if (!this.modal || !this.form) {
        console.warn('クイック日記作成モーダルが見つかりません');
        return;
      }
      
      // モーダルのブートストラップインスタンス
      this.modalInstance = null;
      
      // イベントリスナーの設定
      this.initEventListeners();
      
      // タグデータの初期ロード
      this.loadTagsData();
    }
    
    /**
     * イベントリスナーの初期化
     */
    initEventListeners() {
      // モーダルの初期化
      this.modalInstance = new bootstrap.Modal(this.modal);
      
      // モーダルが表示されたときのイベント
      this.modal.addEventListener('shown.bs.modal', () => {
        // フォームをリセット
        this.resetForm();
        
        // 日付フィールドに明示的に今日の日付を設定
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('quick_purchase_date').value = today;
        
        // 最初のフィールドにフォーカス
        this.symbolInput.focus();
      });
      
      // 銘柄情報取得ボタンのクリックイベント
      if (this.fetchInfoBtn) {
        this.fetchInfoBtn.addEventListener('click', () => {
          this.fetchStockInfo();
        });
      }
      
      // 銘柄コード入力後のEnterキーイベント
      if (this.symbolInput) {
        this.symbolInput.addEventListener('keypress', (e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            this.fetchStockInfo();
          }
        });
      }
      
      // 現在価格取得ボタンのクリックイベント
      if (this.fetchPriceBtn) {
        this.fetchPriceBtn.addEventListener('click', () => {
          this.fetchCurrentPrice();
        });
      }
      
      // 送信ボタンのクリックイベント
      if (this.submitBtn) {
        this.submitBtn.addEventListener('click', () => {
          this.submitForm();
        });
      }
    }
    
    /**
     * モーダルを表示する
     */
    show() {
      if (this.modalInstance) {
        this.modalInstance.show();
      }
    }
    
    /**
     * モーダルを閉じる
     */
    hide() {
      if (this.modalInstance) {
        this.modalInstance.hide();
      }
    }
    
    /**
     * フォームをリセットする
     */// quick-diary.js の初期化部分に追加
    resetForm() {
        this.form.reset();
        
        // 日付を今日に設定
        const today = new Date().toISOString().split('T')[0];
        const dateInput = document.getElementById('quick_purchase_date');
        if (dateInput) {
        dateInput.value = today;
        }
        
        // フィードバックをクリア
        if (this.feedbackEl) {
        this.feedbackEl.innerHTML = '';
        this.feedbackEl.className = 'stock-info-feedback mt-1 small';
        }
        
        // 送信ステータスをリセット
        if (this.formStatusEl) {
        this.formStatusEl.classList.add('d-none');
        }
    }
    
    /**
     * タグデータを読み込む
     */
    async loadTagsData() {
        try {
          // console.log('タグデータの読み込みを開始します...');
          const response = await fetch('/tags/api/list/');
          
          if (!response.ok) {
            throw new Error(`タグの読み込みに失敗しました - ステータス: ${response.status}`);
          }
          
          const data = await response.json();
          // console.log('取得したタグデータ:', data);
          
          // タグのオプションを作成
          if (this.tagsSelect) {
            this.tagsSelect.innerHTML = '';
            
            if (data.tags && data.tags.length > 0) {
              data.tags.forEach(tag => {
                const option = document.createElement('option');
                option.value = tag.id;
                option.textContent = tag.name;
                this.tagsSelect.appendChild(option);
              });
              
            } else {
              // タグがない場合は「タグがありません」というオプションを追加
              const emptyOption = document.createElement('option');
              emptyOption.disabled = true;
              emptyOption.textContent = 'タグがありません';
              this.tagsSelect.appendChild(emptyOption);
            }
            
            // Select2があれば初期化（オプション）
            if (typeof $ !== 'undefined' && $.fn.select2) {
              $(this.tagsSelect).select2({
                placeholder: 'タグを選択...',
                width: '100%'
              });
            }
          } else {
          }
        } catch (error) {          
          // エラーが発生した場合の処理
          if (this.tagsSelect) {
            this.tagsSelect.innerHTML = '';
            const errorOption = document.createElement('option');
            errorOption.disabled = true;
            errorOption.textContent = 'タグの読み込みに失敗しました';
            this.tagsSelect.appendChild(errorOption);
          }
        }
      }
      
    
    /**
     * 銘柄情報を取得する
     */
    // quick-diary.js のfetchStockInfo関数内を修正
    async fetchStockInfo() {
        const stockCode = this.symbolInput.value.trim();
        
        try {
        // フィードバックを表示
        this.showFeedback('<i class="spinner-border spinner-border-sm me-1"></i> 銘柄情報を取得中...', 'info');
        
        // インターネット接続をチェック
        if (!navigator.onLine) {
            throw new Error('インターネット接続がありません');
        }
        
        // APIリクエスト
        const response = await fetch(`/stockdiary/api/stock/info/${stockCode}/`);
        
        if (!response.ok) {
            throw new Error('銘柄情報の取得に失敗しました');
        }
        
        const data = await response.json();
        
        // 銘柄名を設定
        if (this.nameInput && data.company_name) {
            this.nameInput.value = data.company_name;
        }
        
        // セクターを設定
        if (this.sectorInput && data.industry) {
            this.sectorInput.value = data.industry;
        }
        
        // 現在価格を設定
        if (this.priceInput && data.price) {
            this.priceInput.value = data.price;
        }
        
        // 成功フィードバック
        this.showFeedback(`<i class="bi bi-check-circle text-success"></i> ${data.company_name} の情報を取得しました`, 'success');
        } catch (error) {
        // インターネット接続エラーを特別に処理
        if (!navigator.onLine || error.message.includes('ERR_INTERNET_DISCONNECTED')) {
            this.showFeedback(`<i class="bi bi-wifi-off text-warning"></i> インターネット接続がありません。オフラインモードで続行します。`, 'warning');
            
            // 入力された銘柄コードだけでも使用できるようにする
            if (stockCode) {
            if (this.nameInput && !this.nameInput.value) {
                this.nameInput.value = `${stockCode} (オフライン)`;
            }
            }
            return;
        }
        
        // その他のエラーフィードバック
        this.showFeedback(`<i class="bi bi-exclamation-triangle text-danger"></i> ${error.message}`, 'danger');
        }
    }
    
    /**
     * 現在価格を取得する
     */
    async fetchCurrentPrice() {
      const stockCode = this.symbolInput.value.trim();
      
      if (!stockCode) {
        this.showFeedback('銘柄コードを入力してください', 'warning');
        return;
      }
      
      try {
        // フィードバックを表示
        this.showFeedback('<i class="spinner-border spinner-border-sm me-1"></i> 現在価格を取得中...', 'info');
        
        // APIリクエスト
        const response = await fetch(`/stockdiary/api/stock/price/${stockCode}/`);
        
        if (!response.ok) {
          throw new Error('価格の取得に失敗しました');
        }
        
        const data = await response.json();
        
        // 価格を設定
        if (this.priceInput && data.price) {
          this.priceInput.value = data.price;
        }
        
        // 成功フィードバック
        this.showFeedback(`<i class="bi bi-check-circle text-success"></i> 現在価格: ${data.price.toLocaleString()}円`, 'success');
      } catch (error) {
        // エラーフィードバック
        this.showFeedback(`<i class="bi bi-exclamation-triangle text-danger"></i> ${error.message}`, 'danger');
      }
    }
    
    /**
     * フィードバックを表示する
     * @param {string} message - メッセージ
     * @param {string} type - メッセージタイプ (success, info, warning, danger)
     */
    showFeedback(message, type = 'info') {
      if (!this.feedbackEl) return;
      
      this.feedbackEl.innerHTML = message;
      this.feedbackEl.className = `stock-info-feedback mt-1 small text-${type}`;
    }
    
    /**
     * フォームを送信する
     */
    async submitForm() {
        // バリデーション
        if (!this.validateForm()) {
          return;
        }
        
        // 送信中の状態を表示
        if (this.formStatusEl) {
          this.formStatusEl.classList.remove('d-none');
        }
        
        // 送信ボタンを無効化
        if (this.submitBtn) {
          this.submitBtn.disabled = true;
        }
        
        try {
          // CSRFトークンの取得
          const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
          
          // フォームデータを準備
          const formData = new FormData(this.form);
          
          // 日付が正しく設定されているか確認
          const purchaseDate = formData.get('purchase_date');
          if (!purchaseDate) {
            // 日付が設定されていない場合は現在の日付を設定
            const today = new Date().toISOString().split('T')[0];
            formData.set('purchase_date', today);
            // console.log('日付が設定されていないため、現在の日付を使用します:', today);
          }
          
          // APIリクエスト
          const response = await fetch(this.form.action, {
            method: 'POST',
            headers: {
              'X-CSRFToken': csrfToken,
              'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData
          });
        
        // レスポンスを解析
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.message || '日記の作成に失敗しました');
        }
        
        const data = await response.json();
        
        // 成功時の処理
        // トースト通知を表示
        this.showToast('日記を作成しました', 'success');

        // モーダルを閉じる
        this.hide();

        // 日記リストがある場合は新しい日記カードを直接追加
        const diaryContainer = document.getElementById('diary-container');
        if (diaryContainer && data.diary_html) {
        // テンプレートHTML文字列からDOM要素を作成
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = data.diary_html.trim();
        
        // 最初の子要素（日記カード）を取得
        const newDiaryCard = tempDiv.firstElementChild;
        
        if (newDiaryCard) {
            // 日記コンテナの先頭に新しい日記を追加
            diaryContainer.insertBefore(newDiaryCard, diaryContainer.firstChild);
            
            // 新しく追加された要素のイベントリスナーなどを初期化
            if (typeof initializeNewElements === 'function') {
            initializeNewElements(newDiaryCard);
            }
            
            // カードタブの初期化（もし該当関数があれば）
            if (typeof initDiaryCardTabs === 'function') {
            initDiaryCardTabs(newDiaryCard);
            }
            
            // アニメーションで注目を集める
            newDiaryCard.classList.add('new-diary-highlight');
            setTimeout(() => {
            newDiaryCard.classList.remove('new-diary-highlight');
            }, 3000);
            
            // 該当する日記カードまでスクロール
            setTimeout(() => {
            newDiaryCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 200);
            
            return; // 日記カード追加に成功したらここで終了
          }
          // 日記カードの直接追加に失敗した場合は、従来通りのリダイレクトまたはリロード
          if (data.redirect_url) {
            // 作成された日記の詳細ページに遷移
            window.location.href = data.redirect_url;
          } else {
            // または現在のページをリロード
            window.location.reload();
          }
        }
        
        // 日記カードの直接追加に失敗した場合は、従来通りのリダイレクトまたはリロード
        if (data.redirect_url) {
          // 作成された日記の詳細ページに遷移
          window.location.href = data.redirect_url;
        } else {
          // または現在のページをリロード
          window.location.reload();
        }
      } catch (error) {
        // エラー時の処理
        this.showToast(error.message, 'danger');
        
        // 送信状態を元に戻す
        if (this.formStatusEl) {
          this.formStatusEl.classList.add('d-none');
        }
        
        // 送信ボタンを有効化
        if (this.submitBtn) {
          this.submitBtn.disabled = false;
        }
      }
    }
    
    /**
     * フォームのバリデーション
     * @returns {boolean} バリデーション結果
     */
    validateForm() {
      // 必須フィールドのチェック
      const requiredFields = this.form.querySelectorAll('[required]');
      let isValid = true;
      
      requiredFields.forEach(field => {
        if (!field.value.trim()) {
          isValid = false;
          field.classList.add('is-invalid');
          
          // エラーフィードバックの表示
          let feedbackEl = field.nextElementSibling;
          if (!feedbackEl || !feedbackEl.classList.contains('invalid-feedback')) {
            feedbackEl = document.createElement('div');
            feedbackEl.className = 'invalid-feedback';
            field.parentNode.insertBefore(feedbackEl, field.nextSibling);
          }
          
          feedbackEl.textContent = '入力が必要です';
        } else {
          field.classList.remove('is-invalid');
        }
      });
      
      return isValid;
    }
    
    /**
     * トースト通知を表示する
     * @param {string} message - メッセージ
     * @param {string} type - メッセージタイプ (success, info, warning, danger)
     */
    showToast(message, type = 'success') {
      // 既存のトーストを削除
      const existingToast = document.querySelector('.toast-notification');
      if (existingToast) {
        existingToast.remove();
      }
      
      // トースト要素を作成
      const toast = document.createElement('div');
      toast.className = `toast-notification toast align-items-center text-white bg-${type} border-0 show`;
      toast.role = 'alert';
      toast.setAttribute('aria-live', 'assertive');
      toast.setAttribute('aria-atomic', 'true');
      
      const icon = type === 'success' ? 'bi-check-circle' : 'bi-exclamation-triangle';
      
      toast.innerHTML = `
        <div class="d-flex">
          <div class="toast-body">
            <i class="bi ${icon} me-2"></i> ${message}
          </div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
      `;
      
      // スタイル調整
      toast.style.position = 'fixed';
      toast.style.bottom = '20px';
      toast.style.right = '20px';
      toast.style.minWidth = '250px';
      toast.style.zIndex = '1050';
      
      // DOMに追加
      document.body.appendChild(toast);
      
      // 5秒後に自動的に消す
      setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
      }, 5000);
    }
  }
  
  // ページロード時に初期化
  document.addEventListener('DOMContentLoaded', function() {
    // グローバルインスタンスを作成
    window.quickDiaryForm = new QuickDiaryForm();
    
    // スピードダイアルの「新規作成」ボタンにイベントリスナーを追加
    const createButtons = document.querySelectorAll('.speed-dial-btn.action-quick-add');
    createButtons.forEach(btn => {
      btn.addEventListener('click', function(e) {
        // デフォルトのリンク動作をキャンセル
        e.preventDefault();
        e.stopPropagation(); // イベントの伝播も停止
        
        if (window.quickDiaryForm) {
          window.quickDiaryForm.show();
        }
      });
    });
    
    // 「詳細作成」ボタンに正しいURLへの遷移を確保
    const detailCreateButtons = document.querySelectorAll('.speed-dial-btn.action-add');
    detailCreateButtons.forEach(btn => {
      // 既存のイベントリスナーを確認
      if (btn.getAttribute('data-has-listeners') !== 'true') {
        btn.setAttribute('data-has-listeners', 'true');
        // クリックイベントをクリア
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
      }
    });
  });

  // quick_diary.js に追加または修正する部分

/**
 * モーダルが表示されたときのイベント - スワイプヒントの表示/非表示を制御
 */
this.modal.addEventListener('shown.bs.modal', () => {
  // フォームをリセット
  this.resetForm();
  
  // 日付フィールドに明示的に今日の日付を設定
  const today = new Date().toISOString().split('T')[0];
  document.getElementById('quick_purchase_date').value = today;
  
  // 最初のフィールドにフォーカス
  setTimeout(() => {
    this.symbolInput.focus();
  }, 300);
  
  // モバイルデバイスかどうかをチェック
  const isMobile = window.innerWidth < 768 || navigator.maxTouchPoints > 1;
  
  // スワイプヒントの表示/非表示
  const swipeHint = this.modal.querySelector('.swipe-hint');
  if (swipeHint) {
    if (isMobile) {
      // モバイルデバイスではスワイプヒントを表示
      swipeHint.style.display = 'block';
      
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